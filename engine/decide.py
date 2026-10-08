"""Reference decision engine: go for it, kick a field goal, or punt.

Plain Python with no dependencies so that app/engine.js can mirror it line for
line. tests/parity.js checks the two agree on the shipped model.

Method: each option leads to a small set of next states. The win probability
(WP) model scores each next state. The option's value is the probability-
weighted WP across its outcomes. The best option is the one with the highest
value. See docs/fourth-down-whitepaper.md, section 3.
"""
import math

WP_FEATURES = ["score_diff", "game_seconds", "half_seconds", "second_half",
               "yardline", "down", "ydstogo", "pos_to", "def_to",
               "tmw_pending", "receive_2h", "spread", "home"]
# Derived inside wp_raw (nflfastR's engineered terms, Baldwin 2021): the spread's
# weight fades as the game runs, and a lead counts more as time runs out.
WP_DERIVED = ["spread_time", "diff_time_ratio"]


def sigmoid(z):
    return 1.0 / (1.0 + math.exp(-z))


# ---------------------------------------------------------------- WP model
def tree_value(tree, x):
    """tree: list of nodes [feature, threshold, left, right, value, is_leaf]."""
    i = 0
    while True:
        f, thr, left, right, val, leaf = tree[i]
        if leaf:
            return val
        i = left if x[f] <= thr else right


def wp_raw(model, s):
    """Win probability for the team with the ball in state s."""
    e4 = math.exp(-4.0 * (3600.0 - s["game_seconds"]) / 3600.0)
    x = [s[k] for k in WP_FEATURES] + [s["spread"] * e4, s["score_diff"] / e4]
    z = model["wp"]["baseline"]
    for t in model["wp"]["trees"]:
        z += tree_value(t, x)
    return sigmoid(z)


# ---------------------------------------------------------------- logistic helpers
def logistic(m, feats):
    z = m["intercept"]
    for name, c in zip(m["names"], m["coef"]):
        z += c * feats[name]
    return sigmoid(z)


def env_features(st, tog):
    """Weather and stadium inputs, neutral when their toggle is off."""
    indoor = 1 if (tog.get("stadium") and st.get("indoor")) else 0
    alt = st.get("altitude_kft", 0.0) if tog.get("stadium") else 0.0
    if tog.get("weather") and not indoor:
        wind, temp, precip = st.get("wind", 0.0), st.get("temp", 60.0), st.get("precip", 0)
    else:
        wind, temp, precip = 0.0, 70.0, 0
    return {"wind": wind / 10.0, "cold": max(0.0, 50.0 - temp) / 10.0,
            "precip": precip, "indoor": indoor, "altitude": alt}


def combo_key(tog):
    parts = [k for k in ("weather", "stadium") if tog.get(k)]
    return "+".join(parts) or "base"


def p_convert(model, st, tog):
    togo, yl = st["ydstogo"], st["yardline"]
    f = {"is4": 1, "togo": min(togo, 20) / 10.0, "logtogo": math.log(togo),
         "goal": 1 if togo >= yl else 0, "inside10": 1 if yl <= 10 else 0,
         "rz": 1 if (11 <= yl <= 20 and togo < yl) else 0,
         "spread": (st.get("spread", 0.0) / 10.0) if tog.get("spread") else 0.0}
    key = "spread" if tog.get("spread") else "base"
    return logistic(model["conv"][key], f)


def p_field_goal(model, st, tog):
    d = st["yardline"] + model["rules"]["fg_distance_add"]
    e = env_features(st, tog)
    f = {"dist": d / 10.0, "dist2": (d / 10.0) ** 2,
         "year": (model["rules"]["season"] - 2014) / 10.0,
         "era20": 1 if model["rules"]["season"] >= 2020 else 0,
         "wind": e["wind"], "wind_x_dist": e["wind"] * d / 10.0,
         "cold": e["cold"], "precip": e["precip"],
         "indoor": e["indoor"], "altitude": e["altitude"]}
    m = model["fg"]["models"][combo_key(tog)]
    z = m["intercept"] + sum(c * f[n] for n, c in zip(m["names"], m["coef"]))
    if tog.get("kicker"):
        # accuracy shifts the curve; range tilts it around 40 yards
        z += st.get("kicker_a", 0.0) + st.get("kicker_b", 0.0) * (d - 40.0) / 10.0
    return sigmoid(z)


def punt_bin(model, yl):
    for cand in model["punt"]["bins"]:
        if cand["lo"] <= yl <= cand["hi"]:
            return cand
    return model["punt"]["bins"][-1]


def punt_spots(model, st, tog):
    """Opponent yardline_100 after a normal punt (no return TD, no muff), as
    equally likely quantiles."""
    b = punt_bin(model, st["yardline"])
    shift = 0.0
    key = combo_key(tog)
    if key != "base":
        e = env_features(st, tog)
        adj = model["punt"]["adj"][key]
        shift = sum(c * e[n] for n, c in zip(adj["names"], adj["coef"]))
    return [min(99.0, max(1.0, q + shift)) for q in b["q"]]


# ---------------------------------------------------------------- state transitions
def togo_bucket(model, togo):
    edges = model["gain"]["edges"]
    i = 0
    for j, e in enumerate(edges[:-1]):
        if togo >= e:
            i = j
    return i


def elapsed(model, kind, half_seconds):
    return model["clock"][kind][1 if half_seconds <= 120 else 0]


def value_after(model, st, us_ball, sd_us, yardline, secs, togo=None, down=1, pos_to=None):
    """WP for US after an event: who has the ball, the score, the spot, the clock.

    st holds the clock and timeouts at the snap. Timeouts carry over, unless
    pos_to overrides ours (a timeout we just used).
    """
    our_to = st["pos_to"] if pos_to is None else pos_to
    hs = st["half_seconds"]
    tmw = st["tmw_pending"]
    if tmw and hs - secs < 120:
        hs_new, tmw_new = 120.0, 0          # the two-minute warning stops the clock
    else:
        hs_new, tmw_new = hs - secs, tmw if hs - secs > 120 else 0
    if hs_new <= 0:
        if st["second_half"]:
            return 1.0 if sd_us > 0 else (0.0 if sd_us < 0 else 0.5)
        # Halftime: the second-half receiver starts at the kickoff spot.
        us_recv = st["receive_2h"] == 1
        s2 = {"score_diff": sd_us if us_recv else -sd_us, "game_seconds": 1800.0,
              "half_seconds": 1800.0, "second_half": 1, "yardline": model["kickoff_start"],
              "down": 1, "ydstogo": 10, "pos_to": 3, "def_to": 3, "tmw_pending": 1,
              "receive_2h": 0, "spread": st["spread_used"] * (1 if us_recv else -1),
              "home": st["home"] if us_recv else 1 - st["home"]}
        p = wp_raw(model, s2)
        return p if us_recv else 1.0 - p
    gs = hs_new + (0 if st["second_half"] else 1800)
    yl = min(99.0, max(1.0, yardline))
    s = {"score_diff": sd_us if us_ball else -sd_us, "game_seconds": gs,
         "half_seconds": hs_new, "second_half": st["second_half"], "yardline": yl,
         "down": down, "ydstogo": togo if togo is not None else min(10.0, yl),
         "pos_to": our_to if us_ball else st["def_to"],
         "def_to": st["def_to"] if us_ball else our_to,
         "tmw_pending": tmw_new,
         "receive_2h": (st["receive_2h"] if us_ball else 1 - st["receive_2h"]) if not st["second_half"] else 0,
         "spread": st["spread_used"] if us_ball else -st["spread_used"],
         "home": st["home"] if us_ball else 1 - st["home"]}
    p = wp_raw(model, s)
    return p if us_ball else 1.0 - p


def prepare(st, tog):
    """Fill the derived fields of a 4th-down state."""
    s = dict(st)
    s["second_half"] = 1 if s["qtr"] >= 3 else 0
    s["tmw_pending"] = 1 if s["half_seconds"] > 120 else 0
    s["spread_used"] = s.get("spread", 0.0) if tog.get("spread") else 0.0
    s["down"] = s.get("down", 4)
    if s["second_half"]:
        s["receive_2h"] = 0
    return s


# ---------------------------------------------------------------- the three options
def wp_go(model, st, tog):
    yl, sd, hs = st["yardline"], st["score_diff"], st["half_seconds"]
    pc = p_convert(model, st, tog)
    b = togo_bucket(model, st["ydstogo"])
    pts = model["rules"]["td_points"]
    succ = 0.0
    gains = model["gain"]["success_q"][b]
    for g in gains:
        g = max(g, st["ydstogo"])
        if g >= yl:      # touchdown, then we kick off
            succ += value_after(model, st, False, sd + pts, model["kickoff_start"], elapsed(model, "score", hs))
        else:
            succ += value_after(model, st, True, sd, yl - g, elapsed(model, "go_success", hs))
    succ /= len(gains)
    fail_spot = 100.0 - (yl - model["gain"]["fail_mean"][b])
    fail = value_after(model, st, False, sd, fail_spot, elapsed(model, "go_fail", hs))
    return pc * succ + (1 - pc) * fail, {"p_convert": pc, "wp_if_convert": succ, "wp_if_fail": fail}


def wp_play(model, st, tog):
    """1st-3rd down: run one more play, then value where it leaves us.

    Gains come from real plays on that down and distance; turnovers at the
    real rate. If the play would run out the clock we call a timeout (the play
    then costs only its own length) or, with none left, spike the ball, which
    costs a down."""
    yl, sd, hs, dn, togo = st["yardline"], st["score_diff"], st["half_seconds"], st["down"], st["ydstogo"]
    b = togo_bucket(model, togo)
    gains = model["play"]["gain_q"][dn - 1][b]
    p_to = model["play"]["p_turnover"][dn - 1]
    pts = model["rules"]["td_points"]
    first, short = [], []
    for g in gains:
        if g >= yl:
            first.append(value_after(model, st, False, sd + pts, model["kickoff_start"], elapsed(model, "score", hs)))
            continue
        made = g >= togo
        secs = elapsed(model, "play_first" if made else "play_short", hs)
        to = st["pos_to"]
        nd = 1 if made else dn + 1
        if hs - secs <= 0:
            # the clock would run out: call a timeout, or else spike the ball
            # (costs a down; allowed while it leaves at least 4th down)
            if to > 0:
                secs, to = model["clock"]["timeout_play"], to - 1
            elif nd + 1 <= 4:
                secs, nd = model["clock"]["spike_total"], nd + 1
        new_yl = yl - g
        if made:
            first.append(value_after(model, st, True, sd, new_yl, secs, down=nd, pos_to=to))
        else:
            nt = min(max(togo - g, 1.0), min(99.0, max(1.0, new_yl)))
            short.append(value_after(model, st, True, sd, new_yl, secs, togo=nt, down=nd, pos_to=to))
    tov = value_after(model, st, False, sd, 100.0 - yl, elapsed(model, "go_fail", hs))
    n = len(gains)
    v = (1 - p_to) * (sum(first) + sum(short)) / n + p_to * tov
    p_first = (1 - p_to) * len(first) / n
    return v, {"p_convert": p_first,
               "wp_if_convert": sum(first) / len(first) if first else None,
               "wp_if_fail": ((1 - p_to) * sum(short) / n + p_to * tov) / (1 - p_first) if p_first < 1 else None,
               "p_turnover": p_to}


def wp_fg(model, st, tog):
    yl, sd, hs = st["yardline"], st["score_diff"], st["half_seconds"]
    r = model["rules"]
    if yl + r["fg_distance_add"] > r["fg_max_distance"]:
        return None, {"p_make": 0.0, "distance": yl + r["fg_distance_add"], "out_of_range": True}
    pm = p_field_goal(model, st, tog)
    make = value_after(model, st, False, sd + 3, model["kickoff_start"], elapsed(model, "fg", hs))
    spot = yl + r["fg_snap_to_spot"]
    opp_yl = 80.0 if spot <= r["missed_fg_min_spot"] else 100.0 - spot
    miss = value_after(model, st, False, sd, opp_yl, elapsed(model, "fg", hs))
    return pm * make + (1 - pm) * miss, {"p_make": pm, "wp_if_make": make, "wp_if_miss": miss,
                                         "distance": yl + r["fg_distance_add"]}


def wp_punt(model, st, tog):
    spots = punt_spots(model, st, tog)
    b = punt_bin(model, st["yardline"])
    hs = st["half_seconds"]
    secs = elapsed(model, "punt", hs)
    sd = st["score_diff"]
    r = model["rules"]
    # Fair-catch kick (Rule 11-4-3): late in a half, a fair catch lets them try a
    # free-kick field goal from the catch spot (distance = spot + 10, no rush),
    # untimed if the punt ran out the clock. They take it when it beats playing on.
    fc_secs = model["clock"]["punt_fair_catch"][1 if hs <= 120 else 0]
    window = hs - fc_secs <= r["fair_catch_kick_window"]
    end = lambda s_: value_after(model, st, False, s_, 50.0, hs + 1.0)   # the half ends
    fck_risk = 0.0

    def spot_value(y):
        nonlocal fck_risk
        v_n = value_after(model, st, False, sd, y, secs)
        if not window or y + 10 > r["fg_max_distance"]:
            return v_n
        # their kick, our weather and stadium, a league-average kicker
        pm = p_field_goal(model, dict(st, yardline=y - r["fg_distance_add"] + 10), dict(tog, kicker=False))
        v_fck = pm * end(sd - 3) + (1 - pm) * end(sd)
        v_play_on = value_after(model, st, False, sd, y, fc_secs)
        if v_fck < v_play_on:
            fck_risk += b["p_fc"] * pm / len(spots)
        v_fc = min(v_play_on, v_fck)
        return (1 - b["p_fc"]) * v_n + b["p_fc"] * v_fc

    normal = sum(spot_value(y) for y in spots) / len(spots)
    # return touchdown: they score 7, we receive the kickoff
    td = value_after(model, st, True, sd - model["rules"]["td_points"], model["kickoff_start"], secs)
    # muff recovered by us: our ball at the recovery spot
    muff = value_after(model, st, True, sd, b["muff_spot"], secs)
    v = (1 - b["p_td"] - b["p_muff"]) * normal + b["p_td"] * td + b["p_muff"] * muff
    return v, {"opp_yardline_mean": sum(spots) / len(spots), "p_return_td": b["p_td"], "p_muff": b["p_muff"],
               "fair_catch_kick_risk": fck_risk}


def decide(model, state, toggles=None):
    """state keys: score_diff, qtr, half_seconds, yardline, ydstogo, pos_to, down (default 4),
    def_to, home, receive_2h, and optional spread, wind, temp, precip, indoor,
    altitude_kft, kicker_a, kicker_b. Returns WP of each option and the call."""
    tog = toggles or {}
    st = prepare(state, tog)
    if st["down"] < 4:          # early down: run a play or kick now; nobody punts
        go, gd = wp_play(model, st, tog)
        pu, pd = None, {}
    else:
        go, gd = wp_go(model, st, tog)
        pu, pd = wp_punt(model, st, tog)
    fg, fd = wp_fg(model, st, tog)
    opts = {"go": go, "fg": fg, "punt": pu}
    avail = {k: v for k, v in opts.items() if v is not None}
    ranked = sorted(avail, key=avail.get, reverse=True)
    margin = avail[ranked[0]] - avail[ranked[1]] if len(ranked) > 1 else 1.0
    return {"wp": opts, "best": ranked[0], "margin": margin,
            "tossup": margin < model["rules"]["tossup_margin"],
            "detail": {"go": gd, "fg": fd, "punt": pd}}
