# Setup ComfyUI con soporte GPU (NVIDIA CUDA) en Windows.
# Ejecutar desde: PowerShell (como usuario normal).
# Requisitos: Git, Python 3.10/3.11, NVIDIA drivers actualizados.

$ErrorActionPreference = "Stop"
$ComfyUIBase = if ($env:COMFYUI_DIR) { $env:COMFYUI_DIR } else { Join-Path (Join-Path $PSScriptRoot "..") "ComfyUI" }
$ComfyUIRoot = (Resolve-Path $ComfyUIBase -ErrorAction SilentlyContinue).Path
if (-not $ComfyUIRoot) { $ComfyUIRoot = $ComfyUIBase }

Write-Host "=== ComfyUI GPU Setup ===" -ForegroundColor Cyan
Write-Host "Ruta ComfyUI: $ComfyUIRoot"
Write-Host ""

# 1) Clonar si no existe
if (-not (Test-Path (Join-Path $ComfyUIRoot "main.py"))) {
    $parent = Split-Path $ComfyUIRoot -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Write-Host "Clonando ComfyUI..." -ForegroundColor Yellow
    git clone https://github.com/comfyanonymous/ComfyUI.git $ComfyUIRoot
    if ($LASTEXITCODE -ne 0) { throw "git clone fallo" }
} else {
    Write-Host "ComfyUI ya existe en $ComfyUIRoot" -ForegroundColor Green
}

# 2) Venv
$venvPath = Join-Path $ComfyUIRoot ".venv"
if (-not (Test-Path (Join-Path $venvPath "Scripts\activate.ps1"))) {
    Write-Host "Creando entorno virtual..." -ForegroundColor Yellow
    python -m venv $venvPath
    if ($LASTEXITCODE -ne 0) { throw "python -m venv fallo. Instala Python 3.10 o 3.11." }
}
$activate = Join-Path $venvPath "Scripts\Activate.ps1"
. $activate

# 3) PyTorch con CUDA (primero, para que requirements.txt no instale CPU)
Write-Host "Instalando PyTorch con CUDA (GPU)..." -ForegroundColor Yellow
python -m pip install --upgrade pip
# cu124 = CUDA 12.4 (Python 3.13); cu121 para Python 3.10-3.12
$pyVer = (python -c "import sys; print(f'{sys.version_info.major}{sys.version_info.minor}')" 2>$null)
$cuIndex = if ($pyVer -ge "313") { "cu124" } else { "cu121" }
pip install torch torchvision torchaudio --index-url "https://download.pytorch.org/whl/$cuIndex"
if ($LASTEXITCODE -ne 0) { throw "pip install torch fallo" }

# 4) Dependencias ComfyUI
Write-Host "Instalando dependencias de ComfyUI..." -ForegroundColor Yellow
Set-Location $ComfyUIRoot
pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "pip install -r requirements.txt fallo" }

# 5) Carpetas de modelos
$checkpoints = Join-Path $ComfyUIRoot "models" "checkpoints"
$vae = Join-Path $ComfyUIRoot "models" "vae"
$clip = Join-Path $ComfyUIRoot "models" "clip"
foreach ($d in @($checkpoints, $vae, $clip)) {
    if (-not (Test-Path $d)) { New-Item -ItemType Directory -Path $d -Force | Out-Null }
}

# 6) Verificar GPU
Write-Host ""
Write-Host "Verificando GPU..." -ForegroundColor Cyan
python -c "import torch; print('CUDA disponible:', torch.cuda.is_available()); print('Dispositivo:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'N/A')"
if ($LASTEXITCODE -ne 0) { Write-Host "Advertencia: no se pudo verificar CUDA." -ForegroundColor Red }

Write-Host ""
Write-Host "=== Setup completado ===" -ForegroundColor Green
Write-Host "Descarga el modelo FLUX.1 y ponlo en: $checkpoints"
Write-Host "  Ejemplo: flux1-schnell-fp8.safetensors"
Write-Host "  https://huggingface.co/Comfy-Org/flux1-schnell"
Write-Host ""
Write-Host "Para arrancar ComfyUI con GPU:"
Write-Host "  .\scripts\run_comfyui_gpu.ps1"
Write-Host "  o: cd $ComfyUIRoot ; .\.venv\Scripts\Activate.ps1 ; python main.py --listen 127.0.0.1 --port 8188"
