# Abre ComfyUI (GPU) en una ventana nueva.
# Luego puedes iniciar rest_api.py en otra terminal para el generador.
# Uso: .\scripts\start_comfyui_and_check.ps1

$ErrorActionPreference = "Stop"
$root = Join-Path $PSScriptRoot ".."
$comfyDir = if ($env:COMFYUI_DIR) { $env:COMFYUI_DIR } else { Join-Path (Resolve-Path $root) "ComfyUI" }
$mainPy = Join-Path $comfyDir "main.py"
$venvActivate = Join-Path $comfyDir ".venv" "Scripts" "Activate.ps1"

if (-not (Test-Path $mainPy)) {
    Write-Host "ComfyUI no encontrado. Ejecuta primero: .\scripts\setup_comfyui_gpu.ps1" -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando ComfyUI con GPU en http://127.0.0.1:8188 ..." -ForegroundColor Cyan
Write-Host "Cierra esta ventana para detener ComfyUI." -ForegroundColor Gray
Write-Host ""

$cmd = "cd '$comfyDir'; & '$venvActivate'; python main.py --listen 127.0.0.1 --port 8188"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $cmd

Write-Host "Ventana de ComfyUI abierta. En otra terminal ejecuta:" -ForegroundColor Green
Write-Host "  cd $root\genImages; python rest_api.py" -ForegroundColor Yellow
Write-Host "Luego prueba: Invoke-RestMethod -Uri http://127.0.0.1:8002/health" -ForegroundColor Yellow
