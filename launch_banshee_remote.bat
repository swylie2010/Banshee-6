@echo off
rem launch_banshee_remote.bat - start Banshee reachable over your Tailscale network.
rem
rem This is the normal launcher with ONE switch flipped: it binds Banshee Core to
rem this PC's Tailscale address only. A phone signed into your tailnet can reach it;
rem regular wifi / LAN cannot (the port isn't opened there at all). If Tailscale
rem isn't running, Core safely falls back to local-only.

set "BANSHEE_HOST=tailscale"

echo.
echo   ============================================================
echo   Banshee REMOTE mode (Tailscale). This PC's Tailscale address:
echo.
tailscale ip -4
echo.
echo   On your phone, signed into Tailscale, open:
echo       http://[the-address-above]:8765/ui/
echo   ============================================================
echo.

call "%~dp0launch_banshee.bat"
