"""Build runnable strategies from specs and compute look-ahead-safe selections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from strategies.spec import DEFAULT_SPECS_DIR, StrategySpec, load_specs_dir


def _regime_mask(
    closes: pd.DataFrame, benchmark: str, gate: str | None
) -> pd.Series | None:
    """Boolean per-date series: True when the regime gate permits trading.

    The gate is evaluated on data **strictly before** the entry boundary by shifting one
    day (Design: "Regime gates ... are evaluated on data strictly prior to the entry
    boundary").
    """
    if gate is None:
        return None
    if benchmark not in closes.columns:
        # Without the benchmark we cannot evaluate the gate; default to flat (cash).
        return pd.Series(False, index=closes.index)
    bench = closes[benchmark]
    if gate == "spy_above_200dma":
        ma = bench.rolling(200, min_periods=200).mean()
        mask = bench > ma
    elif gate == "spy_above_50dma":
        ma = bench.rolling(50, min_periods=50).mean()
        mask = bench > ma
    else:
        raise ValueError(f"unknown regime_gate: {gate!r}")
    return mask.shift(1).fillna(False)


@dataclass
class Strategy:
    """A runnable strategy: a spec plus its look-ahead-safe selection logic."""

    spec: StrategySpec
    benchmark: str = "SPY"

    @property
    def id(self) -> str:
        return self.spec.id

    @property
    def category(self) -> str:
        return self.spec.category

    @property
    def side(self) -> str:
        return self.spec.side

    def select(self, closes: pd.DataFrame, volumes: pd.DataFrame | None = None) -> pd.DataFrame:
        """Return a (dates x symbols) weight frame, look-ahead-safe.

        Selected names carry weight 1.0; the engine equal-weights and enforces the
        per-boundary trade cap. All signals are shifted one day so a row for date ``D``
        uses only information available through the prior close.
        """
        params = self.spec.params
        top_n = int(params.get("top_n", 10))
        lookback = int(params.get("lookback", 20))
        selection = self.spec.selection

        if selection == "single":
            symbol = params.get("symbol", self.benchmark)
            weights = pd.DataFrame(0.0, index=closes.index, columns=closes.columns)
            if symbol in weights.columns:
                weights[symbol] = 1.0
        else:
            signal = closes.pct_change(lookback)
            # Enforce look-ahead: a date-D decision may use data only through D-1.
            signal = signal.shift(1)
            ascending = selection == "reversion"
            ranks = signal.rank(axis=1, ascending=ascending, method="first")
            weights = (ranks <= top_n).astype("float64")
            # Mask rows where the signal is undefined for every name.
            weights = weights.where(signal.notna().any(axis=1), 0.0)

        mask = _regime_mask(closes, self.benchmark, self.spec.regime_gate)
        if mask is not None:
            weights = weights.mul(mask.astype("float64"), axis=0)

        return weights.fillna(0.0)


def build_strategy(spec: StrategySpec, benchmark: str = "SPY") -> Strategy:
    return Strategy(spec=spec, benchmark=benchmark)


def load_reference_strategies(
    specs_dir: Path | str = DEFAULT_SPECS_DIR, benchmark: str = "SPY"
) -> list[Strategy]:
    """Load every spec under ``specs_dir`` as a runnable strategy."""
    return [build_strategy(spec, benchmark=benchmark) for spec in load_specs_dir(specs_dir)]
