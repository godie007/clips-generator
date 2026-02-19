"""
Prueba que la lógica de la tool MCP n8n_trigger_image_workflow funciona:
POST al webhook con prompt/description y comprueba respuesta JSON del generador.
"""
import asyncio
import json
import httpx
from config import settings

WEBHOOK_PATH = "generate-image"


def _webhook_url(path: str) -> str:
    base = settings.base_url.rstrip("/")
    p = path.lstrip("/")
    if p.startswith("webhook/") or p.startswith("webhook-test/"):
        return f"{base}/{p}"
    return f"{base}/webhook/{p}"


async def main():
    url = _webhook_url(WEBHOOK_PATH)
    body = {"prompt": "una manzana roja sobre mesa blanca", "description": "una manzana roja sobre mesa blanca"}
    print("Simulando MCP n8n_trigger_image_workflow -> POST", url)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=body, headers={"Accept": "application/json", "Content-Type": "application/json"})
    print("Status:", r.status_code)
    if not r.content:
        print("ERROR: cuerpo vacío. Revisa Respond to Webhook (firstIncomingItem).")
        return 1
    try:
        data = r.json()
    except Exception as e:
        print("ERROR: respuesta no es JSON:", e, "| Body:", r.text[:300])
        return 1
    # El generador devuelve { success, images?, error? }
    if "success" in data or "error" in data or "images" in data:
        print("MCP OK: el webhook devuelve la respuesta del generador.")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:600])
        if len(json.dumps(data)) > 600:
            print("...")
        return 0
    print("Respuesta inesperada:", data)
    return 1


if __name__ == "__main__":
    exit(asyncio.run(main()))
