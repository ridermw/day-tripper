"""Declarative strategy specs (YAML-backed).

A spec is intentionally small and serializable so the agent can "dream up" new
parametrizations and the trial ledger (Phase 2) can assign each one an immutable id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_CATEGORIES = ("overnight", "intraday")
VALID_SIDES = ("long", "short")
VALID_SELECTIONS = ("momentum", "reversion", "single")


@dataclass(frozen=True)
class StrategySpec:
    """A single strategy definition.

    Attributes
    ----------
    id:
        Stable human-readable identifier (also used as the trial-ledger key in Phase 2).
    category:
        ``overnight`` (close -> next open) or ``intraday`` (open -> same-day close).
    side:
        ``long`` or ``short``. Shorts are restricted to liquid ETFs in Phase 1
        (Design: "Short realism is a gate, not an option").
    selection:
        Ranking rule: ``momentum``, ``reversion``, or ``single`` (a fixed symbol).
    regime_gate:
        Optional market regime condition, e.g. ``spy_above_200dma``. ``None`` disables.
    params:
        Free-form numeric/string parameters consumed by the selection rule.
    """

    id: str
    category: str
    side: str = "long"
    selection: str = "momentum"
    regime_gate: str | None = None
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.category not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {VALID_CATEGORIES}, got {self.category!r}")
        if self.side not in VALID_SIDES:
            raise ValueError(f"side must be one of {VALID_SIDES}, got {self.side!r}")
        if self.selection not in VALID_SELECTIONS:
            raise ValueError(
                f"selection must be one of {VALID_SELECTIONS}, got {self.selection!r}"
            )

    @classmethod
    def from_dict(cls, payload: dict) -> StrategySpec:
        known = {"id", "category", "side", "selection", "regime_gate", "params"}
        unknown = set(payload) - known
        if unknown:
            raise ValueError(f"unknown spec keys: {sorted(unknown)}")
        return cls(
            id=payload["id"],
            category=payload["category"],
            side=payload.get("side", "long"),
            selection=payload.get("selection", "momentum"),
            regime_gate=payload.get("regime_gate"),
            params=dict(payload.get("params", {})),
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "side": self.side,
            "selection": self.selection,
            "regime_gate": self.regime_gate,
            "params": dict(self.params),
        }


def load_spec(path: Path | str) -> StrategySpec:
    """Load a single strategy spec from a YAML file."""
    payload = yaml.safe_load(Path(path).read_text())
    return StrategySpec.from_dict(payload)


def load_specs_dir(directory: Path | str) -> list[StrategySpec]:
    """Load every ``*.yaml`` spec in ``directory``, sorted by id."""
    specs = [load_spec(p) for p in sorted(Path(directory).glob("*.yaml"))]
    return sorted(specs, key=lambda s: s.id)


DEFAULT_SPECS_DIR = Path(__file__).resolve().parent / "specs"
