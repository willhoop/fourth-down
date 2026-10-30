"""This week's 4th-down calls: the costliest real decisions and the best gutsy ones.

Grades every 4th down of the current season (CONFIG["current_season"]) with the
shipped model and bootstrap, then lists, for each week played so far:

- worst calls: confident mistakes (>= 90% of replicates agree), largest cost first
- best calls: the coach went for it, the engine agreed by 3+ WP points,
  >= 90% of replicates agree, and kicking was a real option (the kick left a
  10%+ win chance, outside the final two minutes)

- the weekly game: five of the week's plays to call before the reveal (see quiz())

Run:  py engine/weekly.py [--download]   (--download refreshes the season's parquet first)
Out:  data/weekly.json, app/weekly.js

A scheduled GitHub Action (.github/workflows/weekly.yml) runs this every
Tuesday during the season and redeploys the site.
"""
import datetime
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG                                  # noqa: E402
from load_data import ROOT                                 # noqa: E402
from grade_coaches import fmt_clock, fmt_spot, score       # noqa: E402

TOP_WORST, TOP_BEST, BEST_MARGIN, MIN_KICK_WP = 10, 5, 0.03, 0.10
# The weekly game: the 5 least obvious plays of the week that still have a clear
# answer. "Obvious" = coaches since 2014 made the engine's call in at least
# QUIZ_OBVIOUS of similar spots (same yards-to-go bin and field zone). Among the
# rest, rank by edge x (1 - that share): a clear edge that coaches usually miss.
# At most QUIZ_SAME_CALL plays share an answer, so "always say go" cannot win,
# and at most one play per team in a game.
QUIZ_MIN_EDGE, QUIZ_OBVIOUS, QUIZ_SAME_CALL = 0.01, 0.80, 3
QUIZ_TOGO_BINS = [0, 1, 3, 6, 10, 99]                    # 1 / 2-3 / 4-6 / 7-10 / 11+
QUIZ_ZONE_BINS = [0, 20, 40, 60, 80, 100]                # yardline_100: red zone ... own 20
# Game grade: A+ = no confident mistakes. Otherwise the team-game is ranked
# against every team-game since 2014 that had one, by win chance given up:
# better than 75% of them = A, 50% = B, 25% = C, 10% = D, else F.
GAME_LETTERS = [(0.25, "A"), (0.50, "B"), (0.75, "C"), (0.90, "D"), (1.01, "F")]


def history_costs():
    """Win chance given up on confident mistakes, per team-game, 2014 to last season,
    for team-games with at least one (from data/decisions.csv.gz)."""
    import numpy as np
    import pandas as pd
    h = pd.read_csv(os.path.join(ROOT, "data", "decisions.csv.gz"))
    h = h[h["season"] < CONFIG["current_season"]]
    wp_choice = np.select([h["choice"] == "go", h["choice"] == "fg"], [h["wp_go"], h["wp_fg"]], h["wp_punt"])
    cost = (h[["wp_go", "wp_fg", "wp_punt"]].max(axis=1) - wp_choice).clip(lower=0)
    conf = (h["choice"] != h["best"]) & (h["conf_wrong"] >= CONFIG["confident_share"])
    h = h.assign(c=cost.where(conf, 0.0))
    per = h.groupby(["game_id", "posteam"])["c"].sum()
    return np.sort(per[per > 0].values)


def game_grade(cost, ref):
    if cost <= 0:
        return "A+"
    worse_than = float((ref < cost).mean())      # share of mistake-games with a smaller cost
    return next(L for cut, L in GAME_LETTERS if worse_than < cut)


def call_row(r):
    sd = int(r["score_diff"])
    return {"when": situation(r), "coach_call": r["choice"], "engine_call": r["best"],
            "edge": round(float(r["margin"]), 3), "cost": round(float(r["cost"]), 3),
            "confident_mistake": bool(r["confident_mistake"]),
            "sure": round(float(1 - r["conf_wrong"]), 2) if r["choice"] == r["best"] else round(float(r["conf_wrong"]), 2),
            "what_happened": str(r["desc"])[:160]}


def team_situation(r):
    """The quiz situation in team terms: "Q1 10:30 · BAL down 4 · 4th & 3 at ATL 3"."""
    sd, tm, op, yl = int(r["score_diff"]), r["posteam"], r["defteam"], int(r["yardline_100"])
    score_txt = "tied" if sd == 0 else (f"{tm} up {sd}" if sd > 0 else f"{tm} down {-sd}")
    spot = "midfield" if yl == 50 else (f"{op} {yl}" if yl < 50 else f"{tm} {100 - yl}")
    return f"{fmt_clock(r['qtr'], r['half_seconds_remaining'])} · {score_txt} · 4th & {int(r['ydstogo'])} at {spot}"


def coach_shares():
    """Share of past coach decisions (seasons before the current one) that made
    each call, by yards-to-go bin and field zone: {(togo_bin, zone_bin, call): share}."""
    import pandas as pd
    h = pd.read_csv(os.path.join(ROOT, "data", "decisions.csv.gz"))
    h = h[h["season"] < CONFIG["current_season"]]
    h = h.assign(tb=pd.cut(h["ydstogo"], QUIZ_TOGO_BINS, labels=False),
                 zb=pd.cut(h["yardline_100"], QUIZ_ZONE_BINS, labels=False))
    out = {}
    for (tb, zb), grp in h.groupby(["tb", "zb"]):
        for call, share in grp["choice"].value_counts(normalize=True).items():
            out[(int(tb), int(zb), call)] = float(share)
    return out


def bins(togo, yl):
    import numpy as np
    return int(np.digitize(togo, QUIZ_TOGO_BINS[1:-1], right=True)), int(np.digitize(yl, QUIZ_ZONE_BINS[1:-1], right=True))


def quiz(g, shares):
    """The weekly game's five plays (see QUIZ_* above), in a fixed shuffled order.
    Every play is a confident engine call (>= 90% of replicates), so each has one answer."""
    import numpy as np
    sure = np.where(g["choice"] == g["best"], 1 - g["conf_wrong"], g["conf_wrong"])
    forced = (g["qtr"] == 4) & (g["half_seconds_remaining"] <= 120)
    ok = g[(sure >= CONFIG["confident_share"]) & ~forced & (g["margin"] >= QUIZ_MIN_EDGE)].copy()
    ok["share"] = [shares.get((*bins(r.ydstogo, r.yardline_100), r.best), 0.5) for r in ok.itertuples()]
    ok["interest"] = ok["margin"] * (1 - ok["share"])
    picked, calls, teams = [], {}, set()
    for limit in (QUIZ_OBVIOUS, 1.01):                    # a thin week: allow obvious plays last
        for i, r in ok[ok["share"] < limit].sort_values("interest", ascending=False).iterrows():
            if len(picked) == 5:
                break
            key = (r["game_id"], r["posteam"])
            if i in picked or key in teams or calls.get(r["best"], 0) >= QUIZ_SAME_CALL:
                continue
            picked.append(i)
            teams.add(key)
            calls[r["best"]] = calls.get(r["best"], 0) + 1
    rows = ok.loc[picked]
    rows = rows.assign(k=[(int(b) * 7919) % 997 for b in rows["play_id"]]).sort_values(["k", "game_id"])
    return [{"team": r["posteam"], "opp": r["defteam"], "coach": r["coach"], "situation": team_situation(r),
             "coach_call": r["choice"], "engine_call": r["best"],
             "wp": {k: (None if r["wp_" + k] != r["wp_" + k] else round(float(r["wp_" + k]), 3))
                    for k in ("go", "fg", "punt")},
             "league_share": round(float(r["share"]), 2),
             "what_happened": str(r["desc"])[:160]} for _, r in rows.iterrows()]


def games_summary(d, df):
    """Every game this season: both teams' 4th downs and a grade for each team."""
    ref = history_costs()
    meta = df.drop_duplicates("game_id").set_index("game_id")
    out = []
    for gid, g in d.groupby("game_id"):
        m = meta.loc[gid]
        teams = []
        for side in ("away", "home"):
            tm = m[side + "_team"]
            tg = g[g["posteam"] == tm].sort_values("play_id")
            cost = float(tg["cost_confident"].sum())
            teams.append({"team": tm, "coach": (tg["coach"].iloc[0] if len(tg) else None),
                          "score": None if m[side + "_score"] != m[side + "_score"] else int(m[side + "_score"]),
                          "calls": int(len(tg)), "mistakes": int(tg["confident_mistake"].sum()),
                          "wp_lost": round(cost, 3), "grade": game_grade(cost, ref),
                          "list": [call_row(r) for _, r in tg.iterrows()]})
        out.append({"id": gid, "week": int(m["week"]), "away": teams[0], "home": teams[1]})
    return sorted(out, key=lambda x: (-x["week"], x["id"]))


def situation(r):
    sd = int(r["score_diff"])
    score_txt = "tied" if sd == 0 else (f"up {sd}" if sd > 0 else f"down {-sd}")
    return (f"{fmt_clock(r['qtr'], r['half_seconds_remaining'])}, {score_txt}, "
            f"4th & {int(r['ydstogo'])} at {fmt_spot(r['yardline_100'])}")


def row(r, kind):
    out = {"week": int(r["week"]), "team": r["posteam"], "opp": r["defteam"], "coach": r["coach"],
           "situation": situation(r), "coach_call": r["choice"], "engine_call": r["best"],
           "wp": {k: (None if r["wp_" + k] != r["wp_" + k] else round(float(r["wp_" + k]), 3))
                  for k in ("go", "fg", "punt")},
           "what_happened": str(r["desc"])[:220]}
    if kind == "worst":
        out["cost"] = round(float(r["cost"]), 3)
        out["confidence"] = round(float(r["conf_wrong"]), 2)
    else:
        out["edge"] = round(float(r["margin"]), 3)
        # a defensive touchdown (pick-six, fumble return) is not a conversion
        lost = (r["interception"] == 1) or (r["fumble_lost"] == 1)
        out["converted"] = bool(not lost and ((r["first_down"] == 1) or (r["touchdown"] == 1)))
    return out


def main(download=False):
    season = CONFIG["current_season"]
    if download:
        path = os.path.join(ROOT, CONFIG["raw_dir"], f"play_by_play_{season}.parquet")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        urllib.request.urlretrieve(CONFIG["pbp_url"].format(season=season), path)
    d, df = score([season])
    weeks = []
    shares = coach_shares()
    for wk, g in sorted(d.groupby("week"), key=lambda x: -x[0]):
        worst = g[g["confident_mistake"]].sort_values("cost", ascending=False).head(TOP_WORST)
        # "gutsy" = kicking was a real option: the kick still left a 10%+ chance and
        # it is not the final two minutes of the game (when going is forced)
        kick = g[["wp_fg", "wp_punt"]].max(axis=1)
        forced = (g["qtr"] == 4) & (g["half_seconds_remaining"] <= 120)
        best = g[(g["choice"] == "go") & (g["best"] == "go") & (g["margin"] >= BEST_MARGIN)
                 & (g["conf_wrong"] <= 1 - CONFIG["confident_share"]) & (kick >= MIN_KICK_WP) & ~forced
                 ].sort_values("margin", ascending=False).head(TOP_BEST)
        weeks.append({"week": int(wk), "decisions": int(len(g)),
                      "confident_mistakes": int(g["confident_mistake"].sum()),
                      "wp_lost": round(float(g["cost_confident"].sum()), 3),
                      "worst": [row(r, "worst") for _, r in worst.iterrows()],
                      "best": [row(r, "best") for _, r in best.iterrows()],
                      "quiz": quiz(g, shares)})
    teams = (d.groupby("posteam").agg(games=("game_id", "nunique"), lost=("cost_confident", "sum"),
                                       mistakes=("confident_mistake", "sum"), calls=("id", "size"))
              .reset_index())
    teams["wins_lost_per_17"] = (17 * teams["lost"] / teams["games"]).round(3)
    out = {"version": CONFIG["version"], "season": season,
           "updated": datetime.date.today().isoformat(), "weeks": weeks,
           "games": games_summary(d, df),
           "game_letters": "A+ = no confident mistakes; otherwise ranked against every team-game since 2014 with one: "
                           "A beats 75% of them, B 50%, C 25%, D 10%, F the worst 10%.",
           "teams": teams.sort_values("wins_lost_per_17").drop(columns="lost").to_dict("records")}
    with open(os.path.join(ROOT, "data", "weekly.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=int)
    with open(os.path.join(ROOT, "app", "weekly.js"), "w") as fh:
        fh.write("// Generated by engine/weekly.py. Do not edit by hand.\n")
        fh.write("const WEEKLY = " + json.dumps(out, separators=(",", ":"), default=int) + ";\n")
        fh.write("if (typeof module !== 'undefined') module.exports = WEEKLY;\n")
    print(f"season {season}: {len(weeks)} weeks, {len(d)} decisions")


if __name__ == "__main__":
    main(download="--download" in sys.argv)
