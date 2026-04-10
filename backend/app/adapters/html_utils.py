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


def sanitize_html_fragment(raw_html: str) -> str:
    wrapper = BeautifulSoup(f"<div id='content-root'>{raw_html or ''}</div>", "html.parser")
    root = wrapper.select_one("#content-root")
    if root is None:
        return ""
    for node in root.select("script, noscript, iframe, frame, object, embed, base, meta, link, form, input, button, textarea, select, option"):
        node.decompose()
    for node in root.select("*"):
        for attribute_name in list(node.attrs.keys()):
            lower_name = attribute_name.lower()
            value = node.attrs.get(attribute_name)
            value_text = " ".join(value) if isinstance(value, list) else str(value or "")
            if lower_name.startswith("on"):
                del node.attrs[attribute_name]
                continue
            if lower_name in {"href", "src"} and value_text.strip().lower().startswith("javascript:"):
                del node.attrs[attribute_name]
                continue
            if lower_name == "target":
                node.attrs[attribute_name] = "_blank"
        if node.name == "a":
            node.attrs["rel"] = "noreferrer noopener"
    return root.decode_contents()
