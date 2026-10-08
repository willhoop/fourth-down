"""Load nflverse play-by-play and derive the columns every model uses.

All perspective-dependent columns are from the offence (posteam) side:
score_diff > 0 means the offence leads; spread > 0 means the offence is favoured.
"""
import os
import re
import numpy as np
import pandas as pd

from config import CONFIG

COLS = [
    "game_id", "play_id", "season", "season_type", "week", "home_team", "away_team",
    "posteam", "defteam", "qtr", "game_half", "down", "ydstogo", "yardline_100",
    "game_seconds_remaining", "half_seconds_remaining",
    "posteam_timeouts_remaining", "defteam_timeouts_remaining",
    "score_differential", "result", "spread_line", "total_line",
    "play_type", "yards_gained", "first_down", "touchdown", "penalty",
    "qb_kneel", "qb_spike", "fourth_down_converted", "fourth_down_failed",
    "field_goal_result", "kick_distance", "kicker_player_id", "kicker_player_name",
    "punt_blocked", "return_touchdown", "touchback",
    "roof", "surface", "temp", "wind", "weather", "stadium", "location",
    "wp", "two_point_attempt", "home_coach", "away_coach", "desc",
    "vegas_wp", "penalty_team", "first_down_penalty",
    "punt_fair_catch", "interception", "fumble_lost", "timeout", "timeout_team",
    "extra_point_result", "two_point_conv_result",
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse_weather(df):
    """Fill temp/wind from the free-text weather string; flag precipitation."""
    w = df["weather"].fillna("").str.lower()
    t = w.str.extract(r"temp:\s*(-?\d+)")[0].astype(float)
    wd = w.str.extract(r"wind:\s*[a-z]*\s*(\d+)\s*mph")[0].astype(float)
    calm = w.str.contains(r"wind:\s*calm")
    wd = wd.where(~calm, 0.0)
    df["temp_f"] = df["temp"].fillna(t)
    df["wind_mph"] = df["wind"].fillna(wd)
    pat = "|".join(CONFIG["precip_words"])
    # "0% chance of rain" style text would be a false hit; drop "chance" phrases.
    no_chance = ~w.str.contains("chance")
    df["precip"] = (w.str.contains(pat) & no_chance).astype(int)
    return df


def _stadium(df):
    indoor = df["roof"].isin(["dome", "closed"])
    df["indoor"] = indoor.astype(int)
    alt = np.zeros(len(df))
    alt[(df["home_team"] == "DEN") & (df["location"] == "Home")] = CONFIG["altitude_stadiums"]["DEN_HOME"]
    alt[df["stadium"].fillna("").str.contains("Azteca")] = CONFIG["altitude_stadiums"]["Azteca"]
    df["altitude_kft"] = alt / 1000.0
    # Indoors there is no wind, no precipitation, and a room temperature.
    df.loc[indoor, "wind_mph"] = 0.0
    df.loc[indoor, "temp_f"] = 70.0
    df.loc[indoor, "precip"] = 0
    return df


def load(seasons=None):
    seasons = seasons or CONFIG["seasons"]
    frames = []
    for s in seasons:
        p = os.path.join(ROOT, CONFIG["raw_dir"], f"play_by_play_{s}.parquet")
        frames.append(pd.read_parquet(p, columns=COLS))
    df = pd.concat(frames, ignore_index=True)
    df = _parse_weather(df)
    df = _stadium(df)

    # Opening-kickoff receiver: posteam on the first kickoff of the game.
    ko = df[(df["play_type"] == "kickoff") & (df["qtr"] == 1)].groupby("game_id")["posteam"].first()
    df["opening_receiver"] = df["game_id"].map(ko)
    df["receive_2h"] = ((df["game_half"] == "Half1") & (df["posteam"] != df["opening_receiver"])).astype(int)

    home = df["posteam"] == df["home_team"]
    df["home"] = home.astype(int)
    df["spread"] = np.where(home, df["spread_line"], -df["spread_line"])
    df["score_diff"] = df["score_differential"]
    df["second_half"] = (df["game_half"] == "Half2").astype(int)
    df["tmw_pending"] = ((df["qtr"].isin([1, 2, 3, 4])) & (df["half_seconds_remaining"] > 120)).astype(int)
    # Win label from the offence's view; ties are NaN and dropped where needed.
    margin = np.where(home, df["result"], -df["result"])
    df["win"] = np.where(margin > 0, 1.0, np.where(margin < 0, 0.0, np.nan))
    return df


def fill_outdoor_weather(df):
    """Impute missing outdoor wind/temp with the median; return count imputed."""
    out = df["indoor"] == 0
    n = int((out & (df["wind_mph"].isna() | df["temp_f"].isna())).sum())
    df.loc[out & df["wind_mph"].isna(), "wind_mph"] = df.loc[out, "wind_mph"].median()
    df.loc[out & df["temp_f"].isna(), "temp_f"] = df.loc[out, "temp_f"].median()
    return df, n
