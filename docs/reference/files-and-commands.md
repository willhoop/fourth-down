# Reference: files and commands

## Folders

| Folder | Contents |
|---|---|
| `app/` | The app. `index.html` (page), `engine.js` (engine), `model.js`, `bootstrap.js`, `grades.js` (generated data). |
| `engine/` | Python pipeline: config, data loading, model fitting, bootstrap, coach grading, reference engine. |
| `build/` | `grade.js` (scores decisions in Node), `render_reports.py`, `build_docs.py`, generated PDFs and deck. |
| `data/` | Generated JSON. `raw/` holds the downloaded parquet files (not in git). |
| `docs/` | White paper, deck source, this documentation, ADRs, generated reports. |
| `tests/` | pytest suite. |
| `assets/` | App icon. |

## Commands

| Command | Reads | Writes | Time |
|---|---|---|---|
| `py engine/download_data.py [--force]` | GitHub (nflverse) | `data/raw/*.parquet` | 1 min |
| `py engine/fit_models.py` | `data/raw/` | `app/model.js`, `data/model.json`, `data/validation.json`, `data/kickers.json` | 1 min |
| `py engine/bootstrap.py` | `data/raw/`, `data/model.json` | `app/bootstrap.js` | 5–20 min |
| `py engine/grade_coaches.py` | `data/raw/`, `app/model.js`, `app/bootstrap.js`, `data/kickers.json` | `data/coach_grades.json`, `app/grades.js` | ~10 min |
| `py build/render_reports.py` | `data/*.json` | `docs/reports/*.md`, results block in the white paper | 1 s |
| `py build/build_docs.py` | `docs/*.md` | `build/*.pdf`, `docs/fourth-down-deck.pptx`, `docs/fourth-down-deck.md` | 30 s |
| `py -m pytest tests -v` | `app/model.js`, `engine/`, `data/*.json` | — | 20 s |

## Generated files — do not edit by hand

`app/model.js`, `app/bootstrap.js`, `app/grades.js`, `data/*.json`,
`docs/reports/*.md`, `docs/fourth-down-deck.md`, and the block between the `GENERATED RESULTS` markers in
the white paper.
