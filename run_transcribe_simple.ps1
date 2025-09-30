# Jednoduchý skript pro spuštění transkripce s monitoringem
param(
    [string]$InputRun = "01K6CPN9XFNSRPCCDZ98A9V2EH",
    [int]$Limit = 1,
    [string]$Mode = "incr"
)

Write-Host "=== 🚀 TRANSCRIPTION WITH MONITORING ===" -ForegroundColor Green
Write-Host ""

# Vytvoř příkaz pro transkripci
$transcribeCmd = "venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode $Mode --input-run $InputRun --limit $Limit --config steps\transcribe_asr_adapter\input\config.yaml"

Write-Host "📋 Příkaz:" -ForegroundColor Cyan
Write-Host "   $transcribeCmd" -ForegroundColor Gray
Write-Host ""

# Spusť monitoring v novém okně
Write-Host "📊 Otevírám monitoring okno..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\watch_progress.ps1"
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "🎬 Spouštím transkripci..." -ForegroundColor Green
Write-Host ""

# Spusť transkripci
Invoke-Expression $transcribeCmd

Write-Host ""
Write-Host "✅ Transkripce dokončena!" -ForegroundColor Green
