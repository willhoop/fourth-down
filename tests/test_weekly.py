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
