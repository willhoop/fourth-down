import json
import math
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "engine"))

S1 = 1 / (1 + math.exp(-1))     # sigmoid(1)  = 0.7310585786...
S_1 = 1 - S1                    # sigmoid(-1) = 0.2689414214...


def load_shipped_model():
    """Read the model from the file the app actually loads, not a copy."""
    text = open(os.path.join(ROOT, "app", "model.js"), encoding="utf-8").read()
    start = text.index("const MODEL = ") + len("const MODEL = ")
    end = text.index(";\nif (typeof module")
    return json.loads(text[start:end])


@pytest.fixture(scope="session")
def shipped():
    return load_shipped_model()


def make_stub(feature, threshold, left, right):
    """A WP model with one split: x[feature] <= threshold -> left, else right (logits)."""
    return {
        "wp": {"baseline": 0.0, "trees": [[[feature, threshold, 1, 2, 0.0, 0],
                                           [0, 0.0, 0, 0, left, 1],
                                           [0, 0.0, 0, 0, right, 1]]]},
        "conv": {"base": {"names": ["is4"], "coef": [0.0], "intercept": 0.0}},
        "fg": {"models": {"base": {"names": ["dist"], "coef": [0.0], "intercept": math.log(3)}}},
        "gain": {"edges": [1, 100], "success_q": [[5.0]], "fail_mean": [0.0]},
        "clock": dict({k: [5.0, 5.0] for k in ("go_success", "go_fail", "punt", "fg", "score",
                                               "play_first", "play_short", "punt_fair_catch")},
                      timeout_play=2.0, spike_total=2.5),
        "play": {"gain_q": [[[5.0]], [[5.0]], [[5.0]]], "p_turnover": [0.0, 0.0, 0.0]},
        "kickoff_start": 75.0,
        "punt": {"bins": [{"lo": 1, "hi": 99, "q": [80.0], "p_td": 0.0, "p_muff": 0.0,
                           "muff_spot": 40.0, "p_fc": 0.0}], "adj": {}},
        "tries": {"pat": 1.0, "two": 0.0},     # a touchdown is worth exactly 7 in the stub
        "rules": {"season": 2025, "td_points": 6, "fg_distance_add": 17, "fg_snap_to_spot": 7,
                  "missed_fg_min_spot": 20, "fg_max_distance": 70, "tossup_margin": 0.01,
                  "fair_catch_kick_window": 10},
    }
