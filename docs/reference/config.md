# Reference: configuration

All settings that change over time are in one block: `CONFIG` in
`engine/config.py`. After you change a setting, rebuild (see
[../how-to/rebuild-everything.md](../how-to/rebuild-everything.md)).

| Setting | Meaning |
|---|---|
| `version` | Engine version. It must equal the newest CHANGELOG entry. |
| `seasons` | Seasons used to fit the models. |
| `holdout_seasons` | Seasons held out for validation. |
| `rules_season` | Season that sets the kickoff spot (current kickoff rules). |
| `touchdown_points` | Points for a touchdown, extra point included. |
| `fg_snap_to_spot`, `fg_distance_add`, `missed_fg_min_spot` | Field-goal geometry and the missed-kick rule. |
| `fg_max_distance` | Longest kick the engine allows. |
| `tossup_margin` | Edge below which a call is a toss-up. |
| `fair_catch_kick_window` | Seconds left after a punt at or below which the opponent may use a fair-catch kick. |
| `wp_trees` | Win-probability model settings. |
| `kicker_prior_grid` | Candidate prior widths for kicker accuracy and range. |
| `replacement`, `replacement_fringe` | Replacement-kicker rules (main and sensitivity). |
| `kicker_list_seasons`, `kicker_list_min_attempts` | Which kickers the app lists. |
| `kicker_grade_min_attempts` | Minimum attempts for a kicker letter grade. |
| `precip_words`, `altitude_stadiums`, `cold_threshold_f` | Weather and stadium definitions. |
| `quantiles`, `togo_buckets`, `punt_bin_width` | Outcome-distribution settings. |
| `grade_seasons`, `current_season` | Seasons graded; the season in progress. |
| `coach_aliases` | Corrections to coach names in the source data. |
| `grade_min_games` | Minimum games for a coach letter grade. |
| `grade_toggles` | Factors used when grading coaches. |
| `bootstrap_models`, `bootstrap_seed` | Number of bootstrap replicates; random seed. |
| `confident_share` | Share of replicates needed for a confident mistake. |
| `bootstrap_draws` | Resamples for each coach's interval. |
