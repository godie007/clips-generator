"""
Centralized configuration via environment variables.
Crea un archivo .env en la raíz del proyecto para sobreescribir defaults.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="IMAGE_MCP_",
        case_sensitive=False,
    )

    # ── ComfyUI backend ──────────────────────────────────────────────────────
    comfyui_url: str = Field(
        default="http://127.0.0.1:8188",
        description="URL base del servidor ComfyUI local",
    )
    comfyui_timeout: int = Field(
        default=120,
        ge=10,
        le=900,
        description="Timeout en segundos para requests a ComfyUI",
    )

    # ── Output storage ───────────────────────────────────────────────────────
    output_dir: Path = Field(
        default=Path("./outputs/images"),
        description="Directorio donde se guardan las imágenes generadas",
    )

    # ── FLUX.1 defaults (4K, calidad profesional) ──────────────────────────────
    default_width: int = Field(default=3840, ge=256, le=4096)
    default_height: int = Field(default=2160, ge=256, le=4096)
    default_steps: int = Field(default=8, ge=1, le=50)   # 8 steps = más detalle profesional
    default_guidance: float = Field(default=4.0, ge=0.0, le=20.0)
    default_model: str = Field(
        default="flux1-schnell-fp8.safetensors",
        description="Checkpoint FLUX.1 en ComfyUI models/checkpoints/",
    )

    # ── MCP server ───────────────────────────────────────────────────────────
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8001, ge=1024, le=65535)
    log_level: str = Field(default="INFO")

    @field_validator("output_dir", mode="before")
    @classmethod
    def ensure_output_dir(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Singleton — importar desde cualquier módulo
settings = Settings()
