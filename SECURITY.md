# Security policy

## Scope

This is a personal research project. It has no server, no database, no user
accounts and no network calls at run time. The app (`app/index.html`) runs
entirely in the browser from local files. The Python pipeline runs locally
and makes one kind of network call: `engine/download_data.py` downloads
public nflverse parquet files from GitHub.

## Reporting a vulnerability

Email **willjhooper@msn.com** with a description and steps to reproduce. This
is a solo project; allow reasonable time for a reply.

## Data handling

- The app stores only the last open tab in `localStorage`. Nothing leaves the
  browser.
- No personal data is collected, stored or sent.
- Raw play-by-play is not committed or redistributed (see
  `docs/adr/0001-data-source.md`).

## Supply chain

- The app loads no external scripts. Every script is a local file.
- Python dependencies: pandas, pyarrow, numpy, scikit-learn, pytest. Pin them
  if you build a release you need to reproduce exactly.
- Downloaded parquet files are data, read with pyarrow; never execute them.
