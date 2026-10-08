"""Kicker skill: accuracy and range, shrunk toward the league, plus replacement level.

For a kick at distance d with environment-adjusted league logit z:

    logit P(make) = z + a_k + b_k * (d - 40) / 10

a_k is accuracy (the shift at 40 yards). b_k is range (how much the curve
tilts with distance; b_k > 0 means the kicker holds his make rate longer).
Each kicker's (a_k, b_k) is a MAP estimate under independent normal priors
N(0, sa^2) and N(0, sb^2). The prior widths are chosen on hold-out seasons.

Replacement level is the pooled, unshrunk (a, b) of fringe kickers: careers
that started in or after `first_season_min`, ended by `last_season_max`, and
had fewer than `max_attempts` attempts. These are the short-tenure fill-ins a
team can sign off the street.
"""
import numpy as np

PIVOT = 40.0


def _x(dist):
    return (np.asarray(dist, dtype=float) - PIVOT) / 10.0


def fit_one(z, x, y, sa, sb, iters=30):
    """Newton's method for the 2-parameter penalised logistic MAP."""
    a = b = 0.0
    ia = 0.0 if sa is None else 1.0 / sa ** 2
    ib = 0.0 if sb is None else 1.0 / sb ** 2
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-(z + a + b * x)))
        r = y - p
        w = p * (1 - p)
        g = np.array([r.sum() - a * ia, (r * x).sum() - b * ib])
        H = -np.array([[w.sum() + ia, (w * x).sum()], [(w * x).sum(), (w * x * x).sum() + ib]])
        step = np.linalg.solve(H, g)
        a, b = a - step[0], b - step[1]
        if abs(step).max() < 1e-9:
            break
    return float(a), float(b)


def fit_effects(f, sa, sb):
    """{kicker_id: (a, b)} for every kicker in frame f (needs _z, made, kick_distance)."""
    if sa == 0 and sb == 0:
        return {}
    out = {}
    for kid, g in f.groupby("kicker_player_id"):
        out[kid] = fit_one(g["_z"].values, _x(g["kick_distance"].values), g["made"].values,
                           sa if sa > 0 else 1e-6, sb if sb > 0 else 1e-6)
    return out


def apply(f, effects):
    ab = f["kicker_player_id"].map(effects)
    a = np.array([t[0] if isinstance(t, tuple) else 0.0 for t in ab])
    b = np.array([t[1] if isinstance(t, tuple) else 0.0 for t in ab])
    return f["_z"].values + a + b * _x(f["kick_distance"].values)


def replacement(f, cfg):
    """nflWAR rule: kicks by kickers ranked outside the top `rank_cutoff` by
    attempts in that season, pooled into one unshrunk (a, b)."""
    n = f.groupby(["season", "kicker_player_id"]).size().rename("n").reset_index()
    n["rank"] = n.groupby("season")["n"].rank(ascending=False, method="first")
    low = n[n["rank"] > cfg["rank_cutoff"]][["season", "kicker_player_id"]]
    g = f.merge(low, on=["season", "kicker_player_id"])
    a, b = fit_one(g["_z"].values, _x(g["kick_distance"].values), g["made"].values, None, None)
    return {"rule": f"outside top {cfg['rank_cutoff']} by attempts in the season",
            "a": a, "b": b, "kicker_seasons": int(len(low)), "attempts": int(len(g)),
            "made_pct": float(g["made"].mean()), "expected_pct": float((1 / (1 + np.exp(-g["_z"]))).mean())}


def replacement_fringe(f, cfg):
    car = f.groupby("kicker_player_id").agg(n=("made", "size"), first=("season", "min"), last=("season", "max"))
    fringe = car[(car["n"] < cfg["max_attempts"]) & (car["first"] >= cfg["first_season_min"])
                 & (car["last"] <= cfg["last_season_max"])].index
    g = f[f["kicker_player_id"].isin(fringe)]
    a, b = fit_one(g["_z"].values, _x(g["kick_distance"].values), g["made"].values, None, None)
    return {"rule": "short careers inside the data", "a": a, "b": b, "kickers": int(len(fringe)), "attempts": int(len(g)),
            "made_pct": float(g["made"].mean()), "expected_pct": float((1 / (1 + np.exp(-g["_z"]))).mean())}


def fifty_pct_distance(z_at, a, b):
    """Distance (yards) where make probability is 50% in neutral conditions.

    z_at(d) is the league logit at distance d. Scans 20-70 yards, the range of
    the data; returns None when the kicker is still above 50% at 70 yards."""
    for d in np.arange(20, 70.01, 0.5):
        if z_at(d) + a + b * (d - PIVOT) / 10 < 0:
            return float(d)
    return None


def grade(f, effects, repl, z_at):
    """Per-kicker table: raw results, over-expected, shrunk skill, and value over replacement."""
    rows = []
    sig = lambda v: 1 / (1 + np.exp(-v))
    for kid, g in f.groupby("kicker_player_id"):
        a, b = effects.get(kid, (0.0, 0.0))
        x = _x(g["kick_distance"].values)
        z = g["_z"].values
        exp_league = sig(z).sum()
        p_true = sig(z + a + b * x)
        p_repl = sig(z + repl["a"] + repl["b"] * x)
        rows.append({
            "id": kid, "name": g["kicker_player_name"].iloc[-1],
            "first_season": int(g["season"].min()), "last_season": int(g["season"].max()),
            "attempts": int(len(g)), "made": int(g["made"].sum()),
            "fg_pct": round(float(g["made"].mean()), 3),
            "expected_pct": round(float(exp_league / len(g)), 3),
            "fgoe": round(float(g["made"].sum() - exp_league), 1),
            "points_over_expected": round(float(3 * (g["made"].sum() - exp_league)), 1),
            "accuracy": round(a, 3), "range": round(b, 3),
            "make_pct_50yd": round(float(sig(z_at(50) + a + b * 1.0)), 3),
            "make_pct_55yd": round(float(sig(z_at(55) + a + b * 1.5)), 3),
            "fifty_pct_distance": fifty_pct_distance(z_at, a, b),
            "points_above_replacement": round(float(3 * (p_true - p_repl).sum()), 1),
            "par_per_100": round(float(300 * (p_true - p_repl).mean()), 1),
        })
    return rows
