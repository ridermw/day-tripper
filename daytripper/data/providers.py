"""Data providers: the abstraction behind which any EOD source can slot in.

- ``SyntheticProvider`` — deterministic, offline, for tests and demos.
- ``CachingProvider`` — wraps any provider and caches results to parquet so
  backtests are reproducible and offline-capable.

Live providers (Stooq, yfinance) implement the same ``fetch`` signature and are
a follow-up; nothing else in the engine needs to change when they land.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
import pandas as pd

from daytripper.prices import PriceData


class Provider(Protocol):
    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData: ...


class SyntheticProvider:
    """Deterministic random-walk OHLC, seeded for reproducibility."""

    def __init__(self, seed: int = 0, start_price: float = 100.0):
        self.seed = seed
        self.start_price = start_price

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        # Drop the BusinessDay freq so data round-trips identically through
        # parquet (which does not preserve the freq attribute) and matches what
        # real EOD providers return.
        dates = pd.DatetimeIndex(pd.bdate_range(start=start, end=end).values)
        rng = np.random.default_rng(self.seed)
        n = len(dates)

        open_cols: dict[str, np.ndarray] = {}
        close_cols: dict[str, np.ndarray] = {}
        for ticker in tickers:
            daily_ret = rng.normal(0.0, 0.01, n)
            closes = self.start_price * np.cumprod(1.0 + daily_ret)
            gaps = rng.normal(0.0, 0.005, n)
            opens = np.empty(n)
            opens[0] = self.start_price
            opens[1:] = closes[:-1] * (1.0 + gaps[1:])
            open_cols[ticker] = opens
            close_cols[ticker] = closes

        opens_df = pd.DataFrame(open_cols, index=dates)
        closes_df = pd.DataFrame(close_cols, index=dates)
        return PriceData(opens=opens_df, closes=closes_df)


class CachingProvider:
    """Cache another provider's output to a parquet directory."""

    def __init__(self, underlying: Provider, cache_dir):
        self.underlying = underlying
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, tickers: Sequence[str], start: str, end: str) -> str:
        raw = "|".join([",".join(tickers), start, end])
        return hashlib.md5(raw.encode()).hexdigest()

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        key = self._key(tickers, start, end)
        opens_path = self.cache_dir / f"{key}-opens.parquet"
        closes_path = self.cache_dir / f"{key}-closes.parquet"

        if opens_path.exists() and closes_path.exists():
            return PriceData(
                opens=pd.read_parquet(opens_path),
                closes=pd.read_parquet(closes_path),
            )

        data = self.underlying.fetch(tickers, start, end)
        data.opens.to_parquet(opens_path)
        data.closes.to_parquet(closes_path)
        return data
