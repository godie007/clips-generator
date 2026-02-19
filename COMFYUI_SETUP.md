# ComfyUI con GPU (NVIDIA)

Para que el generador de imágenes funcione y **aproveche la GPU** de tu PC, ComfyUI debe estar instalado y en marcha con PyTorch + CUDA.

## Opción A: Scripts automáticos (recomendado)

### 1. Requisitos

- **Windows**: PowerShell, Git, Python 3.10 o 3.11.
- **NVIDIA**: Drivers actualizados ([NVIDIA Driver](https://www.nvidia.com/drivers) o GeForce Experience).
- Opcional: [CUDA Toolkit 12.x](https://developer.nvidia.com/cuda-downloads) si los drivers no incluyen CUDA.

### 2. Instalar ComfyUI con GPU

Desde la raíz del proyecto `genImages`:

```powershell
cd C:\Users\diego\workspace\codytion\genVideo\genImages
.\scripts\setup_comfyui_gpu.ps1
```

El script:

- Clona ComfyUI en `genImages/ComfyUI` (o en `%COMFYUI_DIR%` si lo defines).
- Crea un venv e instala **PyTorch con CUDA 12.1** (usa la GPU).
- Instala las dependencias de ComfyUI.
- Crea las carpetas `models/checkpoints`, `models/vae`, `models/clip`.

### 3. Descargar el modelo FLUX.1

El generador usa FLUX.1 schnell. Coloca el checkpoint en ComfyUI:

```
genImages/ComfyUI/models/checkpoints/
```

**Recomendado para GPU 8GB** (ej. RTX 4060): `flux1-schnell-fp8.safetensors`

- [Comfy-Org/flux1-schnell (Hugging Face)](https://huggingface.co/Comfy-Org/flux1-schnell) — descargar `flux1-schnell-fp8.safetensors` y copiarlo en `ComfyUI/models/checkpoints/`.

O con CLI:

```powershell
pip install huggingface_hub
huggingface-cli download Comfy-Org/flux1-schnell flux1-schnell-fp8.safetensors --local-dir genImages/ComfyUI/models/checkpoints/
```

Opcional (VAE y CLIP si ComfyUI lo pide):

```powershell
huggingface-cli download black-forest-labs/FLUX.1-schnell ae.safetensors --local-dir genImages/ComfyUI/models/vae/
huggingface-cli download comfyanonymous/flux_text_encoders clip_l.safetensors t5xxl_fp8_e4m3fn.safetensors --local-dir genImages/ComfyUI/models/clip/
```

### 4. Arrancar ComfyUI (con GPU)

En la misma terminal:

```powershell
.\scripts\run_comfyui_gpu.ps1
```

O en una ventana nueva (y dejar ComfyUI abierto):

```powershell
.\scripts\start_comfyui_and_check.ps1
```

Se abre en **http://127.0.0.1:8188**. ComfyUI usará la GPU si PyTorch se instaló con CUDA (el script de setup lo hace).

### 5. Comprobar que usa la GPU

En la terminal donde corre ComfyUI no debería aparecer “CPU” como dispositivo. Además:

```powershell
cd genImages\ComfyUI
.\.venv\Scripts\Activate.ps1
python -c "import torch; print('CUDA:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
```

Debe salir `CUDA: True` y el nombre de tu GPU.

---

## Opción B: ComfyUI Desktop (instalador oficial)

1. Descarga el instalador para Windows (NVIDIA):  
   [Download ComfyUI Desktop (Windows)](https://download.comfy.org/windows/nsis/x64)
2. Instala y en el asistente elige **Nvidia GPU**.
3. La primera vez descargará Python y PyTorch con CUDA.
4. Abre ComfyUI Desktop; el servidor suele exponerse en el puerto **8188**. Si usa otro puerto, configura en tu `.env`:

   ```env
   IMAGE_MCP_COMFYUI_URL=http://127.0.0.1:8188
   ```

---

## Variable opcional COMFYUI_DIR

Si ComfyUI está en otra ruta:

```env
# En .env del proyecto o en el sistema
COMFYUI_DIR=C:\ruta\a\ComfyUI
```

Los scripts `setup_comfyui_gpu.ps1` y `run_comfyui_gpu.ps1` usan esa ruta.

---

## Orden de arranque

1. **ComfyUI** (puerto 8188) — `.\scripts\run_comfyui_gpu.ps1`
2. **rest_api.py** (puerto 8002) — desde `genImages/genImages`: `python rest_api.py`
3. n8n y el MCP según tu flujo.

Si “ComfyUI no responde”, comprueba que ComfyUI esté abierto en 8188 y que en el navegador **http://127.0.0.1:8188** cargue la interfaz.

### Comprobar estado desde la API

Con `rest_api.py` en marcha (puerto 8002):

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8002/health" -Method GET
```

Si ComfyUI está bien: `ok: true` y lista de checkpoints. Si no: `ok: false` y mensaje para arrancar ComfyUI con GPU.
