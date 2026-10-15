"""Tables for overtime and onside kicks, measured from play-by-play.

Overtime has too few games (about 190 since 2014) to fit its own win model, so
the engine values overtime from its rules plus drive results measured in every
game:

- ot_drive.td / ot_drive.fg: chance that a drive with a first down at a spot
  (5-yard bins of yardline_100) ends in a touchdown / a field goal
- ot_drive.poss_secs: mean length of a possession, in seconds
- ot_drive.next_start: mean spot (yardline_100) where a team starts after the
  other team's drive ends without a score

Onside kicks: the recovery rate by rules era (surprise kicks allowed before
2018; 2018 kickoff rules; 2024 dynamic kickoff, declared kicks only), and the
mean spot of the next snap after a recovered / a lost onside kick.

Used by fit_models.py; run alone to print the tables:  py engine/fit_ot.py
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG                                  # noqa: E402
from load_data import pbp_path                             # noqa: E402

COLS = ["game_id", "play_id", "season", "drive", "qtr", "down", "ydstogo", "yardline_100", "play_type",
        "half_seconds_remaining", "fixed_drive_result", "drive_time_of_possession", "desc",
        "kickoff_attempt", "own_kickoff_recovery", "posteam"]
BIN = 5
ONSIDE_ERAS = [(2014, 2017), (2018, 2023), (2024, 2100)]


def load(seasons):
    return pd.concat([pd.read_parquet(pbp_path(s), columns=COLS) for s in seasons], ignore_index=True)


def mmss(x):
    try:
        m, s = str(x).split(":")
        return int(m) * 60 + int(s)
    except ValueError:
        return np.nan


def ot_drive(p):
    first = p[(p["down"] == 1) & p["play_type"].isin(["run", "pass"]) & (p["half_seconds_remaining"] > 180)
              & p["fixed_drive_result"].notna()]
    b = ((first["yardline_100"].clip(1, 99) - 1) // BIN).astype(int)
    res = first["fixed_drive_result"]
    g = pd.DataFrame({"b": b, "td": res.eq("Touchdown"), "fg": res.eq("Field goal")}).groupby("b").mean()
    g = g.reindex(range(int(np.ceil(99 / BIN))))
    g = g.interpolate().bfill().ffill()
    drives = p.dropna(subset=["drive"]).groupby(["game_id", "drive"]).agg(
        secs=("drive_time_of_possession", lambda s: mmss(s.iloc[0])), res=("fixed_drive_result", "first"),
        start=("yardline_100", "first"), hs=("half_seconds_remaining", "first"))
    full = drives[drives["hs"] > 300]
    nxt = drives.groupby(level=0)["start"].shift(-1)          # where the next drive in the game starts
    after_empty = nxt[drives["res"].isin(["Punt", "Turnover", "Turnover on downs"]) & (drives["hs"] > 300)]
    return {"bin": BIN, "td": [round(float(x), 4) for x in g["td"]], "fg": [round(float(x), 4) for x in g["fg"]],
            "poss_secs": round(float(full["secs"].mean()), 1),
            "next_start": round(float(after_empty.mean()), 1),
            "max_possessions": CONFIG["ot_max_possessions"],
            "n_first_downs": int(len(first))}


def onside(p):
    k = p[p["kickoff_attempt"] == 1].copy()
    k = k[k["desc"].str.contains("onside", case=False, na=False)]
    k["rec"] = k["own_kickoff_recovery"].fillna(0)
    # the next snap's spot, from the side of the team that has the ball
    p = p.sort_values(["game_id", "play_id"])
    scrim = p[p["play_type"].isin(["run", "pass", "punt", "field_goal", "qb_kneel", "qb_spike"])]
    k = pd.merge_asof(k.sort_values("play_id"), scrim[["game_id", "play_id", "yardline_100"]]
                      .rename(columns={"play_id": "nx_id", "yardline_100": "nx_yl"}).sort_values("nx_id"),
                      left_on="play_id", right_on="nx_id", by="game_id", direction="forward")
    rates = []
    for lo, hi in ONSIDE_ERAS:
        e = k[(k["season"] >= lo) & (k["season"] <= hi)]
        if len(e):
            rates.append({"from": lo, "to": hi, "rate": round(float(e["rec"].mean()), 4), "n": int(len(e))})
    return {"by_era": rates,
            "recovered_yl": round(float(k.loc[k["rec"] == 1, "nx_yl"].mean()), 1),
            "lost_yl": round(float(k.loc[k["rec"] == 0, "nx_yl"].mean()), 1)}


def onside_rate(tables, season):
    for e in tables["by_era"]:
        if e["from"] <= season <= e["to"]:
            return e["rate"]
    return tables["by_era"][-1]["rate"]


def tables(seasons=None):
    p = load(seasons or CONFIG["seasons"])
    return ot_drive(p), onside(p)


if __name__ == "__main__":
    import json
    a, b = tables()
    print(json.dumps({"ot_drive": a, "onside": b}, indent=1))
