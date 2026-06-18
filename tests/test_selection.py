"""Position sizing: equal-weight split and the per-day position cap."""

import pandas as pd
import pytest

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest

ZERO_COST = CostModel(0.0, 0.0)


def _intraday_winners(tickers, gain=0.10):
    idx = pd.to_datetime(["2024-01-02"])
    opens = pd.DataFrame({t: [100.0] for t in tickers}, index=idx)
    closes = pd.DataFrame({t: [100.0 * (1 + gain)] for t in tickers}, index=idx)
    return PriceData(opens=opens, closes=closes)


def test_equal_weight_split_across_selected():
    prices = _intraday_winners(["AAA", "BBB"])
    spec = StrategySpec(name="id", category="intraday", side="long")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert len(res.trades) == 2
    assert set(res.trades["notional"]) == {5_000.0}
    # each: 10% of 5_000 = 500 -> day total 1000
    assert res.daily_pnl.iloc[0] == pytest.approx(1000.0)


def test_position_cap_limits_trades_per_day():
    tickers = [f"T{i:02d}" for i in range(12)]
    prices = _intraday_winners(tickers)
    spec = StrategySpec(name="id", category="intraday", side="long")

    res = run_backtest(
        prices, spec, capital=10_000.0, cost_model=ZERO_COST, max_positions=10
    )

    assert len(res.trades) == 10
    assert set(res.trades["notional"]) == {1_000.0}
    # The cap is deterministic: the first 10 tickers in sorted order.
    assert sorted(res.trades["ticker"]) == sorted(tickers)[:10]
