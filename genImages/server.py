"""
mcp-image-gen — Servidor MCP para generación de imágenes con FLUX.1 via ComfyUI.

Expone 3 tools:
  - image_gen_generate  → Genera imágenes desde texto con FLUX.1
  - image_gen_list      → Lista imágenes generadas (con paginación)
  - image_gen_info      → Metadata detallada de una imagen

Transport: streamable_http (compatible con n8n via HTTP MCP tools)
Puerto: 8001 (configurable via IMAGE_MCP_SERVER_PORT)

Uso:
    uv run server.py
    # o
    python server.py
"""
from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

from mcp.server.fastmcp import FastMCP

from shared.config import settings
from tools.generate import register_generate_tool
from tools.info import register_info_tools

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,  # MCP: nunca loggear a stdout en stdio mode
)
logger = logging.getLogger("mcp_image_gen")


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:  # type: ignore[type-arg]
    """
    Ciclo de vida del servidor.
    Se ejecuta al arrancar y al apagar — ideal para inicializar conexiones persistentes.
    """
    logger.info("🚀 mcp-image-gen iniciando...")
    logger.info("   ComfyUI URL : %s", settings.comfyui_url)
    logger.info("   Output dir  : %s", settings.output_dir.resolve())
    logger.info("   Modelo FLUX : %s", settings.default_model)
    logger.info("   Puerto MCP  : %s:%d", settings.server_host, settings.server_port)

    # Verificación de disponibilidad de ComfyUI al arrancar
    from backends.comfyui import get_comfyui_client
    async with get_comfyui_client() as client:
        available = await client.is_available()
        if available:
            checkpoints = await client.get_available_checkpoints()
            logger.info("✅ ComfyUI disponible. Checkpoints: %s", checkpoints or ["(no disponibles)"])
            if settings.default_model not in (checkpoints or []):
                logger.warning(
                    "⚠️  El checkpoint '%s' no está en ComfyUI. "
                    "Descárgalo en ComfyUI/models/checkpoints/ y configura IMAGE_MCP_DEFAULT_MODEL.",
                    settings.default_model,
                )
        else:
            logger.warning(
                "⚠️  ComfyUI NO disponible en %s. "
                "El servidor MCP inicia de todas formas, pero image_gen_generate "
                "fallará hasta que ComfyUI esté corriendo.",
                settings.comfyui_url,
            )

    yield {}  # Estado compartido entre tools (vacío por ahora)

    logger.info("👋 mcp-image-gen apagando...")


# ── Server ────────────────────────────────────────────────────────────────────

mcp = FastMCP(
    name="image_gen_mcp",
    instructions=(
        "Servidor MCP para generación de imágenes de alta calidad usando FLUX.1 via ComfyUI. "
        "Herramientas disponibles:\n"
        "• image_gen_generate — Genera imágenes desde texto (soporta aspect ratios, seeds, batch)\n"
        "• image_gen_list     — Lista imágenes generadas con paginación\n"
        "• image_gen_info     — Metadata detallada (dimensiones, formato, tamaño) de una imagen\n\n"
        "REQUISITO: ComfyUI debe estar corriendo en el puerto configurado (default: 8188) "
        "con el modelo FLUX.1 descargado en models/checkpoints/."
    ),
    lifespan=lifespan,
    host=settings.server_host,
    port=settings.server_port,
    log_level=settings.log_level.upper(),
    streamable_http_path="/mcp",
)

# Registrar todos los tools
register_generate_tool(mcp)
register_info_tools(mcp)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    """Punto de entrada principal. Inicia el servidor con streamable HTTP."""
    logger.info(
        "Iniciando servidor MCP en http://%s:%d/mcp",
        settings.server_host,
        settings.server_port,
    )
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
