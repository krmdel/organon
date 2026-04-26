"""Tests for the citation verification module."""

import io
import json
from unittest.mock import patch, MagicMock

import pytest

# Opt out of the conftest verify_citation stub: this file exercises the
# real `repro.citation_verify` module with its own HTTP-layer mocks.
pytestmark = pytest.mark.real_citation_verify

# Mock CrossRef response fixtures
MOCK_NORMAL_RESPONSE = {
    "status": "ok",
    "message": {
        "DOI": "10.1038/s41586-024-00001-0",
        "title": ["A groundbreaking discovery"],
        "author": [{"family": "Smith", "given": "John"}],
        "published-print": {"date-parts": [[2024, 3, 15]]},
        "container-title": ["Nature"],
        "type": "journal-article",
    },
}

MOCK_RETRACTED_RESPONSE = {
    "status": "ok",
    "message": {
        "DOI": "10.1234/retracted.2024",
        "title": ["A retracted paper"],
        "author": [{"family": "Doe", "given": "Jane"}],
        "published-print": {"date-parts": [[2023, 1, 1]]},
        "container-title": ["Journal X"],
        "type": "journal-article",
        "update-to": [
            {"type": "retraction", "DOI": "10.1234/retraction-notice"}
        ],
    },
}


def _mock_urlopen(response_data):
    """Create a mock urlopen context manager that returns JSON response."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(response_data).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return mock_response


def test_verify_doi_returns_required_keys():
    """Test 1: verify_doi returns dict with all required keys."""
    from repro.citation_verify import verify_doi

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MOCK_NORMAL_RESPONSE)):
        result = verify_doi("10.1038/s41586-024-00001-0")

    assert "doi" in result
    assert "title" in result
    assert "authors" in result
    assert "published" in result
    assert "journal" in result
    assert "is_retracted" in result
    assert "type" in result
    assert result["title"] == "A groundbreaking discovery"
    assert result["authors"] == ["Smith"]
    assert result["journal"] == "Nature"


def test_verify_doi_detects_retraction():
    """Test 2: verify_doi returns is_retracted=True when update-to contains retraction."""
    from repro.citation_verify import verify_doi

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MOCK_RETRACTED_RESPONSE)):
        result = verify_doi("10.1234/retracted.2024")

    assert result["is_retracted"] is True
    assert result["retraction_info"] is not None
    assert result["retraction_info"]["type"] == "retraction"


def test_verify_doi_normal_paper_not_retracted():
    """Test 3: verify_doi returns is_retracted=False for a normal paper."""
    from repro.citation_verify import verify_doi

    with patch("urllib.request.urlopen", return_value=_mock_urlopen(MOCK_NORMAL_RESPONSE)):
        result = verify_doi("10.1038/s41586-024-00001-0")

    assert result["is_retracted"] is False
    assert result["retraction_info"] is None


def test_verify_doi_raises_value_error_on_404():
    """Test 4: verify_doi raises ValueError for 404 response."""
    import urllib.error
    from repro.citation_verify import verify_doi

    mock_error = urllib.error.HTTPError(
        url="https://api.crossref.org/works/10.1234/nonexistent",
        code=404,
        msg="Not Found",
        hdrs={},
        fp=io.BytesIO(b""),
    )

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(ValueError, match="DOI not found"):
            verify_doi("10.1234/nonexistent")


def test_verify_doi_raises_connection_error_on_network_failure():
    """Test 5: verify_doi raises ConnectionError for network failure."""
    import urllib.error
    from repro.citation_verify import verify_doi

    mock_error = urllib.error.URLError("Name or service not known")

    with patch("urllib.request.urlopen", side_effect=mock_error):
        with pytest.raises(ConnectionError, match="Could not reach CrossRef"):
            verify_doi("10.1038/s41586-024-00001-0")


def test_batch_verify_continues_past_failures():
    """Test 6: batch_verify returns results for all DOIs, continuing past failures."""
    import urllib.error
    from repro.citation_verify import batch_verify

    call_count = 0

    def mock_urlopen_mixed(request, *args, **kwargs):
        # *args/**kwargs absorb the `timeout=` kwarg verify_doi now
        # forwards (added in M9).
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise urllib.error.HTTPError(
                url="", code=404, msg="Not Found", hdrs={}, fp=io.BytesIO(b"")
            )
        return _mock_urlopen(MOCK_NORMAL_RESPONSE)

    with patch("urllib.request.urlopen", side_effect=mock_urlopen_mixed):
        results = batch_verify([
            "10.1038/s41586-024-00001-0",
            "10.1234/nonexistent",
            "10.1038/s41586-024-00002-0",
        ])

    assert len(results) == 3
    assert results[0]["title"] == "A groundbreaking discovery"
    assert "error" in results[1]
    assert results[1]["is_retracted"] is None
    assert results[2]["title"] == "A groundbreaking discovery"
