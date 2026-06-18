"""Adaptive allocation -- Phase 1 production allocator.

Design ("Adaptive allocation") / AGENTS.md: the **default production allocator is
equal-weight + cash**. The learned meta-strategy (bandit / online-portfolio, regime
gated) runs in *shadow mode* and only takes command once it beats this benchmark and
cash after costs out-of-sample (Phase 3). Phase 1 ships the benchmark only.
"""

from allocation.equal_weight import EqualWeightAllocator, allocate_equal_weight

__all__ = ["EqualWeightAllocator", "allocate_equal_weight"]
