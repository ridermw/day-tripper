"""Explicit commission + slippage model.

Design ("Fill realism" / "Cost model calibration"): do **not** assume the official
open/close is achievable. Charge, per fill (side):

    commission_bps  -- broker/exchange commission
    slippage_bps    -- fixed conservative slippage
    impact term     -- liquidity-scaled: grows as trade notional approaches a name's
                       average daily dollar volume

A single-boundary trade has two fills (entry + exit), so the round-trip cost is twice the
per-side cost. Every published result must carry a sensitivity table across cost
assumptions (Design: "publish a sensitivity table across cost assumptions").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_BPS = 1.0 / 10_000.0


@dataclass(frozen=True)
class CostModel:
    """Per-fill cost model expressed in basis points of traded notional.

    Attributes
    ----------
    commission_bps:
        Commission charged on each fill (one side).
    slippage_bps:
        Fixed slippage charged on each fill, independent of size.
    impact_coef:
        Coefficient on the square-root liquidity-impact term. The impact (in bps) for a
        fill is ``impact_coef * sqrt(notional / adv_dollar) * 1e4``. Set to 0 to disable.
    """

    commission_bps: float = 1.0
    slippage_bps: float = 5.0
    impact_coef: float = 0.1

    def per_side_fraction(
        self,
        notional: float | np.ndarray = 0.0,
        adv_dollar: float | np.ndarray | None = None,
    ) -> float | np.ndarray:
        """Cost of a single fill as a fraction of notional."""
        fixed = (self.commission_bps + self.slippage_bps) * _BPS
        if adv_dollar is None or self.impact_coef == 0.0:
            return fixed
        adv = np.asarray(adv_dollar, dtype="float64")
        adv = np.where(adv <= 0.0, np.nan, adv)
        impact = self.impact_coef * np.sqrt(np.asarray(notional, dtype="float64") / adv)
        impact = np.nan_to_num(impact, nan=0.0)
        return fixed + impact

    def round_trip_fraction(
        self,
        notional: float | np.ndarray = 0.0,
        adv_dollar: float | np.ndarray | None = None,
    ) -> float | np.ndarray:
        """Cost of an entry + exit (a full single-boundary trade) as a fraction."""
        return 2.0 * self.per_side_fraction(notional, adv_dollar)

    def scaled(self, factor: float) -> CostModel:
        """Return a copy with commission and slippage scaled (for sensitivity tables)."""
        return CostModel(
            commission_bps=self.commission_bps * factor,
            slippage_bps=self.slippage_bps * factor,
            impact_coef=self.impact_coef * factor,
        )


# Multipliers used to publish the mandatory cost-sensitivity table with every result.
COST_SENSITIVITY_GRID: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 3.0)
