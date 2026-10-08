"""app/live.js turns ESPN scoreboard games into form values. The fixture copies
the feed's real structure; expected values are read off the fixture by hand."""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(side_by_id):
    script = ("const L=require(process.argv[1]+'/app/live.js');"
              "const f=JSON.parse(require('fs').readFileSync(process.argv[1]+'/tests/fixtures/espn_scoreboard.json','utf8'));"
              "const sides=JSON.parse(process.argv[2]);"
              "const g=L.games(f);"
              "console.log(JSON.stringify({order:g.map(x=>x.id),out:Object.fromEntries(g.map(x=>[x.id,L.fill(x,sides[x.id])]))}));")
    res = subprocess.run(["node", "-e", script, ROOT, json.dumps(side_by_id)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_live_game_sorted_first():
    """The game in progress (id 2) is listed before the scheduled one."""
    assert run({"1": "away", "2": "away"})["order"] == ["2", "1"]


def test_pregame_teams_line_and_roof():
    """We are TB, the away team; "DAL -8.5" makes us 8.5-point underdogs: +8.5.
    The stadium is indoors. No live fields before kickoff."""
    f = run({"1": "away", "2": "away"})["out"]["1"]
    assert f["our"] == "TB" and f["their"] == "DAL" and f["home"] is False
    assert f["line"] == 8.5 and f["indoor"] is True
    assert "down" not in f and "usScore" not in f


def test_pregame_favorite_side():
    """Same game from Dallas's side: -8.5 (favored), home."""
    f = run({"1": "home", "2": "away"})["out"]["1"]
    assert f["our"] == "DAL" and f["home"] is True and f["line"] == -8.5


def test_in_game_situation_from_the_rams_side():
    """LAR (away) at WSH: ESPN codes become nflverse codes (LAR->LA, WSH->WAS).
    Score 17-20, Q4 2:41, 4th & 2. "WSH 38" is the opponent's 38 for the Rams.
    Rams (away) have 3 timeouts, Washington (home) 1. Possession id 14 = Rams. EVEN = pick'em."""
    f = run({"1": "away", "2": "away"})["out"]["2"]
    assert f["our"] == "LA" and f["their"] == "WAS"
    assert (f["usScore"], f["themScore"]) == (17, 20)
    assert (f["qtr"], f["mm"], f["ss"]) == (4, 2, 41)
    assert (f["down"], f["togo"], f["yd"], f["ownSide"]) == (4, 2, 38, False)
    assert (f["pto"], f["dto"]) == (3, 1)
    assert f["weHaveBall"] is True and f["line"] == 0 and f["indoor"] is False


def test_in_game_from_the_home_side():
    """Washington's view: "WSH 38" is its own 38; timeouts swap; it does not have the ball."""
    f = run({"1": "away", "2": "home"})["out"]["2"]
    assert f["ownSide"] is True and (f["pto"], f["dto"]) == (1, 3) and f["weHaveBall"] is False
