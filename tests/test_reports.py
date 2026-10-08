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
    """CHANGELOG top version = config version exactly. The white paper and the
    data files must match MAJOR.MINOR: a PATCH moves no published figure, so
    files stamped 1.0.0 stay valid under 1.0.1 (same rule as check_projects.py)."""
    import re
    from config import CONFIG
    mm = lambda v: ".".join(v.split(".")[:2])
    top = re.search(r"^## \[([0-9.]+)\]", open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8").read(), re.M).group(1)
    paper = re.search(r"Version:\s*([0-9.]+)", open(os.path.join(ROOT, "docs", "fourth-down-whitepaper.md"), encoding="utf-8").read()).group(1)
    assert top == CONFIG["version"]
    assert mm(paper) == mm(top)
    for f in ("model.json", "coach_grades.json", "kickers.json", "validation.json"):
        assert mm(json.load(open(os.path.join(ROOT, "data", f)))["version"]) == mm(top), f
