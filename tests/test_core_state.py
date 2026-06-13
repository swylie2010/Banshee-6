from pathlib import Path
from unittest.mock import patch


def test_log_error_writes_to_log(tmp_path):
    from core_state import _log_error
    log_file = tmp_path / ".banshee_errors.log"
    with patch("core_state._ERROR_LOG", log_file):
        try:
            raise ValueError("test explosion")
        except ValueError as e:
            _log_error("test-context", e)
    content = log_file.read_text(encoding="utf-8")
    assert "test-context" in content
    assert "ValueError" in content
    assert "test explosion" in content


def test_log_error_never_raises():
    from core_state import _log_error
    with patch("core_state._ERROR_LOG", Path("/nonexistent/path/that/does/not/exist.log")):
        _log_error("test", Exception("boom"))
