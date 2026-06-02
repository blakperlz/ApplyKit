"""Extract job-description text from a URL, PDF, DOCX, or raw text.

Optional dependencies (requests, pdfplumber, python-docx) are imported lazily so
that importing this module — and unit-testing the text and dispatch paths — never
requires them to be installed.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class JDParseError(Exception):
    """Raised when a JD source cannot be read or its type is unsupported."""


@dataclass
class ParsedJD:
    """Extracted JD text plus where it came from."""

    text: str
    source: str
    source_type: str  # "url" | "pdf" | "docx" | "txt" | "text"

    def hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def detect_source_type(source: str) -> str:
    """Classify a source string without reading it.

    A value that looks like a URL -> "url". An existing file -> by suffix
    (".pdf"/".docx"/".txt"). Anything else is treated as raw pasted "text".
    """
    s = source.strip()
    parsed = urlparse(s)
    if parsed.scheme in ("http", "https") and parsed.netloc:
        return "url"

    p = Path(s)
    # Only treat as a file path if it plausibly is one (avoid stat-ing huge
    # pasted blobs as paths).
    if len(s) < 260 and "\n" not in s:
        suffix = p.suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix == ".docx":
            return "docx"
        if suffix in (".txt", ".md"):
            return "txt"
    return "text"


def _read_pdf(path: Path) -> str:
    try:
        import pdfplumber
    except ImportError as exc:
        raise JDParseError(
            "Reading PDFs requires pdfplumber. Install with `pip install pdfplumber`."
        ) from exc
    parts: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts).strip()


def _read_docx(path: Path) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:
        raise JDParseError(
            "Reading DOCX requires python-docx. Install with `pip install python-docx`."
        ) from exc
    document = docx.Document(str(path))
    return "\n".join(par.text for par in document.paragraphs).strip()


def _fetch_url(url: str, timeout: float) -> str:
    try:
        import requests
    except ImportError as exc:
        raise JDParseError(
            "Fetching URLs requires requests. Install with `pip install requests`."
        ) from exc
    try:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ApplyKit/0.1"})
        resp.raise_for_status()
    except Exception as exc:  # requests.RequestException and friends
        raise JDParseError(f"Could not fetch {url}: {exc}") from exc
    return strip_html(resp.text)


def strip_html(html: str) -> str:
    """Best-effort HTML-to-text. Uses the stdlib parser; no extra dependency.

    This is intentionally simple — for scheduled runs, the Cowork layer uses an
    LLM to extract clean JD text. The CLI path just needs something serviceable.
    """
    from html.parser import HTMLParser

    class _Extractor(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.chunks: list[str] = []
            self._skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self._skip += 1

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript") and self._skip:
                self._skip -= 1

        def handle_data(self, data):
            if not self._skip:
                text = data.strip()
                if text:
                    self.chunks.append(text)

    parser = _Extractor()
    parser.feed(html)
    return "\n".join(parser.chunks).strip()


def parse(source: str, timeout: float = 20.0) -> ParsedJD:
    """Read a JD from a URL, file path, or raw text and return :class:`ParsedJD`."""
    source_type = detect_source_type(source)

    if source_type == "text":
        text = source.strip()
        if not text:
            raise JDParseError("Empty JD text.")
        return ParsedJD(text=text, source="text", source_type="text")

    if source_type == "url":
        return ParsedJD(text=_fetch_url(source, timeout), source=source, source_type="url")

    path = Path(source)
    if not path.exists():
        raise JDParseError(f"File not found: {path}")

    if source_type == "pdf":
        text = _read_pdf(path)
    elif source_type == "docx":
        text = _read_docx(path)
    else:  # txt / md
        text = path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        raise JDParseError(f"No text extracted from {path}.")
    return ParsedJD(text=text, source=str(path), source_type=source_type)
