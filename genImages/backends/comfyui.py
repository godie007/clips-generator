"""
Cliente async para la API de ComfyUI.
Encapsula toda la comunicación con ComfyUI — los tools nunca hablan directo con la API.

ComfyUI expone:
  POST /prompt          — Encola un workflow
  GET  /history/{id}   — Obtiene resultado del job
  GET  /view?filename  — Descarga imagen generada
  GET  /system_stats   — Estado del servidor
  GET  /object_info    — Modelos/nodes disponibles
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from shared.config import settings

logger = logging.getLogger(__name__)

# ── Constantes ────────────────────────────────────────────────────────────────

POLL_INTERVAL_SEC = 1.0
# Tiempo máximo de espera = IMAGE_MCP_COMFYUI_TIMEOUT (segundos); 4K puede tardar varios minutos


# ── Workflow templates ────────────────────────────────────────────────────────

def build_flux_workflow(
    *,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    steps: int,
    guidance: float,
    seed: int,
    checkpoint: str,
    output_format: str = "png",
) -> dict[str, Any]:
    """
    Construye el workflow ComfyUI para FLUX.1 schnell/dev.

    FLUX.1 usa FluxGuidance node en lugar de CFG clásico.
    Compatible con flux1-schnell-fp8.safetensors y flux1-dev.safetensors.
    """
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": checkpoint},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": prompt,
                "clip": ["1", 1],
            },
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text": negative_prompt,
                "clip": ["1", 1],
            },
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {
                "width": width,
                "height": height,
                "batch_size": 1,
            },
        },
        "5": {
            "class_type": "FluxGuidance",
            "inputs": {
                "conditioning": ["2", 0],
                "guidance": guidance,
            },
        },
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["5", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": seed,
                "steps": steps,
                "cfg": 1.0,          # FLUX usa FluxGuidance, no CFG
                "sampler_name": "euler",
                "scheduler": "simple",
                "denoise": 1.0,
            },
        },
        "7": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": ["6", 0],
                "vae": ["1", 2],
            },
        },
        "8": {
            "class_type": "SaveImage",
            "inputs": {
                "images": ["7", 0],
                "filename_prefix": "flux_mcp",
            },
        },
    }


# ── ComfyUI Client ────────────────────────────────────────────────────────────

class ComfyUIError(Exception):
    """Error de comunicación con ComfyUI."""


class ComfyUIUnavailableError(ComfyUIError):
    """ComfyUI no está corriendo o no es alcanzable."""


class ComfyUIGenerationError(ComfyUIError):
    """La generación falló en el lado de ComfyUI."""


class ComfyUIClient:
    """
    Cliente async para ComfyUI.
    Usar como context manager async para cleanup automático del httpx client.
    """

    def __init__(self, base_url: str = settings.comfyui_url, timeout: int = settings.comfyui_timeout) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> ComfyUIClient:
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=httpx.Timeout(self._timeout),
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("ComfyUIClient debe usarse como context manager async")
        return self._client

    # ── Health ────────────────────────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Verifica si ComfyUI está corriendo."""
        try:
            response = await self._http.get("/system_stats", timeout=5.0)
            return response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            return False

    async def assert_available(self) -> None:
        """Lanza ComfyUIUnavailableError si ComfyUI no está disponible."""
        if not await self.is_available():
            raise ComfyUIUnavailableError(
                f"ComfyUI no responde en {self._base_url}. "
                "Asegúrate de iniciar ComfyUI con GPU: ejecuta scripts/run_comfyui_gpu.ps1 (ver COMFYUI_SETUP.md)."
            )

    async def get_available_checkpoints(self) -> list[str]:
        """Lista los checkpoints disponibles en ComfyUI."""
        try:
            response = await self._http.get("/object_info/CheckpointLoaderSimple")
            response.raise_for_status()
            data = response.json()
            return data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
        except Exception as exc:
            logger.warning("No se pudo obtener lista de checkpoints: %s", exc)
            return []

    # ── Generation ────────────────────────────────────────────────────────────

    async def generate(
        self,
        workflow: dict[str, Any],
        client_id: str | None = None,
    ) -> list[str]:
        """
        Encola un workflow y espera el resultado.

        Returns:
            Lista de nombres de archivo generados en ComfyUI output/.

        Raises:
            ComfyUIUnavailableError: Si ComfyUI no está corriendo.
            ComfyUIGenerationError: Si la generación falla.
        """
        await self.assert_available()

        cid = client_id or str(uuid.uuid4())
        payload = {"prompt": workflow, "client_id": cid}

        # Encolar job
        try:
            enqueue_resp = await self._http.post("/prompt", json=payload)
            enqueue_resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ComfyUIGenerationError(
                f"Error al encolar workflow en ComfyUI (HTTP {exc.response.status_code}): "
                f"{exc.response.text[:200]}"
            ) from exc

        prompt_id: str = enqueue_resp.json()["prompt_id"]
        logger.info("Job encolado en ComfyUI — prompt_id=%s", prompt_id)

        # Polling hasta completar
        filenames = await self._poll_until_done(prompt_id)
        logger.info("Generación completa — %d imagen(s) producida(s)", len(filenames))
        return filenames

    async def _poll_until_done(self, prompt_id: str) -> list[str]:
        """Hace polling a /history/{id} hasta que el job termine."""
        max_attempts = max(1, int(self._timeout / POLL_INTERVAL_SEC))
        for attempt in range(max_attempts):
            await asyncio.sleep(POLL_INTERVAL_SEC)

            try:
                history_resp = await self._http.get(f"/history/{prompt_id}")
                history_resp.raise_for_status()
                history = history_resp.json()
            except httpx.HTTPStatusError as exc:
                raise ComfyUIGenerationError(
                    f"Error consultando historial de ComfyUI: HTTP {exc.response.status_code}"
                ) from exc

            if prompt_id not in history:
                logger.debug("Job %s aún en cola (intento %d/%d)", prompt_id, attempt + 1, max_attempts)
                continue

            job_data = history[prompt_id]

            # Verificar si hubo error
            if "error" in job_data.get("status", {}):
                error_detail = job_data["status"].get("error", "Error desconocido")
                raise ComfyUIGenerationError(f"ComfyUI reportó error: {error_detail}")

            # Extraer nombres de archivos de los outputs
            filenames = self._extract_output_filenames(job_data)
            if filenames:
                return filenames

        raise ComfyUIGenerationError(
            f"Timeout: el job {prompt_id} no completó en {self._timeout}s. "
            "Considera aumentar IMAGE_MCP_COMFYUI_TIMEOUT en tu .env"
        )

    def _extract_output_filenames(self, job_data: dict[str, Any]) -> list[str]:
        """Extrae los filenames de imágenes del historial de ComfyUI."""
        filenames: list[str] = []
        outputs = job_data.get("outputs", {})
        for node_output in outputs.values():
            for img in node_output.get("images", []):
                if img.get("type") == "output":
                    filenames.append(img["filename"])
        return filenames

    # ── Image Download ────────────────────────────────────────────────────────

    async def download_image(
        self,
        filename: str,
        dest_dir: Path,
        output_format: str = "png",
    ) -> Path:
        """
        Descarga una imagen generada de ComfyUI al directorio de salida local.

        Returns:
            Path absoluto al archivo descargado.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        params = {"filename": filename, "subfolder": "", "type": "output"}
        try:
            response = await self._http.get("/view", params=params)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ComfyUIGenerationError(
                f"No se pudo descargar la imagen '{filename}': HTTP {exc.response.status_code}"
            ) from exc

        dest_path.write_bytes(response.content)
        logger.info("Imagen descargada: %s (%d bytes)", dest_path, len(response.content))
        return dest_path


# ── Singleton factory ─────────────────────────────────────────────────────────

def get_comfyui_client() -> ComfyUIClient:
    """Factory para obtener un cliente configurado con los settings actuales."""
    return ComfyUIClient(
        base_url=settings.comfyui_url,
        timeout=settings.comfyui_timeout,
    )
