"""Render a candidate board into a single self-contained HTML page.

Intentionally plain and dependency-free: inline CSS, no JS, no external assets,
so it drops straight onto GitHub Pages and every number is auditable in view
source. The page states what data it ran on and that the board is *ungraded* —
the falsification gauntlet (DSR/PBO/walk-forward) is a later phase.
"""

from __future__ import annotations

import html as _html

import pandas as pd

_CSS = """
body { font-family: -apple-system, system-ui, sans-serif; margin: 2rem; color: #111; }
h1 { margin-bottom: 0.2rem; }
.meta { color: #555; font-size: 0.9rem; margin-bottom: 1.5rem; }
table { border-collapse: collapse; width: 100%; max-width: 760px; }
th, td { text-align: right; padding: 0.4rem 0.8rem; border-bottom: 1px solid #eee; }
th:first-child, td:first-child { text-align: left; }
thead th { border-bottom: 2px solid #ccc; }
.yes { color: #0a7d28; font-weight: 600; }
.no { color: #b00020; }
.note { color: #777; font-size: 0.85rem; margin-top: 1.5rem; max-width: 760px; }
"""


def _fmt(value: float) -> str:
    return f"{value:,.2f}"


def render_dashboard(board: pd.DataFrame, meta: dict) -> str:
    universe = ", ".join(meta.get("universe", []))
    rows = []
    for _, r in board.iterrows():
        beats = bool(r["beats_cash"])
        mark = '<span class="yes">✓</span>' if beats else '<span class="no">✗</span>'
        rows.append(
            "<tr>"
            f"<td>{_html.escape(str(r['strategy']))}</td>"
            f"<td>{int(r['n_trades'])}</td>"
            f"<td>{_fmt(float(r['net_pnl']))}</td>"
            f"<td>{_fmt(float(r['cash_pnl']))}</td>"
            f"<td>{mark}</td>"
            "</tr>"
        )
    body_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>day-tripper — candidate board</title>
<style>{_CSS}</style>
</head>
<body>
<h1>day-tripper</h1>
<div class="meta">
  Candidate board (ungraded) ·
  capital ${meta.get('capital', 0):,.0f}/day ·
  universe: {_html.escape(universe)} ·
  bars: {meta.get('bars', 0)} ·
  data: {_html.escape(str(meta.get('data_source', 'unknown')))} ·
  generated: {_html.escape(str(meta.get('generated', '')))}
</div>
<table>
<thead>
<tr><th>strategy</th><th>trades</th><th>net P&amp;L ($)</th><th>cash P&amp;L ($)</th><th>beats cash?</th></tr>
</thead>
<tbody>
{body_rows}
</tbody>
</table>
<p class="note">
  Cash is the defending champion: every strategy is measured against a risk-free
  cash baseline after costs. This is a <strong>candidate board only</strong> — the
  falsification gauntlet (purged walk-forward, Deflated Sharpe, PBO) that promotes
  survivors to the real leaderboard is a later phase. Research and education only;
  no real money.
</p>
</body>
</html>
"""
