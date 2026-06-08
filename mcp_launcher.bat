@echo off
:: mcp_launcher.bat — Self-healing Banshee MCP server launcher (Windows)
:: All diagnostic output goes to stderr so it does not corrupt the MCP stdio pipe.
:: Used by ~/.claude/.mcp.json as the banshee-pro MCP command.

setlocal EnableDelayedExpansion

set "BANSHEE_DIR=%~dp0"
if "%BANSHEE_DIR:~-1%"=="\" set "BANSHEE_DIR=%BANSHEE_DIR:~0,-1%"

set "VENV_PYTHON=%BANSHEE_DIR%\.venv\Scripts\python.exe"
set "VENV_PIP=%BANSHEE_DIR%\.venv\Scripts\pip.exe"

:: Create venv if missing
if not exist "%VENV_PYTHON%" (
    echo [banshee-mcp] .venv not found - creating... >&2
    set "PYTHON_CMD="
    where py >nul 2>&1 && (
        py -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PYTHON_CMD=py"
    )
    if not defined PYTHON_CMD (
        where python3 >nul 2>&1 && set "PYTHON_CMD=python3"
    )
    if not defined PYTHON_CMD (
        echo [banshee-mcp] ERROR: No Python 3.10+ found. Run launch_banshee.bat to diagnose. >&2
        exit /b 1
    )
    "%PYTHON_CMD%" -m venv "%BANSHEE_DIR%\.venv" >nul 2>&1
    if not exist "%VENV_PYTHON%" (
        echo [banshee-mcp] ERROR: venv creation failed. Run launch_banshee.bat to diagnose. >&2
        exit /b 1
    )
    echo [banshee-mcp] Installing dependencies... >&2
    "%VENV_PIP%" install -r "%BANSHEE_DIR%\requirements.txt" >nul 2>&1
    echo [banshee-mcp] Ready. >&2
)

:: Repair missing dependencies silently
"%VENV_PYTHON%" -c "import numpy, fastapi, mcp" >nul 2>&1
if %errorlevel% neq 0 (
    echo [banshee-mcp] Repairing dependencies... >&2
    "%VENV_PIP%" install -r "%BANSHEE_DIR%\requirements.txt" >nul 2>&1
)

"%VENV_PYTHON%" "%BANSHEE_DIR%\mcp_server.py"
