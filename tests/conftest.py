"""Shared fixtures: a small deterministic synthetic price panel."""

from __future__ import annotations

from datetime import date

import pytest

from data.providers import SyntheticProvider, load_history
from data.universe import LIQUID_ETF_UNIVERSE


@pytest.fixture(scope="session")
def synthetic_history():
    provider = SyntheticProvider()
    return load_history(
        LIQUID_ETF_UNIVERSE,
        date(2018, 1, 1),
        date(2021, 12, 31),
        provider=provider,
        allow_network=False,
    )
