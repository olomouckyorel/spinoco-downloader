# Real-time progress monitor pro transkripci
param(
    [string]$RunId = ""
)

$transcribeDir = "steps\transcribe_asr_adapter\output\runs"

if ($RunId -eq "") {
    # Najdi nejnovejsi run
    $runs = Get-ChildItem $transcribeDir -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($runs.Count -gt 0) {
        $RunId = $runs[0].Name
        Write-Host "Sleduju nejnovejsi run: $RunId" -ForegroundColor Cyan
    } else {
        Write-Host "Zadne runy nenalezeny. Cekam..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        $runs = Get-ChildItem $transcribeDir -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
        if ($runs.Count -gt 0) {
            $RunId = $runs[0].Name
        } else {
            Write-Host "Stale zadne runy. Ukoncuji." -ForegroundColor Red
            exit 1
        }
    }
}

$progressFile = "$transcribeDir\$RunId\progress.json"
$logFile = "logs\transcriber.log"

Write-Host ""
Write-Host "=== PROGRESS MONITOR ===" -ForegroundColor Green
Write-Host "Progress: $progressFile" -ForegroundColor Gray
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

$lastContent = ""
$lastLogLine = 0

while ($true) {
    Clear-Host
    Write-Host "=== TRANSCRIPTION PROGRESS ===" -ForegroundColor Green
    Write-Host "Run ID: $RunId" -ForegroundColor Cyan
    Write-Host "Time: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
    Write-Host ""
    
    # Progress
    if (Test-Path $progressFile) {
        try {
            $progress = Get-Content $progressFile -Raw | ConvertFrom-Json
            
            $phase = $progress.phase
            $pct = $progress.pct
            $msg = $progress.msg
            $updated = $progress.updated_at_utc
            
            # Progress bar
            $barLength = 40
            $filled = [Math]::Floor($pct / 100 * $barLength)
            $empty = $barLength - $filled
            $filledBar = "#" * $filled
            $emptyBar = "-" * $empty
            $bar = "[$filledBar$emptyBar]"
            
            Write-Host "Phase: $phase" -ForegroundColor Cyan
            Write-Host "$bar $pct%" -ForegroundColor Green
            Write-Host "Status: $msg" -ForegroundColor White
            Write-Host "Updated: $updated" -ForegroundColor Gray
            Write-Host ""
            
            if ($progress.eta_s) {
                $etaMin = [Math]::Ceiling($progress.eta_s / 60)
                Write-Host "ETA: ~$etaMin minutes" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "Chyba pri cteni progress: $_" -ForegroundColor Red
        }
    } else {
        Write-Host "Cekam na progress file..." -ForegroundColor Yellow
    }
    
    # Recent log lines
    Write-Host ""
    Write-Host "--- Recent Logs ---" -ForegroundColor Magenta
    if (Test-Path $logFile) {
        $logs = Get-Content $logFile -Tail 5 -ErrorAction SilentlyContinue
        foreach ($log in $logs) {
            try {
                $logObj = $log | ConvertFrom-Json
                $time = ([DateTime]$logObj.timestamp).ToString("HH:mm:ss")
                $level = $logObj.level.ToUpper()
                $event = $logObj.event
                
                $color = "White"
                if ($level -eq "WARNING") { $color = "Yellow" }
                if ($level -eq "ERROR") { $color = "Red" }
                
                Write-Host "[$time] $level - $event" -ForegroundColor $color
            } catch {
                Write-Host $log -ForegroundColor Gray
            }
        }
    }
    
    # Check if done
    $manifestFile = "$transcribeDir\$RunId\manifest.json"
    if (Test-Path $manifestFile) {
        try {
            $manifest = Get-Content $manifestFile -Raw | ConvertFrom-Json
            if ($manifest.status -eq "success" -or $manifest.status -eq "partial" -or $manifest.status -eq "error") {
                Write-Host ""
                Write-Host "DONE! Status: $($manifest.status)" -ForegroundColor Green
                break
            }
        } catch {
            # Manifest jeste neni kompletni
        }
    }
    
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Monitoring ukoncen. Stisknete libovolnou klavesu..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")