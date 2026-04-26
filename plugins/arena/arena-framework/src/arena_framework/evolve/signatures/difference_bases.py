"""Placeholder — implement a problem-specific signature for your problem.

Subclass the base protocol in ``base.py`` and register it with ``ProgramDB``.

Example::

    from .base import discretize_features

    class MyProblemSignature:
        DEFAULT_RESOLUTIONS = (10, 0.1)  # tune per problem

        def __init__(self, *, resolutions=DEFAULT_RESOLUTIONS):
            self.resolutions = resolutions

        def extract_features(self, state) -> tuple:
            # map your solution state to a fixed-length float tuple
            ...

        def cluster_key(self, state) -> tuple:
            return discretize_features(self.extract_features(state), self.resolutions)
"""
