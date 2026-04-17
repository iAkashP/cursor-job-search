from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Iterable, Optional

from dateutil import parser as date_parser


def dbg(msg: str) -> None:
    if os.getenv("DEBUG", "0") == "1":
        print(f"[DEBUG] {msg}", flush=True)


def normalize_text(s: str) -> str:
    s = s or ""
    s = s.replace("\u00a0", " ")  # non-breaking space
    s = re.sub(r"\s+", " ", s).strip()
    return s.lower()


def text_contains_phrase(haystack: str, phrase: str) -> bool:
    return normalize_text(phrase) in normalize_text(haystack)


def contains_any_keywords(text: str, keywords: Iterable[str]) -> bool:
    t = normalize_text(text)
    for kw in keywords:
        if normalize_text(kw) in t:
            return True
    return False


def extract_country(location: str) -> str:
    """
    Best-effort country extraction from a free-form location string.
    Examples:
      "Bengaluru, Karnataka, IN" -> "IN"
      "London, UK" -> "UK"
      "Remote (Canada)" -> "Canada"
    """
    loc = (location or "").strip()
    if not loc:
        return ""

    # Common: last comma-separated chunk.
    parts = [p.strip() for p in loc.split(",") if p.strip()]
    if parts:
        last = parts[-1]
        # If it's short like "IN", "US", "UK" keep it.
        if len(last) <= 3 and last.isalpha():
            return last.upper()
        # If it's like "IN " with punctuation remove.
        last = re.sub(r"[^A-Za-z]", "", last)
        if len(last) <= 3 and last.isalpha():
            return last.upper()
        return last

    return loc


def parse_datetime_utc(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None

    try:
        dt = date_parser.parse(dt_str)
    except (ValueError, TypeError):
        return None

    if not dt.tzinfo:
        # Many feeds are UTC-ish strings but without tz. Treat as UTC.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_sheet_posted_at(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    # Match example: 2026-04-13T00:00:00.000Z
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def format_sheet_scraped_at(now_utc: Optional[datetime] = None) -> str:
    if not now_utc:
        now_utc = datetime.now(timezone.utc)
    # Convert to IST (Asia/Kolkata) before formatting.
    ist = now_utc.astimezone(ZoneInfo("Asia/Kolkata"))
    # Example: 2026-04-14 19:46 (UTC+5:30)
    return ist.strftime("%Y-%m-%d %H:%M")

