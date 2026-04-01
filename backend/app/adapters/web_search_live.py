from datetime import UTC, datetime
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from app.adapters.base import BaseDiscoveryAdapter, DiscoverySourceInfo


class SearchRequestError(RuntimeError):
    pass


class WebSearchWechatAdapter(BaseDiscoveryAdapter):
    info = DiscoverySourceInfo(
        name="web_search_wechat",
        kind="search",
        description="Search engine discovery constrained to mp.weixin.qq.com pages.",
        live=True,
    )

    def __init__(
        self,
        base_url: str = "https://www.bing.com/search",
        timeout_seconds: int = 20,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/135.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )

    def search(self, keyword: str, limit: int) -> list[dict]:
        query = f"site:mp.weixin.qq.com {keyword}"
        url = f"{self.base_url}?q={quote_plus(query)}&count={limit}"
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
        except Exception as exc:
            raise SearchRequestError("search request failed") from exc
        if response.status_code >= 400:
            raise SearchRequestError(f"search request failed with status {response.status_code}")
        candidates = self._parse_bing_html(response.text, limit)
        now = datetime.now(UTC)
        return [
            {
                "keyword": keyword,
                "source_engine": self.info.name,
                "title": item["title"],
                "snippet": item["snippet"],
                "source_url": item["source_url"],
                "account_name": item["account_name"],
                "discovered_at": now,
            }
            for item in candidates
        ]

    def _parse_bing_html(self, html: str, limit: int) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[dict] = []

        for card in soup.select("li.b_algo"):
            anchor = card.select_one("h2 a")
            if anchor is None:
                continue
            href = anchor.get("href", "").strip()
            if "mp.weixin.qq.com" not in href:
                continue
            snippet_node = card.select_one(".b_caption p")
            title = anchor.get_text(" ", strip=True)
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            items.append(
                {
                    "title": title,
                    "snippet": snippet,
                    "source_url": href,
                    "account_name": self._extract_account_name(title=title, snippet=snippet),
                }
            )
            if len(items) >= limit:
                return items

        for anchor in soup.select("a[href]"):
            href = urljoin(self.base_url, anchor.get("href", "").strip())
            title = anchor.get_text(" ", strip=True)
            if not title or "mp.weixin.qq.com" not in href:
                continue
            items.append(
                {
                    "title": title,
                    "snippet": "",
                    "source_url": href,
                    "account_name": self._extract_account_name(title=title, snippet=""),
                }
            )
            if len(items) >= limit:
                break

        deduped: list[dict] = []
        seen: set[str] = set()
        for item in items:
            if item["source_url"] in seen:
                continue
            seen.add(item["source_url"])
            deduped.append(item)
        return deduped[:limit]

    def _extract_account_name(self, title: str, snippet: str) -> str:
        for candidate in (snippet, title):
            lowered = candidate.lower()
            if "wechat" in lowered or "weixin" in lowered:
                return "WeChat Official Account"
        return "Unknown WeChat Account"
