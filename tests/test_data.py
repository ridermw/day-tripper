"""Provider abstraction + universe + cache tests."""

from __future__ import annotations

from datetime import date

import pandas as pd

from data.cache import ParquetCache, load_cached_history
from data.providers import OHLCV_COLUMNS, SyntheticProvider, load_history
from data.universe import LIQUID_ETF_UNIVERSE, REGIME_BENCHMARK, Universe


def test_synthetic_is_deterministic():
    p1 = SyntheticProvider().fetch("SPY", date(2020, 1, 1), date(2020, 6, 1))
    p2 = SyntheticProvider().fetch("SPY", date(2020, 1, 1), date(2020, 6, 1))
    assert not p1.empty
    pd.testing.assert_frame_equal(p1, p2)
    assert list(p1.columns) == OHLCV_COLUMNS


def test_synthetic_high_low_bracket_open_close():
    frame = SyntheticProvider().fetch("QQQ", date(2020, 1, 1), date(2020, 3, 1))
    assert (frame["high"] >= frame[["open", "close"]].max(axis=1) - 1e-9).all()
    assert (frame["low"] <= frame[["open", "close"]].min(axis=1) + 1e-9).all()


def test_universe_includes_benchmark():
    uni = Universe(symbols=("QQQ", "IWM"))
    assert REGIME_BENCHMARK in uni.symbols
    assert len(uni) == 3


def test_load_history_offline_never_empty():
    hist = load_history(
        LIQUID_ETF_UNIVERSE, date(2019, 1, 1), date(2019, 12, 31), allow_network=False
    )
    assert set(hist).issuperset(set(LIQUID_ETF_UNIVERSE))


def test_cache_round_trip(tmp_path):
    cache = ParquetCache(cache_dir=tmp_path)
    provider = SyntheticProvider()
    hist = load_cached_history(
        ["SPY", "QQQ"],
        date(2020, 1, 1),
        date(2020, 12, 31),
        cache=cache,
        provider=provider,
        allow_network=False,
    )
    assert set(hist) == {"SPY", "QQQ"}
    # Second call should hit disk and return identical data.
    again = cache.read("SPY", provider.name)
    assert again is not None
    pd.testing.assert_frame_equal(
        hist["SPY"], again.loc[hist["SPY"].index], check_freq=False
    )
