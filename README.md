# gtm-dashboard

District-wise geotag summary for Green Tamil Nadu Mission planting reports across
5 departments: Forest Department, Other Departments, Coastal Habitat, Plant-a-Tree
and Agriculture Department.

**Live page:** https://bharathwaj1316.github.io/gtm-dashboard/

## How it works

```
gtm-data release (merged.csv.gz)  --(GitHub Actions, every 30 min)-->  docs/summary.json  -->  GitHub Pages
```

`.github/workflows/update-summary.yml` downloads the merged file using the
`GTM_DATA_TOKEN` secret, runs `scraper/build_from_merged.py` and commits only the
totals when they change. "Data updated" on the page is the merged file's upload time.
The token expires on 1 Dec 2026; replace the secret before then.

## Older PC scraper

```
greentnmission.com/Export  --(scraper, every 30 min)-->  docs/summary.json  -->  GitHub Pages
```

1. `scraper/fetch_exports.py` downloads the 5 Planting Report CSVs using a saved login.
2. `scraper/build_summary.py` counts geotags (one report row = one geotag) and seedlings
   per district, department and financial year into `docs/summary.json`.
   Only counts are published; raw exports with personal data stay local.
3. `scraper/run.py` runs both and commits/pushes `docs/summary.json` when the data changes.
4. `docs/index.html` (the summary table) loads the JSON and reloads it every 30 minutes.

## Setup (Windows)

```powershell
pip install playwright pandas openpyxl
python -m playwright install chromium
python scraper\login.py                 # log in + type the captcha once
python scraper\run.py                   # one update
powershell -ExecutionPolicy Bypass -File scraper\setup_schedule.ps1   # every 30 min
```

The website session expires after a day or two. When it does, a Windows notification
appears; run `python scraper\login.py` again. Errors are written to `logs/run.log`.

## Data notes

- Coastal Habitat has no district column; its division is mapped to a district using
  Forest Department data.
- Plant-a-Tree financial year is derived from the planted date (April–March).
  Records with no date are listed under "Unknown".
- Agriculture is exported one file per financial year.
- Other Departments and Plant-a-Tree use the export default "Verified only".
