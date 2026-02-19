"""Prueba el workflow que llama al MCP/generador: POST al webhook (API del workflow)."""
import asyncio
import json
import httpx
from config import settings

WEBHOOK_PATH = "generate-image"


async def main():
    base = settings.base_url.rstrip("/")
    url = f"{base}/webhook/{WEBHOOK_PATH}"
    body = {"description": "una manzana roja sobre mesa blanca, luz de estudio", "prompt": "A red apple on a white table, studio lighting"}
    print("POST", url)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=body)
    print("Status:", r.status_code, "Content-Length:", len(r.content))
    try:
        if not r.content:
            print("Body vacío. Revisa en n8n que el nodo 'Respond to Webhook' devuelva la salida del HTTP Request.")
            return
        data = r.json()
        # Si la respuesta es muy larga (ej. base64), mostrar resumen
        s = json.dumps(data, indent=2, ensure_ascii=False)
        if len(s) > 2500:
            print(s[:2400] + "\n... [recortado]")
        else:
            print(s)
        if data.get("success") and data.get("images"):
            print("\nOK: el workflow llamó al generador y devolvió imágenes.")
        elif data.get("success") is False and data.get("error"):
            print("\nGenerador respondió (ComfyUI puede no estar corriendo):", (data.get("error") or "")[:200])
        elif r.status_code == 404:
            print("\nWebhook no registrado: en n8n abre el workflow 'Image Gen Test', guarda y activa el toggle.")
        else:
            print("\nRevisa que rest_api.py (puerto 8002) esté corriendo y que la URL del nodo HTTP sea host.docker.internal:8002.")
    except Exception as e:
        print("Body (raw):", r.text[:800] if r.text else "(vacío)", "Error:", e)


if __name__ == "__main__":
    asyncio.run(main())
