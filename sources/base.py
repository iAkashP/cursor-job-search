from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class Job:
    job_title: str
    company: str
    location: str
    country: str
    job_url: str
    sponsorship_type: str
    posted_at_utc: Optional[datetime]
    scraped_at_utc: Optional[datetime]
    source_name: str

    def dedupe_key(self) -> str:
        # Most sources expose a stable job URL.
        return (self.job_url or "").strip()

