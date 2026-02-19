"""
Backend Chatterbox TTS: genera audio desde texto.
Usa ChatterboxMultilingualTTS (23 idiomas); opcional audio_prompt_path para clonar voz.
Parámetros de voz: language_id, exaggeration, temperature, cfg_weight, etc.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Optional

from shared.config import settings

logger = logging.getLogger(__name__)

_model = None

# Reexportar para GET /languages
SUPPORTED_LANGUAGES = None


def _get_device() -> str:
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return "mps"
    except Exception:
        pass
    return "cpu"


def get_model():
    """Carga el modelo Chatterbox Multilingual TTS una sola vez (lazy)."""
    global _model, SUPPORTED_LANGUAGES
    if _model is not None:
        return _model
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS, SUPPORTED_LANGUAGES as _LANGS
        SUPPORTED_LANGUAGES = _LANGS
    except ImportError as e:
        raise RuntimeError(
            "Instala chatterbox-tts: pip install chatterbox-tts. "
            "Revisa dependencias (torch, torchaudio)."
        ) from e
    # Usar dispositivo disponible; si se pidió cuda pero no hay CUDA, usar cpu
    device = _get_device()
    if settings.device in ("cuda", "cpu", "mps") and settings.device != device:
        if settings.device == "cuda" and device == "cpu":
            logger.warning("CUDA no disponible (torch sin CUDA), usando CPU.")
        else:
            device = settings.device
    logger.info("Cargando Chatterbox Multilingual TTS en %s...", device)
    # En CPU, el paquete chatterbox hace torch.load() sin map_location y falla si los pesos vienen de CUDA
    import torch
    _orig_torch_load = torch.load
    if device == "cpu":
        def _torch_load_cpu(*args, **kwargs):
            if "map_location" not in kwargs:
                kwargs = {**kwargs, "map_location": torch.device("cpu")}
            return _orig_torch_load(*args, **kwargs)
        torch.load = _torch_load_cpu
    try:
        _model = ChatterboxMultilingualTTS.from_pretrained(device=device)
    finally:
        if device == "cpu":
            torch.load = _orig_torch_load
    return _model


def get_supported_languages() -> dict[str, str]:
    """Devuelve dict código -> nombre de idiomas soportados."""
    if SUPPORTED_LANGUAGES is not None:
        return SUPPORTED_LANGUAGES
    try:
        from chatterbox.mtl_tts import SUPPORTED_LANGUAGES as _LANGS
        return _LANGS
    except ImportError:
        return {"en": "English"}


def generate_audio(
    text: str,
    *,
    output_path: Optional[Path] = None,
    audio_prompt_path: Optional[str] = None,
    language_id: Optional[str] = "en",
    exaggeration: float = 0.4,
    cfg_weight: float = 0.5,
    temperature: float = 0.6,
    repetition_penalty: float = 2.0,
    min_p: float = 0.05,
    top_p: float = 1.0,
    speed: float = 1.0,
) -> tuple[bytes, int, Path]:
    """
    Genera audio WAV desde texto y lo guarda en output_path.
    Siempre escribe el .wav en disco cuando la generación es correcta.

    Args:
        text: Texto a sintetizar.
        output_path: Ruta del archivo WAV de salida.
        audio_prompt_path: Ruta a un WAV de referencia para clonar voz (opcional).
        language_id: Código de idioma (en, es, fr, ...). Por defecto "en".
        exaggeration: Intensidad emocional (0.0–2.0, default 0.4; más bajo = más sobrio).
        cfg_weight: Peso CFG / ritmo (0.0–1.0, default 0.5).
        temperature: Temperatura de muestreo (default 0.6; más bajo = más claro y articulado).
        repetition_penalty, min_p, top_p: Parámetros de generación.
        speed: Ritmo de habla (1.0 = normal). < 1 = más pausado (narrar), > 1 = más rápido.

    Returns:
        (wav_bytes, sample_rate, path_dest)
    """
    import torchaudio as ta

    model = get_model()
    if not text or not text.strip():
        raise ValueError("El texto no puede estar vacío.")

    lang = (language_id or "en").strip().lower() or "en"
    start = time.perf_counter()
    wav = model.generate(
        text.strip(),
        language_id=lang,
        audio_prompt_path=audio_prompt_path or None,
        exaggeration=exaggeration,
        cfg_weight=cfg_weight,
        temperature=temperature,
        repetition_penalty=repetition_penalty,
        min_p=min_p,
        top_p=top_p,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Aplicar ritmo (speed): < 1 = más pausado para narrar, > 1 = más rápido
    if speed is not None and abs(speed - 1.0) > 1e-6:
        import torch as _torch
        import librosa
        wav_np = wav.squeeze(0).cpu().numpy()
        wav_np = librosa.effects.time_stretch(wav_np, rate=speed)
        wav = _torch.from_numpy(wav_np).unsqueeze(0)

    # Normalizar loudness para que suene claro y uniforme (target -16 LUFS para voz)
    import torch as _torch
    import numpy as np
    wav_np = wav.squeeze(0).cpu().numpy()
    try:
        import pyloudnorm as pyln
        sr = model.sr
        if wav_np.size >= sr * 2:  # al menos ~2 s para medir LUFS
            meter = pyln.Meter(sr)
            loudness = meter.integrated_loudness(wav_np)
            if np.isfinite(loudness) and loudness > -60:
                wav_np = pyln.normalize.loudness(wav_np, loudness, -16.0)
        wav_np = np.clip(wav_np, -1.0, 1.0).astype(np.float32)
    except Exception as e:
        logger.warning("No se pudo normalizar loudness: %s", e)
    wav = _torch.from_numpy(wav_np).unsqueeze(0)

    if output_path is None:
        output_path = settings.output_dir / f"chatterbox_{int(time.time())}.wav"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ta.save(str(output_path), wav, model.sr)
    if not output_path.is_file():
        raise RuntimeError(f"No se pudo escribir el archivo de audio: {output_path}")
    with open(output_path, "rb") as f:
        wav_bytes = f.read()

    logger.info("Audio generado: %s (%d bytes, %d ms)", output_path.name, len(wav_bytes), elapsed_ms)
    return wav_bytes, model.sr, output_path.resolve()
