from __future__ import annotations

from html import escape

from bs4 import BeautifulSoup


def text_to_html_fragment(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").strip()
    if not normalized:
        return ""
    paragraphs = [part.strip() for part in normalized.split("\n") if part.strip()]
    if not paragraphs:
        return ""
    return "".join(f"<p>{escape(part)}</p>" for part in paragraphs)


def extract_html_fragment(soup: BeautifulSoup, selectors: tuple[str, ...]) -> str:
    for selector in selectors:
        node = soup.select_one(selector)
        if node is not None:
            return str(node)
    return ""
