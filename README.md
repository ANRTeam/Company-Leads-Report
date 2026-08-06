# Angi Leads Report

Upload an Angi Leads CRM export (CSV) and get a performance report:
financials, lead quality/refunds, outreach, field operations, and
conversions.

## Files

- `angi_report_lib.py` - shared logic (metrics + HTML rendering). Edit the
  `CONFIG` section at the top to match your CRM's column names and your
  team's definitions of "fake lead", loss-reason grouping, etc.
- `streamlit_app.py` - the web app (this is the Streamlit entry point).
- `generate_angi_report.py` - command-line version: `python3 generate_angi_report.py your_export.csv report.html`
- `requirements.txt` - Python dependencies.


### 3. Updating later

Any edits (e.g. tuning `FAKE_REASONS` or `LOSS_REASON_GROUPS` in
`angi_report_lib.py`)
