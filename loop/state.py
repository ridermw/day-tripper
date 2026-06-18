"""Persistent state for the loop -- the audit trail artifacts.

State lives under ``state/`` (committed, unlike the rebuildable parquet cache) so each
job's output is a public, diff-able artifact. JSON keeps it human-readable in PRs.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_STATE_DIR = Path(__file__).resolve().parents[1] / "state"


def state_dir(base: Path | str | None = None) -> Path:
    path = Path(base) if base is not None else DEFAULT_STATE_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_state(name: str, payload: dict, base: Path | str | None = None) -> Path:
    path = state_dir(base) / f"{name}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def read_state(name: str, base: Path | str | None = None) -> dict | None:
    path = state_dir(base) / f"{name}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))
