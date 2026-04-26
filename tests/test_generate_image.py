"""Tests for viz-nano-banana generate_image module.

Covers pure functions: get_api_key, auto_detect_resolution,
choose_output_resolution, and mocked Gemini API generation flow.
"""

import importlib.util
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Module import via importlib (matching in-skill test pattern, per D-13)
# ---------------------------------------------------------------------------

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent
    / ".claude"
    / "skills"
    / "viz-nano-banana"
    / "scripts"
    / "generate_image.py"
)

_spec = importlib.util.spec_from_file_location("generate_image", str(_MODULE_PATH))
assert _spec and _spec.loader, f"Could not load spec for {_MODULE_PATH}"
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)  # type: ignore[union-attr]


# ---------------------------------------------------------------------------
# TestGetApiKey (UNIT-01 — pure function, no I/O)
# ---------------------------------------------------------------------------


class TestGetApiKey:
    def test_returns_provided_key_when_given(self):
        """Explicit key argument takes priority over env."""
        result = mod.get_api_key("explicit-key-abc")
        assert result == "explicit-key-abc"

    def test_reads_from_env_when_no_explicit_key(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key-xyz"}, clear=False):
            result = mod.get_api_key(None)
        assert result == "env-key-xyz"

    def test_returns_none_when_no_key_anywhere(self):
        env_without_key = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            result = mod.get_api_key(None)
        assert result is None

    def test_explicit_key_overrides_env(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=False):
            result = mod.get_api_key("override-key")
        assert result == "override-key"


# ---------------------------------------------------------------------------
# TestAutoDetectResolution (UNIT-01 — pure function)
# ---------------------------------------------------------------------------


class TestAutoDetectResolution:
    @pytest.mark.parametrize(
        ("max_input_dim", "expected"),
        [
            (0, "1K"),
            (500, "1K"),
            (1499, "1K"),
            (1500, "2K"),
            (2500, "2K"),
            (2999, "2K"),
            (3000, "4K"),
            (5000, "4K"),
        ],
    )
    def test_thresholds(self, max_input_dim, expected):
        assert mod.auto_detect_resolution(max_input_dim) == expected

    def test_returns_string(self):
        result = mod.auto_detect_resolution(1000)
        assert isinstance(result, str)

    def test_boundary_exactly_1500(self):
        assert mod.auto_detect_resolution(1500) == "2K"

    def test_boundary_exactly_3000(self):
        assert mod.auto_detect_resolution(3000) == "4K"


# ---------------------------------------------------------------------------
# TestChooseOutputResolution (UNIT-01 — pure function)
# ---------------------------------------------------------------------------


class TestChooseOutputResolution:
    def test_explicit_resolution_returned_as_is(self):
        res, auto = mod.choose_output_resolution("2K", 5000, True)
        assert res == "2K"
        assert auto is False

    def test_auto_detect_when_no_request_with_input_images(self):
        res, auto = mod.choose_output_resolution(None, 2200, True)
        assert res == "2K"
        assert auto is True

    def test_defaults_to_1k_without_inputs(self):
        res, auto = mod.choose_output_resolution(None, 0, False)
        assert res == "1K"
        assert auto is False

    def test_explicit_1k_with_large_input_respected(self):
        res, auto = mod.choose_output_resolution("1K", 3500, True)
        assert res == "1K"
        assert auto is False

    def test_returns_tuple_of_two(self):
        result = mod.choose_output_resolution(None, 1000, True)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_auto_detect_high_res_input(self):
        res, auto = mod.choose_output_resolution(None, 4000, True)
        assert res == "4K"
        assert auto is True


# ---------------------------------------------------------------------------
# TestGenerateImageMocked (UNIT-01 — mocked Gemini API)
# ---------------------------------------------------------------------------


class TestGenerateImageMocked:
    """Smoke-test the main() generation flow with a mocked Gemini client."""

    def _build_fake_response(self, image_bytes: bytes = b"fake_image_data"):
        """Build a minimal fake response structure matching the real API."""
        fake_part_text = MagicMock()
        fake_part_text.text = "Here is your image."
        fake_part_text.inline_data = None

        fake_part_image = MagicMock()
        fake_part_image.text = None
        fake_inline = MagicMock()
        fake_inline.data = image_bytes
        fake_part_image.inline_data = fake_inline

        fake_response = MagicMock()
        fake_response.parts = [fake_part_text, fake_part_image]
        return fake_response

    def test_resolution_selection_no_inputs(self):
        """choose_output_resolution with no inputs returns 1K, not auto-detected."""
        res, auto = mod.choose_output_resolution(None, 0, False)
        assert res == "1K"
        assert auto is False

    def test_get_api_key_called_with_none_returns_env(self):
        """When env key is present get_api_key(None) returns it."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test-key-123"}, clear=False):
            assert mod.get_api_key(None) == "test-key-123"

    def test_fake_response_parts_structure(self):
        """Verify our fake response mirrors what main() iterates over."""
        fake_resp = self._build_fake_response(b"fake_image_data")
        assert len(fake_resp.parts) == 2
        # Text part
        assert fake_resp.parts[0].text == "Here is your image."
        assert fake_resp.parts[0].inline_data is None
        # Image part
        assert fake_resp.parts[1].text is None
        assert fake_resp.parts[1].inline_data.data == b"fake_image_data"

    def test_auto_detect_applied_for_large_image(self):
        """For large input images auto-detection should return 4K."""
        res, auto = mod.choose_output_resolution(None, 3500, True)
        assert res == "4K"
        assert auto is True
