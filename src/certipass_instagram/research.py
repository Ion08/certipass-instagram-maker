"""Small, source-bounded daily research snapshot.

Only fetches certiPass's own site and a short allowlist of primary technical docs.
It never searches arbitrary URLs proposed by generated content.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
import re
from typing import Callable

import requests
from pypdf.errors import PdfReadError, PdfStreamError


@dataclass(frozen=True)
class Page:
    title: str
    url: str
    accessed_at: str
    text: str

    def evidence(self) -> dict[str, str]:
        return {"title": self.title, "url": self.url,
                "accessed_at": self.accessed_at, "text": self.text}


SOURCES = (
    ("certiPass.md", "https://www.certipass.md/"),
    ("Despre certiPass.md", "https://www.certipass.md/about"),
    ("ANCE: acordarea notei 10 la informatică", "https://ance.gov.md/node/1573"),
    ("Ordinul MEC nr. 1326/2023 și anexele", "https://ance.gov.md/sites/default/files/ordin_1326_2023_cu_privire_la_acordarea_notei_10_la_informatica_.pdf"),
    ("Python documentation: floating point arithmetic", "https://docs.python.org/3/tutorial/floatingpoint.html"),
    ("SQLite SELECT documentation", "https://www.sqlite.org/lang_select.html"),
    ("MDN: HTTP overview", "https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview"),
)


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def fetch_snapshot(*, get: Callable = requests.get, timeout: float = 15) -> list[Page]:
    """Fetch current official/primary references; unavailable pages are omitted."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    pages: list[Page] = []
    for title, url in SOURCES:
        try:
            response = get(url, timeout=timeout, headers={"User-Agent": "certipass-instagram-maker/0.1"})
            response.raise_for_status()
            if url.lower().endswith(".pdf"):
                from pypdf import PdfReader
                reader = PdfReader(BytesIO(response.content))
                text = " ".join(page.extract_text() or "" for page in reader.pages)
            else:
                parser = _Text()
                parser.feed(response.text)
                text = " ".join(parser.parts)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                pages.append(Page(title, url, now, text[:7000]))
        except (requests.RequestException, ValueError, PdfReadError, PdfStreamError):
            continue
    return pages
