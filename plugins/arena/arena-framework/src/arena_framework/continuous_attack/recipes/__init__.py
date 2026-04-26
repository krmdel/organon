"""Recipe modules for the continuous-attack adapter registry (U14).

Each recipe module declares a recipe class conforming to
:class:`arena_framework.continuous_attack.ContinuousRecipe` and registers
a factory at import time via
:func:`arena_framework.continuous_attack.register_recipe`.

* ``sphere_lbfgs``     — sphere manifold L-BFGS + basin-hop (Thomson-shaped)
* ``softmin_cascade``  — β-annealed soft-min (Tammes-shaped) [U14/3]
* ``nonneg_smooth_max`` — β-annealed smooth-max for nonneg autocorrelation [U14/4]
* ``warmstart_polish`` — noise trials + ULP tweaks on a competitor seed [U14/5]
* ``plane_2d_packing`` — 2D analog of sphere_lbfgs for packing problems [U14/6]
* ``discrete_local_search`` — ±1 flip local search / SA [deferred]

Importing this package on its own does not pull heavy deps. Each recipe
module imports numpy/scipy at module-level; call :func:`load_all_recipes`
to eagerly register every concrete recipe (the orchestrator calls it once
at startup).
"""

from __future__ import annotations


def load_all_recipes() -> None:
    """Import all recipe modules to trigger their ``register_recipe``
    side-effects. Safe to call repeatedly — Python caches module imports.

    Called once by the orchestrator at startup (U14/7). Tests that need a
    specific recipe registered can import the module directly or call
    this helper for the full set.
    """
    from . import sphere_lbfgs  # noqa: F401
    from . import softmin_cascade  # noqa: F401
    from . import nonneg_smooth_max  # noqa: F401
    from . import warmstart_polish  # noqa: F401
    from . import plane_2d_packing  # noqa: F401
