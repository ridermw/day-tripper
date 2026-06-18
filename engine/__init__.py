"""Engine: explicit cost model + vectorized daily-OHLC backtester.

"Costs are the core, not a footnote." See docs/DESIGN.md, "Engine" and AGENTS.md #4.
"""

from engine.backtest import (
    BacktestConfig,
    BacktestResult,
    build_price_matrices,
    run_backtest,
)
from engine.costs import COST_SENSITIVITY_GRID, CostModel

__all__ = [
    "CostModel",
    "COST_SENSITIVITY_GRID",
    "BacktestConfig",
    "BacktestResult",
    "build_price_matrices",
    "run_backtest",
]
