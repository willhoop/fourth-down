// Live game: turn one game from ESPN's public NFL scoreboard into form values.
// The feed is unofficial and can change, so every field is optional: anything
// missing comes back undefined and the form keeps its value. Browsers may only
// read the site.web.api.espn.com host: site.api.espn.com sends no CORS header to
// browsers (it does to curl), so pages on other sites are blocked from it.
// tests/test_live.py runs this file against a saved copy of the real feed.
(function (root) {
  const ESPN_URL = "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard";
  const RENAME = { WSH: "WAS", LAR: "LA" };            // ESPN code -> nflverse code
  const code = (a) => RENAME[a] || a;

  function games(feed) {
    const order = { in: 0, pre: 1, post: 2 };
    return (feed.events || []).map((e) => {
      const c = e.competitions[0], st = (c.status || {}).type || {};
      return { id: e.id, name: e.shortName, state: st.state, detail: st.shortDetail, c };
    }).sort((a, b) => (order[a.state] ?? 3) - (order[b.state] ?? 3));
  }

  // side: "home" or "away" (which team "we" are)
  function fill(game, side) {
    const c = game.c, other = side === "home" ? "away" : "home";
    const us = c.competitors.find((x) => x.homeAway === side);
    const them = c.competitors.find((x) => x.homeAway === other);
    const ours = code(us.team.abbreviation), theirs = code(them.team.abbreviation);
    const out = { our: ours, their: theirs, home: side === "home", state: game.state };
    if (c.venue && typeof c.venue.indoor === "boolean") out.indoor = c.venue.indoor;
    // betting line such as "DAL -8.5": the named team is favored by 8.5.
    // Returned in betting convention for us: negative = we are favored.
    const det = ((c.odds || [])[0] || {}).details;
    if (det) {
      const m = String(det).match(/^([A-Z]{2,3})\s+([-+]?\d+(?:\.\d+)?)$/);
      if (m) out.line = code(m[1]) === ours ? -Math.abs(+m[2]) : Math.abs(+m[2]);
      else if (/^(EVEN|PK|PICK)/i.test(det)) out.line = 0;
    }
    if (game.state !== "in") return out;
    out.usScore = +us.score || 0;
    out.themScore = +them.score || 0;
    const per = c.status.period, clk = String(c.status.displayClock || "").split(":");
    if (per >= 1 && per <= 4) out.qtr = per;
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

  const api = { ESPN_URL, games, fill, code };
  if (typeof module !== "undefined") module.exports = api;
  else root.Live = api;
})(this);
