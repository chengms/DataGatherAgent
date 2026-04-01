from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.schemas.workflow import DiscoveryCandidate, FetchedArticle


@dataclass(frozen=True)
class AdapterInfo:
    name: str
    kind: str
    platform: str
    description: str
    live: bool = False


class BaseAdapter(ABC):
    info: AdapterInfo

    def supports_platform(self, platform: str) -> bool:
        return self.info.platform == platform


class BaseDiscoveryAdapter(BaseAdapter):
    def discover(self, keyword: str, limit: int) -> list[DiscoveryCandidate]:
        return self._discover(keyword=keyword, limit=limit)

    @abstractmethod
    def _discover(self, keyword: str, limit: int) -> list[DiscoveryCandidate]:
        raise NotImplementedError

    # Compatibility shim for older callers.
    def search(self, keyword: str, limit: int) -> list[dict]:
        return [candidate.model_dump() for candidate in self.discover(keyword=keyword, limit=limit)]


class BaseFetchAdapter(BaseAdapter):
    def fetch_article(self, candidate: DiscoveryCandidate) -> FetchedArticle:
        return self._fetch_article(candidate)

    @abstractmethod
    def _fetch_article(self, candidate: DiscoveryCandidate) -> FetchedArticle:
        raise NotImplementedError

    # Compatibility shim for older callers.
    def fetch(self, candidate: dict) -> dict:
        return self.fetch_article(DiscoveryCandidate.model_validate(candidate)).model_dump()
