"""Engine, cost model, look-ahead, capital model, and scorer tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.backtest import BacktestConfig, build_price_matrices, run_backtest
from engine.costs import CostModel
from scorer.baseline import cash_baseline_series
from scorer.metrics import cost_sensitivity_table, score_result
from strategies.library import build_strategy
from strategies.spec import StrategySpec


def _single_strategy(category, side="long", symbol="SPY", gate=None):
    spec = StrategySpec(
        id=f"{category}_{side}_{symbol}",
        category=category,
        side=side,
        selection="single",
        regime_gate=gate,
        params={"symbol": symbol},
    )
    return build_strategy(spec)


def test_cost_model_round_trip_is_twice_per_side():
    cm = CostModel(commission_bps=1.0, slippage_bps=5.0, impact_coef=0.0)
    assert np.isclose(cm.per_side_fraction(), 6.0 / 10_000.0)
    assert np.isclose(cm.round_trip_fraction(), 2 * (6.0 / 10_000.0))


def test_overnight_return_matches_manual(synthetic_history):
    strat = _single_strategy("overnight", symbol="SPY")
    cm = CostModel(commission_bps=0.0, slippage_bps=0.0, impact_coef=0.0)
    res = run_backtest(synthetic_history, strat, cost_model=cm)
    matrices = build_price_matrices(synthetic_history)
    opens, closes = matrices["open"], matrices["close"]
    # Overnight: close(D) -> open(D+1). Pick a day with a position.
    traded = res.trades.iloc[0]
    dt = traded["date"]
    loc = closes.index.get_loc(dt)
    expected = opens.iloc[loc + 1]["SPY"] / closes.loc[dt, "SPY"] - 1.0
    assert np.isclose(traded["gross_return"], expected)


def test_costs_reduce_pnl(synthetic_history):
    strat = _single_strategy("intraday", symbol="QQQ")
    free = run_backtest(
        synthetic_history, strat, cost_model=CostModel(0.0, 0.0, 0.0)
    )
    costly = run_backtest(
        synthetic_history, strat, cost_model=CostModel(2.0, 10.0, 0.2)
    )
    assert costly.total_pnl < free.total_pnl


def test_capital_model_non_compounding(synthetic_history):
    config = BacktestConfig(capital_per_book=10_000.0)
    strat = _single_strategy("intraday", symbol="SPY")
    res = run_backtest(synthetic_history, strat, config=config)
    # Each trade's notional never exceeds the per-book capital (non-compounding).
    assert (res.trades["notional"] <= config.capital_per_book + 1e-6).all()


def test_trade_cap_enforced(synthetic_history):
    spec = StrategySpec(
        id="mom_capped",
        category="overnight",
        side="long",
        selection="momentum",
        params={"lookback": 20, "top_n": 50},  # request more than the cap
    )
    strat = build_strategy(spec)
    config = BacktestConfig(max_entries=10)
    res = run_backtest(synthetic_history, strat, config=config)
    assert res.daily["n_positions"].max() <= 10


def test_no_lookahead_shifted_signal(synthetic_history):
    # A momentum strategy must not use same-day information: the selection frame for
    # date D must be derivable from data through D-1. We verify the strategy shifts by
    # checking the first lookback+1 rows have no positions.
    spec = StrategySpec(
        id="mom_lag", category="intraday", selection="momentum",
        params={"lookback": 20, "top_n": 5},
    )
    strat = build_strategy(spec)
    closes = build_price_matrices(synthetic_history)["close"]
    weights = strat.select(closes)
    # Row 0..lookback cannot have a valid (shifted) signal.
    assert weights.iloc[: 20].sum().sum() == 0


def test_cash_in_flat_regime(synthetic_history):
    # Regime gate that is rarely satisfied still yields the risk-free return on flat days.
    config = BacktestConfig()
    strat = _single_strategy("overnight", symbol="SPY", gate="spy_above_200dma")
    res = run_backtest(synthetic_history, strat, config=config)
    flat_days = res.daily[res.daily["n_positions"] == 0]
    if not flat_days.empty:
        assert np.allclose(flat_days["book_return"], config.risk_free_daily)


def test_cash_baseline_series_positive():
    idx = pd.bdate_range("2020-01-01", "2020-12-31")
    base = cash_baseline_series(idx)
    assert base["cum_cash_pnl"].iloc[-1] > 0


def test_score_result_and_sensitivity(synthetic_history):
    strat = _single_strategy("intraday", symbol="SPY")
    res = run_backtest(synthetic_history, strat)
    score = score_result(res)
    assert score.n_days == len(res.daily)
    assert score.graded is False  # Phase 1: candidate board only.
    table = cost_sensitivity_table(synthetic_history, strat)
    assert list(table["cost_multiplier"]) == [0.5, 1.0, 1.5, 2.0, 3.0]
    # Higher costs never increase P&L.
    assert table["total_pnl"].is_monotonic_decreasing
