# Clips Generator — Imágenes y audio con MCP + n8n

Stack para generar **imágenes** (FLUX.1 + ComfyUI) y **audio** (Chatterbox TTS), con servidores MCP, APIs REST e integración n8n.

## Estructura del proyecto

```
├── README.md
├── COMFYUI_SETUP.md
├── docker-compose.yml     # n8n (opcional)
├── .gitignore
├── scripts/               # ComfyUI GPU (Windows)
├── genImages/             # Imágenes: MCP (8001) + REST (8002)
├── genAudio/              # Audio TTS: MCP (8003) + REST (8004)
└── n8n-mcp-service/       # MCP n8n (8010): dispara workflows imagen y audio
```

## Inicio rápido

**Imágenes**
1. ComfyUI con GPU — [COMFYUI_SETUP.md](COMFYUI_SETUP.md) y `.\scripts\run_comfyui_gpu.ps1`
2. Generador — `cd genImages && pip install -e . && python rest_api.py` (8002)
3. MCP imagen — `cd genImages && python server.py` (8001)

**Audio (TTS)**
1. Generador — `cd genAudio && pip install -e . && python rest_api.py` (8004)
2. MCP audio — `cd genAudio && python server.py` (8003)

**n8n**
- `docker-compose up`; configurar MCP con `n8n-mcp-service`
- Workflows: `python create_workflow.py` (imagen), `python create_workflow_audio.py` (audio)
- Webhooks: `POST /webhook/generate-image` (body: `description`), `POST /webhook/generate-audio` (body: `text`)

Documentación: [genImages/README.md](genImages/README.md), [genAudio/README.md](genAudio/README.md).
