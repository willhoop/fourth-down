# Contributing

This is a solo project. These rules keep it consistent.

## Before you change anything

Read the white paper (`docs/fourth-down-whitepaper.md`), sections 3–6, and the
risk register. Most changes touch a published figure.

## Every change, in one pass

1. Change the code. If you change `engine/decide.py`, make the same change in
   `app/engine.js` (and the reverse). The parity test fails if they differ.
2. Add or update tests. Derive expected values by hand on a stub model
   (`tests/conftest.py::make_stub`), never by copying current output.
3. Rebuild what the change touches (see
   `docs/how-to/rebuild-everything.md`): models, bootstrap, grades, reports,
   PDFs.
4. Run `py -m pytest tests -v`. All tests pass.
5. Write one `CHANGELOG.md` entry, bump `version` in `engine/config.py`, and set
   the date. Include the `### Record` section (Measured, Basis, Supersedes,
   Owed to the next major).
6. Run `py ../portfolio/build/check_projects.py`.

## Versions

- PATCH: no published figure moves.
- MINOR: a figure moves under the same method.
- MAJOR: the method moves, so old and new figures answer different questions.

A retraction never waits: a figure that is no longer true comes out of every
document in the same pass.

## Never

- Never commit `data/raw/`.
- Never edit generated files by hand: `app/model.js`, `app/bootstrap.js`,
  `app/grades.js`, `data/*.json`, `docs/reports/*.md`, `docs/fourth-down-deck.md`,
  or the generated block in the white paper.
- Never type a result figure into a document. Render it from the pipeline.
