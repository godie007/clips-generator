"""
Tool MCP: audio_gen_generate - genera audio desde texto con Chatterbox TTS.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from backends.chatterbox import generate_audio
from shared.config import settings

logger = logging.getLogger(__name__)


class GenerateAudioInput(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Texto a sintetizar en voz.")
    audio_prompt_path: str | None = Field(default=None, description="Ruta a clip de referencia para clonar voz (opcional).")
    language: str | None = Field(default="en", description="Código de idioma (en, es, fr, de, it, pt, ja, zh, …).")
    exaggeration: float = Field(default=0.4, ge=0.0, le=2.0, description="Intensidad emocional (0.0–2.0). Más bajo = más sobrio.")
    temperature: float = Field(default=0.6, ge=0.05, le=2.0, description="Temperatura de muestreo. Más bajo = más claro y articulado.")
    cfg_weight: float = Field(default=0.5, ge=0.0, le=1.0, description="Peso CFG / ritmo.")
    speed: float = Field(default=1.0, ge=0.5, le=1.5, description="Ritmo de habla. 1.0 = normal; < 1 = más pausado (narrar); > 1 = más rápido.")
    include_base64: bool = Field(default=True, description="Incluir audio en base64 en la respuesta JSON.")


def register_audio_tool(mcp: FastMCP) -> None:
    @mcp.tool(name="audio_gen_generate", annotations={"title": "Generar audio (TTS)"})
    async def audio_gen_generate(params: GenerateAudioInput) -> str:
        """Genera audio (WAV) desde texto usando Chatterbox TTS (multilingüe)."""
        start_ms = int(time.time() * 1000)
        try:
            out_path = settings.output_dir / f"chatterbox_{start_ms}.wav"
            p = params

            def _run():
                return generate_audio(
                    p.text,
                    output_path=out_path,
                    audio_prompt_path=p.audio_prompt_path,
                    language_id=p.language or "en",
                    exaggeration=p.exaggeration,
                    cfg_weight=p.cfg_weight,
                    temperature=p.temperature,
                    speed=p.speed,
                )

            wav_bytes, sr, path = await asyncio.get_event_loop().run_in_executor(None, _run)
        except Exception as e:
            logger.exception("Error generando audio")
            return json.dumps({"success": False, "error": str(e), "audio_path": None, "filename": None}, indent=2, ensure_ascii=False)

        result = {"success": True, "audio_path": str(path.resolve()), "filename": path.name, "sample_rate": sr, "text_length": len(params.text)}
        if params.include_base64:
            result["base64_audio"] = base64.b64encode(wav_bytes).decode("ascii")
        return json.dumps(result, indent=2, ensure_ascii=False)
