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
