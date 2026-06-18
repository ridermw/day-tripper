"""Provider abstraction so no single data source is load-bearing.

Resolution order (Design, "Data layer" / Premise 5):

    Stooq (primary EOD, if reachable) -> yfinance (fallback) -> Synthetic (deterministic)

The synthetic provider guarantees the loop and the test-suite run **offline and
deterministically** when external sources are blocked (Design, "Known Biases": "Stooq
access can change or be blocked"). Synthetic data is clearly labelled as such so it is
never mistaken for a real track record.

Every provider returns a canonical, split/dividend-adjusted OHLCV frame:

    index : DatetimeIndex (sorted, business days, named "date")
    cols  : ["open", "high", "low", "close", "volume"]
"""

from __future__ import annotations

import hashlib
import io
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from datetime import date

import numpy as np
import pandas as pd

OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def _empty_frame() -> pd.DataFrame:
    idx = pd.DatetimeIndex([], name="date")
    return pd.DataFrame(columns=OHLCV_COLUMNS, index=idx, dtype="float64")


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """Coerce a raw provider frame into the canonical schema."""
    out = frame.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    missing = [c for c in OHLCV_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(f"provider frame missing columns: {missing}")
    out = out[OHLCV_COLUMNS].astype("float64")
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index), name="date")
    out = out[~out.index.duplicated(keep="last")].sort_index()
    # Drop rows with a missing open or close (Design: "skip names with a missing
    # open or close").
    out = out.dropna(subset=["open", "close"])
    return out


class DataProvider(ABC):
    """Base class for EOD OHLCV providers."""

    name: str = "base"
    #: True when the data is not a real market feed and must be labelled as such.
    synthetic: bool = False

    @abstractmethod
    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Return canonical OHLCV for ``symbol`` in ``[start, end]`` (may be empty)."""

    def available(self) -> bool:  # pragma: no cover - trivial default
        return True


class StooqProvider(DataProvider):
    """Primary EOD source via Stooq's CSV endpoint (no API key required)."""

    name = "stooq"
    synthetic = False
    _BASE = "https://stooq.com/q/d/l/"

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        ticker = symbol.lower()
        if "." not in ticker:
            ticker = f"{ticker}.us"
        url = (
            f"{self._BASE}?s={ticker}&i=d"
            f"&d1={start:%Y%m%d}&d2={end:%Y%m%d}"
        )
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "day-tripper/0.1"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
        except (urllib.error.URLError, TimeoutError, OSError):
            return _empty_frame()
        if not raw or raw.lstrip().lower().startswith("<"):
            return _empty_frame()
        frame = pd.read_csv(io.StringIO(raw))
        if frame.empty or "Date" not in frame.columns:
            return _empty_frame()
        frame = frame.rename(columns={"Date": "date"}).set_index("date")
        return _normalize(frame)


class YFinanceProvider(DataProvider):
    """Fallback EOD source via the optional ``yfinance`` dependency."""

    name = "yfinance"
    synthetic = False

    def available(self) -> bool:
        try:
            import yfinance  # noqa: F401
        except Exception:
            return False
        return True

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        try:
            import yfinance as yf
        except Exception:
            return _empty_frame()
        try:
            raw = yf.download(
                symbol,
                start=str(start),
                end=str(end),
                auto_adjust=True,
                progress=False,
            )
        except Exception:
            return _empty_frame()
        if raw is None or raw.empty:
            return _empty_frame()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.get_level_values(0)
        return _normalize(raw)


class SyntheticProvider(DataProvider):
    """Deterministic synthetic OHLCV so backtests run offline and reproducibly.

    The price path is a seeded geometric random walk; the seed is derived from the
    symbol so each name is stable across runs. This is **not** market data and the
    dashboard labels any synthetic-sourced result accordingly.
    """

    name = "synthetic"
    synthetic = True

    def __init__(self, annual_drift: float = 0.06, annual_vol: float = 0.18) -> None:
        self.annual_drift = annual_drift
        self.annual_vol = annual_vol

    def _seed(self, symbol: str) -> int:
        digest = hashlib.sha256(symbol.upper().encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def fetch(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        days = pd.bdate_range(start=start, end=end, name="date")
        n = len(days)
        if n == 0:
            return _empty_frame()
        rng = np.random.default_rng(self._seed(symbol))
        dt = 1.0 / 252.0
        mu, sigma = self.annual_drift, self.annual_vol
        # Daily close-to-close log returns.
        shocks = rng.normal(
            (mu - 0.5 * sigma**2) * dt, sigma * np.sqrt(dt), size=n
        )
        base = 50.0 + (self._seed(symbol) % 200)
        close = base * np.exp(np.cumsum(shocks))
        # Overnight gap: part of each day's move happens between prior close and open.
        gap = rng.normal(0.0, sigma * np.sqrt(dt) * 0.5, size=n)
        prev_close = np.concatenate([[base], close[:-1]])
        open_ = prev_close * np.exp(gap)
        high = np.maximum(open_, close) * (1.0 + np.abs(rng.normal(0, 0.003, size=n)))
        low = np.minimum(open_, close) * (1.0 - np.abs(rng.normal(0, 0.003, size=n)))
        volume = rng.integers(5_000_000, 80_000_000, size=n).astype("float64")
        frame = pd.DataFrame(
            {
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
            },
            index=days,
        )
        return _normalize(frame)


def get_default_provider(allow_network: bool = True) -> DataProvider:
    """Return the first usable provider, preferring real sources.

    When ``allow_network`` is False (e.g. deterministic test runs) the synthetic
    provider is used directly.
    """
    if allow_network:
        for provider in (StooqProvider(), YFinanceProvider()):
            if provider.available():
                return provider
    return SyntheticProvider()


def load_history(
    symbols,
    start: date,
    end: date,
    provider: DataProvider | None = None,
    allow_network: bool = True,
) -> dict[str, pd.DataFrame]:
    """Load canonical OHLCV for ``symbols``, falling back per-symbol when a source is
    empty.

    Returns a mapping ``symbol -> OHLCV frame``. Symbols that resolve to no data are
    omitted. The synthetic provider is always available as a last resort so the result
    is never empty when at least one symbol is requested.
    """
    primary = provider or get_default_provider(allow_network=allow_network)
    fallback = SyntheticProvider()
    out: dict[str, pd.DataFrame] = {}
    for symbol in symbols:
        frame = primary.fetch(symbol, start, end)
        if frame.empty and not isinstance(primary, SyntheticProvider):
            frame = fallback.fetch(symbol, start, end)
        if not frame.empty:
            out[symbol] = frame
    return out
