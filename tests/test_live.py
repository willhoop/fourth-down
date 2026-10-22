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
    assert "neutral" not in f
    assert "down" not in f and "usScore" not in f


def test_neutral_site_flag():
    """A game marked neutralSite (London, the Super Bowl) comes back neutral."""
    script = ("const L=require(process.argv[1]+'/app/live.js');"
              "const g={id:'9',name:'X',state:'pre',c:{neutralSite:true,competitors:["
              "{homeAway:'home',team:{id:'1',abbreviation:'JAX'}},{homeAway:'away',team:{id:'2',abbreviation:'PHI'}}]}};"
              "console.log(JSON.stringify(L.fill(g,'away')));")
    out = json.loads(subprocess.run(["node", "-e", script, ROOT], capture_output=True, text=True, check=True).stdout)
    assert out["neutral"] is True and out["our"] == "PHI"


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


def node(js):
    res = subprocess.run(["node", "-e", "const L=require(process.argv[1]+'/app/live.js');" + js, ROOT],
                         capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_summary_line_after_kickoff():
    """The summary feed keeps the line after kickoff. "HOU -6.5": HOU favored by
    6.5, so -6.5 for HOU and +6.5 for TEN. A book with no usable line is skipped."""
    sum_ = {"pickcenter": [{"details": None}, {"provider": {"name": "DraftKings"}, "details": "HOU -6.5"}]}
    out = node("const s=" + json.dumps(sum_) + ";console.log(JSON.stringify([L.lineFromSummary(s,'HOU'),L.lineFromSummary(s,'TEN')]))")
    assert out == [-6.5, 6.5]


def test_no_line_is_undefined():
    """No pickcenter, or text that is not a line, gives no value (the app then sets the teams even).
    "EVEN" is a line of 0; ESPN's WSH maps to WAS."""
    out = node("console.log(JSON.stringify([L.lineFromSummary({},'HOU')===undefined,L.parseLine('OFF','HOU')===undefined,"
               "L.parseLine('EVEN','HOU'),L.parseLine('WSH -3','WAS')]))")
    assert out == [True, True, 0, -3]


# ---------- shape check: a saved real ESPN scoreboard (week 8 of 2026, fetched
# 2026-10-22) must pass, and each kind of break must be named, not ignored.
REAL = os.path.join(ROOT, "tests", "fixtures", "espn_scoreboard_real.json")


def validate(feed):
    res = subprocess.run(["node", "-e", "const L=require(process.argv[1]+'/app/live.js');"
                          "console.log(JSON.stringify(L.validate(JSON.parse(require('fs').readFileSync(0,'utf8')))))", ROOT],
                         input=json.dumps(feed), capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_real_feed_has_the_shape_we_read():
    feed = json.load(open(REAL, encoding="utf-8"))
    assert len(feed["events"]) == 14
    assert validate(feed) == [], "ESPN's scoreboard shape changed: update app/live.js before the app breaks"


def test_handmade_fixture_also_passes():
    assert validate(json.load(open(os.path.join(ROOT, "tests", "fixtures", "espn_scoreboard.json")))) == []


def test_each_break_is_named():
    feed = json.load(open(REAL, encoding="utf-8"))
    assert validate({}) == ["events: missing or not a list"]
    b = json.loads(json.dumps(feed))
    del b["events"][0]["competitions"][0]["competitors"][0]["team"]["abbreviation"]
    assert validate(b) == ["events[0].competitors[0].team: needs abbreviation and id"]
    b = json.loads(json.dumps(feed))
    b["events"][1]["competitions"][0]["status"]["type"]["state"] = "halftime"
    assert validate(b) == ["events[1].status.type.state: missing or unknown"]
    b = json.loads(json.dumps(feed))
    b["events"][2]["competitions"][0]["competitors"].pop()
    assert validate(b) == ["events[2].competitors: need one home and one away"]
    b = json.loads(json.dumps(feed))
    c = b["events"][3]["competitions"][0]
    c["status"]["type"]["state"] = "in"
    del c["status"]["period"]
    assert validate(b) == ["events[3].status.period: missing in a live game"]


@pytest.mark.skipif(os.environ.get("FD_LIVE_CHECK") != "1", reason="network check; runs in the scheduled ESPN workflow")
def test_live_espn_feed_shape():
    """Fetches ESPN now. Fails loudly (red workflow, email) when the shape changes."""
    import urllib.request
    url = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    feed = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "fourth-down-check"}), timeout=20))
    assert validate(feed) == [], "ESPN's scoreboard shape changed"


# ---------- which game is on the TV (text read off a score bar)
NAMES = {"NE": "Patriots", "CHI": "Bears", "PIT": "Steelers", "NO": "Saints", "SF": "49ers", "ATL": "Falcons"}


def match(text):
    script = ("const L=require(process.argv[1]+'/app/live.js');"
              "const f=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
              "const m=L.matchGame(process.argv[3],L.games(f),JSON.parse(process.argv[4]));"
              "console.log(JSON.stringify(m?{name:m.game.name,teams:m.teams,sure:m.sure}:null));")
    res = subprocess.run(["node", "-e", script, ROOT, REAL, text, json.dumps(NAMES)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


def test_both_abbreviations_find_the_game():
    m = match("NE 14 CHI 10 3RD & 4 12:41")
    assert m["name"] == "NE @ CHI" and sorted(m["teams"]) == ["CHI", "NE"] and m["sure"]


def test_digit_read_as_letter_is_only_a_guess():
    """'N0' could be NO and '5F' SF (0->O, 5->S): the guess ranks the game, the
    exact team makes it sure. A guess alone ('T8' -> TB) is never sure."""
    m = match("PIT 7 N0 3")
    assert m["name"] == "PIT VS NO" and m["teams"] == ["PIT"] and m["sure"]
    m = match("5F 21 ATL 17")
    assert m["name"] == "SF @ ATL" and m["teams"] == ["ATL"] and m["sure"]
    m = match("T8 10")
    assert m["name"] == "TB @ CAR" and m["sure"] is False


def test_nickname_alone_counts():
    assert match("STEELERS 7  SAINTS 3")["name"] == "PIT VS NO"


def test_one_team_is_enough_when_no_other_game_is_close():
    m = match("BEARS 10  2ND & 7")
    assert m == {"name": "NE @ CHI", "teams": ["CHI"], "sure": True}


def test_nothing_readable_is_no_match():
    assert match("4TH & 2  12:41  FOX") is None


def test_team_glued_to_score_is_split():
    """OCR often drops the space: 'NE14 CHI10'."""
    m = match("NE14 CHI10 3RD &4")
    assert m["name"] == "NE @ CHI" and m["sure"]


def test_logo_read_as_letter_is_close_not_sure():
    """'QCHI' (a logo read as Q) is one letter from CHI: it ranks the game but is
    never 'sure' on its own, so the app asks which game it is."""
    m = match("QCHI 10")
    assert m["name"] == "NE @ CHI" and m["sure"] is False
