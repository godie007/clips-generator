# Solucionar 404 en webhook "POST generate-audio"

El error **"The requested webhook POST generate-audio is not registered"** aparece cuando el workflow **no está activo**. En n8n, los webhooks de producción solo se registran con el workflow activado.

## Pasos para que funcione

1. **Abre n8n** en el navegador: http://localhost:5678

2. **Abre el workflow** "Audio Gen Test" (desde la lista de workflows).

3. **Guarda el workflow** por si acaso: `Ctrl+S` (o menú Save).

4. **Activa el workflow** con el interruptor (toggle) que está **arriba a la derecha** del editor:
   - Debe decir **"Inactive"** → haz clic para que pase a **"Active"**.
   - Cuando esté activo, n8n registra la URL de producción:
     - `POST http://localhost:5678/webhook/generate-audio`

5. **Vuelve a probar** tu llamada (Postman, script o MCP):
   ```bash
   cd n8n-mcp-service
   python test_workflow_audio_api.py
   ```

## Comprobar sin activar (solo prueba)

Si quieres probar el flujo **sin** activar el workflow:

1. Abre el workflow "Audio Gen Test".
2. Haz clic en el nodo **Webhook**.
3. En el panel derecho, pulsa **"Listen for Test Event"**.
4. Usa la **Test URL** que te muestra n8n (suele ser `http://localhost:5678/webhook-test/generate-audio`).
5. Envía un POST a esa URL con body `{"text": "Hello"}`.

Esa URL solo funciona mientras el nodo está escuchando; para uso normal (p. ej. desde MCP o otro servicio) necesitas tener el workflow **activado** como en los pasos 1–5.
