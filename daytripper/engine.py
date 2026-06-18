"""The backtest engine.

Vectorized over the universe per trade day, but written plainly here for
correctness first. For each trade date it asks the strategy what to hold (using
only prior data), computes each single-boundary trade's P&L from daily OHLC,
and records a full trade ledger plus daily P&L.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from daytripper.costs import CostModel
from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec

TRADE_COLUMNS = [
    "date",
    "ticker",
    "category",
    "side",
    "entry_price",
    "exit_price",
    "gross_return",
    "notional",
    "cost",
    "net_pnl",
]


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    daily_pnl: pd.Series
    cash_baseline: pd.Series
    total_pnl: float


TRADING_DAYS_PER_YEAR = 252


def run_backtest(
    prices: PriceData,
    spec: StrategySpec,
    capital: float = 10_000.0,
    cost_model: CostModel | None = None,
    max_positions: int = 10,
    risk_free_annual: float = 0.0,
) -> BacktestResult:
    dates = list(prices.dates)
    costs = cost_model or CostModel()
    daily_rf = risk_free_annual / TRADING_DAYS_PER_YEAR

    # Overnight trades exit at the *next* open, so the last date has no exit.
    if spec.category == "overnight":
        trade_dates = dates[:-1]
    else:
        trade_dates = dates

    rows: list[dict] = []
    daily: dict = {}

    for i, day in enumerate(trade_dates):
        history = prices.before(day)
        if spec.regime(history):
            selected = list(spec.select(history, prices.tickers))
            # Cap entries per day, preserving the selector's priority order.
            selected = selected[:max_positions]
        else:
            selected = []

        day_pnl = 0.0
        n = len(selected)
        if n > 0:
            notional = capital / n
            for ticker in selected:
                if spec.category == "overnight":
                    nxt = dates[i + 1]
                    entry = float(prices.closes.at[day, ticker])
                    exit_price = float(prices.opens.at[nxt, ticker])
                else:
                    entry = float(prices.opens.at[day, ticker])
                    exit_price = float(prices.closes.at[day, ticker])

                gross_return = (exit_price / entry - 1.0) * spec.sign
                cost = costs.round_trip_cost(notional)
                net_pnl = gross_return * notional - cost
                rows.append(
                    {
                        "date": day,
                        "ticker": ticker,
                        "category": spec.category,
                        "side": spec.side,
                        "entry_price": entry,
                        "exit_price": exit_price,
                        "gross_return": gross_return,
                        "notional": notional,
                        "cost": cost,
                        "net_pnl": net_pnl,
                    }
                )
                day_pnl += net_pnl

        daily[day] = day_pnl

    trades = pd.DataFrame(rows, columns=TRADE_COLUMNS)
    daily_pnl = pd.Series(daily, dtype=float)
    cash_baseline = pd.Series(
        {day: capital * daily_rf for day in trade_dates}, dtype=float
    )
    total_pnl = float(trades["net_pnl"].sum()) if not trades.empty else 0.0
    return BacktestResult(
        trades=trades,
        daily_pnl=daily_pnl,
        cash_baseline=cash_baseline,
        total_pnl=total_pnl,
    )
