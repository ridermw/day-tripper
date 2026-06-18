# day-tripper

An open-source, **agent-operated**, **falsification-first** day-trading *research*
system. A compound-engineering agent loop proposes strategies, backtests them honestly,
grades them, allocates across them, and runs them in continuous paper trading — entirely
in public. A human seeds intent (via GitHub issues) and observes. **No real money is
ever used.**

> **Status:** Phase 1. The architecture is approved
> ([`docs/DESIGN.md`](docs/DESIGN.md)). Implemented and tested: the engine core, cost
> model, risk-free cash baseline, data-provider abstraction (with parquet caching), the
> candidate board, a static HTML dashboard, and a scheduled publish workflow. Next: the
> DSR/PBO falsification gauntlet (Phase 2) and live data providers.

## The thesis: honesty is the product

Most "trading systems" show a wall of green by ignoring transaction costs and
data-mining their own backtests. day-tripper is built to do the opposite. Its core job
is to **kill strategies**, not collect them.

- **Cash is the defending champion.** Nothing reaches the leaderboard until it beats a
  risk-free cash baseline *after costs*, *out-of-sample*.
- **Every trial is counted.** A many-strategy leaderboard is multiple-hypothesis testing.
  An immutable trial ledger feeds a Deflated Sharpe Ratio + Probability-of-Backtest-
  Overfitting penalty so the system can't lie to itself.
- **"Sometimes the best trade is no trade."** Staying in cash is a first-class
  allocation, and the empirically correct default when nothing survives the gauntlet.
- A public **graveyard** of killed strategies is a first-class output. Showing what does
  *not* work is the rare, credible thing.

## What it is (and isn't)

Every strategy is one of two single-boundary shapes — **overnight** (buy at close, sell
at next open) or **intraday** (buy at open, sell at same-day close), long or short — on
liquid US equities and ETFs, gated by a market **regime** signal. Because trades are
single-boundary, **daily open/close data is sufficient** — no intraday/tick data is ever
required, and free EOD sources cover the research.

- Capital model: two independent **$10,000/day, non-compounding** books (overnight and
  intraday), so per-day skill is measured without compounding luck.
- At most **10 entries per boundary per book per day** (customizable).
- This is **research and education only. Not investment advice. No real money.**

## The five-plus-two components

1. **Strategy library** — stores, versions, and generates strategy specs.
2. **Engine** — vectorized daily-OHLC backtester with an explicit cost/slippage model;
   the same code path drives optional paper execution.
3. **Scorer / falsification gate** — cost → purged walk-forward OOS → DSR/PBO → beats
   cash. Survivors are promoted; failures are buried.
4. **Adaptive allocation (meta-strategy)** — regime-gated online allocation across
   promoted strategies; runs in shadow mode until it beats equal-weight + cash.
5. **Dashboard** — a static site on GitHub Pages: leaderboard, candidate board,
   graveyard, daily/weekly/monthly P&L vs cash.
6. **The meta-loop** — the md files, prompts, and GitHub Actions that let the agent build,
   run, grade, and maintain the whole thing. See [`AGENTS.md`](AGENTS.md).

## How the loop runs

A **post-close** GitHub Actions job (`.github/workflows/daily.yml`) runs the backtest on
EOD data, regenerates the candidate board, and republishes the dashboard to
[`docs/`](docs/) (served on GitHub Pages). Commits are the audit trail.

The design's **pre-open** and **pre-close** entry-locking jobs activate with paper
execution (a later phase) — wiring empty schedules now would be cargo-cult. Today the
loop runs on offline synthetic data; live providers are a follow-up.

## Roadmap

- **Phase 1** — data provider + vectorized engine + cost model + cash baseline + one
  reference strategy per side, on a liquid-ETF universe. Candidate board only.
- **Phase 2** — trial ledger + purged walk-forward CV + DSR + PBO gate + graveyard. The
  leaderboard begins here.
- **Phase 3** — regime detection + shadow-mode meta-strategy allocation.
- **Phase 4 (optional)** — Alpaca paper execution for realtime validation.

## For contributors and agents

- Full architecture: [`docs/DESIGN.md`](docs/DESIGN.md)
- Operating rules for agent sessions: [`AGENTS.md`](AGENTS.md)

### Develop

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # run the test suite
python -m daytripper.demo   # end-to-end candidate board on synthetic data
```

## Disclaimer

This project is for research and educational purposes only. It does not execute real
trades, does not use real money, and is not financial or investment advice. Past or
simulated performance does not indicate future results.

## License

[GPL-3.0](LICENSE).
