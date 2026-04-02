from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.external_tool import (
    MediaCrawlerBilibiliDiscoveryAdapter,
    MediaCrawlerBilibiliFetchAdapter,
    MediaCrawlerDouyinDiscoveryAdapter,
    MediaCrawlerDouyinFetchAdapter,
    MediaCrawlerWeiboDiscoveryAdapter,
    MediaCrawlerWeiboFetchAdapter,
    MediaCrawlerXiaohongshuDiscoveryAdapter,
    MediaCrawlerXiaohongshuFetchAdapter,
)
from app.adapters.mock_wechat_clean import MockWechatFetchAdapter, MockWechatSearchAdapter
from app.adapters.wechat_exporter_service import WechatExporterFetchAdapter, WechatExporterSearchAdapter
from app.adapters.web_fetch_live import WebFetchWechatAdapter
from app.adapters.web_search_live import WebSearchWechatAdapter
from app.core.exceptions import AdapterNotFoundError


class AdapterRegistry:
    def __init__(self) -> None:
        self._discovery: dict[str, BaseDiscoveryAdapter] = {
            "mock_wechat_search": MockWechatSearchAdapter(),
            "web_search_wechat": WebSearchWechatAdapter(),
            "wechat_exporter_search": WechatExporterSearchAdapter(),
            "xiaohongshu_external_search": MediaCrawlerXiaohongshuDiscoveryAdapter(),
            "weibo_external_search": MediaCrawlerWeiboDiscoveryAdapter(),
            "bilibili_external_search": MediaCrawlerBilibiliDiscoveryAdapter(),
            "douyin_external_search": MediaCrawlerDouyinDiscoveryAdapter(),
        }
        self._fetch: dict[str, BaseFetchAdapter] = {
            "mock_wechat_fetch": MockWechatFetchAdapter(),
            "web_fetch_wechat": WebFetchWechatAdapter(),
            "wechat_exporter_fetch": WechatExporterFetchAdapter(),
            "xiaohongshu_external_fetch": MediaCrawlerXiaohongshuFetchAdapter(),
            "weibo_external_fetch": MediaCrawlerWeiboFetchAdapter(),
            "bilibili_external_fetch": MediaCrawlerBilibiliFetchAdapter(),
            "douyin_external_fetch": MediaCrawlerDouyinFetchAdapter(),
        }

    def get_discovery(self, name: str) -> BaseDiscoveryAdapter:
        try:
            return self._discovery[name]
        except KeyError as exc:
            raise AdapterNotFoundError(name, "discovery") from exc

    def get_fetch(self, name: str) -> BaseFetchAdapter:
        try:
            return self._fetch[name]
        except KeyError as exc:
            raise AdapterNotFoundError(name, "fetch") from exc

    def list_discovery_sources(self) -> list[BaseDiscoveryAdapter]:
        return list(self._discovery.values())

    def list_fetch_sources(self) -> list[BaseFetchAdapter]:
        return list(self._fetch.values())

    def list_discovery_adapters(self) -> list[BaseDiscoveryAdapter]:
        return self.list_discovery_sources()

    def list_fetch_adapters(self) -> list[BaseFetchAdapter]:
        return self.list_fetch_sources()

    def list_sources(self) -> list[BaseDiscoveryAdapter | BaseFetchAdapter]:
        return [*self._discovery.values(), *self._fetch.values()]


adapter_registry = AdapterRegistry()
