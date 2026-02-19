"""
Configuración del servidor de audio (Chatterbox TTS).
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AUDIO_MCP_",
        case_sensitive=False,
    )

    output_dir: Path = Field(
        default=Path("./outputs/audio"),
        description="Directorio donde se guardan los audios generados",
    )
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8003, ge=1024, le=65535)
    rest_port: int = Field(default=8004, ge=1024, le=65535)
    log_level: str = Field(default="INFO")
    device: str = Field(
        default="cuda",
        description="Device para Chatterbox: cuda, cpu o mps",
    )
    # Ruta por defecto al audio de referencia para clonar voz (~10 s). WAV o MP3. Si está definida, se usa cuando el request no envía audio_prompt_path.
    default_audio_prompt_path: Path | None = Field(
        default=Path("voiceReference.mp3"),
        description="Ruta por defecto al audio de referencia (ej. voiceReference.mp3 o mi_voz.wav)",
    )

    @field_validator("output_dir", mode="before")
    @classmethod
    def ensure_output_dir(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("default_audio_prompt_path", mode="before")
    @classmethod
    def optional_path(cls, v: str | Path | None) -> Path | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return Path(v)


settings = Settings()
