from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.mock_wechat import MockWechatFetchAdapter, MockWechatSearchAdapter
from app.adapters.web_search_live import WebSearchWechatAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._discovery: dict[str, BaseDiscoveryAdapter] = {
            "mock_wechat_search": MockWechatSearchAdapter(),
            "web_search_wechat": WebSearchWechatAdapter(),
        }
        self._fetch: dict[str, BaseFetchAdapter] = {
            "wechat": MockWechatFetchAdapter(),
        }

    def get_discovery(self, name: str) -> BaseDiscoveryAdapter:
        return self._discovery[name]

    def get_fetch(self, platform: str) -> BaseFetchAdapter:
        return self._fetch[platform]

    def list_discovery_sources(self) -> list[BaseDiscoveryAdapter]:
        return list(self._discovery.values())


adapter_registry = AdapterRegistry()
