# Master skript - Spustí transkripci a automaticky otevře monitoring
param(
    [string]$InputRun = "01K6CPN9XFNSRPCCDZ98A9V2EH",
    [int]$Limit = 1,
    [string]$Mode = "incr"
)

Write-Host "=== 🚀 TRANSCRIPTION WITH MONITORING ===" -ForegroundColor Green
Write-Host ""

# Zkontroluj že monitoring skripty existují
if (!(Test-Path "watch_progress.ps1")) {
    Write-Host "❌ watch_progress.ps1 neexistuje!" -ForegroundColor Red
    exit 1
}

# Vytvoř příkaz pro transkripci
$transcribeCmd = "venv\Scripts\python.exe steps\transcribe_asr_adapter\run.py --mode $Mode --input-run $InputRun --limit $Limit --config steps\transcribe_asr_adapter\input\config.yaml"

Write-Host "📋 Příkaz pro transkripci:" -ForegroundColor Cyan
Write-Host "   $transcribeCmd" -ForegroundColor Gray
Write-Host ""

# Spusť monitoring v novém okně
Write-Host "📊 Otevírám monitoring okno..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\watch_progress.ps1"
Start-Sleep -Seconds 2

# Pokud chce uživatel i logy
$openLogs = Read-Host "Otevřít i sledování logů? (y/n)"
if ($openLogs -eq "y") {
    Write-Host "📝 Otevírám log okno..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\watch_logs.ps1"
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "🎬 Spouštím transkripci v tomto okně..." -ForegroundColor Green
Write-Host ""
Start-Sleep -Seconds 2

# Spusť transkripci v aktuálním okně
Invoke-Expression $transcribeCmd

Write-Host ""
Write-Host "✅ Transkripce dokončena!" -ForegroundColor Green
Write-Host "📊 Monitoring okna můžete zavřít." -ForegroundColor Yellow
