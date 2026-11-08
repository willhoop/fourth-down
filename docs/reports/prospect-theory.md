# Prospect-theory fit: fear of failing

<!-- Rendered by build/render_reports.py from data/prospect.json. Do not edit by hand. -->

## Method

Every 4th down 2014-2026 without overtime (n = 45,730 in 3,417 games). The engine prices each option as a gamble: going for it converts with chance p (WP after success, WP after failure); a field goal is made with chance p; a punt is a sure thing. Outcomes are measured from the punt WP (field goal WP when there is no punt), in units of 5 WP points. A logit choice model with Prelec weighting w(p) = exp(-(-ln p)^gamma) and value x^alpha (gains), -lambda(-x)^alpha (losses) is fit by maximum likelihood (Tversky & Kahneman 1992; Whittaker 2026). gamma = lambda = alpha = 1 is the computer.

Each coach: lambda only, with the league's gamma, alpha and tau; standard error clustered by game; shrunk toward the league by empirical Bayes (prior sd of log lambda 0.1567, from 91 coaches with 100+ calls).

## League

| Parameter | Fit | 95% range (100 game-resampled refits) | Computer |
|---|---|---|---|
| gamma (calibration) | 1.191 | 1.158-1.23 | 1 |
| lambda (fear of failing) | 2.701 | 2.646-2.76 | 1 |
| alpha (value of big gains) | 0.463 | 0.453-0.474 | 1 |

Read as: a 51% chance feels like 54%, 85% like 89%, 10% like 7%. A failed 4th down weighs 2.7 times a conversion of the same size (lab median for people: 2.25). A gain 4 times as big feels 1.9 times as good.

## By era

| Seasons | Decisions | gamma | lambda | alpha |
|---|---|---|---|---|
| 2014-2017 | 14,472 | 1.05 | 2.942 | 0.426 |
| 2018-2021 | 14,198 | 1.211 | 2.745 | 0.473 |
| 2022-2025 | 15,432 | 1.327 | 2.494 | 0.492 |

## Hold-out test

Fit on 2014-2023, scored on 2024-2025 (n = 7,568). The second model adds a constant preference for each kick, so prospect theory cannot win only by learning that coaches like to kick.

| Model | Calls predicted | Log loss |
|---|---|---|
| Computer (expected WP) | 57.5% | 0.7917 |
| Computer that likes kicking | 74.7% | 0.6353 |
| Prospect theory | 79.8% | 0.4942 |

## Coaches in 2026

| Coach | Calls | Fear of failing | 95% range | Own calls only |  |
|---|---|---|---|---|---|
| Brian Schottenheimer | 149 | 2.05 | 1.80-2.32 | 1.93 |  |
| Raheem Morris | 362 | 2.11 | 1.89-2.35 | 2.04 |  |
| Dan Campbell | 618 | 2.13 | 1.93-2.36 | 2.07 |  |
| Shane Steichen | 414 | 2.15 | 1.92-2.40 | 2.08 |  |
| Jonathan Gannon | 393 | 2.22 | 1.98-2.48 | 2.15 |  |
| Dave Canales | 290 | 2.25 | 1.99-2.54 | 2.17 |  |
| Kevin O'Connell | 513 | 2.28 | 2.02-2.57 | 2.21 |  |
| Nick Sirianni | 673 | 2.28 | 2.08-2.49 | 2.24 |  |
| Ben Johnson | 195 | 2.29 | 1.95-2.68 | 2.15 |  |
| Robert Saleh | 571 | 2.30 | 2.05-2.57 | 2.24 |  |
| Kellen Moore | 175 | 2.35 | 2.12-2.61 | 2.31 |  |
| Klint Kubiak | 53 | 2.37 | 1.82-3.09 | 1.63 | few calls |
| Dan Quinn | 828 | 2.43 | 2.21-2.66 | 2.40 |  |
| Jeff Hafley | 43 | 2.43 | 1.93-3.07 | 2.11 | few calls |
| Mike McCarthy | 1167 | 2.44 | 2.26-2.64 | 2.43 |  |
| Matt LaFleur | 792 | 2.45 | 2.24-2.67 | 2.43 |  |
| Todd Monken | 62 | 2.48 | 1.99-3.10 | 2.27 | few calls |
| Mike Vrabel | 833 | 2.49 | 2.27-2.73 | 2.47 |  |
| Sean McDermott | 1039 | 2.56 | 2.36-2.77 | 2.55 |  |
| John Harbaugh | 1415 | 2.59 | 2.41-2.79 | 2.58 |  |
| Sean McVay | 1140 | 2.61 | 2.44-2.79 | 2.60 |  |
| Liam Coen | 158 | 2.64 | 2.27-3.08 | 2.62 |  |
| Aaron Glenn | 186 | 2.66 | 2.41-2.94 | 2.66 |  |
| Jim Harbaugh | 409 | 2.67 | 2.38-3.00 | 2.67 |  |
| Zac Taylor | 842 | 2.69 | 2.50-2.91 | 2.69 |  |
| DeMeco Ryans | 472 | 2.77 | 2.54-3.01 | 2.77 |  |
| Mike Macdonald | 295 | 2.80 | 2.48-3.16 | 2.82 |  |
| Kyle Shanahan | 995 | 2.81 | 2.58-3.06 | 2.82 |  |
| Todd Bowles | 1036 | 2.83 | 2.59-3.08 | 2.84 |  |
| Sean Payton | 1258 | 2.87 | 2.68-3.08 | 2.88 |  |
| Jesse Minter | 60 | 2.90 | 2.49-3.39 | 2.98 | few calls |
| Andy Reid | 1391 | 2.92 | 2.70-3.16 | 2.94 |  |

## What these numbers do not prove

- That coaches feel fear. The fit describes choices, not beliefs or motives.
- That the engine is right. lambda grows when coaches pass on the engine's go calls; if the engine overrates going for it, that error is counted as fear (risk 21).
- That the reference point is right. Another reference (the WP before the snap) would move lambda (ADR-0004).
- That the figures match Whittaker (2026): another WP model, reference point and estimator. That study reports gamma 0.34, lambda 1.42, alpha 0.30 with no error ranges.
- That one coach differs from another unless their 95% ranges do not overlap.
