"""Tests for tool-gdrive skill — isolated from real Drive mount.

Uses a tmp_path as a fake Drive root via monkeypatching find_drive_root,
so tests run on CI without needing Google Drive desktop installed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPT = ROOT / ".claude" / "skills" / "tool-gdrive" / "scripts" / "gdrive_ops.py"


@pytest.fixture
def gdrive_module():
    """Import gdrive_ops.py as a module."""
    spec = importlib.util.spec_from_file_location("gdrive_ops", SKILL_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_drive(tmp_path, monkeypatch, gdrive_module):
    """Point find_drive_root() at a tmp_path so tests don't touch real Drive."""
    drive_root = tmp_path / "My Drive"
    drive_root.mkdir()
    monkeypatch.setattr(gdrive_module, "find_drive_root", lambda: drive_root)
    return drive_root


class TestGdriveCategorize:
    """Extension → category mapping."""

    @pytest.mark.parametrize("filename,expected", [
        ("data.csv", "data"),
        ("results.xlsx", "data"),
        ("raw.json", "data"),
        ("table.tsv", "data"),
        ("fig.png", "figures"),
        ("fig.svg", "figures"),
        ("scan.tiff", "figures"),
        ("draft.md", "manuscripts"),
        ("paper.pdf", "manuscripts"),
        ("manuscript.tex", "manuscripts"),
        ("deck.pptx", "presentations"),
        ("refs.bib", "papers"),
        ("random.txt", "notes"),
        ("unknown.xyz", "notes"),
    ])
    def test_category_mapping(self, gdrive_module, filename, expected):
        assert gdrive_module.categorize(Path(filename)) == expected


class TestGdriveStatus:
    def test_status_no_drive(self, monkeypatch, gdrive_module):
        monkeypatch.setattr(gdrive_module, "find_drive_root", lambda: None)
        s = gdrive_module.status()
        assert s["installed"] is False
        assert "error" in s

    def test_status_with_drive(self, fake_drive, gdrive_module):
        s = gdrive_module.status()
        assert s["installed"] is True
        assert s["drive_root"] == str(fake_drive)
        # Staging root not yet created
        assert s["staging_exists"] is False


class TestGdriveStage:
    def test_stage_csv_auto_category(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "experiment.csv"
        src.write_text("id,value\n1,42\n2,43\n")

        dest = gdrive_module.stage(src)

        assert dest.exists()
        assert dest.parent.name == "data"
        assert dest.name == "experiment.csv"
        # Staging root created
        assert (fake_drive / "organon").is_dir()
        # Content preserved
        assert dest.read_text() == src.read_text()

    def test_stage_png_to_figures(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "plot.png"
        src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

        dest = gdrive_module.stage(src)

        assert dest.parent.name == "figures"
        assert dest.read_bytes() == src.read_bytes()

    def test_stage_md_to_manuscripts(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "draft.md"
        src.write_text("# Intro\n\nSome prose.\n")

        dest = gdrive_module.stage(src)

        assert dest.parent.name == "manuscripts"

    def test_stage_bib_to_papers(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "refs.bib"
        src.write_text("@article{foo2024, title={Bar}}")

        dest = gdrive_module.stage(src)

        assert dest.parent.name == "papers"

    def test_stage_unknown_to_notes(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "random.xyz"
        src.write_text("hi")

        dest = gdrive_module.stage(src)

        assert dest.parent.name == "notes"

    def test_stage_explicit_category_overrides_extension(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "experiment.csv"
        src.write_text("data")

        dest = gdrive_module.stage(src, category="notes")

        assert dest.parent.name == "notes"  # not 'data'

    def test_stage_rename(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "temp.csv"
        src.write_text("data")

        dest = gdrive_module.stage(src, rename="final_dataset.csv")

        assert dest.name == "final_dataset.csv"
        assert dest.parent.name == "data"

    def test_stage_collision_appends_timestamp(self, fake_drive, gdrive_module, tmp_path):
        src = tmp_path / "dup.csv"
        src.write_text("v1")

        d1 = gdrive_module.stage(src)
        d2 = gdrive_module.stage(src)
        d3 = gdrive_module.stage(src)

        paths = {d1, d2, d3}
        assert len(paths) == 3, "each stage should get a unique destination"
        assert all(p.exists() for p in paths)

    def test_stage_missing_source_raises(self, fake_drive, gdrive_module, tmp_path):
        missing = tmp_path / "ghost.csv"
        with pytest.raises(SystemExit, match="source not found"):
            gdrive_module.stage(missing)

    def test_stage_directory_raises(self, fake_drive, gdrive_module, tmp_path):
        d = tmp_path / "a_dir"
        d.mkdir()
        with pytest.raises(SystemExit, match="directories not yet supported"):
            gdrive_module.stage(d)

    def test_stage_no_drive_raises(self, monkeypatch, gdrive_module, tmp_path):
        monkeypatch.setattr(gdrive_module, "find_drive_root", lambda: None)
        src = tmp_path / "f.csv"
        src.write_text("x")
        with pytest.raises(SystemExit, match="Google Drive desktop not detected"):
            gdrive_module.stage(src)


class TestGdriveList:
    def test_list_empty(self, fake_drive, gdrive_module):
        assert gdrive_module.list_staged() == []

    def test_list_after_staging(self, fake_drive, gdrive_module, tmp_path):
        for name in ["a.csv", "b.png", "c.md"]:
            src = tmp_path / name
            src.write_text("x")
            gdrive_module.stage(src)

        entries = gdrive_module.list_staged()
        categories = {e["category"] for e in entries}
        assert categories == {"data", "figures", "manuscripts"}
        names = {e["name"] for e in entries}
        assert names == {"a.csv", "b.png", "c.md"}

    def test_list_filtered_by_category(self, fake_drive, gdrive_module, tmp_path):
        for name in ["x1.csv", "x2.csv", "fig.png"]:
            src = tmp_path / name
            src.write_text("x")
            gdrive_module.stage(src)

        data_only = gdrive_module.list_staged(category="data")
        assert len(data_only) == 2
        assert all(e["category"] == "data" for e in data_only)


class TestGdriveShareLink:
    def test_share_link_is_file_url(self, gdrive_module, tmp_path):
        p = tmp_path / "x.csv"
        p.write_text("x")
        link = gdrive_module.share_link(p)
        assert link.startswith("file://")
        assert str(p.resolve()) in link


class TestGdriveCli:
    """End-to-end CLI tests via subprocess."""

    def test_cli_status_json(self, tmp_path, monkeypatch):
        # Can't monkeypatch a subprocess easily; run real status against real system.
        # If no Drive installed, the test will still pass — we just verify exit code.
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "status", "--json"],
            capture_output=True, text=True
        )
        assert result.returncode in (0, 1)
        payload = json.loads(result.stdout)
        assert "installed" in payload

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "--help"],
            capture_output=True, text=True
        )
        assert result.returncode == 0
        assert "stage" in result.stdout
        assert "list" in result.stdout
        assert "status" in result.stdout
