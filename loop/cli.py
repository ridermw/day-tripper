"""Command-line entrypoint: ``daytripper <job>``.

Jobs map one-to-one to the scheduled GitHub Actions workflows.
"""

from __future__ import annotations

import argparse
import json
from datetime import date

from loop.runner import run_post_close, run_pre_close, run_pre_open

JOBS = {
    "pre-open": run_pre_open,
    "pre-close": run_pre_close,
    "post-close": run_post_close,
}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daytripper", description=__doc__)
    parser.add_argument("job", choices=sorted(JOBS), help="which scheduled job to run")
    parser.add_argument("--as-of", default=None, help="run date (YYYY-MM-DD); default today")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="force the deterministic synthetic provider (no network)",
    )
    parser.add_argument(
        "--lookback-years", type=int, default=5, help="history window to load"
    )
    args = parser.parse_args(argv)

    fn = JOBS[args.job]
    payload = fn(
        as_of=_parse_date(args.as_of),
        allow_network=not args.offline,
        lookback_years=args.lookback_years,
    )
    summary = {
        "job": args.job,
        "as_of_date": payload.get("as_of_date"),
        "data_source": payload.get("data_source"),
        "synthetic": payload.get("synthetic"),
    }
    if "books" in payload:
        summary["books"] = {
            cat: {"total_pnl": round(b["total_pnl"], 2), "cash_pnl": round(b["cash_pnl"], 2)}
            for cat, b in payload["books"].items()
        }
    if "locked_entries" in payload:
        summary["locked_entries"] = len(payload["locked_entries"])
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
