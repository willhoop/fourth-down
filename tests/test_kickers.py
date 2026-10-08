"""Kicker skill estimation. Expected values derived by hand."""
import math

import numpy as np
import pandas as pd
import pytest

import kickers


def test_unpenalised_fit_recovers_rates():
    """League logit 0 everywhere. At 40 yd (x = 0): 3 of 4 made. At 50 yd (x = 1):
    1 of 2 made. The MLE solves sigmoid(a) = 3/4 and sigmoid(a + b) = 1/2, so
    a = ln 3 = 1.0986 and b = -ln 3."""
    z = np.zeros(6)
    x = np.array([0, 0, 0, 0, 1, 1], dtype=float)
    y = np.array([1, 1, 1, 0, 1, 0], dtype=float)
    a, b = kickers.fit_one(z, x, y, None, None)
    assert a == pytest.approx(math.log(3), abs=1e-6)
    assert b == pytest.approx(-math.log(3), abs=1e-6)


def test_prior_shrinks_toward_league():
    """Same data with a tight prior: both estimates move toward 0 but keep their sign."""
    z = np.zeros(6)
    x = np.array([0, 0, 0, 0, 1, 1], dtype=float)
    y = np.array([1, 1, 1, 0, 1, 0], dtype=float)
    a, b = kickers.fit_one(z, x, y, 0.2, 0.1)
    assert 0 < a < math.log(3)
    assert -math.log(3) < b < 0


def test_one_parameter_prior_closed_form_check():
    """Range prior ~0 (b fixed near 0). One kick at x = 0, made, league logit 0,
    accuracy prior sd 1. MAP of a solves (1 - sigmoid(a)) - a = 0. Newton by
    hand from a = 0.4: a = 0.4010581375."""
    a, b = kickers.fit_one(np.zeros(1), np.zeros(1), np.ones(1), 1.0, 1e-6)
    assert a == pytest.approx(0.4010581375, abs=1e-6)
    assert abs(b) < 1e-6


def test_fifty_pct_distance():
    """League logit (60 - d) / 10 crosses 0 at 60 yd; the scan returns the first
    half-yard step past it, 60.5. A kicker with a = 1 moves it 10 yd: 70.5 is past
    the 70-yd data edge, so None."""
    z_at = lambda d: (60 - d) / 10
    assert kickers.fifty_pct_distance(z_at, 0.0, 0.0) == 60.5
    assert kickers.fifty_pct_distance(z_at, 1.0, 0.0) is None


def test_replacement_uses_kickers_outside_top_n():
    """Cutoff 2 per season. 2020: K1 (5 kicks), K2 (4), K3 (2) -> K3 is replacement.
    2021: K2 (5), K3 (4), K1 (2) -> K1 is replacement. The 4 replacement kicks:
    at 40 yd one make and one miss, at 50 yd one make and one miss. League logit
    0, so the pooled MLE is a = 0, b = 0, and the make rate is 0.5."""
    def kick(season, k, dist, made):
        return {"season": season, "kicker_player_id": k, "kick_distance": dist, "made": made, "_z": 0.0}
    rows = [kick(2020, "K1", 40.0, 1) for _ in range(5)] + [kick(2020, "K2", 40.0, 1) for _ in range(4)]
    rows += [kick(2020, "K3", 40.0, 1), kick(2020, "K3", 50.0, 0)]
    rows += [kick(2021, "K2", 40.0, 1) for _ in range(5)] + [kick(2021, "K3", 40.0, 1) for _ in range(4)]
    rows += [kick(2021, "K1", 40.0, 0), kick(2021, "K1", 50.0, 1)]
    r = kickers.replacement(pd.DataFrame(rows), {"rank_cutoff": 2})
    assert r["attempts"] == 4
    assert r["kicker_seasons"] == 2
    assert r["made_pct"] == 0.5
    assert r["a"] == pytest.approx(0.0, abs=1e-6)
    assert r["b"] == pytest.approx(0.0, abs=1e-6)
