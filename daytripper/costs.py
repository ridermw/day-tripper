"""Transaction-cost model.

Costs are the core of this engine, not a footnote: the gross overnight edge is
largely eaten by costs, so a backtest without them is a noise generator. This is
a deliberately conservative flat round-trip model (commission + slippage, in
basis points, charged on entry and exit). A liquidity-scaled slippage term is a
documented follow-up.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    commission_bps: float = 0.0
    slippage_bps: float = 0.0

    def round_trip_cost(self, notional: float) -> float:
        """Total cost to open and close a position of the given notional."""
        per_fill = abs(notional) * (self.commission_bps + self.slippage_bps) / 10_000.0
        return 2.0 * per_fill
