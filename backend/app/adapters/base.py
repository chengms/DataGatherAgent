from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoverySourceInfo:
    name: str
    kind: str
    description: str


class BaseDiscoveryAdapter(ABC):
    info: DiscoverySourceInfo

    @abstractmethod
    def search(self, keyword: str, limit: int) -> list[dict]:
        raise NotImplementedError


class BaseFetchAdapter(ABC):
    @abstractmethod
    def fetch(self, candidate: dict) -> dict:
        raise NotImplementedError

