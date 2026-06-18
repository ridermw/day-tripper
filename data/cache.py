"""Parquet cache so backtests are reproducible and offline-capable.

Cached frames live under ``data/cache/`` (git-ignored; EOD data is rebuildable). Each
symbol is stored as one parquet file keyed by symbol and the provider name, so synthetic
and real data never collide. See Design, "Data layer" and "Reproducibility".
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from data.providers import (
    OHLCV_COLUMNS,
    DataProvider,
    SyntheticProvider,
    get_default_provider,
)

DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / "cache"


class ParquetCache:
    """A tiny on-disk parquet cache for canonical OHLCV frames."""

    def __init__(self, cache_dir: Path | str = DEFAULT_CACHE_DIR) -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, symbol: str, provider_name: str) -> Path:
        safe = symbol.upper().replace("/", "_").replace(".", "_")
        return self.cache_dir / f"{provider_name}__{safe}.parquet"

    def read(self, symbol: str, provider_name: str) -> pd.DataFrame | None:
        path = self._path(symbol, provider_name)
        if not path.exists():
            return None
        frame = pd.read_parquet(path)
        frame.index = pd.DatetimeIndex(frame.index, name="date")
        return frame[OHLCV_COLUMNS]

    def write(self, symbol: str, provider_name: str, frame: pd.DataFrame) -> None:
        path = self._path(symbol, provider_name)
        frame.to_parquet(path)

    def get(
        self,
        symbol: str,
        start: date,
        end: date,
        provider: DataProvider,
        refresh: bool = False,
    ) -> pd.DataFrame:
        """Return cached OHLCV for ``symbol`` covering ``[start, end]``.

        Fetches and persists from ``provider`` on a cache miss, or when the cached range
        does not cover the request, or when ``refresh`` is set.
        """
        cached = None if refresh else self.read(symbol, provider.name)
        if cached is not None and not cached.empty:
            covered = (
                cached.index.min() <= pd.Timestamp(start)
                and cached.index.max() >= pd.Timestamp(end)
            )
            if covered:
                mask = (cached.index >= pd.Timestamp(start)) & (
                    cached.index <= pd.Timestamp(end)
                )
                return cached.loc[mask]
        fresh = provider.fetch(symbol, start, end)
        if not fresh.empty:
            self.write(symbol, provider.name, fresh)
        return fresh


def load_cached_history(
    symbols,
    start: date,
    end: date,
    cache: ParquetCache | None = None,
    provider: DataProvider | None = None,
    allow_network: bool = True,
    refresh: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load OHLCV for ``symbols`` through the parquet cache.

    Mirrors :func:`data.providers.load_history` but persists each frame to disk and
    reads it back on subsequent runs, guaranteeing reproducibility. Falls back to the
    synthetic provider per-symbol so the result is never empty for a valid request.
    """
    cache = cache or ParquetCache()
    primary = provider or get_default_provider(allow_network=allow_network)
    fallback = SyntheticProvider()
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = cache.get(symbol, start, end, primary, refresh=refresh)
        if frame.empty and not isinstance(primary, SyntheticProvider):
            frame = cache.get(symbol, start, end, fallback, refresh=refresh)
        if not frame.empty:
            out[symbol] = frame
    return out
