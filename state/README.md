# Loop state — the public audit trail

The scheduled jobs write JSON artifacts here and commit them so every decision is a
public, diff-able record (Design: "issues and PRs are the audit trail"):

- `locked_overnight.json` — overnight (close-side) entries locked by the **pre-close** job.
- `locked_intraday.json`  — intraday (open-side) entries locked by the **pre-open** job,
  plus the prior overnight book it resolves.
- `latest_results.json`   — the **post-close** job's full results payload (also the source
  for the dashboard).

These files are regenerated each run and are safe to delete (the loop recreates them).
