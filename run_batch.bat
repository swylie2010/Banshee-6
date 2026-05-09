@echo off
title Banshee Pro — Batch Backtest Runner
cd /d "%~dp0"

echo.
echo  ██████╗  █████╗ ███╗   ██╗███████╗██╗  ██╗███████╗███████╗
echo  ██╔══██╗██╔══██╗████╗  ██║██╔════╝██║  ██║██╔════╝██╔════╝
echo  ██████╔╝███████║██╔██╗ ██║███████╗███████║█████╗  █████╗
echo  ██╔══██╗██╔══██║██║╚██╗██║╚════██║██╔══██║██╔══╝  ██╔══╝
echo  ██████╔╝██║  ██║██║ ╚████║███████║██║  ██║███████╗███████╗
echo  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝
echo.
echo  MTF Batch Backtest Runner
echo  Results saved to strategies.json as runs complete.
echo  A popup will appear when finished -- safe to walk away.
echo.

python run_batch.py %*

echo.
echo  ════════════════════════════════════════
echo  Done. Press any key to close this window.
echo  ════════════════════════════════════════
pause >nul
