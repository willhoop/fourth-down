"""Compare this engine with nfl4th (Ben Baldwin, nflverse) on the same plays.

nfl4th is the only public 4th-down model that publishes its numbers for every
play: go_wp, fg_wp, punt_wp and go_boost, per (game_id, play_id), 2014 onward
(MIT licence). This script joins them to our graded decisions
(data/decisions.csv.gz) and measures:

1. Agreement: how often the two engines recommend the same option, overall,
   on clear calls, and as a 3x3 table.
2. Aggressiveness: our go advantage vs theirs (both in win-probability points).
3. Accuracy of the win probabilities: for the option the coach actually chose,
   each engine predicts the chance of winning; we score both against the real
   result (Brier score and log loss). Only held-out seasons count for this, so
   our model is not scored on games it was trained on.

It cannot say which engine's *recommendation* is right: the outcome of the
option a coach did not pick is never seen.

Run:  py engine/compare_nfl4th.py [--download]
In:   data/raw/nfl4th/pre_computed_go_boost.rds (gitignored; --download fetches it)
Out:  data/nfl4th_comparison.json, docs/reports/nfl4th-comparison.md
"""
import gzip
import json
import os
import struct
import sys
import urllib.request

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG                                  # noqa: E402
from load_data import ROOT                                 # noqa: E402

NFL4TH_URL = "https://github.com/nflverse/nfl4th/releases/download/nfl4th_infrastructure/pre_computed_go_boost.rds"
RDS_PATH = os.path.join(ROOT, "data", "raw", "nfl4th", "pre_computed_go_boost.rds")
TOSSUP = 0.01            # both engines call a gap under 1 WP point a toss-up
HELD_OUT_FROM = 2024     # first season our WP model never saw in training (see validation report)
OPTIONS = ["go", "fg", "punt"]


# ---------- a minimal reader for R's .rds (XDR) format: enough for a data.frame
# of numeric and character columns, so the comparison needs no R install
class _Rds:
    def __init__(self, b):
        self.b, self.p, self.refs = b, 0, []

    def i(self):
        v = struct.unpack(">i", self.b[self.p:self.p + 4])[0]
        self.p += 4
        return v

    def obj(self):
        f = self.i()
        t, has_attr, has_tag = f & 0xFF, (f >> 9) & 1, (f >> 10) & 1
        if t in (254, 242):                      # NULL, empty env
            return None
        if t == 255:                             # reference
            return self.refs[(f >> 8) - 1]
        if t == 1:                               # symbol
            o = self.obj()
            self.refs.append(o)
            return o
        if t == 22:                              # external pointer (data.table)
            self.refs.append(None)
            self.obj(), self.obj()
            if has_attr:
                self.obj()
            return None
        if t == 9:                               # string
            n = self.i()
            if n == -1:
                return None
            v = self.b[self.p:self.p + n].decode("utf8", "replace")
            self.p += n
            return v
        if t == 2:                               # pairlist
            if has_attr:
                self.obj()
            tag = self.obj() if has_tag else None
            car, cdr = self.obj(), self.obj()
            return [(tag, car)] + (cdr or [])
        n = self.i()
        if t in (10, 13):                        # logical, integer
            v = list(struct.unpack(f">{n}i", self.b[self.p:self.p + 4 * n]))
            self.p += 4 * n
        elif t == 14:                            # double
            v = list(struct.unpack(f">{n}d", self.b[self.p:self.p + 8 * n]))
            self.p += 8 * n
        elif t in (16, 19):                      # character, list
            v = [self.obj() for _ in range(n)]
        else:
            raise ValueError(f"unsupported R type {t}")
        attr = self.obj() if has_attr else None
        return (t, v, attr)


def read_rds_frame(path):
    b = gzip.open(path).read()
    assert b[:2] == b"X\n", "not an XDR .rds file"
    r = _Rds(b)
    r.p = 2
    version = r.i()
    r.i(), r.i()
    if version == 3:
        n = r.i()
        r.p += n                                 # skip the native encoding name
    _, cols, attr = r.obj()
    names = dict(attr)["names"][1]
    out = {}
    for name, (t, v, _) in zip(names, cols):
        if t == 14:
            v = [np.nan if x != x else x for x in v]          # R NA is a NaN
        out[name] = v
    return pd.DataFrame(out)


def best_option(wp):
    """The option with the highest win probability; NaN options are unavailable."""
    return wp[OPTIONS].astype(float).idxmax(axis=1, skipna=True)


def margin(wp):
    """Gap between the best and second-best available option (WP points, 0-1).
    NaN when only one option is available (no decision to make)."""
    v = np.sort(np.nan_to_num(wp[OPTIONS].astype(float).values, nan=-np.inf), axis=1)
    gap = v[:, -1] - v[:, -2]
    return np.where(np.isfinite(gap), gap, np.nan)


def go_advantage(wp):
    kick = wp[["fg", "punt"]].astype(float).max(axis=1, skipna=True)
    return wp["go"].astype(float) - kick


def scores(p, y):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, float)
    return {"brier": round(float(np.mean((p - y) ** 2)), 4),
            "log_loss": round(float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))), 4)}


def brier_diff_ci(game, p_us, p_them, y, reps=1000, seed=0):
    """Ours minus nfl4th Brier score, with a 95% interval from resampling whole games
    (plays within a game are correlated)."""
    d = pd.DataFrame({"g": game, "e": (p_us - y) ** 2 - (p_them - y) ** 2})
    per = d.groupby("g")["e"].agg(["sum", "count"])
    s, c = per["sum"].to_numpy(), per["count"].to_numpy()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(s), size=(reps, len(s)))
    boot = s[idx].sum(1) / c[idx].sum(1)
    return {"diff": round(float(s.sum() / c.sum()), 4),
            "ci95": [round(float(np.percentile(boot, 2.5)), 4), round(float(np.percentile(boot, 97.5)), 4)],
            "games": int(len(s))}


def clock(r):
    left = int(r.half_seconds_remaining) - (900 if int(r.qtr) in (1, 3) else 0)
    return f"Q{int(r.qtr)} {left // 60}:{left % 60:02d}"


def compare(ours, theirs):
    m = ours.merge(theirs, on=["game_id", "play_id"], how="inner")
    us = m[["wp_go", "wp_fg", "wp_punt"]].set_axis(OPTIONS, axis=1)
    them = m[["go_wp", "fg_wp", "punt_wp"]].set_axis(OPTIONS, axis=1)
    them.loc[them["fg"].eq(0), "fg"] = np.nan           # nfl4th writes 0 when a kick is out of range
    m = m.assign(us_best=best_option(us), them_best=best_option(them),
                 us_margin=margin(us), them_margin=margin(them),
                 us_go_adv=go_advantage(us), them_go_adv=go_advantage(them))
    sure = np.where(m["choice"] == m["best"], 1 - m["conf_wrong"], m["conf_wrong"])
    m = m.assign(us_sure=sure)
    agree = m["us_best"] == m["them_best"]
    clear = (m["us_margin"] >= TOSSUP) & (m["them_margin"] >= TOSSUP)
    confident = clear & (m["us_sure"] >= CONFIG["confident_share"])
    table = pd.crosstab(m["us_best"], m["them_best"]).reindex(index=OPTIONS, columns=OPTIONS, fill_value=0)
    dis = m[~agree & clear]
    by_togo = (m.assign(b=pd.cut(m["ydstogo"], [0, 1, 3, 6, 10, 99], labels=["1", "2-3", "4-6", "7-10", "11+"]))
               .groupby("b", observed=True).apply(lambda g: pd.Series({
                   "plays": int(len(g)),
                   "agree": round(float((g["us_best"] == g["them_best"]).mean()), 3),
                   "we_go_they_kick": int(((g["us_best"] == "go") & (g["them_best"] != "go")).sum()),
                   "they_go_we_kick": int(((g["them_best"] == "go") & (g["us_best"] != "go")).sum())}), include_groups=False))
    # accuracy of each engine's WP for the option the coach actually took (held-out seasons only)
    h = m[(m["season"] >= HELD_OUT_FROM) & m["win"].notna()]
    pick = lambda w: w.loc[h.index].to_numpy()[np.arange(len(h)), h["choice"].map({k: i for i, k in enumerate(OPTIONS)}).to_numpy()]
    p_us, p_them = pick(us), pick(them)
    ok = ~np.isnan(p_us) & ~np.isnan(p_them) & (h["win"] != 0.5).to_numpy()
    return {
        "version": CONFIG["version"],
        "plays": {"ours": int(len(ours)), "nfl4th": int(len(theirs)), "matched": int(len(m)),
                  "seasons": f"{int(m['season'].min())}-{int(m['season'].max())}"},
        "agreement": {
            "all": round(float(agree.mean()), 3),
            "clear_calls": round(float(agree[clear].mean()), 3), "clear_n": int(clear.sum()),
            "confident_calls": round(float(agree[confident].mean()), 3), "confident_n": int(confident.sum()),
        },
        "table": {r: {c: int(table.loc[r, c]) for c in OPTIONS} for r in OPTIONS},
        "disagreements_clear": {"n": int(len(dis)),
                                "we_go_they_kick": int(((dis["us_best"] == "go") & (dis["them_best"] != "go")).sum()),
                                "they_go_we_kick": int(((dis["them_best"] == "go") & (dis["us_best"] != "go")).sum()),
                                "fg_vs_punt": int((dis["us_best"].isin(["fg", "punt"]) & dis["them_best"].isin(["fg", "punt"])).sum())},
        "go_advantage": {
            "correlation": round(float(m[["us_go_adv", "them_go_adv"]].corr().iloc[0, 1]), 3),
            "mean_ours_minus_theirs_pts": round(float((m["us_go_adv"] - m["them_go_adv"]).mean() * 100), 2),
            "median_ours_minus_theirs_pts": round(float((m["us_go_adv"] - m["them_go_adv"]).median() * 100), 2),
            "share_go_ours": round(float((m["us_best"] == "go").mean()), 3),
            "share_go_nfl4th": round(float((m["them_best"] == "go").mean()), 3),
        },
        "by_yards_to_go": {str(k): v for k, v in by_togo.to_dict("index").items()},
        "coaches": {"agree_with_us": round(float((m["choice"] == m["us_best"]).mean()), 3),
                    "agree_with_nfl4th": round(float((m["choice"] == m["them_best"]).mean()), 3)},
        "wp_accuracy_held_out": {"seasons": f"{HELD_OUT_FROM}-{int(m['season'].max())}", "n": int(ok.sum()),
                                 "ours": scores(p_us[ok], h["win"].to_numpy()[ok]),
                                 "nfl4th": scores(p_them[ok], h["win"].to_numpy()[ok]),
                                 "brier_ours_minus_nfl4th": brier_diff_ci(h["game_id"].to_numpy()[ok], p_us[ok], p_them[ok],
                                                                          h["win"].to_numpy()[ok].astype(float))},
        "biggest_disagreements": [
            {"game_id": r.game_id, "situation": f"{clock(r)}, {'tied' if r.score_diff == 0 else ('up ' if r.score_diff > 0 else 'down ') + str(abs(int(r.score_diff)))}, 4th & {int(r.ydstogo)} at {'opp' if r.yardline_100 <= 50 else 'own'} {int(r.yardline_100 if r.yardline_100 <= 50 else 100 - r.yardline_100)}",
             "ours": r.us_best, "nfl4th": r.them_best, "coach": r.choice,
             "our_margin_pts": round(float(r.us_margin) * 100, 1), "nfl4th_margin_pts": round(float(r.them_margin) * 100, 1)}
            for r in dis.assign(s=np.minimum(dis["us_margin"], dis["them_margin"])).sort_values("s", ascending=False).head(10).itertuples()],
    }


def pct(x):
    return f"{x * 100:.1f}%"


def report(r):
    a, g, w, d = r["agreement"], r["go_advantage"], r["wp_accuracy_held_out"], r["disagreements_clear"]
    t = r["table"]
    lines = [
        "# Comparison with nfl4th",
        "",
        f"Version {r['version']}. Generated by `engine/compare_nfl4th.py`. Do not edit by hand.",
        "",
        "**Method.** nfl4th (Ben Baldwin, nflverse, MIT licence) publishes win probabilities for go, field goal",
        "and punt on every 4th down since 2014. We join them to our graded decisions on (game_id, play_id) and",
        "compare the recommended option, the size of the go advantage, and the accuracy of each engine's win",
        "probability for the option the coach chose. Source: "
        "[nflverse/nfl4th release `nfl4th_infrastructure`](https://github.com/nflverse/nfl4th/releases/tag/nfl4th_infrastructure).",
        "",
        f"**Sample.** {r['plays']['matched']:,} plays matched ({r['plays']['seasons']}); we grade {r['plays']['ours']:,}, nfl4th lists {r['plays']['nfl4th']:,}.",
        "",
        "## Agreement",
        "",
        "| Plays | Same call |",
        "|---|---|",
        f"| All matched plays | {pct(a['all'])} |",
        f"| Clear calls (both engines: best option leads by 1+ WP point), n = {a['clear_n']:,} | {pct(a['clear_calls'])} |",
        f"| Clear and confident (18 of our 20 resampled models agree), n = {a['confident_n']:,} | {pct(a['confident_calls'])} |",
        "",
        "Rows: our call. Columns: nfl4th's call.",
        "",
        "| | nfl4th go | nfl4th FG | nfl4th punt |",
        "|---|---|---|---|",
    ] + [f"| ours {k} | {t[k]['go']:,} | {t[k]['fg']:,} | {t[k]['punt']:,} |" for k in OPTIONS] + [
        "",
        f"On clear calls they disagree {d['n']:,} times: we say go and nfl4th kicks {d['we_go_they_kick']:,} times; "
        f"nfl4th says go and we kick {d['they_go_we_kick']:,} times; field goal vs punt {d['fg_vs_punt']:,} times.",
        "",
        "## Aggressiveness",
        "",
        f"- We recommend going for it on {pct(g['share_go_ours'])} of plays; nfl4th on {pct(g['share_go_nfl4th'])}.",
        f"- Our go advantage minus nfl4th's: mean {g['mean_ours_minus_theirs_pts']:+.2f} WP points, median {g['median_ours_minus_theirs_pts']:+.2f}.",
        f"- Correlation of the two go advantages: {g['correlation']:.3f}.",
        "",
        "| Yards to go | Plays | Same call | We go, nfl4th kicks | nfl4th goes, we kick |",
        "|---|---|---|---|---|",
    ] + [f"| {k} | {int(v['plays']):,} | {pct(v['agree'])} | {int(v['we_go_they_kick']):,} | {int(v['they_go_we_kick']):,} |" for k, v in r["by_yards_to_go"].items()] + [
        "",
        f"Coaches made the call we recommend on {pct(r['coaches']['agree_with_us'])} of plays, and nfl4th's on {pct(r['coaches']['agree_with_nfl4th'])}.",
        "",
        "## Accuracy of the win probabilities",
        "",
        f"For the option the coach chose, each engine's win probability scored against the final result. Held-out",
        f"seasons only ({w['seasons']}, n = {w['n']:,}); lower is better.",
        "",
        "| Engine | Brier score | Log loss |",
        "|---|---|---|",
        f"| Ours | {w['ours']['brier']:.4f} | {w['ours']['log_loss']:.4f} |",
        f"| nfl4th | {w['nfl4th']['brier']:.4f} | {w['nfl4th']['log_loss']:.4f} |",
        "",
        f"Brier score, ours minus nfl4th: {w['brier_ours_minus_nfl4th']['diff']:+.4f} (95% interval "
        f"{w['brier_ours_minus_nfl4th']['ci95'][0]:+.4f} to {w['brier_ours_minus_nfl4th']['ci95'][1]:+.4f}, resampling "
        f"{w['brier_ours_minus_nfl4th']['games']:,} whole games). An interval that contains 0 means no detectable difference.",
        "",
        "## Largest clear disagreements",
        "",
        "| Game | Situation | Ours | nfl4th | Coach | Our edge | nfl4th edge |",
        "|---|---|---|---|---|---|---|",
    ] + [f"| {x['game_id']} | {x['situation']} | {x['ours']} | {x['nfl4th']} | {x['coach']} | {x['our_margin_pts']} | {x['nfl4th_margin_pts']} |"
         for x in r["biggest_disagreements"]] + [
        "",
        "## What these numbers do not prove",
        "",
        "- Agreement is not accuracy. Two engines can agree and both be wrong.",
        "- No test here shows whose *recommendation* is right: the result of the option a coach did not pick is",
        "  never observed.",
        "- The win-probability scores use only the option the coach chose, which is not a random sample of",
        "  options, and one game contributes many correlated plays. nfl4th's WP model may have been trained on",
        "  some of the held-out seasons; ours was not. Small differences in Brier score are within noise.",
        "- nfl4th's numbers are its published precomputed values, with no weather and a league-average kicker.",
        "  Ours are graded with the actual weather, roof and kicker, so some disagreement is by design.",
    ]
    return "\n".join(lines) + "\n"


def main(download=False):
    if download or not os.path.exists(RDS_PATH):
        if not download:
            sys.exit(f"missing {RDS_PATH}; run with --download")
        os.makedirs(os.path.dirname(RDS_PATH), exist_ok=True)
        urllib.request.urlretrieve(NFL4TH_URL, RDS_PATH)
    theirs = read_rds_frame(RDS_PATH)
    ours = pd.read_csv(os.path.join(ROOT, "data", "decisions.csv.gz"))
    r = compare(ours, theirs)
    with open(os.path.join(ROOT, "data", "nfl4th_comparison.json"), "w") as fh:
        json.dump(r, fh, indent=1)
    with open(os.path.join(ROOT, "docs", "reports", "nfl4th-comparison.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(report(r))
    print(json.dumps({k: r[k] for k in ("plays", "agreement", "go_advantage", "coaches", "wp_accuracy_held_out")}, indent=1))


if __name__ == "__main__":
    main(download="--download" in sys.argv)
