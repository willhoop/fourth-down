"""Overtime and onside-kick logic in engine/decide.py, on tiny hand-made tables
so every expected value can be worked out by hand."""
import os
import sys

import pytest

from conftest import ROOT

sys.path.insert(0, os.path.join(ROOT, "engine"))
import decide as D                                          # noqa: E402

# every drive: 50% touchdown, 20% field goal, 30% nothing; possessions of 180 s
T = {"ot_drive": {"bin": 50, "td": [0.5, 0.5], "fg": [0.2, 0.2], "poss_secs": 180.0, "next_start": 70.0,
                  "max_possessions": 12},
     "tries": {"pat": 1.0, "two": 0.5}, "kickoff_start": 65.0}


def test_sudden_death_by_hand():
    """k=1: 0.7 + 0.3 * (1 - tie 0.5) = 0.85. k=2: 0.7 + 0.3 * (1 - 0.85) = 0.745."""
    st = {}
    assert D.ot_sudden(T, st, True, 30, 1) == pytest.approx(0.85)
    assert D.ot_sudden(T, st, True, 30, 2) == pytest.approx(0.745)


def test_tie_value_counts_for_us_only():
    """A tie worth nothing to us is worth everything to them. k=1, them with the
    ball: 0.7 + 0.3 * (1 - our tie value 0) = 1.0. Us with the ball: 0.7 + 0.3 * (1 - 1) = 0.7."""
    assert D.ot_sudden(T, {"tie_value": 0.0}, False, 30, 1) == pytest.approx(1.0)
    assert D.ot_sudden(T, {"tie_value": 0.0}, True, 30, 1) == pytest.approx(0.7)


def test_answer_down_three_by_hand():
    """Trailing by 3, k=2: a TD wins (0.5 * 1); a FG ties and they receive with
    k=1: 0.2 * (1 - 0.85) = 0.03. Total 0.53. Nothing: lose."""
    assert D.ot_answer(T, {}, True, 3, 30, 2) == pytest.approx(0.53)


def test_answer_down_seven_takes_better_try():
    """Trailing by 7, k=2: after the TD, PAT ties (1.0 * 0.15) or 2 wins (0.5):
    take 0.5. 0.5 * 0.5 = 0.25; a FG still trails: 0. Total 0.25."""
    assert D.ot_answer(T, {}, True, 7, 30, 2) == pytest.approx(0.25)


def test_possessions_from_the_clock():
    """10:00 left, 180 s possessions: floor(600/180) + 1 = 4. Playoffs: the cap."""
    assert D.ot_possessions(T, {}, 600) == 4
    assert D.ot_possessions(T, {"playoffs": 1}, 600) == 12
    assert D.ot_possessions(T, {}, 0) == 0


def test_phase_from_score_and_first_flag():
    base = {"qtr": 5, "half_seconds": 500, "home": 1}
    assert D.prepare(dict(base, score_diff=0, ot_first=True), {})["ot_phase"] == "first"
    assert D.prepare(dict(base, score_diff=0), {})["ot_phase"] == "sudden"
    assert D.prepare(dict(base, score_diff=-3, ot_first=True), {})["ot_phase"] == "answer"


def test_playoffs_have_no_tie_in_regulation_value():
    """End of regulation, tied: regular season = (1 - p_tie)(0.5 + edge) + p_tie * tie_value.
    Even teams (edge 0), p_tie 0.1, tie worth 0: 0.45. Playoffs: 0.5."""
    m = {"ot": {"slope": 1.0, "p_tie": 0.1}}
    assert D.ot_value(m, {"spread_used": 0.0, "tie_value": 0.0}) == pytest.approx(0.45)
    assert D.ot_value(m, {"spread_used": 0.0, "tie_value": 0.0, "playoffs": 1}) == pytest.approx(0.5)


def test_onside_only_when_the_kicker_trails(monkeypatch):
    """With value_after stubbed (our ball = 0.4, their ball = 0.1), a trailing
    kicker compares normal 0.1 with onside 0.2 * 0.4 + 0.8 * 0.1 = 0.16 and takes
    it; a leading kicker never onside-kicks."""
    m = {"onside": {"rate": 0.2, "recovered_yl": 52, "lost_yl": 47}, "kickoff_start": 65}
    monkeypatch.setattr(D, "value_after", lambda model, st, us_ball, sd, yl, secs: 0.4 if us_ball else 0.1)
    assert D.kick_after(m, {}, True, -6, 5) == pytest.approx(0.16)
    assert D.kick_after(m, {}, True, 3, 5) == pytest.approx(0.1)
    assert D.kick_after(m, {"ot": 1}, True, -6, 5) == pytest.approx(0.1)
