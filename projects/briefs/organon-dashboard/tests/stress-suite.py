"""End-to-end stress suite for the Organon Dashboard.

Hits every public API + every edge case I (Claude) could think of in one
pass. Run while the dev server is up:

    cd projects/briefs/organon-dashboard
    bash -lc 'set -a; source ../../../.env 2>/dev/null; set +a; npm run dev'
    # in another shell:
    python3 tests/stress-suite.py

The script emits a tab-aligned PASS / FAIL line per case, plus a final
summary. A failed case prints the response body for forensics. Tests that
need external compute (claude -p, FAL FLUX) are tagged [SKIP-EXTERNAL]
and not counted against the gate.

Idempotent: every artifact created during the run is cleaned up at the
end (manuscripts, sections, dataframes, figures, favourites).
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("DASHBOARD_BASE", "http://localhost:8769")
PROJECT = "__root__"
RESULTS = []   # (status, name, message)
CREATED_FILE_IDS = []
CREATED_MANUSCRIPTS = []
CREATED_HYP_IDS = []


def req(method, path, *, body=None, json_body=None, multipart=None, ok_codes=(200, 201)):
    headers = {}
    data = None
    if json_body is not None:
        data = json.dumps(json_body).encode()
        headers["Content-Type"] = "application/json"
    elif multipart is not None:
        boundary = f"----stress{uuid.uuid4().hex}"
        out = bytearray()
        for part in multipart:
            out += f"--{boundary}\r\n".encode()
            out += f'Content-Disposition: form-data; name="{part["name"]}"'.encode()
            if "filename" in part:
                out += f'; filename="{part["filename"]}"'.encode()
            out += b"\r\n"
            ct = part.get("content_type") or ("application/octet-stream" if isinstance(part["value"], (bytes, bytearray)) else "text/plain")
            out += f"Content-Type: {ct}\r\n\r\n".encode()
            v = part["value"]
            out += v if isinstance(v, (bytes, bytearray)) else v.encode()
            out += b"\r\n"
        out += f"--{boundary}--\r\n".encode()
        data = bytes(out)
        headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    elif body is not None:
        data = body if isinstance(body, (bytes, bytearray)) else body.encode()
    request = urllib.request.Request(f"{BASE}{path}", data=data, headers=headers, method=method)
    try:
        r = urllib.request.urlopen(request, timeout=30)
        status = r.status
        raw = r.read()
        try:
            return status, json.loads(raw)
        except json.JSONDecodeError:
            return status, raw
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}
    except urllib.error.URLError as e:
        return -1, {"error": str(e)}


def case(name, *, expect_status=None, predicate=None, skip=False):
    def decorator(func):
        if skip:
            RESULTS.append(("SKIP", name, "skipped by harness"))
            return func
        try:
            status, body = func()
            if expect_status is not None:
                status_ok = status in (expect_status if isinstance(expect_status, (list, tuple, set)) else (expect_status,))
            else:
                status_ok = True
            pred_ok = True
            pred_msg = ""
            if predicate is not None:
                pred_ok, pred_msg = predicate(status, body)
            if status_ok and pred_ok:
                RESULTS.append(("PASS", name, f"HTTP {status}"))
            else:
                RESULTS.append(("FAIL", name, f"HTTP {status} — {pred_msg or ''} body={str(body)[:200]}"))
        except Exception as exc:
            RESULTS.append(("FAIL", name, f"exception: {exc}"))
        return func
    return decorator


def section(label):
    print(f"\n=== {label} ===")


# ---------------------------------------------------------------------------
# Phase 1 — /lit
# ---------------------------------------------------------------------------
section("Phase 1 — /lit + library")

@case("GET /api/lit/library on __root__", expect_status=200)
def t():
    return req("GET", f"/api/lit/library?project={PROJECT}")

@case("GET /api/lit/library with unknown project (404)", expect_status=404)
def t():
    return req("GET", "/api/lit/library?project=does-not-exist")

@case("POST /api/lit/library with empty body (400)", expect_status=400)
def t():
    return req("POST", "/api/lit/library", body="")

@case("POST /api/lit/library missing paper.id (400)", expect_status=400)
def t():
    return req("POST", "/api/lit/library", json_body={"project": PROJECT, "paper": {"_artifact": "paper", "title": "x"}})

@case("POST /api/lit/library wrong _artifact discriminator (400)", expect_status=400)
def t():
    return req("POST", "/api/lit/library", json_body={
        "project": PROJECT,
        "paper": {"_artifact": "hypothesis", "id": "x", "title": "x"},
    })


# ---------------------------------------------------------------------------
# Phase 2 — /hypothesis
# ---------------------------------------------------------------------------
section("Phase 2 — /hypothesis + personas")

@case("GET /api/hypothesis on __root__", expect_status=200)
def t():
    return req("GET", f"/api/hypothesis?project={PROJECT}")

@case("POST /api/hypothesis with empty claim (400)", expect_status=400)
def t():
    return req("POST", "/api/hypothesis", json_body={"project": PROJECT, "claim": ""})

@case("POST /api/hypothesis with valid stub claim", expect_status=(200, 201))
def t():
    s, b = req("POST", "/api/hypothesis", json_body={
        "project": PROJECT,
        "claim": "Stress-test claim — created by tests/stress-suite.py",
        "paper_ids": [],
        "personas": [],
    })
    if isinstance(b, dict) and (hyp := b.get("hypothesis")):
        if "id" in hyp:
            CREATED_HYP_IDS.append(hyp["id"])
    return s, b

@case("GET /api/hypothesis/[id] for missing id (404)", expect_status=404)
def t():
    return req("GET", f"/api/hypothesis/hyp-9999-deadbeef?project={PROJECT}")

@case("GET /api/personas on __root__", expect_status=200)
def t():
    return req("GET", f"/api/personas?project={PROJECT}")

@case("PUT /api/personas with non-array body (400)", expect_status=400)
def t():
    return req("PUT", f"/api/personas?project={PROJECT}", json_body={"personas": "not-an-array"})


# ---------------------------------------------------------------------------
# Phase 3 — /data (upload, override, stat picker, plot)
# ---------------------------------------------------------------------------
section("Phase 3 — /data uploads + stat picker + plot")

# Build a few sample CSVs in memory.
SMALL_CSV = (
    b"id,age,treatment,outcome,recorded_at\n"
    b"1,54,control,0.42,2026-04-01T10:00:00\n"
    b"2,38,drug-a,0.81,2026-04-01T10:05:00\n"
    b"3,62,control,0.31,2026-04-02T11:00:00\n"
    b"4,29,drug-b,0.68,2026-04-02T11:30:00\n"
    b"5,45,drug-a,0.74,2026-04-03T09:15:00\n"
    b"6,71,control,,2026-04-03T09:45:00\n"
    b"7,33,drug-b,0.59,2026-04-04T08:30:00\n"
    b"8,50,drug-a,0.88,2026-04-04T08:45:00\n"
    b"9,42,control,0.40,2026-04-05T12:00:00\n"
    b"10,27,drug-b,0.65,2026-04-05T12:20:00\n"
    b"11,56,control,0.48,2026-04-06T08:00:00\n"
    b"12,29,drug-a,0.78,2026-04-06T08:30:00\n"
)
UNICODE_CSV = "x,y,note\n1,2,naïve café résumé\n3,4,日本語\n".encode()
UPLOAD_FILE_ID = None

@case("POST /api/data/load empty body (Phase 8 strict: 404 missing project)", expect_status=404)
def t():
    # Empty multipart body → no `project` field → resolveProjectFromRequest
    # returns null → 404. Pre-Phase 8 this fell through to __root__ + 400
    # invalid-body. Phase 8 strict mode surfaces missing-project as 404.
    return req("POST", "/api/data/load", body="")

@case("POST /api/data/load with .png extension (415)", expect_status=415)
def t():
    return req("POST", "/api/data/load", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "file", "filename": "fake.png", "value": b"\x89PNG\r\n\x1a\nfake", "content_type": "image/png"},
    ])

@case("POST /api/data/load with valid CSV", expect_status=201)
def t():
    s, b = req("POST", "/api/data/load", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "file", "filename": "stress-small.csv", "value": SMALL_CSV, "content_type": "text/csv"},
    ])
    global UPLOAD_FILE_ID
    if isinstance(b, dict) and "dataframe" in b:
        UPLOAD_FILE_ID = b["dataframe"]["id"]
        CREATED_FILE_IDS.append(UPLOAD_FILE_ID)
    return s, b

@case("POST /api/data/load with unicode-heavy CSV", expect_status=201)
def t():
    s, b = req("POST", "/api/data/load", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "file", "filename": "stress-unicode.csv", "value": UNICODE_CSV, "content_type": "text/csv"},
    ])
    if isinstance(b, dict) and "dataframe" in b:
        CREATED_FILE_IDS.append(b["dataframe"]["id"])
    return s, b

@case("POST /api/data/preview override age → categorical", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and any(c.get("name") == "age" and c.get("type") == "categorical" for c in (b.get("dataframe") or {}).get("columns", [])),
          "age column should now be categorical",
      ))
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", f"/api/data/preview/{UPLOAD_FILE_ID}?project={PROJECT}",
               json_body={"column_overrides": {"age": "categorical"}})

@case("POST /api/data/preview restore age → numeric", expect_status=200)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", f"/api/data/preview/{UPLOAD_FILE_ID}?project={PROJECT}",
               json_body={"column_overrides": {"age": "numeric"}})

@case("POST /api/data/preview missing file_id (404)", expect_status=404)
def t():
    return req("POST", f"/api/data/preview/data-9999-deadbe?project={PROJECT}", json_body={})

@case("POST /api/stat-picker group mode → 2 recommendations", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and len(b.get("recommendations") or []) >= 2,
          "expected ≥ 2 ranked recommendations",
      ))
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/stat-picker", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID,
        "answers": {"mode": "group", "value_col": "outcome", "group_col": "treatment", "paired": False},
    })

@case("POST /api/stat-picker correlation mode", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and any(r.get("test_name") == "pearson" for r in b.get("recommendations") or []),
          "expected pearson recommendation",
      ))
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/stat-picker", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID,
        "answers": {"mode": "correlation", "x_col": "age", "y_col": "outcome"},
    })

@case("POST /api/stat-picker group with text col (400)", expect_status=400)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/stat-picker", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID,
        "answers": {"mode": "group", "value_col": "treatment", "group_col": "outcome", "paired": False},
    })

@case("POST /api/stat-picker power without n or target (400)", expect_status=400)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/stat-picker", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID,
        "answers": {"mode": "power", "test_kind": "t-test", "effect_size": 0.5, "alpha": 0.05},
    })

@case("POST /api/data/plot histogram", expect_status=201,
      predicate=lambda s, b: (
          isinstance(b, dict) and (b.get("figure") or {}).get("backend") == "matplotlib",
          "expected matplotlib backend",
      ))
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/data/plot", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID, "kind": "histogram",
        "params": {"x_col": "age", "bins": 8},
    })

@case("POST /api/data/plot invalid kind (400)", expect_status=400)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/data/plot", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID, "kind": "spaceship",
        "params": {},
    })

@case("POST /api/data/plot scatter missing y_col (400)", expect_status=400)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/data/plot", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID, "kind": "scatter",
        "params": {"x_col": "age"},
    })

@case("POST /api/data/plot heatmap (no required cols)", expect_status=201)
def t():
    if UPLOAD_FILE_ID is None: return -1, {}
    return req("POST", "/api/data/plot", json_body={
        "project": PROJECT, "file_id": UPLOAD_FILE_ID, "kind": "heatmap", "params": {},
    })

@case("GET /api/data/figures (after 2 plots)", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and (b.get("total") or 0) >= 2,
          "expected ≥ 2 figures",
      ))
def t():
    return req("GET", f"/api/data/figures?project={PROJECT}")


# ---------------------------------------------------------------------------
# Phase 4 — /figures (no FAL roundtrip — needs key)
# ---------------------------------------------------------------------------
section("Phase 4 — /figures + mask validation")

@case("POST /api/images/edit empty body (Phase 8 strict: 404 missing project)", expect_status=404)
def t():
    # Same shape as data/load empty: no `project` field → null → 404.
    return req("POST", "/api/images/edit", body="")

@case("POST /api/images/edit missing fig_id (400)", expect_status=400)
def t():
    return req("POST", "/api/images/edit", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "prompt", "value": "test"},
    ])

@case("POST /api/images/edit unknown fig_id (404)", expect_status=404)
def t():
    return req("POST", "/api/images/edit", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "fig_id", "value": "fig-fake-deadbeef"},
        {"name": "prompt", "value": "test"},
        {"name": "mask", "filename": "mask.png", "value": b"\x89PNG\r\n\x1a\n", "content_type": "image/png"},
    ])

@case("GET /api/images/missing-fig (404)", expect_status=404)
def t():
    return req("GET", f"/api/images/fig-fake-deadbeef?project={PROJECT}")

@case("GET /api/figures/[fig]/[file] path traversal blocked (400)", expect_status=400)
def t():
    return req("GET", f"/api/figures/fig-x/..%2F..%2Fetc%2Fpasswd?project={PROJECT}")


# ---------------------------------------------------------------------------
# Phase 5 — /draft (manuscripts, sections, export)
# ---------------------------------------------------------------------------
section("Phase 5 — /draft + manuscripts + sections")

MS_SLUG = None

@case("POST /api/draft/new empty title (400)", expect_status=400)
def t():
    return req("POST", "/api/draft/new", json_body={"project": PROJECT, "title": ""})

@case("POST /api/draft/new with valid title", expect_status=201)
def t():
    s, b = req("POST", "/api/draft/new", json_body={
        "project": PROJECT, "title": "Stress Test Manuscript", "citation_style": "apa",
    })
    global MS_SLUG
    if isinstance(b, dict) and "manuscript" in b:
        MS_SLUG = b["manuscript"]["slug"]
        CREATED_MANUSCRIPTS.append(MS_SLUG)
    return s, b

@case("POST /api/draft/new with same title (slug suffix)", expect_status=201,
      predicate=lambda s, b: (
          isinstance(b, dict) and (b.get("manuscript") or {}).get("slug", "").endswith("-2"),
          "expected slug to get -2 suffix",
      ))
def t():
    s, b = req("POST", "/api/draft/new", json_body={
        "project": PROJECT, "title": "Stress Test Manuscript", "citation_style": "ieee",
    })
    if isinstance(b, dict) and "manuscript" in b:
        CREATED_MANUSCRIPTS.append(b["manuscript"]["slug"])
    return s, b

@case("PATCH /api/draft/[slug]/sections/introduction with content_md", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and "pmid-37889012" in (b.get("section") or {}).get("linked_paper_ids", []),
          "linked_paper_ids should auto-extract pmid-37889012",
      ))
def t():
    if MS_SLUG is None: return -1, {}
    md = "## Introduction\n\nGLP-1 receptor agonists are widely used. See \\cite{pmid-37889012} and \\fig{fig-fake}.\n"
    return req("PATCH", f"/api/draft/{MS_SLUG}/sections/introduction?project={PROJECT}",
               json_body={"content_md": md})

@case("POST /api/draft/[slug]/sections duplicate id (409)", expect_status=409)
def t():
    if MS_SLUG is None: return -1, {}
    return req("POST", f"/api/draft/{MS_SLUG}/sections", json_body={
        "project": PROJECT, "section_id": "introduction",
    })

@case("PATCH /api/draft/[slug] reorder", expect_status=200)
def t():
    if MS_SLUG is None: return -1, {}
    return req("PATCH", f"/api/draft/{MS_SLUG}?project={PROJECT}", json_body={
        "ordering": ["title", "abstract", "results", "introduction", "methods", "discussion", "references"],
    })

@case("POST /api/draft/[slug]/export markdown (force=true to bypass Phase 5 422)", expect_status=201)
def t():
    if MS_SLUG is None: return -1, {}
    # Section content carries `\cite{pmid-37889012}` + `\fig{fig-fake}` which
    # don't resolve against the (empty) test library. Phase 5's 422-on-
    # unresolved would refuse the export. Pass force=true to bypass — exactly
    # the escape valve documented in PHASE_FIXSPRINT_05_PLAN.md and the
    # "Architecture invariants" contract in NEXT_SESSION_2026-05-06c.md §5.
    return req("POST", f"/api/draft/{MS_SLUG}/export?project={PROJECT}",
               json_body={"project": PROJECT, "format": "markdown", "force": True})

@case("POST /api/draft/[slug]/export substack (501 stub, force=true)", expect_status=501)
def t():
    if MS_SLUG is None: return -1, {}
    return req("POST", f"/api/draft/{MS_SLUG}/export?project={PROJECT}",
               json_body={"project": PROJECT, "format": "substack", "force": True})

@case("POST /api/draft/[slug]/action invalid action (400)", expect_status=400)
def t():
    if MS_SLUG is None: return -1, {}
    return req("POST", f"/api/draft/{MS_SLUG}/action?project={PROJECT}",
               json_body={"project": PROJECT, "section_id": "introduction", "action": "delete"})


# ---------------------------------------------------------------------------
# Phase 6 — /tools, /crons, /runs, /search
# ---------------------------------------------------------------------------
section("Phase 6 — /tools + /crons + /runs + cmdk search")

@case("GET /api/tools/catalog has ≥ 30 entries", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and (b.get("total") or 0) >= 30,
          f"expected ≥ 30 tools, got {(b.get('total') or 0)}",
      ))
def t():
    return req("GET", "/api/tools/catalog")

@case("GET /api/crons returns jobs", expect_status=200)
def t():
    return req("GET", "/api/crons")

@case("POST /api/tools/run with mcp:* tool (501 hint)", expect_status=501)
def t():
    return req("POST", "/api/tools/run", json_body={
        "project": PROJECT, "tool_id": "mcp:paperclip", "prompt": "test",
    })

@case("POST /api/tools/run empty prompt (400)", expect_status=400)
def t():
    return req("POST", "/api/tools/run", json_body={"project": PROJECT, "tool_id": "sci-data-analysis", "prompt": ""})

@case("PUT /api/tools/favourites with non-array (200, defaults to [])", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and b.get("favourites") == [],
          "non-array body should fall back to empty array",
      ))
def t():
    return req("PUT", f"/api/tools/favourites?project={PROJECT}", json_body={"favourites": "not-an-array"})

@case("GET /api/runs unknown run id (404)", expect_status=404)
def t():
    return req("GET", f"/api/runs/2099-01-01T00-00-00-000Z?project={PROJECT}")

@case("GET /api/search empty q returns 0 results", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and b.get("results") == [],
          "empty q should return zero hits",
      ))
def t():
    return req("GET", f"/api/search?project={PROJECT}&q=&limit=5")

@case("GET /api/search invalid type filter ignored", expect_status=200)
def t():
    return req("GET", f"/api/search?project={PROJECT}&q=stress&types=spaceship,paper&limit=5")


# ---------------------------------------------------------------------------
# Cross-feature
# ---------------------------------------------------------------------------
section("Cross-feature flows")

@case("Search finds the manuscript we just created", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and any(h.get("type") == "manuscript" and "stress" in h.get("title", "").lower()
                                       for h in b.get("results") or []),
          "expected stress-test manuscript in search results",
      ))
def t():
    return req("GET", f"/api/search?project={PROJECT}&q=stress&types=manuscript,section&limit=5")

@case("Search finds the section we just edited", expect_status=200,
      predicate=lambda s, b: (
          isinstance(b, dict) and any(h.get("type") == "section" and "introduction" in h.get("id", "")
                                       for h in b.get("results") or []),
          "expected introduction section in search results",
      ))
def t():
    return req("GET", f"/api/search?project={PROJECT}&q=GLP-1&types=section&limit=5")

@case("Concurrent uploads of the same CSV land 2 distinct file_ids", expect_status=None,
      predicate=lambda s, b: (
          isinstance(b, dict) and b.get("count", 0) == 2 and len(set(b.get("ids", []))) == 2,
          f"expected 2 distinct ids, got {b}",
      ))
def t():
    csv1 = SMALL_CSV
    csv2 = SMALL_CSV + b"13,99,control,0.50,2026-04-07T08:00:00\n"  # different bytes → different file_id
    s1, b1 = req("POST", "/api/data/load", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "file", "filename": "concurrent-1.csv", "value": csv1, "content_type": "text/csv"},
    ])
    s2, b2 = req("POST", "/api/data/load", multipart=[
        {"name": "project", "value": PROJECT},
        {"name": "file", "filename": "concurrent-2.csv", "value": csv2, "content_type": "text/csv"},
    ])
    ids = []
    if isinstance(b1, dict) and "dataframe" in b1:
        ids.append(b1["dataframe"]["id"]); CREATED_FILE_IDS.append(b1["dataframe"]["id"])
    if isinstance(b2, dict) and "dataframe" in b2:
        ids.append(b2["dataframe"]["id"]); CREATED_FILE_IDS.append(b2["dataframe"]["id"])
    return 200, {"count": len(ids), "ids": ids}


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
section("Cleanup")

for fid in CREATED_FILE_IDS:
    s, _ = req("DELETE", f"/api/data/preview/{fid}?project={PROJECT}")
    print(f"  deleted file {fid} → HTTP {s}")
for hid in CREATED_HYP_IDS:
    s, _ = req("DELETE", f"/api/hypothesis/{hid}?project={PROJECT}")
    print(f"  deleted hypothesis {hid} → HTTP {s}")

# Manuscripts: best-effort cleanup via filesystem since there's no DELETE endpoint.
# (Phase 5 didn't expose DELETE /api/draft/[slug] — surfaced as a known gap below.)

# Wipe figures + manuscripts at repo root left from synthetic project.
# parents[0] = tests/, [1] = organon-dashboard/, [2] = briefs/, [3] = projects/,
# [4] = organon root.
import shutil
for stray in [".organon-dashboard", "figures", "results", "manuscripts"]:
    p = Path(__file__).resolve().parents[4] / stray
    if p.exists() and p.is_dir():
        try:
            shutil.rmtree(p)
            print(f"  removed stray {p}")
        except Exception as exc:
            print(f"  could not remove {p}: {exc}")
# data/ at repo root may contain pre-existing user files (e.g.
# tooluniverse-catalog.json); only remove the data-* prefix files we
# created during the test.
data_dir = Path(__file__).resolve().parents[4] / "data"
if data_dir.exists():
    for f in data_dir.glob("data-*"):
        try:
            f.unlink()
            print(f"  removed stray {f}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
passes = sum(1 for r in RESULTS if r[0] == "PASS")
fails  = sum(1 for r in RESULTS if r[0] == "FAIL")
skips  = sum(1 for r in RESULTS if r[0] == "SKIP")
print(f"PASS: {passes}    FAIL: {fails}    SKIP: {skips}    TOTAL: {len(RESULTS)}")
print()
for status, name, msg in RESULTS:
    icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "·"}[status]
    line = f"  {icon} {name}"
    if status == "FAIL":
        line += f"\n      └─ {msg}"
    elif status == "SKIP":
        line += f" — {msg}"
    print(line)

sys.exit(1 if fails > 0 else 0)
