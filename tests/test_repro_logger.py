"""Tests for the reproducibility logger module."""

import json
import hashlib
from pathlib import Path

import pytest


def test_log_operation_writes_valid_json_line(tmp_repro_dir):
    """Test 1: log_operation writes a valid JSON line with required keys."""
    from repro.repro_logger import log_operation, LEDGER_PATH

    entry = log_operation(
        skill="sci-data-analysis",
        operation="statistical_test",
        params={"test": "t-test", "alpha": 0.05},
    )

    assert "timestamp" in entry
    assert entry["skill"] == "sci-data-analysis"
    assert entry["operation"] == "statistical_test"
    assert entry["params"] == {"test": "t-test", "alpha": 0.05}

    # Verify it was written as valid JSON
    ledger = LEDGER_PATH
    lines = ledger.read_text().strip().split("\n")
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["skill"] == "sci-data-analysis"


def test_log_operation_includes_file_hashes(tmp_repro_dir, sample_data_file):
    """Test 2: log_operation includes SHA-256 file hashes for data_files."""
    from repro.repro_logger import log_operation

    entry = log_operation(
        skill="sci-data-analysis",
        operation="load_csv",
        params={"delimiter": ","},
        data_files=[str(sample_data_file)],
    )

    assert len(entry["data_files"]) == 1
    file_entry = entry["data_files"][0]
    assert file_entry["path"] == str(sample_data_file)
    assert len(file_entry["sha256"]) == 64  # SHA-256 hex digest length


def test_log_operation_handles_empty_data_files(tmp_repro_dir):
    """Test 3: log_operation handles empty data_files list."""
    from repro.repro_logger import log_operation

    entry = log_operation(
        skill="sci-data-analysis",
        operation="compute_stats",
        params={"method": "mean"},
        data_files=[],
    )

    assert entry["data_files"] == []


def test_log_operation_appends_entries(tmp_repro_dir):
    """Test 4: log_operation appends (does not overwrite) existing entries."""
    from repro.repro_logger import log_operation, LEDGER_PATH

    log_operation(skill="skill-1", operation="op-1", params={})
    log_operation(skill="skill-2", operation="op-2", params={})

    lines = LEDGER_PATH.read_text().strip().split("\n")
    assert len(lines) == 2
    assert json.loads(lines[0])["skill"] == "skill-1"
    assert json.loads(lines[1])["skill"] == "skill-2"


def test_file_hash_returns_correct_sha256(sample_data_file):
    """Test 5: _file_hash returns correct SHA-256 hex digest."""
    from repro.repro_logger import _file_hash

    result = _file_hash(str(sample_data_file))
    expected = hashlib.sha256(b"a,b\n1,2\n").hexdigest()
    assert result == expected


def test_generate_summary_produces_markdown(tmp_repro_dir):
    """Test 6: generate_summary reads JSONL and produces markdown summary."""
    from repro.repro_logger import log_operation, generate_summary, LEDGER_PATH

    log_operation(skill="sci-data-analysis", operation="t-test", params={"alpha": 0.05})
    log_operation(skill="sci-figure-gen", operation="scatter_plot", params={"x": "col1"})

    summary = generate_summary()

    assert "# Reproducibility Summary" in summary
    assert "sci-data-analysis" in summary
    assert "t-test" in summary
    assert "sci-figure-gen" in summary


def test_log_operation_includes_environment(tmp_repro_dir):
    """Test 7: log_operation includes environment dict with package versions."""
    from repro.repro_logger import log_operation

    entry = log_operation(
        skill="sci-data-analysis",
        operation="test",
        params={},
    )

    assert "environment" in entry
    env = entry["environment"]
    assert "python" in env
    assert "pandas" in env
    assert "scipy" in env
