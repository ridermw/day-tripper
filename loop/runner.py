"""Orchestration for the three scheduled jobs."""

from __future__ import annotations

from datetime import UTC, date, datetime

from allocation.equal_weight import allocate_equal_weight
from dashboard.render import render_site
from data.cache import load_cached_history
from data.providers import SyntheticProvider, get_default_provider
from data.universe import default_universe
from engine.backtest import BacktestConfig, run_backtest
from engine.costs import CostModel
from loop.state import write_state
from scorer.metrics import cost_sensitivity_table, score_result
from strategies.library import load_reference_strategies


def _load_history(as_of: date, lookback_years: int, allow_network: bool):
    """Load OHLCV for the universe, returning (history, source_name, synthetic).

    Honesty rule: if the real source is unavailable for *any* requested symbol we mark
    the whole run synthetic, so a mixed/simulated result is never mislabelled as real.
    """
    universe = default_universe()
    start = date(as_of.year - lookback_years, as_of.month, as_of.day)
    provider = get_default_provider(allow_network=allow_network)
    history = load_cached_history(
        list(universe.symbols),
        start,
        as_of,
        provider=provider,
        allow_network=allow_network,
    )
    synthetic = isinstance(provider, SyntheticProvider)
    if not synthetic:
        # Detect per-symbol synthetic fallback: any missing symbol => label synthetic.
        if set(history) != set(universe.symbols):
            synthetic = True
    source = "synthetic" if synthetic else provider.name
    return history, source, synthetic


def _strategies():
    return load_reference_strategies()


def _intended_trades(history, strategies, categories) -> list[dict]:
    """The locked entries for the next boundary: the most recent selection row."""
    from engine.backtest import build_price_matrices

    closes = build_price_matrices(history)["close"]
    if closes.empty:
        return []
    trades: list[dict] = []
    for strat in strategies:
        if strat.category not in categories:
            continue
        weights = strat.select(closes)
        if weights.empty:
            continue
        last = weights.iloc[-1]
        for symbol, w in last.items():
            if w > 0:
                trades.append(
                    {
                        "strategy_id": strat.id,
                        "book": strat.category,
                        "side": strat.side,
                        "symbol": symbol,
                        "as_of": str(closes.index[-1].date()),
                    }
                )
    return trades


def run_post_close(
    as_of: date | None = None,
    allow_network: bool = True,
    lookback_years: int = 5,
    config: BacktestConfig | None = None,
    cost_model: CostModel | None = None,
    state_base=None,
    site_dir=None,
) -> dict:
    """Ingest data, backtest all strategies, score, allocate, and regenerate the site."""
    as_of = as_of or date.today()
    config = config or BacktestConfig()
    cost_model = cost_model or CostModel()
    history, source, synthetic = _load_history(as_of, lookback_years, allow_network)
    strategies = _strategies()

    results = [
        run_backtest(history, s, config=config, cost_model=cost_model, synthetic=synthetic)
        for s in strategies
    ]
    candidate_board = [score_result(r, config).to_dict() for r in results]
    allocations = allocate_equal_weight(results, config)

    books = {
        cat: {
            "total_pnl": alloc.total_pnl,
            "cash_pnl": alloc.cash_pnl,
            "strategy_ids": alloc.strategy_ids,
        }
        for cat, alloc in allocations.items()
    }
    cumulative = {
        cat: {
            "dates": [str(d.date()) for d in alloc.daily.index],
            "cum_book_pnl": alloc.daily["cum_book_pnl"].tolist(),
            "cum_cash_pnl": alloc.daily["cum_cash_pnl"].tolist(),
        }
        for cat, alloc in allocations.items()
    }
    sensitivity = {
        s.id: cost_sensitivity_table(
            history, s, base_cost=cost_model, config=config, synthetic=synthetic
        ).to_dict(orient="records")
        for s in strategies
    }
    intended = _intended_trades(history, strategies, {"overnight", "intraday"})

    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "as_of_date": str(as_of),
        "data_source": source,
        "synthetic": synthetic,
        "candidate_board": candidate_board,
        "books": books,
        "cumulative": cumulative,
        "cost_sensitivity": sensitivity,
        "intended_trades": intended,
    }
    write_state("latest_results", payload, base=state_base)
    render_site(payload, site_dir=site_dir) if site_dir else render_site(payload)
    return payload


def _run_boundary(job: str, category: str, as_of, allow_network, lookback_years, state_base):
    as_of = as_of or date.today()
    history, source, synthetic = _load_history(as_of, lookback_years, allow_network)
    strategies = _strategies()
    locked = _intended_trades(history, strategies, {category})
    payload = {
        "job": job,
        "generated_at": datetime.now(UTC).isoformat(),
        "as_of_date": str(as_of),
        "data_source": source,
        "synthetic": synthetic,
        "boundary": category,
        "locked_entries": locked,
    }
    write_state(f"locked_{category}", payload, base=state_base)
    return payload


def run_pre_close(
    as_of: date | None = None,
    allow_network: bool = True,
    lookback_years: int = 5,
    state_base=None,
) -> dict:
    """Lock overnight (close-side) entries before the close auction."""
    return _run_boundary(
        "pre-close", "overnight", as_of, allow_network, lookback_years, state_base
    )


def run_pre_open(
    as_of: date | None = None,
    allow_network: bool = True,
    lookback_years: int = 5,
    state_base=None,
) -> dict:
    """Lock intraday (open-side) entries before the open; resolve the prior overnight book."""
    payload = _run_boundary(
        "pre-open", "intraday", as_of, allow_network, lookback_years, state_base
    )
    # Resolve the prior overnight book: surface yesterday's locked overnight entries so
    # the pre-open job closes the loop on them (full P&L resolution is the post-close job).
    from loop.state import read_state

    prior = read_state("locked_overnight", base=state_base)
    payload["resolved_overnight"] = prior.get("locked_entries", []) if prior else []
    write_state("locked_intraday", payload, base=state_base)
    return payload
