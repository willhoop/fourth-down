# ADR-0004: Measure 4th-down gambles from the punt

**Status:** Accepted, 2026-11-07

## Context

Prospect theory needs a reference point: outcomes above it are gains, below it
losses. The fear-of-failing figure (lambda) depends on it. Whittaker (2026)
fits the same model to coaches but does not state its reference point.
Candidates:

1. The punt's WP (the field goal's when there is no punt): the safe call.
2. The WP before the snap.
3. The expected WP of the best option.

## Decision

Use (1). A coach deciding on 4th down compares the gamble with the call that
"nobody gets fired for". The punt is close to a sure thing in WP, so it is a
natural zero. With no punt (inside the opponent's 35 or so), the field goal is
the safe call.

## Consequences

- Positive: every gamble has a clear "loss" side (a failed try, a missed
  kick), so lambda reads as "fear of failing".
- Positive: the punt then carries no weighting at all, which keeps the model
  small (four numbers for the league).
- Negative: lambda absorbs any general dislike of going for it, whatever its
  cause, including engine error (risk 21).
- Negative: (2) would give another lambda. The figure is comparable only with
  fits that use the same reference point, not with Whittaker (2026).
- Negative: the field goal is treated as a gamble when there is a punt, but
  as the reference when there is not, so its role changes at the edge of
  range.
