"""
Tools MCP para interactuar con n8n: listar workflows y disparar webhook de generación de imágenes.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field

from config import settings

logger = logging.getLogger(__name__)

# Cabecera oficial de n8n para API
N8N_API_KEY_HEADER = "X-N8N-API-KEY"


# ── Input models ─────────────────────────────────────────────────────────────

class TriggerImageWorkflowInput(BaseModel):
    """Input para disparar un workflow de n8n que genera imágenes (vía webhook)."""
    webhook_path: str = Field(
        ...,
        description="Path del webhook en n8n, ej: 'generate-image' o URL completa si base_url no aplica",
        min_length=1,
    )
    prompt: str = Field(
        ...,
        description="Prompt para generación de imagen (se envía en el body del POST)",
        min_length=1,
        max_length=2000,
    )
    use_full_url: bool = Field(
        default=False,
        description="Si True, webhook_path se interpreta como URL completa (ignorando base_url)",
    )


class ListWorkflowsInput(BaseModel):
    """Input para listar workflows (opcional: solo activos)."""
    active_only: bool = Field(
        default=True,
        description="Si True, solo devuelve workflows activos",
    )


class CreateImageWorkflowInput(BaseModel):
    """Input para crear el workflow de prueba (Webhook -> HTTP Request -> Respond)."""
    image_gen_url: str = Field(
        default="http://host.docker.internal:8002/generate",
        description="URL del endpoint REST del generador de imágenes",
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    h: dict[str, str] = {"Accept": "application/json", "Content-Type": "application/json"}
    if settings.api_key:
        h[N8N_API_KEY_HEADER] = settings.api_key
    return h


def _webhook_url(webhook_path: str, use_full_url: bool) -> str:
    if use_full_url:
        return webhook_path if webhook_path.startswith("http") else f"http://localhost:5678/{webhook_path}"
    base = settings.base_url.rstrip("/")
    path = webhook_path.lstrip("/")
    if path.startswith("webhook/") or path.startswith("webhook-test/"):
        return f"{base}/{path}"
    return f"{base}/webhook/{path}"


# ── Tools ────────────────────────────────────────────────────────────────────

def register_n8n_tools(mcp: FastMCP) -> None:

    @mcp.tool(
        name="n8n_trigger_image_workflow",
        annotations={
            "title": "Generar imagen vía n8n",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def n8n_trigger_image_workflow(params: TriggerImageWorkflowInput) -> str:
        """
        Dispara un workflow de n8n mediante su webhook para generar una imagen.

        El workflow en n8n debe tener:
        1. Nodo Webhook (POST) que reciba el body.
        2. Nodo MCP Client apuntando a http://127.0.0.1:8001/mcp con la tool image_gen_generate.
        3. El prompt se envía en el body como { "prompt": "..." }.

        Valida que la respuesta indique éxito (ej. que n8n devolvió datos de imagen o success).
        """
        url = _webhook_url(params.webhook_path, params.use_full_url)
        # El generador REST acepta "description" o "prompt"; enviamos ambos para compatibilidad
        body: dict[str, Any] = {"prompt": params.prompt, "description": params.prompt}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers=_headers(),
                )
        except httpx.ConnectError as e:
            return _json_error(f"No se pudo conectar a n8n: {e}. Revisa N8N_MCP_BASE_URL y que n8n esté corriendo.")
        except httpx.TimeoutException as e:
            return _json_error(f"Timeout al llamar al webhook de n8n: {e}")
        except Exception as e:
            logger.exception("Error inesperado llamando webhook n8n")
            return _json_error(f"Error: {type(e).__name__}: {e}")

        try:
            response_data = response.json() if response.content else {}
        except Exception:
            response_data = {"raw_text": response.text[:500] if response.text else ""}

        success = response.status_code >= 200 and response.status_code < 300
        # Validación: considerar éxito si hay images o success en la respuesta
        if success and isinstance(response_data, dict):
            has_images = (
                "images" in response_data
                or "image_path" in str(response_data).lower()
                or response_data.get("success") is True
            )
            if has_images or response_data.get("success") is True:
                validation = "validado: n8n devolvió datos de imagen o success."
            else:
                validation = "respuesta OK pero sin campo de imagen/success; revisa el workflow en n8n."
        else:
            validation = f"respuesta HTTP {response.status_code}; revisa el webhook y el workflow."

        result = {
            "success": success,
            "status_code": response.status_code,
            "validation": validation,
            "response": response_data,
            "webhook_url": url,
        }
        return json.dumps(result, indent=2, ensure_ascii=False)

    @mcp.tool(
        name="n8n_list_workflows",
        annotations={
            "title": "Listar workflows de n8n",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        },
    )
    async def n8n_list_workflows(params: ListWorkflowsInput) -> str:
        """
        Lista los workflows de la instancia n8n (requiere API key válida).

        Útil para obtener IDs o nombres y configurar el webhook de generación de imágenes.
        """
        if not settings.api_key:
            return _json_error("N8N_MCP_API_KEY no está configurado. Añade tu API key en .env")

        url = f"{settings.base_url.rstrip('/')}/api/v1/workflows"
        if params.active_only:
            url += "?active=true"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=_headers())
        except httpx.ConnectError as e:
            return _json_error(f"No se pudo conectar a n8n: {e}. Revisa N8N_MCP_BASE_URL.")
        except Exception as e:
            logger.exception("Error listando workflows n8n")
            return _json_error(f"Error: {type(e).__name__}: {e}")

        if response.status_code == 401:
            return _json_error("API key inválida o expirada. Revisa N8N_MCP_API_KEY.")
        if response.status_code != 200:
            return _json_error(f"n8n devolvió HTTP {response.status_code}: {response.text[:300]}")

        try:
            data = response.json()
        except Exception:
            return _json_error("Respuesta de n8n no es JSON válido.")

        workflows = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(workflows, list):
            workflows = [workflows]

        list_result = {
            "total": len(workflows),
            "workflows": [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "active": w.get("active"),
                }
                for w in workflows
            ],
        }
        return json.dumps(list_result, indent=2, ensure_ascii=False)

    @mcp.tool(
        name="n8n_create_image_workflow",
        annotations={
            "title": "Crear workflow de prueba de generación de imágenes",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    async def n8n_create_image_workflow(params: CreateImageWorkflowInput) -> str:
        """
        Crea en n8n un workflow vía API: Webhook (POST generate-image) -> HTTP Request al generador -> Respond to Webhook.
        Luego activa el workflow. Requiere que el generador REST esté en la URL indicada (p. ej. rest_api.py en puerto 8002).
        """
        if not settings.api_key:
            return _json_error("N8N_MCP_API_KEY no está configurado.")

        wid, hid, rid = "w1", "h1", "r1"
        workflow = {
            "name": "Image Gen Test",
            "nodes": [
                {
                    "id": wid,
                    "name": "Webhook",
                    "type": "n8n-nodes-base.webhook",
                    "typeVersion": 2,
                    "position": [0, 0],
                    "parameters": {
                        "path": "generate-image",
                        "httpMethod": "POST",
                        "responseMode": "responseNode",
                        "responseNodeId": rid,
                    },
                },
                {
                    "id": hid,
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "typeVersion": 4.2,
                    "position": [280, 0],
                    "parameters": {
                        "method": "POST",
                        "url": params.image_gen_url,
                        "sendBody": True,
                        "specifyBody": "json",
                        "jsonBody": "={{ JSON.stringify($json.body || $json) }}",
                    },
                },
                {
                    "id": rid,
                    "name": "Respond to Webhook",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "typeVersion": 1.1,
                    "position": [560, 0],
                    "parameters": {"respondWith": "firstIncomingItem"},
                },
            ],
            "connections": {
                "Webhook": {"main": [[{"node": "HTTP Request", "type": "main", "index": 0}]]},
                "HTTP Request": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
            },
            "settings": {},
        }

        base = settings.base_url.rstrip("/")
        create_url = f"{base}/api/v1/workflows"
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(create_url, json=workflow, headers=_headers())
        except Exception as e:
            return _json_error(f"Error creando workflow: {e}")

        if r.status_code in (200, 201):
            data = r.json()
            wf_id = data.get("id") or data.get("data", {}).get("id")
            if wf_id:
                activate_url = f"{base}/api/v1/workflows/{wf_id}/activate"
                ar = None
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        ar = await client.post(activate_url, headers=_headers())
                except Exception:
                    pass
                if ar and ar.status_code in (200, 204):
                    return json.dumps({
                        "success": True,
                        "workflow_id": wf_id,
                        "webhook_url": f"{base}/webhook/generate-image",
                        "message": "Workflow creado y activado.",
                    }, indent=2, ensure_ascii=False)
            return json.dumps({"success": True, "data": data}, indent=2, ensure_ascii=False)
        return _json_error(f"n8n devolvió {r.status_code}: {r.text[:400]}")


def _json_error(msg: str) -> str:
    return json.dumps({"success": False, "error": msg}, indent=2, ensure_ascii=False)
