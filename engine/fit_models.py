"""Fit every model from nflverse play-by-play and write the shipped model.

Run:  py engine/fit_models.py
Out:  data/model.json, app/model.js, data/validation.json

Two passes. The validation pass fits on CONFIG seasons minus holdout_seasons and
scores the holdout. The shipped pass refits on every season.
"""
import datetime
import json
import math
import os
import random
import sys

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG                      # noqa: E402
from load_data import ROOT, fill_outdoor_weather, load   # noqa: E402
import decide                                  # noqa: E402
import kickers                                 # noqa: E402

Q = CONFIG["quantiles"]
QPTS = [(i + 0.5) / Q for i in range(Q)]
RUSHPASS = ["run", "pass"]

WP_MONO = {"score_diff": 1, "yardline": -1, "pos_to": 1, "def_to": -1, "spread": 1,
           "spread_time": 1, "diff_time_ratio": 1}
WP_ALL = decide.WP_FEATURES + decide.WP_DERIVED
# 4th-down-by-distance terms (is4_1, is4_23, is4_logtogo) were tested in 1.1.0 and
# left out: on the same 1,849 hold-out 4th downs they moved log loss from 0.6424 to
# 0.6419, a difference too small to justify three more terms. The columns stay
# computed so the test can be repeated.
CONV_BASE = ["is4", "togo", "logtogo", "goal", "inside10", "rz"]
# Kicking era: a linear year trend, a 2020+ step (nfl4th's choice), or both.
# The validation pass picks the one with the best hold-out log loss.
FG_ERA_CANDIDATES = {"trend": ["year"], "era2020": ["era20"], "both": ["year", "era20"]}
FG_BASE = ["dist", "dist2", "year"]
KICKER_LETTERS = [(0.10, "A+"), (0.25, "A"), (0.40, "B+"), (0.60, "B"), (0.75, "C+"), (0.90, "C"), (1.01, "D")]
FG_WEATHER = ["wind", "wind_x_dist", "cold", "precip"]
FG_STADIUM = ["indoor", "altitude"]
COMBOS = {"base": [], "weather": FG_WEATHER, "stadium": FG_STADIUM,
          "weather+stadium": FG_WEATHER + FG_STADIUM}
PUNT_ENV = {"weather": ["wind", "cold", "precip"], "stadium": ["indoor", "altitude"],
            "weather+stadium": ["wind", "cold", "precip", "indoor", "altitude"]}


# ------------------------------------------------------------------ helpers
def r6(x):
    return float(f"{x:.6g}")


def snaps(df):
    s = df[df["down"].notna() & df["posteam"].notna() & (df["qtr"] <= 4)].copy()
    s = s.sort_values(["game_id", "play_id"])
    g = s.groupby("game_id")
    for c in ["posteam", "yardline_100", "game_seconds_remaining", "game_half"]:
        s["next_" + c] = g[c].shift(-1)
    s["elapsed"] = s["game_seconds_remaining"] - s["next_game_seconds_remaining"]
    s["same_half"] = s["game_half"] == s["next_game_half"]
    s["poss_change"] = s["posteam"] != s["next_posteam"]
    return s


def wp_frame(s):
    d = s.rename(columns={"game_seconds_remaining": "game_seconds",
                          "half_seconds_remaining": "half_seconds",
                          "yardline_100": "yardline",
                          "posteam_timeouts_remaining": "pos_to",
                          "defteam_timeouts_remaining": "def_to"})
    d = d[d["win"].notna() & d["spread"].notna() & d["score_diff"].notna()].copy()
    e4 = np.exp(-4.0 * (3600.0 - d["game_seconds"]) / 3600.0)
    d["spread_time"] = d["spread"] * e4
    d["diff_time_ratio"] = d["score_diff"] / e4
    return d


def fit_wp(d):
    mono = [WP_MONO.get(f, 0) for f in WP_ALL]
    m = HistGradientBoostingClassifier(monotonic_cst=mono, random_state=0,
                                       early_stopping=False, **CONFIG["wp_trees"])
    m.fit(d[WP_ALL].values.astype(float), d["win"].values)
    return m


def export_wp(m):
    trees = []
    for (pred,) in m._predictors:
        nodes = []
        for n in pred.nodes:
            nodes.append([int(n["feature_idx"]), r6(n["num_threshold"]), int(n["left"]),
                          int(n["right"]), r6(n["value"]), int(n["is_leaf"])])
        trees.append(nodes)
    return {"features": WP_ALL, "baseline": r6(float(np.ravel(m._baseline_prediction)[0])),
            "trees": trees}


def logit_fit(X, y, names):
    m = LogisticRegression(C=1e6, max_iter=5000)
    m.fit(X[names].values.astype(float), y)
    return m, {"names": names, "coef": [r6(c) for c in m.coef_[0]], "intercept": r6(m.intercept_[0])}


def calib_table(p, y, edges):
    rows = []
    bins = np.digitize(p, edges)
    for b in range(1, len(edges)):
        k = bins == b
        if k.sum() >= 30:
            rows.append({"bin": f"{edges[b-1]:.2f}-{edges[b]:.2f}", "n": int(k.sum()),
                         "predicted": round(float(p[k].mean()), 3), "actual": round(float(y[k].mean()), 3)})
    return rows


def metrics(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {"n": int(len(y)), "log_loss": round(float(log_loss(y, p)), 4),
            "brier": round(float(brier_score_loss(y, p)), 4)}


# ------------------------------------------------------------------ feature frames
def conv_frame(s):
    # A defensive penalty that gives a first down is a conversion (nfl4th does
    # the same). Other penalty plays are replayed downs and are left out.
    def_pen = ((s["penalty"] == 1) & (s["penalty_team"] == s["defteam"]) & (s["first_down_penalty"] == 1)
               & s["play_type"].isin(RUSHPASS + ["no_play"]))
    clean = s["play_type"].isin(RUSHPASS) & (s["penalty"] != 1)
    c = s[(s["down"].isin([3, 4])) & (clean | def_pen)
          & (s["qb_kneel"] != 1) & (s["qb_spike"] != 1) & (s["ydstogo"] >= 1)].copy()
    c["success"] = ((c["first_down"] == 1) | (c["touchdown"] == 1) | def_pen[c.index]).astype(int)
    c["yards_gained"] = c["yards_gained"].where(~def_pen[c.index], 0.0).fillna(0.0)
    c["is4"] = (c["down"] == 4).astype(int)
    c["togo"] = c["ydstogo"].clip(upper=20) / 10.0
    c["logtogo"] = np.log(c["ydstogo"])
    c["goal"] = (c["ydstogo"] >= c["yardline_100"]).astype(int)
    c["inside10"] = (c["yardline_100"] <= 10).astype(int)
    c["rz"] = (c["yardline_100"].between(11, 20) & (c["ydstogo"] < c["yardline_100"])).astype(int)
    c["is4_1"] = c["is4"] * (c["ydstogo"] == 1)
    c["is4_23"] = c["is4"] * c["ydstogo"].between(2, 3)
    c["is4_logtogo"] = c["is4"] * c["logtogo"]
    c["spread"] = c["spread"].fillna(0) / 10.0
    return c


def fg_frame(df):
    f = df[(df["play_type"] == "field_goal") & df["kick_distance"].notna() & (df["qtr"] <= 5)].copy()
    f["made"] = (f["field_goal_result"] == "made").astype(int)
    d = f["kick_distance"]
    f["dist"] = d / 10.0
    f["dist2"] = (d / 10.0) ** 2
    f["year"] = (f["season"] - 2014) / 10.0
    f["era20"] = (f["season"] >= 2020).astype(int)
    f["wind"] = f["wind_mph"] / 10.0
    f["wind_x_dist"] = f["wind"] * d / 10.0
    f["cold"] = (CONFIG["cold_threshold_f"] - f["temp_f"]).clip(lower=0) / 10.0
    f["altitude"] = f["altitude_kft"]
    return f


def punt_frame(s, all_outcomes=False):
    """Normal punts (opponent ball, no return TD). all_outcomes=True also keeps
    return TDs and muffs recovered by the kicking team, flagged."""
    p = s[(s["play_type"] == "punt") & (s["penalty"] != 1) & s["same_half"]].copy()
    n_all = len(p)
    p["is_td"] = (p["return_touchdown"] == 1).astype(int)
    p["is_muff"] = ((~p["poss_change"]) & (p["is_td"] == 0)).astype(int)
    if not all_outcomes:
        p = p[(p["is_td"] == 0) & (p["is_muff"] == 0)]
    p["opp_yl"] = p["next_yardline_100"]
    p["wind"] = p["wind_mph"] / 10.0
    p["cold"] = (CONFIG["cold_threshold_f"] - p["temp_f"]).clip(lower=0) / 10.0
    p["altitude"] = p["altitude_kft"]
    return p, n_all - len(p)


def bucket_index(togo):
    edges = CONFIG["togo_buckets"]
    return np.searchsorted(edges, togo, side="right") - 1


# ------------------------------------------------------------------ model build
def build(df, s, kicker_prior=None, ko_df=None, fg_era="trend", wp=True):
    """ko_df: plays used to measure the kickoff spot. The rule era is a known rule,
    not an outcome, so validation passes the full data here."""
    ko_df = df if ko_df is None else ko_df
    out = {}
    # WP
    if wp:
        d = wp_frame(s)
        out["_wp_model"] = fit_wp(d)
        out["wp"] = export_wp(out["_wp_model"])

    # conversion
    c = conv_frame(s)
    y = c["success"].values
    out["conv"] = {"base": logit_fit(c, y, CONV_BASE)[1],
                   "spread": logit_fit(c, y, CONV_BASE + ["spread"])[1]}

    # gains after a conversion / a failure, by distance bucket
    c["b"] = bucket_index(c["ydstogo"].values)
    succ_q, fail_m = [], []
    for b in range(len(CONFIG["togo_buckets"]) - 1):
        k = c["b"] == b
        succ_q.append([r6(v) for v in np.quantile(c.loc[k & (c["success"] == 1), "yards_gained"], QPTS)])
        fail_m.append(r6(c.loc[k & (c["success"] == 0), "yards_gained"].mean()))
    out["gain"] = {"edges": CONFIG["togo_buckets"], "success_q": succ_q, "fail_mean": fail_m}

    # field goals
    f = fg_frame(df)
    out["fg"] = {"models": {}, "era": fg_era}
    base_names = ["dist", "dist2"] + FG_ERA_CANDIDATES[fg_era]
    for key, extra in COMBOS.items():
        out["fg"]["models"][key] = logit_fit(f, f["made"].values, base_names + extra)[1]

    # kicker skill against the fullest model, so a kicker is not credited for altitude or a dome
    full = out["fg"]["models"]["weather+stadium"]
    f["_z"] = full["intercept"] + sum(cf * f[n].values for n, cf in zip(full["names"], full["coef"]))
    sa, sb = kicker_prior if kicker_prior is not None else (0.3, 0.1)
    eff = kickers.fit_effects(f, sa, sb)
    repl = kickers.replacement(f, CONFIG["replacement"])
    recent = f[f["season"].isin(CONFIG["kicker_list_seasons"])]
    cnt = recent.groupby("kicker_player_id").size()
    names = f.groupby("kicker_player_id")["kicker_player_name"].last()
    tot = f.groupby("kicker_player_id").size()
    team = f.sort_values(["season", "week"]).groupby("kicker_player_id")["posteam"].last()
    ks = [{"id": k, "name": names[k], "team": team[k], "a": r6(eff.get(k, (0, 0))[0]),
           "b": r6(eff.get(k, (0, 0))[1]), "attempts": int(tot[k])}
          for k in cnt[cnt >= CONFIG["kicker_list_min_attempts"]].index]
    out["fg"]["kickers"] = sorted(ks, key=lambda r: r["name"])
    # Teams: home stadium (roof, altitude) and current kicker, from the latest
    # fit season, so the app can fill these in from a team pick.
    last = max(CONFIG["seasons"])
    hg = df[(df["season"] == last) & (df["location"] == "Home")].drop_duplicates("game_id")
    kick_last = f[f["season"] == last].groupby(["posteam", "kicker_player_id"]).size().reset_index(name="n")
    teams = {}
    for tm, g in hg.groupby("home_team"):
        kk = kick_last[kick_last["posteam"] == tm].sort_values("n", ascending=False)
        teams[tm] = {"indoor": int(g["indoor"].mode().iloc[0]),
                     "altitude_kft": float(g["altitude_kft"].max()),
                     "kicker": kk["kicker_player_id"].iloc[0] if len(kk) else None}
    out["teams"] = teams
    out["fg"]["replacement"] = {k: (r6(v) if isinstance(v, float) else v) for k, v in repl.items()}
    out["fg"]["kicker_prior"] = [sa, sb]
    out["_kicker_effects"] = eff
    out["_fg_frame"] = f

    # punts
    p, _ = punt_frame(s)
    pa, _ = punt_frame(s, all_outcomes=True)
    g_td, g_muff = pa["is_td"].mean(), pa["is_muff"].mean()
    K = 200     # pseudo-counts: rare events are shrunk toward the league rate
    w = CONFIG["punt_bin_width"]
    bins = []
    lo = 1
    while lo <= 99:
        hi = lo + w - 1
        k = (p["yardline_100"] >= lo) & (p["yardline_100"] <= hi)
        if k.sum() >= 40:
            bins.append({"lo": lo, "hi": hi, "n": int(k.sum()),
                         "q": [r6(v) for v in np.quantile(p.loc[k, "opp_yl"], QPTS)]})
        lo += w
    # stretch the end bins to cover the whole field
    bins[0]["lo"], bins[-1]["hi"] = 1, 99
    for a, b in zip(bins, bins[1:]):
        a["hi"] = b["lo"] - 1
    for b in bins:
        k = (pa["yardline_100"] >= b["lo"]) & (pa["yardline_100"] <= b["hi"])
        n = int(k.sum())
        b["p_td"] = r6((pa.loc[k, "is_td"].sum() + K * g_td) / (n + K))
        b["p_muff"] = r6((pa.loc[k, "is_muff"].sum() + K * g_muff) / (n + K))
        mk = k & (pa["is_muff"] == 1)
        # a muff is recovered about where the returner would have started
        b["muff_spot"] = r6(pa.loc[mk, "next_yardline_100"].mean()) if mk.sum() >= 10             else r6(100.0 - float(np.mean(b["q"])))
    p["bin_mean"] = 0.0
    for b in bins:
        k = (p["yardline_100"] >= b["lo"]) & (p["yardline_100"] <= b["hi"])
        p.loc[k, "bin_mean"] = float(np.mean(b["q"]))
    resid = p["opp_yl"] - p["bin_mean"]
    adj = {}
    for key, names_ in PUNT_ENV.items():
        lr = LinearRegression().fit(p[names_].values.astype(float), resid.values)
        # coefficients only: the shift is zero in neutral conditions by construction
        adj[key] = {"names": names_, "coef": [r6(v) for v in lr.coef_]}
    g_fc = p["punt_fair_catch"].fillna(0).mean()
    for b in bins:
        k = (p["yardline_100"] >= b["lo"]) & (p["yardline_100"] <= b["hi"])
        b["p_fc"] = r6((p.loc[k, "punt_fair_catch"].fillna(0).sum() + K * g_fc) / (int(k.sum()) + K))
    out["punt"] = {"bins": bins, "adj": adj, "return_td_rate": r6(g_td), "muff_rate": r6(g_muff),
                   "n": int(len(pa))}

    # clock: game seconds from this snap to the next snap, by outcome
    def med(k):
        r = []
        for two in (False, True):
            kk = k & s["same_half"] & ((s["half_seconds_remaining"] <= 120) == two) & (s["penalty"] != 1)
            r.append(round(float(s.loc[kk, "elapsed"].median()), 1))
        return r
    rp = s["play_type"].isin(RUSHPASS)
    d4 = s["down"] == 4
    early = s["down"].isin([1, 2, 3]) & rp & (s["penalty"] != 1) & (s["qb_kneel"] != 1) & (s["qb_spike"] != 1)
    out["clock"] = {
        "go_success": med(d4 & rp & (s["first_down"] == 1) & (s["touchdown"] != 1) & ~s["poss_change"]),
        "go_fail": med(d4 & rp & (s["fourth_down_failed"] == 1) & s["poss_change"]),
        "punt": med((s["play_type"] == "punt") & s["poss_change"]),
        "fg": med((s["play_type"] == "field_goal") & s["poss_change"]),
        "score": med(rp & (s["touchdown"] == 1) & (s["return_touchdown"] != 1) & s["poss_change"]),
        # 1st-3rd down plays: a first down keeps the clock running; a short gain
        # often stops it (incompletions, out of bounds)
        "play_first": med(early & (s["first_down"] == 1) & (s["touchdown"] != 1) & ~s["poss_change"]),
        "play_short": med(early & (s["first_down"] != 1) & (s["touchdown"] != 1) & ~s["poss_change"]),
        # the clock stops on a fair catch, so snap-to-snap time = the punt play itself
        "punt_fair_catch": med((s["play_type"] == "punt") & (s["punt_fair_catch"] == 1) & s["poss_change"]),
    }
    # a play followed at once by the offense's own timeout: the play's real length
    a_ = df.sort_values(["game_id", "play_id"])
    g_ = a_.groupby("game_id")
    nt, ntt, ngs = g_["timeout"].shift(-1), g_["timeout_team"].shift(-1), g_["game_seconds_remaining"].shift(-1)
    k_ = (a_["play_type"].isin(RUSHPASS) & (nt == 1) & (ntt == a_["posteam"]) & (a_["penalty"] != 1)
          & (a_["half_seconds_remaining"] <= 120))
    secs_ = (a_["game_seconds_remaining"] - ngs)[k_]
    out["clock"]["timeout_play"] = round(float(secs_[secs_ >= 0].median()), 1)
    # a play followed by a spike: snap -> spike snap -> next snap, final 2:00 of a half
    sp = s["qb_spike"].fillna(0)
    nxt_spike = s.groupby("game_id")["qb_spike"].shift(-1).fillna(0) == 1
    nxt_el = s.groupby("game_id")["elapsed"].shift(-1)
    kk = rp & nxt_spike & (sp != 1) & ~s["poss_change"] & s["same_half"] & (s["half_seconds_remaining"] <= 120)
    tot = (s["elapsed"] + nxt_el)[kk]
    out["clock"]["spike_total"] = round(float(tot[tot >= 0].median()), 1)

    # 1st-3rd down plays: turnover rate by down, and yards gained by down x distance
    e = s[early].copy()
    e["to"] = ((e["interception"] == 1) | (e["fumble_lost"] == 1)).astype(int)
    e["b"] = bucket_index(e["ydstogo"].clip(lower=1).values)
    gq, pto = [], []
    for dn in (1, 2, 3):
        ed = e[e["down"] == dn]
        pto.append(r6(ed["to"].mean()))
        row = []
        for b in range(len(CONFIG["togo_buckets"]) - 1):
            kk = (ed["b"] == b) & (ed["to"] == 0)
            src = ed.loc[kk, "yards_gained"] if kk.sum() >= 200 else ed.loc[ed["to"] == 0, "yards_gained"]
            row.append([r6(v) for v in np.quantile(src.fillna(0), QPTS)])
        gq.append(row)
    out["play"] = {"gain_q": gq, "p_turnover": pto}

    # where the receiving team starts after a kickoff, under the current rules
    k = ko_df[(ko_df["play_type"] == "kickoff") & (ko_df["season"] == CONFIG["rules_season"])].sort_values(["game_id", "play_id"])
    ks = snaps(ko_df[ko_df["season"] == CONFIG["rules_season"]])
    nxt = ks[["game_id", "play_id", "posteam", "yardline_100"]]
    m = pd.merge_asof(k[["game_id", "play_id", "posteam"]].sort_values("play_id"),
                      nxt.sort_values("play_id"), on="play_id", by="game_id",
                      direction="forward", suffixes=("", "_next"))
    m = m[m["posteam"] == m["posteam_next"]]
    out["kickoff_start"] = round(float(m["yardline_100"].mean()), 1)
    # every season's spot, so past decisions are judged under their own rules
    ka = ko_df[ko_df["play_type"] == "kickoff"].sort_values(["game_id", "play_id"])
    sa = snaps(ko_df)[["game_id", "play_id", "posteam", "yardline_100"]]
    ma = pd.merge_asof(ka[["game_id", "play_id", "posteam", "season"]].sort_values("play_id"),
                       sa.sort_values("play_id"), on="play_id", by="game_id",
                       direction="forward", suffixes=("", "_next"))
    ma = ma[ma["posteam"] == ma["posteam_next"]]
    out["kickoff_by_season"] = {str(k): round(float(v), 1) for k, v in ma.groupby("season")["yardline_100"].mean().items()}
    assert out["kickoff_start"] == out["kickoff_start"], "kickoff spot is NaN: no rules_season data"

    # extra point and 2-point try rates
    tr = df[df["season"] >= CONFIG["try_seasons_from"]]
    pat, two = tr["extra_point_result"].dropna(), tr["two_point_conv_result"].dropna()
    out["tries"] = {"pat": r6((pat == "good").mean()), "two": r6((two == "success").mean()),
                    "n_pat": int(len(pat)), "n_two": int(len(two))}
    # overtime: the better team's edge, fit on decided OT games; ties count 0.5
    gm = df.drop_duplicates("game_id")
    otg = gm[gm["game_id"].isin(set(df.loc[df["qtr"] == 5, "game_id"])) & gm["spread_line"].notna()]
    dec = otg[otg["result"] != 0]
    lr = LogisticRegression(fit_intercept=False).fit((dec[["spread_line"]] / 10.0).values, (dec["result"] > 0).astype(int))
    out["ot"] = {"slope": r6(lr.coef_[0][0]), "p_tie": r6((otg["result"] == 0).mean()), "n_games": int(len(otg))}
    out["rules"] = {"season": CONFIG["rules_season"], "td_points": CONFIG["touchdown_points"],
                    "fg_distance_add": CONFIG["fg_distance_add"], "fg_snap_to_spot": CONFIG["fg_snap_to_spot"],
                    "missed_fg_min_spot": CONFIG["missed_fg_min_spot"],
                    "fg_max_distance": CONFIG["fg_max_distance"], "tossup_margin": CONFIG["tossup_margin"],
                    "fair_catch_kick_window": CONFIG["fair_catch_kick_window"],
                    "short_yardage": CONFIG["short_yardage"]}
    return out


def write_kicker_grades(mdl):
    f, eff = mdl["_fg_frame"], mdl["_kicker_effects"]
    full = mdl["fg"]["models"]["weather+stadium"]
    co = dict(zip(full["names"], full["coef"]))
    yr = (CONFIG["rules_season"] - 2014) / 10.0
    era = co.get("year", 0.0) * yr + co.get("era20", 0.0) * (1 if CONFIG["rules_season"] >= 2020 else 0)
    z_at = lambda d: full["intercept"] + co["dist"] * d / 10 + co["dist2"] * (d / 10) ** 2 + era
    rows = kickers.grade(f, eff, mdl["fg"]["replacement"], z_at)
    repl = mdl["fg"]["replacement"]
    alt = kickers.replacement_fringe(f, CONFIG["replacement_fringe"])
    out = {"version": CONFIG["version"], "rules_season": CONFIG["rules_season"],
           "replacement_sensitivity": dict(alt, make_pct_50yd=round(float(1 / (1 + np.exp(-(z_at(50) + alt["a"] + alt["b"])))), 3)),
           "replacement": dict(repl, make_pct_50yd=round(float(1 / (1 + np.exp(-(z_at(50) + repl["a"] + repl["b"])))), 3),
                               fifty_pct_distance=kickers.fifty_pct_distance(z_at, repl["a"], repl["b"])),
           "league_make_pct_50yd": round(float(1 / (1 + np.exp(-z_at(50)))), 3),
           "league_fifty_pct_distance": kickers.fifty_pct_distance(z_at, 0.0, 0.0),
           "kickers": sorted(rows, key=lambda r: -r["points_above_replacement"])}
    # Letter grades for kickers active in the latest season, by value over
    # replacement per 100 kicks (skill, not volume). Same cut-offs as coaches.
    cur = [r for r in out["kickers"] if r["last_season"] == max(CONFIG["seasons"])
           and r["attempts"] >= CONFIG["kicker_grade_min_attempts"]]
    ref = np.array([r["par_per_100"] for r in cur])
    for r in out["kickers"]:
        r["current"] = r in cur
        r["grade"] = None
    for r in cur:
        worse_share = float((ref > r["par_per_100"]).mean())   # share of kickers better than this one
        r["grade"] = next(L for cut, L in KICKER_LETTERS if worse_share < cut)
    out["grade_rule"] = (f"kickers active in {max(CONFIG['seasons'])} with at least "
                         f"{CONFIG['kicker_grade_min_attempts']} career attempts, ranked by points above "
                         "replacement per 100 kicks")
    with open(os.path.join(ROOT, "data", "kickers.json"), "w") as fh:
        json.dump(out, fh, indent=1)


# ------------------------------------------------------------------ validation
def predict_logit(m, X):
    z = m["intercept"] + sum(c * X[n].values for n, c in zip(m["names"], m["coef"]))
    return 1 / (1 + np.exp(-z))


def validate(df, s):
    hold = CONFIG["holdout_seasons"]
    tr_df, te_df = df[~df["season"].isin(hold)], df[df["season"].isin(hold)]
    tr_s, te_s = s[~s["season"].isin(hold)], s[s["season"].isin(hold)]
    v = {"train_seasons": sorted(set(tr_df["season"])), "test_seasons": hold}

    ft = fg_frame(te_df)
    # pick the kicking-era term on the holdout
    era_rows = {}
    for era in FG_ERA_CANDIDATES:
        b = build(tr_df, tr_s, kicker_prior=(0.0, 0.0), ko_df=df, fg_era=era, wp=False)
        era_rows[era] = metrics(predict_logit(b["fg"]["models"]["base"], ft), ft["made"].values)
    fg_era = min(era_rows, key=lambda k: era_rows[k]["log_loss"])
    v["fg_era"] = {"candidates": era_rows, "chosen": fg_era}

    # pick the kicker priors on the holdout
    base = build(tr_df, tr_s, kicker_prior=(0.0, 0.0), ko_df=df, fg_era=fg_era, wp=False)
    full = base["fg"]["models"]["weather+stadium"]
    ft["_z"] = full["intercept"] + sum(c * ft[n].values for n, c in zip(full["names"], full["coef"]))
    sig_rows = []
    for sa, sb in CONFIG["kicker_prior_grid"]:
        eff = kickers.fit_effects(base["_fg_frame"], sa, sb)
        sig_rows.append({"sa": sa, "sb": sb, **metrics(1 / (1 + np.exp(-kickers.apply(ft, eff))), ft["made"].values)})
    b_ = min(sig_rows, key=lambda r: r["log_loss"])
    best = (b_["sa"], b_["sb"])
    v["kicker_prior"] = {"grid": sig_rows, "chosen": list(best)}
    acc_only = min((r for r in sig_rows if r["sb"] == 0), key=lambda r: r["log_loss"])
    v["kicker_prior"]["best_accuracy_only"] = acc_only

    mdl = build(tr_df, tr_s, kicker_prior=best, ko_df=df, fg_era=fg_era)

    # WP
    d = wp_frame(te_s)
    p = mdl["_wp_model"].predict_proba(d[WP_ALL].values.astype(float))[:, 1]
    y = d["win"].values
    nf = d["vegas_wp"].notna().values
    # nflfastR's vegas_wp also uses the spread, so it is the fair comparison.
    # nflfastR was fit on these seasons too, so this flatters nflfastR.
    v["wp"] = {"engine": metrics(p, y),
               "nflfastR_vegas_wp_same_plays": metrics(d["vegas_wp"].values[nf], y[nf]),
               "nflfastR_wp_no_spread_same_plays": metrics(d["wp"].values[nf], y[nf]),
               "engine_same_plays": metrics(p[nf], y[nf]),
               "score_only_baseline": metrics(score_only(tr_s, d), y),
               "calibration": calib_table(p, y, np.linspace(0, 1, 11)),
               "games": int(d["game_id"].nunique())}
    late = (d["game_seconds"] <= 300).values
    v["wp"]["final_5_min"] = metrics(p[late], y[late])

    # conversion on 4th downs only
    c = conv_frame(te_s)
    c4 = c[c["is4"] == 1]
    pc = predict_logit(mdl["conv"]["base"], c4)
    pcs = predict_logit(mdl["conv"]["spread"], c4)
    v["conv"] = {"base": metrics(pc, c4["success"].values), "spread": metrics(pcs, c4["success"].values),
                 "by_togo": []}
    for lo, hi in [(1, 1), (2, 3), (4, 6), (7, 10), (11, 99)]:
        k = ((c4["ydstogo"] >= lo) & (c4["ydstogo"] <= hi)).values
        v["conv"]["by_togo"].append({"togo": f"{lo}" if lo == hi else f"{lo}-{hi}", "n": int(k.sum()),
                                     "predicted": round(float(pc[k].mean()), 3),
                                     "actual": round(float(c4["success"].values[k].mean()), 3)})

    # field goals
    v["fg"] = {}
    for key in COMBOS:
        pf = predict_logit(mdl["fg"]["models"][key], ft)
        v["fg"][key] = metrics(pf, ft["made"].values)
    pf = predict_logit(mdl["fg"]["models"]["base"], ft)
    v["fg"]["by_distance"] = []
    for lo, hi in [(18, 29), (30, 39), (40, 49), (50, 54), (55, 70)]:
        k = ((ft["kick_distance"] >= lo) & (ft["kick_distance"] <= hi)).values
        v["fg"]["by_distance"].append({"distance": f"{lo}-{hi}", "n": int(k.sum()),
                                       "predicted": round(float(pf[k].mean()), 3),
                                       "actual": round(float(ft["made"].values[k].mean()), 3)})

    # punts: mean absolute error of the mean predicted spot
    pt, _ = punt_frame(te_s)
    pred = []
    for _, r in pt.iterrows():
        st = {"yardline": r["yardline_100"]}
        pred.append(np.mean(decide.punt_spots(mdl, st, {})))
    pred = np.array(pred)
    v["punt"] = {"n": int(len(pt)), "mae_yards": round(float(np.abs(pred - pt["opp_yl"].values).mean()), 2),
                 "naive_mae_yards": round(float(np.abs(pt["opp_yl"].mean() - pt["opp_yl"].values).mean()), 2)}

    v["coach_agreement"] = coach_agreement(mdl, te_s)
    return v, best, fg_era


def score_only(tr_s, d):
    t = wp_frame(tr_s)
    X = lambda q: np.c_[q["score_diff"] / np.sqrt(q["game_seconds"] + 60), q["score_diff"]]
    m = LogisticRegression(max_iter=1000).fit(X(t), t["win"])
    return m.predict_proba(X(d))[:, 1]


def coach_agreement(mdl, te_s, n=3000):
    """Engine call vs what coaches did on held-out 4th downs (descriptive only)."""
    rows = te_s[(te_s["down"] == 4) & te_s["play_type"].isin(RUSHPASS + ["punt", "field_goal"])
                & (te_s["penalty"] != 1) & (te_s["qb_kneel"] != 1) & te_s["spread"].notna()]
    rows = rows.sample(min(n, len(rows)), random_state=0)
    act_map = {"run": "go", "pass": "go", "punt": "punt", "field_goal": "fg"}
    agree, tot, strong_go, strong_go_went = 0, 0, 0, 0
    by = {}
    chosen = {"go": [], "fg": [], "punt": []}
    for _, r in rows.iterrows():
        st = {"kickoff_start": mdl["kickoff_by_season"].get(str(int(r["season"])), mdl["kickoff_start"]),
              "score_diff": r["score_diff"], "qtr": r["qtr"], "half_seconds": r["half_seconds_remaining"],
              "yardline": r["yardline_100"], "ydstogo": r["ydstogo"],
              "pos_to": r["posteam_timeouts_remaining"], "def_to": r["defteam_timeouts_remaining"],
              "home": r["home"], "receive_2h": r["receive_2h"]}
        out = decide.decide(mdl, st)
        a = act_map[r["play_type"]]
        if not np.isnan(r["win"]) and out["wp"][a] is not None:
            chosen[a].append((out["wp"][a], r["win"]))
        tot += 1
        agree += out["best"] == a
        by.setdefault(out["best"], {}).setdefault(a, 0)
        by[out["best"]][a] += 1
        if out["best"] == "go" and out["margin"] >= 0.02:
            strong_go += 1
            strong_go_went += a == "go"
    # Option-value calibration: for the option the coach chose, the engine's WP
    # for that option against how often the team went on to win.
    calib = {a: {"n": len(v), "predicted": round(float(np.mean([p for p, _ in v])), 3),
                 "actual": round(float(np.mean([w for _, w in v])), 3)} for a, v in chosen.items() if v}
    return {"n": tot, "agreement": round(agree / tot, 3), "matrix_engine_by_coach": by,
            "option_calibration": calib,
            "strong_go_n": strong_go,
            "strong_go_coach_went": round(strong_go_went / strong_go, 3) if strong_go else None}


# ------------------------------------------------------------------ main
def main():
    t0 = datetime.datetime.now()
    df = load()
    df, n_imp = fill_outdoor_weather(df)
    s = snaps(df)
    print(f"loaded {len(df):,} plays, {len(s):,} snaps; imputed outdoor weather on {n_imp:,} plays")

    v, prior, fg_era = validate(df, s)
    v["imputed_weather_plays"] = n_imp
    print(json.dumps({k: v[k] for k in ("wp", "conv", "fg", "punt", "coach_agreement")}, indent=1, default=str)[:4000])

    mdl = build(df, s, kicker_prior=prior, fg_era=fg_era)
    write_kicker_grades(mdl)
    for k in [k for k in mdl if k.startswith("_")]:
        mdl.pop(k)
    mdl["version"] = CONFIG["version"]
    mdl["built"] = datetime.date.today().isoformat()
    mdl["seasons"] = CONFIG["seasons"]
    mdl["source"] = "nflverse play-by-play (github.com/nflverse/nflverse-data, release 'pbp')"
    mdl["sample"] = {"plays": int(len(df)), "snaps": int(len(s)),
                     "field_goals": int((df["play_type"] == "field_goal").sum()),
                     "punts": int((df["play_type"] == "punt").sum())}

    with open(os.path.join(ROOT, "data", "model.json"), "w") as fh:
        json.dump(mdl, fh, separators=(",", ":"))
    with open(os.path.join(ROOT, "app", "model.js"), "w") as fh:
        fh.write("// Generated by engine/fit_models.py. Do not edit by hand.\n")
        fh.write("const MODEL = " + json.dumps(mdl, separators=(",", ":")) + ";\n")
        fh.write("if (typeof module !== 'undefined') module.exports = MODEL;\n")
    v["version"] = CONFIG["version"]
    v["built"] = mdl["built"]
    with open(os.path.join(ROOT, "data", "validation.json"), "w") as fh:
        json.dump(v, fh, indent=1, default=str)
    print("done in", datetime.datetime.now() - t0)


if __name__ == "__main__":
    main()
