# Reference: engine API

The Python engine (`engine/decide.py`) and the JavaScript engine
(`app/engine.js`) have the same functions and give the same numbers.

## decide(model, state, toggles)

Returns the win probability of each option and the call.

**state** (all numbers):

| Key | Meaning |
|---|---|
| `score_diff` | Our score minus their score. |
| `qtr` | Quarter, 1–4. |
| `half_seconds` | Seconds left in the half (1–1800). |
| `yardline` | Yards to the opponent's goal line (1–99). |
| `ydstogo` | Yards to go (1 or more, not more than `yardline`). |
| `down` | 1–4. Default 4. On 1–3 the options are a play (`go`) and a field goal; `punt` is null. |
| `pos_to`, `def_to` | Our timeouts, their timeouts (0–3). |
| `home` | 1 if we are the home team. |
| `receive_2h` | 1 if we receive the second-half kickoff (first half only). |
| `spread` | Points we are favored by (team-strength factor). |
| `wind`, `temp`, `precip` | mph, °F, 0 or 1 (weather factor). |
| `indoor`, `altitude_kft` | 0 or 1; thousands of feet (stadium factor). |
| `kicker_a`, `kicker_b` | Kicker accuracy and range (kicker factor). |

**toggles**: `{weather, stadium, spread, kicker}`, each true or false.

**Returns**:

```
{ wp: {go, fg, punt},        // fg is null when the kick is over 70 yd
  best: "go" | "fg" | "punt",
  margin: number,            // best minus second best, in WP (0-1)
  tossup: boolean,           // margin < tossup_margin
  detail: { go: {p_convert, wp_if_convert, wp_if_fail},
            fg: {p_make, wp_if_make, wp_if_miss, distance},
            punt: {opp_yardline_mean, p_return_td, p_muff, fair_catch_kick_risk} } }
// on downs 1-3, detail.go is {p_convert (first down), wp_if_convert, wp_if_fail, p_turnover}
```

## Other functions

| Python / JavaScript | Returns |
|---|---|
| `wp_raw` / `wpRaw` | WP for the team with the ball in snap state `s`. |
| `p_convert` / `pConvert` | Conversion probability. |
| `p_field_goal` / `pFieldGoal` | Make probability. |
| `punt_spots` / `puntSpots` | Opponent start spots after a normal punt (20 quantiles). |

## Example (Python)

```python
import json, sys
sys.path.insert(0, "engine")
import decide
model = json.load(open("data/model.json"))
state = dict(score_diff=-3, qtr=4, half_seconds=270, yardline=34, ydstogo=3,
             pos_to=2, def_to=3, home=1, receive_2h=0)
print(decide.decide(model, state))
```

## Example (Node)

```js
const M = require("./app/model.js"), E = require("./app/engine.js");
console.log(E.decide(M, { score_diff: -3, qtr: 4, half_seconds: 270, yardline: 34,
  ydstogo: 3, pos_to: 2, def_to: 3, home: 1, receive_2h: 0 }, {}));
```
