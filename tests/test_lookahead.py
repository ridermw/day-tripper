"""No-lookahead: selection for trade date t sees only data strictly before t."""

import pandas as pd

from daytripper.prices import PriceData
from daytripper.strategy import StrategySpec
from daytripper.costs import CostModel
from daytripper.engine import run_backtest


def test_selector_never_sees_current_or_future_dates():
    idx = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    opens = pd.DataFrame({"AAA": [100.0, 100.0, 100.0]}, index=idx)
    closes = pd.DataFrame({"AAA": [110.0, 110.0, 110.0]}, index=idx)
    prices = PriceData(opens=opens, closes=closes)

    seen_history_dates: list[list] = []

    def recording_select(history, universe):
        seen_history_dates.append(list(history.dates))
        return list(universe)

    spec = StrategySpec(
        name="id", category="intraday", side="long", select=recording_select
    )

    run_backtest(prices, spec, capital=10_000.0, cost_model=CostModel(0.0, 0.0))

    # Trade date d0 sees nothing; d1 sees [d0]; d2 sees [d0, d1]. Never the
    # current trade date or anything after it.
    assert seen_history_dates[0] == []
    assert seen_history_dates[1] == [pd.Timestamp("2024-01-02")]
    assert seen_history_dates[2] == [
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2024-01-03"),
    ]
