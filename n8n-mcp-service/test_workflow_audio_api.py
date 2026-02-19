"""Prueba el workflow de audio: POST al webhook de n8n (simula llamada desde n8n)."""
import asyncio
import json
import httpx
from config import settings

WEBHOOK_PATH = "generate-audio"


async def main():
    base = settings.base_url.rstrip("/")
    url = f"{base}/webhook/{WEBHOOK_PATH}"
    body = {"text": "Hello from n8n test. This is a short audio sample."}
    print("POST", url)
    print("Body:", json.dumps(body, ensure_ascii=False))
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=body)
    print("Status:", r.status_code, "Content-Length:", len(r.content))
    try:
        if not r.content:
            print("Body vacío. Revisa en n8n que 'Respond to Webhook' devuelva la salida del HTTP Request.")
            return
        data = r.json()
        s = json.dumps(data, indent=2, ensure_ascii=False)
        if len(s) > 3000:
            print(s[:2800] + "\n... [recortado]")
        else:
            print(s)
        if data.get("success") and (data.get("filename") or data.get("base64_audio")):
            print("\nOK: el workflow llamó a genAudio y devolvió audio.")
        elif data.get("success") is False and data.get("error"):
            print("\nGenAudio respondió (puede faltar chatterbox-tts o no estar en marcha):", (data.get("error") or "")[:300])
        elif r.status_code == 404:
            print("\nWebhook no registrado: en n8n abre el workflow 'Audio Gen Test', guarda y activa el toggle.")
        else:
            print("\nRevisa que rest_api.py de genAudio esté en 8004 y que el nodo HTTP use host.docker.internal:8004.")
    except Exception as e:
        print("Body (raw):", r.text[:800] if r.text else "(vacío)", "Error:", e)


if __name__ == "__main__":
    asyncio.run(main())
