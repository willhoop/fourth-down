# ADR-0001: Use nflverse play-by-play as the only data source

**Status:** Accepted, 2026-10-08

## Context

The engine needs every NFL play with score, clock, field position, timeouts,
the pre-game line, weather, roof, kicker and head coach. Options: nflverse
play-by-play (public, free, maintained, one parquet per season), NFL Next Gen
Stats (tracking data, not public at play level), or a paid feed.

## Decision

Use nflverse play-by-play, seasons 2014–2025 for fitting and 2014–2026 for
grading coaches. Download with `engine/download_data.py`. Do not commit the
raw files. Ship only fitted model parameters.

## Consequences

- Positive: free, reproducible, the same source as nflfastR, nfl4th and most
  published work, so results compare directly.
- Positive: 2026 games are fully out of sample for the model.
- Negative: yards to go is a whole number, so the engine cannot see that
  "4th & 1" ranges from inches to a full yard (Lopez 2020). See risk 1.
- Negative: weather fields have gaps; see risk 10.
- Negative: the project depends on nflverse continuing to publish. A future
  break means pinning a release or caching files elsewhere.
