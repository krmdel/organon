"""Offline tests for E3 — stage_audit_bundle in gdrive_ops.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Resolve gdrive_ops without installing as a package
GDRIVE_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(GDRIVE_SCRIPTS))
import gdrive_ops  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """A temp directory that acts as both the markdown workspace and fake Drive root."""
    return tmp_path


@pytest.fixture()
def fake_drive(tmp_path: Path) -> Path:
    """Fake Drive My Drive root so tests never touch real Drive."""
    drive = tmp_path / "FakeDrive" / "My Drive"
    drive.mkdir(parents=True)
    return drive


@pytest.fixture()
def md_file(workspace: Path) -> Path:
    p = workspace / "draft.md"
    p.write_text("# Draft\n\nSome content.\n")
    return p


# ---------------------------------------------------------------------------
# _find_audit_artifacts
# ---------------------------------------------------------------------------

class TestFindAuditArtifacts:
    def test_empty_dir(self, md_file: Path) -> None:
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert result == []

    def test_bib_only(self, md_file: Path, workspace: Path) -> None:
        bib = workspace / "references.bib"
        bib.write_text("@article{a, title={T}}\n")
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert bib in result

    def test_citations_json_only(self, md_file: Path, workspace: Path) -> None:
        cj = workspace / "draft.citations.json"
        cj.write_text("{}")
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert cj in result

    def test_audit_md_only(self, md_file: Path, workspace: Path) -> None:
        audit = workspace / "draft-audit.md"
        audit.write_text("# Audit\n")
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert audit in result

    def test_all_types(self, md_file: Path, workspace: Path) -> None:
        bib = workspace / "references.bib"
        bib.write_text("@article{x}")
        cj = workspace / "draft.citations.json"
        cj.write_text("{}")
        audit = workspace / "draft-audit.md"
        audit.write_text("# Audit\n")
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert set(result) == {bib, cj, audit}

    def test_does_not_include_md_itself(self, md_file: Path) -> None:
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert md_file not in result

    def test_ignores_unrelated_files(self, md_file: Path, workspace: Path) -> None:
        (workspace / "notes.txt").write_text("x")
        (workspace / "data.csv").write_text("a,b\n1,2\n")
        result = gdrive_ops._find_audit_artifacts(md_file)
        assert result == []


# ---------------------------------------------------------------------------
# stage_audit_bundle
# ---------------------------------------------------------------------------

class TestStageAuditBundle:
    def _patch_drive(self, fake_drive: Path):
        return patch.object(gdrive_ops, "find_drive_root", return_value=fake_drive)

    def test_md_only_no_artifacts(self, md_file: Path, workspace: Path, fake_drive: Path) -> None:
        with self._patch_drive(fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)
        assert result["skipped"] == []
        assert len(result["staged"]) == 1
        assert Path(result["staged"][0]["src"]) == md_file

    def test_bundle_dir_name(self, md_file: Path, fake_drive: Path) -> None:
        with self._patch_drive(fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)
        bundle = Path(result["bundle_dir"])
        assert bundle.name == "draft_audit"
        assert bundle.parent.name == "manuscripts"

    def test_artifacts_staged(self, md_file: Path, workspace: Path, fake_drive: Path) -> None:
        bib = workspace / "references.bib"
        bib.write_text("@article{x}")
        cj = workspace / "draft.citations.json"
        cj.write_text("{}")
        audit = workspace / "draft-audit.md"
        audit.write_text("# Audit\n")

        with self._patch_drive(fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)

        assert result["skipped"] == []
        staged_names = {Path(s["src"]).name for s in result["staged"]}
        assert staged_names == {"draft.md", "references.bib", "draft.citations.json", "draft-audit.md"}

    def test_staged_files_exist_on_disk(self, md_file: Path, workspace: Path, fake_drive: Path) -> None:
        bib = workspace / "refs.bib"
        bib.write_text("@article{y}")
        with self._patch_drive(fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)
        for item in result["staged"]:
            assert Path(item["dest"]).is_file()

    def test_size_bytes_correct(self, md_file: Path, fake_drive: Path) -> None:
        with self._patch_drive(fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)
        item = result["staged"][0]
        assert item["size_bytes"] == md_file.stat().st_size

    def test_collision_adds_timestamp_suffix(self, md_file: Path, workspace: Path, fake_drive: Path) -> None:
        with self._patch_drive(fake_drive):
            r1 = gdrive_ops.stage_audit_bundle(md_file)
            r2 = gdrive_ops.stage_audit_bundle(md_file)
        dest1 = Path(r1["staged"][0]["dest"])
        dest2 = Path(r2["staged"][0]["dest"])
        assert dest1 != dest2

    def test_wrong_extension_raises(self, tmp_path: Path, fake_drive: Path) -> None:
        txt = tmp_path / "notes.txt"
        txt.write_text("x")
        with self._patch_drive(fake_drive):
            with pytest.raises(SystemExit):
                gdrive_ops.stage_audit_bundle(txt)

    def test_missing_file_raises(self, tmp_path: Path, fake_drive: Path) -> None:
        missing = tmp_path / "nonexistent.md"
        with self._patch_drive(fake_drive):
            with pytest.raises(SystemExit):
                gdrive_ops.stage_audit_bundle(missing)

    def test_no_drive_raises(self, md_file: Path) -> None:
        with patch.object(gdrive_ops, "find_drive_root", return_value=None):
            with pytest.raises(SystemExit):
                gdrive_ops.stage_audit_bundle(md_file)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class TestStageBundleCLI:
    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(GDRIVE_SCRIPTS / "gdrive_ops.py"), *args],
            capture_output=True,
            text=True,
        )

    def test_cli_json_output_keys(self, md_file: Path, fake_drive: Path) -> None:
        with patch.object(gdrive_ops, "find_drive_root", return_value=fake_drive):
            result = gdrive_ops.stage_audit_bundle(md_file)
        assert {"bundle_dir", "staged", "skipped"} == set(result.keys())

    def test_cli_help_lists_stage_bundle(self) -> None:
        proc = self._run("--help")
        assert "stage-bundle" in proc.stdout

    def test_stage_bundle_help(self) -> None:
        proc = self._run("stage-bundle", "--help")
        assert proc.returncode == 0
        assert "audit" in proc.stdout.lower()
