# genImages — Generación de imágenes con FLUX.1

Stack para generar imágenes en 4K vía **ComfyUI** + **FLUX.1**, con servidor MCP, API REST y integración n8n.

## Estructura del proyecto

```
genImages/
├── README.md              # Este archivo
├── COMFYUI_SETUP.md       # Guía ComfyUI + GPU
├── docker-compose.yml     # n8n (opcional)
├── .gitignore
├── scripts/               # Scripts Windows (ComfyUI GPU)
│   ├── setup_comfyui_gpu.ps1
│   ├── run_comfyui_gpu.ps1
│   └── start_comfyui_and_check.ps1
├── genImages/             # Servidor MCP + API REST (generador)
│   ├── README.md
│   ├── pyproject.toml
│   ├── server.py          # MCP (puerto 8001)
│   ├── rest_api.py        # REST POST /generate (puerto 8002)
│   ├── shared/            # Config y modelos
│   ├── backends/          # Cliente ComfyUI
│   └── tools/             # Tools MCP (generate, info)
├── n8n-mcp-service/       # MCP que dispara workflows n8n
│   ├── server.py          # MCP n8n (puerto 8010)
│   ├── create_workflow.py
│   ├── tools_n8n.py
│   ├── test_workflow_api.py
│   └── test_mcp_trigger.py
└── local-files/           # (opcional)
```

## Inicio rápido

1. **ComfyUI con GPU** — [COMFYUI_SETUP.md](COMFYUI_SETUP.md) y `.\scripts\run_comfyui_gpu.ps1`
2. **Generador** — `cd genImages && pip install -e . && python rest_api.py` (puerto 8002)
3. **MCP imagen** — `cd genImages && python server.py` (puerto 8001)
4. **n8n** — `docker-compose up` o instalar n8n; configurar MCP n8n con `n8n-mcp-service`

Documentación detallada del generador: [genImages/README.md](genImages/README.md).
