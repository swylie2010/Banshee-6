#!/usr/bin/env bash
# launch_banshee.sh — Self-healing Banshee 5 launcher (Linux / macOS)
# Finds Python, creates .venv, installs deps, launches Core.
# Re-run any time to repair a broken environment.
# Usage: bash launch_banshee.sh [--no-ui]

set -euo pipefail

BANSHEE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$BANSHEE_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"
REQUIREMENTS="$BANSHEE_DIR/requirements.txt"

echo "-----------------------------------------------"
echo "      BANSHEE 5 — STARTUP CHECK"
echo "-----------------------------------------------"

# ── Step 1: Find Python 3.10+ ─────────────────────
echo "[1/4] Finding Python..."
PYTHON_CMD=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
            version=$("$candidate" -c "import sys; v=sys.version_info; print(f'{v.major}.{v.minor}.{v.micro}')")
            PYTHON_CMD="$candidate"
            echo "      Found: $candidate ($version)"
            break
        fi
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo ""
    echo "  ERROR: No Python 3.10+ found."
    echo ""
    echo "  Possible causes:"
    echo "    - Python is not installed."
    echo "        Ubuntu/Debian: sudo apt install python3.12"
    echo "        macOS:         brew install python@3.12"
    echo "    - A tool (conda, another app's venv, pyenv) is shadowing Python."
    echo "        Check: which python3 && python3 --version"
    echo "    - Python is installed but below 3.10."
    echo ""
    exit 1
fi

# ── Step 2: Create venv if missing ────────────────
echo "[2/4] Checking virtual environment..."
if [ ! -f "$VENV_PYTHON" ]; then
    echo "      Creating Banshee virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    echo "      Created: $VENV_DIR"
else
    echo "      OK: $VENV_DIR"
fi

# ── Step 3: Install / repair dependencies ─────────
echo "[3/4] Checking dependencies..."
if ! "$VENV_PYTHON" -c "import numpy, pandas, fastapi, uvicorn" >/dev/null 2>&1; then
    echo "      Installing requirements (first run or repair)..."
    echo "      This may take a few minutes on first launch."
    LOCK_FILE="$BANSHEE_DIR/requirements-lock.txt"
    if [ -f "$LOCK_FILE" ]; then
        echo "      Using requirements-lock.txt (pinned versions)"
        "$VENV_PIP" install -r "$LOCK_FILE"
    else
        "$VENV_PIP" install -r "$REQUIREMENTS"
    fi
    echo "      Dependencies installed."
else
    echo "      OK: all core dependencies present"
fi

# ── Step 4: Launch ────────────────────────────────
echo "[4/4] Starting Banshee Core (port 8765)..."

if [[ "${1:-}" == "--no-ui" ]]; then
    exec "$VENV_PYTHON" "$BANSHEE_DIR/banshee_core.py"
fi

"$VENV_PYTHON" "$BANSHEE_DIR/banshee_core.py" &
CORE_PID=$!
echo "      Waiting for Core..."
sleep 3

if ! curl -s http://127.0.0.1:8765/health >/dev/null 2>&1; then
    echo ""
    echo "  ERROR: Core did not respond at http://127.0.0.1:8765/health"
    echo ""
    echo "  Possible causes:"
    echo "    - Port 8765 already in use:  lsof -i :8765"
    echo "    - A stale Banshee process:   bash stop_banshee.sh"
    echo "    - A Python traceback above this line (scroll up)"
    echo ""
    kill "$CORE_PID" 2>/dev/null || true
    exit 1
fi

echo "      Core online."
echo ""
echo "Banshee 5 running at http://localhost:8765/ui/"
echo "Core PID: $CORE_PID  — stop with: bash stop_banshee.sh"
wait "$CORE_PID"
