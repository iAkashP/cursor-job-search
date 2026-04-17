from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

import feedparser
import requests

from config import HTTP_TIMEOUT_SECONDS, MAX_HTML_BYTES
from utils import dbg, parse_datetime_utc


def _first_nonempty(*vals: Optional[str]) -> str:
    for v in vals:
        if v:
            return v
    return ""


def _clean_html_like_text(s: str) -> str:
    # RSS descriptions are often HTML-ish; keep simple stripping.
    # This is intentionally light to avoid pulling in heavy HTML parsers for feeds.
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_and_parse_rss(feed_url: str) -> Any:
    headers = {"User-Agent": "cursor-job-search/1.0 (job feed scraper)"}
    dbg(f"Fetching RSS: {feed_url}")
    resp = requests.get(feed_url, headers=headers, timeout=HTTP_TIMEOUT_SECONDS)
    resp.raise_for_status()

    # Avoid extremely large responses.
    content = resp.content[:MAX_HTML_BYTES]
    return feedparser.parse(content)


def rss_entries_as_dicts(parsed_feed: Any) -> Iterable[Dict[str, Any]]:
    for entry in parsed_feed.entries or []:
        title = _first_nonempty(getattr(entry, "title", None), entry.get("title"))
        link = _first_nonempty(getattr(entry, "link", None), entry.get("link"))
        author = _first_nonempty(getattr(entry, "author", None), entry.get("author"))
        published = _first_nonempty(entry.get("published"), entry.get("updated"))
        description = _first_nonempty(entry.get("description"), entry.get("summary"))

        yield {
            "title": title,
            "link": link,
            "author": author,
            "published": published,
            "description": description,
        }


def guess_location_and_company_from_description(
    description: str, fallback_company: str = ""
) -> Dict[str, str]:
    """
    Best-effort extraction from RSS snippet text.
    Many feeds include patterns like:
      - "Company: X"
      - "Location: Y"
      - "Candidate Required Location: Z"
    """
    d = _clean_html_like_text(description or "")
    lowered = d.lower()

    def pick(patterns: List[str]) -> str:
        for p in patterns:
            m = re.search(p, d, flags=re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    company = pick([r"Company\s*:\s*([^\n]+)"])
    if not company:
        company = fallback_company

    location = pick(
        [
            r"Location\s*:\s*([^\n]+)",
            r"Candidate Required Location\s*:\s*([^\n]+)",
            r"Country\s*:\s*([^\n]+)",
        ]
    )

    # Sometimes location is embedded as "(Remote - US)" etc. Try to keep it.
    if not location and re.search(r"\bremote\b", lowered):
        location = "Remote"

    return {"company": company or "", "location": location or ""}


def build_rss_job_fingerprint(
    title: str, company: str, link: str
) -> str:
    # Helps with dedupe when some feeds have changing URLs.
    return f"{(title or '').strip()}::{(company or '').strip()}::{(link or '').strip()}"


def parse_rss_for_jobs(feed_url: str) -> List[Dict[str, Any]]:
    parsed = fetch_and_parse_rss(feed_url)
    results: List[Dict[str, Any]] = []
    for e in rss_entries_as_dicts(parsed):
        results.append(e)
    return results


def job_description_text(entry: Dict[str, Any]) -> str:
    desc = entry.get("description") or ""
    return _clean_html_like_text(desc)


def parse_posted_at(entry: Dict[str, Any]) -> Optional[Any]:
    return parse_datetime_utc(entry.get("published"))

