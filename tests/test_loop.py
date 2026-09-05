"""Loop orchestration: fetch -> backtest -> board -> artifacts."""

import pandas as pd

from daytripper.costs import CostModel
from daytripper.data import FallbackProvider, SyntheticProvider
from daytripper.strategy import StrategySpec
from daytripper.loop.run import run_once, write_artifacts


def _strategies():
    return [
        StrategySpec(name="overnight-long", category="overnight", side="long"),
        StrategySpec(name="intraday-long", category="intraday", side="long"),
    ]


def test_run_once_produces_board_html_and_results():
    artifacts = run_once(
        SyntheticProvider(seed=3),
        _strategies(),
        universe=["ETFA", "ETFB", "ETFC", "SGOV"],
        start="2024-01-01",
        end="2024-02-29",
        capital=10_000.0,
        cost_model=CostModel(2.0, 3.0),
        cash_ticker="SGOV",
        generated="2026-06-18T00:00:00Z",
        data_source="synthetic",
    )

    assert isinstance(artifacts.board, pd.DataFrame)
    assert len(artifacts.board) == 2
    assert set(artifacts.results) == {"overnight-long", "intraday-long"}
    assert "day-tripper" in artifacts.html.lower()
    assert "synthetic" in artifacts.html
    assert "SGOV" in artifacts.html


def test_write_artifacts_writes_html_and_csv(tmp_path):
    artifacts = run_once(
        SyntheticProvider(seed=3),
        _strategies(),
        universe=["ETFA", "ETFB"],
        start="2024-01-01",
        end="2024-01-31",
        capital=10_000.0,
        cost_model=CostModel(2.0, 3.0),
        cash_ticker="SGOV",
        generated="2026-06-18T00:00:00Z",
    )

    write_artifacts(artifacts, tmp_path)

    index = tmp_path / "index.html"
    board_csv = tmp_path / "board.csv"
    assert index.exists()
    assert board_csv.exists()
    assert "day-tripper" in index.read_text().lower()
    assert "overnight-long" in board_csv.read_text()


class _EmptyRealProvider:
    source_name = "real"

    def fetch(self, tickers, start, end):
        empty = pd.DataFrame(columns=tickers, index=pd.DatetimeIndex([]), dtype=float)
        from daytripper.prices import PriceData

        return PriceData(opens=empty, closes=empty.copy())


def test_run_once_discloses_synthetic_fallback_and_stable_generation_date():
    provider = FallbackProvider([_EmptyRealProvider(), SyntheticProvider(seed=3)])

    artifacts = run_once(
        provider,
        _strategies(),
        universe=["ETFA", "ETFB"],
        start="2024-01-01",
        end="2024-01-31",
        capital=10_000.0,
        cost_model=CostModel(2.0, 3.0),
        cash_ticker="SGOV",
        generated=None,
        data_source="real",
    )

    assert "data: synthetic" in artifacts.html
    assert "generated: 2024-01-31T00:00:00Z" in artifacts.html
