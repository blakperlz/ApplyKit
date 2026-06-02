"""Scout: monitor career pages and detect new postings.

Per ADR-001 Tension 2, extraction is LLM-assisted and Scout runs primarily in
Cowork (where LLM calls are free). To keep this module testable and runtime-
agnostic, the *extractor* is injected: it is any callable
``extractor(html, company) -> list[(title, url)]``. The Cowork layer passes an
LLM-backed extractor; tests pass a stub; the CLI can pass an HTML heuristic.

The new-vs-seen diff against ``postings_cache`` is pure SQL and fully tested.
"""

from __future__ import annotations

import hashlib
import sqlite3
from typing import Callable, Iterable, Optional

from .config import Company, Config
from .models import Posting, utc_now_iso

Extractor = Callable[[str, str], Iterable[tuple[str, str]]]


def url_hash(url: str) -> str:
    """Stable short hash used as the per-company identity of a posting."""
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()[:16]


def is_new_posting(conn: sqlite3.Connection, company: str, url: str) -> bool:
    """True if (company, url) has not been cached before."""
    row = conn.execute(
        "SELECT 1 FROM postings_cache WHERE company = ? AND url_hash = ?",
        (company, url_hash(url)),
    ).fetchone()
    return row is None


def remember_posting(conn: sqlite3.Connection, posting: Posting) -> bool:
    """Insert a posting into the cache. Returns False if it was already present."""
    h = posting.url_hash or url_hash(posting.url)
    try:
        conn.execute(
            "INSERT INTO postings_cache(company, title, url, url_hash, first_seen) "
            "VALUES(?, ?, ?, ?, ?)",
            (posting.company, posting.title, posting.url, h, posting.first_seen or utc_now_iso()),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # UNIQUE(company, url_hash) — already seen


def diff_postings(
    conn: sqlite3.Connection,
    company: str,
    listings: Iterable[tuple[str, str]],
) -> list[Posting]:
    """Given (title, url) pairs from a page, return only the not-seen-before ones.

    New postings are written to the cache as a side effect, so a second call with
    the same listings returns nothing.
    """
    fresh: list[Posting] = []
    for title, url in listings:
        if is_new_posting(conn, company, url):
            posting = Posting(
                company=company, title=title, url=url, url_hash=url_hash(url)
            )
            if remember_posting(conn, posting):
                fresh.append(posting)
    return fresh


def scout_company(
    conn: sqlite3.Connection,
    company: Company,
    *,
    extractor: Extractor,
    fetcher: Optional[Callable[[str], str]] = None,
) -> list[Posting]:
    """Fetch one company's career page, extract listings, and return new postings."""
    html = (fetcher or _default_fetch)(company.careers_url)
    listings = list(extractor(html, company.name))
    return diff_postings(conn, company.name, listings)


def scout_all(
    conn: sqlite3.Connection,
    config: Config,
    *,
    extractor: Extractor,
    fetcher: Optional[Callable[[str], str]] = None,
) -> list[Posting]:
    """Scout every configured company, dream tier first. Returns all new postings.

    Failures on a single company are swallowed so one broken page does not abort
    the whole run.
    """
    tier_order = {"dream": 0, "target": 1, "opportunistic": 2}
    companies = sorted(config.companies, key=lambda c: tier_order.get(c.tier.value, 9))
    new_postings: list[Posting] = []
    for company in companies:
        try:
            new_postings.extend(
                scout_company(conn, company, extractor=extractor, fetcher=fetcher)
            )
        except Exception:  # noqa: BLE001 - one bad page shouldn't kill the run
            continue
    return new_postings


def _default_fetch(url: str) -> str:
    # Scout needs raw HTML for the extractor (not stripped text), so fetch directly.
    try:
        import requests
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Scout's default fetcher needs requests installed.") from exc
    resp = requests.get(url, timeout=20, headers={"User-Agent": "ApplyKit/0.1"})
    resp.raise_for_status()
    return resp.text
