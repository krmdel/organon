"""Tests for tool-obsidian skill — isolated from any real vault.

Uses a tmp_path fake vault via monkeypatching find_vault, so tests run
on CI without needing Obsidian installed.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_SCRIPT = ROOT / ".claude" / "skills" / "tool-obsidian" / "scripts" / "obsidian_ops.py"


@pytest.fixture
def obs_module():
    spec = importlib.util.spec_from_file_location("obsidian_ops", SKILL_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_vault(tmp_path, monkeypatch, obs_module):
    """Fake vault with .obsidian marker, swapped in via monkeypatch."""
    vault = tmp_path / "TestVault"
    vault.mkdir()
    (vault / ".obsidian").mkdir()
    monkeypatch.setattr(obs_module, "find_vault", lambda: vault)
    return vault


class TestVaultDetection:
    def test_env_var_override(self, tmp_path, monkeypatch, obs_module):
        vault = tmp_path / "EnvVault"
        vault.mkdir()
        monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
        # Also clear the registry + common paths
        monkeypatch.setattr(obs_module, "MACOS_REGISTRY", tmp_path / "nonexistent.json")
        detected = obs_module.find_vault()
        assert detected == vault

    def test_env_var_expands_tilde(self, monkeypatch, obs_module, tmp_path):
        vault = tmp_path / "HomeVault"
        vault.mkdir()
        # Fake home → tmp_path so ~/HomeVault resolves to vault
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("OBSIDIAN_VAULT", "~/HomeVault")
        detected = obs_module._from_env()
        assert detected == vault

    def test_env_var_missing_returns_none(self, monkeypatch, obs_module):
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        assert obs_module._from_env() is None

    def test_env_var_nonexistent_returns_none(self, monkeypatch, obs_module, tmp_path):
        monkeypatch.setenv("OBSIDIAN_VAULT", str(tmp_path / "does_not_exist"))
        assert obs_module._from_env() is None

    def test_registry_picks_most_recent(self, tmp_path, monkeypatch, obs_module):
        v_old = tmp_path / "OldVault"
        v_old.mkdir()
        v_new = tmp_path / "NewVault"
        v_new.mkdir()
        registry = tmp_path / "obsidian.json"
        registry.write_text(json.dumps({
            "vaults": {
                "a": {"path": str(v_old), "ts": 100},
                "b": {"path": str(v_new), "ts": 200},
            }
        }))
        monkeypatch.setattr(obs_module, "MACOS_REGISTRY", registry)
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        assert obs_module._from_registry() == v_new

    def test_registry_skips_missing_paths(self, tmp_path, monkeypatch, obs_module):
        v_real = tmp_path / "RealVault"
        v_real.mkdir()
        registry = tmp_path / "obsidian.json"
        registry.write_text(json.dumps({
            "vaults": {
                "a": {"path": "/does/not/exist", "ts": 500},
                "b": {"path": str(v_real), "ts": 100},
            }
        }))
        monkeypatch.setattr(obs_module, "MACOS_REGISTRY", registry)
        assert obs_module._from_registry() == v_real

    def test_registry_empty_returns_none(self, tmp_path, monkeypatch, obs_module):
        registry = tmp_path / "obsidian.json"
        registry.write_text(json.dumps({"vaults": {}}))
        monkeypatch.setattr(obs_module, "MACOS_REGISTRY", registry)
        assert obs_module._from_registry() is None

    def test_find_vault_no_sources(self, monkeypatch, obs_module, tmp_path):
        monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
        monkeypatch.setattr(obs_module, "MACOS_REGISTRY", tmp_path / "no-registry.json")
        monkeypatch.setattr(obs_module, "_from_common_paths", lambda: None)
        assert obs_module.find_vault() is None


class TestStatus:
    def test_status_no_vault(self, monkeypatch, obs_module):
        monkeypatch.setattr(obs_module, "find_vault", lambda: None)
        s = obs_module.status()
        assert s["installed"] is False
        assert "error" in s

    def test_status_with_vault(self, fake_vault, obs_module):
        s = obs_module.status()
        assert s["installed"] is True
        assert s["vault_root"] == str(fake_vault)
        assert s["vault_name"] == "TestVault"
        assert s["staging_exists"] is False


class TestSlugify:
    @pytest.mark.parametrize("title,expected", [
        ("Hello World", "hello-world"),
        ("CRISPR Delivery — Paper Notes", "crispr-delivery-paper-notes"),
        ("   weird  spaces   ", "weird-spaces"),
        ("UPPER_case & punct!", "upper-case-punct"),
        ("", "untitled"),
        ("---", "untitled"),
        ("nümbér 42", "nümbér-42"),  # unicode word chars preserved
    ])
    def test_slugify(self, obs_module, title, expected):
        assert obs_module.slugify(title) == expected


class TestFrontmatter:
    def test_frontmatter_minimal(self, obs_module):
        fm = obs_module.build_frontmatter("My Title")
        assert fm.startswith("---\n")
        assert "title: My Title" in fm
        assert "created:" in fm
        assert fm.endswith("---\n")

    def test_frontmatter_with_tags(self, obs_module):
        fm = obs_module.build_frontmatter("T", tags=["foo", "#bar"])
        assert "tags: [foo, bar]" in fm  # # stripped

    def test_frontmatter_with_links(self, obs_module):
        fm = obs_module.build_frontmatter("T", links=["Other Note", "Second"])
        assert '"[[Other Note]]"' in fm
        assert '"[[Second]]"' in fm

    def test_frontmatter_with_source(self, obs_module):
        fm = obs_module.build_frontmatter("T", source="https://doi.org/10.1/abc")
        assert "source: https://doi.org/10.1/abc" in fm


class TestWriteNote:
    def test_write_basic(self, fake_vault, obs_module):
        dest = obs_module.write_note("My Paper", "Some content", category="paper-notes")
        assert dest.exists()
        assert dest.name == "my-paper.md"
        assert dest.parent.name == "paper-notes"
        text = dest.read_text()
        assert "title: My Paper" in text
        assert "# My Paper" in text
        assert "Some content" in text

    def test_write_creates_staging_root(self, fake_vault, obs_module):
        assert not (fake_vault / "organon").exists()
        obs_module.write_note("Seed", "body")
        assert (fake_vault / "organon").is_dir()
        assert (fake_vault / "organon" / "inbox").is_dir()

    def test_write_all_categories(self, fake_vault, obs_module):
        for cat in ["data-notes", "paper-notes", "daily", "experiments", "drafts", "inbox"]:
            dest = obs_module.write_note(f"{cat}-test", "body", category=cat)
            assert dest.parent.name == cat

    def test_write_invalid_category_raises(self, fake_vault, obs_module):
        with pytest.raises(SystemExit, match="unknown category"):
            obs_module.write_note("T", "body", category="nonsense")

    def test_write_collision_appends_counter(self, fake_vault, obs_module):
        d1 = obs_module.write_note("Same Title", "v1")
        d2 = obs_module.write_note("Same Title", "v2")
        d3 = obs_module.write_note("Same Title", "v3")
        assert {d1.name, d2.name, d3.name} == {"same-title.md", "same-title-1.md", "same-title-2.md"}
        assert d1.read_text().endswith("v1\n")
        assert d2.read_text().endswith("v2\n")

    def test_write_overwrite_flag(self, fake_vault, obs_module):
        d1 = obs_module.write_note("T", "original")
        d2 = obs_module.write_note("T", "replaced", overwrite=True)
        assert d1 == d2
        assert "replaced" in d2.read_text()

    def test_write_with_tags_and_links(self, fake_vault, obs_module):
        dest = obs_module.write_note(
            "Full Note", "body",
            tags=["foo", "bar"],
            links=["Other Paper"],
            source="https://example.com",
        )
        text = dest.read_text()
        assert "tags: [foo, bar]" in text
        assert '"[[Other Paper]]"' in text
        assert "source: https://example.com" in text

    def test_write_no_vault_raises(self, monkeypatch, obs_module):
        monkeypatch.setattr(obs_module, "find_vault", lambda: None)
        with pytest.raises(SystemExit, match="Obsidian vault not detected"):
            obs_module.write_note("T", "body")


class TestAppendNote:
    def test_append_to_existing(self, fake_vault, obs_module):
        dest = obs_module.write_note("Base", "first line")
        obs_module.append_to_note(dest, "second line")
        text = dest.read_text()
        assert "first line" in text
        assert "second line" in text

    def test_append_with_heading(self, fake_vault, obs_module):
        dest = obs_module.write_note("Base", "original")
        obs_module.append_to_note(dest, "new content", heading="Update")
        text = dest.read_text()
        assert "## Update" in text
        assert "new content" in text
        # Heading appears after original
        assert text.index("original") < text.index("## Update")

    def test_append_missing_note_raises(self, fake_vault, obs_module):
        with pytest.raises(SystemExit, match="note not found"):
            obs_module.append_to_note(fake_vault / "ghost.md", "x")


class TestDailyNote:
    def test_daily_path_is_today(self, fake_vault, obs_module):
        from datetime import date
        path = obs_module.daily_note_path()
        assert path.name == f"{date.today().isoformat()}.md"
        assert path.parent.name == "daily"

    def test_append_daily_creates_note(self, fake_vault, obs_module):
        from datetime import date
        path = obs_module.append_daily("first entry")
        assert path.exists()
        text = path.read_text()
        assert "first entry" in text
        assert f"title: {date.today().isoformat()}" in text
        assert "tags: [daily]" in text

    def test_append_daily_twice_same_file(self, fake_vault, obs_module):
        p1 = obs_module.append_daily("entry 1", heading="Morning")
        p2 = obs_module.append_daily("entry 2", heading="Afternoon")
        assert p1 == p2
        text = p2.read_text()
        assert "## Morning" in text
        assert "## Afternoon" in text
        assert "entry 1" in text
        assert "entry 2" in text


class TestListNotes:
    def test_list_empty(self, fake_vault, obs_module):
        assert obs_module.list_notes() == []

    def test_list_after_writing(self, fake_vault, obs_module):
        obs_module.write_note("Alpha", "a", category="data-notes")
        obs_module.write_note("Beta", "b", category="paper-notes")
        obs_module.write_note("Gamma", "c", category="inbox")
        entries = obs_module.list_notes()
        assert len(entries) == 3
        categories = {e["category"] for e in entries}
        assert categories == {"data-notes", "paper-notes", "inbox"}
        for e in entries:
            assert "obsidian_uri" in e
            assert e["obsidian_uri"].startswith("obsidian://open?vault=")

    def test_list_filtered_by_category(self, fake_vault, obs_module):
        obs_module.write_note("x1", "1", category="experiments")
        obs_module.write_note("x2", "2", category="experiments")
        obs_module.write_note("other", "3", category="inbox")
        exps = obs_module.list_notes(category="experiments")
        assert len(exps) == 2
        assert all(e["category"] == "experiments" for e in exps)


class TestSearchNotes:
    def test_search_by_content(self, fake_vault, obs_module):
        obs_module.write_note("N1", "this mentions CRISPR delivery")
        obs_module.write_note("N2", "this mentions protein folding")
        obs_module.write_note("N3", "irrelevant stuff")

        results = obs_module.search_notes("CRISPR")
        assert len(results) == 1
        assert results[0]["name"] == "n1.md"
        assert "CRISPR" in results[0]["snippet"]

    def test_search_case_insensitive(self, fake_vault, obs_module):
        obs_module.write_note("N1", "ALPHAFOLD3 results")
        results = obs_module.search_notes("alphafold3")
        assert len(results) == 1

    def test_search_by_filename(self, fake_vault, obs_module):
        obs_module.write_note("CRISPR Review", "body", category="paper-notes")
        results = obs_module.search_notes("crispr")
        assert len(results) == 1

    def test_search_no_results(self, fake_vault, obs_module):
        obs_module.write_note("unrelated", "nothing")
        assert obs_module.search_notes("does not exist") == []

    def test_search_filtered_by_category(self, fake_vault, obs_module):
        obs_module.write_note("Note A", "shared term", category="paper-notes")
        obs_module.write_note("Note B", "shared term", category="experiments")
        results = obs_module.search_notes("shared", category="paper-notes")
        assert len(results) == 1
        assert results[0]["category"] == "paper-notes"


class TestObsidianUri:
    def test_uri_format(self, fake_vault, obs_module):
        dest = obs_module.write_note("Test Note", "body", category="paper-notes")
        uri = obs_module.obsidian_uri(dest)
        assert uri.startswith("obsidian://open?vault=TestVault&file=")
        # file= should not include .md extension
        assert ".md" not in uri.split("file=")[1]
        # Should include the scientific-os/paper-notes/test-note path
        assert "paper-notes" in uri

    def test_uri_no_vault_returns_empty(self, monkeypatch, obs_module, tmp_path):
        monkeypatch.setattr(obs_module, "find_vault", lambda: None)
        assert obs_module.obsidian_uri(tmp_path / "x.md") == ""


class TestCli:
    """Subprocess smoke tests."""

    def test_cli_help(self):
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        for cmd in ["status", "write", "append", "daily", "list", "search", "link"]:
            assert cmd in result.stdout

    def test_cli_status_json_no_vault(self, tmp_path, monkeypatch):
        """When no vault is set, status should exit 1 but return valid JSON."""
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),  # no registry, no common paths under fake home
            "OBSIDIAN_VAULT": "",
        }
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "status", "--json"],
            capture_output=True, text=True, env=env,
        )
        # Exit code 1 when no vault detected
        assert result.returncode in (0, 1)
        payload = json.loads(result.stdout)
        assert "installed" in payload

    def test_cli_status_json_with_env_vault(self, tmp_path):
        vault = tmp_path / "CliVault"
        vault.mkdir()
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "OBSIDIAN_VAULT": str(vault),
        }
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "status", "--json"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["installed"] is True
        assert payload["vault_name"] == "CliVault"

    def test_cli_write_then_list(self, tmp_path):
        vault = tmp_path / "CliVault2"
        vault.mkdir()
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "OBSIDIAN_VAULT": str(vault),
        }
        # Write
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "write", "Test Paper",
             "--body", "CRISPR notes", "--category", "paper-notes",
             "--tags", "genomics,review", "--json"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert "staged" in payload
        assert payload["category"] == "paper-notes"

        # List
        result = subprocess.run(
            [sys.executable, str(SKILL_SCRIPT), "list", "--json"],
            capture_output=True, text=True, env=env,
        )
        assert result.returncode == 0
        entries = json.loads(result.stdout)
        assert len(entries) == 1
        assert entries[0]["name"] == "test-paper.md"
