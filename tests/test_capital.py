"""Capital model: risk-free cash baseline and non-compounding daily notional."""

import pandas as pd
import pytest

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest

ZERO_COST = CostModel(0.0, 0.0)


def test_cash_baseline_earns_risk_free_yield():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"AAA": [100.0, 100.0]}, index=idx)
    closes = pd.DataFrame({"AAA": [110.0, 110.0]}, index=idx)
    prices = PriceData(opens=opens, closes=closes)
    spec = StrategySpec(name="id", category="intraday", side="long")

    # 2.52% annual / 252 trading days = 0.01% daily -> $1/day on $10k.
    res = run_backtest(
        prices, spec, capital=10_000.0, cost_model=ZERO_COST, risk_free_annual=0.0252
    )

    assert len(res.cash_baseline) == 2
    assert res.cash_baseline.tolist() == pytest.approx([1.0, 1.0])


def test_notional_is_non_compounding():
    # Day 0 doubles (+100%); day 1 is a small winner. Day 1 must still size off
    # the fixed $10k, not off the day-0 gain.
    idx = pd.to_datetime(["2024-01-02", "2024-01-03"])
    opens = pd.DataFrame({"AAA": [100.0, 100.0]}, index=idx)
    closes = pd.DataFrame({"AAA": [200.0, 110.0]}, index=idx)
    prices = PriceData(opens=opens, closes=closes)
    spec = StrategySpec(name="id", category="intraday", side="long")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert (res.trades["notional"] == 10_000.0).all()
    assert res.daily_pnl.iloc[0] == pytest.approx(10_000.0)  # +100% of 10k
    assert res.daily_pnl.iloc[1] == pytest.approx(1_000.0)  # +10% of 10k, not of 20k
