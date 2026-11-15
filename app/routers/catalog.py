from fastapi import APIRouter, Depends, Query

from app.config import settings
from app.keitaro import KeitaroClient, get_keitaro
from app.schemas import Option

router = APIRouter(prefix="/api", tags=["catalog"])


@router.get("/offers", response_model=list[Option])
def search_offers(q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=100), keitaro: KeitaroClient = Depends(get_keitaro)):
    needle = q.strip().lower()
    offers = [offer for offer in keitaro.list_offers() if offer.get("state", "active") != "deleted"]
    if needle:
        offers = [offer for offer in offers if needle in offer["name"].lower() or needle == str(offer["id"])]
    return [{"id": offer["id"], "name": offer["name"]} for offer in offers[:limit]]


@router.get("/options")
def options(keitaro: KeitaroClient = Depends(get_keitaro)):
    def pick(items: list[dict], label: str = "name") -> list[dict]:
        return [{"id": item["id"], "name": item[label]} for item in items]

    return {
        "groups": pick(keitaro.list_groups()),
        "domains": pick(keitaro.list_domains()),
        "sources": pick(keitaro.list_sources()),
        "defaults": {
            "group_id": settings.default_group_id,
            "domain_id": settings.default_domain_id,
            "source_id": settings.default_source_id,
        },
    }
