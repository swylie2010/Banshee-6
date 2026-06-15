@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   BANSHEE PRO 2.0 -- New Machine Setup
echo ============================================================
echo.

:: Detect this script's own directory (where mcp_server.py lives)
set "BANSHEE_DIR=%~dp0"
:: Remove trailing backslash
if "%BANSHEE_DIR:~-1%"=="\" set "BANSHEE_DIR=%BANSHEE_DIR:~0,-1%"

set "MCP_SERVER=%BANSHEE_DIR%\mcp_server.py"
set "MCP_FILE=%USERPROFILE%\.claude\.mcp.json"
set "MCP_FILE2=%USERPROFILE%\.mcp.json"

echo [INFO] Banshee directory : %BANSHEE_DIR%
echo [INFO] MCP server path   : %MCP_SERVER%
echo [INFO] MCP config target : %MCP_FILE%
echo.

:: ── Step 1: Install Python dependencies ──────────────────────────
if exist "%BANSHEE_DIR%\requirements-lock.txt" (
    echo [1/3] Installing from requirements-lock.txt ^(pinned^)...
    pip install -r "%BANSHEE_DIR%\requirements-lock.txt"
) else (
    echo [1/3] Installing Python dependencies from requirements.txt...
    pip install -r "%BANSHEE_DIR%\requirements.txt"
)
if %ERRORLEVEL% NEQ 0 (
    echo [WARN] pip install returned errors -- check output above.
) else (
    echo [OK] Dependencies installed.
)
echo.

:: ── Step 2: Ensure .claude directory exists ──────────────────────
if not exist "%USERPROFILE%\.claude" mkdir "%USERPROFILE%\.claude"

:: ── Step 3: Write .mcp.json using PowerShell for clean JSON ──────
echo [2/3] Writing MCP config to %MCP_FILE% ...

:: Convert backslashes to forward slashes for Python/JSON compat
set "MCP_PATH_FWD=%MCP_SERVER:\=/%"

powershell -NoProfile -Command ^
  "$cfg = @{ mcpServers = @{ 'banshee-pro' = @{ command = 'python'; args = @('%MCP_PATH_FWD%') } } }; " ^
  "$cfg | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 '%MCP_FILE%'; " ^
  "$cfg | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 '%MCP_FILE2%'"

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to write MCP config. Check PowerShell permissions.
    goto :end
)
echo [OK] MCP config written to:
echo      %MCP_FILE%
echo      %MCP_FILE2%
echo.

:: ── Step 4: Create keys file template if missing ──────────────────
echo [3/3] Checking keys file...
set "KEYS_FILE=%USERPROFILE%\.banshee_keys.json"
if not exist "%KEYS_FILE%" (
    echo {"FRED_API": {"key": ""}, "AI_API": {"type": "Gemini", "key": "", "model": "gemini-2.5-flash"}} > "%KEYS_FILE%"
    echo [OK] Created blank keys file at %KEYS_FILE%
    echo      Open Banshee Pro Streamlit UI and enter your API keys in Settings.
) else (
    echo [OK] Keys file already exists at %KEYS_FILE%
)
echo.

:end
echo ============================================================
echo   Setup complete.
echo   Next steps:
echo     1. Run: streamlit run "%BANSHEE_DIR%\app.py"
echo     2. Open Settings tab -- enter your FRED + AI keys
echo     3. Restart Claude Code to activate the MCP server
echo ============================================================
echo.
pause
endlocal
