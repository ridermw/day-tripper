"""Data providers: the abstraction behind which any EOD source can slot in.

- ``SyntheticProvider`` — deterministic, offline, for tests and demos.
- ``YFinanceProvider`` — dividend-adjusted live prices.
- ``FallbackProvider`` — ordered per-symbol fallback with provenance.
- ``CachingProvider`` — parquet prices plus their source manifest.
"""

from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Protocol, Sequence

import numpy as np
import pandas as pd

from daytripper.prices import PriceData

try:
    import yfinance as yf
except ImportError:  # Optional outside scheduled live-data runs.
    yf = None


class Provider(Protocol):
    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData: ...


class SyntheticProvider:
    """Deterministic random-walk OHLC, seeded for reproducibility."""

    source_name = "synthetic"

    def __init__(
        self,
        seed: int = 0,
        start_price: float = 100.0,
        cash_tickers: Sequence[str] = (),
    ):
        self.seed = seed
        self.start_price = start_price
        self.cash_tickers = (
            {cash_tickers} if isinstance(cash_tickers, str) else set(cash_tickers)
        )

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        # Drop the BusinessDay freq so data round-trips identically through
        # parquet (which does not preserve the freq attribute) and matches what
        # real EOD providers return.
        dates = pd.DatetimeIndex(pd.bdate_range(start=start, end=end).values)
        n = len(dates)

        open_cols: dict[str, np.ndarray] = {}
        close_cols: dict[str, np.ndarray] = {}
        for ticker in tickers:
            seed_material = f"{self.seed}:{ticker}".encode()
            ticker_seed = int.from_bytes(hashlib.sha256(seed_material).digest()[:8])
            rng = np.random.default_rng(ticker_seed)
            if ticker in self.cash_tickers:
                daily_ret = rng.normal(0.00015, 0.00003, n)
                gap_volatility = 0.00002
            else:
                daily_ret = rng.normal(0.0, 0.01, n)
                gap_volatility = 0.005
            closes = self.start_price * np.cumprod(1.0 + daily_ret)
            gaps = rng.normal(0.0, gap_volatility, n)
            opens = np.empty(n)
            opens[0] = self.start_price
            opens[1:] = closes[:-1] * (1.0 + gaps[1:])
            open_cols[ticker] = opens
            close_cols[ticker] = closes

        opens_df = pd.DataFrame(open_cols, index=dates)
        closes_df = pd.DataFrame(close_cols, index=dates)
        return PriceData(opens=opens_df, closes=closes_df)


class YFinanceProvider:
    """Dividend-adjusted daily prices from Yahoo Finance."""

    source_name = "yfinance"

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        if yf is None:
            raise RuntimeError("yfinance is not installed")

        inclusive_end = str(pd.Timestamp(end) + timedelta(days=1))[:10]
        opens: dict[str, pd.Series] = {}
        closes: dict[str, pd.Series] = {}
        for ticker in tickers:
            frame = yf.download(
                ticker,
                start=str(start),
                end=inclusive_end,
                auto_adjust=True,
                progress=False,
            )
            if frame.empty:
                continue
            if isinstance(frame.columns, pd.MultiIndex):
                frame = frame.xs(ticker, axis=1, level=-1)
            opens[ticker] = frame["Open"]
            closes[ticker] = frame["Close"]

        if not opens:
            empty = pd.DataFrame(columns=list(tickers), index=pd.DatetimeIndex([]), dtype=float)
            return PriceData(opens=empty, closes=empty.copy())
        return PriceData(
            opens=pd.concat(opens, axis=1, join="inner").sort_index(),
            closes=pd.concat(closes, axis=1, join="inner").sort_index(),
        )


class FallbackProvider:
    """Try ordered providers per ticker and retain auditable provenance."""

    def __init__(self, providers: Sequence[Provider]):
        if not providers:
            raise ValueError("at least one provider is required")
        self.providers = list(providers)
        self.sources: dict[str, str] = {}

    @property
    def cache_key(self) -> str:
        return ",".join(
            getattr(provider, "source_name", type(provider).__name__)
            for provider in self.providers
        )

    @property
    def data_source(self) -> str:
        sources = sorted(set(self.sources.values()))
        return sources[0] if len(sources) == 1 else f"mixed: {', '.join(sources)}"

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        opens: dict[str, pd.Series] = {}
        closes: dict[str, pd.Series] = {}
        self.sources = {}
        for ticker in tickers:
            for provider in self.providers:
                try:
                    data = provider.fetch([ticker], start, end)
                except Exception:
                    continue
                if data.opens.empty or ticker not in data.tickers:
                    continue
                opens[ticker] = data.opens[ticker]
                closes[ticker] = data.closes[ticker]
                self.sources[ticker] = getattr(
                    provider, "source_name", type(provider).__name__
                )
                break
            else:
                raise RuntimeError(f"no provider returned prices for {ticker}")

        return PriceData(
            opens=pd.concat(opens, axis=1, join="inner").sort_index(),
            closes=pd.concat(closes, axis=1, join="inner").sort_index(),
        )


class CachingProvider:
    """Cache another provider's output to a parquet directory."""

    def __init__(self, underlying: Provider, cache_dir):
        self.underlying = underlying
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sources: dict[str, str] = {}

    @property
    def data_source(self) -> str:
        sources = sorted(set(self.sources.values()))
        return sources[0] if len(sources) == 1 else f"mixed: {', '.join(sources)}"

    def _key(self, tickers: Sequence[str], start: str, end: str) -> str:
        provider_key = getattr(
            self.underlying,
            "cache_key",
            getattr(self.underlying, "source_name", type(self.underlying).__name__),
        )
        raw = "|".join([provider_key, ",".join(tickers), start, end])
        return hashlib.md5(raw.encode()).hexdigest()

    def fetch(self, tickers: Sequence[str], start: str, end: str) -> PriceData:
        key = self._key(tickers, start, end)
        opens_path = self.cache_dir / f"{key}-opens.parquet"
        closes_path = self.cache_dir / f"{key}-closes.parquet"
        sources_path = self.cache_dir / f"{key}-sources.json"

        if opens_path.exists() and closes_path.exists() and sources_path.exists():
            self.sources = json.loads(sources_path.read_text())
            return PriceData(
                opens=pd.read_parquet(opens_path),
                closes=pd.read_parquet(closes_path),
            )

        data = self.underlying.fetch(tickers, start, end)
        self.sources = getattr(
            self.underlying,
            "sources",
            {ticker: getattr(self.underlying, "source_name", "unknown") for ticker in tickers},
        )
        if "synthetic" in self.sources.values():
            return data
        data.opens.to_parquet(opens_path)
        data.closes.to_parquet(closes_path)
        sources_path.write_text(json.dumps(self.sources, indent=2, sort_keys=True) + "\n")
        return data
