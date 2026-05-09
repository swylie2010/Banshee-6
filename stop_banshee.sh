#!/usr/bin/env bash
# stop_banshee.sh — Stop all Banshee Pro 4 processes on Linux
pkill -f banshee_core.py    2>/dev/null && echo "Core stopped."    || echo "Core was not running."
pkill -f "streamlit run"    2>/dev/null && echo "UI stopped."      || echo "UI was not running."
