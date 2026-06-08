#!/usr/bin/env bash
# mcp_launcher.sh — Self-healing Banshee MCP server launcher (Linux / macOS)
# All diagnostic output goes to stderr so it does not corrupt the MCP stdio pipe.
# Used by ~/.claude/.mcp.json as the banshee-pro MCP command on non-Windows machines.

BANSHEE_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_PYTHON="$BANSHEE_DIR/.venv/bin/python"
VENV_PIP="$BANSHEE_DIR/.venv/bin/pip"

# Create venv if missing
if [ ! -f "$VENV_PYTHON" ]; then
    echo "[banshee-mcp] .venv not found - creating..." >&2
    PYTHON_CMD=""
    for candidate in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>/dev/null; then
                PYTHON_CMD="$candidate"
                break
            fi
        fi
    done
    if [ -z "$PYTHON_CMD" ]; then
        echo "[banshee-mcp] ERROR: No Python 3.10+ found. Run launch_banshee.sh to diagnose." >&2
        exit 1
    fi
    "$PYTHON_CMD" -m venv "$BANSHEE_DIR/.venv" >/dev/null 2>&1
    if [ ! -f "$VENV_PYTHON" ]; then
        echo "[banshee-mcp] ERROR: venv creation failed. Run launch_banshee.sh to diagnose." >&2
        exit 1
    fi
    echo "[banshee-mcp] Installing dependencies..." >&2
    "$VENV_PIP" install -r "$BANSHEE_DIR/requirements.txt" >/dev/null 2>&1
    echo "[banshee-mcp] Ready." >&2
fi

# Repair missing dependencies silently
if ! "$VENV_PYTHON" -c "import numpy, fastapi, mcp" >/dev/null 2>&1; then
    echo "[banshee-mcp] Repairing dependencies..." >&2
    "$VENV_PIP" install -r "$BANSHEE_DIR/requirements.txt" >/dev/null 2>&1
fi

exec "$VENV_PYTHON" "$BANSHEE_DIR/mcp_server.py"
