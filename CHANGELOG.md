# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/),
[Semantic Versioning](https://semver.org/). Newest first. Dates are ISO 8601.

## [1.3.9] — 2026-10-13

### Added

- **Comparison with nfl4th** (Ben Baldwin, nflverse), the only public 4th-down
  model with per-play numbers: `engine/compare_nfl4th.py`, report
  `docs/reports/nfl4th-comparison.md`. It reads nfl4th's published .rds file
  directly (no R needed). Reason: the user asked how the engine compares with
  public ones.

### Notes

- The comparison found a defect: the field-goal curve gives a 48% make chance
  at 67 yards (risk 17). The engine recommends field goals from 58+ yards on
  1,318 plays and charges 587 confident mistakes there. The fix (refit and
  regrade) is the next release.

### Record

- **Measured.** No existing figure moved (PATCH). New figures, from `data/nfl4th_comparison.json`
  (44,836 matched plays, 2014-2026): same call on 71.3% of plays,
  87.8% of clear calls (n = 18,989); we recommend going for it on
  57.7% of plays, nfl4th on 42.1%; held-out Brier score
  0.1469 vs 0.1480 (difference -0.0011, 95% interval
  -0.0027 to +0.0005: no detectable difference).
- **Basis.** unchanged
- **Supersedes.** Nothing. Coach grades are not retracted yet: the long-kick
  defect is measured, but how much each grade moves is not; the next release
  measures and replaces them.
- **Owed to the next major.** White paper: a section on the nfl4th comparison
  and the long-kick fix. Deck: one slide on how we compare.

## [1.3.8] — 2026-10-13

### Changed

- **Teams are picked as Away and Home, then who has the ball.** The old pickers
  asked for "who has the ball" and "defense" before any game was chosen, which
  read as if a defense could have the ball. Manual entry now matches live mode:
  Away, Home, then a "Who has the ball?" switch with the two team names, and a
  Home field / Neutral site switch.
- **Away on the left, home on the right** for the scores, timeouts, field side
  and second-half kickoff. Switching the ball moves the offense, not the numbers.

### Removed

- The swap button and the "Where's the game?" row (both now follow from Away,
  Home and who has the ball).

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.7] — 2026-10-13

### Fixed

- **Switching who has the ball no longer moves the scores to the other team.**
  In a live game, tapping the other team relabelled the score boxes but kept the
  numbers, so the Bears' 17 became the Packers' 17. Now the scores and timeouts
  swap with the ball, and each team's boxes stay in the same place on screen
  (away on the left, home on the right).

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.6] — 2026-10-13

### Changed

- **Sharing a call sends only the decision and a link**, for example
  "GO FOR IT." The old message listed the whole situation and was hard to read
  on a phone.
- **Large link preview.** The link goes through a small page per call and
  distance (`app/s/<call>-<yards>/`) with a 1200 × 630 image: "4TH & 2" over
  "GO FOR IT". iMessage and Android show it as a large card. 68 images
  (go, field goal, punt, toss-up; 4th & 1 to 15, then "long"; plus one each for
  early downs), made by `build/og_images.py`. GitHub Pages is static, so the
  yard line and clock cannot be in the image.

### Notes

- 1.3.5 committed an unfinished draft of these pages by mistake. It was not
  deployed (the Pages workflow did not copy it) and is replaced here.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.5] — 2026-10-13

### Fixed

- **The 4th Down Duel card no longer shows when it has nothing to do.** It
  appeared under every call with only a hint, which read as a broken feature.
  It now shows only when you picked **Your call** before **Get the call**.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.4] — 2026-10-13

### Fixed

- **Fill from a live game now shows the games at once.** The games were in a
  drop-down that a script cannot open, so it took a second tap. They are now a
  list of buttons, and the scoreboard loads with the page, so the list is ready
  on the first tap. After a pick, only that game stays shown.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.3] — 2026-10-13

### Added

- **Weekly game (Play tab).** Five of last week's fourth downs: call what the
  engine says, then see its call and the coach's. You score for matching the
  engine; the coach scores when his real call matched it. Everyone gets the same
  five plays, and Send shares a square scorecard. The plays (`quiz()` in
  `engine/weekly.py`): the two costliest confident mistakes, the best gutsy go,
  and two correct but close kicks, so "always go" does not win.

### Changed

- **Less text on the form.** Explanations moved to About. The optional factors
  stay closed, even when autofill switches them on, and show their value in one
  line. Get the call stays pinned at the bottom of a phone screen.
- The ball starts at the opponent's 40.
- Team pickers show the team name only, so they fit next to the swap button.

### Record

- **Measured.** No figure changed. The weekly game reuses the shipped grades.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Deck: the weekly game and the Duel. White paper:
  a short note on how the weekly plays are chosen.

## [1.3.2] — 2026-10-13

### Added

- **4th Down Duel**, a Wordle-style game for group chats. Make your call before
  the engine, log what the coach did, and send a scorecard of green, yellow and
  black squares. It uses the phone's share sheet (iMessage, Android) or copies
  the text. Reason: friends asked for something to send mid-game.
- **Betting line autofill.** Picking two teams (or a live game) looks up the
  pre-game line on ESPN, falling back to the game summary because the
  scoreboard drops the line at kickoff. If no line is found the app says so and
  sets the teams even.

### Changed

- **No "your team" perspective.** The form is in terms of the team with the
  ball and the defense, labelled with team names. A live game selects the team
  with the ball automatically; a swap button gives the ball to the other team
  and flips every two-sided input.
- Team strength reads "Texans by 6.5" instead of a signed betting line.
- Higher contrast: darker page, lighter input wells with visible edges.

### Record

- **Measured.** No figure changed. The engine, models and grades are untouched;
  the betting line is an input the user could already set by hand.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Deck: mention the Duel and the line autofill. The
  technical how-to is updated in this release.

## [1.3.1] — 2026-10-13

### Changed

- Play-by-play is read from the shared NFL data store (`Projects/nfl-data`)
  when it is present, so this machine keeps one copy of the data. CI and fresh
  clones still use `data/raw/` (`store_dir` in the config).

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.3.0] — 2026-10-13

### Fixed

- **With team strength switched off, playing at home scored slightly worse than
  playing away.** "Off" set the spread to 0, but betting lines already include
  home-field advantage, so a line of 0 at home describes a home team weaker than
  its opponent. "Off" now means equal teams: the home team gets the measured
  home-field edge (the average home line since 2021, 1.74 points), the away team
  the opposite, a neutral site none. Coach grades are unaffected (they use the
  real line); the validation's agreement figure moves slightly.

### Changed

- Redesign: dark by default, a cleaner layout and a broadcast-style typeface.
  The results screen leads with the call, the reason, the 100% split, and Share
  and Edit on the first phone screen.
- "We are" is now "Where's the game?": Our stadium / Their stadium / Neutral site.
- Shared links are short: the situation is packed into about 21 digits
  (`?c=…`), with optional factors appended only when on. A round trip through a
  browser restores every field. Old long links no longer open a situation.
- "Wins lost / 17" is now "Wins lost per season", and the Coaches tab defines a
  confident mistake and wins lost per season in plain words.
- The map's hover label no longer sticks on phones; the season table keeps the
  team column on screen.
- Coach grades and the weekly page now include week 5.
- Coach grades have a "Since 2021" view (the default) next to "All since 2014".
  It grades only calls from 2021 on, against coaches with a full season in that
  window, so long-tenured coaches are not judged by an earlier era's norms
  (`recent_from` in the config). Why 2021: coaches' go rates had settled near
  20–24% (13% through 2017), the 17-game season began, and a coach has about
  300 graded calls since, enough for a stable grade.
- `llms.txt` describes the project for AI agents, at the repo root and on the site.
- Games tab (replaces This week): every game of the season with each team's
  fourth downs, the coach's call against the engine's, and a grade per team per
  game. A+ = no confident mistakes; otherwise the team-game is ranked against
  every team-game since 2014 that had one (A beats 75%, B 50%, C 25%, D 10%, F
  the rest). The week's costliest and gutsiest calls stay on the same tab.
- Four tabs (Call, Games, Coaches, Kickers) with About as a header link; on a
  phone they sit in a bottom tab bar that never wraps.

### Record

- **Measured.** Validation agreement with coaches (`data/validation.json`).
- **Basis.** unchanged — the same question; the fix changes what "even matchup"
  means when the team-strength factor is off.
- **Supersedes.** Agreement on held-out 4th downs ~~62.0%~~ 61.7%; held-out plays
  where the engine favored going by 2+ points ~~709~~ 694.
- **Owed to the next major.** Nothing new (risk 14 remains).

## [1.2.6] — 2026-10-13

### Added

- Neutral site option (London, Mexico City, the Super Bowl) next to Home and
  Away. The win model only learned home and away, so a neutral game is scored as
  the average of the two. Live game mode sets it from ESPN's neutral-site flag.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.2.5] — 2026-10-13

### Removed

- The football emoji from the app header. The site now has no emoji.

### Record

- **Measured.** No figure changed.
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

## [1.2.4] — 2026-10-13

### Changed

- The call now leads with a 100% split: how the 20 resampled models vote among
  go, field goal and punt (for example 95% / 5% / 0%). The win chance after each
  choice stays below it as detail.
- Live game mode asks for your team by name ("Buccaneers" / "Cowboys") instead
  of asking home or away a second time.
- The weekly job also runs on Wednesday, in case nflverse posts Monday's game late.

### Record

- **Measured.** No figure changed (the split shows the existing bootstrap).
- **Basis.** unchanged
- **Supersedes.** Nothing.
- **Owed to the next major.** Nothing new.

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
