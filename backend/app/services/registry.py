from app.adapters.base import BaseDiscoveryAdapter, BaseFetchAdapter
from app.adapters.mock_wechat import MockWechatFetchAdapter, MockWechatSearchAdapter


class AdapterRegistry:
    def __init__(self) -> None:
        self._discovery: dict[str, BaseDiscoveryAdapter] = {
            "mock_wechat_search": MockWechatSearchAdapter(),
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

