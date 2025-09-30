# Real-time log monitor
Write-Host "=== LOG MONITOR ===" -ForegroundColor Green
Write-Host "Sledovani logu v real-time" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host ""

$logFile = "logs\transcriber.log"

if (!(Test-Path $logFile)) {
    Write-Host "Log soubor neexistuje: $logFile" -ForegroundColor Red
    exit 1
}

# Zobraz poslednich 10 radku
Write-Host "--- Historie (poslednich 10 radku) ---" -ForegroundColor Magenta
Get-Content $logFile -Tail 10 | ForEach-Object {
    try {
        $log = $_ | ConvertFrom-Json
        $time = ([DateTime]$log.timestamp).ToString("HH:mm:ss")
        $level = $log.level.ToUpper()
        $event = $log.event
        
        $color = "White"
        if ($level -eq "WARNING") { $color = "Yellow" }
        if ($level -eq "ERROR") { $color = "Red" }
        
        Write-Host "[$time] $level - $event" -ForegroundColor $color
    } catch {
        Write-Host $_ -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "--- Live Updates ---" -ForegroundColor Green

# Sleduj nove radky
Get-Content $logFile -Wait -Tail 0 | ForEach-Object {
    try {
        $log = $_ | ConvertFrom-Json
        $time = ([DateTime]$log.timestamp).ToString("HH:mm:ss")
        $level = $log.level.ToUpper()
        $event = $log.event
        
        $color = "Cyan"
        if ($level -eq "WARNING") { $color = "Yellow" }
        if ($level -eq "ERROR") { $color = "Red" }
        
        Write-Host "[$time] $level - $event" -ForegroundColor $color
        
        # Beep pri chybe
        if ($level -eq "ERROR") {
            [Console]::Beep(800, 200)
        }
    } catch {
        Write-Host $_ -ForegroundColor Gray
    }
}