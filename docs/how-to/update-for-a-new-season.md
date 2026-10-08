# How to update for a new season or a rule change

## Add a completed season

1. Open `engine/config.py`.
2. Add the season to `seasons`. Add it to `grade_seasons` if it is not there.
3. Move `holdout_seasons` to the two newest complete seasons.
4. Set `kicker_list_seasons` to the two newest complete seasons.
5. Set `current_season` to the season in progress.
6. Increase `version` (see the rules below).
7. Do all steps in [rebuild-everything.md](rebuild-everything.md).

## Refresh the current season during the year

1. Download the new weeks:

   ```bash
   py engine/download_data.py --force
   ```

2. Do steps 5 to 8 in [rebuild-everything.md](rebuild-everything.md). You do
   not refit the model.

## Apply a rule change

1. If the change moves the kickoff touchback, set `rules_season` to the first
   season under the new rule. The engine measures the new kickoff spot from
   that season.
2. If the change moves the missed-field-goal spot, change `fg_snap_to_spot`
   or `missed_fg_min_spot`.
3. Rebuild everything.

## Version and changelog

- No published figure moves: PATCH.
- A figure moves and the method stays the same: MINOR.
- The method changes, so old and new figures answer different questions: MAJOR.

Write one `CHANGELOG.md` entry with a `### Record` section in the same pass.
