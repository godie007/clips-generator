"""Crea el workflow n8n para audio: Webhook -> HTTP Request a genAudio REST (8004) -> Respond."""
import asyncio
import httpx
from config import settings

N8N_API_KEY_HEADER = "X-N8N-API-KEY"
WORKFLOW_NAME = "Audio Gen Test"
WEBHOOK_PATH = "generate-audio"
AUDIO_GENERATOR_URL = "http://host.docker.internal:8004/generate"


def _workflow_payload():
    wid, hid, rid = "wa1", "ha1", "ra1"
    return {
        "name": WORKFLOW_NAME,
        "nodes": [
            {
                "id": wid,
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
                "parameters": {
                    "path": WEBHOOK_PATH,
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
                    "url": AUDIO_GENERATOR_URL,
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


async def main():
    if not settings.api_key:
        print("N8N_MCP_API_KEY no configurado en .env")
        return
    base = settings.base_url.rstrip("/")
    headers = {"Accept": "application/json", "Content-Type": "application/json", N8N_API_KEY_HEADER: settings.api_key}
    webhook_url = f"{base}/webhook/{WEBHOOK_PATH}"
    api_base = f"{base}/api/v1"

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(f"{api_base}/workflows", headers=headers)
    if r.status_code != 200:
        print("Error listar workflows:", r.status_code, r.text[:400])
        return
    data = r.json()
    workflows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(workflows, list):
        workflows = [workflows] if workflows else []
    audio_workflows = [w for w in workflows if w.get("name") == WORKFLOW_NAME]

    async with httpx.AsyncClient(timeout=30.0) as client:
        if len(audio_workflows) == 1:
            wf_id = audio_workflows[0].get("id")
            ar = await client.post(f"{api_base}/workflows/{wf_id}/activate", headers=headers)
            print("Workflow 'Audio Gen Test' ya existe. id:", wf_id)
            print("Webhook:", webhook_url)
            print("Si al probar obtienes 404, activa el workflow en n8n (toggle arriba a la derecha) y guarda.")
            return

        if len(audio_workflows) > 1:
            for w in audio_workflows:
                await client.delete(f"{api_base}/workflows/{w.get('id')}", headers=headers)
            audio_workflows = []

        r = await client.post(f"{api_base}/workflows", json=_workflow_payload(), headers=headers)
    if r.status_code not in (200, 201):
        print("Error crear workflow:", r.status_code, r.text[:600])
        return
    created = r.json()
    wf_id = created.get("id") or (created.get("data") or {}).get("id")
    if not wf_id:
        print("Respuesta sin id:", created)
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(f"{api_base}/workflows/{wf_id}/activate", headers=headers)
    print("Workflow creado. id:", wf_id)
    print("Webhook:", webhook_url)
    print("Asegúrate de que rest_api.py de genAudio esté en marcha en el puerto 8004.")
    print("Si el webhook devuelve 404, activa el workflow en n8n: abre el workflow, guarda (Ctrl+S) y activa el toggle arriba a la derecha.")


if __name__ == "__main__":
    asyncio.run(main())
