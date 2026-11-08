"""Fit coaches' 4th-down calls to prospect theory, with the engine as the computer.

After Whittaker (2026), "Evaluating 4th Down Decision Making in the NFL with
Prospect Theory", and Tversky & Kahneman (1992). Each option is a gamble the
engine prices: going for it converts with chance p (WP after success, WP after
failure), a field goal is made with chance p, a punt is a sure thing. Outcomes
are measured from the punt's WP (the field goal's when there is no punt), in
units of 5 WP points.

    w(p) = exp(-(-ln p)^gamma)                 probability weighting (Prelec)
    v(x) = x^alpha if x >= 0, else -lam (-x)^alpha
    V(option) = sum over outcomes of w(p) v(x)
    P(coach picks option) = softmax(V / tau)

gamma = 1, lam = 1, alpha = 1 is the computer: plain expected WP. lam is the
"fear of failing": a loss of x feels lam times as big as a gain of x.

League: one fit, with a game-resampled bootstrap for the 95% range. Each coach:
lam only (gamma, alpha, tau held at the league fit), shrunk toward the league
by empirical Bayes, so a coach with few calls stays near the league.

Run:  py engine/fit_prospect.py      (after engine/fit_models.py)
Out:  data/prospect.json, app/prospect.js
Play-by-play comes from data/raw if present, else from the nflverse URL (read
into memory, not saved).
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np
from scipy.optimize import minimize, minimize_scalar

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = CONFIG["prospect"]
CALL_INDEX = {"go": 0, "fg": 1, "punt": 2}


# ---------- the model (pure functions; tested by hand)

def weight(p, gamma):
    """Prelec weighting. w(1/e) = 1/e for every gamma; gamma = 1 is w(p) = p."""
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.exp(-(-np.log(p)) ** gamma)


def value(x, alpha, lam):
    """Gains x^alpha; losses -lam (-x)^alpha."""
    x = np.asarray(x, float)
    return np.where(x >= 0, np.abs(x) ** alpha, -lam * np.abs(x) ** alpha)


def gambles(rows, unit=None):
    """Arrays from priced decisions (dicts or a DataFrame's records): go and fg
    as (p, x_success, x_fail), punt as x, which options exist, and the call."""
    unit = unit or P["unit_wp"]
    nan = float("nan")
    f = lambda v: nan if v is None or v != v else float(v)
    go, fg, pu, ev, ch = [], [], [], [], []
    for r in rows:
        ref = f(r["wp_punt"]) if f(r["wp_punt"]) == f(r["wp_punt"]) else f(r["wp_fg"])
        go.append([f(r["pc"]), (f(r["go_s"]) - ref) / unit, (f(r["go_f"]) - ref) / unit])
        fg.append([f(r["pm"]), (f(r["fg_s"]) - ref) / unit, (f(r["fg_f"]) - ref) / unit])
        pu.append((f(r["wp_punt"]) - ref) / unit)
        ev.append([(f(r["wp_go"]) - ref) / unit, (f(r["wp_fg"]) - ref) / unit, (f(r["wp_punt"]) - ref) / unit])
        ch.append(CALL_INDEX[r["choice"]])
    D = {"go": np.array(go), "fg": np.array(fg), "punt": np.array(pu), "ev": np.array(ev), "choice": np.array(ch)}
    D["avail"] = ~np.isnan(D["ev"])
    return D


def option_values(D, gamma, lam, alpha):
    """Prospect-theory value of each option; -inf where the option does not exist."""
    out = np.full(D["ev"].shape, -np.inf)
    for k, name in ((0, "go"), (1, "fg")):
        m = np.nan_to_num(D[name])
        v = weight(m[:, 0], gamma) * value(m[:, 1], alpha, lam) + weight(1 - m[:, 0], gamma) * value(m[:, 2], alpha, lam)
        out[:, k] = np.where(D["avail"][:, k], v, -np.inf)
    out[:, 2] = np.where(D["avail"][:, 2], value(np.nan_to_num(D["punt"]), alpha, lam), -np.inf)
    return out


def computer_values(D, bias=(0.0, 0.0)):
    """Expected WP of each option, plus an optional constant preference for the
    field goal and the punt (a computer that simply likes kicking)."""
    v = np.nan_to_num(D["ev"]) + np.array([0.0, bias[0], bias[1]])
    return np.where(D["avail"], v, -np.inf)


def log_probs(V, tau, choice):
    z = V / tau
    z = z - z.max(1, keepdims=True)
    lp = z - np.log(np.exp(z).sum(1, keepdims=True))
    return lp[np.arange(len(z)), choice]


def fit_league(D, weights=None, start=(1.0, 2.0, 0.5, 0.3)):
    """Maximum likelihood (gamma, lam, alpha, tau); weights repeat rows (bootstrap)."""
    w = np.ones(len(D["choice"])) if weights is None else weights

    def nll(t):
        g, lam, a, tau = np.exp(t)
        return -(w * log_probs(option_values(D, g, lam, a), tau, D["choice"])).sum()
    r = minimize(nll, np.log(start), method="L-BFGS-B", bounds=[(np.log(0.05), np.log(20))] * 4)
    return np.exp(r.x), r.fun


def fit_computer(D, bias=False):
    """The computer's only free number is tau (and the kick preference, if asked)."""
    def nll(t):
        b = (t[1], t[2]) if bias else (0.0, 0.0)
        return -log_probs(computer_values(D, b), np.exp(t[0]), D["choice"]).sum()
    r = minimize(nll, [0.0, 0.0, 0.0] if bias else [0.0], method="L-BFGS-B")
    tau = np.exp(r.x[0])
    return tau, ((r.x[1], r.x[2]) if bias else (0.0, 0.0)), r.fun


def subset(D, mask):
    return {k: v[mask] for k, v in D.items()}


def coach_raw(D, games, league):
    """One coach's log lam with the league's gamma, alpha, tau; standard error
    clustered by game (calls in one game are not independent)."""
    g, _, a, tau = league

    def lp(loglam):
        return log_probs(option_values(D, g, np.exp(loglam), a), tau, D["choice"])
    r = minimize_scalar(lambda x: -lp(x).sum(), bounds=(np.log(0.2), np.log(20)), method="bounded")
    x, h = r.x, 1e-3
    score = (lp(x + h) - lp(x - h)) / (2 * h)
    hess = -(lp(x + h).sum() - 2 * lp(x).sum() + lp(x - h).sum()) / h ** 2
    _, inv = np.unique(games, return_inverse=True)
    s_game = np.bincount(inv, weights=score)
    var = (s_game ** 2).sum() / hess ** 2 if hess > 0 else float("inf")
    return float(x), float(np.sqrt(var))


def prior_sd(raw, se):
    """Spread of true coach values: raw spread minus the noise in each estimate."""
    raw, se = np.asarray(raw), np.asarray(se)
    return float(np.sqrt(max(raw.var() - (se ** 2).mean(), 1e-4)))


def shrink(raw, se, mean, sd):
    """Normal-normal posterior: precision-weighted average of the coach and the league."""
    prec = 1 / se ** 2 + 1 / sd ** 2
    return (raw / se ** 2 + mean / sd ** 2) / prec, np.sqrt(1 / prec)


# ---------- the pipeline

def price(d):
    """Run build/prospect.js on every decision, one node process per core."""
    import grade_coaches as gc
    rows = [{"id": i, "state": gc.decision_state(r, d.attrs, *d.attrs["kick"])}
            for i, (_, r) in enumerate(d.iterrows())]
    n = max(1, (os.cpu_count() or 2) - 2)
    tmp = os.path.join(ROOT, "data", "prospect_tmp")
    os.makedirs(tmp, exist_ok=True)
    procs, outs = [], []
    for i in range(n):
        inp, outp = os.path.join(tmp, f"in_{i}.json"), os.path.join(tmp, f"out_{i}.json")
        with open(inp, "w") as fh:
            json.dump({"toggles": CONFIG["grade_toggles"], "decisions": rows[i::n]}, fh)
        procs.append(subprocess.Popen(["node", os.path.join(ROOT, "build", "prospect.js"), inp, outp]))
        outs.append(outp)
    for pr in procs:
        if pr.wait() != 0:
            raise SystemExit("a pricing process failed")
    priced = sorted((x for o in outs for x in json.load(open(o))), key=lambda x: x["id"])
    shutil.rmtree(tmp, ignore_errors=True)
    return priced


def main():
    import grade_coaches as gc
    _, d, ab, by_game, by_season = gc.prepare(P["seasons"])
    d = d[d["qtr"] <= 4].reset_index(drop=True)          # no overtime
    d.attrs["kick"] = (ab, by_game, by_season)
    print(f"pricing {len(d):,} decisions ...", flush=True)
    priced = price(d)
    for x, (_, r) in zip(priced, d.iterrows()):
        x["choice"] = gc.CHOICE[r["play_type"]]
    D = gambles(priced)
    season = d["season"].to_numpy()
    games = d["game_id"].to_numpy()
    coach = d["coach"].replace(CONFIG["coach_aliases"]).to_numpy()
    n = len(season)

    league, nll = fit_league(D)
    print("league:", np.round(league, 3), flush=True)

    # 95% range: refit on games drawn with replacement
    rng = np.random.default_rng(P["seed"])
    ug, inv = np.unique(games, return_inverse=True)
    reps = []
    for _ in range(P["bootstrap_reps"]):
        pick = np.bincount(rng.integers(0, len(ug), len(ug)), minlength=len(ug))
        reps.append(fit_league(D, weights=pick[inv].astype(float), start=league)[0])
    lo, hi = np.percentile(np.array(reps), [2.5, 97.5], axis=0)

    # Hold-out: fit before the hold-out seasons, score on them
    h0, h1 = P["holdout"]
    tr, te = season < h0, (season >= h0) & (season <= h1)
    Dtr, Dte = subset(D, tr), subset(D, te)
    pt, _ = fit_league(Dtr, start=league)
    tc, _, _ = fit_computer(Dtr)
    tb, bb, _ = fit_computer(Dtr, bias=True)

    def score(V, tau):
        return {"log_loss": round(float(-log_probs(V, tau, Dte["choice"]).mean()), 4),
                "accuracy": round(float((V.argmax(1) == Dte["choice"]).mean()), 4)}
    holdout = {"fit_seasons": [int(season.min()), h0 - 1], "test_seasons": [h0, h1], "n": int(te.sum()),
               "computer": score(computer_values(Dte), tc),
               "computer_likes_kicking": score(computer_values(Dte, bb), tb),
               "prospect": score(option_values(Dte, *pt[:3]), pt[3])}

    eras = []
    for a, b in P["eras"]:
        m = (season >= a) & (season <= b)
        t, _ = fit_league(subset(D, m), start=league)
        eras.append({"from": a, "to": b, "n": int(m.sum()), "gamma": round(t[0], 3),
                     "lambda": round(t[1], 3), "alpha": round(t[2], 3)})

    # Each coach: raw, then shrunk toward the league
    names = sorted(set(c for c in coach if isinstance(c, str)))
    raw = {}
    for c in names:
        m = coach == c
        x, se = coach_raw(subset(D, m), games[m], league)
        raw[c] = (x, se, int(m.sum()), len(set(games[m])), int(season[m].min()), int(season[m].max()))
    big = [v for v in raw.values() if v[2] >= P["min_decisions"]]
    mu, sd = float(np.log(league[1])), prior_sd([v[0] for v in big], [v[1] for v in big])
    coaches = []
    for c, (x, se, k, g, s0, s1) in raw.items():
        post, psd = shrink(x, se, mu, sd)
        coaches.append({"coach": c, "decisions": k, "games": g, "first_season": s0, "last_season": s1,
                        "lambda": round(float(np.exp(post)), 2),
                        "lo": round(float(np.exp(post - 1.96 * psd)), 2),
                        "hi": round(float(np.exp(post + 1.96 * psd)), 2),
                        "raw_lambda": round(float(np.exp(x)), 2), "raw_se_log": round(se, 4),
                        "few_calls": k < P["min_decisions"]})
    coaches.sort(key=lambda c: c["lambda"])

    g, lam, a, tau = league
    out = {"version": CONFIG["version"],
           "source": "Whittaker (2026); Tversky & Kahneman (1992). Engine: app/model.js.",
           "reference": "punt WP (field goal WP when there is no punt)", "unit_wp": P["unit_wp"],
           "seasons": [int(season.min()), int(season.max())], "n": n, "games": int(len(ug)),
           "league": {"gamma": round(g, 3), "lambda": round(lam, 3), "alpha": round(a, 3), "tau": round(tau, 3),
                      "ci95": {k: [round(float(lo[i]), 3), round(float(hi[i]), 3)]
                               for i, k in enumerate(["gamma", "lambda", "alpha", "tau"])},
                      "bootstrap_reps": P["bootstrap_reps"]},
           "readouts": {"feels_51": round(float(weight(0.51, g)), 3), "feels_85": round(float(weight(0.85, g)), 3),
                        "feels_10": round(float(weight(0.10, g)), 3),
                        "gain_4_vs_1": round(float(4 ** a), 2), "lab_lambda": P["lab_lambda"]},
           "holdout": holdout, "eras": eras,
           "shrinkage": {"prior_mean_log_lambda": round(mu, 4), "prior_sd_log_lambda": round(sd, 4),
                         "coaches_used": len(big)},
           "coaches": coaches}
    with open(os.path.join(ROOT, "data", "prospect.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, indent=1)
    app = {"league": round(lam, 2), "lab": P["lab_lambda"],
           "coaches": {c["coach"]: [c["lambda"], c["lo"], c["hi"], c["decisions"]] for c in coaches}}
    with open(os.path.join(ROOT, "app", "prospect.js"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("// Written by engine/fit_prospect.py. Fear of failing (prospect-theory lambda):\n"
                 "// coach -> [lambda, low, high, decisions]. Do not edit by hand.\n"
                 "const PROSPECT = " + json.dumps(app, separators=(",", ":")) + ";\n"
                 "if (typeof module !== \"undefined\") module.exports = PROSPECT;\n")
    print(json.dumps({k: out[k] for k in ("league", "readouts", "holdout", "eras", "shrinkage")}, indent=1))


if __name__ == "__main__":
    main()
