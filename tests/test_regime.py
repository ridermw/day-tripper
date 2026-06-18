"""Regime gate: a strategy only trades on days its regime is active."""

import pandas as pd
import pytest

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest

ZERO_COST = CostModel(0.0, 0.0)


def _intraday_two_days() -> PriceData:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"AAA": [100.0, 100.0]}, index=idx)
    closes = pd.DataFrame({"AAA": [110.0, 110.0]}, index=idx)
    return PriceData(opens=opens, closes=closes)


def test_regime_off_blocks_all_trades():
    prices = _intraday_two_days()
    spec = StrategySpec(
        name="id", category="intraday", side="long", regime=lambda history: False
    )

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert len(res.trades) == 0
    assert res.total_pnl == pytest.approx(0.0)
    assert (res.daily_pnl == 0.0).all()


def test_regime_gates_per_day():
    prices = _intraday_two_days()
    # Active only on the first day (when no prior history exists).
    spec = StrategySpec(
        name="id",
        category="intraday",
        side="long",
        regime=lambda history: len(history.dates) == 0,
    )

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert len(res.trades) == 1
    assert res.trades.iloc[0]["date"] == pd.Timestamp("2024-01-02")
    assert res.daily_pnl.loc[pd.Timestamp("2024-01-03")] == pytest.approx(0.0)
