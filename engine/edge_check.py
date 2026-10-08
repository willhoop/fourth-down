"""Edge calibration: does following the engine win as much more as it predicts?

For each graded 4th down the engine predicts the WP of every option. Among
decisions with the same predicted edge for going (WP_go minus the best kick),
some coaches went and some kicked. If the engine's edges are right, teams that
went should beat teams that kicked by about the predicted edge, after allowing
for the gap in the engine's own expected WP of the two choices. If the realized
gap is smaller, the engine overstates the value of going (risk 14).

Comparison: in each edge bin, (actual win rate of goers - actual of kickers)
against (mean predicted WP of goers' choice - mean predicted WP of kickers'
choice). Teams that went often knew something the engine cannot see (a true
4th & inches, a hurt defender), which pushes goers' real results up. So the
realized gap is biased toward going, and the ratio realized / predicted is an
UPPER bound on how much of the engine's predicted edge is real.

Run:  py engine/edge_check.py      (after engine/grade_coaches.py)
Out:  data/edge_check.json
"""
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import CONFIG     # noqa: E402
from load_data import ROOT    # noqa: E402

BINS = [-1.0, 0.0, 0.01, 0.02, 0.04, 0.08, 1.0]


def main():
    d = pd.read_csv(os.path.join(ROOT, "data", "decisions.csv.gz"))
    d = d[d["win"].notna()].copy()
    d["kick"] = d[["wp_fg", "wp_punt"]].max(axis=1)
    d["edge_go"] = d["wp_go"] - d["kick"]
    d["went"] = (d["choice"] == "go").astype(int)
    d["pred_choice"] = np.where(d["went"] == 1, d["wp_go"],
                                np.where(d["choice"] == "fg", d["wp_fg"], d["wp_punt"]))
    d["bin"] = pd.cut(d["edge_go"], BINS)
    rows, num, den = [], 0.0, 0.0
    for b, g in d.groupby("bin", observed=True):
        go, kk = g[g["went"] == 1], g[g["went"] == 0]
        if len(go) < 30 or len(kk) < 30:
            continue
        pred_gap = go["pred_choice"].mean() - kk["pred_choice"].mean()
        act_gap = go["win"].mean() - kk["win"].mean()
        # cluster-free SE of a difference of means (games share outcomes, so this is optimistic)
        se = np.sqrt(go["win"].var() / len(go) + kk["win"].var() / len(kk))
        rows.append({"edge_bin": str(b), "went": int(len(go)), "kicked": int(len(kk)),
                     "predicted_gap": round(float(pred_gap), 4), "actual_gap": round(float(act_gap), 4),
                     "se": round(float(se), 4)})
        rows[-1]["actual_minus_predicted"] = round(float(act_gap - pred_gap), 4)
        w = 1.0 / se ** 2               # pool bins by precision
        num += w * (act_gap - pred_gap)
        den += w
    pooled = num / den if den else None
    out = {"version": CONFIG["version"], "bins": rows,
           "pooled_actual_minus_predicted": round(pooled, 4) if den else None,
           "pooled_se": round(den ** -0.5, 4) if den else None,
           "reading": "Negative means teams that went did worse, relative to teams that kicked, than the engine predicted (the engine overstates going).",
           "note": "Teams that went often knew something the engine cannot see, which flatters going; a result near zero does not clear the engine."}
    with open(os.path.join(ROOT, "data", "edge_check.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
