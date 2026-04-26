"""Tests for sci-trending-research backend (last30days lib/).

Covers pure logic functions (dates, dedupe, score, schema, normalize) and
mocked search functions (search_reddit, search_x via mock_response parameter).
No real HTTP calls or API keys required.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent / ".claude" / "skills" / "sci-trending-research" / "scripts")
sys.path.insert(0, SCRIPTS_DIR)
# Note: Do NOT add LIB_DIR directly to sys.path — it conflicts with stdlib 'http' module.
# Import via 'lib.' prefix from SCRIPTS_DIR.

from lib import dates, dedupe, score, schema, normalize
from lib.openai_reddit import _extract_core_subject, parse_reddit_response, search_reddit
from lib.xai_x import parse_x_response, search_x
from lib.env import get_config, get_available_sources, get_missing_keys


# ---------------------------------------------------------------------------
# TestDates
# ---------------------------------------------------------------------------

class TestDates:
    def test_get_date_range_returns_strings(self):
        from_date, to_date = dates.get_date_range(30)
        assert isinstance(from_date, str)
        assert isinstance(to_date, str)
        assert len(from_date) == 10  # YYYY-MM-DD
        assert len(to_date) == 10

    def test_get_date_range_from_before_to(self):
        from_date, to_date = dates.get_date_range(30)
        assert from_date < to_date

    def test_get_date_range_custom_days(self):
        from_7, to_7 = dates.get_date_range(7)
        from_30, to_30 = dates.get_date_range(30)
        assert from_7 > from_30  # 7-day window starts more recently

    def test_parse_date_iso_format(self):
        dt = dates.parse_date("2024-01-15")
        assert dt is not None
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_date_iso_with_time(self):
        dt = dates.parse_date("2024-01-15T12:30:00")
        assert dt is not None
        assert dt.year == 2024

    def test_parse_date_none_input(self):
        result = dates.parse_date(None)
        assert result is None

    def test_parse_date_empty_string(self):
        result = dates.parse_date("")
        assert result is None

    def test_parse_date_unix_timestamp(self):
        # 2024-01-15 in epoch
        ts = "1705276800"
        dt = dates.parse_date(ts)
        assert dt is not None
        assert dt.year == 2024

    def test_timestamp_to_date_valid(self):
        result = dates.timestamp_to_date(1705276800)
        assert result is not None
        assert len(result) == 10
        assert result.startswith("2024")

    def test_timestamp_to_date_none(self):
        result = dates.timestamp_to_date(None)
        assert result is None

    def test_get_date_confidence_in_range(self):
        conf = dates.get_date_confidence("2024-06-15", "2024-06-01", "2024-06-30")
        assert conf == "high"

    def test_get_date_confidence_out_of_range(self):
        conf = dates.get_date_confidence("2023-01-01", "2024-06-01", "2024-06-30")
        assert conf == "low"

    def test_get_date_confidence_none(self):
        conf = dates.get_date_confidence(None, "2024-06-01", "2024-06-30")
        assert conf == "low"


# ---------------------------------------------------------------------------
# TestDedupe
# ---------------------------------------------------------------------------

class TestDedupe:
    def test_normalize_text_lowercases(self):
        result = dedupe.normalize_text("Hello World")
        assert result == "hello world"

    def test_normalize_text_strips_punctuation(self):
        result = dedupe.normalize_text("Hello, World!")
        assert "," not in result
        assert "!" not in result

    def test_normalize_text_collapses_whitespace(self):
        result = dedupe.normalize_text("hello   world")
        assert "  " not in result
        assert result == "hello world"

    def test_get_ngrams_produces_set(self):
        result = dedupe.get_ngrams("hello", n=3)
        assert isinstance(result, set)
        assert len(result) > 0

    def test_get_ngrams_correct_size(self):
        text = "abcde"
        result = dedupe.get_ngrams(text, n=3)
        # Expected: "abc", "bcd", "cde"
        assert "abc" in result
        assert "bcd" in result
        assert "cde" in result

    def test_jaccard_similarity_identical(self):
        s = {"a", "b", "c"}
        result = dedupe.jaccard_similarity(s, s)
        assert result == 1.0

    def test_jaccard_similarity_disjoint(self):
        s1 = {"a", "b"}
        s2 = {"c", "d"}
        result = dedupe.jaccard_similarity(s1, s2)
        assert result == 0.0

    def test_jaccard_similarity_partial(self):
        s1 = {"a", "b", "c"}
        s2 = {"b", "c", "d"}
        result = dedupe.jaccard_similarity(s1, s2)
        # intersection=2, union=4 → 0.5
        assert 0.0 < result < 1.0

    def test_jaccard_similarity_empty(self):
        result = dedupe.jaccard_similarity(set(), {"a", "b"})
        assert result == 0.0

    def test_dedupe_removes_near_duplicates(self):
        # Create two nearly identical items
        item1 = schema.RedditItem(
            id="R1", title="Machine learning in healthcare applications",
            url="https://reddit.com/r/ML/1", subreddit="ML", score=100,
        )
        item2 = schema.RedditItem(
            id="R2", title="Machine learning in healthcare applications today",
            url="https://reddit.com/r/ML/2", subreddit="ML", score=50,
        )
        item3 = schema.RedditItem(
            id="R3", title="Totally different topic about cooking",
            url="https://reddit.com/r/food/3", subreddit="food", score=80,
        )
        result = dedupe.dedupe_items([item1, item2, item3], threshold=0.6)
        # item1 and item2 are near-duplicates; item1 wins (higher score)
        # item3 is unique
        assert len(result) < 3
        ids = [r.id for r in result]
        assert "R1" in ids  # Higher score survives
        assert "R3" in ids  # Unique item survives

    def test_dedupe_single_item_unchanged(self):
        item = schema.RedditItem(
            id="R1", title="Test", url="https://reddit.com/1", subreddit="test",
        )
        result = dedupe.dedupe_items([item])
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestScore
# ---------------------------------------------------------------------------

class TestScore:
    def test_log1p_safe_positive(self):
        import math
        result = score.log1p_safe(10)
        assert abs(result - math.log1p(10)) < 1e-9

    def test_log1p_safe_zero(self):
        result = score.log1p_safe(0)
        assert result == 0.0

    def test_log1p_safe_negative(self):
        result = score.log1p_safe(-5)
        assert result == 0.0

    def test_log1p_safe_none(self):
        result = score.log1p_safe(None)
        assert result == 0.0

    def test_compute_reddit_engagement_raw_with_data(self):
        eng = schema.Engagement(score=1000, num_comments=50, upvote_ratio=0.95)
        result = score.compute_reddit_engagement_raw(eng)
        assert result is not None
        assert result > 0

    def test_compute_reddit_engagement_raw_none(self):
        result = score.compute_reddit_engagement_raw(None)
        assert result is None

    def test_compute_reddit_engagement_raw_empty(self):
        eng = schema.Engagement()  # All None
        result = score.compute_reddit_engagement_raw(eng)
        assert result is None

    def test_compute_x_engagement_raw_with_data(self):
        eng = schema.Engagement(likes=500, reposts=100, replies=30, quotes=10)
        result = score.compute_x_engagement_raw(eng)
        assert result is not None
        assert result > 0

    def test_compute_x_engagement_raw_none(self):
        result = score.compute_x_engagement_raw(None)
        assert result is None

    def test_compute_x_engagement_raw_empty(self):
        eng = schema.Engagement()
        result = score.compute_x_engagement_raw(eng)
        assert result is None

    @pytest.mark.parametrize("upvotes,comments,ratio", [
        (100, 20, 0.8),
        (5000, 200, 0.95),
        (0, 0, 0.5),
    ])
    def test_reddit_engagement_parametrized(self, upvotes, comments, ratio):
        eng = schema.Engagement(score=upvotes, num_comments=comments, upvote_ratio=ratio)
        result = score.compute_reddit_engagement_raw(eng)
        if upvotes == 0 and comments == 0:
            # Both zero, still a valid float (0.0 contributions from log1p(0))
            assert result is not None
        else:
            assert result is not None and result >= 0


# ---------------------------------------------------------------------------
# TestSchema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_reddit_item_creation(self):
        item = schema.RedditItem(
            id="R1", title="Test post", url="https://reddit.com/r/test/1",
            subreddit="test",
        )
        assert item.id == "R1"
        assert item.title == "Test post"
        assert item.relevance == 0.5  # default
        assert item.score == 0  # default

    def test_x_item_creation(self):
        item = schema.XItem(
            id="X1", text="A tweet about science", url="https://x.com/user/1",
            author_handle="scientist",
        )
        assert item.id == "X1"
        assert item.text == "A tweet about science"
        assert item.author_handle == "scientist"

    def test_reddit_item_to_dict(self):
        item = schema.RedditItem(
            id="R1", title="Test", url="https://reddit.com/r/test/1",
            subreddit="test",
        )
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "R1"
        assert d["title"] == "Test"
        assert "subreddit" in d
        assert "score" in d

    def test_x_item_to_dict(self):
        item = schema.XItem(
            id="X1", text="Tweet", url="https://x.com/u/1", author_handle="user",
        )
        d = item.to_dict()
        assert isinstance(d, dict)
        assert d["id"] == "X1"
        assert d["author_handle"] == "user"

    def test_report_creation(self):
        report = schema.Report(
            topic="machine learning", range_from="2024-01-01", range_to="2024-01-31",
            generated_at="2024-01-31T12:00:00Z", mode="auto",
        )
        assert report.topic == "machine learning"
        assert report.mode == "auto"
        assert report.reddit == []
        assert report.x == []

    def test_report_to_dict(self):
        report = schema.Report(
            topic="AI", range_from="2024-01-01", range_to="2024-01-31",
            generated_at="2024-01-31T12:00:00Z", mode="auto",
        )
        d = report.to_dict()
        assert isinstance(d, dict)
        assert d["topic"] == "AI"
        assert "range" in d
        assert d["range"]["from"] == "2024-01-01"

    def test_report_from_dict_round_trip(self):
        report = schema.Report(
            topic="genomics", range_from="2024-01-01", range_to="2024-01-31",
            generated_at="2024-01-31T12:00:00Z", mode="both",
        )
        d = report.to_dict()
        restored = schema.Report.from_dict(d)
        assert restored.topic == report.topic
        assert restored.range_from == report.range_from
        assert restored.mode == report.mode

    def test_engagement_to_dict(self):
        eng = schema.Engagement(score=100, num_comments=10, upvote_ratio=0.9)
        d = eng.to_dict()
        assert d["score"] == 100
        assert d["num_comments"] == 10

    def test_sub_scores_to_dict(self):
        subs = schema.SubScores(relevance=80, recency=60, engagement=70)
        d = subs.to_dict()
        assert d["relevance"] == 80
        assert d["recency"] == 60
        assert d["engagement"] == 70


# ---------------------------------------------------------------------------
# TestNormalize
# ---------------------------------------------------------------------------

class TestNormalize:
    def _make_reddit_item(self, date=None, score=50):
        return schema.RedditItem(
            id="R1", title="Test", url="https://reddit.com/r/test/1",
            subreddit="test", date=date, score=score,
        )

    def _make_x_item(self, date=None, score=50):
        return schema.XItem(
            id="X1", text="Test tweet", url="https://x.com/u/1",
            author_handle="user", date=date, score=score,
        )

    def test_filter_by_date_range_keeps_in_range(self):
        items = [self._make_reddit_item(date="2024-06-15")]
        result = normalize.filter_by_date_range(items, "2024-06-01", "2024-06-30")
        assert len(result) == 1

    def test_filter_by_date_range_removes_old(self):
        items = [self._make_reddit_item(date="2023-01-01")]
        result = normalize.filter_by_date_range(items, "2024-06-01", "2024-06-30")
        assert len(result) == 0

    def test_filter_by_date_range_keeps_no_date_by_default(self):
        items = [self._make_reddit_item(date=None)]
        result = normalize.filter_by_date_range(items, "2024-06-01", "2024-06-30")
        assert len(result) == 1

    def test_filter_by_date_range_removes_no_date_when_required(self):
        items = [self._make_reddit_item(date=None)]
        result = normalize.filter_by_date_range(items, "2024-06-01", "2024-06-30", require_date=True)
        assert len(result) == 0

    def test_normalize_reddit_items_basic(self):
        raw = [
            {
                "id": "abc123",
                "title": "Cool thread about genomics",
                "url": "https://reddit.com/r/genomics/comments/abc123/cool_thread/",
                "subreddit": "genomics",
                "date": "2024-06-15",
                "relevance": 0.9,
                "why_relevant": "Discusses CRISPR techniques",
                "engagement": {"score": 500, "num_comments": 30, "upvote_ratio": 0.88},
            }
        ]
        result = normalize.normalize_reddit_items(raw, "2024-06-01", "2024-06-30")
        assert len(result) == 1
        assert isinstance(result[0], schema.RedditItem)
        assert result[0].title == "Cool thread about genomics"
        assert result[0].relevance == 0.9
        assert result[0].engagement is not None
        assert result[0].engagement.score == 500

    def test_normalize_reddit_items_empty(self):
        result = normalize.normalize_reddit_items([], "2024-06-01", "2024-06-30")
        assert result == []

    def test_normalize_reddit_items_missing_optional_fields(self):
        raw = [{"id": "x", "title": "Minimal", "url": "https://reddit.com/1", "subreddit": "sub"}]
        result = normalize.normalize_reddit_items(raw, "2024-06-01", "2024-06-30")
        assert len(result) == 1
        assert result[0].relevance == 0.5  # Default
        assert result[0].engagement is None


# ---------------------------------------------------------------------------
# TestSearchReddit
# ---------------------------------------------------------------------------

class TestSearchReddit:
    def _make_mock_response(self):
        """Create a canned OpenAI Responses API response structure."""
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({
                                "items": [
                                    {
                                        "title": "CRISPR advancements in 2024",
                                        "url": "https://www.reddit.com/r/science/comments/abc123/crispr/",
                                        "subreddit": "science",
                                        "date": "2024-06-15",
                                        "why_relevant": "Discusses CRISPR gene editing",
                                        "relevance": 0.9,
                                    }
                                ]
                            })
                        }
                    ]
                }
            ]
        }

    def test_search_reddit_with_mock_response(self):
        """search_reddit with mock_response bypasses HTTP — should return the mock dict."""
        mock = self._make_mock_response()
        result = search_reddit(
            api_key="fake_key", model="gpt-4o",
            topic="CRISPR", from_date="2024-06-01", to_date="2024-06-30",
            mock_response=mock,
        )
        assert result is mock

    def test_parse_reddit_response_extracts_items(self):
        mock = self._make_mock_response()
        items = parse_reddit_response(mock)
        assert isinstance(items, list)
        assert len(items) == 1
        assert items[0]["title"] == "CRISPR advancements in 2024"
        assert "reddit.com" in items[0]["url"]

    def test_parse_reddit_response_empty_output(self):
        items = parse_reddit_response({})
        assert items == []

    def test_parse_reddit_response_error_field(self):
        items = parse_reddit_response({"error": {"message": "Rate limit exceeded"}})
        assert items == []

    def test_parse_reddit_response_filters_non_reddit_urls(self):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({
                                "items": [
                                    {
                                        "title": "Not Reddit",
                                        "url": "https://www.example.com/something",
                                        "subreddit": "test",
                                        "date": None,
                                        "why_relevant": "irrelevant",
                                        "relevance": 0.5,
                                    }
                                ]
                            })
                        }
                    ]
                }
            ]
        }
        items = parse_reddit_response(response)
        assert items == []

    def test_extract_core_subject_removes_noise(self):
        result = _extract_core_subject("best machine learning practices")
        assert "best" not in result
        assert "practices" not in result
        assert "machine" in result or "learning" in result


# ---------------------------------------------------------------------------
# TestSearchX
# ---------------------------------------------------------------------------

class TestSearchX:
    def _make_mock_x_response(self):
        return {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({
                                "items": [
                                    {
                                        "text": "Exciting new genomics paper out today!",
                                        "url": "https://x.com/scientist/status/123456789",
                                        "author_handle": "scientist",
                                        "date": "2024-06-15",
                                        "engagement": {"likes": 150, "reposts": 30, "replies": 10, "quotes": 5},
                                        "why_relevant": "New genomics research",
                                        "relevance": 0.85,
                                    }
                                ]
                            })
                        }
                    ]
                }
            ]
        }

    def test_search_x_with_mock_response(self):
        """search_x with mock_response bypasses HTTP — should return the mock dict."""
        mock = self._make_mock_x_response()
        result = search_x(
            api_key="fake_key", model="grok-2",
            topic="genomics", from_date="2024-06-01", to_date="2024-06-30",
            mock_response=mock,
        )
        assert result is mock

    def test_parse_x_response_extracts_items(self):
        mock = self._make_mock_x_response()
        items = parse_x_response(mock)
        assert isinstance(items, list)
        assert len(items) == 1
        assert "genomics" in items[0]["text"]
        assert items[0]["author_handle"] == "scientist"

    def test_parse_x_response_empty(self):
        items = parse_x_response({})
        assert items == []

    def test_parse_x_response_error_field(self):
        items = parse_x_response({"error": {"message": "Unauthorized"}})
        assert items == []

    def test_parse_x_response_engagement_normalized(self):
        mock = self._make_mock_x_response()
        items = parse_x_response(mock)
        assert len(items) == 1
        eng = items[0].get("engagement")
        assert eng is not None
        assert "likes" in eng

    @pytest.mark.parametrize("date_str,valid", [
        ("2024-06-15", True),
        ("not-a-date", False),
        (None, True),  # None is kept as-is
    ])
    def test_parse_x_response_date_validation(self, date_str, valid):
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": json.dumps({
                                "items": [
                                    {
                                        "text": "Test post",
                                        "url": "https://x.com/user/status/1",
                                        "author_handle": "user",
                                        "date": date_str,
                                        "why_relevant": "test",
                                        "relevance": 0.5,
                                    }
                                ]
                            })
                        }
                    ]
                }
            ]
        }
        items = parse_x_response(response)
        assert len(items) == 1
        if not valid:
            assert items[0]["date"] is None
        else:
            assert items[0]["date"] == date_str


# ---------------------------------------------------------------------------
# TestEnvDetect
# ---------------------------------------------------------------------------

class TestEnvDetect:
    def test_get_config_with_openai_key(self):
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123", "XAI_API_KEY": ""}):
            config = get_config()
            assert config["OPENAI_API_KEY"] == "sk-test123"

    def test_get_config_with_xai_key(self):
        with patch.dict(os.environ, {"XAI_API_KEY": "xai-test456", "OPENAI_API_KEY": ""}):
            config = get_config()
            assert config["XAI_API_KEY"] == "xai-test456"

    def test_get_config_without_keys(self):
        env_vars = {
            "OPENAI_API_KEY": "", "XAI_API_KEY": "",
            "OPENAI_MODEL_POLICY": "", "OPENAI_MODEL_PIN": "",
            "XAI_MODEL_POLICY": "", "XAI_MODEL_PIN": "",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            # We only verify the function returns without error and returns a dict
            config = get_config()
            assert isinstance(config, dict)

    def test_get_available_sources_both_keys(self):
        config = {"OPENAI_API_KEY": "sk-test", "XAI_API_KEY": "xai-test"}
        assert get_available_sources(config) == "both"

    def test_get_available_sources_openai_only(self):
        config = {"OPENAI_API_KEY": "sk-test", "XAI_API_KEY": None}
        assert get_available_sources(config) == "reddit"

    def test_get_available_sources_xai_only(self):
        config = {"OPENAI_API_KEY": None, "XAI_API_KEY": "xai-test"}
        assert get_available_sources(config) == "x"

    def test_get_available_sources_no_keys(self):
        config = {"OPENAI_API_KEY": None, "XAI_API_KEY": None}
        assert get_available_sources(config) == "web"

    def test_get_missing_keys_none_missing(self):
        config = {"OPENAI_API_KEY": "sk-test", "XAI_API_KEY": "xai-test"}
        assert get_missing_keys(config) == "none"

    def test_get_missing_keys_xai_missing(self):
        config = {"OPENAI_API_KEY": "sk-test", "XAI_API_KEY": None}
        assert get_missing_keys(config) == "x"

    def test_get_missing_keys_both_missing(self):
        config = {"OPENAI_API_KEY": None, "XAI_API_KEY": None}
        assert get_missing_keys(config) == "both"
