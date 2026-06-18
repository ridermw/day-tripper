"""Candidate board: turn raw backtest results into a ranked, comparable table.

In Phase 1 this is a *candidate* board (ungraded) — the falsification gauntlet
(purged walk-forward, Deflated Sharpe, PBO) that promotes survivors to the real
leaderboard is a later phase. The one judgment encoded here is the project's
baseline rule: did the strategy beat cash?
"""

from __future__ import annotations

import pandas as pd

from daytripper.engine import BacktestResult


def summarize_result(name: str, result: BacktestResult) -> dict:
    net_pnl = float(result.total_pnl)
    cash_pnl = float(result.cash_baseline.sum())
    return {
        "strategy": name,
        "n_trades": int(len(result.trades)),
        "net_pnl": net_pnl,
        "cash_pnl": cash_pnl,
        "beats_cash": bool(net_pnl > cash_pnl),
    }


def candidate_board(results: dict[str, BacktestResult]) -> pd.DataFrame:
    rows = [summarize_result(name, res) for name, res in results.items()]
    board = pd.DataFrame(rows)
    return board.sort_values("net_pnl", ascending=False).reset_index(drop=True)
