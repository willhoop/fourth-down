// Prices each 4th down's options as gambles for engine/fit_prospect.py:
// the chance of success and the WP after success and after failure.
// Input: argv[2] (a chunk of decisions); output: argv[3]. Not run on its own.
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const MODEL = require(path.join(ROOT, "app", "model.js"));
const E = require(path.join(ROOT, "app", "engine.js"));
const inp = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const out = inp.decisions.map((d) => {
  const r = E.decide(MODEL, d.state, inp.toggles);
  const g = r.detail.go, f = r.detail.fg;
  return { id: d.id, wp_go: r.wp.go, wp_fg: r.wp.fg, wp_punt: r.wp.punt,
    pc: g.p_convert, go_s: g.wp_if_convert, go_f: g.wp_if_fail,
    pm: r.wp.fg === null ? null : f.p_make, fg_s: f.wp_if_make ?? null, fg_f: f.wp_if_miss ?? null };
});
fs.writeFileSync(process.argv[3], JSON.stringify(out));
