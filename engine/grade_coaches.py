"""Grade head coaches' 4th-down calls against the engine.

Every 4th down is played twice on paper. Once as the coach called it, and once
as the engine would call it. Both are scored with the same win-probability (WP)
model. For each call:

    cost      = WP(engine's best option) - WP(coach's option)     >= 0
    realized  = WP after the play actually happened (next snap, or final result)
    luck      = realized - WP(coach's option)

cost measures the decision. luck measures what the dice did after it. Summed
over a career, cost is the expected wins the calls gave away.

Run:  py engine/grade_coaches.py      (after engine/fit_models.py)
Out:  data/coach_grades.json, app/grades.js
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG                              # noqa: E402
from load_data import ROOT, fill_outdoor_weather, load  # noqa: E402
from fit_models import snaps                           # noqa: E402

CHOICE = {"run": "go", "pass": "go", "punt": "punt", "field_goal": "fg"}
NEXT_COLS = ["score_diff", "game_seconds_remaining", "half_seconds_remaining", "second_half",
             "yardline_100", "down", "ydstogo", "posteam_timeouts_remaining",
             "defteam_timeouts_remaining", "tmw_pending", "receive_2h", "spread", "home"]
WP_NAMES = ["score_diff", "game_seconds", "half_seconds", "second_half", "yardline", "down",
            "ydstogo", "pos_to", "def_to", "tmw_pending", "receive_2h", "spread", "home"]
LETTERS = [(0.10, "A+"), (0.25, "A"), (0.40, "B+"), (0.60, "B"), (0.75, "C+"), (0.90, "C"), (1.01, "D")]


def team_kickers(df, kick):
    """(game_id, posteam) -> kicker id; falls back to the team's main kicker that season."""
    k = df[df["play_type"].isin(["field_goal", "extra_point"]) & df["kicker_player_id"].notna()]
    by_game = k.groupby(["game_id", "posteam"])["kicker_player_id"].agg(lambda s: s.mode().iloc[0])
    by_season = k.groupby(["season", "posteam"])["kicker_player_id"].agg(lambda s: s.mode().iloc[0])
    return by_game, by_season


def fmt_clock(qtr, hs):
    q_secs = hs - (900 if qtr in (1, 3) else 0)
    q_secs = max(0, int(q_secs))
    return f"Q{int(qtr)} {q_secs // 60}:{q_secs % 60:02d}"


def fmt_spot(yl):
    yl = int(yl)
    return "50" if yl == 50 else (f"opp {yl}" if yl < 50 else f"own {100 - yl}")


def prepare(seasons=None):
    df = load(seasons or CONFIG["grade_seasons"])
    df, _ = fill_outdoor_weather(df)
    s = snaps(df)
    g = s.groupby("game_id")
    for c in NEXT_COLS:
        s["nx_" + c] = g[c].shift(-1)

    kick = json.load(open(os.path.join(ROOT, "data", "kickers.json")))
    ab = {r["id"]: (r["accuracy"], r["range"]) for r in kick["kickers"]}
    shipped = json.load(open(os.path.join(ROOT, "data", "model.json")))
    by_game, by_season = team_kickers(df, kick)

    d = s[(s["down"] == 4) & s["play_type"].isin(CHOICE) & (s["penalty"] != 1)
          & (s["qb_kneel"] != 1) & (s["qb_spike"] != 1) & s["spread"].notna()].copy()
    d["coach"] = np.where(d["posteam"] == d["home_team"], d["home_coach"], d["away_coach"]) \
        if "home_coach" in d else None
    d.attrs["kickoff"] = (shipped["kickoff_by_season"], shipped["kickoff_start"])
    return df, d, ab, by_game, by_season


def score(seasons=None):
    """Play every 4th down in `seasons` twice; return (decisions frame, plays)."""
    df, d, ab, by_game, by_season = prepare(seasons)
    games = df.drop_duplicates("game_id")
    final = {}
    for _, r in games.iterrows():
        final[(r["game_id"], r["home_team"])] = 1.0 if r["result"] > 0 else (0.0 if r["result"] < 0 else 0.5)
        final[(r["game_id"], r["away_team"])] = 1.0 if r["result"] < 0 else (0.0 if r["result"] > 0 else 0.5)

    rows = []
    for _, r in d.iterrows():
        kid = by_game.get((r["game_id"], r["posteam"])) or by_season.get((r["season"], r["posteam"]))
        ka, kb = ab.get(kid, (0.0, 0.0))
        ko_map, ko_now = d.attrs["kickoff"]
        st = {"kickoff_start": ko_map.get(str(int(r["season"])), ko_now),
              "score_diff": float(r["score_diff"]), "qtr": int(r["qtr"]),
              "half_seconds": float(r["half_seconds_remaining"]), "yardline": float(r["yardline_100"]),
              "ydstogo": float(r["ydstogo"]), "pos_to": float(r["posteam_timeouts_remaining"]),
              "def_to": float(r["defteam_timeouts_remaining"]), "home": int(r["home"]),
              "receive_2h": int(r["receive_2h"]), "spread": float(r["spread"]),
              "wind": float(r["wind_mph"]), "temp": float(r["temp_f"]), "precip": int(r["precip"]),
              "indoor": int(r["indoor"]), "altitude_kft": float(r["altitude_kft"]),
              "kicker_a": ka, "kicker_b": kb,
              # Lopez (2020): on a recorded 4th & 1, teams that went were closer to
              # the line than teams that kicked. Judge each call at its group's distance.
              "short": "went" if CHOICE[r["play_type"]] == "go" else "kicked"}
        # The next regulation snap, or the final result when there is none
        # (game over, or the game went to overtime).
        nxt = None
        if all(pd.notna(r["nx_" + c]) for c in NEXT_COLS):
            nxt = {n: float(r["nx_" + c]) for n, c in zip(WP_NAMES, NEXT_COLS)}
        rows.append({"id": f"{r['game_id']}|{int(r['play_id'])}", "state": st, "next": nxt,
                     "choice": CHOICE[r["play_type"]],
                     "next_same_team": bool(r["next_posteam"] == r["posteam"]),
                     "final": final[(r["game_id"], r["posteam"])]})
    # One node process per core, each on its own chunk of decisions.
    n = max(1, (os.cpu_count() or 2) - 2)
    tmp = os.path.join(ROOT, "data", "grading_tmp")
    os.makedirs(tmp, exist_ok=True)
    procs, outs = [], []
    for i in range(n):
        inp, outp = os.path.join(tmp, f"in_{i}.json"), os.path.join(tmp, f"out_{i}.json")
        with open(inp, "w") as fh:
            json.dump({"toggles": CONFIG["grade_toggles"], "decisions": rows[i::n]}, fh)
        procs.append(subprocess.Popen(["node", os.path.join(ROOT, "build", "grade.js"), inp, outp]))
        outs.append(outp)
    print(f"prepared {len(rows):,} decisions; scoring in {n} node processes ...", flush=True)
    for pr in procs:
        if pr.wait() != 0:
            raise SystemExit("a grading process failed")
    scored = pd.DataFrame([r for o in outs for r in json.load(open(o))])
    shutil.rmtree(tmp, ignore_errors=True)

    d["id"] = d["game_id"] + "|" + d["play_id"].astype(int).astype(str)
    d = d.merge(scored, on="id")
    d["choice"] = d["play_type"].map(CHOICE)
    d["wp_choice"] = np.select([d["choice"] == "go", d["choice"] == "fg"], [d["wp_go"], d["wp_fg"]], d["wp_punt"])
    d["wp_best"] = d[["wp_go", "wp_fg", "wp_punt"]].max(axis=1)
    d["cost"] = (d["wp_best"] - d["wp_choice"]).clip(lower=0)
    d["luck"] = d["realized"] - d["wp_choice"]
    d["agree"] = d["choice"] == d["best"]
    # Brill, Yurko & Wyner (2025): only charge a coach when the bootstrap is sure.
    d["confident_mistake"] = (~d["agree"]) & (d["conf_wrong"] >= CONFIG["confident_share"])
    d["cost_confident"] = d["cost"].where(d["confident_mistake"], 0.0)
    d["coach"] = d["coach"].replace(CONFIG["coach_aliases"])
    return d, df


def main():
    d, df = score()
    write(d, df)


def boot_ci(cost, games, n, rng):
    if len(cost) == 0:
        return [0.0, 0.0]
    draws = rng.choice(cost, size=(n, len(cost)), replace=True).sum(axis=1) / games
    return [round(float(np.percentile(draws, 5)), 4), round(float(np.percentile(draws, 95)), 4)]


def coach_table(d, games_by_coach, rng):
    out = {}
    for coach, g in d.groupby("coach"):
        ng = games_by_coach.get(coach, 0)
        clear = g[~g["tossup"]]
        eng_go = clear[clear["best"] == "go"]
        dis = g[~g["agree"]]
        seasons = []
        for season, gs in g.groupby("season"):
            n_games = gs["game_id"].nunique()
            seasons.append({"season": int(season), "team": gs["posteam"].mode().iloc[0], "decisions": len(gs),
                            "wp_lost_per_game": round(float(gs["cost_confident"].sum() / max(n_games, 1)), 4),
                            "confident_mistakes": int(gs["confident_mistake"].sum()),
                            "go_rate": round(float((gs["choice"] == "go").mean()), 3),
                            "agree": round(float(gs["agree"].mean()), 3)})
        worst = g.sort_values(["cost_confident", "cost"], ascending=False).head(5)
        cm = g[g["confident_mistake"]]
        out[coach] = {
            "coach": coach, "teams": sorted(set(g["posteam"])),
            "first_season": int(g["season"].min()), "last_season": int(g["season"].max()),
            "games": int(ng), "decisions": int(len(g)), "clear_calls": int(len(clear)),
            "agree": round(float(g["agree"].mean()), 3),
            "agree_clear": round(float(clear["agree"].mean()), 3) if len(clear) else None,
            "go_rate": round(float((g["choice"] == "go").mean()), 3),
            # clear calls only: a toss-up or a dead tie (garbage time) is not "the engine says go"
            "engine_go_rate": round(float(((g["best"] == "go") & ~g["tossup"]).mean()), 3),
            "went_when_engine_said_go": round(float((eng_go["choice"] == "go").mean()), 3) if len(eng_go) else None,
            # graded figure: WP lost on confident mistakes only
            "confident_mistakes": int(len(cm)),
            "confident_mistake_kinds": {f"{a}->{b}": int(n) for (a, b), n in
                                        cm.groupby(["choice", "best"]).size().items()},
            "wp_lost_total": round(float(g["cost_confident"].sum()), 3),
            "wp_lost_per_game": round(float(g["cost_confident"].sum() / max(ng, 1)), 4),
            "wp_lost_per_game_ci90": boot_ci(g["cost_confident"].values, max(ng, 1), CONFIG["bootstrap_draws"], rng),
            "wins_lost_per_17": round(float(17 * g["cost_confident"].sum() / max(ng, 1)), 3),
            # every disagreement, sure or not (for comparison only)
            "wins_lost_per_17_all_calls": round(float(17 * g["cost"].sum() / max(ng, 1)), 3),
            "luck_total": round(float(g["luck"].sum()), 3),
            "replay": {   # the disagreements, played twice
                "n": int(len(dis)),
                "coach_expected": round(float(dis["wp_choice"].mean()), 4) if len(dis) else None,
                "engine_expected": round(float(dis["wp_best"].mean()), 4) if len(dis) else None,
                "coach_realized": round(float(dis["realized"].mean()), 4) if len(dis) else None,
            },
            "by_choice": {k: {"coach": int((g["choice"] == k).sum()), "engine": int((g["best"] == k).sum())}
                          for k in ("go", "fg", "punt")},
            "seasons": seasons,
            "worst_calls": [{
                "season": int(r["season"]), "week": int(r["week"]), "team": r["posteam"], "opp": r["defteam"],
                "situation": f"{fmt_clock(r['qtr'], r['half_seconds_remaining'])}, "
                             f"{'up' if r['score_diff'] > 0 else 'down' if r['score_diff'] < 0 else 'tied'}"
                             f"{'' if r['score_diff'] == 0 else ' ' + str(abs(int(r['score_diff'])))}, "
                             f"4th & {int(r['ydstogo'])} at {fmt_spot(r['yardline_100'])}",
                "coach_call": r["choice"], "engine_call": r["best"],
                "wp": {k: (None if pd.isna(r["wp_" + k]) else round(float(r["wp_" + k]), 3)) for k in ("go", "fg", "punt")},
                "cost": round(float(r["cost"]), 3), "realized": round(float(r["realized"]), 3),
                "confidence": round(float(r["conf_wrong"]), 2),
                "what_happened": str(r["desc"])[:220]} for _, r in worst.iterrows()],
        }
    return out


def write(d, df):
    # every graded decision, compact, for checks such as engine/edge_check.py
    keep = ["season", "week", "game_id", "play_id", "posteam", "coach", "qtr", "half_seconds_remaining",
            "score_diff", "ydstogo", "yardline_100", "choice", "best", "margin", "wp_go", "wp_fg", "wp_punt",
            "conf_wrong", "realized", "win"]
    d[keep].to_csv(os.path.join(ROOT, "data", "decisions.csv.gz"), index=False, float_format="%.4f")
    rng = np.random.default_rng(0)
    gm = pd.concat([df[["game_id", "home_coach"]].rename(columns={"home_coach": "coach"}),
                    df[["game_id", "away_coach"]].rename(columns={"away_coach": "coach"})]).drop_duplicates()
    gm["coach"] = gm["coach"].replace(CONFIG["coach_aliases"])
    games_by_coach = gm.groupby("coach").size().to_dict()
    table = coach_table(d, games_by_coach, rng)

    # league reference: every head coach with a full season of games in the data
    eligible = [v for v in table.values() if v["games"] >= CONFIG["grade_min_games"]]
    ref = np.array(sorted(v["wp_lost_per_game"] for v in eligible))
    for v in table.values():
        if v["games"] >= CONFIG["grade_min_games"]:
            pct = float((ref < v["wp_lost_per_game"]).mean())     # share of coaches who did better
            v["percentile_better_than"] = round(1 - pct, 3)
            v["grade"] = next(L for cut, L in LETTERS if pct < cut)
        else:
            v["percentile_better_than"], v["grade"] = None, "Incomplete"

    cur = d[d["season"] == CONFIG["current_season"]]
    cur_coaches = sorted(set(cur["coach"]))
    current = sorted((table[c] for c in cur_coaches if c in table), key=lambda v: v["wp_lost_per_game"])

    league = d.groupby("season").apply(lambda g: pd.Series({
        "decisions": len(g), "go_rate": round(float((g["choice"] == "go").mean()), 3),
        "engine_go_rate": round(float(((g["best"] == "go") & ~g["tossup"]).mean()), 3),
        "engine_tossup_share": round(float(g["tossup"].mean()), 3),
        "agree": round(float(g["agree"].mean()), 3),
        "wins_lost_per_team_season_confident": round(float(17 * g["cost_confident"].sum() / (2 * g["game_id"].nunique())), 3),
        "wins_lost_per_team_season_all": round(float(17 * g["cost"].sum() / (2 * g["game_id"].nunique())), 3),
        "confident_share_of_calls": round(float((g["conf_wrong"].ge(CONFIG["confident_share"]) | g["conf_wrong"].le(1 - CONFIG["confident_share"])).mean()), 3)}),
        include_groups=False).reset_index().to_dict("records")

    out = {"version": CONFIG["version"], "seasons": CONFIG["grade_seasons"],
           "model_fit_seasons": CONFIG["seasons"], "toggles": CONFIG["grade_toggles"],
           "decisions": int(len(d)), "coaches_in_reference": int(len(eligible)),
           "league_by_season": league, "current": current,
           "letters": [{"worse_than_share_below": c, "grade": L} for c, L in LETTERS]}
    with open(os.path.join(ROOT, "data", "coach_grades.json"), "w") as fh:
        json.dump(out, fh, indent=1, default=float)
    kick = json.load(open(os.path.join(ROOT, "data", "kickers.json")))
    with open(os.path.join(ROOT, "app", "grades.js"), "w") as fh:
        fh.write("// Generated by engine/grade_coaches.py. Do not edit by hand.\n")
        fh.write("const GRADES = " + json.dumps(out, default=float, separators=(",", ":")) + ";\n")
        fh.write("const KICKERS = " + json.dumps(kick, separators=(",", ":")) + ";\n")
        fh.write("if (typeof module !== 'undefined') module.exports = { GRADES, KICKERS };\n")
    print(f"graded {len(d):,} decisions; {len(current)} current coaches")
    for v in current:
        print(f"{v['coach']:22s} {v['grade']:10s} games={v['games']:3d} lost/g={v['wp_lost_per_game']:.4f} "
              f"wins/17={v['wins_lost_per_17']:.2f} (all {v['wins_lost_per_17_all_calls']:.2f}) conf_mist={v['confident_mistakes']} agree={v['agree']:.2f} go={v['go_rate']:.2f} "
              f"eng_go={v['engine_go_rate']:.2f} luck={v['luck_total']:+.2f}")


if __name__ == "__main__":
    main()
