"""Data layer: a provider abstraction with a deterministic synthetic source and
a parquet caching wrapper. No network — live providers slot in behind the same
interface in a follow-up.
"""

import pandas as pd
import pandas.testing as pdt
import pytest

from daytripper.prices import PriceData
from daytripper.data import (
    CachingProvider,
    FallbackProvider,
    SyntheticProvider,
    YFinanceProvider,
)


def test_synthetic_provider_returns_pricedata_for_universe():
    provider = SyntheticProvider(seed=0)

    data = provider.fetch(["AAA", "BBB"], start="2024-01-01", end="2024-01-31")

    assert isinstance(data, PriceData)
    assert data.tickers == ["AAA", "BBB"]
    assert len(data.dates) > 0
    assert (data.opens > 0).all().all()
    assert (data.closes > 0).all().all()


def test_synthetic_provider_is_deterministic():
    a = SyntheticProvider(seed=42).fetch(["AAA"], start="2024-01-01", end="2024-01-15")
    b = SyntheticProvider(seed=42).fetch(["AAA"], start="2024-01-01", end="2024-01-15")

    pdt.assert_frame_equal(a.opens, b.opens)
    pdt.assert_frame_equal(a.closes, b.closes)


def test_synthetic_provider_gives_each_ticker_distinct_stable_prices():
    provider = SyntheticProvider(seed=42)

    together = provider.fetch(["AAA", "BBB"], start="2024-01-01", end="2024-01-15")
    alone = provider.fetch(["BBB"], start="2024-01-01", end="2024-01-15")

    assert not together.closes["AAA"].equals(together.closes["BBB"])
    pdt.assert_series_equal(together.closes["BBB"], alone.closes["BBB"])


class _CountingProvider:
    """Underlying provider that records how many times it was hit."""

    source_name = "real"

    def __init__(self):
        self.calls = 0

    def fetch(self, tickers, start, end) -> PriceData:
        self.calls += 1
        return SyntheticProvider(seed=1).fetch(tickers, start, end)


def test_caching_provider_reads_from_cache_on_second_call(tmp_path):
    underlying = _CountingProvider()
    cached = CachingProvider(underlying, cache_dir=tmp_path)

    first = cached.fetch(["AAA", "BBB"], start="2024-01-01", end="2024-01-31")
    second = cached.fetch(["AAA", "BBB"], start="2024-01-01", end="2024-01-31")

    assert underlying.calls == 1  # second call served from parquet cache
    assert cached.sources == {"AAA": "real", "BBB": "real"}
    assert cached.data_source == "real"
    pdt.assert_frame_equal(first.opens, second.opens)
    pdt.assert_frame_equal(first.closes, second.closes)


class _EmptyProvider:
    source_name = "empty"

    def fetch(self, tickers, start, end) -> PriceData:
        empty = pd.DataFrame(columns=list(tickers), index=pd.DatetimeIndex([]), dtype=float)
        return PriceData(opens=empty, closes=empty.copy())


class _WorkingProvider:
    source_name = "real"

    def fetch(self, tickers, start, end) -> PriceData:
        return SyntheticProvider(seed=1).fetch(tickers, start, end)


def test_fallback_provider_records_actual_source_per_ticker():
    provider = FallbackProvider([_EmptyProvider(), _WorkingProvider()])

    data = provider.fetch(["AAA", "BBB"], start="2024-01-01", end="2024-01-05")

    assert data.tickers == ["AAA", "BBB"]
    assert provider.sources == {"AAA": "real", "BBB": "real"}
    assert provider.data_source == "real"


def test_fallback_provider_discloses_any_synthetic_prices():
    provider = FallbackProvider([_EmptyProvider(), SyntheticProvider(seed=1)])

    provider.fetch(["AAA"], start="2024-01-01", end="2024-01-05")

    assert provider.sources == {"AAA": "synthetic"}
    assert "synthetic" in provider.data_source


def test_caching_provider_does_not_persist_synthetic_fallback(tmp_path):
    fallback = FallbackProvider([_EmptyProvider(), SyntheticProvider(seed=1)])
    cached = CachingProvider(fallback, cache_dir=tmp_path)

    cached.fetch(["AAA"], start="2024-01-01", end="2024-01-05")

    assert list(tmp_path.iterdir()) == []


def test_yfinance_requests_inclusive_end_and_adjusted_prices(monkeypatch):
    calls = {}
    index = pd.to_datetime(["2024-01-02"])
    downloaded = pd.DataFrame(
        {
            "Open": [100.0],
            "Close": [101.0],
        },
        index=index,
    )

    class _YF:
        @staticmethod
        def download(ticker, **kwargs):
            calls["ticker"] = ticker
            calls.update(kwargs)
            return downloaded

    monkeypatch.setattr("daytripper.data.providers.yf", _YF)

    data = YFinanceProvider().fetch(["SGOV"], "2024-01-01", "2024-01-02")

    assert calls["end"] == "2024-01-03"
    assert calls["auto_adjust"] is True
    assert data.closes.at[index[0], "SGOV"] == 101.0
