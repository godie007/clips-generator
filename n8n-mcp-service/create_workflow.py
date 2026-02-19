"""Crea el workflow n8n que llama al MCP/generador de imagenes: Webhook -> HTTP Request a rest_api (8002) -> Respond."""
import asyncio
import json
import httpx
from config import settings

N8N_API_KEY_HEADER = "X-N8N-API-KEY"
WORKFLOW_NAME = "Image Gen Test"
WEBHOOK_PATH = "generate-image"
# Desde n8n en Docker, 127.0.0.1 es el contenedor; host.docker.internal es la máquina host
GENERATOR_URL = "http://host.docker.internal:8002/generate"


def _workflow_payload():
    wid, hid, rid = "w1", "h1", "r1"
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
                    "url": GENERATOR_URL,
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
        print("Comprueba N8N_MCP_BASE_URL (misma URL donde abres n8n en el navegador) y que la API key sea de esa instancia.")
        return
    data = r.json()
    workflows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(workflows, list):
        workflows = [workflows] if workflows else []
    image_gen_workflows = [w for w in workflows if w.get("name") == WORKFLOW_NAME]

    async with httpx.AsyncClient(timeout=30.0) as client:
        if len(image_gen_workflows) > 1:
            for w in image_gen_workflows:
                dr = await client.delete(f"{api_base}/workflows/{w.get('id')}", headers=headers)
                if dr.status_code in (200, 204):
                    print("Eliminado duplicado id:", w.get("id"))
            image_gen_workflows = []

        if len(image_gen_workflows) == 1:
            wf_id = image_gen_workflows[0].get("id")
            gr = await client.get(f"{api_base}/workflows/{wf_id}", headers=headers)
            if gr.status_code == 200:
                wf = gr.json()
                updated = False
                for node in wf.get("nodes", []):
                    if node.get("type") == "n8n-nodes-base.httpRequest" and node.get("parameters"):
                        if "127.0.0.1:8002" in str(node["parameters"].get("url", "")):
                            node["parameters"]["url"] = GENERATOR_URL
                            updated = True
                    if node.get("type") == "n8n-nodes-base.respondToWebhook" and node.get("parameters"):
                        if node["parameters"].get("respondWith") != "firstIncomingItem":
                            node["parameters"]["respondWith"] = "firstIncomingItem"
                            if "responseBody" in node["parameters"]:
                                del node["parameters"]["responseBody"]
                            updated = True
                if updated:
                    # PUT solo acepta: name, nodes, connections, settings, staticData, shared
                    # PUT: solo enviar campos editables; shared/staticData pueden tener campos read-only
                    put_body = {k: wf[k] for k in ("name", "nodes", "connections", "settings") if k in wf}
                    pr = await client.put(f"{api_base}/workflows/{wf_id}", json=put_body, headers=headers)
                    if pr.status_code == 200:
                        print("Workflow actualizado: generador y Respond to Webhook (firstIncomingItem).")
                    else:
                        print("Error al guardar workflow:", pr.status_code, pr.text[:200])
            ar = await client.post(f"{api_base}/workflows/{wf_id}/activate", headers=headers)
            print("Un solo workflow 'Image Gen Test' (id:", wf_id, ").")
            print("Abre en el navegador:", base + "/workflow/" + wf_id)
            print("En n8n: Guarda (Ctrl+S) y activa el toggle para registrar el webhook.")
            print("Webhook:", webhook_url)
            return

        r = await client.post(f"{api_base}/workflows", json=_workflow_payload(), headers=headers)
    if r.status_code not in (200, 201):
        print("Error crear workflow:", r.status_code, r.text[:600])
        return
    created = r.json()
    wf_id = created.get("id") or (created.get("data") or {}).get("id")
    if not wf_id:
        print("Respuesta de crear (sin id):", json.dumps(created, indent=2)[:800])
        return
    async with httpx.AsyncClient(timeout=10.0) as client:
        ar = await client.post(f"{api_base}/workflows/{wf_id}/activate", headers=headers)
    print("Workflow creado. id:", wf_id)
    print("Abre en el navegador:", base + "/workflow/" + wf_id)
    print("En n8n: Guarda (Ctrl+S) y activa el toggle para que el webhook funcione.")
    print("Webhook:", webhook_url)


if __name__ == "__main__":
    asyncio.run(main())
