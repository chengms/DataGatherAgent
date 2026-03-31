from fastapi import APIRouter

from app.services.registry import adapter_registry


router = APIRouter()


@router.get("/sources")
def list_sources() -> list[dict[str, str]]:
    return [
        {"name": source.name, "kind": source.kind, "description": source.description}
        for source in adapter_registry.list_discovery_sources()
    ]

