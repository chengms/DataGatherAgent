from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from app.adapters.base import AdapterInfo, BaseDiscoveryAdapter, BaseFetchAdapter
from app.core.config import WECHAT_EXPORTER_API_KEY, WECHAT_EXPORTER_BASE_URL
from app.core.exceptions import FetchRequestError, SearchRequestError
from app.schemas.workflow import DiscoveryCandidate, FetchedArticle


class WechatExporterServiceClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.base_url = (base_url or WECHAT_EXPORTER_BASE_URL or "").rstrip("/")
        self.api_key = api_key or WECHAT_EXPORTER_API_KEY
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def _headers(self) -> dict[str, str]:
        if not self.api_key:
            raise SearchRequestError(
                "WECHAT_EXPORTER_API_KEY is not configured",
                details={"required_env": "WECHAT_EXPORTER_API_KEY"},
            )
        return {"X-Auth-Key": self.api_key}

    def _request_json(self, path: str, params: dict[str, Any]) -> Any:
        if not self.base_url:
            raise SearchRequestError(
                "WECHAT_EXPORTER_BASE_URL is not configured",
                details={"required_env": "WECHAT_EXPORTER_BASE_URL"},
            )
        url = f"{self.base_url}{path}"
        response = self.session.get(
            url,
            params=params,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise SearchRequestError(
                f"wechat exporter request failed with status {response.status_code}",
                details={"url": url, "params": params, "response": response.text[:1000]},
            )
        try:
            return response.json()
        except ValueError as exc:
            raise SearchRequestError(
                "wechat exporter returned non-JSON response",
                details={"url": url, "params": params, "response": response.text[:1000]},
            ) from exc

    def search_accounts(self, keyword: str, size: int = 3) -> list[dict[str, Any]]:
        payload = self._request_json("/api/public/v1/account", {"keyword": keyword, "size": size})
        return self._extract_items(payload)

    def list_articles(self, fakeid: str, size: int = 10) -> list[dict[str, Any]]:
        payload = self._request_json("/api/public/v1/article", {"fakeid": fakeid, "size": size})
        return self._extract_items(payload)

    def download_article(self, url: str, format_name: str = "html") -> str:
        if not self.base_url:
            raise FetchRequestError(
                "WECHAT_EXPORTER_BASE_URL is not configured",
                details={"required_env": "WECHAT_EXPORTER_BASE_URL"},
            )
        request_url = f"{self.base_url}/api/public/v1/download"
        response = self.session.get(
            request_url,
            params={"url": url, "format": format_name},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        if response.status_code >= 400:
            raise FetchRequestError(
                f"wechat exporter download failed with status {response.status_code}",
                details={"url": url, "response": response.text[:1000]},
            )
        return response.text

    def _extract_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("data", "items", "list", "records"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        raise SearchRequestError(
            "wechat exporter response schema is not recognized",
            details={"response_type": type(payload).__name__},
        )


class WechatExporterSearchAdapter(BaseDiscoveryAdapter):
    info = AdapterInfo(
        name="wechat_exporter_search",
        kind="search",
        platform="wechat",
        description="Searches WeChat public accounts and article lists through a self-hosted wechat-article-exporter service.",
        live=True,
    )

    def __init__(self, client: WechatExporterServiceClient | None = None) -> None:
        self.client = client or WechatExporterServiceClient()

    def _discover(self, keyword: str, limit: int) -> list[DiscoveryCandidate]:
        accounts = self.client.search_accounts(keyword=keyword, size=1)
        if not accounts:
            return []

        fakeid = self._pick_first(accounts, "fakeid", "biz", "id")
        if not fakeid:
            raise SearchRequestError(
                "wechat exporter account search response is missing a fakeid",
                details={"keyword": keyword, "account": accounts[0]},
            )

        account_name = self._pick_first(accounts, "nickname", "name", "account_name") or keyword
        articles = self.client.list_articles(fakeid=fakeid, size=limit)
        now = datetime.now(UTC)
        candidates: list[DiscoveryCandidate] = []
        for article in articles[:limit]:
            source_url = self._pick_first(article, "link", "url", "source_url")
            title = self._pick_first(article, "title", "name")
            if not source_url or not title:
                continue
            candidates.append(
                DiscoveryCandidate(
                    keyword=keyword,
                    source_engine=self.info.name,
                    title=title,
                    snippet=self._pick_first(article, "digest", "summary", "snippet") or "",
                    source_url=source_url,
                    account_name=self._pick_first(article, "nickname", "account_name") or account_name,
                    discovered_at=now,
                )
            )
        return candidates

    def _pick_first(self, payload: list[dict[str, Any]] | dict[str, Any], *keys: str) -> str | None:
        item = payload[0] if isinstance(payload, list) else payload
        for key in keys:
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return None


class WechatExporterFetchAdapter(BaseFetchAdapter):
    info = AdapterInfo(
        name="wechat_exporter_fetch",
        kind="fetch",
        platform="wechat",
        description="Downloads WeChat article content through a self-hosted wechat-article-exporter service.",
        live=True,
    )

    def __init__(self, client: WechatExporterServiceClient | None = None) -> None:
        self.client = client or WechatExporterServiceClient()

    def _fetch_article(self, candidate: DiscoveryCandidate) -> FetchedArticle:
        html = self.client.download_article(candidate.source_url, format_name="html")
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text("\n", strip=True)
        publish_time = self._extract_publish_time(soup)
        source_id = candidate.source_url.rstrip("/").split("/")[-1]
        return FetchedArticle(
            keyword=candidate.keyword,
            platform="wechat",
            source_engine=self.info.name,
            content_kind="article",
            title=self._extract_title(soup) or candidate.title,
            source_url=candidate.source_url,
            account_name=self._extract_account_name(soup) or candidate.account_name,
            publish_time=publish_time,
            read_count=0,
            comment_count=0,
            content_text=text,
            source_id=source_id,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str | None:
        for selector in ("#activity-name", "h1", "title"):
            node = soup.select_one(selector)
            if node is not None:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        return None

    def _extract_account_name(self, soup: BeautifulSoup) -> str | None:
        for selector in ("#js_name", ".profile_meta_value"):
            node = soup.select_one(selector)
            if node is not None:
                text = node.get_text(" ", strip=True)
                if text:
                    return text
        return None

    def _extract_publish_time(self, soup: BeautifulSoup) -> datetime:
        node = soup.select_one("#publish_time")
        if node is not None:
            raw = node.get_text(" ", strip=True)
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M", "%Y/%m/%d"):
                try:
                    return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
        return datetime.now(UTC)
