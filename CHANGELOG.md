# Changelog

All notable changes are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/),
[Semantic Versioning](https://semver.org/). Newest first. Dates are ISO 8601.

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
