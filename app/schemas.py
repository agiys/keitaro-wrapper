import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

GEO_RE = re.compile(r"^[A-Za-z]{2}$")


class CampaignCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: list[str] = Field(min_length=1)
    offer_id: int
    group_id: int | None = None
    domain_id: int | None = None
    source_id: int | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("geo", mode="before")
    @classmethod
    def split_geo(cls, value):
        if isinstance(value, str):
            value = value.split(",")
        return [item.strip().upper() for item in value if str(item).strip()]

    @field_validator("geo")
    @classmethod
    def check_geo(cls, value: list[str]) -> list[str]:
        for code in value:
            if not GEO_RE.match(code):
                raise ValueError(f"invalid country code: {code}")
        return list(dict.fromkeys(value))


class OfferAdd(BaseModel):
    offer_id: int


class ShareItem(BaseModel):
    offer_id: int
    share: int = Field(ge=0, le=100)


class SharesUpdate(BaseModel):
    shares: list[ShareItem] = Field(min_length=1)


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    keitaro_id: int
    name: str
    alias: str
    geo: str
    created_at: datetime


class Option(BaseModel):
    id: int
    name: str
