# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/),
[Semantic Versioning](https://semver.org/). Newest first. Dates are ISO 8601.

## [1.2.3] — 2026-10-08

### Notes

- Tested and rejected one explanation for the late-game "go" over-prediction
  (risk 14): that defenses stop must-go tries more often. Late 4th downs by
  trailing teams convert 43.7% against 44.6% predicted (n = 1,584; −0.9 ± 1.2
  points), so the conversion model is not the source. Recorded in the risk
  register so it is not chased again.

### Record

- **Measured.** No published figure changed (a new diagnostic in the risk register).
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Fold the risk 14 diagnostics into the white paper.

## [1.2.2] — 2026-10-08

### Changed

- Phone layout for the Coaches and Kickers tabs: compact cards show the grade,
  name, biggest habit and the key number without sideways scrolling, with a
  "Sort by" menu. Coaches without a full season sort to the bottom instead of
  the top. Shorter Coaches intro.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.2.1] — 2026-10-08

### Fixed

- Live game mode could not load on the website. `site.api.espn.com` sends a CORS
  header to command-line tools but not to browsers, so the browser blocked it; a
  curl check had wrongly suggested it would work. The app now reads the same
  scoreboard from `site.web.api.espn.com`, which browsers may read. Verified by
  driving the deployed site in a headless browser.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.2.0] — 2026-10-08

### Fixed

- **Past seasons were graded under today's kickoff rule.** Every post-score
  kickoff used the 2025 starting spot (opponent at its own 31), but the receiving
  team started near its own 22 in 2014–15 and its own 25 in 2016–23. So in older
  seasons the engine handed the opponent 5–8 free yards after every score,
  undervaluing field goals and touchdowns and overstating the case for going. The
  spot is now measured for every season (`kickoff_by_season`) and each graded
  decision uses its own season's spot. Found by checking each option's predicted
  win rate against outcomes by score: field goals when trailing by 4–9 were
  under-predicted by 2.5 ± 1.1 points (now 2.0 ± 1.1).
- This also corrects a fairness problem: the error grew with how far back a
  coach's career goes, so long-tenured coaches were graded more harshly.

### Added

- Live game mode: "Fill from a live game" reads ESPN's public NFL scoreboard and
  fills in the teams, betting line, roof and, during a game, the score, clock,
  down, distance, ball spot and timeouts (`app/live.js`). The feed is unofficial;
  the user checks the form before getting the call. Not available in the private
  Claude copy, which blocks outside data.

### Record

- **Measured.** League confident-mistake cost per team-season and the share of
  clear engine "go" calls (`data/coach_grades.json`); nine coach letter grades;
  the edge check (`data/edge_check.json`).
- **Basis.** unchanged — the same question; the fix removes an error in how past
  seasons were scored.
- **Supersedes.** League cost ~~0.92~~ 0.84 (2014), ~~0.93~~ 0.86 (2016),
  ~~0.71~~ 0.63 (2023); 2025 unchanged at 0.62. Clear go ~~33.1%~~ 30.2% (2014).
  Grades: McCarthy ~~B+~~ A, Quinn ~~B+~~ A, Reid ~~A~~ B+, Moore ~~A~~ B+,
  Canales ~~A~~ B+, Johnson ~~B+~~ B, Morris ~~B+~~ B, Glenn ~~B~~ C+,
  Bowles ~~C~~ C+. Lowest-cost three: ~~Coen, Macdonald, Campbell~~ Coen,
  McDermott, LaFleur. Edge check ~~−0.6~~ −0.5 ± 0.6 WP points.
- **Owed to the next major.** Risk 14 (cost totals above published estimates)
  remains; the residual option biases (field goals trailing by 4–9 +2.0 ± 1.1,
  late going-for-it −2.7 ± 1.3) are the next lead.

## [1.1.0] — 2026-10-08

### Added

- Overtime is valued by team strength. Both teams now get the ball in overtime
  (playoffs since 2022, regular season since 2025), so a tie at the end of
  regulation is worth 0.5 plus the better team's edge, fit on 189 overtime games.
  It was a flat 0.5.
- After a touchdown the scoring team takes the extra point (94.4%) or the 2-point
  try (47.7%), whichever is better for it. A touchdown was a flat 7.
- 4th & 1 precision (Lopez 2020): the app asks "inches / not sure / about a yard",
  and the coach grader judges teams that went at 0.70 yd and teams that kicked at
  0.98 yd.
- "This week" tab: each week's costliest calls and best gutsy calls for the
  current season, refreshed every Tuesday by a scheduled GitHub Action.
- Edge calibration check (`engine/edge_check.py`) and per-decision export
  (`data/decisions.csv.gz`).
- App: matchup picker (fills in stadium and kicker), a one-sentence "why" under
  each call, a "Share this call" link that opens at the same situation,
  install-to-home-screen, and each coach's biggest habit.

### Changed

- 4th-down-by-distance conversion terms were tested and left out: on the same
  1,849 hold-out plays they moved log loss from 0.6424 to 0.6419.

### Notes

- These changes did not close the gap between the engine's league cost totals
  and published estimates (risk 14). The edge check puts goers at -0.6 ± 0.6 WP
  points against the engine's prediction relative to kickers, and -7.4 ± 3.2 in
  the bin where the engine favors going by 8+ points. That bin is the next lead.
- Fixed before release: the first weekly page counted a pick-six as a
  "converted" gutsy call and listed forced last-second attempts as gutsy.

### Record

- **Measured.** League confident-mistake cost per team-season (`data/coach_grades.json`)
  and the share of clear engine "go" calls moved; five coach letter grades moved.
- **Basis.** unchanged — the same question (win probability of each option);
  the overtime, touchdown and 4th & 1 terms refine how it is answered.
- **Supersedes.** 2014 cost ~~0.90~~ 0.92; 2025 cost ~~0.61~~ 0.62; 2025 clear go
  ~~33.7%~~ 34.5%. Grades: Andy Reid ~~B+~~ A, Dan Quinn ~~A~~ B+, Ben Johnson
  ~~B~~ B+, DeMeco Ryans ~~B+~~ B, Shane Steichen ~~C+~~ C.
- **Owed to the next major.** Fold risk 14's resolution into the white paper,
  deck and technical docs once the cost totals are reconciled with published
  estimates.

## [1.0.1] — 2026-10-08

### Added

- The app is published at https://willhoop.github.io/fourth-down/ so it can be
  shared and used on a phone. `.github/workflows/pages.yml` deploys `app/` after
  the tests pass on every push to `main`.

### Changed

- The version test compares the white paper and data stamps at MAJOR.MINOR, the
  same rule as `portfolio/build/check_projects.py`. A PATCH moves no figure, so
  the 1.0.0 data files stay valid.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new. (Risk 14, the cost-total gap against
  published estimates, remains owed.)

## [1.0.0] — 2026-10-08

First release.

### Added

- Decision engine (`engine/decide.py`, `app/engine.js`): go, field goal or punt,
  scored by win probability after each option. Clock runoff, two-minute warning,
  halftime and end of game are modelled.
- Win-probability model: boosted trees on 2014–2025 snaps with monotone
  constraints and nflfastR's spread-fade and score/time terms.
- Conversion model (3rd and 4th downs pooled, red-zone term, defensive-penalty
  first downs), field-goal model (weather, stadium, era), punt model (return TD
  and muff outcomes), all measured from nflverse play-by-play.
- Optional factors with on/off switches: weather, stadium, team strength, kicker.
- Kicker accuracy and range with empirical-Bayes shrinkage; replacement level by
  the nflWAR rule; kicker grades.
- Whole-pipeline bootstrap (20 game-resampled refits) with confidence shown in the
  app.
- Coach grading: every fourth down since 2014 replayed as called and as the engine
  would call it; coaches charged only for confident mistakes.
- Early downs: on 1st–3rd down the engine compares running one more play with
  kicking a field goal now. It looks one play ahead, using measured gains,
  turnovers and clock times, and calls a timeout or spikes the ball when the
  clock would run out.
- Fair-catch kick (Rule 11-4-3) on late punts; drop-kick field goals treated as
  field goals.
- App with Decision, Coaches, Kickers and About tabs; desktop shortcut. Phone-first
  layout, a situation screen with a "Get the call" button and a separate results
  screen, ±1 and ±5 buttons, a betting-line spread input, and a searchable,
  ranked kicker chart.
- White paper, plain-English deck, technical documentation, ADRs 0001–0003, risk
  register, generated validation and grade reports, tests, CI.

### Notes

- Bugs found and fixed during development, before release (risk register 7, 8):
  a NaN kickoff spot in validation that put post-score kickoffs at the 1-yard line,
  and a field-goal curve that rose again past 83 yards. Neither reached a
  published figure.
- A literature review (white paper section 9) led to: bootstrap uncertainty,
  grading only confident mistakes, nflfastR engineered WP terms, punt return TDs
  and muffs, defensive-penalty conversions, and the nflWAR replacement rule.

### Record

- **Measured.** First publication of every figure in the white paper section 7
  and `docs/reports/`, from `data/validation.json`, `data/coach_grades.json` and
  `data/kickers.json`.
- **Basis.** New.
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing.
