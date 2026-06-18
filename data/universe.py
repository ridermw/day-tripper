"""The tradable universe.

Phase 1 starts with liquid ETFs only (see docs/DESIGN.md, "Phasing"). Single-name
equities are added in later phases once point-in-time membership and borrow assumptions
exist. SPY doubles as the regime benchmark (e.g. SPY > 200DMA gate).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Liquid US-listed ETFs: broad index, sector, and asset-class exposure. These are chosen
# for deep liquidity so the cost/slippage model is credible (Design: "Universe liquidity
# floor"). The regime benchmark (SPY) is always included.
LIQUID_ETF_UNIVERSE: tuple[str, ...] = (
    "SPY",  # S&P 500
    "QQQ",  # Nasdaq 100
    "IWM",  # Russell 2000
    "DIA",  # Dow 30
    "EFA",  # Developed ex-US
    "EEM",  # Emerging markets
    "TLT",  # Long Treasuries
    "IEF",  # 7-10y Treasuries
    "LQD",  # IG corporate bonds
    "HYG",  # High-yield bonds
    "GLD",  # Gold
    "XLF",  # Financials
    "XLK",  # Technology
    "XLE",  # Energy
    "XLV",  # Health care
)

# The benchmark used by regime gates and as the market reference on the dashboard.
REGIME_BENCHMARK: str = "SPY"


@dataclass(frozen=True)
class Universe:
    """A named set of symbols with a minimum dollar-volume liquidity floor.

    The liquidity floor is informational in Phase 1 (the seed universe is already liquid)
    but is carried through so later phases can screen single names. See Design,
    "Universe liquidity floor".
    """

    symbols: tuple[str, ...] = field(default=LIQUID_ETF_UNIVERSE)
    name: str = "liquid_etfs"
    min_dollar_volume: float = 5_000_000.0

    def __post_init__(self) -> None:
        if REGIME_BENCHMARK not in self.symbols:
            object.__setattr__(self, "symbols", (REGIME_BENCHMARK, *self.symbols))

    def __iter__(self):
        return iter(self.symbols)

    def __len__(self) -> int:
        return len(self.symbols)


def default_universe() -> Universe:
    """The Phase 1 liquid-ETF universe."""
    return Universe()
