"""Strategy specification.

A strategy is one of two single-boundary shapes (overnight or intraday), a side
(long or short), a ``select`` rule that picks tickers each day, and a ``regime``
gate that switches the strategy on or off based on market conditions.

Both ``select`` and ``regime`` receive only data available *before* the trade
date (a no-lookahead ``PriceData`` view), so they cannot peek at the future.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

CATEGORIES = ("overnight", "intraday")
SIDES = ("long", "short")


def select_all(history, universe: Sequence[str]) -> list[str]:
    """Default selection: hold the whole universe (no price signal used)."""
    return list(universe)


def always_on(history) -> bool:
    """Default regime: always active."""
    return True


@dataclass
class StrategySpec:
    name: str
    category: str  # "overnight" | "intraday"
    side: str  # "long" | "short"
    select: Callable = select_all
    regime: Callable = always_on

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"category must be one of {CATEGORIES}, got {self.category!r}")
        if self.side not in SIDES:
            raise ValueError(f"side must be one of {SIDES}, got {self.side!r}")

    @property
    def sign(self) -> float:
        return 1.0 if self.side == "long" else -1.0
