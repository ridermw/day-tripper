"""Scorer: the cash baseline and Phase 1 candidate-board metrics.

**Phase 1 publishes a candidate board, not a leaderboard.** The full falsification
gauntlet (purged walk-forward OOS -> DSR + PBO/CSCV against the trial ledger -> beats
cash) arrives in Phase 2. Until then nothing is "promoted"; results are explicitly
labelled ungraded. See docs/DESIGN.md, "Scorer / falsification gate" and "Phasing", and
AGENTS.md (the constitution + the gauntlet).
"""

from scorer.baseline import CashBaseline, cash_baseline_series
from scorer.metrics import CandidateScore, cost_sensitivity_table, score_result

__all__ = [
    "CashBaseline",
    "cash_baseline_series",
    "CandidateScore",
    "score_result",
    "cost_sensitivity_table",
]
