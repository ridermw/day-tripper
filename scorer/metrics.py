"""Phase 1 candidate-board metrics + the mandatory cost-sensitivity table.

These are descriptive, net-of-cost metrics for the ungraded candidate board. They do
**not** constitute promotion: the gauntlet (purged WF / DSR / PBO) is Phase 2.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.backtest import BacktestConfig, BacktestResult, run_backtest
from engine.costs import COST_SENSITIVITY_GRID, CostModel


@dataclass
class CandidateScore:
    """Descriptive, net-of-cost metrics for one strategy (ungraded candidate board)."""

    strategy_id: str
    category: str
    side: str
    n_days: int
    total_pnl: float
    cash_pnl: float
    excess_pnl: float  # total_pnl - cash_pnl
    ann_return: float  # on the fixed book notional
    sharpe: float
    hit_rate: float
    max_drawdown: float
    n_trades: int
    beats_cash: bool
    graded: bool = False  # Phase 1: always False -> candidate board, never leaderboard.
    synthetic: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_id": self.strategy_id,
            "category": self.category,
            "side": self.side,
            "n_days": self.n_days,
            "total_pnl": self.total_pnl,
            "cash_pnl": self.cash_pnl,
            "excess_pnl": self.excess_pnl,
            "ann_return": self.ann_return,
            "sharpe": self.sharpe,
            "hit_rate": self.hit_rate,
            "max_drawdown": self.max_drawdown,
            "n_trades": self.n_trades,
            "beats_cash": self.beats_cash,
            "graded": self.graded,
            "synthetic": self.synthetic,
            "notes": list(self.notes),
        }


def _sharpe(returns: pd.Series, trading_days: int) -> float:
    r = returns.dropna()
    if r.empty or r.std(ddof=0) == 0:
        return 0.0
    return float(np.sqrt(trading_days) * r.mean() / r.std(ddof=0))


def _max_drawdown(cum_pnl: pd.Series) -> float:
    if cum_pnl.empty:
        return 0.0
    running_max = cum_pnl.cummax()
    drawdown = cum_pnl - running_max
    return float(drawdown.min())


def score_result(
    result: BacktestResult, config: BacktestConfig | None = None
) -> CandidateScore:
    """Compute candidate-board metrics from a backtest result."""
    config = config or BacktestConfig()
    daily = result.daily
    book_ret = daily["book_return"]
    n_days = int(len(daily))
    total_pnl = float(daily["book_pnl"].sum())
    cash_pnl = float(daily["cash_pnl"].sum())
    ann_return = (
        float(book_ret.mean() * config.trading_days) if n_days else 0.0
    )
    hit_rate = (
        float((daily["book_pnl"] > daily["cash_pnl"]).mean()) if n_days else 0.0
    )
    notes: list[str] = []
    if result.synthetic:
        notes.append(
            "SYNTHETIC DATA -- not a real track record (external source unavailable)."
        )
    notes.append("Phase 1 candidate board: ungraded (no gauntlet yet).")

    return CandidateScore(
        strategy_id=result.strategy_id,
        category=result.category,
        side=result.side,
        n_days=n_days,
        total_pnl=total_pnl,
        cash_pnl=cash_pnl,
        excess_pnl=total_pnl - cash_pnl,
        ann_return=ann_return,
        sharpe=_sharpe(book_ret, config.trading_days),
        hit_rate=hit_rate,
        max_drawdown=_max_drawdown(daily["cum_book_pnl"]),
        n_trades=int(len(result.trades)),
        beats_cash=total_pnl > cash_pnl,
        graded=False,
        synthetic=result.synthetic,
        notes=notes,
    )


def cost_sensitivity_table(
    history: dict[str, pd.DataFrame],
    strategy,
    base_cost: CostModel | None = None,
    config: BacktestConfig | None = None,
    grid: tuple[float, ...] = COST_SENSITIVITY_GRID,
    synthetic: bool = False,
) -> pd.DataFrame:
    """Re-run the strategy across scaled cost assumptions (Design requirement).

    Returns one row per multiplier with total P&L, excess-over-cash, and whether the
    conclusion ("beats cash") survives tightening costs.
    """
    base_cost = base_cost or CostModel()
    config = config or BacktestConfig()
    rows = []
    for factor in grid:
        cm = base_cost.scaled(factor)
        res = run_backtest(history, strategy, config=config, cost_model=cm, synthetic=synthetic)
        rows.append(
            {
                "cost_multiplier": factor,
                "total_pnl": res.total_pnl,
                "cash_pnl": res.cash_pnl,
                "excess_pnl": res.total_pnl - res.cash_pnl,
                "beats_cash": res.beats_cash,
            }
        )
    return pd.DataFrame(rows)
