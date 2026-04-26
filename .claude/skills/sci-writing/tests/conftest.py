"""pytest configuration for sci-writing citation-pipeline tests."""

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "network: tests that make real HTTP calls (arXiv, CrossRef, NCBI). "
        "Excluded from CI with -m 'not network'.",
    )
