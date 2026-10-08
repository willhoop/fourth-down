# How to rebuild everything from raw data

You need Python 3.12 and Node.js 20 or later.

1. Install the Python packages:

   ```bash
   py -m pip install pandas pyarrow numpy scikit-learn pytest weasyprint markdown python-pptx
   ```

2. Download the raw data (about 250 MB):

   ```bash
   py engine/download_data.py
   ```

3. Fit the models (about 1 minute). This writes `app/model.js`,
   `data/model.json`, `data/validation.json` and `data/kickers.json`:

   ```bash
   py engine/fit_models.py
   ```

4. Fit the bootstrap replicates (about 5–20 minutes). This writes
   `app/bootstrap.js`:

   ```bash
   py engine/bootstrap.py
   ```

5. Grade the coaches (about 10 minutes). This writes `data/coach_grades.json`
   and `app/grades.js`:

   ```bash
   py engine/grade_coaches.py
   ```

6. Make the weekly page and the edge check:

   ```bash
   py engine/weekly.py
   py engine/edge_check.py
   ```

7. Render the reports and the results block in the white paper:

   ```bash
   py build/render_reports.py
   ```

8. Build the PDFs and the deck:

   ```bash
   py build/build_docs.py
   ```

9. Run the tests. All tests must pass:

   ```bash
   py -m pytest tests -v
   ```

Do the steps in this order. Each step reads the output of the step before it.
If you change the model (step 3), do steps 4 to 9 again.
