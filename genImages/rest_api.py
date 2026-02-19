"""REST POST /generate: body con descripcion de la imagen a generar."""
from __future__ import annotations

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

from shared.config import settings
from shared.models import GenerateImageInput, ResponseFormat
from tools.generate import run_generation


async def health(_request):
    """GET /health: comprueba si ComfyUI está disponible (para usar GPU)."""
    try:
        from backends.comfyui import ComfyUIClient
        async with ComfyUIClient() as client:
            ok = await client.is_available()
            if ok:
                checkpoints = await client.get_available_checkpoints()
                return JSONResponse({
                    "ok": True,
                    "comfyui": settings.comfyui_url,
                    "message": "ComfyUI listo. Arranca con GPU si usaste scripts/run_comfyui_gpu.ps1.",
                    "checkpoints_sample": checkpoints[:5] if checkpoints else [],
                })
    except Exception as e:
        pass
    return JSONResponse({
        "ok": False,
        "comfyui": settings.comfyui_url,
        "error": "ComfyUI no responde. Inicia ComfyUI con GPU: scripts/run_comfyui_gpu.ps1 (ver COMFYUI_SETUP.md).",
    }, status_code=503)


async def generate(request):
    try:
        body = await request.json() or {}
    except Exception:
        return JSONResponse({"success": False, "error": "Body JSON invalido"}, status_code=400)
    # Acepta "description" o "prompt" + opcionales: aspect_ratio, width, height, steps, guidance_scale
    prompt = (body.get("description") or body.get("prompt") or "").strip()
    if len(prompt) < 3:
        return JSONResponse(
            {
                "success": False,
                "error": "Body debe incluir la descripcion de la imagen (min 3 caracteres). Ej: {\"description\": \"una manzana roja sobre mesa blanca\"}",
            },
            status_code=400,
        )
    from shared.models import AspectRatio
    aspect_ratio_str = (body.get("aspect_ratio") or "16:9").strip()
    try:
        aspect_ratio = AspectRatio(aspect_ratio_str)
    except ValueError:
        aspect_ratio = AspectRatio.LANDSCAPE
    params = GenerateImageInput(
        prompt=prompt[:2000],
        response_format=ResponseFormat.JSON,
        aspect_ratio=aspect_ratio,
        width=body.get("width"),
        height=body.get("height"),
        steps=int(body["steps"]) if body.get("steps") is not None else 8,
        guidance_scale=float(body["guidance_scale"]) if body.get("guidance_scale") is not None else 4.0,
    )
    result = await run_generation(params)
    return JSONResponse(result.model_dump())


app = Starlette(
    routes=[
        Route("/health", health, methods=["GET"]),
        Route("/generate", generate, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8002)
