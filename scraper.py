from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

import config
from sheets_append import append_rows, connect_sheet, ensure_header, job_to_row
from sources.base import Job
from sources.rss_source import (
    build_rss_job_fingerprint,
    guess_location_and_company_from_description,
    job_description_text,
    parse_rss_for_jobs,
)
from utils import (
    dbg,
    contains_any_keywords,
    extract_country,
    normalize_text,
    parse_datetime_utc,
)


# Match "data engineer" + close variants.
# Kept loose because job titles vary a lot across boards.
DATA_ENGINEER_REGEX = re.compile(
    r"\bdata[\s\-]+engineer(ing)?\b",
    re.IGNORECASE,
)


def load_state(state_file: str) -> Set[str]:
    if not os.path.exists(state_file):
        return set()
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            keys = raw.get("seen_keys", [])
        elif isinstance(raw, list):
            keys = raw
        else:
            keys = []
        return set(keys)
    except Exception as e:
        dbg(f"Failed to load state: {e}")
        return set()


def save_state(state_file: str, seen_keys: Set[str]) -> None:
    tmp_file = state_file + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump({"seen_keys": sorted(seen_keys)}, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, state_file)


def looks_like_data_engineer(job_title: str, description: str) -> bool:
    text = f"{job_title or ''} {description or ''}".strip()
    return bool(DATA_ENGINEER_REGEX.search(text))


def looks_like_remote_anywhere(text: str) -> bool:
    if not text:
        return False
    t = normalize_text(text)
    if "remote" not in t and "work from anywhere" not in t:
        return False
    # Heuristic: must mention remote/anywhere-like + global/worldwide.
    return contains_any_keywords(t, config.REMOTE_ANYWHERE_KEYWORDS)


def looks_like_india_eligible(text: str) -> bool:
    if not text:
        return False
    return contains_any_keywords(text, config.INDIA_ELIGIBLE_KEYWORDS)


def looks_like_sponsorship_or_relocation(text: str) -> bool:
    if not text:
        return False
    t = normalize_text(text)

    for kw in config.NEGATIVE_SPONSORSHIP_KEYWORDS:
        if normalize_text(kw) in t:
            return False

    # Must include at least one positive keyword.
    return contains_any_keywords(t, config.POSITIVE_SPONSORSHIP_KEYWORDS)


def infer_sponsorship_type(text: str) -> str:
    t = normalize_text(text)
    if "relocation" in t:
        return "Relocation Support"

    # Visa/work authorization keywords.
    visa_keywords = [
        "visa sponsorship",
        "visa sponsor",
        "visa support",
        "work authorization",
        "work permit",
        "immigration support",
        "immigration assistance",
        "h1b",
        "h-1b",
        "green card",
        "tn visa",
        "tier 2",
        "l1 visa",
    ]
    if any(normalize_text(k) in t for k in visa_keywords):
        return "Visa Sponsorship"

    if "sponsorship" in t or "sponsor" in t:
        return "Sponsorship Support"

    return ""


def fetch_full_page_text(job_url: str) -> str:
    # This is a best-effort recall improvement when the RSS snippet lacks sponsorship keywords.
    headers = {"User-Agent": "cursor-job-search/1.0 (job page scraper)"}
    resp = requests.get(job_url, headers=headers, timeout=config.HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "").lower()
    if "text" not in content_type and "html" not in content_type:
        return ""

    # Cap size to avoid huge downloads.
    raw = resp.content[: config.MAX_HTML_BYTES]
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ", strip=True)
    return text[: config.MAX_HTML_BYTES]


def within_last_window(posted_at_utc: Optional[datetime], now_utc: datetime) -> bool:
    if not posted_at_utc:
        return False
    if posted_at_utc > now_utc:
        return False
    return now_utc - posted_at_utc <= timedelta(hours=config.WINDOW_HOURS)


def scrape_jobs_from_sources() -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for src in config.SOURCES:
        name = src["name"]
        feed_url = src["feed_url"]
        try:
            entries = parse_rss_for_jobs(feed_url)
        except Exception as e:
            dbg(f"[{name}] failed to fetch/parse feed: {e}")
            continue
        print(f"[feed] {name}: {len(entries)} entries")

        for entry in entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            author = (entry.get("author") or "").strip()
            description_raw = entry.get("description") or ""
            description_text = job_description_text(entry)
            loc_comp = guess_location_and_company_from_description(description_text, fallback_company=author)
            location = loc_comp.get("location") or ""
            company = loc_comp.get("company") or author or ""
            country = extract_country(location)
            posted_at_utc = parse_datetime_utc(entry.get("published"))

            candidates.append(
                {
                    "source_name": name,
                    "job_title": title,
                    "company": company,
                    "location": location,
                    "country": country,
                    "job_url": link,
                    "description": description_text,
                    "posted_at_utc": posted_at_utc,
                }
            )
    return candidates


def filter_and_build_jobs(candidates: List[Dict[str, Any]], now_utc: datetime) -> Tuple[List[Job], List[str]]:
    jobs: List[Job] = []
    accepted_keys: List[str] = []
    seen_keys = load_state(config.STATE_FILE)

    data_engineer_pass = 0
    remote_india_pass = 0
    sponsorship_pass = 0

    for c in candidates:
        job_title = c["job_title"]
        description = c["description"]
        job_url = c["job_url"]

        if not looks_like_data_engineer(job_title, description):
            continue
        data_engineer_pass += 1

        if not within_last_window(c.get("posted_at_utc"), now_utc):
            continue

        candidate_text = f"{job_title}\n{description}"

        sponsorship_ok = looks_like_sponsorship_or_relocation(candidate_text)
        remote_anywhere_ok = looks_like_remote_anywhere(candidate_text)
        india_ok = remote_anywhere_ok and looks_like_india_eligible(candidate_text)

        if (config.FETCH_FULL_PAGE_ON_AMBIGUOUS and job_url) and (not sponsorship_ok) and (not india_ok):
            # Recall improvement: fetch the full page and re-check keywords.
            try:
                full_text = fetch_full_page_text(job_url)
                if full_text:
                    candidate_text = full_text  # Use full text for inference.
                sponsorship_ok = looks_like_sponsorship_or_relocation(candidate_text)
                remote_anywhere_ok = looks_like_remote_anywhere(candidate_text)
                india_ok = remote_anywhere_ok and looks_like_india_eligible(candidate_text)
            except Exception as e:
                dbg(f"Full page fetch failed for {job_url}: {e}")

        if not sponsorship_ok and not india_ok:
            continue

        if sponsorship_ok:
            sponsorship_pass += 1
        if india_ok:
            remote_india_pass += 1

        # Column "Sponsorship Type" doubles as "match category" for non-visa remote-anywhere jobs.
        sponsorship_type = infer_sponsorship_type(candidate_text)
        if not sponsorship_type and india_ok:
            sponsorship_type = "Remote - India Eligible"

        country = c.get("country") or extract_country(c.get("location") or "")

        dedupe_key = (job_url or "").strip()
        if not dedupe_key:
            dedupe_key = build_rss_job_fingerprint(job_title, c.get("company") or "", c.get("job_url") or "")

        if dedupe_key in seen_keys:
            continue

        job = Job(
            job_title=job_title,
            company=c.get("company") or "",
            location=c.get("location") or "",
            country=country or "",
            job_url=job_url or "",
            sponsorship_type=sponsorship_type or "Relocation Support",
            posted_at_utc=c.get("posted_at_utc"),
            scraped_at_utc=now_utc,
            source_name=c.get("source_name") or "",
        )

        jobs.append(job)
        accepted_keys.append(dedupe_key)

    print(
        "[filter] Summary: "
        f"data-engineer candidates={data_engineer_pass}, "
        f"sponsorship_or_relocation matches={sponsorship_pass}, "
        f"remote-anywhere+India matches={remote_india_pass}"
    )
    return jobs, accepted_keys


def run_once() -> None:
    now_utc = datetime.now(timezone.utc)
    print(f"[run] Started at UTC {now_utc.isoformat(timespec='seconds')}")

    candidates = scrape_jobs_from_sources()
    print(f"[run] Candidates collected from RSS feeds: {len(candidates)}")

    jobs, accepted_keys = filter_and_build_jobs(candidates, now_utc)
    print(f"[run] Filtered NEW matching jobs: {len(jobs)}")

    if not jobs:
        print("No matching new jobs found.")
        return

    sheet = connect_sheet()
    ensure_header(sheet)
    rows = [job_to_row(j) for j in jobs]
    for j in jobs:
        print(f"[append] {j.job_title} | {j.company} | {j.location} | {j.sponsorship_type}")
    append_rows(sheet, rows)

    # Update dedupe state only after successful append.
    seen_keys = load_state(config.STATE_FILE)
    seen_keys.update(accepted_keys)
    save_state(config.STATE_FILE, seen_keys)

    print(f"Appended {len(jobs)} jobs to Google Sheet.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", nargs="?", default="run", choices=["run"], help="Run the scraper")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug output")
    args = parser.parse_args()
    if getattr(args, "debug", False):
        os.environ["DEBUG"] = "1"
    if args.command == "run":
        run_once()


if __name__ == "__main__":
    main()

