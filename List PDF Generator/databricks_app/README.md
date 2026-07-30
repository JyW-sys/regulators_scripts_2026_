# List PDF Generator — Streamlit app

Hosted version of `../list_pdf_generator.py`: upload one or more "SQL Ready"
`.xlsx` workbooks in a browser, click a button, download the PDFs. No Python
needed on the user's machine — this is meant to run as a **Databricks App**.

## Test locally first (Mac)

```bash
cd "databricks_app"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Opens at `http://localhost:8501`. Upload the same workbook you'd normally use
with the standalone script and confirm the downloaded PDFs match (same
filenames, same 32-names-per-page layout).

Things to check:
- Upload **two workbooks at once** — both should produce PDFs, no filename collisions.
- Upload a workbook **missing a required column** (Name/RegCtry/RegCode/ListCode) — should show a warning and skip it, not crash.
- Upload a workbook whose **filename doesn't contain `"SQL Ready <date-time>"`** — should warn and skip, not crash.
- A name with **accented / Eastern European / Cyrillic characters** should render correctly (this validates the bundled `fonts/DejaVuSans.ttf`).
- Output filenames should look like `RegCtry RegCode SQL Ready <date-time from the uploaded file's own name>- ListCode.pdf`.

## Deploy to Databricks

**Option A — UI:**
1. In your Databricks workspace: **Apps → + Create app → Custom**.
2. Give it a name (e.g. `list-pdf-generator`).
3. Upload/sync this `databricks_app/` folder's contents (`app.py`, `app.yaml`,
   `requirements.txt`, `fonts/`) as the app's source.
4. Deploy. Databricks installs `requirements.txt` and runs the `command` from
   `app.yaml`.

**Option B — CLI** (from inside `databricks_app/`):
```bash
databricks sync --watch . /Workspace/Users/<you>/list-pdf-generator
databricks apps deploy list-pdf-generator --source-code-path /Workspace/Users/<you>/list-pdf-generator
```

Once deployed, share the app's URL — anyone with workspace access can use it
straight from a browser.

## Notes
- The bundled font is **DejaVu Sans** (open license, not Arial) — the Databricks
  cluster is Linux, so the original script's Windows/macOS Arial paths don't
  exist there. DejaVu covers Western + Eastern European + Cyrillic + Greek.
- Per-file size cap for Databricks Apps is 10 MB; the font file is ~750 KB.
- The original `list_pdf_generator.py` is untouched and still works standalone.
