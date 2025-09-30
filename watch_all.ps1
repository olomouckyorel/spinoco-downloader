# Komplexni monitoring - progress bar + logy v jednom okne
param(
    [string]$RunId = ""
)

$transcribeDir = "steps\transcribe_asr_adapter\output\runs"
$logFile = "logs\transcriber.log"

# Najdi nejnovejsi run
if ($RunId -eq "") {
    $runs = Get-ChildItem $transcribeDir -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if ($runs.Count -gt 0) {
        $RunId = $runs[0].Name
    } else {
        Write-Host "Cekam na start transkripce..." -ForegroundColor Yellow
        Start-Sleep -Seconds 3
        $runs = Get-ChildItem $transcribeDir -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
        if ($runs.Count -gt 0) {
            $RunId = $runs[0].Name
        }
    }
}

$progressFile = "$transcribeDir\$RunId\progress.json"

Write-Host "============================================" -ForegroundColor Green
Write-Host "     TRANSCRIPTION MONITOR" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
if ($RunId) {
    Write-Host "Run ID: $RunId" -ForegroundColor Cyan
}
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

$logLineCount = 0
$isDone = $false

while (-not $isDone) {
    Clear-Host
    
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "     TRANSCRIPTION MONITOR" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "Time: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
    if ($RunId) {
        Write-Host "Run ID: $RunId" -ForegroundColor Cyan
    }
    Write-Host ""
    
    # === PROGRESS BAR ===
    if ($RunId -and (Test-Path $progressFile)) {
        try {
            $progress = Get-Content $progressFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
            
            $phase = $progress.phase
            $pct = $progress.pct
            $msg = $progress.msg
            
            # Progress bar
            $barLength = 50
            $filled = [Math]::Floor($pct / 100 * $barLength)
            $empty = $barLength - $filled
            $filledBar = "#" * $filled
            $emptyBar = "-" * $empty
            $bar = "[$filledBar$emptyBar]"
            
            Write-Host "PROGRESS:" -ForegroundColor Yellow
            Write-Host "  Phase: $phase" -ForegroundColor Cyan
            Write-Host "  $bar $pct%" -ForegroundColor Green
            Write-Host "  $msg" -ForegroundColor White
            
            if ($progress.eta_s) {
                $etaMin = [Math]::Ceiling($progress.eta_s / 60)
                Write-Host "  ETA: ~$etaMin min" -ForegroundColor Yellow
            }
            
            Write-Host ""
        } catch {
            Write-Host "PROGRESS: Cekam na data..." -ForegroundColor Yellow
            Write-Host ""
        }
    } else {
        Write-Host "PROGRESS: Cekam na start..." -ForegroundColor Yellow
        Write-Host ""
        
        # Zkus znovu najit run
        if (-not $RunId) {
            $runs = Get-ChildItem $transcribeDir -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
            if ($runs.Count -gt 0) {
                $RunId = $runs[0].Name
                $progressFile = "$transcribeDir\$RunId\progress.json"
            }
        }
    }
    
    # === RECENT LOGS ===
    Write-Host "--------------------------------------------" -ForegroundColor Gray
    Write-Host "RECENT ACTIVITY:" -ForegroundColor Yellow
    Write-Host ""
    
    if (Test-Path $logFile) {
        $logs = Get-Content $logFile -Tail 10 -ErrorAction SilentlyContinue
        foreach ($log in $logs) {
            try {
                $logObj = $log | ConvertFrom-Json
                $time = ([DateTime]$logObj.timestamp).ToString("HH:mm:ss")
                $level = $logObj.level.ToUpper()
                $event = $logObj.event
                
                # Zkrat dlouhe zpravy
                if ($event.Length -gt 80) {
                    $event = $event.Substring(0, 77) + "..."
                }
                
                $color = "White"
                $prefix = "  "
                if ($level -eq "WARNING") { 
                    $color = "Yellow"
                    $prefix = "! "
                }
                if ($level -eq "ERROR") { 
                    $color = "Red"
                    $prefix = "X "
                }
                if ($level -eq "INFO" -and $event -like "*dokoncen*") {
                    $color = "Green"
                    $prefix = "> "
                }
                
                Write-Host "$prefix[$time] $event" -ForegroundColor $color
            } catch {
                # Preskoc neparsovatele radky
            }
        }
    } else {
        Write-Host "  Cekam na logy..." -ForegroundColor Gray
    }
    
    Write-Host ""
    Write-Host "--------------------------------------------" -ForegroundColor Gray
    
    # === CHECK IF DONE ===
    if ($RunId) {
        $manifestFile = "$transcribeDir\$RunId\manifest.json"
        if (Test-Path $manifestFile) {
            try {
                $manifest = Get-Content $manifestFile -Raw -ErrorAction SilentlyContinue | ConvertFrom-Json
                if ($manifest.status -eq "success") {
                    Write-Host ""
                    Write-Host "HOTOVO! Transkripce uspesne dokoncena!" -ForegroundColor Green
                    $isDone = $true
                    break
                } elseif ($manifest.status -eq "partial") {
                    Write-Host ""
                    Write-Host "HOTOVO s chybami! Nektre nahravky selhaly." -ForegroundColor Yellow
                    $isDone = $true
                    break
                } elseif ($manifest.status -eq "error") {
                    Write-Host ""
                    Write-Host "CHYBA! Transkripce selhala." -ForegroundColor Red
                    $isDone = $true
                    break
                }
            } catch {
                # Manifest jeste neni kompletni
            }
        }
    }
    
    Start-Sleep -Seconds 2
}

Write-Host ""
Write-Host "Monitoring ukoncen." -ForegroundColor Gray
Write-Host "Stisknete Enter pro zavreni..." -ForegroundColor Gray
Read-Host
