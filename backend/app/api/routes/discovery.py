from fastapi import APIRouter

from app.services.registry import adapter_registry


router = APIRouter()


@router.get("/sources")
def list_sources() -> list[dict[str, str]]:
    return [
        {
            "name": source.info.name,
            "kind": source.info.kind,
            "description": source.info.description,
            "live": str(source.info.live).lower(),
        }
        for source in adapter_registry.list_discovery_sources()
    ]
