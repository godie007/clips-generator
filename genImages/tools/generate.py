"""
Tool: image_gen_generate
Genera imágenes usando FLUX.1 via ComfyUI.
"""
from __future__ import annotations

import json
import logging
import random
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from backends.comfyui import ComfyUIGenerationError, ComfyUIUnavailableError, build_flux_workflow, get_comfyui_client
from shared.config import settings
from shared.models import (
    GenerateImageInput,
    GeneratedImage,
    GenerationResult,
    ResponseFormat,
    format_file_size,
    resolve_dimensions,
)

logger = logging.getLogger(__name__)


def register_generate_tool(mcp: FastMCP) -> None:
    """Registra el tool image_gen_generate en el servidor MCP."""

    @mcp.tool(
        name="image_gen_generate",
        annotations={
            "title": "Generar Imagen con FLUX.1",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def image_gen_generate(params: GenerateImageInput) -> str:
        """
        Genera imágenes de alta calidad usando FLUX.1 [schnell] via ComfyUI.

        FLUX.1 es el modelo open-source de mayor calidad disponible en 2025 para 8GB VRAM.
        Produce imágenes photo-realistas, artísticas o cinematográficas desde texto.

        Args:
            params (GenerateImageInput): Parámetros validados que incluyen:
                - prompt (str): Descripción detallada (requerido, 3-2000 chars)
                - negative_prompt (str): Elementos a evitar
                - aspect_ratio (AspectRatio): '1:1', '16:9', '9:16', '4:3', '21:9', 'custom'
                - width/height (int): Solo si aspect_ratio='custom'. Múltiplos de 64.
                - steps (int): Pasos FLUX schnell: 4-8. Dev: 20-30.
                - guidance_scale (float): 1.0-5.0 para FLUX.1
                - seed (int | None): Seed para reproducibilidad
                - output_format (ImageFormat): 'png', 'jpeg', 'webp'
                - batch_size (int): 1-4 imágenes simultáneas
                - response_format (ResponseFormat): 'json' o 'markdown'

        Returns:
            str: JSON o Markdown con los paths de las imágenes generadas y metadata.

            JSON schema:
            {
                "success": bool,
                "images": [{
                    "image_path": str,    // path absoluto al archivo
                    "filename": str,
                    "width": int,
                    "height": int,
                    "format": str,
                    "seed": int,
                    "prompt": str,
                    "steps": int,
                    "guidance_scale": float,
                    "file_size_bytes": int,
                    "generation_time_ms": int
                }],
                "total_generated": int,
                "error": str | null
            }
        """
        logger.info("Generando imagen: prompt='%s...'", params.prompt[:60])
        result = await run_generation(params)
        return _format_result(result, params.response_format)


async def run_generation(params: GenerateImageInput) -> GenerationResult:
    """Lógica de generación reutilizable (MCP tool y REST)."""
    start_ms = int(time.time() * 1000)
    width, height = resolve_dimensions(
        params.aspect_ratio, params.width, params.height,
        settings.default_width, settings.default_height,
    )
    seed = params.seed if params.seed is not None else random.randint(0, 2**32 - 1)
    generated_images: list[GeneratedImage] = []
    try:
        async with get_comfyui_client() as client:
            for i in range(params.batch_size):
                batch_seed = seed + i
                workflow = build_flux_workflow(
                    prompt=params.prompt, negative_prompt=params.negative_prompt,
                    width=width, height=height, steps=params.steps,
                    guidance=params.guidance_scale, seed=batch_seed,
                    checkpoint=settings.default_model, output_format=params.output_format.value,
                )
                filenames = await client.generate(workflow)
                for filename in filenames:
                    local_path = await client.download_image(filename=filename, dest_dir=settings.output_dir)
                    generated_images.append(GeneratedImage(
                        image_path=str(local_path.resolve()), filename=local_path.name,
                        width=width, height=height, format=params.output_format.value, seed=batch_seed,
                        prompt=params.prompt, steps=params.steps, guidance_scale=params.guidance_scale,
                        file_size_bytes=local_path.stat().st_size, generation_time_ms=int(time.time() * 1000) - start_ms,
                    ))
        return GenerationResult(success=True, images=generated_images, total_generated=len(generated_images))
    except (ComfyUIUnavailableError, ComfyUIGenerationError) as exc:
        return GenerationResult(success=False, images=[], total_generated=0, error=str(exc))
    except Exception as exc:
        logger.exception("Error inesperado en image_gen_generate")
        return GenerationResult(success=False, images=[], total_generated=0, error=f"{type(exc).__name__}: {exc}")


def _error_response(error_msg: str, fmt: ResponseFormat) -> str:
    """Formatea un error de generación según el formato solicitado."""
    result = GenerationResult(success=False, images=[], total_generated=0, error=error_msg)
    return _format_result(result, fmt)


def _format_result(result: GenerationResult, fmt: ResponseFormat) -> str:
    """Serializa el resultado en JSON o Markdown."""
    if fmt == ResponseFormat.JSON:
        return result.model_dump_json(indent=2)

    # Markdown — legible para humanos / debugging
    if not result.success:
        return f"## Error de Generación\n\n❌ {result.error}"

    lines = [f"## Imágenes Generadas ({result.total_generated})"]
    for i, img in enumerate(result.images, 1):
        lines += [
            f"\n### Imagen {i}",
            f"- **Archivo**: `{img.image_path}`",
            f"- **Dimensiones**: {img.width}×{img.height}px",
            f"- **Formato**: {img.format.upper()}",
            f"- **Seed**: `{img.seed}`",
            f"- **Steps**: {img.steps}",
            f"- **Tamaño**: {format_file_size(img.file_size_bytes)}",
            f"- **Tiempo**: {img.generation_time_ms}ms",
            f"- **Prompt**: *{img.prompt[:100]}{'...' if len(img.prompt) > 100 else ''}*",
        ]

    return "\n".join(lines)
