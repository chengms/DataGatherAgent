import re
from datetime import UTC, datetime

import requests
from bs4 import BeautifulSoup

from app.adapters.base import BaseFetchAdapter, DiscoverySourceInfo


class FetchRequestError(RuntimeError):
    pass


class WebFetchWechatAdapter(BaseFetchAdapter):
    info = DiscoverySourceInfo(
        name="web_fetch_wechat",
        kind="fetch",
        description="Directly fetches mp.weixin.qq.com article pages and extracts article details.",
        live=True,
    )

    def __init__(self, timeout_seconds: int = 20) -> None:
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

    def fetch(self, candidate: dict) -> dict:
        url = candidate["source_url"]
        try:
            response = self.session.get(url, timeout=self.timeout_seconds)
        except Exception as exc:
            raise FetchRequestError("article fetch request failed") from exc
        if response.status_code >= 400:
            raise FetchRequestError(f"article fetch failed with status {response.status_code}")
        return self._parse_article_page(candidate, response.text)

    def _parse_article_page(self, candidate: dict, html: str) -> dict:
        soup = BeautifulSoup(html, "html.parser")

        title = self._first_text(soup.select_one("#activity-name")) or self._first_text(soup.select_one("h1")) or candidate["title"]
        account_name = self._first_text(soup.select_one("#js_name")) or candidate["account_name"]
        publish_time = self._extract_publish_time(soup, html)
        content_text = self._extract_content_text(soup)
        read_count = self._extract_metric(html, ["read_num", "readCount"])
        comment_count = self._extract_metric(html, ["comment_id", "commentCount"])
        source_id = candidate["source_url"].rstrip("/").split("/")[-1]

        return {
            "keyword": candidate["keyword"],
            "platform": "wechat",
            "title": title,
            "source_url": candidate["source_url"],
            "account_name": account_name,
            "publish_time": publish_time,
            "read_count": read_count,
            "comment_count": comment_count,
            "content_text": content_text,
            "source_id": source_id,
        }

    def _extract_content_text(self, soup: BeautifulSoup) -> str:
        container = soup.select_one("#js_content") or soup.select_one(".rich_media_content")
        if container is None:
            raise FetchRequestError("article content not found")
        text = container.get_text("\n", strip=True)
        if not text:
            raise FetchRequestError("article content is empty")
        return text

    def _extract_publish_time(self, soup: BeautifulSoup, html: str) -> datetime:
        time_text = self._first_text(soup.select_one("#publish_time"))
        if time_text:
            parsed = self._try_parse_datetime(time_text)
            if parsed is not None:
                return parsed

        match = re.search(r"var\s+ct\s*=\s*['\"]?(\d{10})['\"]?", html)
        if match:
            return datetime.fromtimestamp(int(match.group(1)), tz=UTC)

        return datetime.now(UTC)

    def _extract_metric(self, html: str, keys: list[str]) -> int:
        for key in keys:
            patterns = [
                rf'"{re.escape(key)}"\s*:\s*(\d+)',
                rf"{re.escape(key)}\s*[:=]\s*['\"]?(\d+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, html)
                if match:
                    return int(match.group(1))
        return 0

    def _try_parse_datetime(self, raw: str) -> datetime | None:
        cleaned = raw.strip().replace("\u00a0", " ")
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
            try:
                return datetime.strptime(cleaned, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
        return None

    def _first_text(self, node) -> str | None:
        if node is None:
            return None
        text = node.get_text(" ", strip=True)
        return text or None
