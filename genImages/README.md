# mcp-image-gen 🎨

Servidor MCP para generación de imágenes con **FLUX.1** via **ComfyUI**.
Parte del stack `media-mcp-suite` para n8n.

## Stack

| Componente | Tecnología |
|---|---|
| Generación | FLUX.1 [schnell] FP8 |
| Backend | ComfyUI API |
| Servidor MCP | FastMCP (Python SDK) |
| Gestor deps | uv |
| Transport | Streamable HTTP (puerto 8001) |

---

## Instalación

### 1. Instalar uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Instalar ComfyUI (con GPU recomendado)

**Para usar la GPU de tu PC** (recomendado), sigue la guía en la raíz del repo:

- **[COMFYUI_SETUP.md](../COMFYUI_SETUP.md)** — scripts automáticos en Windows: `scripts/setup_comfyui_gpu.ps1` y `scripts/run_comfyui_gpu.ps1` (instalan PyTorch con CUDA y arrancan ComfyUI).

Instalación manual (si no usas los scripts):

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
# En Windows con GPU: instalar primero PyTorch con CUDA, luego:
pip install -r requirements.txt
```

### 3. Descargar FLUX.1 [schnell] FP8

**Recomendado para RTX 4060 8GB** — cabe en VRAM con calidad excelente:

```bash
# Opción A: desde Hugging Face CLI
pip install huggingface_hub
huggingface-cli download black-forest-labs/FLUX.1-schnell \
    flux1-schnell.safetensors \
    --local-dir ComfyUI/models/checkpoints/

# Opción B: versión FP8 (más pequeña, igual calidad)
# Descargar manualmente desde:
# https://huggingface.co/Comfy-Org/flux1-schnell/blob/main/flux1-schnell-fp8.safetensors
# y colocar en: ComfyUI/models/checkpoints/
```

También necesitas los modelos VAE y CLIP de FLUX.1:

```bash
# VAE
huggingface-cli download black-forest-labs/FLUX.1-schnell \
    ae.safetensors \
    --local-dir ComfyUI/models/vae/

# CLIP / T5
huggingface-cli download comfyanonymous/flux_text_encoders \
    clip_l.safetensors t5xxl_fp8_e4m3fn.safetensors \
    --local-dir ComfyUI/models/clip/
```

### 4. Iniciar ComfyUI

Con GPU (si usaste los scripts): desde la raíz del repo `genImages` ejecuta `.\scripts\run_comfyui_gpu.ps1`.

Manual:

```bash
cd ComfyUI
python main.py --listen 127.0.0.1 --port 8188
```

### 5. Instalar y configurar mcp-image-gen

```bash
cd mcp-image-gen
cp .env.example .env
# Editar .env si es necesario (paths, modelo, etc.)

uv sync
```

### 6. Iniciar el servidor MCP

```bash
uv run server.py
# Servidor disponible en: http://127.0.0.1:8001/mcp
```

---

## Tools disponibles

### `image_gen_generate`

Genera imágenes desde texto usando FLUX.1.

```json
{
  "prompt": "Aerial view of Colombian coffee region, golden hour, cinematic, 8k",
  "aspect_ratio": "16:9",
  "steps": 4,
  "guidance_scale": 3.5,
  "seed": 42,
  "output_format": "png",
  "response_format": "json"
}
```

**Aspect ratios soportados**: `1:1` (1024×1024), `16:9` (1280×720), `9:16` (720×1280), `4:3` (1024×768), `21:9` (1344×576), `custom`

**FLUX.1 schnell tips:**
- `steps`: 1-8 es suficiente (recomendado: 4)
- `guidance_scale`: 1.0-5.0 (recomendado: 3.5)
- FP8 usa ~6GB VRAM → queda headroom para otras operaciones

### `image_gen_list`

Lista imágenes generadas con paginación.

```json
{
  "limit": 20,
  "offset": 0,
  "response_format": "json"
}
```

### `image_gen_info`

Metadata de una imagen específica.

```json
{
  "image_path": "/absolute/path/to/image.png",
  "response_format": "json"
}
```

---

## API REST `POST /generate`

El servidor `rest_api.py` (puerto 8002) expone un único endpoint para n8n u otros clientes HTTP.

**Request:** `Content-Type: application/json`, body con `description` o `prompt` (mín. 3 caracteres). Opcionales: `aspect_ratio`, `width`, `height`, `steps`, `guidance_scale`.

**Respuesta cuando genera correctamente:**

```json
{
    "success": true,
    "images": [
        {
            "image_path": "C:\\...\\outputs\\images\\flux_mcp_00005_.png",
            "filename": "flux_mcp_00005_.png",
            "width": 1920,
            "height": 1088,
            "format": "png",
            "seed": 3745989268,
            "prompt": "A breathtaking aerial photograph...",
            "steps": 8,
            "guidance_scale": 4,
            "file_size_bytes": 3283560,
            "generation_time_ms": 88390
        }
    ],
    "total_generated": 1,
    "error": null
}
```

**Respuesta cuando falla:** `success: false`, `images: []`, `total_generated: 0`, `error` con el mensaje (ej. ComfyUI no responde, timeout).

---

## Integración con n8n

En n8n, agrega un nodo **MCP Client** (HTTP):

```
URL: http://127.0.0.1:8001/mcp
Transport: Streamable HTTP
```

El servidor expone las 3 tools como herramientas MCP estándar.

---

## Variables de entorno

Ver `.env.example` para la lista completa. Las más importantes:

| Variable | Default | Descripción |
|---|---|---|
| `IMAGE_MCP_COMFYUI_URL` | `http://127.0.0.1:8188` | URL de ComfyUI |
| `IMAGE_MCP_DEFAULT_MODEL` | `flux1-schnell-fp8.safetensors` | Checkpoint FLUX.1 |
| `IMAGE_MCP_OUTPUT_DIR` | `./outputs/images` | Dónde guardar imágenes |
| `IMAGE_MCP_SERVER_PORT` | `8001` | Puerto del servidor MCP |

---

## Estructura del proyecto

```
mcp-image-gen/
├── server.py              # Entry point — FastMCP + lifespan
├── pyproject.toml         # Dependencias (uv)
├── .env.example           # Variables de entorno
├── shared/
│   ├── config.py          # Settings (pydantic-settings)
│   └── models.py          # Schemas Pydantic compartidos
├── backends/
│   └── comfyui.py         # Cliente async ComfyUI API
└── tools/
    ├── generate.py        # Tool: image_gen_generate
    └── info.py            # Tools: image_gen_list, image_gen_info
```
