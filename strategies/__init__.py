"""Strategy library: declarative specs + selection logic.

Each strategy is a small declarative spec (``category``, ``side``, ``selection``,
``regime_gate``, ``params``) plus a look-ahead-safe selection function. See
docs/DESIGN.md, "Strategy library". Phase 1 ships one reference strategy per side.
"""

from strategies.library import Strategy, build_strategy, load_reference_strategies
from strategies.spec import StrategySpec, load_spec, load_specs_dir

__all__ = [
    "StrategySpec",
    "load_spec",
    "load_specs_dir",
    "Strategy",
    "build_strategy",
    "load_reference_strategies",
]
