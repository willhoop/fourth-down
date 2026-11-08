"""Render every published figure from the pipeline's JSON. No figure is typed by hand.

Run:  py build/render_reports.py      (after fit_models.py, bootstrap.py, grade_coaches.py)
Out:  docs/reports/validation-report.md
      docs/reports/coach-grades.md
      docs/reports/kicker-grades.md
      docs/reports/prospect-theory.md
      the generated block inside docs/fourth-down-whitepaper.md

tests/test_reports.py re-renders and fails if any committed file is stale.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BEGIN, END = "<!-- BEGIN GENERATED RESULTS -->", "<!-- END GENERATED RESULTS -->"


def j(name):
    return json.load(open(os.path.join(ROOT, "data", name), encoding="utf-8"))


def pct(x, d=1):
    return "—" if x is None else f"{100 * x:.{d}f}%"


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


# ---------------------------------------------------------------- validation
def validation_md(v, m):
    wp = v["wp"]
    oc = v["coach_agreement"]["option_calibration"]
    kp = v["kicker_prior"]
    best = next(r for r in kp["grid"] if [r["sa"], r["sb"]] == kp["chosen"])
    none = next(r for r in kp["grid"] if r["sa"] == 0 and r["sb"] == 0)
    s = []
    s.append(f"Model version {v['version']}, built {v['built']}. Fit on {v['train_seasons'][0]}–{v['train_seasons'][-1]}; "
             f"scored on held-out seasons {', '.join(map(str, v['test_seasons']))} ({wp['games']} games). "
             "Splits are by season, so plays from one game never sit on both sides.")
    s.append("\n#### Win probability (every held-out snap)\n")
    s.append(table(["Model", "Plays", "Log loss", "Brier"], [
        ["This engine", f"{wp['engine']['n']:,}", wp["engine"]["log_loss"], wp["engine"]["brier"]],
        ["nflfastR `vegas_wp` (same plays; nflfastR was trained on them)", f"{wp['nflfastR_vegas_wp_same_plays']['n']:,}",
         wp["nflfastR_vegas_wp_same_plays"]["log_loss"], wp["nflfastR_vegas_wp_same_plays"]["brier"]],
        ["nflfastR `wp` without the spread", f"{wp['nflfastR_wp_no_spread_same_plays']['n']:,}",
         wp["nflfastR_wp_no_spread_same_plays"]["log_loss"], wp["nflfastR_wp_no_spread_same_plays"]["brier"]],
        ["Score-and-time-only logistic baseline", f"{wp['score_only_baseline']['n']:,}",
         wp["score_only_baseline"]["log_loss"], wp["score_only_baseline"]["brier"]],
        ["This engine, final 5 minutes only", f"{wp['final_5_min']['n']:,}", wp["final_5_min"]["log_loss"], wp["final_5_min"]["brier"]],
    ]))
    s.append("\nCalibration (predicted vs actual win rate by predicted-probability bin):\n")
    s.append(table(["Bin", "Plays", "Predicted", "Actual"],
                   [[r["bin"], f"{r['n']:,}", pct(r["predicted"]), pct(r["actual"])] for r in wp["calibration"]]))
    s.append("\n#### Option values (the test that matters for decisions)\n")
    s.append("For each held-out 4th down, the engine's win probability for the option the coach actually chose, "
             "against how often that team won:\n")
    s.append(table(["Coach chose", "Plays", "Engine predicted", "Actual win rate"],
                   [[k, oc[k]["n"], pct(oc[k]["predicted"]), pct(oc[k]["actual"])] for k in ("go", "fg", "punt")]))
    s.append("\n#### Conversion on 4th down\n")
    s.append(f"Log loss {v['conv']['base']['log_loss']} (n = {v['conv']['base']['n']}); with team strength "
             f"{v['conv']['spread']['log_loss']}.\n")
    s.append(table(["Yards to go", "Plays", "Predicted", "Actual"],
                   [[r["togo"], r["n"], pct(r["predicted"]), pct(r["actual"])] for r in v["conv"]["by_togo"]]))
    s.append("\n#### Field goals\n")
    s.append(table(["Factors", "Kicks", "Log loss", "Brier"],
                   [[k, v["fg"][k]["n"], v["fg"][k]["log_loss"], v["fg"][k]["brier"]]
                    for k in ("base", "weather", "stadium", "weather+stadium")]))
    s.append("\n" + table(["Distance", "Kicks", "Predicted", "Actual"],
                          [[r["distance"], r["n"], pct(r["predicted"]), pct(r["actual"])] for r in v["fg"]["by_distance"]]))
    era = v["fg_era"]
    s.append(f"\nKicking-era term chosen on the hold-out: **{era['chosen']}** "
             f"(log loss: " + ", ".join(f"{k} {r['log_loss']}" for k, r in era["candidates"].items()) + ").")
    s.append(f"\nKicker skill priors chosen on the hold-out: accuracy sd {kp['chosen'][0]}, range sd {kp['chosen'][1]}. "
             f"Log loss {none['log_loss']} with no kicker effect, {best['log_loss']} with it "
             f"(accuracy only: {kp['best_accuracy_only']['log_loss']}).")
    s.append("\n#### Punts\n")
    s.append(f"Mean absolute error of the predicted opponent start: **{v['punt']['mae_yards']} yd** "
             f"(n = {v['punt']['n']:,}), against {v['punt']['naive_mae_yards']} yd for a league-average guess.")
    ca = v["coach_agreement"]
    s.append("\n#### Agreement with coaches (descriptive)\n")
    s.append(f"On {ca['n']:,} sampled held-out 4th downs the engine's call matched the coach's {pct(ca['agreement'])} of the time. "
             f"Where the engine favored going by 2+ points ({ca['strong_go_n']} plays), coaches went {pct(ca['strong_go_coach_went'])} of the time.")
    s.append("\n#### Clock and rules measured from the data\n")
    s.append(table(["Event", "Seconds to next snap (normal)", "(final 2:00 of half)"],
                   [[k] + (v if isinstance(v, list) else ["—", v]) for k, v in m["clock"].items()]))
    s.append(f"\nKickoff: the receiving team starts at yardline_100 **{m['kickoff_start']}** on average under the "
             f"{m['rules']['season']} rules. Punt return TD rate {pct(m['punt']['return_td_rate'], 2)}; "
             f"muff recovered by the kicking team {pct(m['punt']['muff_rate'], 2)}.")
    s.append(f"\nWeather: outdoor wind or temperature imputed on {v['imputed_weather_plays']:,} plays after parsing the weather text.")
    e = j("edge_check.json")
    s.append("\n#### Edge calibration (does following the engine win as much more as it predicts?)\n")
    s.append("Graded 4th downs binned by the engine's predicted edge for going. In each bin, teams that went are "
             "compared with teams that kicked: the engine's predicted gap in win probability against the realized "
             "gap in win rate. Teams that went often knew something the engine cannot see, so the realized gap is "
             "biased toward going and the ratio is an upper bound on how much of the predicted edge is real.\n")
    s.append(table(["Predicted edge for going", "Went", "Kicked", "Predicted gap", "Actual gap", "Actual \u2212 predicted", "\u00b1 SE"],
                   [[r["edge_bin"], r["went"], r["kicked"], f"{100 * r['predicted_gap']:+.1f} pts",
                     f"{100 * r['actual_gap']:+.1f} pts", f"{100 * r['actual_minus_predicted']:+.1f} pts",
                     f"{100 * r['se']:.1f}"] for r in e["bins"]]))
    s.append(f"\nPooled (precision-weighted): actual minus predicted {100 * e['pooled_actual_minus_predicted']:+.1f} "
             f"\u00b1 {100 * e['pooled_se']:.1f} WP points. Games share outcomes, so the true uncertainty is larger.")
    return "\n".join(s)


# ---------------------------------------------------------------- coaches
def coach_rows(g, key="current"):
    return [[c["grade"], c["coach"], ", ".join(c["teams"]), c["games"], c["decisions"], c["confident_mistakes"],
             f"{c['wins_lost_per_17']:.2f} [{17 * c['wp_lost_per_game_ci90'][0]:.2f}–{17 * c['wp_lost_per_game_ci90'][1]:.2f}]",
             f"{c['wins_lost_per_17_all_calls']:.2f}", pct(c["went_when_engine_said_go"], 0),
             f"{c['luck_total']:+.2f}"] for c in g[key]]


COACH_HEAD = ["Grade", "Coach", "Team(s)", "Games", "4th downs", "Confident mistakes",
              "Wins lost / 17 games [90% CI]", "All disagreements / 17", "Went when engine said go", "Luck (wins)"]


def coaches_md(g):
    s = [f"# Head coaches vs the engine\n",
         f"Version {g['version']}. Generated by `build/render_reports.py` from `data/coach_grades.json`. "
         f"Method: white paper, section 5.\n",
         f"{g['decisions']:,} fourth downs, {g['seasons'][0]}–{g['seasons'][-1]}. The model is fit on "
         f"{g['model_fit_seasons'][0]}–{g['model_fit_seasons'][-1]}; {g['seasons'][-1]} calls are out of sample. "
         f"Grades rank each coach's confident-mistake cost per game against all {g['coaches_in_reference']} head coaches "
         "with at least 17 games in the data. Luck is what happened after the coach's calls minus what those calls were "
         "expected to produce; it says nothing about decision quality.\n",
         table(COACH_HEAD, coach_rows(g)),
         f"\n## Recent seasons only ({g['recent_from']}–{g['seasons'][-1]})\n",
         f"The same grading, using only calls from {g['recent_from']} on and ranking against the "
         f"{g['coaches_in_reference_recent']} head coaches with a full season in that window, so a long career "
         "is not judged by an earlier era's norms. The app shows this view by default.\n",
         table(COACH_HEAD, coach_rows(g, "current_recent")),
         "\n## League trend\n",
         table(["Season", "4th downs", "Coaches went", "Engine clearly says go", "Agreement",
                "Wins lost / team-season (confident)", "(all disagreements)", "Share of calls confident"],
               [[r["season"], r["decisions"], pct(r["go_rate"]), pct(r["engine_go_rate"]), pct(r["agree"]),
                 f"{r['wins_lost_per_team_season_confident']:.2f}", f"{r['wins_lost_per_team_season_all']:.2f}",
                 pct(r["confident_share_of_calls"])] for r in g["league_by_season"]]),
         "\n## Each coach: the calls played twice\n"]
    for c in g["current"]:
        rp = c["replay"]
        s.append(f"### {c['coach']} — {c['grade']}\n")
        s.append(f"{c['decisions']} fourth downs in {c['games']} games ({c['first_season']}–{c['last_season']}). "
                 f"Went for it {pct(c['go_rate'], 0)}; the engine would have gone {pct(c['engine_go_rate'], 0)}. "
                 f"Agreed on {pct(c['agree'], 0)} of calls. {c['confident_mistakes']} confident mistakes "
                 f"({', '.join(f'{k} ×{n}' for k, n in c['confident_mistake_kinds'].items()) or 'none'}).")
        if rp["n"]:
            s.append(f"\nOn the {rp['n']} disagreements, his calls were expected to leave a {pct(rp['coach_expected'])} "
                     f"average win chance and the engine's {pct(rp['engine_expected'])}. "
                     f"After his calls the team actually stood at {pct(rp['coach_realized'])}.")
        if c["worst_calls"]:
            s.append("\nCostliest calls:\n")
            for w in c["worst_calls"][:3]:
                s.append(f"- {w['season']} wk {w['week']} {w['team']} vs {w['opp']}, {w['situation']}: "
                         f"{w['coach_call']} (engine: {w['engine_call']}), cost {100 * w['cost']:.1f} WP pts, "
                         f"{round(100 * w['confidence'])}% of replicates agree.")
        s.append("")
    return "\n".join(s)


# ---------------------------------------------------------------- kickers
def kickers_md(k):
    r = k["replacement"]
    cur = sorted([x for x in k["kickers"] if x["current"]], key=lambda x: -x["par_per_100"])
    s = [f"# Kicker grades\n",
         f"Version {k['version']}. Generated by `build/render_reports.py` from `data/kickers.json`. Method: white paper, section 4.\n",
         f"Replacement level ({r['rule']}): {r['kicker_seasons']} kicker-seasons, {r['attempts']} kicks, "
         f"{pct(r['made_pct'])} made against {pct(r['expected_pct'])} expected; {pct(r['make_pct_50yd'], 0)} from 50 yd "
         f"against {pct(k['league_make_pct_50yd'], 0)} for an average kicker. Sensitivity rule "
         f"({k['replacement_sensitivity']['rule']}): {pct(k['replacement_sensitivity']['made_pct'])} made, "
         f"{pct(k['replacement_sensitivity']['make_pct_50yd'], 0)} from 50 yd.\n",
         f"Grades: {k['grade_rule']}.\n",
         table(["Grade", "Kicker", "Seasons", "Att.", "FG%", "Expected", "Makes over exp.", "Make % 50", "Make % 55",
                "50% range", "Pts over repl. / 100", "Career pts over repl."],
               [[x["grade"], x["name"], f"{x['first_season']}–{x['last_season']}", x["attempts"], pct(x["fg_pct"]),
                 pct(x["expected_pct"]), f"{x['fgoe']:+}", pct(x["make_pct_50yd"], 0), pct(x["make_pct_55yd"], 0),
                 "70+" if x["fifty_pct_distance"] is None else f"{x['fifty_pct_distance']} yd",
                 x["par_per_100"], x["points_above_replacement"]] for x in cur])]
    return "\n".join(s)


# ---------------------------------------------------------------- white paper block
def paper_block(v, m, g, k):
    wp, oc = v["wp"], v["coach_agreement"]["option_calibration"]
    cur = g["current"]
    graded = [c for c in cur if c["grade"] != "Incomplete"]
    top = sorted(graded, key=lambda c: c["wp_lost_per_game"])[:3]
    bot = sorted(graded, key=lambda c: -c["wp_lost_per_game"])[:3]
    lg = g["league_by_season"]
    first, last = lg[0], [r for r in lg if r["season"] == max(g["model_fit_seasons"])][0]
    kc = sorted([x for x in k["kickers"] if x["current"]], key=lambda x: -x["par_per_100"])
    s = [BEGIN,
         "<!-- Rendered by build/render_reports.py from data/*.json. Do not edit by hand. -->\n",
         "**Headline results**\n",
         f"- Win-probability log loss on held-out {', '.join(map(str, v['test_seasons']))}: **{wp['engine']['log_loss']}** "
         f"(nflfastR `vegas_wp` on the same {wp['engine']['n']:,} plays: {wp['nflfastR_vegas_wp_same_plays']['log_loss']}).",
         f"- Option values on held-out 4th downs, predicted vs actual win rate: go {pct(oc['go']['predicted'])} vs "
         f"{pct(oc['go']['actual'])} (n = {oc['go']['n']}); field goal {pct(oc['fg']['predicted'])} vs {pct(oc['fg']['actual'])} "
         f"(n = {oc['fg']['n']}); punt {pct(oc['punt']['predicted'])} vs {pct(oc['punt']['actual'])} (n = {oc['punt']['n']}).",
         f"- League cost of 4th-down calls, confident mistakes only: **{first['wins_lost_per_team_season_confident']:.2f}** wins "
         f"per team-season in {first['season']}, **{last['wins_lost_per_team_season_confident']:.2f}** in {last['season']}. "
         f"Counting every disagreement: {first['wins_lost_per_team_season_all']:.2f} and {last['wins_lost_per_team_season_all']:.2f}.",
         f"- Coaches went for it on {pct(first['go_rate'])} of 4th downs in {first['season']} and {pct(last['go_rate'])} in "
         f"{last['season']}; the engine clearly favored going (edge of 1 point or more) on {pct(first['engine_go_rate'])} "
         f"and {pct(last['engine_go_rate'])}.",
         f"- Share of 4th downs that are toss-ups (edge under 1 WP point), {lg[0]['season']}–{lg[-1]['season']}: "
         f"{pct(min(r['engine_tossup_share'] for r in lg))} to {pct(max(r['engine_tossup_share'] for r in lg))}. "
         f"Share of calls the bootstrap is confident about: {pct(min(r['confident_share_of_calls'] for r in lg))} to "
         f"{pct(max(r['confident_share_of_calls'] for r in lg))}.",
         f"- Current head coaches with the lowest confident-mistake cost: " +
         "; ".join(f"{c['coach']} {c['wins_lost_per_17']:.2f} wins/17 games ({c['grade']})" for c in top) + ".",
         f"- Highest: " + "; ".join(f"{c['coach']} {c['wins_lost_per_17']:.2f} ({c['grade']})" for c in bot) + ".",
         (lambda rec: f"- Recent seasons only ({g['recent_from']} on), lowest cost: " +
          "; ".join(f"{c['coach']} {c['wins_lost_per_17']:.2f} ({c['grade']})" for c in rec[:3]) + ".")(
             sorted([c for c in g["current_recent"] if c["grade"] != "Incomplete"], key=lambda c: c["wp_lost_per_game"])),
         (lambda e: f"- Edge check: relative to teams that kicked, teams that went did "
          f"{100 * e['pooled_actual_minus_predicted']:+.1f} ± {100 * e['pooled_se']:.1f} WP points versus the engine's "
          f"prediction (negative = the engine overstates going; selection flatters going, so near zero does not clear it).")(j("edge_check.json")),
         f"- Replacement-level kicker: {pct(k['replacement']['made_pct'])} made vs {pct(k['replacement']['expected_pct'])} expected; "
         f"{pct(k['replacement']['make_pct_50yd'], 0)} from 50 yd vs {pct(k['league_make_pct_50yd'], 0)} league average.",
         f"- Top current kickers by points over replacement per 100 kicks: " +
         "; ".join(f"{x['name']} {x['par_per_100']}" for x in kc[:3]) + ".",
         "",
         "Full tables: `docs/reports/validation-report.md`, `docs/reports/coach-grades.md`, `docs/reports/kicker-grades.md`.",
         END]
    return "\n".join(s)


def prospect_md(p):
    L, h, r = p["league"], p["holdout"], p["readouts"]
    ci = L["ci95"]
    rows = [[f"{e['from']}-{e['to']}", f"{e['n']:,}", e["gamma"], e["lambda"], e["alpha"]] for e in p["eras"]]
    last = max(x["last_season"] for x in p["coaches"])
    cur = [c for c in p["coaches"] if c["last_season"] == last]
    crow = [[c["coach"], c["decisions"], f"{c['lambda']:.2f}", f"{c['lo']:.2f}-{c['hi']:.2f}", f"{c['raw_lambda']:.2f}",
             "few calls" if c["few_calls"] else ""] for c in cur]
    hm = lambda name, key: [name, pct(h[key]["accuracy"]), h[key]["log_loss"]]
    return "\n".join([
        "# Prospect-theory fit: fear of failing",
        "",
        "<!-- Rendered by build/render_reports.py from data/prospect.json. Do not edit by hand. -->",
        "",
        "## Method",
        "",
        f"Every 4th down {p['seasons'][0]}-{p['seasons'][1]} without overtime (n = {p['n']:,} in {p['games']:,} games). "
        "The engine prices each option as a gamble: going for it converts with chance p (WP after success, WP after "
        "failure); a field goal is made with chance p; a punt is a sure thing. Outcomes are measured from "
        f"the {p['reference']}, in units of {round(p['unit_wp'] * 100)} WP points. A logit choice model with "
        "Prelec weighting w(p) = exp(-(-ln p)^gamma) and value x^alpha (gains), -lambda(-x)^alpha (losses) is fit by "
        "maximum likelihood (Tversky & Kahneman 1992; Whittaker 2026). gamma = lambda = alpha = 1 is the computer.",
        "",
        "Each coach: lambda only, with the league's gamma, alpha and tau; standard error clustered by game; shrunk "
        f"toward the league by empirical Bayes (prior sd of log lambda {p['shrinkage']['prior_sd_log_lambda']}, "
        f"from {p['shrinkage']['coaches_used']} coaches with 100+ calls).",
        "",
        "## League",
        "",
        table(["Parameter", "Fit", f"95% range ({L['bootstrap_reps']} game-resampled refits)", "Computer"], [
            ["gamma (calibration)", L["gamma"], f"{ci['gamma'][0]}-{ci['gamma'][1]}", 1],
            ["lambda (fear of failing)", L["lambda"], f"{ci['lambda'][0]}-{ci['lambda'][1]}", 1],
            ["alpha (value of big gains)", L["alpha"], f"{ci['alpha'][0]}-{ci['alpha'][1]}", 1]]),
        "",
        f"Read as: a 51% chance feels like {pct(r['feels_51'], 0)}, 85% like {pct(r['feels_85'], 0)}, 10% like "
        f"{pct(r['feels_10'], 0)}. A failed 4th down weighs {L['lambda']:.1f} times a conversion of the same size "
        f"(lab median for people: {r['lab_lambda']}). A gain 4 times as big feels {r['gain_4_vs_1']} times as good.",
        "",
        "## By era",
        "",
        table(["Seasons", "Decisions", "gamma", "lambda", "alpha"], rows),
        "",
        "## Hold-out test",
        "",
        f"Fit on {h['fit_seasons'][0]}-{h['fit_seasons'][1]}, scored on {h['test_seasons'][0]}-{h['test_seasons'][1]} "
        f"(n = {h['n']:,}). The second model adds a constant preference for each kick, so prospect theory cannot win "
        "only by learning that coaches like to kick.",
        "",
        table(["Model", "Calls predicted", "Log loss"], [hm("Computer (expected WP)", "computer"),
              hm("Computer that likes kicking", "computer_likes_kicking"), hm("Prospect theory", "prospect")]),
        "",
        f"## Coaches in {last}",
        "",
        table(["Coach", "Calls", "Fear of failing", "95% range", "Own calls only", ""], crow),
        "",
        "## What these numbers do not prove",
        "",
        "- That coaches feel fear. The fit describes choices, not beliefs or motives.",
        "- That the engine is right. lambda grows when coaches pass on the engine's go calls; if the engine "
        "overrates going for it, that error is counted as fear (risk 21).",
        "- That the reference point is right. Another reference (the WP before the snap) would move lambda (ADR-0004).",
        "- That the figures match Whittaker (2026): another WP model, reference point and estimator. That study "
        "reports gamma 0.34, lambda 1.42, alpha 0.30 with no error ranges.",
        "- That one coach differs from another unless their 95% ranges do not overlap.",
    ]) + "\n"


def render_all(write=True):
    v, m, g, k = j("validation.json"), j("model.json"), j("coach_grades.json"), j("kickers.json")
    files = {
        "docs/reports/validation-report.md": f"# Validation report\n\n{validation_md(v, m)}\n\n"
        "## What these numbers do not prove\n\n"
        "- That following the engine wins more games. Option values are calibrated on average, which is necessary, "
        "not sufficient. No randomized test of 4th-down policy exists.\n"
        "- That any single call is right. See the bootstrap confidence for that call.\n"
        "- Anything about seasons with different rules. The kickoff spot is measured from one rule season.\n"
        "- That short-yardage conversion is unbiased. Yards to go is a whole number (Lopez 2020; risk 1).\n",
        "docs/reports/coach-grades.md": coaches_md(g) + "\n",
        "docs/reports/kicker-grades.md": kickers_md(k) + "\n",
        "docs/reports/prospect-theory.md": prospect_md(j("prospect.json")),
    }
    paper = os.path.join(ROOT, "docs", "fourth-down-whitepaper.md")
    text = open(paper, encoding="utf-8").read()
    pat = re.compile(re.escape(BEGIN) + ".*?" + re.escape(END), re.S)
    files["docs/fourth-down-whitepaper.md"] = pat.sub(lambda _: paper_block(v, m, g, k), text)
    if write:
        for rel, body in files.items():
            with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(body)
    return files


if __name__ == "__main__":
    for rel in render_all():
        print("wrote", rel)
