"""Engine arithmetic on stub models. Every expected value is derived by hand.

Stub WP model: one split. Feature index 0 is score_diff, 2 is half_seconds,
4 is yardline. Leaf logits of +1 / -1 give WP of
S1 = sigmoid(1) = 0.7310585786 and S_1 = sigmoid(-1) = 0.2689414214.
Stub conversion: P = 0.5. Stub field goal: logit ln 3, so P(make) = 0.75.
Every success gains 5 yards. Every clock runoff is 5 seconds.
"""
import math

import pytest

import decide
from conftest import S1, S_1, make_stub

BASE = dict(score_diff=0, qtr=4, half_seconds=600, yardline=20, ydstogo=5,
            pos_to=3, def_to=3, home=1, receive_2h=0)


def test_sigmoid_values():
    assert decide.sigmoid(0) == 0.5
    assert decide.sigmoid(1) == pytest.approx(0.7310585786, abs=1e-10)


def test_option_values_midgame():
    """Stub: score_diff <= -1 -> logit -1, else +1 (the team with the ball wins
    when not behind).
    Go:   convert -> our ball, tied -> S1; fail -> their ball, tied -> 1 - S1 = S_1.
          0.5 * S1 + 0.5 * S_1 = 0.5
    FG:   make -> their ball, they trail 3 -> their WP S_1 -> ours S1.
          miss -> their ball, tied -> ours S_1.  0.75 S1 + 0.25 S_1 = 0.6155292893
    Punt: their ball, tied -> S_1 = 0.2689414214
    """
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, BASE)
    assert out["wp"]["go"] == pytest.approx(0.5, abs=1e-12)
    assert out["wp"]["fg"] == pytest.approx(0.75 * S1 + 0.25 * S_1, abs=1e-12)
    assert out["wp"]["fg"] == pytest.approx(0.6155292893, abs=1e-9)
    assert out["wp"]["punt"] == pytest.approx(S_1, abs=1e-12)
    assert out["best"] == "fg"
    assert out["margin"] == pytest.approx(0.6155292893 - 0.5, abs=1e-9)
    assert out["tossup"] is False


def test_last_play_field_goal_wins_or_loses():
    """Q4, 3 s left, down 2. Any play ends the game (runoff 5 s).
    FG: make -> up 1 -> 1.0; miss -> down 2 -> 0.0. Value = P(make) = 0.75.
    Go: a non-TD conversion ends the game down 2 -> 0.0. Punt -> 0.0."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, score_diff=-2, half_seconds=3))
    assert out["wp"]["fg"] == pytest.approx(0.75)
    assert out["wp"]["go"] == 0.0
    assert out["wp"]["punt"] == 0.0
    assert out["best"] == "fg"


def test_touchdown_on_last_play():
    """4th & 3 at the 3, down 5, 3 s left. A conversion gains 5 >= 3 -> TD ->
    up 2 -> game over, win. Go = 0.5 * 1 + 0.5 * 0 = 0.5. FG -> down 2 -> 0."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, score_diff=-5, half_seconds=3, yardline=3, ydstogo=3))
    assert out["wp"]["go"] == pytest.approx(0.5)
    assert out["wp"]["fg"] == 0.0
    assert out["best"] == "go"


def test_tied_at_end_is_half():
    """Game ends tied -> 0.5 (overtime treated as a coin flip)."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    st = decide.prepare(dict(BASE, half_seconds=3), {})
    assert decide.value_after(m, st, True, 0, 50, 5) == 0.5


def test_two_minute_warning_stops_the_clock():
    """Stub on half_seconds (index 2): <= 100 -> +1, else -1.
    From 2:05 with a 37 s play the clock stops at 2:00 (120 > 100) -> -1 -> S_1.
    From 1:55 (warning already used) 115 - 37 = 78 <= 100 -> +1 -> S1."""
    m = make_stub(2, 100.0, 1.0, -1.0)
    st = decide.prepare(dict(BASE, half_seconds=125), {})
    assert st["tmw_pending"] == 1
    assert decide.value_after(m, st, True, 0, 50, 37) == pytest.approx(S_1)
    st2 = decide.prepare(dict(BASE, half_seconds=115), {})
    assert st2["tmw_pending"] == 0
    assert decide.value_after(m, st2, True, 0, 50, 37) == pytest.approx(S1)


def test_halftime_gives_ball_to_second_half_receiver():
    """First half, 3 s left, we receive the 2nd-half kickoff, tied.
    Stub on score_diff: tied -> +1 for the team with the ball -> S1 for us.
    If they receive: they have the ball tied -> their S1 -> ours S_1."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    st = decide.prepare(dict(BASE, qtr=2, half_seconds=3, receive_2h=1), {})
    assert decide.value_after(m, st, False, 0, 50, 5) == pytest.approx(S1)
    st = decide.prepare(dict(BASE, qtr=2, half_seconds=3, receive_2h=0), {})
    assert decide.value_after(m, st, True, 0, 50, 5) == pytest.approx(S_1)


def test_missed_field_goal_spot():
    """Stub on yardline (index 4): <= 70 -> +1, else -1.
    From the 10: kick spot 17 <= 20 -> their ball at their 20 (yardline 80) -> -1
    -> their S_1 -> our S1.  From the 30: spot 37 -> yardline 63 -> +1 -> ours S_1."""
    m = make_stub(4, 70.0, 1.0, -1.0)
    m["fg"]["models"]["base"]["intercept"] = -50.0          # always miss
    st = decide.prepare(dict(BASE, yardline=10, ydstogo=10), {})
    assert decide.wp_fg(m, st, {})[0] == pytest.approx(S1, abs=1e-9)
    st = decide.prepare(dict(BASE, yardline=30), {})
    assert decide.wp_fg(m, st, {})[0] == pytest.approx(S_1, abs=1e-9)


def test_field_goal_out_of_range():
    """Yardline 54 -> 71-yard kick > 70 max -> not an option."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, yardline=54, ydstogo=5))
    assert out["wp"]["fg"] is None
    assert out["best"] in ("go", "punt")


def test_kicker_accuracy_and_range():
    """League logit 0 at every distance. Kicker a = 0.5, b = -0.2, kick from
    yardline 33 = 50 yards: z = 0.5 + (-0.2)(50 - 40)/10 = 0.3 -> sigmoid(0.3)."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["fg"]["models"]["base"]["intercept"] = 0.0
    st = dict(yardline=33, kicker_a=0.5, kicker_b=-0.2)
    assert decide.p_field_goal(m, st, {"kicker": True}) == pytest.approx(1 / (1 + math.exp(-0.3)))
    assert decide.p_field_goal(m, st, {}) == 0.5        # toggle off: league kicker


def test_punt_return_td_and_muff():
    """p_td = 0.1, p_muff = 0.2. Stub on score_diff (<= -1 -> -1).
    normal punt: their ball, tied -> ours S_1.
    return TD: our ball, down 7 -> -1 -> S_1.  muff: our ball, tied -> S1.
    0.7 S_1 + 0.1 S_1 + 0.2 S1 = 0.8 * 0.2689414214 + 0.2 * 0.7310585786."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["punt"]["bins"][0].update(p_td=0.1, p_muff=0.2)
    st = decide.prepare(BASE, {})
    assert decide.wp_punt(m, st, {})[0] == pytest.approx(0.8 * S_1 + 0.2 * S1, abs=1e-12)


def test_toggles_off_mean_neutral_environment():
    """Weather off -> wind 0, room temperature, no precipitation."""
    e = decide.env_features({"wind": 30, "temp": 10, "precip": 1}, {})
    assert e == {"wind": 0.0, "cold": 0.0, "precip": 0, "indoor": 0, "altitude": 0.0}
    e = decide.env_features({"wind": 30, "temp": 10, "precip": 1}, {"weather": True})
    assert e["wind"] == 3.0 and e["cold"] == 4.0 and e["precip"] == 1
    # indoors cancels weather
    e = decide.env_features({"wind": 30, "temp": 10, "precip": 1, "indoor": 1},
                            {"weather": True, "stadium": True})
    assert e["wind"] == 0.0 and e["cold"] == 0.0 and e["precip"] == 0


# ---------------------------------------------------------------- early downs
def test_early_down_kicks_when_clock_runs_out():
    """3rd & 10 at the 20, Q4, 3 s left, down 2, no timeouts. Every play gains 5
    (short of the line) and takes 5 s. A spike would turn 4th into a 5th down, so
    it is not allowed: the clock runs out, game over down 2 -> 0.
    FG: 0.75 (make wins, miss loses). No punt on an early down."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, down=3, ydstogo=10, score_diff=-2, half_seconds=3, pos_to=0))
    assert out["wp"]["go"] == 0.0
    assert out["wp"]["fg"] == pytest.approx(0.75)
    assert out["wp"]["punt"] is None
    assert out["best"] == "fg"


def test_early_down_uses_a_timeout():
    """Same, with one timeout: the play then costs only 2 s (timeout_play), so 1 s
    is left and it is our 3rd & 5 at the 15, down 2 -> stub logit -1 -> S_1."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, down=2, ydstogo=10, score_diff=-2, half_seconds=3, pos_to=1))
    assert out["wp"]["go"] == pytest.approx(S_1)


def test_early_down_spike_when_out_of_timeouts():
    """2nd & 10 at the 20, 3 s left, down 2, no timeouts. The play would run out
    the clock, so the team spikes: 2.5 s (spike_total) leaves 0.5 s, and the spike
    costs a down -> our 4th & 5 at the 15, down 2 -> stub logit -1 -> S_1."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, down=2, ydstogo=10, score_diff=-2, half_seconds=3, pos_to=0))
    assert out["wp"]["go"] == pytest.approx(S_1)


def test_early_down_midgame_play_beats_kick():
    """2nd & 10 at the 20, 10:00 left, tied. Play: our 3rd & 5, tied -> S1.
    FG: 0.75 * S1 + 0.25 * S_1 = 0.6155 < S1, so run a play."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    out = decide.decide(m, dict(BASE, down=2, ydstogo=10))
    assert out["wp"]["go"] == pytest.approx(S1)
    assert out["best"] == "go"


def test_early_down_turnover():
    """2nd down turnover rate 0.1: 0.9 * S1 + 0.1 * (their ball, tied -> S_1)."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["play"]["p_turnover"] = [0.0, 0.1, 0.0]
    out = decide.decide(m, dict(BASE, down=2, ydstogo=10))
    assert out["wp"]["go"] == pytest.approx(0.9 * S1 + 0.1 * S_1)


# ---------------------------------------------------------------- fair-catch kick
def test_fair_catch_kick_after_last_punt():
    """We lead by 2, 3 s left, 4th down, we punt; every punt is fair-caught at
    their 50. The clock runs out, but a fair catch gives them an untimed free kick:
    distance 50 + 10 = 60 yd, P(make) = 0.75 (stub). If it is good they lead by 1.
    Value = 0.75 * 0 + 0.25 * 1 = 0.25. Without fair catches the half just ends: 1.0."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["punt"]["bins"][0].update(q=[50.0], p_fc=1.0)
    st = decide.prepare(dict(BASE, score_diff=2, half_seconds=3), {})
    assert decide.wp_punt(m, st, {})[0] == pytest.approx(0.25)
    m["punt"]["bins"][0]["p_fc"] = 0.0
    assert decide.wp_punt(m, st, {})[0] == pytest.approx(1.0)


def test_fair_catch_kick_out_of_range():
    """Caught at their 65: a 75-yd free kick is past the 70-yd limit, so no threat."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["punt"]["bins"][0].update(q=[65.0], p_fc=1.0)
    st = decide.prepare(dict(BASE, score_diff=2, half_seconds=3), {})
    assert decide.wp_punt(m, st, {})[0] == pytest.approx(1.0)


# ---------------------------------------------------------------- v1.1: overtime, tries, 4th & 1
def test_overtime_value_by_team_strength():
    """Tie at the end of regulation. OT slope 0.7 per 10 points, ties 10%.
    Even teams: 0.5. Favored by 10: 0.5 + 0.9 * (sigmoid(0.7) - 0.5)
    = 0.5 + 0.9 * 0.1681878 = 0.6513690."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["ot"] = {"slope": 0.7, "p_tie": 0.1}
    st = decide.prepare(dict(BASE, half_seconds=3), {})
    assert decide.value_after(m, st, True, 0, 50, 5) == pytest.approx(0.5)
    st = decide.prepare(dict(BASE, half_seconds=3, spread=10.0), {"spread": True})
    assert decide.value_after(m, st, True, 0, 50, 5) == pytest.approx(0.5 + 0.9 * (1 / (1 + math.exp(-0.7)) - 0.5))


def test_touchdown_takes_the_better_try():
    """Down 8, 3 s left: a touchdown ends the game. Extra point (95%) leaves us
    down 1 -> 0. Two-point try (48%) ties -> 0.5 (no OT model). Value of the
    touchdown = max(0, 0.48 * 0.5) = 0.24, so the team goes for two."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["tries"] = {"pat": 0.95, "two": 0.48}
    st = decide.prepare(dict(BASE, half_seconds=3, score_diff=-8), {})
    assert decide.touchdown_value(m, st, True, -8, 5) == pytest.approx(0.24)


def test_opponent_touchdown_takes_their_better_try():
    """We lead by 7, 3 s left, they return a punt for a TD: down 1 after 6, they
    pick the try that is worst for us. PAT (95%) ties: 0.95 * 0.5 + 0.05 * 1 = 0.525.
    Two (48%) wins for them: 0.48 * 0 + 0.52 * 1 = 0.52. They go for two -> 0.52."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["tries"] = {"pat": 0.95, "two": 0.48}
    st = decide.prepare(dict(BASE, half_seconds=3, score_diff=7), {})
    assert decide.touchdown_value(m, st, False, 7, 5) == pytest.approx(0.52)


def test_fourth_and_inches_distance():
    """Recorded 4th & 1, average true distance 0.85. Inches (0.35) -> the model
    sees 0.5 yd; a full yard (1.0) -> 1.15 yd; unknown -> 1."""
    m = make_stub(0, -1.0, -1.0, 1.0)
    m["rules"]["short_yardage"] = {"mean_true": 0.85, "inches": 0.35, "full_yard": 1.0, "went": 0.7, "kicked": 0.98}
    assert decide.conv_distance(m, {"ydstogo": 1, "short": "inches"}) == pytest.approx(0.5)
    assert decide.conv_distance(m, {"ydstogo": 1, "short": "full_yard"}) == pytest.approx(1.15)
    assert decide.conv_distance(m, {"ydstogo": 1}) == 1
    assert decide.conv_distance(m, {"ydstogo": 2, "short": "inches"}) == 2


def test_kickoff_spot_follows_the_state():
    """A made field goal in 2015 (touchback at the 20: opponent starts at yardline
    78) must use that spot, not today's. Stub WP on yardline (index 4): <= 75 -> +1,
    else -1, for the team with the ball. 2015 spot 78 -> their -1 -> our S1.
    Current spot 75 (stub default) -> their +1 -> our S_1. P(make) = 0.75, miss
    at the 20 -> their spot 73 -> their +1 -> our S_1."""
    m = make_stub(4, 75.0, 1.0, -1.0)
    st = decide.prepare(dict(BASE, yardline=20), {})
    old = decide.prepare(dict(BASE, yardline=20, kickoff_start=78.0), {})
    assert decide.wp_fg(m, old, {})[0] == pytest.approx(0.75 * S1 + 0.25 * S_1)
    assert decide.wp_fg(m, st, {})[0] == pytest.approx(S_1)
