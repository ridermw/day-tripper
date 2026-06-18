"""Dashboard rendering: a candidate board DataFrame -> static HTML string."""

import pandas as pd

from daytripper.dashboard import render_dashboard


def _board() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"strategy": "alpha", "n_trades": 10, "net_pnl": 123.45, "cash_pnl": 5.0, "beats_cash": True},
            {"strategy": "dud", "n_trades": 4, "net_pnl": -50.0, "cash_pnl": 5.0, "beats_cash": False},
        ]
    )


def _meta() -> dict:
    return {
        "capital": 10_000.0,
        "universe": ["ETFA", "ETFB"],
        "bars": 65,
        "generated": "2026-06-18T00:00:00Z",
        "data_source": "synthetic",
    }


def test_render_is_html_with_title_and_thesis():
    html = render_dashboard(_board(), _meta())

    assert "<html" in html.lower()
    assert "day-tripper" in html.lower()
    assert "Candidate board" in html
    # The thesis must be visible: strategies are measured against cash.
    assert "cash" in html.lower()


def test_render_lists_every_strategy_and_value():
    html = render_dashboard(_board(), _meta())

    assert "alpha" in html
    assert "dud" in html
    assert "123.45" in html  # net_pnl, 2dp
    assert "-50.00" in html


def test_render_marks_beats_cash_and_discloses_data_source():
    html = render_dashboard(_board(), _meta())

    assert "✓" in html  # alpha beats cash
    assert "✗" in html  # dud does not
    # Honesty: the dashboard says what data it ran on.
    assert "synthetic" in html
