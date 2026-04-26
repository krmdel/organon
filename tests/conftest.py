"""Shared test fixtures for Scientific OS tests."""

import os
import re
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: tests taking more than ~5s wall-clock")
    config.addinivalue_line("markers", "needs_arena_data: requires projects/einstein-arena-*/ fixture")
    config.addinivalue_line(
        "markers",
        "real_citation_verify: opt out of the conftest verify_citation stub "
        "(used by tests that exercise repro.citation_verify directly)",
    )


@pytest.fixture(autouse=True)
def _skip_doi_verification_by_default(monkeypatch):
    """Citation integrity Fix A: cmd_check_research now batch-verifies
    every DOI in the .bib against CrossRef before advancing to
    phase='researched'. Tests run offline and use fake/placeholder DOIs
    that would fail real CrossRef lookups, so we short-circuit the
    verification by default. Tests that specifically exercise the
    fabricated-DOI path must monkeypatch _verify_dois_via_crossref
    directly to return a forced failure.
    """
    monkeypatch.setenv("SCI_OS_SKIP_DOI_VERIFY", "1")


@pytest.fixture(autouse=True)
def _stub_citation_verification(monkeypatch, request):
    """Stub `repro.citation_verify` network functions for offline tests.

    Many tests seed bib entries with placeholder DOIs (e.g.
    10.1038/nature12373 paired with a hand-rolled title). Real CrossRef
    resolves those DOIs to real but unrelated papers, so check_bib_integrity
    (Phase 8) trips CRITICAL on every fixture. Default stub returns a
    passthrough that mirrors the bib entry: title + authors match by
    construction, no retraction, no dual-id conflict — so the gate passes
    without network. Tests that specifically exercise a verification
    failure (retraction, title mismatch, ConnectionError) override this
    fixture locally by monkeypatching `verify_citation`. Tests that
    exercise the real `repro.citation_verify` module (with their own
    HTTP-layer mocks) must mark themselves with
    `@pytest.mark.real_citation_verify` to opt out of the stub entirely.
    """
    if request.node.get_closest_marker("real_citation_verify"):
        return
    try:
        from repro import citation_verify
    except ImportError:
        return

    def _split_authors(raw):
        """Extract surnames from a bibtex author field so the stub
        matches what `compare_authors` expects from a CrossRef record."""
        if not raw:
            return []
        out = []
        for chunk in raw.split(" and "):
            chunk = chunk.strip()
            if not chunk:
                continue
            if "," in chunk:
                out.append(chunk.split(",", 1)[0].strip())
            else:
                parts = chunk.split()
                if parts:
                    out.append(parts[-1])
        return out

    def _stub_citation(entry):
        if not isinstance(entry, dict):
            return {
                "title": "",
                "authors": [],
                "is_retracted": False,
                "retraction_info": None,
                "abstract": "",
                "source": "stub",
                "dual_id_conflict": None,
            }
        return {
            "title": entry.get("title", ""),
            "authors": _split_authors(entry.get("author", "")),
            "is_retracted": False,
            "retraction_info": None,
            "abstract": "",
            "source": "stub",
            "dual_id_conflict": None,
        }

    def _stub_simple(identifier, **_):
        return {
            "title": "<stub>",
            "authors": [],
            "is_retracted": False,
            "retraction_info": None,
            "abstract": "",
            "source": "stub",
        }

    monkeypatch.setattr(citation_verify, "verify_citation", _stub_citation, raising=False)
    monkeypatch.setattr(citation_verify, "verify_doi", _stub_simple, raising=False)
    monkeypatch.setattr(citation_verify, "verify_arxiv", _stub_simple, raising=False)
    monkeypatch.setattr(citation_verify, "verify_pubmed", _stub_simple, raising=False)

    # verify_ops imports these at module load, so the module's local
    # bindings need patching too.
    try:
        import sys
        scripts_dir = (
            Path(__file__).resolve().parent.parent
            / ".claude" / "skills" / "sci-writing" / "scripts"
        )
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        import verify_ops as _verify_ops  # type: ignore[import-not-found]
        monkeypatch.setattr(_verify_ops, "verify_citation", _stub_citation, raising=False)
        monkeypatch.setattr(_verify_ops, "verify_doi", _stub_simple, raising=False)
        monkeypatch.setattr(_verify_ops, "verify_arxiv", _stub_simple, raising=False)
    except Exception:
        pass

    # researcher_ops auto-enables B3 receipt API verification when CI=true,
    # which would hit real CrossRef on test fixtures with placeholder DOIs.
    # Stub it to a no-op so receipts seeded from fake DOIs pass the gate.
    # paper_pipeline imports the same function under an alias, so patch
    # both bindings.
    _noop_receipts = lambda *_args, **_kwargs: []
    try:
        import researcher_ops as _researcher_ops  # type: ignore[import-not-found]
        monkeypatch.setattr(
            _researcher_ops, "verify_receipts_against_api", _noop_receipts,
            raising=False,
        )
    except Exception:
        pass
    try:
        import paper_pipeline as _paper_pipeline  # type: ignore[import-not-found]
        monkeypatch.setattr(
            _paper_pipeline, "_verify_receipts_api", _noop_receipts,
            raising=False,
        )
    except Exception:
        pass


@pytest.fixture
def tmp_repro_dir(tmp_path):
    """Create a temporary repro directory and patch LEDGER_PATH to use it."""
    ledger_path = tmp_path / "ledger.jsonl"
    summaries_dir = tmp_path / "summaries"
    summaries_dir.mkdir()

    with patch("repro.repro_logger.LEDGER_PATH", ledger_path):
        yield tmp_path


@pytest.fixture
def sample_data_file(tmp_path):
    """Create a temp CSV file with known content for hash testing."""
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("a,b\n1,2\n")
    return csv_file


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / ".claude" / "skills"
CLAUDE_MD = ROOT / "CLAUDE.md"
SCRIPTS_DIR = ROOT / "scripts"
ENV_EXAMPLE = ROOT / ".env.example"

ALL_SKILLS = sorted([
    d.name for d in SKILLS_DIR.iterdir()
    if d.is_dir() and not d.name.startswith("_")
])

ALL_SHELL_SCRIPTS = sorted(SCRIPTS_DIR.glob("**/*.sh"))

# Legacy skill names that must not appear in committed source files.
# Stored as fragments to avoid this file itself matching the cleanup grep.
_MKT = "mkt-"
_STR = "str-"
_VIZ_UGC = "viz-ugc-"
LEGACY_PATTERNS = [
    _MKT + "brand-voice", _MKT + "content-repurposing", _MKT + "copywriting",
    _MKT + "icp", _MKT + "positioning", _MKT + "ugc-scripts",
    _STR + "trending-research", _VIZ_UGC + "heygen",
]

EXCLUDED_DIRS = {".claude/worktrees", ".planning", ".git", "node_modules", ".venv"}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def load_skill_frontmatter(skill_name: str) -> dict:
    """Parse YAML frontmatter from a skill's SKILL.md."""
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    text = skill_md.read_text()
    match = re.match(r"^---\n(.*?\n)---", text, re.DOTALL)
    if not match:
        return {}
    return yaml.safe_load(match.group(1)) or {}


def extract_skill_names_from_registry() -> set:
    """Extract skill names from CLAUDE.md Skill Registry tables."""
    text = CLAUDE_MD.read_text()
    names = set()
    for m in re.finditer(r"\|\s*`([a-z][a-z0-9-]*)`\s*\|", text):
        name = m.group(1)
        if any(name.startswith(p) for p in ["sci-", "viz-", "tool-", "meta-", "ops-"]):
            names.add(name)
    return names


def extract_skill_names_from_context_matrix() -> set:
    """Extract skill names from CLAUDE.md Context Matrix table."""
    text = CLAUDE_MD.read_text()
    # Find Context Matrix section
    idx = text.find("## Context Matrix")
    if idx == -1:
        return set()
    section = text[idx:]
    names = set()
    for m in re.finditer(r"\|\s*`([a-z][a-z0-9-]*)`\s*\|", section):
        name = m.group(1)
        if any(name.startswith(p) for p in ["sci-", "viz-", "tool-", "meta-", "ops-"]):
            names.add(name)
    return names


def parse_service_registry() -> list:
    """Extract rows from CLAUDE.md Service Registry table."""
    text = CLAUDE_MD.read_text()
    idx = text.find("### Service Registry")
    if idx == -1:
        return []
    section = text[idx:idx+3000]
    rows = []
    lines = section.split("\n")
    table_lines = [l for l in lines if l.strip().startswith("|") and "---" not in l]
    if len(table_lines) < 2:
        return []
    headers = [h.strip() for h in table_lines[0].split("|")[1:-1]]
    for line in table_lines[1:]:
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows
