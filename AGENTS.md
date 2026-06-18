# AGENTS.md — operating rules for agent sessions

This repository is **agent-operated**. A human seeds intent through GitHub issues and
observes; agents do the building, grading, and maintenance. This file orients any agent
session picking up work. The full architecture and rationale live in
[`docs/DESIGN.md`](docs/DESIGN.md) — that document is the source of truth; this file is
the short version of the rules you must not break.

## Non-negotiables (the constitution)

1. **Cash is the defending champion.** No strategy reaches the **leaderboard** until it
   beats a risk-free cash baseline *after costs*, *out-of-sample*. Pre-gauntlet results
   live on a clearly-labeled **candidate board**, never called a leaderboard.
2. **Count every trial.** Every generated, mutated, and rejected strategy/parameter set
   registers in an **immutable trial ledger** with a unique id and counts against the
   multiple-testing penalty (Deflated Sharpe Ratio + Probability of Backtest Overfitting
   via CSCV). Do not quietly discard trials to flatter a result.
3. **No look-ahead.** Overnight (close-side) entries may use only data available before
   today's close; intraday (open-side) entries may use only data through the prior close.
   When in doubt, lag the signal one day.
4. **Costs are the core, not a footnote.** Every backtest applies an explicit
   commission + slippage model and publishes a sensitivity table. "No edge after costs"
   is a valid, valuable result.
5. **Single-boundary holds only** — close→open or open→close. Never multi-day.
6. **Capital model:** two independent **$10,000/day, non-compounding** books (overnight,
   intraday). At most **10 entries per boundary per book per day** (customizable). Cash
   earns the risk-free / broker-sweep yield, not 0%.
7. **Daily OHLC only.** No intraday/tick data is required or used.
8. **No real money. Ever.** Paper / simulated execution only. Shorts are restricted to
   liquid ETFs / large caps until a borrow-fee model exists.
9. **Show the work.** All work is public; issues and PRs are the audit trail.

## The falsification gauntlet (order matters)

A candidate must pass, in order, before promotion:

1. Positive **net of costs**.
2. **Purged walk-forward** out-of-sample with embargo.
3. **DSR + PBO/CSCV** penalty against the full trial ledger.
4. **Beats the cash baseline** after costs.

Survivors are promoted to the leaderboard. Failures go to the public **graveyard** with
the reason they died. **Promotion is not permanent** — re-evaluate each cycle and demote
when the growing trial ledger or decaying performance drops a strategy below cash.

## The loop (planned)

Three scheduled GitHub Actions workflows behind a data-provider abstraction:

- **pre-open** — lock intraday open-side entries; resolve the prior overnight book.
- **pre-close** — lock overnight close-side entries.
- **post-close** — ingest official OHLC, run the gauntlet, update allocation, simulate
  the day, regenerate the dashboard, commit, and open/close issues + PRs.

Deterministic steps run as plain Python; agent/LLM steps are bounded and budget-capped;
credentials live in GitHub Secrets; jobs are idempotent and open an issue on failure.

## Where to start

The repo is in design phase — no code yet. Build in the phase order in
[`docs/DESIGN.md`](docs/DESIGN.md):

- **Phase 1:** provider abstraction (Stooq if verified, yfinance fallback) + parquet
  cache + vectorized daily-OHLC engine + cost model + risk-free cash baseline + one
  reference strategy per side, on a **liquid-ETF universe**. Publishes a candidate board.
- Then Phase 2 (rigor) → Phase 3 (allocation) → Phase 4 (optional paper execution).

Planned layout: `data/`, `strategies/`, `engine/`, `scorer/`, `allocation/`,
`dashboard/`, `loop/`.

## Working agreement

- Treat `docs/DESIGN.md` as the source of truth; if you must deviate, update it in the
  same PR and say why.
- Keep results reproducible: pin dependencies, cache data, keep backtests deterministic.
- Be honest about bias. Label any result that relies on incomplete free data (see the
  "Known Biases & Data Realism" section of the design doc).
