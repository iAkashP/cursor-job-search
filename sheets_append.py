from __future__ import annotations

import json
import os
from typing import Iterable, List

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import COLUMN_ORDER, CREDS_FILE, SHEET_NAME
from utils import dbg


# ── Google Sheets ─────────────────────────────────────────────────────────────
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # GitHub Actions: GOOGLE_CREDS_JSON secret contains the full JSON string
    # Local: just read creds.json directly from disk
    creds_env = os.getenv("GOOGLE_CREDS_JSON", "").strip()

    if creds_env.startswith("{"):
        dbg("Using GOOGLE_CREDS_JSON env variable")
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            json.loads(creds_env), scope)
    elif os.path.exists(CREDS_FILE):
        dbg(f"Using local {CREDS_FILE}")
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, scope)
    else:
        raise FileNotFoundError(
            f"creds.json not found at: {os.path.abspath(CREDS_FILE)}\n"
            f"Make sure creds.json is in the same folder as scraper.py"
        )

    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1


def append_rows(sheet, rows: Iterable[List[str]]) -> None:
    rows = list(rows)
    if not rows:
        return
    dbg(f"Appending {len(rows)} rows to Google Sheet")
    # Sheets are usually configured with the header row already.
    sheet.append_rows(rows, value_input_option="USER_ENTERED")


def job_to_row(job) -> List[str]:
    # Keep ordering aligned with COLUMN_ORDER.
    scraped_at_utc = job.scraped_at_utc
    return [
        job.job_title or "",
        job.company or "",
        job.location or "",
        job.country or "",
        job.job_url or "",
        job.sponsorship_type or "",
        format_sheet_posted_at(job.posted_at_utc),
        format_sheet_scraped_at(scraped_at_utc),
    ]


def format_sheet_posted_at(dt):
    from utils import format_sheet_posted_at as _fmt

    return _fmt(dt)


def format_sheet_scraped_at(dt):
    from utils import format_sheet_scraped_at as _fmt

    return _fmt(dt)


def ensure_header(sheet) -> None:
    # Optional: ensure header matches expected columns.
    # We avoid overwriting if the sheet already has values.
    try:
        header = sheet.row_values(1)
        if not header:
            sheet.append_row(COLUMN_ORDER, value_input_option="USER_ENTERED")
    except Exception:
        # If header read fails, just proceed; append_rows will still work.
        pass

