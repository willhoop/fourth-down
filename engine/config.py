"""The one configuration block.

Everything that changes over time lives here: the seasons used, the rule era,
the hold-out split, and the modelling knobs. A new season or a new kickoff rule
is a single edit here followed by `py engine/fit_models.py`.
"""

CONFIG = {
    # ---- engine version (must equal the newest CHANGELOG entry) ----
    "version": "1.0.1",

    # ---- data ----
    # nflverse play-by-play, one parquet per season, from
    # https://github.com/nflverse/nflverse-data/releases/tag/pbp
    "seasons": list(range(2014, 2026)),
    "raw_dir": "data/raw",
    "pbp_url": "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet",

    # Validation: fit on these seasons, score on the rest. The shipped model is
    # then refit on every season.
    "holdout_seasons": [2024, 2025],

    # ---- rule era ----
    # Rules that change the value of a score (kickoff touchback spot, dynamic
    # kickoff) are measured from this season only. 2025 = touchback at the 35.
    "rules_season": 2025,
    # Points credited for a touchdown (6 + extra point). The 2025 PAT rate was
    # ~95%; the engine uses a whole 7 and says so in the white paper.
    "touchdown_points": 7,
    # Missed field goal: ball goes to the opponent at the spot of the kick
    # (line of scrimmage + 7), or their 20 if that is closer to their goal.
    "fg_snap_to_spot": 7,
    "fg_distance_add": 17,       # kick distance = yardline_100 + 17
    "missed_fg_min_spot": 20,
    # Longest attempt in the 2014-2025 data (70 yd). The make curve is not
    # trusted past the data, so longer kicks are "out of range".
    "fg_max_distance": 70,
    # Fair-catch kick (NFL Rule 11-4-3): after a fair catch the receiving team
    # may try a free-kick field goal from the catch spot (place or drop kick,
    # no rush, kick distance = spot + 10). If time expires during the punt, it is
    # an untimed down. The engine lets the opponent take it when this many
    # seconds or fewer remain after the punt (about one play's worth).
    "fair_catch_kick_window": 10,
    # A call whose margin is under this many WP points is shown as a toss-up.
    "tossup_margin": 0.01,

    # ---- win-probability model (gradient-boosted trees) ----
    "wp_trees": {
        "max_iter": 250,
        "learning_rate": 0.08,
        "max_leaf_nodes": 31,
        "min_samples_leaf": 200,
        "l2_regularization": 1.0,
    },

    # ---- kicker effect (empirical Bayes shrinkage) ----
    # Candidate prior SDs (accuracy, range) on the logit scale; the fit picks
    # the pair with the best hold-out log loss. (0, 0) = no kicker effect.
    "kicker_prior_grid": [[sa, sb] for sa in (0.0, 0.1, 0.2, 0.3, 0.4, 0.6)
                          for sb in (0.0, 0.05, 0.1, 0.2, 0.3)],
    # Replacement level (nflWAR rule, Yurko et al. 2019): in each season, rank
    # kickers by attempts; kicks by anyone outside the top 32 form one pooled
    # replacement curve. The fringe-career rule is kept as a sensitivity check.
    "replacement": {"rank_cutoff": 32},
    "replacement_fringe": {"max_attempts": 50, "first_season_min": 2015, "last_season_max": 2024},
    # Kickers listed in the app: at least this many attempts in these seasons.
    "kicker_list_seasons": [2024, 2025],
    "kicker_list_min_attempts": 10,
    "kicker_grade_min_attempts": 30,

    # ---- weather / stadium ----
    "precip_words": ["rain", "snow", "shower", "drizzle", "sleet", "flurr", "storm"],
    # Stadiums at high altitude (feet above sea level).
    "altitude_stadiums": {
        "DEN_HOME": 5280,    # Denver home games
        "Azteca": 7350,      # Estadio Azteca, Mexico City
    },
    "cold_threshold_f": 50,  # temperature below this counts as cold

    # ---- punt / gain distributions ----
    "quantiles": 20,         # points used to summarise each outcome distribution
    "togo_buckets": [1, 2, 4, 7, 11, 100],   # left edges: 1, 2-3, 4-6, 7-10, 11+
    "punt_bin_width": 5,     # yardline bins for punt results

    # ---- coach grading ----
    # Decisions graded: every 4th down called by a current head coach in these
    # seasons. 2026 is out of sample for the model (fit on `seasons`).
    "grade_seasons": list(range(2014, 2027)),
    "current_season": 2026,
    # The source misspells one name; display the correct one.
    "coach_aliases": {"Klint Kubliak": "Klint Kubiak"},
    # No letter grade below this many games as head coach in the data.
    "grade_min_games": 17,
    # The graded engine uses every factor: the coach knows his kicker, the
    # weather and the matchup.
    "grade_toggles": {"weather": True, "stadium": True, "spread": True, "kicker": True},
    "bootstrap_draws": 2000,      # resamples of a coach's calls for his CI
    # Whole-pipeline bootstrap (engine/bootstrap.py): replicate models, each
    # refit on games resampled with replacement.
    "bootstrap_models": 20,
    "bootstrap_seed": 2026,
    # A call counts as a confident mistake only when at least this share of
    # replicates rank another option above the coach's.
    "confident_share": 0.9,

    # ---- heatmap ----
    "map_max_togo": 15,
}
