"""End-to-end Phase 1 demo: synthetic data -> engine -> candidate board.

Run it with:  python -m daytripper.demo

This wires the tested pieces together so the loop produces a visible, ranked
candidate board (ungraded) with every strategy measured against the risk-free
cash baseline. It uses the offline synthetic provider, so it runs anywhere.
"""

from __future__ import annotations

import tempfile

from daytripper.board import candidate_board
from daytripper.costs import CostModel
from daytripper.data import CachingProvider, SyntheticProvider
from daytripper.engine import run_backtest
from daytripper.strategy import StrategySpec

UNIVERSE = ["ETFA", "ETFB", "ETFC", "ETFD", "ETFE"]
CAPITAL = 10_000.0
COST = CostModel(commission_bps=2.0, slippage_bps=3.0)
RISK_FREE_ANNUAL = 0.04


def momentum_select(history, universe):
    """Hold names whose last close rose vs the prior close (no lookahead)."""
    if len(history.dates) < 2:
        return []
    last = history.closes.iloc[-1]
    prev = history.closes.iloc[-2]
    return [t for t in universe if last[t] > prev[t]]


def uptrend_regime(history):
    """Active only when the recent window is trending up."""
    if len(history.dates) < 5:
        return False
    window = history.closes.iloc[-5:]
    return bool(window.iloc[-1].mean() >= window.iloc[0].mean())


def main() -> None:
    with tempfile.TemporaryDirectory() as cache_dir:
        provider = CachingProvider(SyntheticProvider(seed=7), cache_dir=cache_dir)
        prices = provider.fetch(UNIVERSE, start="2024-01-01", end="2024-03-31")

        strategies = [
            StrategySpec(name="overnight-long-all", category="overnight", side="long"),
            StrategySpec(
                name="intraday-momentum",
                category="intraday",
                side="long",
                select=momentum_select,
            ),
            StrategySpec(
                name="overnight-uptrend-gated",
                category="overnight",
                side="long",
                regime=uptrend_regime,
            ),
        ]

        results = {
            spec.name: run_backtest(
                prices,
                spec,
                capital=CAPITAL,
                cost_model=COST,
                risk_free_annual=RISK_FREE_ANNUAL,
            )
            for spec in strategies
        }

        board = candidate_board(results)
        print(f"\nday-tripper Phase 1 candidate board  (capital ${CAPITAL:,.0f}/day)")
        print(f"universe={UNIVERSE}  bars={len(prices.dates)}  "
              f"cost={COST.commission_bps + COST.slippage_bps:.0f}bps/fill\n")
        print(board.to_string(index=False))
        print("\nNote: candidate board only — the falsification gauntlet "
              "(DSR/PBO/walk-forward) is a later phase.\n")


if __name__ == "__main__":
    main()
