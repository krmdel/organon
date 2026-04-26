"""Quote sidecar builder for sci-literature-research cite mode.

Writes a `{slug}.quotes.json` file alongside the `.bib` so downstream
skills (sci-writer, sci-auditor) have real pre-fetched source text to
work from instead of inventing quotes from memory.

Schema (v1):
    {
      "version": 1,
      "source": "sci-literature-research cite mode",
      "generated_at": "2026-04-13T10:30:00Z",
      "quotes": [
        {
          "key": "Mali2013",
          "doi": "10.1038/nature12373",
          "candidate_quotes": [
            {
              "text": "verbatim sentence from abstract or full text",
              "source_anchor": "10.1038/nature12373",
              "source_type": "doi" | "paperclip",
              "confidence": "abstract" | "full-text" | "title"
            }
          ]
        }
      ]
    }

Downstream usage: a writer agent reads this file and copies entries into
the draft's `.citations.json` sidecar (one entry per used `[@Key]`). The
writer is never supposed to fabricate a quote — the upstream seeds are
the only permitted source.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


SIDECAR_VERSION = 1
DEFAULT_SOURCE = "sci-literature-research cite mode"

# Max candidate quotes per bib key. Keeps the sidecar bounded and forces
# downstream agents to pick the best supporting sentence rather than
# dumping whole abstracts.
MAX_CANDIDATES_PER_KEY = 3

# Minimum sentence length (characters) to be worth surfacing.
MIN_SENTENCE_CHARS = 40


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _split_sentences(text: str) -> list[str]:
    """Rough sentence split on punctuation + capital letter. Good enough
    for abstracts; no NLP dep required."""
    if not text:
        return []
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if s.strip()]


def _best_sentences(text: str, limit: int = MAX_CANDIDATES_PER_KEY) -> list[str]:
    sentences = _split_sentences(text)
    kept = [s for s in sentences if len(s) >= MIN_SENTENCE_CHARS]
    return kept[:limit] if kept else sentences[:limit]


def _build_doi_candidates(entry: dict) -> list[dict]:
    """Build abstract-sourced candidates for a DOI entry.

    Tier 3: the title fallback is dead. The old behavior — emitting the
    paper title as a 'supporting quote' when no abstract was available —
    laundered a one-sentence label into the sidecar where downstream
    skills treated it like verbatim evidence. No abstract means no
    candidates; the caller must either add a Paperclip full-text entry
    or accept that this key has no upstream seed.
    """
    doi = (entry.get("doi") or "").strip()
    abstract = entry.get("abstract") or entry.get("summary") or ""

    out: list[dict] = []
    for sentence in _best_sentences(abstract):
        out.append(
            {
                "text": sentence,
                "source_anchor": doi,
                "source_type": "doi",
                "confidence": "abstract",
            }
        )
    return out


def _build_paperclip_candidates(entry: dict) -> list[dict]:
    """For Paperclip entries, `content.lines` is a list of `{line: n, text: "..."}`
    objects (see tool-paperclip citations section). Build anchors of the
    form `https://citations.gxl.ai/papers/<doc_id>#L<n>`.
    """
    doc_id = entry.get("doc_id") or entry.get("paperclip_id") or ""
    base = f"https://citations.gxl.ai/papers/{doc_id}" if doc_id else ""

    content = entry.get("content") or {}
    lines = content.get("lines") if isinstance(content, dict) else None

    out: list[dict] = []
    if isinstance(lines, list):
        for row in lines[:MAX_CANDIDATES_PER_KEY]:
            if not isinstance(row, dict):
                continue
            text = (row.get("text") or "").strip()
            line_no = row.get("line")
            if not text or line_no is None:
                continue
            anchor = f"{base}#L{line_no}" if base else ""
            if not anchor:
                continue
            out.append(
                {
                    "text": text,
                    "source_anchor": anchor,
                    "source_type": "paperclip",
                    "confidence": "full-text",
                }
            )

    if out:
        return out

    # Fallback: treat the entry like a normal DOI-based record if the
    # caller only surfaced an abstract.
    doi_fallback = _build_doi_candidates(entry)
    return doi_fallback


def _detect_source_type(entry: dict) -> str:
    source = (entry.get("source") or "").lower()
    if "paperclip" in source:
        return "paperclip"
    if entry.get("doc_id") or entry.get("paperclip_id"):
        return "paperclip"
    return "doi"


def build_quotes_sidecar(
    entries: Iterable[dict],
    bib_path: str,
    source: str = DEFAULT_SOURCE,
) -> str:
    """Build and write a `{slug}.quotes.json` file next to `bib_path`.

    Args:
        entries: Iterable of dicts, each describing one bib entry. Required
            keys: `key`. Optional: `doi`, `title`, `abstract`/`summary`,
            `content`, `doc_id` (paperclip), `source`.
        bib_path: Path to the sibling `.bib` file. The sidecar is written
            at `{bib_path.stem}.quotes.json` in the same directory.
        source: Free-text label stored in the sidecar header.

    Returns:
        Absolute path of the written sidecar file.
    """
    bib = Path(bib_path)
    if bib.suffix.lower() != ".bib":
        raise ValueError(f"bib_path must end in .bib, got '{bib_path}'")

    sidecar_path = bib.with_suffix(".quotes.json")

    quotes: list[dict] = []
    for entry in entries:
        key = (entry.get("key") or "").strip()
        if not key:
            continue
        src_type = _detect_source_type(entry)
        if src_type == "paperclip":
            candidates = _build_paperclip_candidates(entry)
        else:
            candidates = _build_doi_candidates(entry)
        if not candidates:
            continue
        quotes.append(
            {
                "key": key,
                "doi": (entry.get("doi") or "").strip() or None,
                "candidate_quotes": candidates,
            }
        )

    payload = {
        "version": SIDECAR_VERSION,
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "quotes": quotes,
    }

    sidecar_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return str(sidecar_path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Build a quotes.json sidecar from a JSON entries file."
    )
    parser.add_argument("entries_json", help="Path to JSON array of entry dicts")
    parser.add_argument("bib_path", help="Path to the sibling .bib file")
    args = parser.parse_args()

    with open(args.entries_json, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = build_quotes_sidecar(data, args.bib_path)
    print(out)
