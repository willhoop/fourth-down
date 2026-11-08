"""Prospect-theory fit (engine/fit_prospect.py). Expected values are derived by
hand or from the parameters that generated the data, never from the output."""
import json
import math
import os

import numpy as np
import pytest

from conftest import ROOT

fp = pytest.importorskip("fit_prospect")


def test_prelec_weight_by_hand():
    # gamma = 1 is no distortion
    assert fp.weight(0.3, 1.0) == pytest.approx(0.3)
    # every Prelec curve crosses the diagonal at 1/e: -ln(1/e) = 1, and 1^gamma = 1
    for g in (0.3, 0.7, 1.4):
        assert fp.weight(math.exp(-1), g) == pytest.approx(math.exp(-1))
    # w(0.25, 0.5) = exp(-sqrt(ln 4)) = exp(-1.177410) = 0.308076
    assert fp.weight(0.25, 0.5) == pytest.approx(0.308076, abs=1e-6)
    # gamma > 1 pushes a long shot down: w(0.1, 2) = exp(-(ln 10)^2) = exp(-5.301898) = 0.004982
    assert fp.weight(0.1, 2.0) == pytest.approx(0.004982, abs=1e-6)


def test_value_function_by_hand():
    # 4^0.5 = 2; a loss of 4 with lam = 2 is -2 * 2 = -4
    assert fp.value(4, 0.5, 2.0) == pytest.approx(2.0)
    assert fp.value(-4, 0.5, 2.0) == pytest.approx(-4.0)
    # a loss of x weighs lam times a gain of x, whatever alpha is
    for a in (0.3, 0.6, 1.0):
        assert -fp.value(-3, a, 2.7) / fp.value(3, a, 2.7) == pytest.approx(2.7)


def test_option_values_by_hand():
    """One decision: go converts 50% (+4 units / -2 units), no field goal, punt is
    the reference (0). gamma = 1, alpha = 1, lam = 2:
    V(go) = 0.5 * 4 + 0.5 * (-2 * 2) = 0; with lam = 1 it is 0.5 * 4 - 0.5 * 2 = 1."""
    row = {"choice": "punt", "wp_go": 0.51, "wp_fg": None, "wp_punt": 0.46,
           "pc": 0.5, "go_s": 0.66, "go_f": 0.36, "pm": None, "fg_s": None, "fg_f": None}
    D = fp.gambles([row])
    assert D["go"][0] == pytest.approx([0.5, 4.0, -2.0])
    v2 = fp.option_values(D, 1.0, 2.0, 1.0)[0]
    v1 = fp.option_values(D, 1.0, 1.0, 1.0)[0]
    assert v2[0] == pytest.approx(0.0) and v1[0] == pytest.approx(1.0)
    assert v2[1] == -np.inf and v2[2] == pytest.approx(0.0)
    # the computer sees expected WP: (0.51 - 0.46) / 0.05 = 1 unit for going
    assert fp.computer_values(D)[0][0] == pytest.approx(1.0)


def test_shrinkage_by_hand():
    """Equal precision for coach and league: the posterior is halfway, and its
    variance halves: raw 1.0 (se 0.5), league 0 (sd 0.5) -> 0.5, sd sqrt(0.125)."""
    m, s = fp.shrink(1.0, 0.5, 0.0, 0.5)
    assert m == pytest.approx(0.5) and s == pytest.approx(math.sqrt(0.125))
    # prior spread = raw variance minus mean noise: var(0, 2) = 1, minus 0.75 -> sqrt(0.25)
    assert fp.prior_sd([0.0, 2.0], [math.sqrt(0.75)] * 2) == pytest.approx(0.5)


def test_fit_recovers_known_parameters():
    """Simulate coaches with known gamma, lam, alpha, tau; the fit must find them."""
    rng = np.random.default_rng(7)
    n = 20000
    true = (1.2, 2.5, 0.5, 0.3)
    pc = rng.uniform(0.25, 0.8, n)
    has_fg = rng.random(n) < 0.5
    D = {"go": np.c_[pc, rng.uniform(0.5, 5, n), rng.uniform(-5, -0.5, n)],
         "fg": np.c_[np.where(has_fg, rng.uniform(0.5, 0.95, n), np.nan),
                     rng.uniform(0.2, 3, n), rng.uniform(-3, -0.3, n)],
         "punt": np.zeros(n)}
    D["ev"] = np.c_[np.zeros(n), np.where(has_fg, 0.0, np.nan), np.zeros(n)]
    D["avail"] = ~np.isnan(D["ev"])
    V = fp.option_values(D, *true[:3]) / true[3]
    p = np.exp(V - V.max(1, keepdims=True))
    p /= p.sum(1, keepdims=True)
    D["choice"] = (p.cumsum(1) > rng.random((n, 1))).argmax(1)
    got, _ = fp.fit_league(D)
    for g, t in zip(got, true):
        assert g == pytest.approx(t, rel=0.12), (got, true)


def load_shipped():
    path = os.path.join(ROOT, "data", "prospect.json")
    if not os.path.exists(path):
        pytest.skip("data/prospect.json not built")
    return json.load(open(path, encoding="utf-8"))


def test_shipped_coaches_sit_between_their_own_calls_and_the_league():
    out = load_shipped()
    mu = out["shrinkage"]["prior_mean_log_lambda"]
    assert mu == pytest.approx(math.log(out["league"]["lambda"]), abs=1e-3)
    for c in out["coaches"]:
        lo_, hi_ = sorted([c["raw_lambda"], math.exp(mu)])
        assert lo_ - 0.01 <= c["lambda"] <= hi_ + 0.01, c
        assert c["lo"] <= c["lambda"] <= c["hi"], c
        assert c["few_calls"] == (c["decisions"] < 100)


def test_app_file_matches_the_data():
    out = load_shipped()
    text = open(os.path.join(ROOT, "app", "prospect.js"), encoding="utf-8").read()
    app = json.loads(text[text.index("const PROSPECT = ") + 17:text.index(";\nif (typeof module")])
    assert app["league"] == pytest.approx(round(out["league"]["lambda"], 2))
    assert len(app["coaches"]) == len(out["coaches"])
    for c in out["coaches"]:
        assert app["coaches"][c["coach"]] == [c["lambda"], c["lo"], c["hi"], c["decisions"]]


def test_published_claim_holds_on_held_out_seasons():
    """The report says prospect theory predicts unseen seasons better than a
    computer that likes kicking. The data must still say so."""
    h = load_shipped()["holdout"]
    assert h["prospect"]["log_loss"] < h["computer_likes_kicking"]["log_loss"] < h["computer"]["log_loss"]
