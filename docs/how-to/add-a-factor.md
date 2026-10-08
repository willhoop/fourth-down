# How to add a factor

This example adds a new field-goal input. Other inputs follow the same steps.

1. In `engine/load_data.py`, derive the new column from the play-by-play.
2. In `engine/fit_models.py`, add the column to the frame (`fg_frame`) and to
   the feature lists (for example `FG_WEATHER`).
3. In `engine/decide.py`, add the input to the feature dictionary in
   `p_field_goal`. Give it a neutral value for when its toggle is off.
4. In `app/engine.js`, make the same change. The two files must stay the same
   in logic.
5. In `app/index.html`, add a control and read it in `readState`.
6. Add a test in `tests/test_decide.py` with a value that you calculate by hand.
7. Rebuild everything. The parity test fails if step 3 and step 4 differ.
8. Write a CHANGELOG entry. A new factor that moves a published figure is a
   MINOR change.
