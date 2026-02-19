# Arranca ComfyUI usando GPU (NVIDIA).
# Asegura que se use el entorno con PyTorch+CUDA instalado.

$ErrorActionPreference = "Stop"
$ComfyUIBase = if ($env:COMFYUI_DIR) { $env:COMFYUI_DIR } else { Join-Path (Join-Path $PSScriptRoot "..") "ComfyUI" }
$ComfyUIRoot = $ComfyUIBase
if (Test-Path $ComfyUIBase) { $ComfyUIRoot = (Resolve-Path $ComfyUIBase).Path }

$mainPy = Join-Path $ComfyUIRoot "main.py"
if (-not (Test-Path $mainPy)) {
    Write-Host "ComfyUI no encontrado en: $ComfyUIRoot" -ForegroundColor Red
    Write-Host "Ejecuta primero: .\scripts\setup_comfyui_gpu.ps1" -ForegroundColor Yellow
    exit 1
}

$venvScripts = Join-Path (Join-Path (Join-Path $ComfyUIRoot ".venv") "Scripts") "Activate.ps1"
if (Test-Path $venvScripts) {
    & $venvScripts
    Write-Host "Entorno virtual ComfyUI activado (GPU)." -ForegroundColor Green
} else {
    Write-Host "Aviso: no hay .venv en ComfyUI; usando Python del sistema." -ForegroundColor Yellow
}

Write-Host "Iniciando ComfyUI en http://127.0.0.1:8188 (GPU por defecto si PyTorch tiene CUDA)..." -ForegroundColor Cyan
Set-Location $ComfyUIRoot
python main.py --listen 127.0.0.1 --port 8188
