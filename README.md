# Cursor Job Search (Data Engineer + Sponsorship/Relocation)

This project collects jobs from free RSS sources, filters for:
1) job title or description contains `data engineer`
2) the job mentions visa sponsorship / work authorization or relocation
3) job is posted within the last `WINDOW_HOURS` (default: `96`)

New matches are appended to a Google Sheet every run (scheduled via GitHub Actions).

## Google Sheets setup

1. Create a Google service account and download its credentials JSON.
2. Share the target Google Sheet with the service account email.
3. Set either:
   - `GOOGLE_CREDS_JSON` (recommended): put the full JSON string into an environment variable/secret
   - or place `creds.json` next to `scraper.py` and set `CREDS_FILE=creds.json`

Required env/secrets:
- `SHEET_NAME` (defaults to `LinkedIn Jobs` in `config.py`; optional override)
- `GOOGLE_CREDS_JSON` (or `creds.json` file)

## Local run

```bash
pip install -r requirements.txt

export GOOGLE_CREDS_JSON='{"type":"service_account", ...}'
export SHEET_NAME='Sheet1'

python scraper.py run
```

## Scheduled run (daily)

This repo includes `.github/workflows/schedule.yml`, which runs daily at `00:00 UTC` using free GitHub Actions cron.

Set these GitHub Actions secrets:
- `GOOGLE_CREDS_JSON`
- `SHEET_NAME`

## How the sheet columns are filled

The sheet columns (in append order) are:
`Job Title`, `Company`, `Location`, `Country`, `LinkedIn URLs`, `Sponsorship Type`, `Posted At (UTC)`, `Scraped At`

Note: the `LinkedIn URLs` column is populated with the job posting URL from the source RSS feed (not an actual LinkedIn link).
`Scraped At` is written in IST (`Asia/Kolkata`).

## Filtering logic notes (best-effort)

- Sponsorship/relocation is inferred from keyword matches in the RSS snippet; optionally the scraper fetches the full job page for extra recall when needed.
- Because RSS feeds do not always include a reliable "sponsorship" flag, completeness is best-effort without paid search APIs.

## Configuration (optional)

Environment variables you may change:
- `WINDOW_HOURS` (default `96`)
- `DEBUG=1`
- `FETCH_FULL_PAGE_ON_AMBIGUOUS=0` to skip full-page keyword checks
