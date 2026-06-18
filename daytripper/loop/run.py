"""One pass of the loop: fetch prices, backtest every strategy, build the
candidate board, and render the dashboard. Writing artifacts is a thin,
separate step so the orchestration stays testable.

In Phase 1 there is no live execution, so this is a single post-close publish
pass on EOD data. The pre-open / pre-close entry-locking jobs in the design
activate with paper execution (a later phase); wiring three empty schedules now
would be cargo-cult.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

import pandas as pd

from daytripper.board import candidate_board
from daytripper.costs import CostModel
from daytripper.data import CachingProvider, SyntheticProvider
from daytripper.dashboard import render_dashboard
from daytripper.data.providers import Provider
from daytripper.engine import BacktestResult, run_backtest
from daytripper.strategy import StrategySpec

DEFAULT_UNIVERSE = ["ETFA", "ETFB", "ETFC", "ETFD", "ETFE"]
DEFAULT_CAPITAL = 10_000.0
DEFAULT_COST = CostModel(commission_bps=2.0, slippage_bps=3.0)
DEFAULT_RISK_FREE = 0.04


@dataclass
class RunArtifacts:
    board: pd.DataFrame
    html: str
    results: dict[str, BacktestResult]


def run_once(
    provider: Provider,
    strategies: Sequence[StrategySpec],
    *,
    universe: Sequence[str],
    start: str,
    end: str,
    capital: float,
    cost_model: CostModel,
    risk_free_annual: float,
    generated: str,
    data_source: str = "synthetic",
) -> RunArtifacts:
    prices = provider.fetch(list(universe), start, end)
    results = {
        spec.name: run_backtest(
            prices,
            spec,
            capital=capital,
            cost_model=cost_model,
            risk_free_annual=risk_free_annual,
        )
        for spec in strategies
    }
    board = candidate_board(results)
    meta = {
        "capital": capital,
        "universe": list(universe),
        "bars": len(prices.dates),
        "generated": generated,
        "data_source": data_source,
    }
    html = render_dashboard(board, meta)
    return RunArtifacts(board=board, html=html, results=results)


def write_artifacts(artifacts: RunArtifacts, out_dir) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(artifacts.html)
    artifacts.board.to_csv(out / "board.csv", index=False)


def default_strategies() -> list[StrategySpec]:
    return [
        StrategySpec(name="overnight-long-all", category="overnight", side="long"),
        StrategySpec(name="intraday-long-all", category="intraday", side="long"),
        StrategySpec(name="overnight-short-all", category="overnight", side="short"),
    ]


def main(argv: Sequence[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = argv[0] if argv else "docs"

    cache = Path(".cache/prices")
    provider = CachingProvider(SyntheticProvider(seed=7), cache_dir=cache)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    artifacts = run_once(
        provider,
        default_strategies(),
        universe=DEFAULT_UNIVERSE,
        start="2024-01-01",
        end="2024-03-31",
        capital=DEFAULT_CAPITAL,
        cost_model=DEFAULT_COST,
        risk_free_annual=DEFAULT_RISK_FREE,
        generated=generated,
        data_source="synthetic (offline) — live providers pending",
    )
    write_artifacts(artifacts, out_dir)
    print(f"wrote dashboard to {out_dir}/index.html and {out_dir}/board.csv")


if __name__ == "__main__":
    main()
