"""Core engine behavior — return math for single-boundary trades.

These tests pin down the most fundamental contract: given daily OHLC, an
overnight trade (buy close, sell next open) and an intraday trade (buy open,
sell same-day close) produce exactly the right P&L, with side flipping sign.
"""

import pandas as pd
import pytest

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest

ZERO_COST = CostModel(commission_bps=0.0, slippage_bps=0.0)


def _prices(opens: dict, closes: dict) -> PriceData:
    idx = pd.to_datetime(sorted(opens))
    tickers = sorted({t for day in opens.values() for t in day})
    o = pd.DataFrame(
        {t: [opens[d.strftime("%Y-%m-%d")].get(t) for d in idx] for t in tickers},
        index=idx,
    )
    c = pd.DataFrame(
        {t: [closes[d.strftime("%Y-%m-%d")].get(t) for d in idx] for t in tickers},
        index=idx,
    )
    return PriceData(opens=o, closes=c)


def test_overnight_long_single_trade():
    # Enter at close of day 0 (100), exit at next open (110) => +10%.
    prices = _prices(
        opens={"2024-01-02": {"AAA": 100.0}, "2024-01-03": {"AAA": 110.0}},
        closes={"2024-01-02": {"AAA": 100.0}, "2024-01-03": {"AAA": 100.0}},
    )
    spec = StrategySpec(name="on", category="overnight", side="long")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert len(res.trades) == 1
    trade = res.trades.iloc[0]
    assert trade["ticker"] == "AAA"
    assert trade["entry_price"] == 100.0
    assert trade["exit_price"] == 110.0
    assert trade["gross_return"] == pytest.approx(0.10)
    assert trade["net_pnl"] == pytest.approx(1000.0)
    assert res.total_pnl == pytest.approx(1000.0)


def test_intraday_long_signs_per_day():
    # Day 0: open 100 -> close 110 = +10%. Day 1: open 100 -> close 90 = -10%.
    prices = _prices(
        opens={"2024-01-02": {"AAA": 100.0}, "2024-01-03": {"AAA": 100.0}},
        closes={"2024-01-02": {"AAA": 110.0}, "2024-01-03": {"AAA": 90.0}},
    )
    spec = StrategySpec(name="id", category="intraday", side="long")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert len(res.trades) == 2
    assert res.daily_pnl.iloc[0] == pytest.approx(1000.0)
    assert res.daily_pnl.iloc[1] == pytest.approx(-1000.0)
    assert res.total_pnl == pytest.approx(0.0, abs=1e-6)


def test_short_flips_sign():
    prices = _prices(
        opens={"2024-01-02": {"AAA": 100.0}, "2024-01-03": {"AAA": 110.0}},
        closes={"2024-01-02": {"AAA": 100.0}, "2024-01-03": {"AAA": 100.0}},
    )
    spec = StrategySpec(name="on-short", category="overnight", side="short")

    res = run_backtest(prices, spec, capital=10_000.0, cost_model=ZERO_COST)

    assert res.trades.iloc[0]["net_pnl"] == pytest.approx(-1000.0)
    assert res.total_pnl == pytest.approx(-1000.0)


def test_cash_baseline_tracks_cash_etf_total_return():
    prices = _prices(
        opens={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
            "2024-01-04": {"AAA": 100.0, "SGOV": 102.01},
        },
        closes={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
            "2024-01-04": {"AAA": 100.0, "SGOV": 102.01},
        },
    )
    spec = StrategySpec(name="cash-comparison", category="intraday", side="long")

    result = run_backtest(
        prices,
        spec,
        capital=10_000.0,
        cost_model=ZERO_COST,
        cash_ticker="SGOV",
    )

    assert list(result.trades["ticker"].unique()) == ["AAA"]
    assert list(result.cash_baseline) == pytest.approx([0.0, 100.0, 100.0])


def test_idle_book_earns_cash_etf_return():
    prices = _prices(
        opens={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
        },
        closes={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
        },
    )
    spec = StrategySpec(
        name="never-on",
        category="intraday",
        side="long",
        regime=lambda history: False,
    )

    result = run_backtest(
        prices,
        spec,
        capital=10_000.0,
        cost_model=ZERO_COST,
        cash_ticker="SGOV",
    )

    assert result.trades.empty
    assert list(result.daily_pnl) == pytest.approx([0.0, 100.0])
    assert result.total_pnl == pytest.approx(100.0)


def test_overnight_cash_comparison_uses_next_observed_daily_cash_return():
    prices = _prices(
        opens={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
        },
        closes={
            "2024-01-02": {"AAA": 100.0, "SGOV": 100.0},
            "2024-01-03": {"AAA": 100.0, "SGOV": 101.0},
        },
    )
    spec = StrategySpec(name="overnight", category="overnight", side="long")

    result = run_backtest(
        prices,
        spec,
        capital=10_000.0,
        cost_model=ZERO_COST,
        cash_ticker="SGOV",
    )

    assert list(result.cash_baseline) == pytest.approx([100.0])
