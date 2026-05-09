@echo off
echo ----------------------------------------------------
echo         STARTING BANSHEE PRO 4 COMMAND CENTER
echo ----------------------------------------------------
cd /d "%~dp0"

echo [1/2] Starting Banshee Core (port 8765)...
start "Banshee Core" /MIN python banshee_core.py

echo Waiting for Core to boot...
timeout /t 3 /nobreak >nul

echo [2/2] Starting Banshee Dashboard...
streamlit run app.py
pause
