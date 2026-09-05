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
from pathlib import Path
from typing import Sequence

import pandas as pd

from daytripper.board import candidate_board
from daytripper.costs import CostModel
from daytripper.data import (
    CachingProvider,
    FallbackProvider,
    SyntheticProvider,
    YFinanceProvider,
)
from daytripper.dashboard import render_dashboard
from daytripper.data.providers import Provider
from daytripper.engine import BacktestResult, run_backtest
from daytripper.strategy import StrategySpec

DEFAULT_UNIVERSE = ["SPY", "QQQ", "IWM", "DIA", "TLT"]
DEFAULT_CAPITAL = 10_000.0
DEFAULT_COST = CostModel(commission_bps=2.0, slippage_bps=3.0)
DEFAULT_CASH_TICKER = "SGOV"


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
    cash_ticker: str,
    generated: str | None,
    data_source: str | None = None,
) -> RunArtifacts:
    requested_tickers = list(dict.fromkeys([*universe, cash_ticker]))
    prices = provider.fetch(requested_tickers, start, end)
    actual_source = getattr(provider, "data_source", data_source or "unknown")
    sources = getattr(provider, "sources", {})
    cash_source = sources.get(
        cash_ticker,
        getattr(provider, "source_name", actual_source),
    )
    if generated is None:
        generated = f"{prices.dates[-1].date().isoformat()}T00:00:00Z"
    results = {
        spec.name: run_backtest(
            prices,
            spec,
            capital=capital,
            cost_model=cost_model,
            cash_ticker=cash_ticker,
        )
        for spec in strategies
    }
    board = candidate_board(results)
    meta = {
        "capital": capital,
        "universe": list(universe),
        "bars": len(prices.dates),
        "generated": generated,
        "data_source": actual_source,
        "cash_ticker": cash_ticker,
        "cash_source": cash_source,
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
    offline = "--offline" in argv
    positional = [arg for arg in argv if not arg.startswith("--")]
    out_dir = positional[0] if positional else "docs"

    cache = Path(".cache/prices")
    sources = [SyntheticProvider(seed=7, cash_tickers=[DEFAULT_CASH_TICKER])]
    if not offline:
        sources.insert(0, YFinanceProvider())
    provider = CachingProvider(FallbackProvider(sources), cache_dir=cache)
    end = pd.Timestamp.now(tz="UTC").date()
    start = max(
        pd.Timestamp(end) - pd.DateOffset(years=5),
        pd.Timestamp("2020-05-26"),
    ).date()

    artifacts = run_once(
        provider,
        default_strategies(),
        universe=DEFAULT_UNIVERSE,
        start=start.isoformat(),
        end=end.isoformat(),
        capital=DEFAULT_CAPITAL,
        cost_model=DEFAULT_COST,
        cash_ticker=DEFAULT_CASH_TICKER,
        generated=None,
    )
    write_artifacts(artifacts, out_dir)
    print(f"wrote dashboard to {out_dir}/index.html and {out_dir}/board.csv")


if __name__ == "__main__":
    main()
