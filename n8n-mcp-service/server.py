"""
Servidor MCP para consumir n8n: disparar workflows (ej. generación de imágenes) y listar workflows.
Usa N8N_MCP_API_KEY (JWT) para autenticación.
"""
from __future__ import annotations

import logging
import sys

from mcp.server.fastmcp import FastMCP

from config import settings
from tools_n8n import register_n8n_tools

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_n8n")


mcp = FastMCP(
    name="n8n_image_mcp",
    instructions=(
        "Servidor MCP para disparar workflows de n8n (p. ej. generación de imágenes). "
        "Herramientas: n8n_trigger_image_workflow (POST al webhook con prompt) y n8n_list_workflows (lista workflows con API key). "
        "Para generar imágenes, el workflow en n8n debe tener Webhook + MCP Client apuntando al servidor image_gen (http://127.0.0.1:8001/mcp)."
    ),
    host=settings.server_host,
    port=settings.server_port,
    log_level=settings.log_level.upper(),
    streamable_http_path="/mcp",
)

register_n8n_tools(mcp)


def main() -> None:
    logger.info("Iniciando MCP n8n en http://%s:%d/mcp", settings.server_host, settings.server_port)
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
