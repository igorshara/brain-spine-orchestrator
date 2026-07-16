"""Use-driven assist — lasting recovery is maximised by partial, fading help.

Locks in IZAR invention #2 on the plasticity twin: full assist (the machine does
everything) destroys activity-dependent recovery; the optimum assist is interior;
and fading the assist as recovery grows (assist-as-needed) beats any fixed level.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from bso.plasticity import optimal_assist, use_driven_course

N = 40


def test_full_assist_destroys_recovery():
    """If the stimulator does it all (assist=1), the patient's circuits barely
    engage, so lasting recovery collapses versus leaving room for own effort."""
    r = optimal_assist(n_sessions=N)
    assert r["full_assist_R"] < 0.5 * r["no_assist_R"]


def test_optimum_is_interior():
    """Best fixed assist is neither 0 nor 1 — there is a sweet spot."""
    r = optimal_assist(n_sessions=N)
    assert 0.0 < r["best_assist"] < 1.0


def test_adaptive_beats_best_fixed():
    """Fading the assist as recovery grows is at least as good as the best fixed
    level — the actionable assist-as-needed protocol."""
    r = optimal_assist(n_sessions=N)
    assert r["adaptive_R"] >= r["best_R"] - 1e-6


def test_recovery_is_monotone_in_disuse_decay_direction():
    """Sanity: more assist past the optimum monotonically lowers recovery (the
    use-dependence is real, not noise)."""
    r = optimal_assist(n_sessions=N)
    finals = r["final_R"]
    # from assist 0.5 upward, recovery should not increase
    half = len(finals) // 2
    tail = finals[half:]
    assert all(tail[i] >= tail[i + 1] - 1e-9 for i in range(len(tail) - 1))


def test_determinism():
    assert use_driven_course(0.3, N) == use_driven_course(0.3, N)
