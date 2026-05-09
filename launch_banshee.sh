#!/usr/bin/env bash
# launch_banshee.sh — Start Banshee Pro 4 on Linux
# Usage: bash launch_banshee.sh [--no-ui]
#   --no-ui  Start Core only (no Streamlit); useful for OpenClaw / MCP-only operation

set -e
BANSHEE_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$BANSHEE_DIR"

echo "----------------------------------------------------"
echo "        STARTING BANSHEE PRO 4 COMMAND CENTER"
echo "----------------------------------------------------"

echo "[1/2] Starting Banshee Core (port 8765)..."
python3 banshee_core.py &
CORE_PID=$!
echo "      Core PID: $CORE_PID"

echo "      Waiting for Core to boot..."
sleep 3

# Check Core is up
if ! curl -s http://127.0.0.1:8765/health >/dev/null 2>&1; then
    echo "ERROR: Core did not start. Check for missing dependencies or port conflict."
    kill "$CORE_PID" 2>/dev/null
    exit 1
fi
echo "      Core online."

if [[ "$1" == "--no-ui" ]]; then
    echo "[2/2] Skipping Streamlit (--no-ui mode)."
    echo ""
    echo "Banshee Core running at http://127.0.0.1:8765"
    echo "Core PID: $CORE_PID  — kill with: kill $CORE_PID"
    wait "$CORE_PID"
else
    echo "[2/2] Starting Banshee Dashboard (Streamlit)..."
    streamlit run app.py --server.port 8501 &
    UI_PID=$!
    echo "      UI PID: $UI_PID"
    echo ""
    echo "Banshee Pro 4 running."
    echo "  Core:  http://127.0.0.1:8765"
    echo "  UI:    http://localhost:8501"
    echo ""
    echo "PIDs: Core=$CORE_PID  UI=$UI_PID"
    echo "Stop: kill $CORE_PID $UI_PID"
    wait
fi
