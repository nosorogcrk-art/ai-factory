import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from log_analyzer import parse_log_line, analyze_log_file, generate_report

def test_parse_log_line():
    line = "2026-04-07 10:00:00,123 - INFO - Test message"
    parsed = parse_log_line(line)
    assert parsed is not None
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "Test message"
    assert parsed["timestamp"] == datetime(2026, 4, 7, 10, 0, 0)

def test_analyze_log_file(tmp_path):
    log_file = tmp_path / "test.log"
    log_file.write_text(
        "2026-04-07 10:00:00,123 - ERROR - Something went wrong\n"
        "2026-04-07 10:00:01,456 - INFO - duration_ms: 150\n"
        "2026-04-07 09:00:00,789 - ERROR - Old error\n"
    )
    since = datetime(2026, 4, 7, 9, 30, 0)
    result = analyze_log_file(log_file, since)
    assert result["error_count"] == 1
    assert result["info_count"] == 1
    assert len(result["duration_ops"]) == 1
    assert result["duration_ops"][0][1] == 150

def test_generate_report():
    analysis = {
        "test.log": {
            "error_count": 2,
            "warning_count": 0,
            "errors": ["err1", "err2"],
            "warnings": [],
            "info_count": 5,
            "duration_ops": [("op1", 100), ("op2", 200)]
        }
    }
    report = generate_report(analysis, 24)
    assert report["total_errors"] == 2
    assert report["average_duration_ms"] == 150
    assert len(report["top_errors"]) >= 1