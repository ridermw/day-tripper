"""Candidate board: summarize backtest results and rank them vs the cash baseline."""

import pandas as pd

from daytripper.engine import BacktestResult
from daytripper.board import summarize_result, candidate_board


def _result(net_pnl: float, n_trades: int, cash_pnl: float) -> BacktestResult:
    trades = pd.DataFrame({"net_pnl": [net_pnl / n_trades] * n_trades})
    daily_pnl = pd.Series([net_pnl], dtype=float)
    cash_baseline = pd.Series([cash_pnl], dtype=float)
    return BacktestResult(
        trades=trades, daily_pnl=daily_pnl, cash_baseline=cash_baseline, total_pnl=net_pnl
    )


def test_summarize_reports_trades_pnl_and_beats_cash():
    res = _result(net_pnl=500.0, n_trades=3, cash_pnl=2.0)

    row = summarize_result("s1", res)

    assert row["strategy"] == "s1"
    assert row["n_trades"] == 3
    assert row["net_pnl"] == 500.0
    assert row["cash_pnl"] == 2.0
    assert row["beats_cash"] is True


def test_summarize_marks_loser_against_cash():
    res = _result(net_pnl=-50.0, n_trades=2, cash_pnl=2.0)

    row = summarize_result("dud", res)

    assert row["beats_cash"] is False


def test_candidate_board_sorts_by_net_pnl_desc():
    board = candidate_board(
        {
            "low": _result(net_pnl=10.0, n_trades=1, cash_pnl=2.0),
            "high": _result(net_pnl=900.0, n_trades=1, cash_pnl=2.0),
        }
    )

    assert list(board["strategy"]) == ["high", "low"]
