# Validation report

Model version 1.2.0, built 2026-10-08. Fit on 2014–2023; scored on held-out seasons 2024, 2025 (569 games). Splits are by season, so plays from one game never sit on both sides.

#### Win probability (every held-out snap)

| Model | Plays | Log loss | Brier |
|---|---|---|---|
| This engine | 81,654 | 0.446 | 0.148 |
| nflfastR `vegas_wp` (same plays; nflfastR was trained on them) | 81,654 | 0.4457 | 0.1475 |
| nflfastR `wp` without the spread | 81,654 | 0.4841 | 0.1641 |
| Score-and-time-only logistic baseline | 81,654 | 0.4931 | 0.1672 |
| This engine, final 5 minutes only | 9,427 | 0.2501 | 0.0812 |

Calibration (predicted vs actual win rate by predicted-probability bin):

| Bin | Plays | Predicted | Actual |
|---|---|---|---|
| 0.00-0.10 | 11,790 | 3.4% | 3.5% |
| 0.10-0.20 | 7,786 | 15.0% | 16.6% |
| 0.20-0.30 | 7,226 | 24.8% | 26.1% |
| 0.30-0.40 | 6,755 | 35.0% | 34.3% |
| 0.40-0.50 | 6,271 | 44.9% | 43.4% |
| 0.50-0.60 | 6,202 | 55.1% | 55.2% |
| 0.60-0.70 | 7,068 | 65.1% | 64.4% |
| 0.70-0.80 | 7,608 | 75.1% | 73.6% |
| 0.80-0.90 | 7,889 | 85.0% | 83.5% |
| 0.90-1.00 | 13,059 | 96.4% | 96.1% |

#### Option values (the test that matters for decisions)

For each held-out 4th down, the engine's win probability for the option the coach actually chose, against how often that team won:

| Coach chose | Plays | Engine predicted | Actual win rate |
|---|---|---|---|
| go | 670 | 37.3% | 38.1% |
| fg | 826 | 56.4% | 55.6% |
| punt | 1501 | 47.2% | 46.6% |

#### Conversion on 4th down

Log loss 0.6424 (n = 1849); with team strength 0.6406.

| Yards to go | Plays | Predicted | Actual |
|---|---|---|---|
| 1 | 721 | 69.7% | 71.3% |
| 2-3 | 491 | 60.9% | 60.3% |
| 4-6 | 332 | 51.3% | 56.3% |
| 7-10 | 179 | 37.3% | 36.9% |
| 11-99 | 126 | 21.8% | 32.5% |

#### Field goals

| Factors | Kicks | Log loss | Brier |
|---|---|---|---|
| base | 2306 | 0.3688 | 0.1147 |
| weather | 2306 | 0.3671 | 0.114 |
| stadium | 2306 | 0.3676 | 0.1142 |
| weather+stadium | 2306 | 0.3673 | 0.114 |

| Distance | Kicks | Predicted | Actual |
|---|---|---|---|
| 18-29 | 469 | 98.0% | 97.7% |
| 30-39 | 632 | 93.3% | 93.7% |
| 40-49 | 640 | 81.8% | 80.8% |
| 50-54 | 354 | 69.3% | 74.0% |
| 55-70 | 211 | 59.3% | 61.1% |

Kicking-era term chosen on the hold-out: **trend** (log loss: trend 0.3688, era2020 0.3694, both 0.3697).

Kicker skill priors chosen on the hold-out: accuracy sd 0.4, range sd 0.1. Log loss 0.3673 with no kicker effect, 0.3665 with it (accuracy only: 0.3666).

#### Punts

Mean absolute error of the predicted opponent start: **6.75 yd** (n = 3,714), against 10.9 yd for a league-average guess.

#### Agreement with coaches (descriptive)

On 3,000 sampled held-out 4th downs the engine's call matched the coach's 62.0% of the time. Where the engine favored going by 2+ points (709 plays), coaches went 46.7% of the time.

#### Clock and rules measured from the data

| Event | Seconds to next snap (normal) | (final 2:00 of half) |
|---|---|---|
| go_success | 37.0 | 18.0 |
| go_fail | 5.0 | 6.0 |
| punt | 9.0 | 9.0 |
| fg | 5.0 | 5.0 |
| score | 8.0 | 6.0 |
| play_first | 37.0 | 11.0 |
| play_short | 36.0 | 6.0 |
| punt_fair_catch | 7.0 | 7.0 |
| timeout_play | — | 6.0 |
| spike_total | — | 16.0 |

Kickoff: the receiving team starts at yardline_100 **69.3** on average under the 2025 rules. Punt return TD rate 0.39%; muff recovered by the kicking team 1.44%.

Weather: outdoor wind or temperature imputed on 1,425 plays after parsing the weather text.

#### Edge calibration (does following the engine win as much more as it predicts?)

Graded 4th downs binned by the engine's predicted edge for going. In each bin, teams that went are compared with teams that kicked: the engine's predicted gap in win probability against the realized gap in win rate. Teams that went often knew something the engine cannot see, so the realized gap is biased toward going and the ratio is an upper bound on how much of the predicted edge is real.

| Predicted edge for going | Went | Kicked | Predicted gap | Actual gap | Actual − predicted | ± SE |
|---|---|---|---|---|---|---|
| (-1.0, 0.0] | 1715 | 19368 | -27.6 pts | -27.2 pts | +0.3 pts | 1.1 |
| (0.0, 0.01] | 1911 | 7556 | -23.4 pts | -24.4 pts | -1.0 pts | 1.1 |
| (0.01, 0.02] | 932 | 3964 | -5.8 pts | -5.0 pts | +0.8 pts | 1.8 |
| (0.02, 0.04] | 1445 | 3886 | +0.4 pts | -0.7 pts | -1.1 pts | 1.5 |
| (0.04, 0.08] | 1323 | 1748 | +2.8 pts | +3.1 pts | +0.3 pts | 1.8 |
| (0.08, 1.0] | 662 | 280 | -0.2 pts | -7.1 pts | -6.9 pts | 3.4 |

Pooled (precision-weighted): actual minus predicted -0.5 ± 0.6 WP points. Games share outcomes, so the true uncertainty is larger.

## What these numbers do not prove

- That following the engine wins more games. Option values are calibrated on average, which is necessary, not sufficient. No randomized test of 4th-down policy exists.
- That any single call is right. See the bootstrap confidence for that call.
- Anything about seasons with different rules. The kickoff spot is measured from one rule season.
- That short-yardage conversion is unbiased. Yards to go is a whole number (Lopez 2020; risk 1).
