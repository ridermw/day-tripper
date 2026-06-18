# The meta-loop — how the agent runs day-tripper

This document is the operating manual for the autopilot loop. It explains how the agent
proposes, tests, grades, promotes/kills, and reports — so a future session can run the
whole system from the repo alone. `docs/DESIGN.md` is the source of truth; this is the
how-to. The non-negotiables live in [`AGENTS.md`](../AGENTS.md).

## The three scheduled jobs

The loop is three GitHub Actions workflows behind a data-provider abstraction. Each maps
to one `daytripper` subcommand and is **idempotent** (safe to re-run).

| Job          | Workflow                          | When (UTC)        | What it does |
|--------------|-----------------------------------|-------------------|--------------|
| `pre-open`   | `.github/workflows/pre-open.yml`  | 13:15, Mon–Fri    | Lock intraday (open-side) entries; resolve the prior overnight book. |
| `pre-close`  | `.github/workflows/pre-close.yml` | 19:45, Mon–Fri    | Lock overnight (close-side) entries before the close auction. |
| `post-close` | `.github/workflows/post-close.yml`| 23:00, Mon–Fri    | Ingest EOD OHLC, backtest, score, allocate, simulate, regenerate the dashboard, publish to Pages. |

Run any job locally:

```bash
pip install -e .
daytripper post-close --offline --as-of 2021-12-31   # deterministic synthetic data
daytripper pre-close                                  # live data if reachable
```

`--offline` forces the deterministic synthetic provider so the loop runs with no network.
When the real EOD source is unavailable for any symbol, the run is **labelled synthetic**
end-to-end and the dashboard shows a warning banner — a synthetic run is never passed off
as a real track record.

## Look-ahead discipline (non-negotiable)

Selections are shifted one trading day, so a decision for date `D` uses only information
available through the prior close. Overnight P&L resolves `close(D) → open(D+1)`; intraday
resolves `open(D) → close(D)`. See `strategies/library.py` and `engine/backtest.py`.

## Costs and the cash baseline

Every backtest applies the explicit commission + slippage model (`engine/costs.py`) and
publishes a **cost-sensitivity table** across multipliers. Idle capital earns the
risk-free yield, not 0% — **cash is the defending champion**. "No edge after costs" is a
valid, valuable result.

## Phase 1 scope (this PR) vs later phases

Phase 1 publishes a **candidate board** only — results are *ungraded*. The word
"leaderboard" is reserved for survivors of the full gauntlet, which arrives in Phase 2:

1. **Trial ledger** — every generated/mutated/rejected strategy gets an immutable id and
   counts against the multiple-testing penalty.
2. **Purged walk-forward** out-of-sample with embargo.
3. **Deflated Sharpe + PBO/CSCV** against the trial ledger.
4. **Beats cash** after costs, out-of-sample.

Survivors are promoted to the leaderboard; failures go to the public **graveyard** with
the reason they died. Promotion is **not permanent** — re-evaluate each cycle and demote
when the growing ledger or decaying performance drops a strategy below cash.

## How the agent extends the system

- **Propose a strategy:** add a YAML spec under `strategies/specs/` (`category`, `side`,
  `selection`, `regime_gate`, `params`). The loop picks it up automatically.
- **Test it:** `daytripper post-close --offline` runs every spec and writes results.
- **Grade it:** Phase 1 = candidate metrics only. Phase 2 wires the gauntlet into
  `scorer/`.
- **Report:** the dashboard (`dashboard/`) regenerates from `state/latest_results.json`
  and deploys to Pages; `state/` is the committed audit trail.

## Where state lives

- `state/` — committed JSON audit trail (locked entries, latest results).
- `data/cache/` — parquet EOD cache (git-ignored; rebuildable).
- `dashboard/site/` — generated static site (git-ignored; deployed to Pages).

## Operational rules

- Deterministic steps run as plain Python in CI; jobs are idempotent.
- Credentials (later phases) live in GitHub Secrets, never in code.
- A failing job should open an issue (wire this up alongside Phase 2).
- Keep results reproducible: pinned deps, cached data, deterministic backtests.
