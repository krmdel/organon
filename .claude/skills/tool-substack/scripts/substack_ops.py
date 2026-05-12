#!/usr/bin/env python3
"""substack_ops.py — markdown → Substack draft, direct HTTP client.

Subcommands:
    test-auth              Verify SUBSTACK_* env vars + session validity
    convert <md>           Print ProseMirror JSON for <md> (no network)
    upload-image <png>     Upload a single PNG, print CDN URL
    push <md>              Full pipeline: upload images, create draft
    list-drafts            List existing drafts (title, id, date)
    edit <id> <md>         Update an existing draft by id

Credentials (loaded from repo .env):
    SUBSTACK_PUBLICATION_URL   https://your-pub.substack.com
    SUBSTACK_SESSION_TOKEN     substack.sid cookie value
    SUBSTACK_USER_ID           integer user id

No external MCP server. No Docker. One script, one dependency chain
(markdown-it-py + requests), all local.
"""

from __future__ import annotations

import argparse
import base64
import datetime
import hashlib
import json
import mimetypes
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    import requests
except ImportError:
    print("[ERROR] 'requests' not installed. Run: bash .claude/skills/tool-substack/scripts/setup.sh", file=sys.stderr)
    sys.exit(1)

try:
    from markdown_it import MarkdownIt
    from markdown_it.token import Token
except ImportError:
    print("[ERROR] 'markdown-it-py' not installed. Run: bash .claude/skills/tool-substack/scripts/setup.sh", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# .env loader (walks up from this script to find repo .env, same pattern as
# viz-nano-banana/generate_image.py::_load_dotenv)
# ---------------------------------------------------------------------------


def _load_dotenv() -> None:
    here = Path(__file__).resolve()
    for parent in [here] + list(here.parents):
        candidate = parent / ".env"
        if candidate.is_file():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ.setdefault(key, val)
            return


_load_dotenv()


# ---------------------------------------------------------------------------
# Verification gate (E1) — pre-push citation check
# ---------------------------------------------------------------------------

# Matches [@Key]-style citation markers used by sci-writing pipeline.
# Phase 9: broadened from `[@Key]` to `[@Key…]` so pandoc-suffix forms
# (`[@Smith2020, p. 5]`, `[@A; @B]`, `[@A,@B]`) trigger the gate. The old
# strict pattern silently short-circuited the gate to "no citations", which
# bypassed the entire bib + sidecar contract for any draft using a non-canonical
# pandoc form. The new pattern only requires `[@\w` to fire — the actual key
# extraction happens in verify_ops.extract_used_keys.
_CITATION_MARKER_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*")

# Ledger for --no-verify overrides: one JSON record per line
LEDGER_PATH = Path.home() / ".scientific-os" / "substack-publish-ledger.jsonl"


def _write_ledger(entry: dict) -> None:
    """Append a JSON record to the publish ledger (creates parents as needed)."""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _safe_md5(path: Path) -> str:
    """Phase 9 (DP3): manuscript hash for ledger entries.

    Clean push/edit ledger entries already include the md5 of the manuscript
    bytes so a forensic audit can correlate any ledger row to the exact
    file content at the time of the action. This helper extends that
    invariant to bypass entries (--no-verify, refused, ungated_bypass)
    where the same correlation is most needed. Returns "" on read failure
    so a transient OSError can never block ledger writes.
    """
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except OSError:
        return ""


def _run_verify_gate(md_path: Path, no_verify: bool = False) -> tuple[bool, str]:
    """Run the citation verification gate on a markdown file.

    Looks for a sibling .bib file or [@Key] markers in the markdown.
    If found, imports verify_ops and runs run_verification().

    Returns:
        (blocked, report_text) — blocked=True means CRITICAL findings;
        caller must refuse unless no_verify=True (which logs to ledger).

    Gracefully degrades if verify_ops is unavailable — warns but allows push.
    """
    text = md_path.read_text(encoding="utf-8")
    has_markers = bool(_CITATION_MARKER_RE.search(text))

    # Locate sibling .bib
    bib_candidates = list(md_path.parent.glob("*.bib"))
    bib_path = str(bib_candidates[0]) if bib_candidates else None

    if not has_markers and not bib_path:
        # No citations to gate — clean pass
        return False, ""

    # Locate verify_ops.py relative to this script
    # substack_ops.py: .claude/skills/tool-substack/scripts/
    # verify_ops.py:   .claude/skills/sci-writing/scripts/
    sci_writing_scripts = (
        Path(__file__).resolve().parents[2] / "sci-writing" / "scripts"
    )
    if str(sci_writing_scripts) not in sys.path:
        sys.path.insert(0, str(sci_writing_scripts))
    # Also ensure project root is on path for repro/ imports
    project_root = Path(__file__).resolve().parents[4]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    try:
        from verify_ops import run_verification, VerificationError  # type: ignore[import]
    except ImportError as e:
        # Phase 8: a missing verify_ops on the publish path used to fall through
        # to a clean pass with a stderr WARNING. That turned a broken venv into
        # a silent disable of the citation gate. Now: refuse the publish unless
        # the operator explicitly opts out via SCI_OS_ALLOW_UNGATED=1, in which
        # case the bypass is logged to the publish ledger so the audit trail
        # records the override.
        msg = (
            f"[tool-substack] BLOCKED: verify_ops unavailable ({e}). "
            "The citation gate cannot run, so the publish is refused. "
            "Fix the import error (likely a broken venv or missing repro/ "
            "dependency) and retry. To bypass in an emergency, set "
            "SCI_OS_ALLOW_UNGATED=1 — the bypass is logged to "
            f"{LEDGER_PATH}."
        )
        if os.environ.get("SCI_OS_ALLOW_UNGATED", "").strip().lower() in ("1", "true", "yes"):
            try:
                _write_ledger({
                    "ts": datetime.datetime.utcnow().isoformat() + "Z",
                    "outcome": "ungated_bypass",
                    "path": str(md_path),
                    "reason": f"verify_ops ImportError: {e}",
                    "md5": _safe_md5(md_path),
                })
            except Exception:
                pass
            print(
                f"[tool-substack] SCI_OS_ALLOW_UNGATED=1 — proceeding "
                f"WITHOUT citation gate (logged to {LEDGER_PATH}).",
                file=sys.stderr,
            )
            return False, "ungated_bypass"
        print(msg, file=sys.stderr)
        return True, "verify_ops_unavailable"

    print("[tool-substack] running citation verification gate…", file=sys.stderr)
    try:
        result = run_verification(
            manuscript_path=str(md_path),
            bib_path=bib_path,
            apply_fixes=False,
        )
    except VerificationError as e:
        # Missing bib when [@Key] markers exist — treat as blocked
        report = f"[tool-substack] GATE BLOCKED: {e}"
        print(report, file=sys.stderr)
        return True, report

    blocked = result.get("blocked", False)
    summary = result.get("summary", {})
    criticals = summary.get("critical", 0)
    majors = summary.get("major", 0)

    status_line = (
        f"CRITICAL={criticals} MAJOR={majors} INFO={summary.get('info', 0)}"
    )

    if blocked:
        lines = [
            "",
            "┌─────────────────────────────────────────────────────────────┐",
            "│  SUBSTACK PUSH BLOCKED — CITATION GATE FAILED               │",
            "└─────────────────────────────────────────────────────────────┘",
            f"  {status_line}",
            "",
        ]
        findings = result.get("findings", [])
        crit_findings = [f for f in findings if f.get("severity") == "critical"]
        for f in crit_findings[:5]:
            lines.append(f"  • [{f.get('criterion','')}] {f.get('finding','')}")
        if len(crit_findings) > 5:
            lines.append(f"  … and {len(crit_findings) - 5} more CRITICAL findings")
        lines += [
            "",
            "  Fix the citations above, or bypass with:",
            f"  python3 {Path(__file__).name} push --no-verify {md_path}",
            "  (bypass is logged to the publish ledger)",
            "",
        ]
        report = "\n".join(lines)
        print(report, file=sys.stderr)
    else:
        print(
            f"[tool-substack] citation gate passed ({status_line})",
            file=sys.stderr,
        )

    return blocked, status_line


# ---------------------------------------------------------------------------
# E2 — verification footer helpers
# ---------------------------------------------------------------------------


def _audit_bundle_sha1(md_path: Path) -> str:
    """Compute SHA1 over all audit artefacts adjacent to the markdown file.

    Searches the same directory for: *.bib, *.citations.json, *-audit.md.
    Falls back to the markdown file itself when no audit artefacts exist.
    Returns the first 12 hex chars of the digest — long enough to be
    meaningful, short enough to read in a footer.
    """
    import hashlib

    artefacts: list[Path] = []
    for pattern in ("*.bib", "*.citations.json", "*-audit.md"):
        artefacts.extend(sorted(md_path.parent.glob(pattern)))
    if not artefacts:
        artefacts = [md_path]

    h = hashlib.sha1()
    for p in sorted(artefacts):
        try:
            h.update(p.read_bytes())
        except OSError:
            pass
    return h.hexdigest()[:12]


def _build_footer_nodes(md_path: Path, gate_summary: str) -> list[dict]:
    """Return ProseMirror nodes for the verification footer paragraph.

    Format:
        ─────────────────────────────────────────
        Verified by Scientific-OS citation gate · SHA: <sha1> · <audit_file>
    """
    sha1 = _audit_bundle_sha1(md_path)
    audit_files = sorted(md_path.parent.glob("*-audit.md"))
    audit_ref = audit_files[0].name if audit_files else f"{md_path.stem}-audit.md"
    status = f" · {gate_summary}" if gate_summary and gate_summary != "no-citations" else ""
    footer_text = (
        f"Verified by Scientific-OS citation gate · SHA: {sha1} · {audit_ref}{status}"
    )
    return [
        {"type": "horizontal_rule"},
        {
            "type": "paragraph",
            "attrs": {"textAlign": "left"},
            "content": [
                {
                    "type": "text",
                    "text": footer_text,
                    "marks": [{"type": "em"}],
                }
            ],
        },
    ]


PUBLICATION_URL = os.environ.get("SUBSTACK_PUBLICATION_URL", "").rstrip("/")
SESSION_TOKEN = os.environ.get("SUBSTACK_SESSION_TOKEN", "")
USER_ID = os.environ.get("SUBSTACK_USER_ID", "")


# ---------------------------------------------------------------------------
# Credential check
# ---------------------------------------------------------------------------


CREDENTIALS_GUIDE = """
[tool-substack] Missing Substack credentials in .env

Required variables:
  SUBSTACK_PUBLICATION_URL   (e.g. https://organon-sandbox.substack.com)
  SUBSTACK_SESSION_TOKEN     (value of substack.sid cookie)
  SUBSTACK_USER_ID           (integer user id)

Extraction steps:
  1. Log into your Substack publication in Chrome
  2. DevTools → Application → Cookies → https://substack.com
     Copy the value of 'substack.sid' → SUBSTACK_SESSION_TOKEN
  3. DevTools → Network tab → refresh page → filter 'subscription'
     Click a request, look for '"user_id": <int>' in the response → SUBSTACK_USER_ID
  4. SUBSTACK_PUBLICATION_URL = root URL of your publication

Add all three to .env (gitignored). See .env.example for the template.
"""


def _require_credentials() -> None:
    missing = [
        name
        for name, val in [
            ("SUBSTACK_PUBLICATION_URL", PUBLICATION_URL),
            ("SUBSTACK_SESSION_TOKEN", SESSION_TOKEN),
            ("SUBSTACK_USER_ID", USER_ID),
        ]
        if not val
    ]
    if missing:
        print(CREDENTIALS_GUIDE, file=sys.stderr)
        print(f"[tool-substack] Missing: {', '.join(missing)}", file=sys.stderr)
        sys.exit(2)


# ---------------------------------------------------------------------------
# HTTP session factory
# ---------------------------------------------------------------------------


def _session() -> requests.Session:
    s = requests.Session()
    # Substack uses two cookie names that both reference the same session
    s.cookies.set("substack.sid", SESSION_TOKEN, domain=".substack.com")
    s.cookies.set("connect.sid", SESSION_TOKEN, domain=".substack.com")
    pub_host = PUBLICATION_URL.replace("https://", "").replace("http://", "")
    s.cookies.set("substack.sid", SESSION_TOKEN, domain=pub_host)
    s.cookies.set("connect.sid", SESSION_TOKEN, domain=pub_host)
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36",
            "Referer": f"{PUBLICATION_URL}/publish/post",
            "Origin": PUBLICATION_URL,
            "Accept": "application/json",
        }
    )
    return s


# ---------------------------------------------------------------------------
# test-auth
# ---------------------------------------------------------------------------


def cmd_test_auth() -> int:
    _require_credentials()
    s = _session()
    url = f"{PUBLICATION_URL}/api/v1/subscription"
    try:
        r = s.get(url, timeout=15)
    except requests.RequestException as e:
        print(f"[tool-substack] network error: {e}", file=sys.stderr)
        return 1
    print(f"[tool-substack] GET {url} → {r.status_code}")
    if r.status_code == 200:
        try:
            data = r.json()
        except Exception:
            data = {}
        print(f"[tool-substack] publication URL: {PUBLICATION_URL}")
        print(f"[tool-substack] user id: {USER_ID}")
        print("[tool-substack] session valid ✓")
        return 0
    print(f"[tool-substack] response: {r.text[:500]}", file=sys.stderr)
    print("[tool-substack] session invalid — re-extract substack.sid cookie", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


def _image_to_data_uri(path: Path) -> str:
    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        mime = "image/png"
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def upload_image(path: Path) -> dict[str, Any]:
    """Upload a single local image, return the Substack CDN descriptor.

    Substack's endpoint accepts JSON {image: <data uri | public url>}
    and returns a dict with fields including {url, width, height, ...}.
    Exact response shape may vary; we return whatever JSON comes back.
    """
    _require_credentials()
    if not path.is_file():
        raise FileNotFoundError(f"image not found: {path}")
    url = f"{PUBLICATION_URL}/api/v1/image"
    payload = {"image": _image_to_data_uri(path)}
    s = _session()
    r = s.post(url, json=payload, timeout=60)
    if r.status_code >= 400:
        raise RuntimeError(
            f"image upload failed {r.status_code}: {r.text[:500]}"
        )
    try:
        return r.json()
    except Exception as e:
        raise RuntimeError(f"image upload returned non-JSON: {r.text[:500]}") from e


def cmd_upload_image(path_str: str) -> int:
    path = Path(path_str).expanduser().resolve()
    try:
        data = upload_image(path)
    except Exception as e:
        print(f"[tool-substack] {e}", file=sys.stderr)
        return 1
    print(json.dumps(data, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------


_FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONT_RE.match(text)
    if not m:
        return {}, text
    fm_raw = m.group(1)
    body = text[m.end() :]
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip('"').strip("'")
    return fm, body


# ---------------------------------------------------------------------------
# Markdown → ProseMirror
# ---------------------------------------------------------------------------
#
# Substack's ProseMirror schema (observed from their editor network calls and
# from community reverse-engineering in SubstackPost.js):
#
#   doc               → {type: 'doc', content: [...]}
#   heading           → {type: 'heading', attrs: {level}, content: [inline...]}
#   paragraph         → {type: 'paragraph', content: [inline...]}
#   bullet_list       → {type: 'bullet_list', content: [list_item...]}
#   ordered_list      → {type: 'ordered_list', attrs: {start, order}, content: [...]}
#   list_item         → {type: 'list_item', content: [{type: 'paragraph', content: [inline...]}]}
#   blockquote        → {type: 'blockquote', content: [paragraph...]}
#   horizontal_rule   → {type: 'horizontal_rule'}
#   code_block        → {type: 'code_block', attrs: {language}, content: [{type: 'text', text: '...'}]}
#   captionedImage    → {type: 'captionedImage', content: [{type: 'image2', attrs: {src, alt, width, height, resizeWidth}}]}
#
# Inline:
#   text              → {type: 'text', text: '...'}
#   strong mark       → {type: 'strong'}
#   em mark           → {type: 'em'}
#   code mark         → {type: 'code'}
#   link mark         → {type: 'link', attrs: {href, target: '_blank', rel: '', class: null}}
#
# If Substack rejects any of these shapes we'll find out on the first test push
# and fix the specific node in place — every mapping is isolated.


def _img_dims(path: Path) -> tuple[int, int]:
    """Return (width, height) for a PNG without pulling in Pillow.

    PNG IHDR chunk starts at byte 16. Width and height are big-endian uint32.
    If parsing fails, return (1456, 819) — Substack's default content width.
    """
    try:
        with path.open("rb") as f:
            sig = f.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                return 1456, 819
            f.read(4)  # chunk length
            f.read(4)  # 'IHDR'
            w = int.from_bytes(f.read(4), "big")
            h = int.from_bytes(f.read(4), "big")
            if w > 0 and h > 0:
                return w, h
    except Exception:
        pass
    return 1456, 819


class PMConverter:
    """Walk markdown-it tokens and emit ProseMirror JSON.

    Handles: headings, paragraphs, bullet/ordered lists, blockquotes, code
    blocks (with language), horizontal rules, inline bold/italic/code/link,
    and image references (local paths get uploaded first, external URLs pass
    through).
    """

    def __init__(self, base_dir: Path, upload_fn) -> None:
        self.base_dir = base_dir
        self.upload_fn = upload_fn
        self._mark_stack: list[dict[str, Any]] = []

    # -- inline ------------------------------------------------------------

    def _inline(self, token: Token) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not token.children:
            return out
        marks: list[dict[str, Any]] = []
        for child in token.children:
            t = child.type
            if t == "text":
                if child.content:
                    out.append(self._text_node(child.content, marks))
            elif t == "strong_open":
                marks = marks + [{"type": "strong"}]
            elif t == "strong_close":
                marks = [m for m in marks if m["type"] != "strong"]
            elif t == "em_open":
                marks = marks + [{"type": "em"}]
            elif t == "em_close":
                marks = [m for m in marks if m["type"] != "em"]
            elif t == "code_inline":
                out.append(self._text_node(child.content, marks + [{"type": "code"}]))
            elif t == "link_open":
                href = dict(child.attrs or {}).get("href", "")
                marks = marks + [
                    {
                        "type": "link",
                        "attrs": {
                            "href": href,
                            "target": "_blank",
                            "rel": "",
                            "class": None,
                        },
                    }
                ]
            elif t == "link_close":
                marks = [m for m in marks if m["type"] != "link"]
            elif t == "softbreak":
                out.append(self._text_node(" ", marks))
            elif t == "hardbreak":
                out.append({"type": "hard_break"})
            elif t == "image":
                # markdown image inline — rare, usually top-level blocks
                attrs = dict(child.attrs or {})
                src = attrs.get("src", "")
                alt = child.content or attrs.get("alt", "")
                node = self._image_node(src, alt)
                if node:
                    out.append(node)
            # silently skip anything else
        return out

    def _text_node(self, text: str, marks: list[dict[str, Any]]) -> dict[str, Any]:
        node: dict[str, Any] = {"type": "text", "text": text}
        if marks:
            node["marks"] = [dict(m) for m in marks]
        return node

    # -- images ------------------------------------------------------------

    def _image_node(self, src: str, alt: str) -> dict[str, Any] | None:
        """Return a captionedImage node, uploading local files if needed."""
        if not src:
            return None
        if src.startswith(("http://", "https://")):
            cdn_url = src
            width, height = 1456, 819
        else:
            # Resolve local path — absolute or relative to markdown file
            p = Path(src)
            if not p.is_absolute():
                p = (self.base_dir / src).resolve()
            if not p.is_file():
                print(
                    f"[tool-substack] image not found, skipping: {src}",
                    file=sys.stderr,
                )
                return None
            if getattr(self.upload_fn, "_dry_run", False):
                print(f"[tool-substack] (dry) skip upload: {p.name}", file=sys.stderr)
            else:
                print(f"[tool-substack] uploading image: {p.name}", file=sys.stderr)
            try:
                uploaded = self.upload_fn(p)
            except Exception as e:
                raise RuntimeError(f"image upload failed for {p.name}: {e}") from e
            cdn_url = (
                uploaded.get("url")
                or uploaded.get("image_url")
                or uploaded.get("src")
                or ""
            )
            if not cdn_url:
                raise RuntimeError(
                    f"image upload response missing url: {uploaded}"
                )
            width = (
                uploaded.get("imageWidth")
                or uploaded.get("width")
                or 0
            )
            height = (
                uploaded.get("imageHeight")
                or uploaded.get("height")
                or 0
            )
            if not (width and height):
                width, height = _img_dims(p)
        return {
            "type": "captionedImage",
            "content": [
                {
                    "type": "image2",
                    "attrs": {
                        "src": cdn_url,
                        "fullscreen": False,
                        "imageSize": "normal",
                        "height": int(height),
                        "width": int(width),
                        "resizeWidth": min(728, int(width)),
                        "bytes": None,
                        "alt": alt or None,
                        "title": None,
                        "type": None,
                        "href": None,
                        "belowTheFold": False,
                        "internalRedirect": None,
                    },
                }
            ],
        }

    # -- blocks ------------------------------------------------------------

    def convert(self, md: str) -> dict[str, Any]:
        parser = MarkdownIt("commonmark", {"html": False, "linkify": True})
        tokens = parser.parse(md)
        content: list[dict[str, Any]] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            t = tok.type

            if t == "heading_open":
                level = int(tok.tag[1])
                inline = tokens[i + 1]
                content.append(
                    {
                        "type": "heading",
                        "attrs": {"level": level},
                        "content": self._inline(inline),
                    }
                )
                i += 3  # heading_open, inline, heading_close
                continue

            if t == "paragraph_open":
                inline = tokens[i + 1]
                # Check if this paragraph is a bare image (common blog pattern)
                if (
                    inline.children
                    and len(inline.children) == 1
                    and inline.children[0].type == "image"
                ):
                    child = inline.children[0]
                    attrs = dict(child.attrs or {})
                    img_node = self._image_node(
                        attrs.get("src", ""), child.content or attrs.get("alt", "")
                    )
                    if img_node:
                        content.append(img_node)
                else:
                    para_content = self._inline(inline)
                    if para_content:
                        content.append({"type": "paragraph", "attrs": {"textAlign": "justify"}, "content": para_content})
                    else:
                        content.append({"type": "paragraph", "attrs": {"textAlign": "justify"}})
                i += 3  # paragraph_open, inline, paragraph_close
                continue

            if t == "bullet_list_open":
                items, consumed = self._collect_list(tokens, i, ordered=False)
                content.append(
                    {"type": "bullet_list", "content": items}
                )
                i += consumed
                continue

            if t == "ordered_list_open":
                items, consumed = self._collect_list(tokens, i, ordered=True)
                content.append(
                    {
                        "type": "ordered_list",
                        "attrs": {"start": 1, "order": 1},
                        "content": items,
                    }
                )
                i += consumed
                continue

            if t == "blockquote_open":
                block, consumed = self._collect_blockquote(tokens, i)
                content.append(block)
                i += consumed
                continue

            if t == "fence" or t == "code_block":
                language = (tok.info or "").strip() or None
                code_text = tok.content.rstrip("\n")
                attrs: dict[str, Any] = {}
                if language:
                    attrs["language"] = language
                node = {"type": "code_block", "content": [{"type": "text", "text": code_text}]}
                if attrs:
                    node["attrs"] = attrs
                content.append(node)
                i += 1
                continue

            if t == "hr":
                content.append({"type": "horizontal_rule"})
                i += 1
                continue

            # Unknown / unsupported — skip silently but warn
            i += 1

        return {"type": "doc", "content": content}

    def _collect_list(
        self, tokens: list[Token], start: int, ordered: bool
    ) -> tuple[list[dict[str, Any]], int]:
        close_type = "ordered_list_close" if ordered else "bullet_list_close"
        items: list[dict[str, Any]] = []
        i = start + 1
        while i < len(tokens) and tokens[i].type != close_type:
            if tokens[i].type == "list_item_open":
                li_content, consumed = self._collect_list_item(tokens, i)
                items.append({"type": "list_item", "content": li_content})
                i += consumed
            else:
                i += 1
        return items, (i - start) + 1  # include the close token

    def _collect_list_item(
        self, tokens: list[Token], start: int
    ) -> tuple[list[dict[str, Any]], int]:
        content: list[dict[str, Any]] = []
        i = start + 1
        while i < len(tokens) and tokens[i].type != "list_item_close":
            t = tokens[i].type
            if t == "paragraph_open":
                inline = tokens[i + 1]
                content.append(
                    {"type": "paragraph", "attrs": {"textAlign": "justify"}, "content": self._inline(inline)}
                )
                i += 3
            else:
                i += 1
        return content, (i - start) + 1

    def _collect_blockquote(
        self, tokens: list[Token], start: int
    ) -> tuple[dict[str, Any], int]:
        inner: list[dict[str, Any]] = []
        i = start + 1
        while i < len(tokens) and tokens[i].type != "blockquote_close":
            t = tokens[i].type
            if t == "paragraph_open":
                inline = tokens[i + 1]
                inner.append({"type": "paragraph", "attrs": {"textAlign": "justify"}, "content": self._inline(inline)})
                i += 3
            else:
                i += 1
        return {"type": "blockquote", "content": inner}, (i - start) + 1


# ---------------------------------------------------------------------------
# Mermaid pre-render
# ---------------------------------------------------------------------------


_MERMAID_FENCE_RE = re.compile(
    r"^```mermaid\s*\n(.*?)\n```\s*$",
    re.MULTILINE | re.DOTALL,
)


def preprocess_mermaid(body: str, base_dir: Path, output_dir: Path) -> str:
    """Render each ```mermaid fenced block to PNG via viz-diagram-code and
    replace the fenced block with an image reference. If rendering fails,
    leave the block intact (Substack will ship it as a code block).

    Produces files next to the markdown named:
        {md_stem}_mermaid_{N}.mmd  (source)
        {md_stem}_mermaid_{N}.png  (rendered)
    """
    render_script = (
        Path(__file__).resolve().parents[2]
        / "viz-diagram-code"
        / "scripts"
        / "render_diagram.sh"
    )
    if not render_script.is_file():
        return body

    import subprocess

    count = 0

    def _replace(match: "re.Match[str]") -> str:
        nonlocal count
        count += 1
        diagram_src = match.group(1)
        mmd_path = output_dir / f"mermaid_{count}.mmd"
        png_path = output_dir / f"mermaid_{count}.png"
        try:
            mmd_path.write_text(diagram_src, encoding="utf-8")
            out_base = str(png_path.with_suffix(""))
            subprocess.run(
                ["bash", str(render_script), str(mmd_path), out_base],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except Exception as e:
            print(
                f"[tool-substack] mermaid render failed ({e}) — falling back "
                f"to code block for diagram #{count}",
                file=sys.stderr,
            )
            return match.group(0)
        if not png_path.is_file():
            print(
                f"[tool-substack] mermaid render produced no PNG for diagram "
                f"#{count} — falling back to code block",
                file=sys.stderr,
            )
            return match.group(0)
        print(
            f"[tool-substack] mermaid diagram #{count} rendered → "
            f"{png_path.name}",
            file=sys.stderr,
        )
        return f"![Diagram {count}]({png_path})"

    return _MERMAID_FENCE_RE.sub(_replace, body)


# ---------------------------------------------------------------------------
# convert / push
# ---------------------------------------------------------------------------


def cmd_convert(md_path: str) -> int:
    path = Path(md_path).expanduser().resolve()
    if not path.is_file():
        print(f"[tool-substack] file not found: {path}", file=sys.stderr)
        return 1
    raw = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(raw)

    # Dry converter — no upload function, just inline raw URLs
    def no_upload(_p: Path) -> dict[str, Any]:
        return {"url": f"LOCAL://{_p.name}"}

    no_upload._dry_run = True  # type: ignore[attr-defined]
    conv = PMConverter(base_dir=path.parent, upload_fn=no_upload)
    doc = conv.convert(body)
    out = {
        "title": fm.get("title", ""),
        "subtitle": fm.get("subtitle", ""),
        "doc": doc,
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_push(md_path: str, no_verify: bool = False, no_footer: bool = False) -> int:
    _require_credentials()
    path = Path(md_path).expanduser().resolve()
    if not path.is_file():
        print(f"[tool-substack] file not found: {path}", file=sys.stderr)
        return 1

    # E1 — pre-push citation gate
    blocked, gate_summary = _run_verify_gate(path, no_verify=no_verify)
    if blocked:
        if no_verify:
            _write_ledger({
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
                "action": "push",
                "file": str(path),
                "override": "--no-verify",
                "gate_summary": gate_summary,
                "md5": _safe_md5(path),
            })
            print(
                "[tool-substack] --no-verify: bypass logged to ledger, continuing.",
                file=sys.stderr,
            )
        else:
            _write_ledger({
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
                "action": "push",
                "file": str(path),
                "override": "refused",
                "gate_summary": gate_summary,
                "md5": _safe_md5(path),
            })
            return 1

    raw = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(raw)
    title = fm.get("title", path.stem)
    subtitle = fm.get("subtitle", "")

    print(f"[tool-substack] title:    {title}")
    print(f"[tool-substack] subtitle: {subtitle}")
    print(f"[tool-substack] target:   {PUBLICATION_URL}")

    # Pre-render any ```mermaid blocks to PNG so Substack shows images
    # instead of raw code blocks. Artifacts land next to the markdown.
    body = preprocess_mermaid(body, base_dir=path.parent, output_dir=path.parent)

    conv = PMConverter(base_dir=path.parent, upload_fn=upload_image)
    try:
        doc = conv.convert(body)
    except Exception as e:
        print(f"[tool-substack] conversion failed: {e}", file=sys.stderr)
        return 1

    # E2 — append verification footer unless opted out
    if not no_footer:
        doc["content"].extend(_build_footer_nodes(path, gate_summary))

    # Build draft payload matching Substack's expected shape
    draft_payload = {
        "draft_title": title,
        "draft_subtitle": subtitle,
        "draft_body": json.dumps(doc),
        "draft_bylines": [{"id": int(USER_ID), "is_guest": False}],
        "audience": "everyone",
        "write_comment_permissions": "everyone",
        "draft_section_id": None,
        "section_chosen": True,
    }

    s = _session()
    url = f"{PUBLICATION_URL}/api/v1/drafts"
    print(f"[tool-substack] POST {url}")
    try:
        r = s.post(url, json=draft_payload, timeout=60)
    except requests.RequestException as e:
        print(f"[tool-substack] network error: {e}", file=sys.stderr)
        return 1
    if r.status_code >= 400:
        print(
            f"[tool-substack] draft creation failed {r.status_code}: {r.text[:800]}",
            file=sys.stderr,
        )
        return 1
    try:
        data = r.json()
    except Exception:
        print(f"[tool-substack] non-JSON response: {r.text[:500]}", file=sys.stderr)
        return 1
    draft_id = data.get("id") or data.get("post_id") or "?"
    print(f"[tool-substack] draft created ✓  id={draft_id}")
    print(f"[tool-substack] edit:  {PUBLICATION_URL}/publish/post/{draft_id}")

    # E2 — log successful push to ledger (for audit trail)
    _write_ledger({
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "action": "push",
        "file": str(path),
        "draft_id": str(draft_id),
        "override": "--no-verify" if (no_verify and blocked) else "clean",
        "gate_summary": gate_summary or "no-citations",
        "md5": hashlib.md5(path.read_bytes()).hexdigest(),
    })
    return 0


# ---------------------------------------------------------------------------
# list-drafts
# ---------------------------------------------------------------------------


def cmd_list_drafts(limit: int = 20) -> int:
    _require_credentials()
    s = _session()
    url = f"{PUBLICATION_URL}/api/v1/drafts"
    params = {"filter": "draft", "limit": limit, "offset": 0}
    try:
        r = s.get(url, params=params, timeout=30)
    except requests.RequestException as e:
        print(f"[tool-substack] network error: {e}", file=sys.stderr)
        return 1
    if r.status_code >= 400:
        print(
            f"[tool-substack] list failed {r.status_code}: {r.text[:500]}",
            file=sys.stderr,
        )
        return 1
    try:
        data = r.json()
    except Exception:
        print(f"[tool-substack] non-JSON response: {r.text[:500]}", file=sys.stderr)
        return 1
    # Response is a list of draft objects
    drafts = data if isinstance(data, list) else data.get("drafts", data.get("posts", []))
    if not drafts:
        print("[tool-substack] no drafts found")
        return 0
    print(f"[tool-substack] {len(drafts)} draft(s):\n")
    for d in drafts:
        did = d.get("id", "?")
        title = d.get("draft_title") or d.get("title") or "(untitled)"
        updated = d.get("draft_updated_at") or d.get("post_date") or ""
        if updated:
            updated = updated[:19].replace("T", " ")
        slug = d.get("slug", "")
        print(f"  id={did}  updated={updated}")
        print(f"    title: {title}")
        if slug:
            print(f"    slug:  {slug}")
        print(f"    edit:  {PUBLICATION_URL}/publish/post/{did}")
        print()
    return 0


# ---------------------------------------------------------------------------
# edit (update existing draft)
# ---------------------------------------------------------------------------


def cmd_edit(draft_id: str, md_path: str, no_verify: bool = False, no_footer: bool = False) -> int:
    _require_credentials()
    path = Path(md_path).expanduser().resolve()
    if not path.is_file():
        print(f"[tool-substack] file not found: {path}", file=sys.stderr)
        return 1

    # E1 — pre-edit citation gate (same contract as push)
    blocked, gate_summary = _run_verify_gate(path, no_verify=no_verify)
    if blocked:
        if no_verify:
            _write_ledger({
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
                "action": "edit",
                "draft_id": draft_id,
                "file": str(path),
                "override": "--no-verify",
                "gate_summary": gate_summary,
                "md5": _safe_md5(path),
            })
            print(
                "[tool-substack] --no-verify: bypass logged to ledger, continuing.",
                file=sys.stderr,
            )
        else:
            _write_ledger({
                "ts": datetime.datetime.utcnow().isoformat() + "Z",
                "action": "edit",
                "draft_id": draft_id,
                "file": str(path),
                "override": "refused",
                "gate_summary": gate_summary,
                "md5": _safe_md5(path),
            })
            return 1

    raw = path.read_text(encoding="utf-8")
    fm, body = split_frontmatter(raw)
    title = fm.get("title", path.stem)
    subtitle = fm.get("subtitle", "")

    print(f"[tool-substack] editing draft id={draft_id}")
    print(f"[tool-substack] title:    {title}")
    print(f"[tool-substack] subtitle: {subtitle}")
    print(f"[tool-substack] target:   {PUBLICATION_URL}")

    body = preprocess_mermaid(body, base_dir=path.parent, output_dir=path.parent)

    conv = PMConverter(base_dir=path.parent, upload_fn=upload_image)
    try:
        doc = conv.convert(body)
    except Exception as e:
        print(f"[tool-substack] conversion failed: {e}", file=sys.stderr)
        return 1

    # E2 — append verification footer unless opted out
    if not no_footer:
        doc["content"].extend(_build_footer_nodes(path, gate_summary))

    draft_payload = {
        "draft_title": title,
        "draft_subtitle": subtitle,
        "draft_body": json.dumps(doc),
        "draft_bylines": [{"id": int(USER_ID), "is_guest": False}],
        "audience": "everyone",
        "write_comment_permissions": "everyone",
    }

    s = _session()
    url = f"{PUBLICATION_URL}/api/v1/drafts/{draft_id}"
    print(f"[tool-substack] PUT {url}")
    try:
        r = s.put(url, json=draft_payload, timeout=60)
    except requests.RequestException as e:
        print(f"[tool-substack] network error: {e}", file=sys.stderr)
        return 1
    if r.status_code >= 400:
        print(
            f"[tool-substack] draft update failed {r.status_code}: {r.text[:800]}",
            file=sys.stderr,
        )
        return 1
    print(f"[tool-substack] draft updated ✓  id={draft_id}")
    print(f"[tool-substack] edit:  {PUBLICATION_URL}/publish/post/{draft_id}")
    _write_ledger({
        "ts": datetime.datetime.utcnow().isoformat() + "Z",
        "action": "edit",
        "draft_id": draft_id,
        "file": str(path),
        "override": "--no-verify" if (no_verify and blocked) else "clean",
        "gate_summary": gate_summary or "no-citations",
        "md5": hashlib.md5(path.read_bytes()).hexdigest(),
    })
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(prog="substack_ops")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("test-auth")

    p_conv = sub.add_parser("convert")
    p_conv.add_argument("markdown")

    p_img = sub.add_parser("upload-image")
    p_img.add_argument("image")

    p_push = sub.add_parser("push")
    p_push.add_argument("markdown")
    p_push.add_argument(
        "--no-verify",
        action="store_true",
        default=False,
        help="Skip citation gate (bypass logged to ~/.scientific-os/substack-publish-ledger.jsonl)",
    )
    p_push.add_argument(
        "--no-footer",
        action="store_true",
        default=False,
        help="Omit the verification footer appended to the draft body (E2)",
    )

    p_list = sub.add_parser("list-drafts")
    p_list.add_argument("--limit", type=int, default=20)

    p_edit = sub.add_parser("edit")
    p_edit.add_argument("draft_id")
    p_edit.add_argument("markdown")
    p_edit.add_argument(
        "--no-verify",
        action="store_true",
        default=False,
        help="Skip citation gate (bypass logged to ~/.scientific-os/substack-publish-ledger.jsonl)",
    )
    p_edit.add_argument(
        "--no-footer",
        action="store_true",
        default=False,
        help="Omit the verification footer appended to the draft body (E2)",
    )

    args = parser.parse_args()

    if args.cmd == "test-auth":
        return cmd_test_auth()
    if args.cmd == "convert":
        return cmd_convert(args.markdown)
    if args.cmd == "upload-image":
        return cmd_upload_image(args.image)
    if args.cmd == "push":
        return cmd_push(args.markdown, no_verify=args.no_verify, no_footer=args.no_footer)
    if args.cmd == "list-drafts":
        return cmd_list_drafts(args.limit)
    if args.cmd == "edit":
        return cmd_edit(args.draft_id, args.markdown, no_verify=args.no_verify, no_footer=args.no_footer)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
