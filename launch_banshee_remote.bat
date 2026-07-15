@echo off
rem launch_banshee_remote.bat - start Banshee reachable from your phone over
rem Tailscale, while it also keeps working on this PC at localhost.
rem
rem Binds Core to all interfaces (0.0.0.0), so BOTH http://localhost:8765 and
rem this PC's Tailscale address answer. The companion firewall rule
rem (enable_remote_access_firewall.bat - run ONCE as administrator) keeps inbound
rem connections limited to the Tailscale network, so the port is NOT exposed to
rem regular wifi / LAN / the internet.

set "BANSHEE_HOST=0.0.0.0"

echo.
echo   ============================================================
echo   Banshee REMOTE mode. This PC's Tailscale address:
echo.
tailscale ip -4
echo.
echo   On your phone, signed into Tailscale, open:
echo       http://[the-address-above]:8765/ui/
echo   On this PC you can still use http://localhost:8765/ui/
echo   ============================================================
echo.

call "%~dp0launch_banshee.bat"
