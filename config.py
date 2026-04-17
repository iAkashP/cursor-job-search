from __future__ import annotations

import os

# ---- Google Sheets ----
# Default to your spreadsheet name. Override via env var only if needed.
SHEET_NAME = os.getenv("SHEET_NAME", "LinkedIn Jobs")
CREDS_FILE = os.getenv("CREDS_FILE", "creds.json")

# Column names in your Google Sheet (order matters for append_rows()).
COLUMN_ORDER = [
    "Job Title",
    "Company",
    "Location",
    "Country",
    "LinkedIn URLs",
    "Sponsorship Type",
    "Posted At (UTC)",
    "Scraped At",
]

# ---- Scraping / filtering ----
DATA_ENGINEER_PATTERN = "data engineer"

POSITIVE_SPONSORSHIP_KEYWORDS = [
    "visa sponsorship",
    "visa sponsor",
    "visa support",
    "work visa",
    "work authorization",
    "work authorization",
    "work permit",
    "immigration support",
    "immigration assistance",
    "relocation",
    "relocation support",
    "relocation package",
    "relocate",
    "we can sponsor",
    "we will sponsor",
    "sponsor",
    "sponsorship",
    "h1b",
    "h-1b",
    "skilled worker",
    "tier 2",
    "uk tier 2",
    "green card",
    "l1 visa",
    "tn visa",
]

# If any of these appear, we drop the job even if positive keywords exist.
NEGATIVE_SPONSORSHIP_KEYWORDS = [
    "no visa sponsorship",
    "no sponsorship",
    "will not sponsor",
    "does not sponsor",
    "cannot sponsor",
    "not able to sponsor",
]

# ---- Remote-anywhere + India eligibility (best-effort) ----
# These are heuristics because free RSS feeds rarely include a structured
# "eligible countries" / "work authorization nationality" field.
REMOTE_ANYWHERE_KEYWORDS = [
    "work from anywhere",
    "remote anywhere",
    "remote worldwide",
    "worldwide",
    "global",
    "anywhere",
    "distributed",
    "remote-first",
]

INDIA_ELIGIBLE_KEYWORDS = [
    # Location hint.
    "remote - india",
    "remote (india)",
    "remote india",
    # Authorization hint.
    "eligible to work in india",
    "authorized to work in india",
    "work authorization in india",
    "work permit in india",
    "right to work in india",
    # Residency hint.
    "candidates located in india",
    "located in india",
    "residing in india",
]

WINDOW_HOURS = int(os.getenv("WINDOW_HOURS", "96"))

# Time window: last N hours
# (Kept: default is 96 hours)

# Be nice to job boards
HTTP_TIMEOUT_SECONDS = int(os.getenv("HTTP_TIMEOUT_SECONDS", "20"))
MAX_HTML_BYTES = int(os.getenv("MAX_HTML_BYTES", str(2_000_000)))  # 2MB

# When the RSS snippet is ambiguous, we optionally fetch the full page.
FETCH_FULL_PAGE_ON_AMBIGUOUS = os.getenv("FETCH_FULL_PAGE_ON_AMBIGUOUS", "1") == "1"

# ---- Sources (free feeds) ----
# These are remote-job oriented sources; the filters then narrow to "data engineer" + sponsorship/relocation.
SOURCES = [
    {
        "name": "Remotive RSS",
        # Public RSS feed for Remotive.
        "feed_url": "https://remotive.com/remote-jobs/rss-feed",
    },
    {
        "name": "Remotive RSS (alternate)",
        "feed_url": "https://remotive.com/feed",
    },
    {
        "name": "We Work Remotely RSS",
        "feed_url": "https://weworkremotely.com/remote-job-rss-feed",
    },
    {
        "name": "We Work Remotely RSS (alternate)",
        "feed_url": "https://weworkremotely.com/remote-jobs.rss",
    },
    {
        "name": "RemoteOK RSS - general",
        "feed_url": "https://remoteok.io/remote-jobs.rss",
    },
    {
        "name": "RemoteOK RSS - data engineer",
        "feed_url": "https://remoteok.com/remote-data-engineer-jobs.rss",
    },
    {
        "name": "JobsCollider remote jobs RSS",
        "feed_url": "https://jobscollider.com/remote-jobs.rss",
    },
    {
        "name": "Himalayas remote jobs RSS",
        "feed_url": "https://himalayas.app/jobs/rss",
    },
    {
        "name": "Real Work From Anywhere RSS (all)",
        "feed_url": "https://www.realworkfromanywhere.com/rss.xml",
    },
    {
        "name": "Jobicy remote jobs RSS",
        "feed_url": "https://jobicy.com/feed/job_feed",
    },
]

# Where we remember what we've already appended.
STATE_FILE = os.getenv("STATE_FILE", "state.json")

