"""Daily OHLC price panel.

The whole engine rests on one fact: because every strategy is single-boundary
(close->open or open->close), daily open and close prices fully determine every
trade's P&L. So prices are just two aligned frames — opens and closes — indexed
by date with one column per ticker.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PriceData:
    opens: pd.DataFrame
    closes: pd.DataFrame

    def __post_init__(self) -> None:
        if not self.opens.index.equals(self.closes.index):
            raise ValueError("opens and closes must share the same date index")
        if list(self.opens.columns) != list(self.closes.columns):
            raise ValueError("opens and closes must share the same tickers")

    @property
    def dates(self) -> pd.DatetimeIndex:
        return self.opens.index

    @property
    def tickers(self) -> list[str]:
        return list(self.opens.columns)

    def before(self, date) -> "PriceData":
        """Return a view containing only data strictly before ``date``.

        This is the no-lookahead boundary: decisions for a trade on ``date``
        may only see prices from earlier dates.
        """
        mask = self.opens.index < date
        return PriceData(opens=self.opens.loc[mask], closes=self.closes.loc[mask])
