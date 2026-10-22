// Live game: turn one game from ESPN's public NFL scoreboard into form values.
// The feed is unofficial and can change, so every field is optional: anything
// missing comes back undefined and the form keeps its value. Browsers may only
// read the site.web.api.espn.com host: site.api.espn.com sends no CORS header to
// browsers (it does to curl), so pages on other sites are blocked from it.
// tests/test_live.py runs this file against a saved copy of the real feed.
(function (root) {
  const ESPN_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard";
  const ESPN_SUMMARY = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=";
  const RENAME = { WSH: "WAS", LAR: "LA" };            // ESPN code -> nflverse code
  const code = (a) => RENAME[a] || a;

  // "DAL -8.5": DAL favored by 8.5. Returned for team `ours`: negative = ours favored.
  function parseLine(det, ours) {
    if (!det) return undefined;
    const m = String(det).trim().match(/^([A-Z]{2,3})\s+([-+]?\d+(?:\.\d+)?)$/);
    if (m) return code(m[1]) === ours ? -Math.abs(+m[2]) : Math.abs(+m[2]);
    if (/^(EVEN|PK|PICK)/i.test(String(det).trim())) return 0;
    return undefined;
  }
  // the summary feed for one game: the first sportsbook line that parses
  function lineFromSummary(sum, ours) {
    for (const p of (sum && sum.pickcenter) || []) {
      const v = parseLine(p.details, ours);
      if (v !== undefined) return v;
    }
    return undefined;
  }

  function games(feed) {
    const order = { in: 0, pre: 1, post: 2 };
    return (feed.events || []).map((e) => {
      const c = e.competitions[0], st = (c.status || {}).type || {};
      return { id: e.id, name: e.shortName, state: st.state, detail: st.shortDetail, c,
        playoffs: ((e.season || {}).type === 3) };      // ESPN season type 3 = postseason
    }).sort((a, b) => (order[a.state] ?? 3) - (order[b.state] ?? 3));
  }

  // side: "home" or "away" (which team "we" are)
  function fill(game, side) {
    const c = game.c, other = side === "home" ? "away" : "home";
    const us = c.competitors.find((x) => x.homeAway === side);
    const them = c.competitors.find((x) => x.homeAway === other);
    const ours = code(us.team.abbreviation), theirs = code(them.team.abbreviation);
    const out = { our: ours, their: theirs, home: side === "home", state: game.state, playoffs: !!game.playoffs };
    if (c.venue && typeof c.venue.indoor === "boolean") out.indoor = c.venue.indoor;
    if (c.neutralSite === true) out.neutral = true;       // London, Mexico City, the Super Bowl
    // betting line such as "DAL -8.5": the named team is favored by 8.5.
    // Returned in betting convention for us: negative = we are favored.
    const line = parseLine(((c.odds || [])[0] || {}).details, ours);
    if (line !== undefined) out.line = line;
    if (game.state !== "in") return out;
    out.usScore = +us.score || 0;
    out.themScore = +them.score || 0;
    const per = c.status.period, clk = String(c.status.displayClock || "").split(":");
    if (per >= 1) out.qtr = Math.min(per, 5);           // 5 = overtime (any OT period)
    if (clk.length === 2) { out.mm = +clk[0]; out.ss = +clk[1]; }
    const s = c.situation || {};
    if (s.down >= 1 && s.down <= 4) out.down = s.down;
    if (s.distance > 0) out.togo = s.distance;
    // "DAL 35" = the DAL 35-yard line; midfield is "50"
    const pm = String(s.possessionText || "").match(/(?:([A-Z]{2,3})\s+)?(\d{1,2})$/);
    if (pm) {
      out.yd = +pm[2];
      out.ownSide = pm[1] ? code(pm[1]) === ours : false;
    }
    const tUs = side === "home" ? s.homeTimeouts : s.awayTimeouts;
    const tThem = side === "home" ? s.awayTimeouts : s.homeTimeouts;
    if (tUs >= 0 && tUs <= 3) out.pto = tUs;
    if (tThem >= 0 && tThem <= 3) out.dto = tThem;
    if (s.possession !== undefined) out.weHaveBall = String(s.possession) === String(us.team.id);
    return out;
  }

  // ---------- shape check. ESPN's scoreboard is undocumented and has changed
  // before. validate() lists every field this app needs that is missing; an
  // empty list means the feed is usable. The app shows "Live data unavailable"
  // instead of guessing, and tests/test_live.py runs this on a saved real feed.
  function validate(feed) {
    if (!feed || !Array.isArray(feed.events)) return ["events: missing or not a list"];
    const bad = [];
    feed.events.forEach((e, i) => {
      const at = `events[${i}]`, c = e && Array.isArray(e.competitions) ? e.competitions[0] : null;
      if (!e || e.id === undefined) bad.push(`${at}.id: missing`);
      if (!e || typeof e.shortName !== "string") bad.push(`${at}.shortName: missing`);
      if (!c) { bad.push(`${at}.competitions[0]: missing`); return; }
      const st = c.status && c.status.type;
      if (!st || !["pre", "in", "post"].includes(st.state)) bad.push(`${at}.status.type.state: missing or unknown`);
      const cs = Array.isArray(c.competitors) ? c.competitors : [];
      const sides = cs.map((x) => x && x.homeAway).sort().join(",");
      if (sides !== "away,home") bad.push(`${at}.competitors: need one home and one away`);
      cs.forEach((x, j) => {
        if (!x || !x.team || typeof x.team.abbreviation !== "string" || x.team.id === undefined)
          bad.push(`${at}.competitors[${j}].team: needs abbreviation and id`);
      });
      if (st && st.state === "in") {
        if (typeof c.status.period !== "number") bad.push(`${at}.status.period: missing in a live game`);
        if (typeof c.status.displayClock !== "string") bad.push(`${at}.status.displayClock: missing in a live game`);
        const s = c.situation;          // can be absent between plays; when present it must make sense
        if (s && s.down !== undefined && typeof s.down !== "number") bad.push(`${at}.situation.down: not a number`);
        if (s && s.distance !== undefined && typeof s.distance !== "number") bad.push(`${at}.situation.distance: not a number`);
      }
    });
    return bad;
  }

  // ---------- "which game is on the TV?" from the text read off a score bar.
  // Teams are found by abbreviation (ESPN's and ours) or nickname; OCR often
  // reads 0 for O, 1 for I, 5 for S, so letter-like tokens are cleaned first.
  const ALIASES = { LA: ["LAR"], WAS: ["WSH"], JAX: ["JAC"], LV: ["LVR"], NO: ["NOR"], GB: ["GNB"], KC: ["KAN"],
                    NE: ["NWE"], SF: ["SFO"], TB: ["TAM"] };
  // exact: words as read, plus letters split from a glued score ("NE14" -> NE, 14).
  // guessed: digits read as letters (N0 -> NO, T8 -> TB). A guess ranks a game but
  // never makes a match "sure": on a blurry TV, "TEN" read as "T8" must not become TB.
  function tokens(text) {
    const fix = { 0: "O", 1: "I", 5: "S", 8: "B" };
    const exact = new Set(), guessed = new Set();
    for (const w of String(text).toUpperCase().split(/[^A-Z0-9]+/).filter(Boolean)) {
      exact.add(w);
      for (const part of w.match(/[A-Z]+|[0-9]+/g) || []) exact.add(part);
      if (/[A-Z]/.test(w) && /[0158]/.test(w) && /^[A-Z0158]+$/.test(w)) guessed.add(w.replace(/[0158]/g, (d) => fix[d]));
    }
    return { exact: [...exact], guessed: [...guessed].filter((g) => !exact.has(g)) };
  }
  // one wrong, missing or extra letter (OCR reads a logo as "O" or "Q")
  function near(a, b) {
    if (a === b) return true;
    if (Math.abs(a.length - b.length) > 1 || Math.min(a.length, b.length) < 2) return false;
    let i = 0, j = 0, edits = 0;
    while (i < a.length && j < b.length) {
      if (a[i] === b[j]) { i++; j++; continue; }
      if (++edits > 1) return false;
      if (a.length > b.length) i++; else if (b.length > a.length) j++; else { i++; j++; }
    }
    return edits + (a.length - i) + (b.length - j) <= 1;
  }
  function matchGame(text, gameList, names) {
    const tt = tokens(text), tk = new Set(tt.exact), guess = new Set(tt.guessed);
    const tkList = [...tt.exact, ...tt.guessed];
    const words = (cd, espnCode) => [cd, espnCode, ...(ALIASES[cd] || []), (names && names[cd] ? names[cd].toUpperCase() : null)]
      .filter(Boolean);
    const found = (cd, espnCode) => words(cd, espnCode).some((w) => tk.has(w) || (w.length >= 5 && String(text).toUpperCase().includes(w)));
    // close but not exact (3-letter codes only): counts for less and never makes a match "sure"
    const close = (cd, espnCode) => words(cd, espnCode).some((w) => guess.has(w) ||
      (w.length === 3 && tkList.some((x) => /^[A-Z]+$/.test(x) && near(x, w))));
    const scored = gameList.map((g) => {
      const cs = g.c.competitors;
      const hits = cs.filter((x) => found(code(x.team.abbreviation), x.team.abbreviation)).map((x) => code(x.team.abbreviation));
      const fuzzy = cs.filter((x) => !hits.includes(code(x.team.abbreviation)) && close(code(x.team.abbreviation), x.team.abbreviation)).length;
      const nums = cs.filter((x) => x.score !== undefined && x.score !== "" && tk.has(String(+x.score))).length;
      return { game: g, teams: hits, fuzzy, score: hits.length * 10 + fuzzy * 4 + (g.state === "in" ? 3 : 0) + nums };
    }).filter((x) => x.teams.length > 0 || x.fuzzy > 0).sort((a, b) => b.score - a.score);
    if (!scored.length) return null;
    const best = scored[0];
    // sure when both teams were read, or one team and no other game is close
    // sure: both teams read exactly, or one team read exactly and no other game has an exact hit
    const sure = best.teams.length === 2 || (best.teams.length === 1 && !scored.slice(1).some((x) => x.teams.length > 0));
    return { game: best.game, teams: best.teams, sure, candidates: scored.slice(0, 4).map((x) => x.game) };
  }

  const api = { ESPN_URL, ESPN_SUMMARY, games, fill, code, parseLine, lineFromSummary, validate, tokens, near, matchGame };
  if (typeof module !== "undefined") module.exports = api;
  else root.Live = api;
})(this);
