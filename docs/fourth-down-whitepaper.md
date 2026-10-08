# Fourth Down Engine: Win-Probability Decisions for Go, Field Goal or Punt

Version: 1.0.0 — 2026-10-08
Author: Will Hooper
Data: nflverse play-by-play, 2014–2025 (fit) and 2014–2026 (coach grading)

## Abstract

On fourth down an NFL team chooses between going for it, kicking a field goal
and punting. This paper describes an engine that scores each option by the
team's probability of winning the game afterwards. A gradient-boosted
win-probability (WP) model, trained on every regulation snap from 2014 to
2025, values the situations each option can lead to. Sub-models for
conversion, field-goal success and punt outcome supply the odds of each
situation. The clock, timeouts, the two-minute warning, the second-half
kickoff, the pre-game line, weather, roof, altitude and the kicker all enter
the calculation, and each optional factor can be switched off. A whole-pipeline
bootstrap measures how sure each call is. The engine then grades every current
head coach by replaying each of their fourth downs twice, once as called and
once as the engine would call it, and charging only the calls the bootstrap is
confident were wrong. It also grades every kicker against a measured
replacement level. All results are in section 7; every figure there is rendered
from the pipeline's output files.

## 1. The question

A fourth-down call is a choice between lotteries. Going for it risks giving
the opponent a short field for the chance of keeping the drive. A field goal
trades a likely 3 points for possession. A punt gives up the ball for field
position. Which lottery is best depends on the whole game state: a 3-point
lead is worth little in the first quarter and almost everything with a minute
left.

Expected points (Carter & Machol 1971; Romer 2006) answer the question early in
games, when the score barely matters. Win probability answers it at every
point, because it already accounts for score and clock (Burke; Lock &
Nettleton 2014; Yurko, Ventura & Horowitz 2019; Baldwin 2021). This engine uses
win probability throughout.

The same machinery answers a narrower early-down question: on 1st, 2nd or 3rd
down with the clock running out, should the team kick the field goal now
instead of running another play (section 3.3)?

**Scope.** Regulation only. Overtime plays are excluded from training, and a
game tied at the end of regulation counts as 0.5. Two-point decisions, fake
kicks as a separate option, and onside kicks are out of scope.

## 2. Data

nflverse play-by-play (ADR-0001): one parquet file per season, the same source
as nflfastR and nfl4th. The fit uses 2014–2025; the coach grader also reads
2026 (weeks played so far), which the model has never seen.

Derived columns, all from the offense's point of view:

- `score_diff`: offense score minus defense score.
- `spread`: points the offense was favored by before the game (nflverse
  `spread_line` is from the home side; it is negated for the away team).
- `receive_2h`: 1 in the first half if the offense will receive the second-half
  kickoff, derived from the first kickoff of the game.
- `tmw_pending`: 1 while more than 120 seconds remain in the half, i.e. the
  two-minute warning is still to come.
- Weather: wind and temperature from the structured fields, filled from the
  free-text weather string where missing (46% of outdoor games in 2022 lack the
  structured fields). Precipitation is a keyword match on the same string.
  Indoors, wind and precipitation are 0 and temperature is 70 °F.
- Altitude: 5,280 ft for Denver home games, 7,350 ft for Estadio Azteca.

## 3. Method

### 3.1 Win-probability model

For a snap with features **x**, the model gives the offense's probability of
winning:

  WP(**x**) = σ( b₀ + Σₜ fₜ(**x**) ),  σ(z) = 1 / (1 + e^(−z))

where each fₜ is a regression tree (250 trees, ≤ 31 leaves, gradient boosting
on log loss; scikit-learn `HistGradientBoostingClassifier`). Inputs: score
difference, game seconds, half seconds, half, yard line, down, distance, both
teams' timeouts, two-minute warning pending, second-half receiver, spread,
home, and two engineered terms from nflfastR (Baldwin 2021):

  spread_time = spread · e^(−4·s),  diff_time_ratio = score_diff / e^(−4·s)

with s the elapsed share of the game. The first lets the pre-game line fade as
the game reveals itself; the second lets a lead grow in value as time runs out.
Monotone constraints force WP to rise with score difference, field position,
own timeouts, spread and both engineered terms, and to fall with the
opponent's timeouts. The trees are exported to JSON and evaluated identically
in Python and JavaScript (ADR-0002). Ties are dropped from training.

### 3.2 Option values

Let s be the fourth-down state and V(s′) the WP of a next state s′ from **our**
point of view (V = WP if we have the ball, 1 − WP if they do). Then

  Go   = p_c · E[V(s′ | convert)] + (1 − p_c) · V(s′ | stopped)
  FG   = p_m · V(s′ | made) + (1 − p_m) · V(s′ | missed)
  Punt = (1 − p_td − p_mf) · E[V(s′ | normal punt)] + p_td · V(s′ | return TD) + p_mf · V(s′ | muff)

and the call is the option with the largest value (Romer 2006; nfl4th). The
next states are built as follows.

- **Converted.** Yards gained come from the empirical distribution of gains on
  successful 3rd and 4th downs with similar distance (20 quantiles per
  distance bucket). A gain that reaches the end zone is a touchdown (+7, then
  the opponent receives a kickoff). Otherwise it is our 1st & 10 (or & goal).
- **Stopped.** The opponent takes over where the play ended (mean yards gained
  on failed attempts for that distance).
- **Made field goal.** +3, then the opponent receives a kickoff.
- **Missed field goal.** The opponent takes over at the spot of the kick (line
  of scrimmage + 7), or at its own 20 if that is further from its goal.
  Kicks longer than 70 yards, the longest attempt in the data, are out of range
  and the option is removed.
- **Punt.** The opponent's start spot comes from the empirical distribution of
  real punts from the same 5-yard band. A return touchdown (+7 for them, our
  kickoff return) and a muff recovered by the kicking team are separate
  outcomes, with rates shrunk toward the league rate (200 pseudo-counts).
- **Fair-catch kick.** After a fair catch, NFL Rule 11-4-3 lets the receiving
  team try a free-kick field goal from the catch spot: a place kick or a drop
  kick, with no rush, from (spot + 10) yards. If time expires during the punt, it
  is an untimed down. When 10 seconds or fewer would remain after the punt
  (`fair_catch_kick_window`), each fair catch (rate measured per 5-yard band)
  gives the opponent the better of that kick (league-average kicker, same
  weather and stadium) and playing on. Good punts leave the receiver 70+ yards
  from the goal posts, so the threat is real mainly after short punts at the end
  of a half.
- **Drop kicks from scrimmage** are legal on any down and score the same 3
  points, but they are almost never used and leave no data for a separate make
  rate. The engine treats a drop-kicked field goal as a field goal.
- **Kickoffs** place the receiver at the mean start spot measured under the
  current kickoff rules (`rules_season`).

**Clock.** Each outcome uses the median game-clock time from this snap to the
next snap, measured from the data separately for the final two minutes of a
half. If the two-minute warning is pending and the play would cross 2:00, the
next state starts at 2:00 and the warning is spent. If the half ends, a first
half resets to the second-half kickoff (the receiver gets the ball, timeouts
reset); a second half ends the game, with WP 1, 0 or 0.5 by the final score.
Timeouts carry over unchanged.

### 3.3 Early downs: kick now or run a play?

On 1st–3rd down the options are **run a play** and **kick a field goal now**
(nobody punts). Running a play keeps the kick available on a later down, so it
wins almost always. The exception is the clock:

  Play = (1 − p_to) · E_g[V(s′ | gain g)] + p_to · V(s′ | turnover)

Gains g come from the empirical distribution of 1st-, 2nd- or 3rd-down runs
and passes at similar distance (20 quantiles); p_to is the measured turnover
rate for that down. A gain past the line is a new 1st down; otherwise it is the
next down at the new distance. The clock runs by the measured snap-to-snap time,
separately for plays that gain a first down (clock keeps running) and plays that
do not (incompletions stop it). If that time would end the half and the offense
has a timeout, it calls one, and the play costs only the measured length of a
play followed by a timeout. With no timeout left it spikes the ball, which costs
a down (allowed only while it leaves at least 4th down) and the measured time
from the play's snap through the spike to the next snap. If neither saves the
clock, the half ends and a team that is behind loses the chance to kick. The WP
model values every next state.

### 3.4 Conversion

  logit p_c = β₀ + β₁·is4 + β₂·min(d,20)/10 + β₃·ln d + β₄·goal + β₅·inside10 + β₆·redzone [+ β₇·spread/10]

fitted by maximum likelihood on all 3rd- and 4th-down runs and passes, with
`is4 = 1` at prediction time. Pooling 3rd downs follows Romer (2006), who found
the 3rd/4th difference small, and Brill et al. (2025), whose best conversion
model pools them. A defensive penalty that gives a first down counts as a
conversion, as in nfl4th. The spread term is used when the team-strength factor
is on.

### 3.5 Field goals

  logit p_m = α₀ + α₁·D + α₂·D² + α₃·era [+ weather terms] [+ stadium terms] [+ a_k + b_k·(D − 4)]

with D the kick distance in tens of yards. Weather terms: wind, wind × distance,
cold (degrees below 50 °F), precipitation. Stadium terms: dome or closed roof,
altitude. These follow Clark, Johnson & Stimpson (2013) and Pasteur &
Cunningham-Rhoads (2014). The era term (linear year trend, a 2020+ step, or
both) is chosen on the hold-out seasons. Four models are fit, one for each
on/off combination of the weather and stadium factors, so an off factor is
marginalised rather than set to a guess. a_k and b_k are the kicker's
accuracy and range (section 4).

### 3.6 Factors as toggles

Each optional factor (weather, stadium, team strength, kicker) can be switched
off. Off means: the matching field-goal and punt models without that factor's
terms; a spread of 0 (an even matchup) in the WP and conversion models; a
league-average kicker. The core inputs (score, clock, field position,
distance, timeouts, two-minute warning, second-half receiver, home) are always
on.

## 4. Kickers

**Skill model.** For kicker k, relative to the environment-adjusted league
logit z:

  logit P(make) = z + a_k + b_k · (yards − 40) / 10

a_k (accuracy) moves the whole curve; b_k (range) tilts it, so a big leg holds
its make rate at long distance. This matches the kicker intercepts and distance
slopes of Long (2019) and the distance-varying shrinkage of Osborne & Levine
(2017). Each (a_k, b_k) is a maximum a posteriori estimate under independent
normal priors N(0, σ_a²) and N(0, σ_b²), found by Newton's method. The prior
widths are chosen on a grid by hold-out log loss. Skill is measured against the
fullest environment model, so a Denver kicker is not credited for altitude.

**Replacement level.** Following nflWAR (Yurko et al. 2019): in each season,
kickers are ranked by attempts, and all kicks by anyone outside the top 32 are
pooled into one unshrunk (a_R, b_R). A second rule (short careers inside the
data) is reported as a sensitivity check.

**Value.** For a kicker's actual kicks i,

  points over replacement = 3 · Σᵢ [ σ(zᵢ + a_k + b_k xᵢ) − σ(zᵢ + a_R + b_R xᵢ) ]

reported in total and per 100 kicks. Grades rank kickers active in the latest
season by points over replacement per 100 kicks.

## 5. Grading coaches: every call played twice

For each fourth-down run, pass, punt or field goal by a team (penalties,
kneels and spikes excluded), the engine evaluates the same state with every
factor on, using that game's kicker, weather, roof and line:

- **Coach's way:** V_c = value of the option the coach chose.
- **Engine's way:** V_e = value of the best option.
- **Cost:** V_e − V_c ≥ 0, the expected wins the call gave up.
- **What happened:** V_r = WP at the next snap after the real play (or the
  final result if the game ended), from the coach's side.
- **Luck:** V_r − V_c. Luck sums to zero in expectation; it measures what the
  dice did after the decision, not the decision.

**Confidence.** The whole pipeline is refit on 20 bootstrap resamples of whole
games (section 6). A call is a **confident mistake** only when at least 90% of
replicates rank another option above the coach's choice. Following Brill,
Yurko & Wyner (2025), the graded figure sums cost over confident mistakes only;
the sum over all disagreements is reported alongside (ADR-0003).

**Grades.** A coach's figure is confident-mistake cost per game, expressed as
wins per 17 games, with a 90% interval from resampling his calls. Letters rank
him against every head coach with at least 17 games in the data: the best 10%
earn A+, then A (to 25%), B+ (40%), B (60%), C+ (75%), C (90%) and D. Coaches
with fewer than 17 games are listed as Incomplete.

## 6. Uncertainty and validation

**Bootstrap.** Twenty replicates, each a full refit (WP, conversion, field goal,
punt, clock) on games drawn with replacement. Games are the unit because plays
in a game share one outcome. Brill et al. also resample drives within games;
this engine does not, which may understate variance (risk 4). Confidence moves
in steps of 5%.

**Validation.** Every model is fit on 2014–2023 and scored on 2024–2025. Splits
are by season, so no game is on both sides. The key test is not WP accuracy
alone but whether **option values** are calibrated: for the option a coach
actually chose, does the engine's predicted WP match how often the team won?

**What validation does not prove.** That following the engine wins more games
(no randomized test of 4th-down policy exists); that any single call is right;
or that short-yardage conversion is unbiased (section 8).

## 7. Results

<!-- BEGIN GENERATED RESULTS -->
<!-- Rendered by build/render_reports.py from data/*.json. Do not edit by hand. -->

**Headline results**

- Win-probability log loss on held-out 2024, 2025: **0.446** (nflfastR `vegas_wp` on the same 81,654 plays: 0.4457).
- Option values on held-out 4th downs, predicted vs actual win rate: go 37.3% vs 38.1% (n = 670); field goal 56.3% vs 55.6% (n = 826); punt 47.2% vs 46.6% (n = 1501).
- League cost of 4th-down calls, confident mistakes only: **0.90** wins per team-season in 2014, **0.61** in 2025. Counting every disagreement: 1.16 and 0.84.
- Coaches went for it on 12.7% of 4th downs in 2014 and 24.0% in 2025; the engine clearly favored going (edge of 1 point or more) on 32.6% and 33.7%.
- Share of 4th downs that are toss-ups (edge under 1 WP point), 2014–2026: 38.4% to 44.7%. Share of calls the bootstrap is confident about: 47.8% to 50.5%.
- Current head coaches with the lowest confident-mistake cost: Liam Coen 0.35 wins/17 games (A+); Mike Macdonald 0.47 wins/17 games (A+); Dan Campbell 0.48 wins/17 games (A+).
- Highest: Todd Bowles 0.88 (C); Shane Steichen 0.88 (C+); Sean Payton 0.84 (C+).
- Replacement-level kicker: 76.4% made vs 85.5% expected; 61% from 50 yd vs 77% league average.
- Top current kickers by points over replacement per 100 kicks: B.Aubrey 44.2; C.Boswell 40.8; W.Reichard 39.5.

Full tables: `docs/reports/validation-report.md`, `docs/reports/coach-grades.md`, `docs/reports/kicker-grades.md`.
<!-- END GENERATED RESULTS -->

**Benchmark against the literature.** Published estimates of the cost of
fourth-down conservatism are about 0.4 wins per team-season before 2016 (Romer
2006; Yam & Lopez 2019), 0.35 for 2017–2019, and 0.22 after correcting for exact
distance (Lopez 2020). The engine's toss-up share and confident share agree with
Brill, Yurko & Wyner (2025), who found 44% of edges under 1 point and 48% of
decisions confident. Its share of clear "go" calls is in the range of published
fourth-down bots. **Its league cost totals above are larger than every published
estimate, roughly two to four times the distance-corrected figure.** The most
likely causes are the ones in section 8: whole-number distance (Lopez found it
inflates the apparent gain by about 40%), the separate gains and conversion
models, and a bootstrap that measures sampling noise but not model error. Read
the coach figures as a **ranking** of how closely each coach's calls match the
engine, not as a precise count of wins lost. The letter grades are percentile
ranks for that reason.

## 8. Limitations

1. **Distance is a whole number.** Teams that go on "4th & 1" are closer to the
   line than teams that kick (Lopez 2020). The engine cannot see this, so its
   short-yardage "go" edge is probably biased upward. Lopez found the bias was
   about 40% of the apparent benefit of aggression.
2. **Long-yardage attempts are selected.** Hold-out conversion on 4th & 11+ is
   higher than predicted, because those tries happen mostly in desperate
   late-game spots against soft defenses. The engine is, if anything,
   conservative on long tries.
3. **Gains and conversion are modelled separately.** nfl4th fits one joint
   yards-gained distribution that depends on field position and team strength.
   This engine bins gains by distance only.
4. **One kickoff spot.** Kickoff returns are a mean, not a distribution.
5. **Touchdown = 7.** The extra point is treated as certain; two-point
   decisions are not modelled.
6. **Grading uses in-sample models for 2014–2025.** Option values validate out of
   sample, and 2026 calls are fully out of sample.
7. **Field-goal link.** Osborne & Levine (2017) found a complementary log-log
   link fits better than logit. It was not tested here.

## 9. Relation to the literature

| Choice | This engine | Literature |
|---|---|---|
| Decision rule | Max WP over probability-weighted outcomes | Romer (2006); nfl4th; Brill et al. (2025) |
| WP model | Boosted trees, monotone, spread-fade and score/time terms | nflfastR XGBoost (Baldwin 2021); GAM in nflWAR |
| Conversion | Logistic, 3rd + 4th downs pooled, 4th-down term, defensive-penalty firsts | Romer (2006); nfl4th (joint yards-gained XGBoost) |
| Field goal | Logistic with environment terms and kicker accuracy/range | Clark et al. (2013); Pasteur & Cunningham-Rhoads (2014); Osborne & Levine (2017); nfl4th uses no kicker or weather |
| Punt | Empirical quantiles by 5-yd band, return TD and muff rates | nfl4th kernel density |
| Uncertainty | 20-replicate game bootstrap; grade confident mistakes only | Brill, Yurko & Wyner (2025) |
| Replacement kicker | Outside top 32 by attempts per season | nflWAR (Yurko et al. 2019) |

Coaches' conservatism is consistent with risk aversion over the next state's
value (Sandholtz et al. 2024).

## References

- Baldwin, B. (2021). nflfastR EP, WP, CP, xYAC and xPass models. *Open Source Football.* https://opensourcefootball.com/posts/2020-09-28-nflfastr-ep-wp-and-cp-models/
- Baldwin, B. nfl4th R package. https://github.com/nflverse/nfl4th
- Brill, R. S., Yurko, R., & Wyner, A. J. (2025). Analytics, have some humility: A statistical view of fourth-down decision making. *The American Statistician* 79(3), 393–409. doi:10.1080/00031305.2025.2475801
- Burke, B. Advanced NFL Stats win probability model (described in secondary sources; original page unverified).
- Carter, V., & Machol, R. E. (1971). Operations research on football. *Operations Research* 19(2), 541–544. doi:10.1287/opre.19.2.541
- Clark, T. K., Johnson, A. W., & Stimpson, A. J. (2013). Going for three: Predicting the likelihood of field goal success with logistic regression. *MIT Sloan Sports Analytics Conference.*
- Lock, D., & Nettleton, D. (2014). Using random forests to estimate win probability before each play of an NFL game. *JQAS* 10(2), 197–205. doi:10.1515/jqas-2013-0100
- Long, J. (2019). Kicker ratings: methods notes (blog, not peer-reviewed). https://jacob-long.com/post/kickers-methods-notes
- Lopez, M. J. (2020). Bigger data, better questions, and a return to fourth down behavior. *JQAS* 16(2), 73–79. doi:10.1515/jqas-2020-0056
- nflverse. nflverse-data play-by-play releases. https://github.com/nflverse/nflverse-data/releases/tag/pbp
- Osborne, J. A., & Levine, R. A. (2017). Shrinkage estimation of NFL field goal success probabilities. *Journal of Sports Analytics* 3(2), 129–146.
- Pasteur, R. D., & Cunningham-Rhoads, K. (2014). An expectation-based metric for NFL field goal kickers. *JQAS* 10(1), 49–66. doi:10.1515/jqas-2013-0039
- Romer, D. (2006). Do firms maximize? Evidence from professional football. *Journal of Political Economy* 114(2), 340–365.
- Sandholtz, N., Wu, L., Puterman, M., & Chan, T. C. Y. (2024). Learning risk preferences in Markov decision processes: An application to the fourth down decision in the NFL. *Annals of Applied Statistics* 18(4), 3205–3228. doi:10.1214/24-AOAS1933
- Yam, D. R., & Lopez, M. J. (2019). What was lost? A causal estimate of fourth down behavior in the NFL. *Journal of Sports Analytics* 5(3), 153–167. doi:10.3233/JSA-190294
- Yurko, R., Ventura, S., & Horowitz, M. (2019). nflWAR: A reproducible method for offensive player evaluation in football. *JQAS* 15(3). doi:10.1515/jqas-2018-0010
