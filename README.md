# Fourth Down Engine

Go for it, kick a field goal, or punt? This engine answers with each option's
chance to win the game, learned from every NFL play since 2014. It weighs the
score, clock, field position, yards to go, both teams' timeouts, the two-minute
warning and the second-half kickoff. Weather, stadium, team strength and your
actual kicker are each a switch. It shows how sure it is, grades every current
head coach by replaying each of his fourth downs both ways, and grades every
kicker against a replacement-level kicker.

**Use it online (phone or PC):** https://willhoop.github.io/fourth-down/

**Or locally:** double-click **Fourth Down Engine** on the desktop, or open
`app/index.html`. No install, no internet.

Version 1.2.1. Results and figures: [white paper](docs/fourth-down-whitepaper.md).

## Components

| Component | What it is |
|---|---|
| [app/index.html](app/index.html) | The app: Decision, Coaches, Kickers and About tabs. |
| [app/engine.js](app/engine.js) | Decision engine run by the app. |
| [engine/decide.py](engine/decide.py) | Python reference engine (same results; CI checks parity). |
| [engine/config.py](engine/config.py) | The one configuration block: seasons, rules, settings. |
| [engine/fit_models.py](engine/fit_models.py) | Fits win probability, conversion, field goal, punt, clock and kicker models; validates on held-out seasons. |
| [engine/bootstrap.py](engine/bootstrap.py) | Refits everything on 20 resampled sets of games, for confidence. |
| [engine/grade_coaches.py](engine/grade_coaches.py) | Plays every fourth down twice and grades head coaches. |
| [engine/kickers.py](engine/kickers.py) | Kicker accuracy, range and replacement level. |
| [engine/weekly.py](engine/weekly.py) | This season's costliest and best 4th-down calls, by week (updated every Tuesday by a GitHub Action). |
| [engine/edge_check.py](engine/edge_check.py) | Checks whether teams that followed the engine won as much more as it predicted. |
| [build/render_reports.py](build/render_reports.py) | Renders every published figure from the pipeline output. |
| [build/build_docs.py](build/build_docs.py) | Builds the PDFs and the deck. |
| [docs/fourth-down-whitepaper.md](docs/fourth-down-whitepaper.md) | White paper: method, math, results, sources. |
| [build/fourth-down-deck.pdf](build/fourth-down-deck.pdf) | Plain-English deck. |
| [docs/README.md](docs/README.md) | Technical documentation (Diátaxis, ASD-STE100). |
| [docs/reports/](docs/reports/) | Validation report, coach grades, kicker grades (generated). |
| [docs/adr/](docs/adr/) | Architecture decision records. |
| [RISK_REGISTER.md](RISK_REGISTER.md) | Risks, including accepted ones. |
| [tests/](tests/) | Hand-derived engine tests, shipped-model checks, Python/JS parity, report freshness. |

## Data

nflverse play-by-play ([nflverse-data](https://github.com/nflverse/nflverse-data/releases/tag/pbp)),
2014–2025 for fitting, 2014–2026 for grading. Raw files are not committed;
`py engine/download_data.py` fetches them. See
[docs/how-to/rebuild-everything.md](docs/how-to/rebuild-everything.md).

## License

MIT. See [LICENSE](LICENSE).
