# Banjir data extractor (Public Info Banjir)

This repo runs a Python extractor against the Public Info Banjir site and publishes the latest result as a JSON file (`docs/data.json`). A GitHub Actions workflow runs automatically every 15 minutes and commits the updated JSON back to the repository.

## What it extracts

- Source website: `https://publicinfobanjir.water.gov.my/aras-air/data-paras-air/aras-air-data/`
- States queried (`STATE_CODES` in `extract.py`): `PLS, KDH, PNG, PRK, SEL, WLH, PTJ, NSN, MLK, JHR, PHG, TRG, KEL, SRK, SAB, WLP`
- Filtering rule:
  - Default: no filtering (returns all rows found for each state).
  - Optional: pass `--danger-only` to keep only rows where `Water Level >= Threshold Danger` (when the threshold column is available).
- Output fields:
  - The JSON records include the columns listed in `DESIRED_COLUMNS` in `extract.py` (when present), plus `state_code`.

## Run locally

Requirements: Python 3.10+ recommended.

Install dependencies:

```bash
pip install -r requirements.txt
```

Run and write JSON:

```bash
python extract.py --json docs/data.json
```

Optional: keep only stations at/above danger threshold:

```bash
python extract.py --json docs/data.json --danger-only
```

Optional: also write an XLSX file (requires `openpyxl`, already in `requirements.txt`):

```bash
python extract.py --json docs/data.json --xlsx publicinfobanjir_all_states.xlsx
```

## JSON output format

The extractor writes a single JSON object to `docs/data.json`.

Top-level schema:

```json
{
  "generated_at": "2025-12-23T03:12:45.123456+00:00",
  "source": "https://publicinfobanjir.water.gov.my/aras-air/data-paras-air/aras-air-data/",
  "rows": 123,
  "all": [ { "…row fields…" }, { "…row fields…" } ],
  "states": {
    "SEL": [ { "…row fields…" } ],
    "JHR": [ { "…row fields…" } ]
  }
}
```

Field meanings:

- `generated_at`: ISO-8601 timestamp in UTC for when the JSON was generated.
- `source`: Source URL used by the script.
- `rows`: Total number of rows in `all`.
- `all`: Flattened list of all returned rows across states (after filtering).
- `states`: A map of `state_code` → list of rows for that state (same row structure as `all`).

### Row format

Each row is a JSON object created directly from the HTML table columns. Keys may contain spaces because they come from the website’s table headers.

The script attempts to keep these keys (when present):

- `Station Name Station Name`
- `District District`
- `Main Basin Main Basin`
- `Sub River Basin Sub River Basin`
- `Last Updated Last Updated`
- `Water Level (m) (Graph) Water Level (m) (Graph)`
- `state_code`

Notes:

- Values can be strings, numbers, or `null` (when the table cell is empty).
- `state_code` is always present for returned rows (it is added by the script).

Example row:

```json
{
  "Station Name Station Name": "STATION ABC",
  "District District": "KLANG",
  "Main Basin Main Basin": "SUNGAI XYZ",
  "Sub River Basin Sub River Basin": "SUB BASIN 1",
  "Last Updated Last Updated": "23/12/2025 10:45",
  "Water Level (m) (Graph) Water Level (m) (Graph)": 5.12,
  "state_code": "SEL"
}
```

## “API” / How to call it

There are two common ways to serve `docs/data.json` so your app can fetch it like an API:

### Option A: GitHub Pages (recommended)

1. Go to your repo **Settings → Pages**.
2. **Build and deployment**:
   - Source: **Deploy from a branch**
   - Branch: your default branch (e.g. `main`)
   - Folder: `/docs`
3. Save.

Your JSON will be available at:

```text
https://<owner>.github.io/<repo>/data.json
```

Examples:

```bash
curl "https://<owner>.github.io/<repo>/data.json"
curl "https://<owner>.github.io/<repo>/data.json" | jq '.rows'
curl "https://<owner>.github.io/<repo>/data.json" | jq '.states.SEL | length'
```

In JavaScript:

```js
const res = await fetch("https://<owner>.github.io/<repo>/data.json");
const data = await res.json();
console.log(data.generated_at, data.rows);
```

### Option B: Raw GitHub content URL (quick, no Pages setup)

```text
https://raw.githubusercontent.com/<owner>/<repo>/<branch>/docs/data.json
```

Example:

```bash
curl "https://raw.githubusercontent.com/<owner>/<repo>/main/docs/data.json"
```

Notes:

- Raw URLs are fine for many use cases, but GitHub Pages is typically nicer for “API-like” access.
- If the repo is private, raw URLs require authentication.

## GitHub Actions scheduler (every 15 minutes)

Workflow file: `.github/workflows/extract-every-15min.yml`

What it does:

1. Runs every 15 minutes (`cron: */15 * * * *`) and can also be started manually (workflow dispatch).
2. Installs Python dependencies from `requirements.txt`.
3. Runs: `python extract.py --json docs/data.json --danger-only`
4. If `docs/data.json` changed, commits and pushes the update.

Important setup (required):

- Repo **Settings → Actions → General → Workflow permissions**:
  - Select **Read and write permissions** (so the workflow can commit/push `docs/data.json`).

Important scheduling note:

- GitHub Actions scheduled workflows are not real-time; runs may be delayed depending on GitHub load.

## Troubleshooting

- If the workflow fails on “push”:
  - Ensure **Workflow permissions** is set to **Read and write**.
- If `pd.read_html` fails:
  - The source site may have changed HTML structure temporarily.
  - Re-run locally and inspect the response; you may need to update parsing logic in `extract.py`.
- If `docs/data.json` is 0 rows:
  - The filter keeps only rows where water level meets/exceeds danger threshold (when threshold is available). The site may return none at that moment.
