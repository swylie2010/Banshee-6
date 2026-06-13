import json
import tempfile
from pathlib import Path
from unittest.mock import patch


def _write_briefings(path, entries: list):
    with open(path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_load_latest_briefing_returns_last_entry(tmp_path):
    log = tmp_path / "daily_briefings.jsonl"
    _write_briefings(log, [
        {"date": "2026-06-11", "macro_tone": "bearish"},
        {"date": "2026-06-12", "macro_tone": "neutral"},
        {"date": "2026-06-13", "macro_tone": "bullish"},
    ])
    import predator_engine
    with patch.object(predator_engine, "BRIEFINGS_PATH", str(log)):
        predator_engine._briefing_cache = {}
        predator_engine._briefing_mtime = 0.0
        result = predator_engine.load_latest_briefing()
    assert result["date"] == "2026-06-13"
    assert result["macro_tone"] == "bullish"


def test_load_latest_briefing_returns_none_when_missing(tmp_path):
    import predator_engine
    missing = str(tmp_path / "does_not_exist.jsonl")
    with patch.object(predator_engine, "BRIEFINGS_PATH", missing):
        predator_engine._briefing_cache = {}
        predator_engine._briefing_mtime = 0.0
        result = predator_engine.load_latest_briefing()
    assert result is None


def test_load_latest_briefing_uses_mtime_cache(tmp_path):
    log = tmp_path / "daily_briefings.jsonl"
    _write_briefings(log, [{"date": "2026-06-13", "macro_tone": "bullish"}])
    import predator_engine
    with patch.object(predator_engine, "BRIEFINGS_PATH", str(log)):
        predator_engine._briefing_cache = {}
        predator_engine._briefing_mtime = 0.0
        result1 = predator_engine.load_latest_briefing()
        result2 = predator_engine.load_latest_briefing()
    assert result1 == result2
    assert result1["date"] == "2026-06-13"
