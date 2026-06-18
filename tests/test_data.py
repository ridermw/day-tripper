"""Data layer: a provider abstraction with a deterministic synthetic source and
a parquet caching wrapper. No network — live providers slot in behind the same
interface in a follow-up.
"""

import pandas as pd
import pandas.testing as pdt
import pytest

from daytripper.prices import PriceData
from daytripper.data import SyntheticProvider, CachingProvider


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


class _CountingProvider:
    """Underlying provider that records how many times it was hit."""

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
    pdt.assert_frame_equal(first.opens, second.opens)
    pdt.assert_frame_equal(first.closes, second.closes)
