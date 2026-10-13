"""engine/compare_nfl4th.py: the helpers that turn two engines' win
probabilities into a call and a margin. Expected values derived by hand."""
import json
import os
import sys

import numpy as np
import pandas as pd

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "engine"))
import compare_nfl4th as C                                  # noqa: E402
from config import CONFIG                                   # noqa: E402


def frame(rows):
    return pd.DataFrame(rows, columns=["go", "fg", "punt"])


def test_best_option_skips_unavailable():
    """Row 1: go .40 beats punt .35 (no FG). Row 2: FG .60 beats go .55, punt .50."""
    wp = frame([[0.40, np.nan, 0.35], [0.55, 0.60, 0.50]])
    assert list(C.best_option(wp)) == ["go", "fg"]


def test_margin_is_gap_to_second_best_or_nan():
    """.40 - .35 = .05; .60 - .55 = .05; one option only: no decision, NaN."""
    m = C.margin(frame([[0.40, np.nan, 0.35], [0.55, 0.60, 0.50], [0.30, np.nan, np.nan]]))
    assert np.allclose(m[:2], [0.05, 0.05]) and np.isnan(m[2])


def test_go_advantage_against_best_kick():
    """go .40 vs best kick .35 = +.05; go .55 vs FG .60 = -.05."""
    g = C.go_advantage(frame([[0.40, np.nan, 0.35], [0.55, 0.60, 0.50]]))
    assert np.allclose(g, [0.05, -0.05])


def test_brier_difference_by_hand():
    """Game A: ours .8 vs nfl4th .6 on a win: (.04 - .16) = -.12.
    Game B: ours .3 vs nfl4th .5 on a loss: (.09 - .25) = -.16. Mean -.14."""
    r = C.brier_diff_ci(np.array(["A", "B"]), np.array([0.8, 0.3]), np.array([0.6, 0.5]), np.array([1.0, 0.0]), reps=50)
    assert r["diff"] == -0.14 and r["games"] == 2


def test_published_comparison_matches_version():
    """The shipped comparison was produced by this major.minor version."""
    r = json.load(open(os.path.join(ROOT, "data", "nfl4th_comparison.json")))
    assert r["version"].split(".")[:2] == CONFIG["version"].split(".")[:2]
    assert 0 < r["agreement"]["clear_calls"] <= 1 and r["plays"]["matched"] > 40000
