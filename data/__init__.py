"""Data layer: provider abstraction, parquet cache, and the tradable universe.

Phase 1 deliberately starts with a small set of liquid ETFs (clean, survivorship-free
data). See docs/DESIGN.md, "Data layer" and "Phasing".
"""

from data.cache import ParquetCache
from data.providers import (
    DataProvider,
    StooqProvider,
    SyntheticProvider,
    YFinanceProvider,
    get_default_provider,
    load_history,
)
from data.universe import LIQUID_ETF_UNIVERSE, REGIME_BENCHMARK, Universe

__all__ = [
    "ParquetCache",
    "DataProvider",
    "StooqProvider",
    "YFinanceProvider",
    "SyntheticProvider",
    "get_default_provider",
    "load_history",
    "LIQUID_ETF_UNIVERSE",
    "REGIME_BENCHMARK",
    "Universe",
]
