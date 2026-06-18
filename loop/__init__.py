"""The meta-loop: the three scheduled jobs that run the system in public.

- **pre-open**  -- lock intraday (open-side) entries; resolve the prior overnight book.
- **pre-close** -- lock overnight (close-side) entries.
- **post-close** -- ingest official OHLC, run backtests, score (candidate board), allocate,
  simulate the day, regenerate the dashboard, and persist state.

Deterministic steps run as plain Python in CI; jobs are idempotent so they can re-run
safely. See docs/DESIGN.md, "Meta-loop", and AGENTS.md, "The loop".
"""

from loop.runner import (
    run_post_close,
    run_pre_close,
    run_pre_open,
)

__all__ = ["run_pre_open", "run_pre_close", "run_post_close"]
