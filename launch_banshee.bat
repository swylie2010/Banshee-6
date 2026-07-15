@echo off
setlocal EnableDelayedExpansion

set "BANSHEE_DIR=%~dp0"
if "%BANSHEE_DIR:~-1%"=="\" set "BANSHEE_DIR=%BANSHEE_DIR:~0,-1%"

set "VENV_DIR=%BANSHEE_DIR%\.venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "VENV_PIP=%VENV_DIR%\Scripts\pip.exe"

echo -----------------------------------------------
echo       BANSHEE 6 - STARTUP CHECK
echo -----------------------------------------------

rem --- Step 1: Find Python 3.10+ ---
echo [1/5] Finding Python...
set "PYTHON_CMD="

where py >nul 2>&1
if not errorlevel 1 (
    py -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=py"
)

if not defined PYTHON_CMD (
    where python3 >nul 2>&1
    if not errorlevel 1 (
        python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1
        if not errorlevel 1 set "PYTHON_CMD=python3"
    )
)

if not defined PYTHON_CMD (
    echo.
    echo   ERROR: No Python 3.10+ found.
    echo   Install Python from https://python.org and retry.
    echo.
    pause
    exit /b 1
)
echo       Found: %PYTHON_CMD%

rem --- Step 2: Create venv if missing ---
echo [2/5] Checking virtual environment...
if exist "%VENV_PYTHON%" goto :venv_ok

echo       Creating Banshee virtual environment...
"%PYTHON_CMD%" -m venv "%VENV_DIR%"
if errorlevel 1 (
    echo.
    echo   ERROR: Failed to create virtual environment.
    echo.
    pause
    exit /b 1
)
echo       Created: %VENV_DIR%
goto :venv_done

:venv_ok
echo       OK: %VENV_DIR%

:venv_done

rem --- Step 3: Install / repair dependencies ---
echo [3/5] Checking dependencies...
"%VENV_PYTHON%" -c "import numpy, pandas, fastapi, uvicorn" >nul 2>&1
if not errorlevel 1 (
    echo       OK: all core dependencies present
    goto :launch
)

echo       Installing requirements (first run or repair)...
echo       This may take a few minutes on first launch.
if exist "%BANSHEE_DIR%\requirements-lock.txt" (
    echo       Using requirements-lock.txt
    "%VENV_PIP%" install -r "%BANSHEE_DIR%\requirements-lock.txt"
) else (
    "%VENV_PIP%" install -r "%BANSHEE_DIR%\requirements.txt"
)
if errorlevel 1 (
    echo.
    echo   ERROR: Dependency installation failed.
    echo   Check your internet connection and retry.
    echo.
    pause
    exit /b 1
)
echo       Dependencies installed.

:launch
rem --- Step 4: Build React UI ---
echo [4/5] Building React UI...

if not exist "%BANSHEE_DIR%\ui\node_modules" (
    echo       Installing UI dependencies - first run...
    cd /d "%BANSHEE_DIR%\ui"
    call npm install
    if errorlevel 1 (
        echo.
        echo   ERROR: npm install failed. Is Node.js installed?
        echo.
        pause
        exit /b 1
    )
    cd /d "%BANSHEE_DIR%"
)

cd /d "%BANSHEE_DIR%\ui"
call npm run build
if errorlevel 1 (
    echo.
    echo   ERROR: UI build failed. Check ui/ for JSX errors.
    echo.
    pause
    exit /b 1
)
cd /d "%BANSHEE_DIR%"
echo       OK: ui/dist/bundle.js

rem --- Step 5: Launch ---
echo [5/5] Starting Banshee Core (port 8765)...
start "Banshee Core" /MIN cmd /c "cd /d "%BANSHEE_DIR%" && "%VENV_PYTHON%" banshee_core.py"

echo       Waiting for Core to boot...
timeout /t 6 /nobreak >nul

echo       Opening Banshee 6 UI...
if not defined BANSHEE_HOST start "" "http://localhost:8765/ui/"

echo.
echo Banshee 6 is running at http://localhost:8765/ui/
echo.
pause
