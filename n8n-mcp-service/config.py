"""
Configuración del servidor MCP n8n (variables de entorno).
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="N8N_MCP_",
        case_sensitive=False,
    )

    # Base URL de n8n (ej. http://localhost:5678)
    base_url: str = Field(
        default="http://localhost:5678",
        description="URL base de la instancia n8n",
    )
    # API Key (JWT) de n8n — Settings > n8n API
    api_key: str = Field(
        default="",
        description="API Key / JWT de n8n (X-N8N-API-KEY)",
    )
    # Servidor MCP
    server_host: str = Field(default="127.0.0.1")
    server_port: int = Field(default=8010, ge=1024, le=65535)
    log_level: str = Field(default="INFO")


settings = Settings()
