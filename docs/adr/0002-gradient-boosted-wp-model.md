# ADR-0002: Gradient-boosted trees for win probability, exported to JSON

**Status:** Accepted, 2026-10-08

## Context

Every option is valued through a win-probability (WP) model, so its
accuracy sets the ceiling for the whole engine. The app must run offline from
a double-clicked file with no server. Options: logistic regression (portable,
but cannot capture interactions such as "a 3-point lead matters more late"),
a GAM (nflWAR), or boosted trees (nflfastR uses XGBoost).

## Decision

Fit scikit-learn `HistGradientBoostingClassifier` (250 trees, 31 leaves) with
monotone constraints on score, field position, timeouts and spread. Add
nflfastR's engineered terms (a spread that fades with time; a score-to-time
ratio). Export every tree to JSON and evaluate it in plain JavaScript.

## Consequences

- Positive: hold-out log loss 0.446 on 2024–2025, level with nflfastR's own
  `vegas_wp` on the same plays.
- Positive: no server and no runtime dependency; the same JSON drives the
  Python reference engine and the app.
- Negative: the model file is ~0.5 MB, and each bootstrap replicate adds the
  same again (~10 MB for 20).
- Negative: two implementations (Python and JavaScript) must stay identical.
  CI checks parity on 60 random states.
- Negative: the spread monotone constraint is stricter than nflfastR's.
