"""
Servidor MCP para generación de audio (text-to-speech) con Chatterbox TTS.
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from shared.config import settings
from tools.generate import register_audio_tool

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_audio_gen")

mcp = FastMCP(
    name="audio_gen_mcp",
    instructions=(
        "Servidor MCP para generar audio desde texto (TTS) con Chatterbox. "
        "Usa la herramienta audio_gen_generate con el texto a sintetizar."
    ),
    host=settings.server_host,
    port=settings.server_port,
    log_level=settings.log_level.upper(),
    streamable_http_path="/mcp",
)

register_audio_tool(mcp)


def main() -> None:
    logger.info("Iniciando MCP audio en http://%s:%d/mcp", settings.server_host, settings.server_port)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
