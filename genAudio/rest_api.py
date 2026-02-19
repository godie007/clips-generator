"""
REST API para generacion de audio: POST /generate (text -> WAV).
Devuelve JSON con success, filename, audio_path, base64_audio para n8n.
"""
from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from shared.config import settings
from backends.chatterbox import generate_audio, get_supported_languages


async def health(_request):
    """GET /health: comprueba que el servicio esta listo (y opcionalmente el modelo)."""
    try:
        from backends.chatterbox import get_model
        get_model()
        return JSONResponse({"ok": True, "message": "Chatterbox TTS listo.", "model_loaded": True})
    except Exception as e:
        return JSONResponse({
            "ok": False,
            "model_loaded": False,
            "error": str(e),
            "hint": "Instala en un env con Python 3.10 o 3.11: pip install chatterbox-tts torch torchaudio",
        }, status_code=503)


def _float_param(body: dict, key: str, default: float, min_val: float, max_val: float) -> float:
    v = body.get(key)
    if v is None:
        return default
    try:
        f = float(v)
        return max(min_val, min(max_val, f))
    except (TypeError, ValueError):
        return default


async def languages(_request):
    """GET /languages: lista de idiomas soportados (código -> nombre)."""
    try:
        langs = get_supported_languages()
        return JSONResponse({"languages": langs, "count": len(langs)})
    except Exception as e:
        return JSONResponse({"languages": {"en": "English"}, "error": str(e)})


async def generate(request):
    """POST /generate: body { text, language?, exaggeration?, temperature?, ... } -> JSON con audio en base64."""
    try:
        body = await request.json() or {}
    except Exception:
        return JSONResponse({"success": False, "error": "Body JSON invalido"}, status_code=400)

    text = (body.get("text") or body.get("prompt") or "").strip()
    if len(text) < 1:
        return JSONResponse(
            {"success": False, "error": "Body debe incluir 'text' o 'prompt' (min 1 caracter)."},
            status_code=400,
        )
    if len(text) > 5000:
        text = text[:5000]

    start_ms = int(time.time() * 1000)
    out_path = settings.output_dir / f"chatterbox_{start_ms}.wav"
    raw_ref = body.get("audio_prompt_path") or body.get("audio_prompt")
    if raw_ref:
        ref_path = Path(raw_ref)
        if not ref_path.is_absolute():
            ref_path = (Path(__file__).resolve().parent / ref_path).resolve()
        audio_prompt_path = str(ref_path) if ref_path.is_file() else None
    elif getattr(settings, "default_audio_prompt_path", None):
        ref = settings.default_audio_prompt_path
        if not ref.is_absolute():
            ref = (Path(__file__).resolve().parent / ref).resolve()
        audio_prompt_path = str(ref) if ref.is_file() else None
    else:
        audio_prompt_path = None
    language_id = body.get("language") or body.get("language_id") or "en"
    exaggeration = _float_param(body, "exaggeration", 0.4, 0.0, 2.0)
    cfg_weight = _float_param(body, "cfg_weight", 0.5, 0.0, 1.0)
    temperature = _float_param(body, "temperature", 0.6, 0.05, 2.0)
    repetition_penalty = _float_param(body, "repetition_penalty", 2.0, 1.0, 3.0)
    min_p = _float_param(body, "min_p", 0.05, 0.0, 1.0)
    top_p = _float_param(body, "top_p", 1.0, 0.0, 1.0)
    speed = _float_param(body, "speed", 1.0, 0.5, 1.5)

    def _run():
        return generate_audio(
            text,
            output_path=out_path,
            audio_prompt_path=audio_prompt_path,
            language_id=language_id,
            exaggeration=exaggeration,
            cfg_weight=cfg_weight,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            min_p=min_p,
            top_p=top_p,
            speed=speed,
        )

    try:
        wav_bytes, sr, path = await asyncio.get_event_loop().run_in_executor(None, _run)
    except Exception as e:
        return JSONResponse(
            {"success": False, "filename": None, "audio_path": None, "error": str(e)},
            status_code=200,
        )

    result = {
        "success": True,
        "filename": path.name,
        "audio_path": str(path.resolve()),
        "sample_rate": sr,
        "text_length": len(text),
        "language_id": language_id,
        "base64_audio": base64.b64encode(wav_bytes).decode("ascii"),
        "error": None,
    }
    return JSONResponse(result)


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/languages", languages, methods=["GET"]),
        Route("/generate", generate, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=settings.rest_port)
