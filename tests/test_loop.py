"""Dashboard rendering + full loop orchestration tests (offline/deterministic)."""

from __future__ import annotations

from datetime import date

from dashboard.render import render_html, render_site
from loop.runner import run_post_close, run_pre_close, run_pre_open


def _sample_results() -> dict:
    return {
        "generated_at": "2021-12-31T00:00:00Z",
        "as_of_date": "2021-12-31",
        "data_source": "synthetic",
        "synthetic": True,
        "candidate_board": [
            {
                "strategy_id": "s1", "category": "overnight", "side": "long",
                "n_days": 100, "n_trades": 50, "total_pnl": -10.0, "cash_pnl": 5.0,
                "excess_pnl": -15.0, "sharpe": -0.2, "beats_cash": False,
            }
        ],
        "books": {
            "overnight": {"total_pnl": -10.0, "cash_pnl": 5.0, "strategy_ids": ["s1"]}
        },
        "cumulative": {"overnight": {"cum_book_pnl": [0.0, -5.0, -10.0]}},
        "cost_sensitivity": {
            "s1": [
                {"cost_multiplier": 1.0, "total_pnl": -10.0, "excess_pnl": -15.0,
                 "beats_cash": False}
            ]
        },
        "intended_trades": [
            {"strategy_id": "s1", "book": "overnight", "side": "long", "symbol": "SPY"}
        ],
    }


def test_render_html_contains_sections():
    html = render_html(_sample_results())
    assert "Candidate board" in html
    assert "SYNTHETIC DATA" in html
    assert "<svg" in html
    assert "No real money" in html


def test_render_site_writes_files(tmp_path):
    index = render_site(_sample_results(), site_dir=tmp_path)
    assert index.exists()
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / ".nojekyll").exists()


def test_post_close_offline(tmp_path):
    payload = run_post_close(
        as_of=date(2021, 12, 31),
        allow_network=False,
        lookback_years=3,
        state_base=tmp_path / "state",
        site_dir=tmp_path / "site",
    )
    assert payload["synthetic"] is True
    assert payload["data_source"] == "synthetic"
    assert set(payload["books"]) == {"overnight", "intraday"}
    # Both books carry a cash baseline to clear.
    for book in payload["books"].values():
        assert book["cash_pnl"] > 0
    assert (tmp_path / "state" / "latest_results.json").exists()
    assert (tmp_path / "site" / "index.html").exists()
    assert payload["candidate_board"]


def test_pre_close_locks_overnight(tmp_path):
    payload = run_pre_close(
        as_of=date(2021, 12, 31), allow_network=False, lookback_years=3,
        state_base=tmp_path / "state",
    )
    assert payload["boundary"] == "overnight"
    assert all(t["book"] == "overnight" for t in payload["locked_entries"])
    assert (tmp_path / "state" / "locked_overnight.json").exists()


def test_pre_open_locks_intraday_and_resolves(tmp_path):
    state_base = tmp_path / "state"
    run_pre_close(
        as_of=date(2021, 12, 31), allow_network=False, lookback_years=3,
        state_base=state_base,
    )
    payload = run_pre_open(
        as_of=date(2021, 12, 31), allow_network=False, lookback_years=3,
        state_base=state_base,
    )
    assert payload["boundary"] == "intraday"
    assert all(t["book"] == "intraday" for t in payload["locked_entries"])
    # The prior overnight book is surfaced for resolution.
    assert "resolved_overnight" in payload
