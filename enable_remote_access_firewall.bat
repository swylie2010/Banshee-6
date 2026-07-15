@echo off
rem enable_remote_access_firewall.bat
rem RIGHT-CLICK this file and choose "Run as administrator". Run it once.
rem
rem It adds ONE Windows Firewall rule that lets inbound connections reach
rem Banshee's port (8765) ONLY from Tailscale-range addresses (100.64.0.0/10).
rem Your phone can then reach Banshee over Tailscale, but the port stays closed
rem to regular wifi, the LAN, and the internet. The rule persists across reboots.

net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo   This needs administrator rights.
    echo   Right-click this file and choose "Run as administrator", then run it again.
    echo.
    pause
    exit /b 1
)

echo   Adding firewall rule for Banshee port 8765 ^(Tailscale only^)...
netsh advfirewall firewall delete rule name="Banshee Tailscale 8765" >nul 2>&1
netsh advfirewall firewall add rule name="Banshee Tailscale 8765" dir=in action=allow protocol=TCP localport=8765 remoteip=100.64.0.0/10

echo.
echo   Done. Port 8765 now accepts inbound connections from your Tailscale
echo   network only. You can close this window.
echo.
pause
