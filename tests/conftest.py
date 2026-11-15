import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.keitaro import KeitaroError, get_keitaro
from app.main import app


class FakeKeitaro:
    def __init__(self):
        self.offers = {1: "Offer one", 2: "Offer two", 3: "Offer three"}
        self.campaigns = {}
        self.streams = {}
        self.next_id = 100

    def _id(self):
        self.next_id += 1
        return self.next_id

    def list_offers(self):
        return [{"id": key, "name": value} for key, value in self.offers.items()]

    def get_offer(self, offer_id):
        if offer_id not in self.offers:
            raise KeitaroError(404, "not found")
        return {"id": offer_id, "name": self.offers[offer_id]}

    def list_groups(self):
        return [{"id": 7, "name": "FORTESTS"}]

    def list_domains(self):
        return []

    def list_sources(self):
        return []

    def create_campaign(self, payload):
        campaign = {**payload, "id": self._id()}
        self.campaigns[campaign["id"]] = campaign
        self.streams[campaign["id"]] = []
        return campaign

    def get_campaign(self, campaign_id):
        if campaign_id not in self.campaigns:
            raise KeitaroError(404, "not found")
        return self.campaigns[campaign_id]

    def delete_campaign(self, campaign_id):
        self.campaigns.pop(campaign_id)
        self.streams.pop(campaign_id)

    def create_stream(self, payload):
        stream = {**payload, "id": self._id(), "filters": payload.get("filters", [])}
        stream["offers"] = [{**offer, "state": "active"} for offer in payload.get("offers", [])]
        self.streams[payload["campaign_id"]].append(stream)
        return stream

    def list_streams(self, campaign_id):
        return self.streams[campaign_id]

    def update_stream(self, stream_id, payload):
        for streams in self.streams.values():
            for stream in streams:
                if stream["id"] == stream_id:
                    stream["offers"] = payload["offers"]
                    return stream

    def report(self, campaign_id, grouping):
        return []


@pytest.fixture
def keitaro():
    return FakeKeitaro()


@pytest.fixture
def client(keitaro):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_keitaro] = lambda: keitaro
    yield TestClient(app)
    app.dependency_overrides.clear()
