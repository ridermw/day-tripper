"""The risk-free cash baseline -- the defending champion.

"Cash is the defending champion" (AGENTS.md #1). The baseline earns the risk-free /
broker-sweep yield, not 0% (Design: "Cash baseline = risk-free / broker-sweep yield").
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.backtest import BacktestConfig


@dataclass(frozen=True)
class CashBaseline:
    """Daily risk-free P&L on a fixed, non-compounding book."""

    config: BacktestConfig = BacktestConfig()

    @property
    def daily_pnl(self) -> float:
        return self.config.capital_per_book * self.config.risk_free_daily

    def series(self, index: pd.DatetimeIndex) -> pd.DataFrame:
        return cash_baseline_series(index, self.config)


def cash_baseline_series(
    index: pd.DatetimeIndex, config: BacktestConfig | None = None
) -> pd.DataFrame:
    """Cash P&L over ``index``: fixed daily risk-free return on the book notional."""
    config = config or BacktestConfig()
    daily = config.capital_per_book * config.risk_free_daily
    out = pd.DataFrame(index=index)
    out["cash_pnl"] = daily
    out["cum_cash_pnl"] = out["cash_pnl"].cumsum()
    return out
