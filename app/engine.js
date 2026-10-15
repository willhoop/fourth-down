// Fourth-down decision engine. A line-for-line port of engine/decide.py.
// tests/parity.js checks both give the same numbers on the shipped model.
(function (root) {
  const WP_FEATURES = ["score_diff", "game_seconds", "half_seconds", "second_half",
    "yardline", "down", "ydstogo", "pos_to", "def_to",
    "tmw_pending", "receive_2h", "spread", "home"];
  // Derived inside wpRaw (nflfastR's engineered terms, Baldwin 2021).

  const sigmoid = (z) => 1 / (1 + Math.exp(-z));

  function treeValue(tree, x) {
    let i = 0;
    for (;;) {
      const n = tree[i];
      if (n[5]) return n[4];
      i = x[n[0]] <= n[1] ? n[2] : n[3];
    }
  }

  // home = 0.5 is a neutral site: the average of the home and away predictions.
  function wpRaw(model, s) {
    if (s.home === 0.5) {
      return 0.5 * (wpRaw(model, Object.assign({}, s, { home: 1 })) + wpRaw(model, Object.assign({}, s, { home: 0 })));
    }
    const e4 = Math.exp(-4 * (3600 - s.game_seconds) / 3600);
    const x = WP_FEATURES.map((k) => s[k]).concat([s.spread * e4, s.score_diff / e4]);
    let z = model.wp.baseline;
    for (const t of model.wp.trees) z += treeValue(t, x);
    return sigmoid(z);
  }

  function logistic(m, f) {
    let z = m.intercept;
    m.names.forEach((n, i) => { z += m.coef[i] * f[n]; });
    return sigmoid(z);
  }

  function envFeatures(st, tog) {
    const indoor = tog.stadium && st.indoor ? 1 : 0;
    const alt = tog.stadium ? (st.altitude_kft || 0) : 0;
    let wind = 0, temp = 70, precip = 0;
    if (tog.weather && !indoor) {
      wind = st.wind ?? 0; temp = st.temp ?? 60; precip = st.precip ?? 0;
    }
    return { wind: wind / 10, cold: Math.max(0, 50 - temp) / 10, precip, indoor, altitude: alt };
  }

  function comboKey(tog) {
    const p = ["weather", "stadium"].filter((k) => tog[k]);
    return p.length ? p.join("+") : "base";
  }

  // Distance the conversion model sees. On a recorded 4th & 1, "short" can say how
  // far it really is (Lopez 2020): inches, a full yard, or the went/kicked averages.
  function convDistance(model, st) {
    const sy = model.rules.short_yardage;
    if (st.ydstogo === 1 && sy && st.short !== undefined && st.short in sy) return 1 + sy[st.short] - sy.mean_true;
    return st.ydstogo;
  }

  function pConvert(model, st, tog) {
    const togo = st.ydstogo, yl = st.yardline;
    const d = convDistance(model, st);
    const f = { is4: 1, togo: Math.min(d, 20) / 10, logtogo: Math.log(d),
      is4_1: togo === 1 ? 1 : 0, is4_23: togo >= 2 && togo <= 3 ? 1 : 0, is4_logtogo: Math.log(d),
      goal: togo >= yl ? 1 : 0, inside10: yl <= 10 ? 1 : 0,
      rz: (yl >= 11 && yl <= 20 && togo < yl) ? 1 : 0,
      spread: tog.spread ? (st.spread || 0) / 10 : 0 };
    return logistic(model.conv[tog.spread ? "spread" : "base"], f);
  }

  function pFieldGoal(model, st, tog) {
    const d = st.yardline + model.rules.fg_distance_add;
    const e = envFeatures(st, tog);
    const f = { dist: d / 10, dist2: (d / 10) ** 2, year: (model.rules.season - 2014) / 10,
      era20: model.rules.season >= 2020 ? 1 : 0,
      wind: e.wind, wind_x_dist: e.wind * d / 10, cold: e.cold, precip: e.precip,
      indoor: e.indoor, altitude: e.altitude,
      long: Math.max(0, d - (model.rules.fg_long_from !== undefined ? model.rules.fg_long_from : 999)) / 10 };
    const m = model.fg.models[comboKey(tog)];
    let z = m.intercept;
    m.names.forEach((n, i) => { z += m.coef[i] * f[n]; });
    // accuracy shifts the curve; range tilts it around 40 yards
    if (tog.kicker) z += (st.kicker_a || 0) + (st.kicker_b || 0) * (d - 40) / 10;
    return sigmoid(z);
  }

  function puntBin(model, yl) {
    for (const c of model.punt.bins) if (c.lo <= yl && yl <= c.hi) return c;
    return model.punt.bins[model.punt.bins.length - 1];
  }

  function puntSpots(model, st, tog) {
    const b = puntBin(model, st.yardline);
    let shift = 0;
    const key = comboKey(tog);
    if (key !== "base") {
      const e = envFeatures(st, tog), adj = model.punt.adj[key];
      adj.names.forEach((n, i) => { shift += adj.coef[i] * e[n]; });
    }
    return b.q.map((q) => Math.min(99, Math.max(1, q + shift)));
  }

  function togoBucket(model, togo) {
    const edges = model.gain.edges;
    let i = 0;
    for (let j = 0; j < edges.length - 1; j++) if (togo >= edges[j]) i = j;
    return i;
  }

  const elapsed = (model, kind, hs) => model.clock[kind][hs <= 120 ? 1 : 0];

  function valueAfter(model, st, usBall, sdUs, yardline, secs, togo, down, posTo) {
    if (st.ot) return otValueAfter(model, st, usBall, sdUs, yardline, secs);
    const ourTo = posTo === undefined ? st.pos_to : posTo;
    const hs = st.half_seconds, tmw = st.tmw_pending;
    let hsNew, tmwNew;
    if (tmw && hs - secs < 120) { hsNew = 120; tmwNew = 0; }
    else { hsNew = hs - secs; tmwNew = hs - secs > 120 ? tmw : 0; }
    if (hsNew <= 0) {
      if (st.second_half) return sdUs > 0 ? 1 : (sdUs < 0 ? 0 : otValue(model, st));
      const usRecv = st.receive_2h === 1;
      const s2 = { score_diff: usRecv ? sdUs : -sdUs, game_seconds: 1800, half_seconds: 1800,
        second_half: 1, yardline: kickoffSpot(model, st), down: 1, ydstogo: 10, pos_to: 3, def_to: 3,
        tmw_pending: 1, receive_2h: 0, spread: st.spread_used * (usRecv ? 1 : -1),
        home: usRecv ? st.home : 1 - st.home };
      const p = wpRaw(model, s2);
      return usRecv ? p : 1 - p;
    }
    const gs = hsNew + (st.second_half ? 0 : 1800);
    const yl = Math.min(99, Math.max(1, yardline));
    const s = { score_diff: usBall ? sdUs : -sdUs, game_seconds: gs, half_seconds: hsNew,
      second_half: st.second_half, yardline: yl, down: down === undefined ? 1 : down,
      ydstogo: togo !== undefined && togo !== null ? togo : Math.min(10, yl),
      pos_to: usBall ? ourTo : st.def_to, def_to: usBall ? st.def_to : ourTo,
      tmw_pending: tmwNew,
      receive_2h: st.second_half ? 0 : (usBall ? st.receive_2h : 1 - st.receive_2h),
      spread: usBall ? st.spread_used : -st.spread_used, home: usBall ? st.home : 1 - st.home };
    const p = wpRaw(model, s);
    return usBall ? p : 1 - p;
  }

  // Where the receiving team starts after a kickoff: the state's own season if the
  // grader set it (touchbacks moved in 2016, 2024 and 2025), else current rules.
  const kickoffSpot = (model, st) => (st.kickoff_start !== undefined ? st.kickoff_start : model.kickoff_start);

  // Our chance from a tie at the end of regulation: both teams get the ball in
  // overtime, so 0.5 plus the better team's measured edge. A tied overtime
  // (regular season only) is worth st.tie_value (default half a win).
  function otValue(model, st) {
    const ot = model.ot;
    if (!ot) return 0.5;
    const edge = sigmoid(ot.slope * st.spread_used / 10) - 0.5;
    const pTie = st.playoffs ? 0 : ot.p_tie;
    return (1 - pTie) * (0.5 + edge) + pTie * (st.tie_value !== undefined ? st.tie_value : 0.5);
  }

  // After a score the scorer kicks off. A trailing kicker may declare an onside
  // kick, recovered at its season's measured rate; it takes whichever is better
  // for it. Not in overtime: a team that scores there leads or is tied.
  function kickAfter(model, st, kickerUs, sdUs, secs) {
    const normal = valueAfter(model, st, !kickerUs, sdUs, kickoffSpot(model, st), secs);
    const o = model.onside;
    const trailing = kickerUs ? sdUs < 0 : sdUs > 0;
    if (!o || !trailing || st.ot) return normal;
    const p = st.onside_rate !== undefined ? st.onside_rate : o.rate;
    const onside = p * valueAfter(model, st, kickerUs, sdUs, o.recovered_yl, secs)
      + (1 - p) * valueAfter(model, st, !kickerUs, sdUs, o.lost_yl, secs);
    return kickerUs ? Math.max(normal, onside) : Math.min(normal, onside);
  }

  // ---------- overtime (mirrors engine/decide.py): both teams get the ball; the
  // first team plays for a lead, the other answers once, then the next score
  // wins. Each function returns the value for the team with the ball.
  const otTie = (st, us) => { const u = st.tie_value !== undefined ? st.tie_value : 0.5; return us ? u : 1 - u; };
  function otPossessions(model, st, secsLeft) {
    const t = model.ot_drive;
    if (st.playoffs) return t.max_possessions;
    return secsLeft <= 0 ? 0 : Math.min(t.max_possessions, Math.floor(secsLeft / t.poss_secs) + 1);
  }
  function otDrive(model, yl) {
    const t = model.ot_drive;
    const i = Math.min(t.td.length - 1, Math.max(0, Math.floor((yl - 1) / t.bin)));
    return [t.td[i], t.fg[i]];
  }
  function otSudden(model, st, us, yl, k) {
    if (k <= 0) return otTie(st, us);
    const [td, fg] = otDrive(model, yl);
    return td + fg + (1 - td - fg) * (1 - otSudden(model, st, !us, model.ot_drive.next_start, k - 1));
  }
  function otAnswer(model, st, us, m, yl, k) {
    if (k <= 0) return 0;
    const [td, fg] = otDrive(model, yl);
    const tries = model.tries || { pat: 1, two: 0 };
    const tied = 1 - otSudden(model, st, !us, kickoffSpot(model, st), k - 1);
    const vTd = m <= 6 ? 1 : (m === 7 ? Math.max(tries.two, tries.pat * tied) : tries.two * tied);
    const vFg = m < 3 ? 1 : (m === 3 ? tied : 0);
    return td * vTd + fg * vFg;
  }
  function otFirst(model, st, us, yl, k) {
    if (k <= 0) return otTie(st, us);
    const [td, fg] = otDrive(model, yl);
    const ko = kickoffSpot(model, st);
    return td * (1 - otAnswer(model, st, !us, 7, ko, k - 1))
      + fg * (1 - otAnswer(model, st, !us, 3, ko, k - 1))
      + (1 - td - fg) * (1 - otSudden(model, st, !us, model.ot_drive.next_start, k - 1));
  }
  function otValueAfter(model, st, usBall, sdUs, yardline, secs) {
    const k = otPossessions(model, st, st.half_seconds - secs);
    const yl = Math.min(99, Math.max(1, yardline));
    if (k <= 0 || (sdUs !== 0 && st.ot_phase === "sudden")) return sdUs > 0 ? 1 : (sdUs < 0 ? 0 : otTie(st, true));
    if (st.ot_phase === "answer") {
      if (sdUs > 0) return 1;
      if (sdUs < 0) return usBall ? otAnswer(model, st, true, -sdUs, yl, k) : 0;
      return usBall ? otSudden(model, st, true, yl, k) : 1 - otSudden(model, st, false, yl, k);
    }
    if (st.ot_phase === "first") {
      if (sdUs > 0) return usBall ? 1 : 1 - otAnswer(model, st, false, sdUs, yl, k);
      if (sdUs < 0) return 0;
      return usBall ? otFirst(model, st, true, yl, k) : 1 - otSudden(model, st, false, yl, k);
    }
    return usBall ? otSudden(model, st, true, yl, k) : 1 - otSudden(model, st, false, yl, k);
  }

  // After a touchdown: 6 points, then the scorer takes the extra point or the
  // 2-point try, whichever is better for the scorer.
  function touchdownValue(model, st, usScored, sdBefore, secs) {
    const tries = model.tries || { pat: 1, two: 0 };
    const sign = usScored ? 1 : -1;
    const after = (extra) => kickAfter(model, st, usScored, sdBefore + sign * (model.rules.td_points + extra), secs);
    const v0 = after(0), v1 = after(1), v2 = after(2);
    const pat = tries.pat * v1 + (1 - tries.pat) * v0;
    const two = tries.two * v2 + (1 - tries.two) * v0;
    return usScored ? Math.max(pat, two) : Math.min(pat, two);
  }

  function prepare(state, tog) {
    const s = Object.assign({}, state);
    s.second_half = s.qtr >= 3 ? 1 : 0;
    s.tmw_pending = s.half_seconds > 120 ? 1 : 0;
    if (tog.spread) s.spread_used = s.spread || 0;
    else {
      // even teams: only home-field advantage (carried in the state so the
      // bootstrap replicates use the same value as the shipped model)
      const edge = s.home_edge || 0;
      s.spread_used = s.home === 1 ? edge : (s.home === 0 ? -edge : 0);
    }
    s.down = s.down === undefined ? 4 : s.down;
    if (s.second_half) s.receive_2h = 0;
    if (s.qtr >= 5) {
      // overtime: our phase follows from the score and whether this is the
      // first possession (state.ot_first, asked only when tied)
      s.ot = 1;
      s.tmw_pending = 0;
      s.ot_phase = s.score_diff < 0 ? "answer" : (s.score_diff === 0 && s.ot_first ? "first" : "sudden");
    }
    return s;
  }

  function wpGo(model, st, tog) {
    const yl = st.yardline, sd = st.score_diff, hs = st.half_seconds;
    const pc = pConvert(model, st, tog);
    const b = togoBucket(model, st.ydstogo);
    const gains = model.gain.success_q[b];
    let succ = 0;
    for (let g of gains) {
      g = Math.max(g, st.ydstogo);
      if (g >= yl) succ += touchdownValue(model, st, true, sd, elapsed(model, "score", hs));
      else succ += valueAfter(model, st, true, sd, yl - g, elapsed(model, "go_success", hs));
    }
    succ /= gains.length;
    const failSpot = 100 - (yl - model.gain.fail_mean[b]);
    const fail = valueAfter(model, st, false, sd, failSpot, elapsed(model, "go_fail", hs));
    return [pc * succ + (1 - pc) * fail, { p_convert: pc, wp_if_convert: succ, wp_if_fail: fail }];
  }

  // 1st-3rd down: run one more play, then value where it leaves us.
  function wpPlay(model, st, tog) {
    const yl = st.yardline, sd = st.score_diff, hs = st.half_seconds, dn = st.down, togo = st.ydstogo;
    const b = togoBucket(model, togo);
    const gains = model.play.gain_q[dn - 1][b];
    const pTo = model.play.p_turnover[dn - 1];
    const first = [], short = [];
    for (const g of gains) {
      if (g >= yl) {
        first.push(touchdownValue(model, st, true, sd, elapsed(model, "score", hs)));
        continue;
      }
      const made = g >= togo;
      let secs = elapsed(model, made ? "play_first" : "play_short", hs);
      let to = st.pos_to;
      let nd = made ? 1 : dn + 1;
      if (hs - secs <= 0) {
        // the clock would run out: call a timeout, or else spike the ball
        // (costs a down; allowed while it leaves at least 4th down)
        if (to > 0) { secs = model.clock.timeout_play; to = to - 1; }
        else if (nd + 1 <= 4) { secs = model.clock.spike_total; nd = nd + 1; }
      }
      const newYl = yl - g;
      if (made) first.push(valueAfter(model, st, true, sd, newYl, secs, undefined, nd, to));
      else {
        const nt = Math.min(Math.max(togo - g, 1), Math.min(99, Math.max(1, newYl)));
        short.push(valueAfter(model, st, true, sd, newYl, secs, nt, nd, to));
      }
    }
    const tov = valueAfter(model, st, false, sd, 100 - yl, elapsed(model, "go_fail", hs));
    const n = gains.length, sum = (a) => a.reduce((x, y) => x + y, 0);
    const v = (1 - pTo) * (sum(first) + sum(short)) / n + pTo * tov;
    const pFirst = (1 - pTo) * first.length / n;
    return [v, { p_convert: pFirst,
      wp_if_convert: first.length ? sum(first) / first.length : null,
      wp_if_fail: pFirst < 1 ? ((1 - pTo) * sum(short) / n + pTo * tov) / (1 - pFirst) : null,
      p_turnover: pTo }];
  }

  function wpFg(model, st, tog) {
    const yl = st.yardline, sd = st.score_diff, hs = st.half_seconds, r = model.rules;
    if (yl + r.fg_distance_add > r.fg_max_distance) {
      return [null, { p_make: 0, distance: yl + r.fg_distance_add, out_of_range: true }];
    }
    const pm = pFieldGoal(model, st, tog);
    const make = kickAfter(model, st, true, sd + 3, elapsed(model, "fg", hs));
    const spot = yl + r.fg_snap_to_spot;
    const oppYl = spot <= r.missed_fg_min_spot ? 80 : 100 - spot;
    const miss = valueAfter(model, st, false, sd, oppYl, elapsed(model, "fg", hs));
    return [pm * make + (1 - pm) * miss, { p_make: pm, wp_if_make: make, wp_if_miss: miss,
      distance: yl + r.fg_distance_add }];
  }

  function wpPunt(model, st, tog) {
    const spots = puntSpots(model, st, tog);
    const b = puntBin(model, st.yardline);
    const hs = st.half_seconds;
    const secs = elapsed(model, "punt", hs);
    const sd = st.score_diff, r = model.rules;
    // Fair-catch kick (Rule 11-4-3): late in a half, a fair catch lets them try a
    // free-kick field goal from the catch spot (distance = spot + 10, no rush),
    // untimed if the punt ran out the clock. They take it when it beats playing on.
    const fcSecs = model.clock.punt_fair_catch[hs <= 120 ? 1 : 0];
    const window = hs - fcSecs <= r.fair_catch_kick_window;
    const end = (s_) => valueAfter(model, st, false, s_, 50, hs + 1);   // the half ends
    let fckRisk = 0;
    const spotValue = (y) => {
      const vN = valueAfter(model, st, false, sd, y, secs);
      if (!window || y + 10 > r.fg_max_distance) return vN;
      // their kick, our weather and stadium, a league-average kicker
      const pm = pFieldGoal(model, Object.assign({}, st, { yardline: y - r.fg_distance_add + 10 }),
        Object.assign({}, tog, { kicker: false }));
      const vFck = pm * end(sd - 3) + (1 - pm) * end(sd);
      const vPlayOn = valueAfter(model, st, false, sd, y, fcSecs);
      if (vFck < vPlayOn) fckRisk += b.p_fc * pm / spots.length;
      const vFc = Math.min(vPlayOn, vFck);
      return (1 - b.p_fc) * vN + b.p_fc * vFc;
    };
    let normal = 0;
    for (const y of spots) normal += spotValue(y);
    normal /= spots.length;
    // return touchdown: they score 7, we receive the kickoff
    const td = touchdownValue(model, st, false, sd, secs);
    // muff recovered by us: our ball at the recovery spot
    const muff = valueAfter(model, st, true, sd, b.muff_spot, secs);
    const v = (1 - b.p_td - b.p_muff) * normal + b.p_td * td + b.p_muff * muff;
    return [v, { opp_yardline_mean: spots.reduce((a, c) => a + c, 0) / spots.length,
      p_return_td: b.p_td, p_muff: b.p_muff, fair_catch_kick_risk: fckRisk }];
  }

  function decide(model, state, toggles) {
    const tog = toggles || {};
    const st = prepare(state, tog);
    let go, gd, pu, pd;
    if (st.down < 4) { [go, gd] = wpPlay(model, st, tog); pu = null; pd = {}; }   // early down: play or kick; nobody punts
    else { [go, gd] = wpGo(model, st, tog); [pu, pd] = wpPunt(model, st, tog); }
    const [fg, fd] = wpFg(model, st, tog);
    const wp = { go, fg, punt: pu };
    const ranked = Object.keys(wp).filter((k) => wp[k] !== null).sort((a, b) => wp[b] - wp[a]);
    const margin = ranked.length > 1 ? wp[ranked[0]] - wp[ranked[1]] : 1;
    return { wp, best: ranked[0], margin, tossup: margin < model.rules.tossup_margin,
      detail: { go: gd, fg: fd, punt: pd } };
  }

  const api = { decide, wpRaw, pConvert, pFieldGoal, puntSpots, valueAfter, prepare, WP_FEATURES };
  if (typeof module !== "undefined") module.exports = api;
  else root.FourthDown = api;
})(this);
