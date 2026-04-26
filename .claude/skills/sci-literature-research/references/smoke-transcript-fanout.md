# sci-literature-research — parallel fan-out smoke transcript

Minimal end-to-end demo of the new `parallel_fanout` API added in F.4.C. Does NOT require the live paper-search MCP server; backends are plain callables so unit-test-style stubs stand in for PubMed / arXiv / OpenAlex / Semantic Scholar.

## Invocation

```python
import sys
sys.path.insert(0, ".claude/skills/sci-literature-research/scripts")
from fanout import parallel_fanout, FanoutAllFailedError

def fake_pubmed(query):
    return [
        {"doi": "10.1/a", "title": "Paper A", "year": 2024, "authors": ["Smith"]},
        {"doi": "10.1/b", "title": "Paper B", "year": 2024, "authors": ["Jones"]},
    ]

def fake_arxiv(query):
    return [
        {"arxiv_id": "2401.00001", "title": "Preprint X", "year": 2024, "authors": ["Lee"]},
        {"doi": "10.1/a", "title": "Paper A (arXiv mirror)", "year": 2024, "authors": ["Smith"]},  # dedupe-target
    ]

def flaky_openalex(query):
    import time; time.sleep(5); return []  # will time out

def fast_s2(query):
    return [{"doi": "10.2/s2", "title": "S2 result", "year": 2025, "authors": ["Ng"]}]

result = parallel_fanout(
    query="autoconvolution inequality",
    backends={
        "pubmed": fake_pubmed,
        "arxiv": fake_arxiv,
        "openalex": flaky_openalex,
        "semantic_scholar": fast_s2,
    },
    timeout_per_source=0.5,
    max_results_per_source=50,
)

print(f"degraded = {result['degraded']}")
print(f"failed_sources = {result['failed_sources']}")
print(f"result_count = {len(result['results'])}")
print(f"source_counts = {result['source_counts']}")
```

## Expected output

```
degraded = True
failed_sources = ['openalex']
result_count = 4            # Paper A, Paper B, Preprint X, S2 result (deduped)
source_counts = {'pubmed': 2, 'arxiv': 2, 'openalex': 0, 'semantic_scholar': 1}
```

Invariants the smoke test confirms:

- `degraded` flips to `True` when any backend times out or raises.
- `failed_sources` lists the offending backend by name.
- Dedup collapses Paper A to a single entry despite appearing in both `pubmed` and `arxiv`.
- Total wall time is bounded by `timeout_per_source + max(per_source_time)`, NOT by `sum` — parallelism is real.

## Related tests

- `tests/test_fanout.py::test_fanout_fires_all_n_tracks_in_parallel`
- `tests/test_fanout.py::test_graceful_degradation_on_one_source_failure`
- `tests/test_fanout.py::test_deduplication_by_doi`
- `tests/test_fanout.py::test_all_source_failure_raises_fanout_all_failed_error`
