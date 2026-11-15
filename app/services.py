import secrets
import string

from sqlalchemy.orm import Session

from app.config import settings
from app.keitaro import KeitaroClient, KeitaroError
from app.models import Campaign, OfferChange
from app.schemas import CampaignCreate

GOOGLE_URL = "https://google.com"
ALIAS_ALPHABET = string.ascii_letters + string.digits


class ServiceError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def distribute_shares(count: int) -> list[int]:
    base, extra = divmod(100, count)
    return [base + 1 if index < extra else base for index in range(count)]


def new_alias() -> str:
    return "".join(secrets.choice(ALIAS_ALPHABET) for _ in range(6))


def create_campaign(db: Session, keitaro: KeitaroClient, data: CampaignCreate) -> Campaign:
    group_id = data.group_id or settings.default_group_id
    domain_id = data.domain_id or settings.default_domain_id
    source_id = data.source_id or settings.default_source_id

    try:
        keitaro.get_offer(data.offer_id)
    except KeitaroError as error:
        raise ServiceError(404, f"Offer {data.offer_id} not found in Keitaro") from error

    payload = {
        "name": data.name,
        "alias": new_alias(),
        "type": "position",
        "cost_type": "CPC",
        "cost_value": 0,
        "cost_currency": "USD",
        "group_id": group_id,
        "domain_id": domain_id,
        "traffic_source_id": source_id,
    }
    payload = {key: value for key, value in payload.items() if value is not None}
    created = keitaro.create_campaign(payload)

    try:
        keitaro.create_stream(
            {
                "campaign_id": created["id"],
                "name": "Flow 1",
                "type": "regular",
                "position": 1,
                "schema": "redirect",
                "action_type": "http",
                "action_payload": GOOGLE_URL,
                "collect_clicks": True,
                "filter_or": False,
                "filters": [{"name": "country", "mode": "accept", "payload": data.geo}],
            }
        )
        keitaro.create_stream(
            {
                "campaign_id": created["id"],
                "name": "Flow 2",
                "type": "regular",
                "position": 2,
                "schema": "landings",
                "action_type": "http",
                "collect_clicks": True,
                "offers": [{"offer_id": data.offer_id, "share": 100, "state": "active"}],
            }
        )
    except KeitaroError:
        keitaro.delete_campaign(created["id"])
        raise

    campaign = Campaign(
        keitaro_id=created["id"],
        name=data.name,
        alias=created["alias"],
        geo=",".join(data.geo),
        group_id=group_id,
        domain_id=domain_id,
        source_id=source_id,
    )
    db.add(campaign)
    db.commit()
    return campaign


def find_offer_stream(streams: list[dict]) -> dict:
    for stream in streams:
        if stream.get("schema") == "landings":
            return stream
    raise ServiceError(409, "Campaign has no stream with offers")


def active_offers(stream: dict) -> list[dict]:
    return [offer for offer in stream.get("offers", []) if offer.get("state", "active") == "active"]


def push_offers(keitaro: KeitaroClient, stream_id: int, offers: list[dict]) -> dict:
    return keitaro.update_stream(
        stream_id,
        {"offers": [{"offer_id": o["offer_id"], "share": o["share"], "state": "active"} for o in offers]},
    )


def log_change(db: Session, keitaro_id: int, offer_id: int, action: str) -> None:
    campaign = db.query(Campaign).filter_by(keitaro_id=keitaro_id).one_or_none()
    if campaign:
        db.add(OfferChange(campaign_id=campaign.id, offer_id=offer_id, action=action))
        db.commit()


def add_offer(db: Session, keitaro: KeitaroClient, campaign_id: int, offer_id: int) -> None:
    stream = find_offer_stream(keitaro.list_streams(campaign_id))
    current = active_offers(stream)
    if any(offer["offer_id"] == offer_id for offer in current):
        raise ServiceError(409, f"Offer {offer_id} is already in the campaign")
    try:
        keitaro.get_offer(offer_id)
    except KeitaroError as error:
        raise ServiceError(404, f"Offer {offer_id} not found in Keitaro") from error

    offers = [{"offer_id": offer["offer_id"]} for offer in current] + [{"offer_id": offer_id}]
    for offer, share in zip(offers, distribute_shares(len(offers))):
        offer["share"] = share
    push_offers(keitaro, stream["id"], offers)
    log_change(db, campaign_id, offer_id, "added")


def remove_offer(db: Session, keitaro: KeitaroClient, campaign_id: int, offer_id: int) -> None:
    stream = find_offer_stream(keitaro.list_streams(campaign_id))
    current = active_offers(stream)
    if not any(offer["offer_id"] == offer_id for offer in current):
        raise ServiceError(404, f"Offer {offer_id} is not in the campaign")
    if len(current) == 1:
        raise ServiceError(400, "A campaign must keep at least one offer")

    offers = [{"offer_id": offer["offer_id"]} for offer in current if offer["offer_id"] != offer_id]
    for offer, share in zip(offers, distribute_shares(len(offers))):
        offer["share"] = share
    push_offers(keitaro, stream["id"], offers)
    log_change(db, campaign_id, offer_id, "removed")


def update_shares(keitaro: KeitaroClient, campaign_id: int, shares: dict[int, int]) -> None:
    stream = find_offer_stream(keitaro.list_streams(campaign_id))
    current = active_offers(stream)
    if {offer["offer_id"] for offer in current} != set(shares):
        raise ServiceError(400, "Shares must be given for every offer in the campaign")
    if sum(shares.values()) != 100:
        raise ServiceError(400, "Shares must add up to 100")
    push_offers(keitaro, stream["id"], [{"offer_id": key, "share": value} for key, value in shares.items()])


def campaign_details(db: Session, keitaro: KeitaroClient, campaign_id: int) -> dict:
    campaign = keitaro.get_campaign(campaign_id)
    streams = keitaro.list_streams(campaign_id)
    stream_stats = {row["stream_id"]: row for row in keitaro.report(campaign_id, "stream_id")}
    offer_stats = {row["offer_id"]: row for row in keitaro.report(campaign_id, "offer_id")}
    offer_names = {offer["id"]: offer["name"] for offer in keitaro.list_offers()}

    def stats(row: dict | None) -> dict:
        row = row or {}
        return {
            "clicks": row.get("clicks", 0),
            "unique": row.get("campaign_unique_clicks", 0),
            "bots": row.get("bots", 0),
            "conversions": row.get("conversions", 0),
        }

    local = db.query(Campaign).filter_by(keitaro_id=campaign_id).one_or_none()
    return {
        "id": campaign["id"],
        "name": campaign["name"],
        "alias": campaign["alias"],
        "group_id": campaign.get("group_id"),
        "domain_id": campaign.get("domain_id"),
        "source_id": campaign.get("traffic_source_id"),
        "streams": [
            {
                "id": stream["id"],
                "name": stream["name"],
                "schema": stream["schema"],
                "target": stream.get("action_payload") if stream["schema"] == "redirect" else None,
                "geo": next(
                    (f["payload"] for f in stream.get("filters", []) if f["name"] == "country" and f["mode"] == "accept"),
                    [],
                ),
                "stats": stats(stream_stats.get(stream["id"])),
                "offers": [
                    {
                        "offer_id": offer["offer_id"],
                        "name": offer_names.get(offer["offer_id"], str(offer["offer_id"])),
                        "share": offer["share"],
                        "stats": stats(offer_stats.get(offer["offer_id"])),
                    }
                    for offer in active_offers(stream)
                ],
            }
            for stream in streams
        ],
        "history": [
            {"offer_id": change.offer_id, "action": change.action, "at": change.created_at}
            for change in (local.changes if local else [])
        ],
    }
