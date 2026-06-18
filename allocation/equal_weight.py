"""Equal-weight + cash allocator across promoted strategies, per independent book.

Each book ($10K/day, non-compounding) splits its notional equally across the strategies
active in that book; a day with no active strategy stays in cash at the risk-free yield.
Because the two books (overnight, intraday) never compete for capital, they are allocated
independently and reported separately.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from engine.backtest import BacktestConfig, BacktestResult


@dataclass
class BookAllocation:
    """Combined daily P&L for a single book after equal-weight allocation."""

    category: str
    strategy_ids: list[str]
    daily: pd.DataFrame  # book_return, book_pnl, cash_return, cash_pnl, cum_*

    @property
    def total_pnl(self) -> float:
        return float(self.daily["book_pnl"].sum())

    @property
    def cash_pnl(self) -> float:
        return float(self.daily["cash_pnl"].sum())


@dataclass
class EqualWeightAllocator:
    """The Phase 1 production allocator: equal-weight across a book's strategies."""

    config: BacktestConfig = BacktestConfig()

    def allocate(self, results: list[BacktestResult]) -> dict[str, BookAllocation]:
        return allocate_equal_weight(results, self.config)


def allocate_equal_weight(
    results: list[BacktestResult], config: BacktestConfig | None = None
) -> dict[str, BookAllocation]:
    """Combine per-strategy results into one allocation per book.

    Within a book the daily book-return is the equal-weight average of its strategies'
    book-returns (each strategy is itself backtested on the full book notional). Returns
    a mapping ``category -> BookAllocation``.
    """
    config = config or BacktestConfig()
    by_category: dict[str, list[BacktestResult]] = {}
    for res in results:
        by_category.setdefault(res.category, []).append(res)

    allocations: dict[str, BookAllocation] = {}
    for category, group in by_category.items():
        returns = pd.concat([r.daily["book_return"] for r in group], axis=1)
        combined_return = returns.mean(axis=1)
        rf = config.risk_free_daily
        capital = config.capital_per_book
        daily = pd.DataFrame(index=combined_return.index)
        daily["book_return"] = combined_return
        daily["book_pnl"] = capital * combined_return
        daily["cash_return"] = rf
        daily["cash_pnl"] = capital * rf
        daily["cum_book_pnl"] = daily["book_pnl"].cumsum()
        daily["cum_cash_pnl"] = daily["cash_pnl"].cumsum()
        allocations[category] = BookAllocation(
            category=category,
            strategy_ids=[r.strategy_id for r in group],
            daily=daily,
        )
    return allocations
