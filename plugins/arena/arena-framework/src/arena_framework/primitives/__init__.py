"""Problem-agnostic optimization primitives used by the arena framework.

Each primitive implements a consistent interface:

    result = primitive.run(loss_fn, manifold, budget, warm_start=None)

where
  - ``loss_fn(state) -> float`` is the objective to minimise
  - ``manifold`` exposes ``sample_initial()`` and ``perturb(state, temperature)``
  - ``budget`` caps wall-clock or iteration count (see ``budget.Budget``)
  - ``warm_start`` is an optional initial state (or list of states for
    replica-based primitives like parallel tempering)

Primitives return a dataclass with at minimum ``best_score``, ``best_state``,
``n_iterations``, ``wall_time_s``, and a ``trace`` list for experiment logs.
"""
