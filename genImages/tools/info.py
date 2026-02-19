"""
Tools: image_gen_list, image_gen_info
Gestión de imágenes generadas — listar y obtener metadata.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from PIL import Image as PILImage

from shared.config import settings
from shared.models import (
    GetImageInfoInput,
    ListGeneratedImagesInput,
    ResponseFormat,
    format_file_size,
)

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def register_info_tools(mcp: FastMCP) -> None:
    """Registra los tools de consulta/listado en el servidor MCP."""

    @mcp.tool(
        name="image_gen_list",
        annotations={
            "title": "Listar Imágenes Generadas",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def image_gen_list(params: ListGeneratedImagesInput) -> str:
        """
        Lista las imágenes generadas previamente con paginación.

        Retorna las imágenes ordenadas de más reciente a más antigua.
        Útil para n8n workflows que necesitan referenciar imágenes anteriores.

        Args:
            params (ListGeneratedImagesInput): Parámetros que incluyen:
                - limit (int): Máximo de resultados (1-100, default 20)
                - offset (int): Saltar N resultados para paginación
                - response_format (ResponseFormat): 'json' o 'markdown'

        Returns:
            str: JSON o Markdown con lista de imágenes y metadata de paginación.

            JSON schema:
            {
                "total": int,
                "count": int,
                "offset": int,
                "has_more": bool,
                "next_offset": int | null,
                "images": [{
                    "filename": str,
                    "image_path": str,
                    "file_size": str,     // ej: "1.2 MB"
                    "file_size_bytes": int,
                    "modified_at": str    // ISO timestamp
                }]
            }
        """
        output_dir = settings.output_dir

        if not output_dir.exists():
            return _empty_list_response(params.response_format)

        # Recolectar archivos de imagen ordenados por modificación (más reciente primero)
        image_files = sorted(
            [f for f in output_dir.iterdir() if f.suffix.lower() in SUPPORTED_EXTENSIONS],
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )

        total = len(image_files)
        page = image_files[params.offset : params.offset + params.limit]
        has_more = total > params.offset + len(page)

        items = [
            {
                "filename": f.name,
                "image_path": str(f.resolve()),
                "file_size": format_file_size(f.stat().st_size),
                "file_size_bytes": f.stat().st_size,
                "modified_at": _iso_timestamp(f.stat().st_mtime),
            }
            for f in page
        ]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "total": total,
                    "count": len(items),
                    "offset": params.offset,
                    "has_more": has_more,
                    "next_offset": params.offset + len(items) if has_more else None,
                    "images": items,
                },
                indent=2,
            )

        # Markdown
        if not items:
            return "## Imágenes Generadas\n\n*No hay imágenes en el directorio de output.*"

        lines = [
            f"## Imágenes Generadas ({total} total, mostrando {len(items)})",
            "",
        ]
        for img in items:
            lines.append(f"- **{img['filename']}** — {img['file_size']} — {img['modified_at']}")
            lines.append(f"  `{img['image_path']}`")

        if has_more:
            lines.append(f"\n*Usar offset={params.offset + len(items)} para ver más.*")

        return "\n".join(lines)

    @mcp.tool(
        name="image_gen_info",
        annotations={
            "title": "Obtener Info de Imagen",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def image_gen_info(params: GetImageInfoInput) -> str:
        """
        Obtiene metadata detallada de una imagen generada (dimensiones, formato, EXIF, etc.).

        Acepta path absoluto o solo el nombre de archivo si está en el output_dir configurado.

        Args:
            params (GetImageInfoInput): Parámetros que incluyen:
                - image_path (str): Path absoluto o nombre de archivo
                - response_format (ResponseFormat): 'json' o 'markdown'

        Returns:
            str: JSON o Markdown con metadata de la imagen.

            JSON schema:
            {
                "filename": str,
                "image_path": str,
                "width": int,
                "height": int,
                "format": str,
                "mode": str,            // RGB, RGBA, L, etc.
                "file_size": str,
                "file_size_bytes": int,
                "modified_at": str
            }
        """
        resolved = _resolve_image_path(params.image_path)
        if resolved is None:
            return _not_found_error(params.image_path, params.response_format)

        try:
            with PILImage.open(resolved) as img:
                width, height = img.size
                fmt = img.format or resolved.suffix.lstrip(".").upper()
                mode = img.mode
        except Exception as exc:
            logger.warning("No se pudo abrir imagen %s: %s", resolved, exc)
            return _format_error(
                f"No se pudo leer la imagen: {exc}. "
                "Verifica que el archivo es una imagen válida (PNG, JPEG, WEBP).",
                params.response_format,
            )

        stat = resolved.stat()
        info = {
            "filename": resolved.name,
            "image_path": str(resolved.resolve()),
            "width": width,
            "height": height,
            "format": fmt,
            "mode": mode,
            "file_size": format_file_size(stat.st_size),
            "file_size_bytes": stat.st_size,
            "modified_at": _iso_timestamp(stat.st_mtime),
        }

        if params.response_format == ResponseFormat.JSON:
            return json.dumps(info, indent=2)

        return (
            f"## Información: {resolved.name}\n\n"
            f"- **Dimensiones**: {width}×{height}px\n"
            f"- **Formato**: {fmt} ({mode})\n"
            f"- **Tamaño archivo**: {format_file_size(stat.st_size)}\n"
            f"- **Modificado**: {_iso_timestamp(stat.st_mtime)}\n"
            f"- **Path**: `{resolved.resolve()}`"
        )


# ── Helpers privados ──────────────────────────────────────────────────────────

def _resolve_image_path(image_path: str) -> Path | None:
    """
    Resuelve el path de la imagen.
    Acepta path absoluto, relativo, o solo nombre de archivo (busca en output_dir).
    """
    p = Path(image_path)

    if p.is_absolute() and p.exists():
        return p

    # Buscar en output_dir
    candidate = settings.output_dir / p.name
    if candidate.exists():
        return candidate

    # Intentar relativo al CWD
    if p.exists():
        return p

    return None


def _iso_timestamp(mtime: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _empty_list_response(fmt: ResponseFormat) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps({"total": 0, "count": 0, "offset": 0, "has_more": False, "next_offset": None, "images": []}, indent=2)
    return "## Imágenes Generadas\n\n*Directorio de output no encontrado o vacío.*"


def _not_found_error(image_path: str, fmt: ResponseFormat) -> str:
    msg = (
        f"Imagen no encontrada: '{image_path}'. "
        f"Verifica que el path es correcto o usa image_gen_list para ver las imágenes disponibles."
    )
    return _format_error(msg, fmt)


def _format_error(msg: str, fmt: ResponseFormat) -> str:
    if fmt == ResponseFormat.JSON:
        return json.dumps({"error": msg}, indent=2)
    return f"## Error\n\n❌ {msg}"
