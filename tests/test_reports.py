"""Published figures must match the pipeline output they came from."""
import importlib.util
import json
import os

import pytest

from conftest import ROOT

spec = importlib.util.spec_from_file_location("render_reports", os.path.join(ROOT, "build", "render_reports.py"))
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)


def test_reports_and_whitepaper_are_current():
    """Re-render every report and the white paper's results block; nothing may differ."""
    for rel, body in render.render_all(write=False).items():
        on_disk = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        assert on_disk == body, f"{rel} is stale: run py build/render_reports.py"


def test_versions_agree():
    """CHANGELOG top version = config version = model, grades and white-paper stamps."""
    import re
    from config import CONFIG
    top = re.search(r"^## \[([0-9.]+)\]", open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read(), re.M).group(1)
    paper = re.search(r"Version:\s*([0-9.]+)", open(os.path.join(ROOT, "docs", "fourth-down-whitepaper.md"), encoding="utf-8").read()).group(1)
    assert top == CONFIG["version"] == paper
    for f in ("model.json", "coach_grades.json", "kickers.json", "validation.json"):
        assert json.load(open(os.path.join(ROOT, "data", f)))["version"] == top, f
