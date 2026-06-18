"""Vectorized daily-OHLC backtester.

Computes per-name overnight / intraday returns, applies the regime-masked selection, the
explicit cost model, the per-boundary trade cap, and the two-independent-books capital
model, then produces cumulative P&L plus a full trade ledger.

Capital model (Design / AGENTS.md #6): two independent **$10,000/day, non-compounding**
books (overnight, intraday); at most **10 entries per boundary per book per day**; idle
capital earns the risk-free yield, not 0%.

Look-ahead (Design / AGENTS.md #3): selection frames are already shifted one day by the
strategy, so a date-``D`` decision uses only information available through the prior
close. Overnight P&L resolves close(D) -> open(D+1); intraday resolves open(D) ->
close(D).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from engine.costs import CostModel


@dataclass(frozen=True)
class BacktestConfig:
    """Run-level configuration for a single book."""

    capital_per_book: float = 10_000.0
    max_entries: int = 10
    risk_free_annual: float = 0.045  # cash earns the broker-sweep yield, not 0%.
    trading_days: int = 252

    @property
    def risk_free_daily(self) -> float:
        return (1.0 + self.risk_free_annual) ** (1.0 / self.trading_days) - 1.0


@dataclass
class BacktestResult:
    """Output of a single-strategy backtest."""

    strategy_id: str
    category: str
    side: str
    daily: pd.DataFrame  # index=date; book_return, book_pnl, cash_return, cash_pnl, n_positions
    trades: pd.DataFrame
    synthetic: bool = False
    meta: dict = field(default_factory=dict)

    @property
    def total_pnl(self) -> float:
        return float(self.daily["book_pnl"].sum())

    @property
    def cash_pnl(self) -> float:
        return float(self.daily["cash_pnl"].sum())

    @property
    def beats_cash(self) -> bool:
        return self.total_pnl > self.cash_pnl


def build_price_matrices(
    history: dict[str, pd.DataFrame],
) -> dict[str, pd.DataFrame]:
    """Align per-symbol OHLCV frames into wide (dates x symbols) matrices."""
    if not history:
        empty = pd.DataFrame()
        return {k: empty for k in ("open", "high", "low", "close", "volume")}
    fields = ("open", "high", "low", "close", "volume")
    out: dict[str, pd.DataFrame] = {}
    for fld in fields:
        out[fld] = pd.DataFrame({sym: frame[fld] for sym, frame in history.items()})
        out[fld] = out[fld].sort_index()
    return out


def _cap_selection(sel: pd.DataFrame, cap: int) -> pd.DataFrame:
    """Keep at most ``cap`` selected names per row (deterministic by column order)."""
    counts = sel.cumsum(axis=1)
    return sel & (counts <= cap)


def _boundary_returns(matrices: dict[str, pd.DataFrame], category: str) -> pd.DataFrame:
    opens = matrices["open"]
    closes = matrices["close"]
    if category == "overnight":
        # Enter at close(D), exit at next open(D+1).
        return opens.shift(-1) / closes - 1.0
    if category == "intraday":
        # Enter at open(D), exit at close(D).
        return closes / opens - 1.0
    raise ValueError(f"unknown category: {category!r}")


def run_backtest(
    history: dict[str, pd.DataFrame],
    strategy,
    config: BacktestConfig | None = None,
    cost_model: CostModel | None = None,
    synthetic: bool = False,
) -> BacktestResult:
    """Backtest one strategy over ``history`` and return daily P&L + a trade ledger."""
    config = config or BacktestConfig()
    cost_model = cost_model or CostModel()
    matrices = build_price_matrices(history)
    closes = matrices["close"]
    volumes = matrices["volume"]

    weights = strategy.select(closes, volumes)
    ret = _boundary_returns(matrices, strategy.category)
    # Align selection and returns.
    weights, ret = weights.align(ret, join="left", axis=None)
    weights = weights.reindex(index=closes.index, columns=closes.columns).fillna(0.0)
    ret = ret.reindex(index=closes.index, columns=closes.columns)

    sel = (weights > 0) & ret.notna()
    sel = _cap_selection(sel, config.max_entries)

    k = sel.sum(axis=1)
    n = closes.shape[1]
    capital = config.capital_per_book

    # Equal-weight within the book.
    inv_k = (1.0 / k.where(k > 0)).fillna(0.0)
    w = sel.mul(inv_k, axis=0)

    # Per-name notional and average-dollar-volume for the liquidity-impact cost term.
    notional = np.repeat((capital * inv_k).to_numpy()[:, None], n, axis=1)
    adv = (closes * volumes).to_numpy()
    cost_frac = cost_model.round_trip_fraction(notional, adv)
    cost_frac = pd.DataFrame(cost_frac, index=closes.index, columns=closes.columns)

    side_sign = 1.0 if strategy.side == "long" else -1.0
    net = side_sign * ret - cost_frac

    book_ret = (w * net.fillna(0.0)).sum(axis=1)
    # Days with no position sit in cash and earn the risk-free yield.
    rf = config.risk_free_daily
    book_ret = book_ret.where(k > 0, rf)

    daily = pd.DataFrame(
        {
            "book_return": book_ret,
            "book_pnl": capital * book_ret,
            "cash_return": rf,
            "cash_pnl": capital * rf,
            "n_positions": k.astype("int64"),
        }
    )
    daily["cum_book_pnl"] = daily["book_pnl"].cumsum()
    daily["cum_cash_pnl"] = daily["cash_pnl"].cumsum()

    trades = _build_trade_ledger(
        strategy, matrices, sel, w, ret, cost_frac, net, capital
    )

    return BacktestResult(
        strategy_id=strategy.id,
        category=strategy.category,
        side=strategy.side,
        daily=daily,
        trades=trades,
        synthetic=synthetic,
    )


def _build_trade_ledger(
    strategy,
    matrices: dict[str, pd.DataFrame],
    sel: pd.DataFrame,
    w: pd.DataFrame,
    ret: pd.DataFrame,
    cost_frac: pd.DataFrame,
    net: pd.DataFrame,
    capital: float,
) -> pd.DataFrame:
    cells = sel.stack()
    cells = cells[cells]
    if cells.empty:
        return pd.DataFrame(
            columns=[
                "date", "strategy_id", "book", "side", "symbol", "entry_price",
                "exit_price", "gross_return", "cost_fraction", "net_return",
                "weight", "notional", "pnl",
            ]
        )
    opens = matrices["open"]
    closes = matrices["close"]
    overnight = strategy.category == "overnight"
    rows = []
    for (dt, sym) in cells.index:
        if overnight:
            entry_price = closes.at[dt, sym]
            loc = closes.index.get_loc(dt)
            if loc + 1 < len(opens):
                exit_price = opens.iat[loc + 1, opens.columns.get_loc(sym)]
            else:
                exit_price = np.nan
        else:
            entry_price = opens.at[dt, sym]
            exit_price = closes.at[dt, sym]
        weight = w.at[dt, sym]
        notional = capital * weight
        rows.append(
            {
                "date": dt,
                "strategy_id": strategy.id,
                "book": strategy.category,
                "side": strategy.side,
                "symbol": sym,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "gross_return": ret.at[dt, sym],
                "cost_fraction": cost_frac.at[dt, sym],
                "net_return": net.at[dt, sym],
                "weight": weight,
                "notional": notional,
                "pnl": notional * net.at[dt, sym],
            }
        )
    return pd.DataFrame(rows)
