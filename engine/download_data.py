"""Download nflverse play-by-play for every season the project uses.

Run:  py engine/download_data.py
Out:  data/raw/play_by_play_<season>.parquet  (~20 MB each)

Source: https://github.com/nflverse/nflverse-data/releases/tag/pbp
Existing files are skipped unless --force is given. The current season's file
grows every week, so re-download it with --force before regrading coaches.
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG              # noqa: E402
from load_data import ROOT             # noqa: E402


def main(force=False):
    out = os.path.join(ROOT, CONFIG["raw_dir"])
    os.makedirs(out, exist_ok=True)
    for season in sorted(set(CONFIG["seasons"]) | set(CONFIG["grade_seasons"])):
        path = os.path.join(out, f"play_by_play_{season}.parquet")
        if os.path.exists(path) and not force:
            print(f"{season}: have it")
            continue
        url = CONFIG["pbp_url"].format(season=season)
        print(f"{season}: downloading {url}")
        urllib.request.urlretrieve(url, path)


if __name__ == "__main__":
    main(force="--force" in sys.argv)
