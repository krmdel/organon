"""Per-problem signature functions for MAP-Elites behavioural diversity.

A signature extracts a feature vector from a candidate solution's state.
Programs sharing a signature compete within one cluster; programs with
different signatures coexist. This is what preserves behavioural diversity
under evolutionary pressure.

Signatures are deliberately per-problem — difference-bases cares about
|B|, span, and Sidon density; kissing-d11 cares about support size and
integer fraction; Heilbronn cares about angle distribution. The shared
``Signature`` protocol (``extract_features(state) -> tuple``) is the only
interface callers commit to.
"""

from __future__ import annotations

from .base import Signature, discretize_features
from .difference_bases import DifferenceBasesSignature

__all__ = ["Signature", "DifferenceBasesSignature", "discretize_features"]
