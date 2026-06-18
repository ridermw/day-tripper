"""Cost model is actually applied to net P&L."""

import pandas as pd
import pytest

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest


def _one_overnight_winner() -> PriceData:
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"AAA": [100.0, 110.0]}, index=idx)
    closes = pd.DataFrame({"AAA": [100.0, 100.0]}, index=idx)
    return PriceData(opens=opens, closes=closes)


def test_round_trip_cost_is_subtracted_from_pnl():
    prices = _one_overnight_winner()
    spec = StrategySpec(name="on", category="overnight", side="long")
    # 5 bps commission + 5 bps slippage = 10 bps/fill on a 10_000 notional = $10/fill,
    # round trip = $20.
    cost = CostModel(commission_bps=5.0, slippage_bps=5.0)

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=cost)

    trade = res.trades.iloc[0]
    assert trade["cost"] == pytest.approx(20.0)
    # gross was +1000, minus 20 of cost.
    assert trade["net_pnl"] == pytest.approx(980.0)
    assert res.total_pnl == pytest.approx(980.0)


def test_cost_model_defaults_to_zero_when_none():
    prices = _one_overnight_winner()
    spec = StrategySpec(name="on", category="overnight", side="long")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=None)

    assert res.trades.iloc[0]["cost"] == pytest.approx(0.0)
    assert res.total_pnl == pytest.approx(1000.0)
