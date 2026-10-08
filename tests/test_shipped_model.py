"""Checks on the shipped model (read from app/model.js, the file the app loads).

Expected outcomes come from football rules and published findings, not from
the model's current output.
"""
import json
import os
import random
import shutil
import subprocess

import pytest

import decide
from conftest import ROOT

MID = dict(score_diff=0, qtr=2, half_seconds=900, yardline=50, ydstogo=4,
           pos_to=3, def_to=3, home=1, receive_2h=0)
ALL = {"weather": True, "stadium": True, "spread": True, "kicker": True}


def test_version_matches_config(shipped):
    """Same MAJOR.MINOR: a PATCH release moves no figure, so the model stays valid."""
    from config import CONFIG
    mm = lambda v: ".".join(v.split(".")[:2])
    assert mm(shipped["version"]) == mm(CONFIG["version"])


def test_fg_probability_falls_with_distance(shipped):
    ps = [decide.p_field_goal(shipped, {"yardline": d - 17}, {}) for d in range(18, 71)]
    assert all(a > b for a, b in zip(ps, ps[1:]))
    assert ps[0] > 0.95            # chip shots: NFL kickers make ~98% from under 30
    assert ps[-1] < 0.5            # 70 yd: no one makes these at even odds


def test_conversion_falls_with_distance(shipped):
    ps = [decide.p_convert(shipped, dict(MID, ydstogo=t), {}) for t in range(1, 21)]
    assert all(a > b for a, b in zip(ps, ps[1:]))
    assert 0.6 < ps[0] < 0.8       # 4th & 1 converts roughly 2 times in 3 (Romer 2006: 64% on 3rd & 1)


def test_wp_rises_with_lead(shipped):
    s = dict(score_diff=0, game_seconds=1800, half_seconds=1800, second_half=1, yardline=75,
             down=1, ydstogo=10, pos_to=3, def_to=3, tmw_pending=1, receive_2h=0, spread=0, home=1)
    ps = [decide.wp_raw(shipped, dict(s, score_diff=d)) for d in range(-21, 22)]
    assert all(a <= b for a, b in zip(ps, ps[1:]))


def test_kickoff_spot_is_plausible(shipped):
    # 2025 rules: touchback to the 35 (yardline 65); returns land around there.
    assert 55 <= shipped["kickoff_start"] <= 80


def test_last_play_down_two_kicks(shipped):
    """0:05 left, down 2, 4th & 10 at the opp 20: only a field goal wins."""
    out = decide.decide(shipped, dict(MID, qtr=4, half_seconds=5, score_diff=-2, yardline=20, ydstogo=10))
    assert out["best"] == "fg"


def test_down_four_late_goes(shipped):
    """1:00 left, down 4, 4th & 2 at the opp 30: a field goal still loses."""
    out = decide.decide(shipped, dict(MID, qtr=4, half_seconds=60, score_diff=-4, yardline=30, ydstogo=2))
    assert out["best"] == "go"


def test_long_yardage_deep_punts(shipped):
    """First quarter, tied, 4th & 15 at own 20: punt (every published model agrees)."""
    out = decide.decide(shipped, dict(MID, qtr=1, half_seconds=1700, yardline=80, ydstogo=15))
    assert out["best"] == "punt"


def test_early_down_midgame_runs_a_play(shipped):
    """2nd & 7 at the opp 25, second quarter, tied: run a play; the kick can wait."""
    out = decide.decide(shipped, dict(MID, down=2, ydstogo=7, yardline=25))
    assert out["best"] == "go" and out["wp"]["punt"] is None


def test_early_down_kicks_when_time_expires(shipped):
    """2nd & 7 at the opp 20, 0:04 left, down 2, no timeouts: a play would end the
    game short of a score most of the time, so kick now."""
    out = decide.decide(shipped, dict(MID, qtr=4, half_seconds=4, score_diff=-2, down=2,
                                      ydstogo=7, yardline=20, pos_to=0))
    assert out["best"] == "fg"


def test_team_table(shipped):
    """32 teams; Denver plays at altitude; Detroit and New Orleans play under a roof;
    Green Bay does not. Every listed kicker is one the app can select."""
    T = shipped["teams"]
    assert len(T) == 32
    assert T["DEN"]["altitude_kft"] > 5 and T["GB"]["altitude_kft"] == 0
    assert T["DET"]["indoor"] == 1 and T["NO"]["indoor"] == 1 and T["GB"]["indoor"] == 0
    ids = {k["id"] for k in shipped["fg"]["kickers"]}
    assert all(t["kicker"] in ids for t in T.values() if t["kicker"])


def test_overtime_and_tries_are_measured(shipped):
    """Extra points are good about 94-96% of the time, 2-point tries about 45-50%
    (since 2015). The better team wins overtime more often (positive slope)."""
    assert 0.92 < shipped["tries"]["pat"] < 0.97
    assert 0.42 < shipped["tries"]["two"] < 0.53
    assert shipped["ot"]["slope"] > 0 and 0 < shipped["ot"]["p_tie"] < 0.15


def test_wind_and_altitude_directions(shipped):
    """Clark et al. (2013): wind lowers and altitude raises make probability."""
    st = {"yardline": 33, "wind": 0, "temp": 60, "precip": 0}
    calm = decide.p_field_goal(shipped, st, {"weather": True})
    windy = decide.p_field_goal(shipped, dict(st, wind=25), {"weather": True})
    assert windy < calm
    sea = decide.p_field_goal(shipped, dict(st, altitude_kft=0.0), {"stadium": True})
    denver = decide.p_field_goal(shipped, dict(st, altitude_kft=5.28), {"stadium": True})
    assert denver > sea


def test_replacement_kicker_is_below_league(shipped):
    r = shipped["fg"]["replacement"]
    league = decide.p_field_goal(shipped, {"yardline": 33}, {})
    repl = decide.p_field_goal(shipped, {"yardline": 33, "kicker_a": r["a"], "kicker_b": r["b"]}, {"kicker": True})
    assert repl < league


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_python_and_js_engines_agree(shipped):
    """The app runs app/engine.js; the grader and docs use engine/decide.py."""
    rng = random.Random(7)
    cases = []
    for _ in range(60):
        st = dict(score_diff=rng.randint(-17, 17), qtr=rng.randint(1, 4), half_seconds=rng.randint(1, 1800),
                  yardline=rng.randint(1, 99), ydstogo=rng.randint(1, 15), pos_to=rng.randint(0, 3),
                  def_to=rng.randint(0, 3), home=rng.randint(0, 1), receive_2h=rng.randint(0, 1),
                  spread=rng.uniform(-10, 10), wind=rng.uniform(0, 25), temp=rng.uniform(10, 90),
                  precip=rng.randint(0, 1), indoor=rng.randint(0, 1), altitude_kft=rng.choice([0, 5.28]),
                  kicker_a=rng.uniform(-0.5, 0.5), kicker_b=rng.uniform(-0.2, 0.2))
        st["ydstogo"] = min(st["ydstogo"], st["yardline"])
        st["down"] = rng.randint(1, 4)
        st["short"] = rng.choice([None, "inches", "full_yard", "went", "kicked"])
        if st["short"] is None:
            del st["short"]
        tog = {k: rng.random() < 0.5 for k in ALL}
        cases.append({"state": st, "tog": tog})
    script = (
        "const M=require(process.argv[1]+'/app/model.js'),E=require(process.argv[1]+'/app/engine.js');"
        "const c=JSON.parse(require('fs').readFileSync(0,'utf8'));"
        "console.log(JSON.stringify(c.map(x=>E.decide(M,x.state,x.tog))));")
    res = subprocess.run(["node", "-e", script, ROOT], input=json.dumps(cases), capture_output=True,
                         text=True, check=True)
    js = json.loads(res.stdout)
    for case, j in zip(cases, js):
        p = decide.decide(shipped, case["state"], case["tog"])
        assert p["best"] == j["best"]
        for k in ("go", "fg", "punt"):
            if p["wp"][k] is None:
                assert j["wp"][k] is None
            else:
                assert p["wp"][k] == pytest.approx(j["wp"][k], abs=1e-9)
