# Genera una imagen llamando al webhook de n8n (que a su vez llama al servicio REST del generador).
# Requisitos: n8n en marcha (puerto 5678), rest_api.py en marcha (8002), ComfyUI (8188).
# Uso: .\run_webhook_generate.ps1
#      .\run_webhook_generate.ps1 -PayloadFile .\mi_payload.json

param(
    [string]$PayloadFile = "webhook_payload.json"
)

$url = "http://localhost:5678/webhook/generate-image"
if (-not (Test-Path $PayloadFile)) {
    Write-Host "Creando $PayloadFile de ejemplo..." -ForegroundColor Yellow
    @{ description = "A breathtaking aerial photograph of the Colombian coffee region (Eje Cafetero) at golden hour, rolling green hills, traditional bahareque farmhouses, National Geographic quality" } | ConvertTo-Json | Set-Content $PayloadFile -Encoding UTF8
}
Write-Host "POST $url" -ForegroundColor Cyan
Write-Host "Payload: $PayloadFile" -ForegroundColor Gray
$body = Get-Content $PayloadFile -Raw -ErrorAction Stop
try {
    $r = Invoke-RestMethod -Uri $url -Method POST -ContentType "application/json" -Body $body -TimeoutSec 300
    $r | ConvertTo-Json -Depth 6
    if ($r.success -and $r.images) { Write-Host "`nImagen(es) generada(s)." -ForegroundColor Green }
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    exit 1
}
