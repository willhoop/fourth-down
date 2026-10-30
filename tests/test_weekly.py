"""The weekly page data (app/weekly.js) is well formed and ordered."""
import json
import os

from conftest import ROOT


def load_weekly():
    text = open(os.path.join(ROOT, "app", "weekly.js"), encoding="utf-8").read()
    start = text.index("const WEEKLY = ") + len("const WEEKLY = ")
    return json.loads(text[start:text.index(";\nif (typeof module")])


def test_weekly_shape_and_order():
    w = load_weekly()
    weeks = [x["week"] for x in w["weeks"]]
    assert weeks == sorted(weeks, reverse=True)          # newest week first
    for wk in w["weeks"]:
        costs = [c["cost"] for c in wk["worst"]]
        assert costs == sorted(costs, reverse=True)       # costliest first
        assert all(c["confidence"] >= 0.9 for c in wk["worst"])
        assert all(c["coach_call"] != c["engine_call"] for c in wk["worst"])
        assert all(c["coach_call"] == "go" and c["engine_call"] == "go" and c["edge"] >= 0.03 for c in wk["best"])
        # kicking was a real option on every "gutsy" call
        assert all(max(v for k, v in c["wp"].items() if k != "go" and v is not None) >= 0.10 for c in wk["best"])
        # a pick-six is never "converted"
        assert not any(c["converted"] and "INTERCEPTED" in c["what_happened"] for c in wk["best"])


def test_site_has_no_emoji():
    """The app pages carry no emoji (pictographs U+1F000 and up, or U+2600-27BF)."""
    for name in ("index.html", "engine.js", "live.js"):
        text = open(os.path.join(ROOT, "app", name), encoding="utf-8").read()
        bad = [c for c in text if ord(c) >= 0x1F000 or 0x2600 <= ord(c) <= 0x27BF]
        assert not bad, f"{name}: {bad[:5]}"


def test_game_grades_follow_the_rule():
    """A+ exactly when a team made no confident mistakes in the game; a team with
    a confident mistake can never get A+; every grade is a known letter."""
    w = load_weekly()
    assert w["games"], "no games graded"
    for g in w["games"]:
        for tm in (g["away"], g["home"]):
            assert tm["grade"] in {"A+", "A", "B", "C", "D", "F"}
            assert (tm["grade"] == "A+") == (tm["mistakes"] == 0)
            assert tm["calls"] == len(tm["list"])
            assert tm["mistakes"] == sum(c["confident_mistake"] for c in tm["list"])


def test_weekly_game_has_one_answer_per_play():
    """The weekly game: at most 5 plays a week, no repeats; each answer is the
    option with the highest win chance, and only available options count."""
    w = load_weekly()
    assert w["weeks"][0]["quiz"], "newest week has no game"
    for wk in w["weeks"]:
        q = wk["quiz"]
        assert len(q) <= 5
        assert len({x["situation"] + x["team"] for x in q}) == len(q)
        for x in q:
            wp = {k: v for k, v in x["wp"].items() if v is not None}
            assert x["engine_call"] == max(wp, key=wp.get)
            assert x["coach_call"] in ("go", "fg", "punt")
            assert x["situation"].count(" · ") == 2 and "4th & " in x["situation"]


def test_weekly_game_skips_obvious_calls():
    """Read the rule from the shipped engine/weekly.py: no pick is a spot where
    QUIZ_OBVIOUS or more of past coaches already made the engine's call (checked on
    the newest week; a thin week may fall back to obvious ones), at most QUIZ_SAME_CALL picks share an answer, and
    at most one pick per team."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    import weekly
    w = load_weekly()
    for wk in w["weeks"]:
        q = wk["quiz"]
        shares = [x["league_share"] for x in q]
        assert all(0 <= s <= 1 for s in shares)
        calls = [x["engine_call"] for x in q]
        assert max(calls.count(c) for c in set(calls)) <= weekly.QUIZ_SAME_CALL
        teams = [x["team"] + x["opp"] for x in q]
        assert len(set(teams)) == len(teams)
    assert all(x["league_share"] < weekly.QUIZ_OBVIOUS for x in w["weeks"][0]["quiz"])


def test_coach_share_bins_by_hand():
    """4th & 1 at the opponent 15 -> togo bin 0 (1 yard), zone bin 0 (1-20).
    4th & 7 at own 30 (yardline_100 70) -> togo bin 3 (7-10), zone bin 3 (61-80)."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "engine"))
    import weekly
    assert weekly.bins(1, 15) == (0, 0)
    assert weekly.bins(7, 70) == (3, 3)
    assert weekly.bins(11, 99) == (4, 4)
