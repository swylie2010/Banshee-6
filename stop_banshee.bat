@echo off
echo Stopping Banshee Core (port 8765)...
powershell -Command "$conn = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue; if ($conn) { Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue; Write-Host 'Core stopped.' } else { Write-Host 'Core was not running.' }"
echo.
pause
