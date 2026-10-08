# ADR-0003: Grade coaches only on confident mistakes

**Status:** Accepted, 2026-10-08

## Context

Summing "WP lost versus the engine" over every disagreement charges coaches
for calls where the engine's edge is smaller than its own uncertainty. Brill,
Yurko & Wyner (2025) find only 48% of 4th-down decisions are confident, and
44% have an edge under 1 WP point.

## Decision

Refit the whole pipeline on 20 game-level bootstrap resamples. Charge a call
only when at least 90% of replicates rank another option above the coach's.
Report the all-disagreements figure alongside, for comparison, but grade on
the confident figure.

## Consequences

- Positive: a coach is not penalised for a coin flip.
- Positive: the graded totals are directly comparable to the published
  0.22–0.4 wins per team-season.
- Negative: grading needs the bootstrap (~20 min to build) and is 21 times
  slower to score.
- Negative: with 20 replicates the confidence share moves in steps of 5%.
- Negative: it can under-charge a coach who makes many small, real mistakes.
