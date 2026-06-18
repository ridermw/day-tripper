"""Render the static dashboard from a post-close results payload.

No server, no JS framework: plain HTML + a tiny inline-SVG sparkline so the page is fully
auditable and reproducible. The page always foregrounds two honesty signals: whether the
data is synthetic, and that Phase 1 is a *candidate board*, not a leaderboard.
"""

from __future__ import annotations

import html
import json
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_SITE_DIR = Path(__file__).resolve().parent / "site"


def _fmt_money(value: float) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:,.2f}%"


def _sparkline(series: list[float], width: int = 280, height: int = 60) -> str:
    """A minimal inline-SVG line for a cumulative P&L series."""
    if not series:
        return ""
    lo, hi = min(series), max(series)
    span = hi - lo or 1.0
    n = len(series)
    step = width / max(n - 1, 1)
    pts = []
    for i, v in enumerate(series):
        x = i * step
        y = height - (v - lo) / span * height
        pts.append(f"{x:.1f},{y:.1f}")
    path = " ".join(pts)
    zero_y = height - (0.0 - lo) / span * height if lo <= 0 <= hi else None
    zero = (
        f'<line x1="0" y1="{zero_y:.1f}" x2="{width}" y2="{zero_y:.1f}" '
        'stroke="#999" stroke-dasharray="3,3" stroke-width="1"/>'
        if zero_y is not None
        else ""
    )
    color = "#1a7f37" if series[-1] >= 0 else "#cf222e"
    return (
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f"{zero}"
        f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{path}"/>'
        "</svg>"
    )


def _candidate_rows(board: list[dict]) -> str:
    if not board:
        return '<tr><td colspan="9">No candidates yet.</td></tr>'
    rows = []
    for c in board:
        beats = "✅" if c["beats_cash"] else "❌"
        rows.append(
            "<tr>"
            f"<td>{html.escape(c['strategy_id'])}</td>"
            f"<td>{html.escape(c['category'])}</td>"
            f"<td>{html.escape(c['side'])}</td>"
            f"<td>{c['n_days']}</td>"
            f"<td>{c['n_trades']}</td>"
            f"<td>{_fmt_money(c['total_pnl'])}</td>"
            f"<td>{_fmt_money(c['cash_pnl'])}</td>"
            f"<td>{_fmt_money(c['excess_pnl'])}</td>"
            f"<td>{c['sharpe']:.2f}</td>"
            f"<td>{beats}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _book_cards(books: dict, cumulative: dict) -> str:
    cards = []
    for category, stats in books.items():
        series = cumulative.get(category, {}).get("cum_book_pnl", [])
        spark = _sparkline(series)
        excess = stats["total_pnl"] - stats["cash_pnl"]
        verdict = "beats cash" if excess > 0 else "below cash"
        cards.append(
            '<div class="card">'
            f"<h3>{html.escape(category)} book</h3>"
            f"<p class='big'>{_fmt_money(stats['total_pnl'])}</p>"
            f"<p>cash baseline: {_fmt_money(stats['cash_pnl'])} "
            f"&middot; <strong>{verdict}</strong> ({_fmt_money(excess)})</p>"
            f"<p>strategies: {html.escape(', '.join(stats['strategy_ids']))}</p>"
            f"{spark}"
            "</div>"
        )
    return "\n".join(cards)


def _sensitivity_tables(sensitivity: dict) -> str:
    blocks = []
    for sid, rows in sensitivity.items():
        body = []
        for r in rows:
            beats = "✅" if r["beats_cash"] else "❌"
            body.append(
                "<tr>"
                f"<td>{r['cost_multiplier']:.1f}×</td>"
                f"<td>{_fmt_money(r['total_pnl'])}</td>"
                f"<td>{_fmt_money(r['excess_pnl'])}</td>"
                f"<td>{beats}</td>"
                "</tr>"
            )
        blocks.append(
            f"<h4>{html.escape(sid)}</h4>"
            "<table><thead><tr><th>cost</th><th>total P&amp;L</th>"
            "<th>excess vs cash</th><th>beats cash</th></tr></thead>"
            f"<tbody>{''.join(body)}</tbody></table>"
        )
    return "\n".join(blocks)


def _intended_rows(trades: list[dict]) -> str:
    if not trades:
        return '<tr><td colspan="4">No locked entries.</td></tr>'
    rows = []
    for t in trades:
        rows.append(
            "<tr>"
            f"<td>{html.escape(t['strategy_id'])}</td>"
            f"<td>{html.escape(t['book'])}</td>"
            f"<td>{html.escape(t['side'])}</td>"
            f"<td>{html.escape(t['symbol'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def render_html(results: dict) -> str:
    """Render the full dashboard HTML from a results payload."""
    source = results.get("data_source", "unknown")
    synthetic = results.get("synthetic", False)
    as_of = results.get("as_of_date", "n/a")
    generated = results.get("generated_at", datetime.now(UTC).isoformat())

    banner = ""
    if synthetic:
        banner = (
            '<div class="banner warn">⚠️ SYNTHETIC DATA — external EOD source was '
            "unavailable, so prices are deterministic simulations. This is NOT a real "
            "track record.</div>"
        )
    phase_banner = (
        '<div class="banner info">Phase 1 — <strong>candidate board</strong> '
        "(ungraded). Nothing here has passed the falsification gauntlet, so nothing is "
        "on a leaderboard. Cash is the defending champion.</div>"
    )
    subtitle = (
        f"falsification-first, agent-operated day-trading research &middot; "
        f"data: {html.escape(str(source))} &middot; as of {html.escape(str(as_of))}"
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>day-tripper — candidate board</title>
<style>
 body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0; color: #1f2328;
        background: #f6f8fa; }}
 header {{ background: #0d1117; color: #fff; padding: 18px 24px; }}
 header h1 {{ margin: 0; font-size: 20px; }}
 header p {{ margin: 4px 0 0; color: #9da7b1; font-size: 13px; }}
 main {{ max-width: 980px; margin: 0 auto; padding: 16px 24px 48px; }}
 .banner {{ padding: 10px 14px; border-radius: 6px; margin: 12px 0; font-size: 14px; }}
 .banner.warn {{ background: #fff8c5; border: 1px solid #d4a72c; }}
 .banner.info {{ background: #ddf4ff; border: 1px solid #54aeff; }}
 .cards {{ display: flex; gap: 16px; flex-wrap: wrap; }}
 .card {{ background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 14px;
          flex: 1 1 280px; }}
 .card h3 {{ margin: 0 0 6px; text-transform: capitalize; }}
 .card .big {{ font-size: 24px; font-weight: 700; margin: 4px 0; }}
 table {{ border-collapse: collapse; width: 100%; background: #fff; margin: 8px 0 20px;
          font-size: 14px; }}
 th, td {{ border: 1px solid #d0d7de; padding: 6px 8px; text-align: left; }}
 th {{ background: #f0f3f6; }}
 h2 {{ margin-top: 28px; }}
 footer {{ color: #656d76; font-size: 12px; padding: 0 24px 32px; max-width: 980px;
           margin: 0 auto; }}
</style>
</head>
<body>
<header>
  <h1>day-tripper</h1>
  <p>{subtitle}</p>
</header>
<main>
  {banner}
  {phase_banner}

  <h2>Books — P&amp;L vs cash</h2>
  <div class="cards">
    {_book_cards(results.get('books', {}), results.get('cumulative', {}))}
  </div>

  <h2>Candidate board (ungraded)</h2>
  <table>
    <thead><tr>
      <th>strategy</th><th>book</th><th>side</th><th>days</th><th>trades</th>
      <th>total P&amp;L</th><th>cash P&amp;L</th><th>excess</th><th>Sharpe</th>
      <th>beats cash</th>
    </tr></thead>
    <tbody>
      {_candidate_rows(results.get('candidate_board', []))}
    </tbody>
  </table>

  <h2>Today's locked entries</h2>
  <table>
    <thead><tr><th>strategy</th><th>book</th><th>side</th><th>symbol</th></tr></thead>
    <tbody>
      {_intended_rows(results.get('intended_trades', []))}
    </tbody>
  </table>

  <h2>Cost sensitivity</h2>
  {_sensitivity_tables(results.get('cost_sensitivity', {}))}
</main>
<footer>
  Research and education only. No real money. Simulated / paper execution.
  Generated {html.escape(str(generated))}.
</footer>
</body>
</html>
"""


def render_site(results: dict, site_dir: Path | str = DEFAULT_SITE_DIR) -> Path:
    """Write ``index.html`` and the raw ``results.json`` to ``site_dir``.

    Returns the path to the generated ``index.html``.
    """
    site = Path(site_dir)
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(render_html(results), encoding="utf-8")
    (site / "results.json").write_text(json.dumps(results, indent=2, default=str))
    # A .nojekyll file keeps GitHub Pages from reprocessing the static output.
    (site / ".nojekyll").write_text("")
    return site / "index.html"
