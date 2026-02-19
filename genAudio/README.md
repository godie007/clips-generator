# mcp-audio-gen

Servidor MCP y API REST para **generar audio desde texto** con [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) (Resemble AI).

## Requisitos

- **Python 3.10 o 3.11** (Chatterbox TTS puede fallar en 3.12+ por dependencias)
- PyTorch + **CUDA** (recomendado para velocidad) o CPU
- NVIDIA GPU con drivers actualizados (para CUDA)

## Instalación

```bash
cd genAudio
pip install -e .
pip install chatterbox-tts torch torchaudio
```

Si quieres **usar la GPU (CUDA)** y ves "CUDA no disponible (torch sin CUDA)", reinstala torch/torchaudio con soporte CUDA (ver sección [Usar CUDA (GPU)](#usar-cuda-gpu) más abajo).

## Uso

### Servidor MCP (puerto 8003)

```bash
python server.py
# http://127.0.0.1:8003/mcp
```

### API REST (puerto 8004) — para n8n

```bash
python rest_api.py
# POST http://127.0.0.1:8004/generate
```

**Request:** `Content-Type: application/json`

| Campo | Tipo | Requerido | Default | Descripción |
|-------|------|-----------|---------|-------------|
| `text` / `prompt` | string | sí | — | Texto a sintetizar (máx. 5000 caracteres). |
| `language` / `language_id` | string | no | `"en"` | Código de idioma (en, es, fr, de, it, pt, ja, zh, …). Ver `GET /languages`. |
| `audio_prompt_path` | string | no | — | Ruta a un WAV de referencia para clonar voz (~10 s). Si no se envía, se usa el de `AUDIO_MCP_DEFAULT_AUDIO_PROMPT_PATH` si está definido. |
| `exaggeration` | float | no | 0.4 | Intensidad emocional (0.0–2.0). Más bajo = voz más sobria. |
| `cfg_weight` | float | no | 0.5 | Peso CFG / ritmo (0.0–1.0). |
| `temperature` | float | no | 0.6 | Temperatura de muestreo (0.05–2.0). Más bajo = más claro y articulado. |
| `repetition_penalty` | float | no | 2.0 | Penalización por repetición. |
| `min_p` | float | no | 0.05 | Muestreo min-p. |
| `top_p` | float | no | 1.0 | Muestreo top-p. |
| `speed` | float | no | 1.0 | Ritmo de habla. **1.0 = normal**. **&lt; 1 = más pausado** (ideal para narrar). &gt; 1 = más rápido. Rango 0.5–1.5. |

Ejemplo mínimo:

```json
{ "text": "Hello, this is a test of text to speech." }
```

Ejemplo con idioma y parámetros de voz:

```json
{
  "text": "Hola, esto es una prueba en español.",
  "language": "es",
  "exaggeration": 0.6,
  "temperature": 0.7
}
```

Ejemplo más pausado para narrar:

```json
{
  "text": "Érase una vez un lugar muy lejano...",
  "language": "es",
  "speed": 0.85
}
```

**GET /languages** — Lista de idiomas soportados (código → nombre). Ejemplo: `{"en": "English", "es": "Spanish", ...}`.

**Respuesta correcta (POST /generate):**

```json
{
  "success": true,
  "filename": "chatterbox_123456.wav",
  "audio_path": "/ruta/completa/al/archivo.wav",
  "sample_rate": 24000,
  "text_length": 42,
  "language_id": "es",
  "base64_audio": "...",
  "error": null
}
```

n8n puede decodificar `base64_audio` y guardar el archivo WAV.

### Para que la voz suene más clara

- **Normalización de loudness:** La salida se normaliza automáticamente a -16 LUFS para que el volumen sea uniforme y fácil de escuchar.
- **Referencia de voz:** Usa un audio de referencia en **WAV** (sin compresión) y sin ruido de fondo; si usas MP3, que sea de buena calidad.
- **Por defecto** la voz usa `temperature: 0.6` y `exaggeration: 0.4` para sonar más sobria y articulada. Si aun así suena borracha o rara, baja más: `temperature: 0.5`, `exaggeration: 0.35`.

Si quieres aún más sobrio y claro:
```json
{
  "text": "Tu texto aquí.",
  "language": "es",
  "temperature": 0.5,
  "exaggeration": 0.35
}
```

## Integración con n8n

1. Crea un workflow con Webhook `POST /webhook/generate-audio`.
2. Nodo HTTP Request: `POST http://host.docker.internal:8004/generate`, body `{{ $json.body || $json }}`.
3. Respond to Webhook: First Incoming Item.

Desde el MCP de n8n existe la tool `n8n_trigger_audio_workflow` para disparar este webhook con un texto.

## Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `AUDIO_MCP_OUTPUT_DIR` | `./outputs/audio` | Carpeta de salida WAV |
| `AUDIO_MCP_SERVER_PORT` | 8003 | Puerto MCP |
| `AUDIO_MCP_REST_PORT` | 8004 | Puerto REST |
| `AUDIO_MCP_DEVICE` | cuda | cuda, cpu, mps |
| `AUDIO_MCP_DEFAULT_AUDIO_PROMPT_PATH` | — | Ruta al WAV de tu voz de referencia (~10 s). Si está definida, se usa en cada generación cuando el body no envía `audio_prompt_path`. Ej: `mi_voz_referencia.wav` (relativa al directorio `genAudio`). |

### Voz de referencia por defecto (clonar tu voz)

Para que todas las generaciones usen tu voz sin enviar `audio_prompt_path` en cada request:

1. Graba **unos 10 segundos** de tu voz en WAV (mono o estéreo, sin silencios largos al inicio).
2. Guarda el archivo en el directorio `genAudio`, por ejemplo: `genAudio/mi_voz_referencia.wav`.
3. En tu `.env` añade:
   ```env
   AUDIO_MCP_DEFAULT_AUDIO_PROMPT_PATH=mi_voz_referencia.wav
   ```
4. Reinicia la API. A partir de ahí, los POST a `/generate` sin `audio_prompt_path` usarán esa voz. Para una petición concreta puedes seguir enviando `audio_prompt_path` en el body y tendrá prioridad.

---

## Usar CUDA (GPU)

Si al arrancar ves **"CUDA no disponible (torch sin CUDA), usando CPU"**, tu instalación de PyTorch es solo CPU. Para usar la GPU (más rápido):

1. **Comprueba que tienes drivers NVIDIA actualizados** y, si quieres, la versión de CUDA: `nvidia-smi`.

2. **Reinstala torch y torchaudio con soporte CUDA** dentro del venv de genAudio:

   **Windows (PowerShell), desde `genAudio`:**

   ```powershell
   .\.venv\Scripts\Activate.ps1
   # CUDA 12.4 (recomendado para RTX 30/40). Si tu driver es más antiguo, prueba cu121.
   pip uninstall -y torch torchaudio
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
   ```

   O ejecuta el script incluido:

   ```powershell
   .\.venv\Scripts\python.exe scripts\install_torch_cuda.py
   ```

   **Linux:**

   ```bash
   source .venv/bin/activate
   pip uninstall -y torch torchaudio
   pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124
   ```

3. **Reinicia la API** (`python rest_api.py`). Deberías ver que el modelo se carga en CUDA y la generación es más rápida.

Si no tienes GPU o prefieres CPU, deja `AUDIO_MCP_DEVICE=cuda`; el backend usará CPU automáticamente cuando `torch.cuda.is_available()` sea False.

---

## Si la API devuelve `success: false` y "Instala chatterbox-tts"

Eso indica que **chatterbox-tts** no se pudo cargar (suele fallar en **Python 3.12/3.13** por dependencias nativas). Usa un entorno con **Python 3.10 o 3.11**:

### Opción 1: venv con Python 3.10 o 3.11 (recomendado)

**Windows (PowerShell):**

```powershell
# Si tienes varias versiones: py -0p para listar
cd genAudio
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install chatterbox-tts torch torchaudio
python rest_api.py
```

**Linux/macOS:**

```bash
cd genAudio
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install chatterbox-tts torch torchaudio
python rest_api.py
```

Si no tienes Python 3.11 instalado: en Windows usa el instalador desde [python.org](https://www.python.org/downloads/) o `winget install Python.Python.3.11`; en Ubuntu/Debian: `sudo apt install python3.11 python3.11-venv`.

### Opción 2: Solo CPU (sin CUDA)

Si no necesitas GPU:

```bash
pip install chatterbox-tts torch torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Cuando `rest_api.py` arranque sin errores y `/health` devuelva 200, el webhook de n8n podrá generar el WAV y la respuesta tendrá `success: true`, `filename`, `audio_path` y `base64_audio`.
