# stop_banshee.ps1 — Stop all Banshee 6 Core processes on Windows.
#
# Why this exists: stop_banshee.sh uses `pkill`, which does NOT see native
# Windows python.exe processes from Git Bash, so a "restart" silently leaves the
# old Core holding :8765 — serving stale backend code behind a freshly-refreshed
# UI. This kills the real process by matching its command line.
#
# Usage (from PowerShell):   .\stop_banshee.ps1
# Usage (from Git Bash):     powershell.exe -NoProfile -File stop_banshee.ps1

$procs = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*banshee_core.py*' }

if (-not $procs) {
    Write-Host "Banshee Core was not running."
} else {
    foreach ($p in $procs) {
        Write-Host ("Stopping Core PID {0}" -f $p.ProcessId)
        Stop-Process -Id $p.ProcessId -Force
    }
    Start-Sleep -Seconds 1
    Write-Host "Core stopped."
}

# Confirm the port is actually free.
$still = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Warning "Port 8765 still has a listener (PID $($still.OwningProcess)). Investigate manually."
} else {
    Write-Host "Port 8765 is free."
}
