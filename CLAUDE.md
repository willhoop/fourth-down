# CLAUDE.md — fourth-down engine

Fast orientation for an agent. Not a replacement for the docs.

## What this is

An NFL 4th-down decision engine (go / field goal / punt) by win probability,
plus coach and kicker grades. Method and every figure: `docs/fourth-down-whitepaper.md`.
User opens it from the desktop shortcut (`app/index.html`); he prefers
double-click over commands.

## Pipeline order (each step reads the previous one's output)

1. `py engine/download_data.py` — raw nflverse parquet to `data/raw/` (gitignored).
2. `py engine/fit_models.py` — `app/model.js`, `data/model.json`, `data/validation.json`, `data/kickers.json`.
3. `py engine/bootstrap.py` — `app/bootstrap.js` (20 replicates).
4. `py engine/grade_coaches.py` — `data/coach_grades.json`, `app/grades.js` (uses node + `build/grade.js`).
5. `py build/render_reports.py` — `docs/reports/*.md` and the generated block in the white paper.
6. `py build/build_docs.py` — PDFs and deck in `build/` (headless Edge; WeasyPrint has no GTK here).
7. `py -m pytest tests -v`.

If step 2 changes the model, redo 3–7. `fit_models.py` is deterministic; a
refit with no model change leaves `app/model.js` byte-identical.

## Gotchas

- `engine/decide.py` and `app/engine.js` must stay identical in logic.
  `tests/test_shipped_model.py::test_python_and_js_engines_agree` enforces it.
- All settings that change over time live in `CONFIG` (`engine/config.py`).
- The kickoff spot is measured from `rules_season`; validation passes full
  data for it (it is a rule, not an outcome). A NaN here once put kickoffs at
  the 1-yard line.
- Field goals over `fg_max_distance` (70) are out of range; the quadratic curve
  rises past ~83 yd.
- Coach names: nflverse misspells "Klint Kubliak"; fixed via `coach_aliases`.
- Headless Edge needs `--user-data-dir` set to a temp folder, or it hands off to
  the user's open Edge and prints nothing.
- The user's global rule: never open files in the sidebar preview; give paths.

## Where things stand

Printed by the pipeline, not typed here: see `CHANGELOG.md` and `docs/reports/`.
