"""Render every published figure from the pipeline's JSON. No figure is typed by hand.

Run:  py build/render_reports.py      (after fit_models.py, bootstrap.py, grade_coaches.py)
Out:  docs/reports/validation-report.md
      docs/reports/coach-grades.md
      docs/reports/kicker-grades.md
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
    return "\n".join(s)


# ---------------------------------------------------------------- coaches
def coach_rows(g):
    return [[c["grade"], c["coach"], ", ".join(c["teams"]), c["games"], c["decisions"], c["confident_mistakes"],
             f"{c['wins_lost_per_17']:.2f} [{17 * c['wp_lost_per_game_ci90'][0]:.2f}–{17 * c['wp_lost_per_game_ci90'][1]:.2f}]",
             f"{c['wins_lost_per_17_all_calls']:.2f}", pct(c["went_when_engine_said_go"], 0),
             f"{c['luck_total']:+.2f}"] for c in g["current"]]


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
         f"- Replacement-level kicker: {pct(k['replacement']['made_pct'])} made vs {pct(k['replacement']['expected_pct'])} expected; "
         f"{pct(k['replacement']['make_pct_50yd'], 0)} from 50 yd vs {pct(k['league_make_pct_50yd'], 0)} league average.",
         f"- Top current kickers by points over replacement per 100 kicks: " +
         "; ".join(f"{x['name']} {x['par_per_100']}" for x in kc[:3]) + ".",
         "",
         "Full tables: `docs/reports/validation-report.md`, `docs/reports/coach-grades.md`, `docs/reports/kicker-grades.md`.",
         END]
    return "\n".join(s)


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
