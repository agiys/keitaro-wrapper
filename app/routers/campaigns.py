from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app import services
from app.db import get_db
from app.keitaro import KeitaroClient, get_keitaro
from app.models import Campaign
from app.schemas import CampaignCreate, CampaignOut, OfferAdd, SharesUpdate

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("", response_model=list[CampaignOut])
def list_campaigns(db: Session = Depends(get_db)):
    return db.query(Campaign).order_by(Campaign.id.desc()).all()


@router.post("", response_model=CampaignOut, status_code=201)
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    return services.create_campaign(db, keitaro, data)


@router.get("/{campaign_id}")
def get_campaign(campaign_id: int, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    return services.campaign_details(db, keitaro, campaign_id)


@router.post("/{campaign_id}/offers", status_code=201)
def add_offer(campaign_id: int, data: OfferAdd, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    services.add_offer(db, keitaro, campaign_id, data.offer_id)
    return services.campaign_details(db, keitaro, campaign_id)


@router.delete("/{campaign_id}/offers/{offer_id}")
def remove_offer(campaign_id: int, offer_id: int, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    services.remove_offer(db, keitaro, campaign_id, offer_id)
    return services.campaign_details(db, keitaro, campaign_id)


@router.put("/{campaign_id}/shares")
def update_shares(campaign_id: int, data: SharesUpdate, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    services.update_shares(keitaro, campaign_id, {item.offer_id: item.share for item in data.shares})
    return services.campaign_details(db, keitaro, campaign_id)
