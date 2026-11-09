from __future__ import annotations

import re

from bs4 import BeautifulSoup


def clean_text(value: str | None, *, max_chars: int = 200_000) -> str:
    """Normalize text into a bounded, whitespace-separated string."""
    if not value:
        return ""
    # Keep printable text while removing terminal/control characters.
    value = "".join(char for char in str(value) if char.isprintable() or char.isspace())
    value = re.sub(r"\s+", " ", value).strip()
    return value[:max(0, max_chars)]


def html_to_text(html: str | None, *, max_chars: int = 200_000) -> str:
    """Extract visible text from HTML without allowing parser failures to escape."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, features="lxml")
        for element in soup.find_all(["script", "style", "noscript", "nav", "header", "footer", "form", "aside"]):
            element.decompose()
        return clean_text(soup.get_text(" ", strip=False), max_chars=max_chars)
    except Exception:
        return clean_text(html, max_chars=max_chars)
