// Scores every graded 4th down twice: the coach's call and the engine's call.
// Input:  argv[2] (a chunk of decisions written by engine/grade_coaches.py)
// Output: argv[3]. The grader runs one process per CPU core on separate chunks.
// Run by engine/grade_coaches.py; not meant to be run on its own.
const fs = require("fs");
const path = require("path");
const ROOT = path.join(__dirname, "..");
const MODEL = require(path.join(ROOT, "app", "model.js"));
const E = require(path.join(ROOT, "app", "engine.js"));

const BOOT = require(path.join(ROOT, "app", "bootstrap.js"));
const inp = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const tog = inp.toggles;
const out = [];
for (const d of inp.decisions) {
  const r = E.decide(MODEL, d.state, tog);
  // realized: what actually happened, valued by the same WP model
  let realized;
  if (d.next === null) realized = d.final;
  else {
    const p = E.wpRaw(MODEL, d.next);
    realized = d.next_same_team ? p : 1 - p;
  }
  // Share of replicate models in which the coach's call was NOT the best option.
  let wrong = 0;
  for (const rep of BOOT) {
    const rb = E.decide(rep, d.state, tog);
    if (rb.best !== d.choice) wrong += 1;
  }
  out.push({ id: d.id, best: r.best, margin: r.margin, tossup: r.tossup, conf_wrong: wrong / BOOT.length,
    wp_go: r.wp.go, wp_fg: r.wp.fg, wp_punt: r.wp.punt,
    p_convert: r.detail.go.p_convert, p_make: r.detail.fg.p_make, realized });
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
console.log(`scored ${out.length} decisions`);
