"""
Schemas Pydantic compartidos entre tools y backends.
Single source of truth para todos los tipos de datos del servidor.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class AspectRatio(str, Enum):
    """Aspect ratios predefinidos para generación rápida."""
    SQUARE = "1:1"
    LANDSCAPE = "16:9"
    PORTRAIT = "9:16"
    PHOTO = "4:3"
    WIDE = "21:9"
    CUSTOM = "custom"


class ImageFormat(str, Enum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"


class ResponseFormat(str, Enum):
    JSON = "json"
    MARKDOWN = "markdown"


# ── Input Models ──────────────────────────────────────────────────────────────

class GenerateImageInput(BaseModel):
    """Input para generación de imágenes con FLUX.1."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    prompt: str = Field(
        ...,
        description=(
            "Descripción detallada de la imagen a generar. "
            "Incluir estilo, iluminación, composición. "
            "Ejemplo: 'A cinematic aerial shot of Cartagena Colombia at golden hour, "
            "dramatic clouds, ultra-detailed, 8k'"
        ),
        min_length=3,
        max_length=2000,
    )
    negative_prompt: str = Field(
        default="blurry, low quality, distorted, watermark, text",
        description="Elementos a evitar en la imagen generada",
        max_length=500,
    )
    aspect_ratio: AspectRatio = Field(
        default=AspectRatio.SQUARE,
        description="Relación de aspecto. Usar 'custom' para dimensiones manuales",
    )
    width: Optional[int] = Field(
        default=None,
        description="Ancho en píxeles (solo si aspect_ratio='custom'). Múltiplo de 64, hasta 4096.",
        ge=256,
        le=4096,
    )
    height: Optional[int] = Field(
        default=None,
        description="Alto en píxeles (solo si aspect_ratio='custom'). Múltiplo de 64, hasta 4096.",
        ge=256,
        le=4096,
    )
    steps: int = Field(
        default=8,
        description="Pasos de inferencia. 8-12 para calidad profesional con FLUX schnell.",
        ge=1,
        le=50,
    )
    guidance_scale: float = Field(
        default=4.0,
        description="Escala de guidance. 4.0-4.5 para detalle profesional.",
        ge=0.0,
        le=20.0,
    )
    seed: Optional[int] = Field(
        default=None,
        description="Seed para reproducibilidad. None = aleatorio.",
        ge=0,
        le=2**32 - 1,
    )
    output_format: ImageFormat = Field(
        default=ImageFormat.PNG,
        description="Formato de salida de la imagen",
    )
    batch_size: int = Field(
        default=1,
        description="Número de imágenes a generar en paralelo (máximo 4 con 8GB VRAM)",
        ge=1,
        le=4,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.JSON,
        description="Formato de la respuesta: 'json' para n8n, 'markdown' para lectura humana",
    )


class ImageVariationInput(BaseModel):
    """Input para generar variaciones de una imagen existente."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    image_path: str = Field(
        ...,
        description="Ruta absoluta o relativa a la imagen base",
        min_length=1,
    )
    prompt: str = Field(
        ...,
        description="Descripción de las modificaciones o variaciones deseadas",
        min_length=3,
        max_length=2000,
    )
    strength: float = Field(
        default=0.75,
        description=(
            "Qué tanto se aleja del original. "
            "0.0 = idéntico, 1.0 = completamente diferente"
        ),
        ge=0.0,
        le=1.0,
    )
    seed: Optional[int] = Field(default=None, ge=0, le=2**32 - 1)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON)


class GetImageInfoInput(BaseModel):
    """Input para obtener metadata de una imagen generada."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    image_path: str = Field(
        ...,
        description="Ruta a la imagen. Acepta path absoluto o nombre de archivo en output_dir.",
        min_length=1,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class ListGeneratedImagesInput(BaseModel):
    """Input para listar imágenes generadas."""

    model_config = ConfigDict(extra="forbid")

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ── Output Models ─────────────────────────────────────────────────────────────

class GeneratedImage(BaseModel):
    """Resultado de una imagen generada."""

    image_path: str
    filename: str
    width: int
    height: int
    format: str
    seed: int
    prompt: str
    steps: int
    guidance_scale: float
    file_size_bytes: int
    generation_time_ms: int


class GenerationResult(BaseModel):
    """Resultado completo de una llamada a generate_image."""

    success: bool
    images: list[GeneratedImage]
    total_generated: int
    error: Optional[str] = None


# ── Helpers ───────────────────────────────────────────────────────────────────

# 4K / calidad profesional: múltiplos de 64 para FLUX
ASPECT_RATIO_DIMENSIONS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.SQUARE: (2048, 2048),       # 2K square (8GB VRAM)
    AspectRatio.LANDSCAPE: (3840, 2160),    # 4K UHD 16:9
    AspectRatio.PORTRAIT: (2160, 3840),     # 4K vertical 9:16
    AspectRatio.PHOTO: (2560, 1920),        # 4:3 alto detalle
    AspectRatio.WIDE: (3840, 1600),        # 21:9 cinematográfico (múltiplo 64)
}


def resolve_dimensions(
    aspect_ratio: AspectRatio,
    width: Optional[int],
    height: Optional[int],
    default_width: int = 1024,
    default_height: int = 1024,
) -> tuple[int, int]:
    """Calcula dimensiones finales respetando múltiplos de 64 (requerimiento FLUX.1)."""
    if aspect_ratio == AspectRatio.CUSTOM:
        w = width or default_width
        h = height or default_height
    else:
        w, h = ASPECT_RATIO_DIMENSIONS.get(aspect_ratio, (default_width, default_height))

    # FLUX.1 requiere dimensiones múltiplos de 64
    w = (w // 64) * 64
    h = (h // 64) * 64
    return max(w, 64), max(h, 64)


def format_file_size(size_bytes: int) -> str:
    """Formatea bytes en string legible."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 ** 2:.1f} MB"
