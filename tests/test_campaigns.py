import pytest

from app.services import distribute_shares


def create(client, **overrides):
    body = {"name": "test_ageev_a", "geo": "mx, au", "offer_id": 1, **overrides}
    return client.post("/api/campaigns", json=body)


def offer_shares(client, campaign_id):
    streams = client.get(f"/api/campaigns/{campaign_id}").json()["streams"]
    return {offer["offer_id"]: offer["share"] for offer in streams[1]["offers"]}


@pytest.mark.parametrize("count,expected", [(1, [100]), (2, [50, 50]), (3, [34, 33, 33]), (7, [15, 15, 14, 14, 14, 14, 14])])
def test_distribute_shares_sums_to_100(count, expected):
    shares = distribute_shares(count)
    assert shares == expected
    assert sum(shares) == 100


def test_create_builds_two_flows(client, keitaro):
    response = create(client)
    assert response.status_code == 201
    campaign_id = response.json()["keitaro_id"]
    first, second = keitaro.streams[campaign_id]
    assert first["action_payload"] == "https://google.com"
    assert first["filters"] == [{"name": "country", "mode": "accept", "payload": ["MX", "AU"]}]
    assert second["offers"][0]["offer_id"] == 1 and second["offers"][0]["share"] == 100
    assert client.get("/api/campaigns").json()[0]["geo"] == "MX,AU"


def test_create_passes_group_domain_and_source(client, keitaro):
    campaign_id = create(client, group_id=7, domain_id=3, source_id=5).json()["keitaro_id"]
    stored = keitaro.campaigns[campaign_id]
    assert (stored["group_id"], stored["domain_id"], stored["traffic_source_id"]) == (7, 3, 5)


def test_create_rejects_bad_geo(client):
    assert create(client, geo="MEX").status_code == 422


def test_create_rejects_unknown_offer(client, keitaro):
    assert create(client, offer_id=99).status_code == 404
    assert keitaro.campaigns == {}


def test_failed_stream_creation_removes_campaign(client, keitaro, monkeypatch):
    from app.keitaro import KeitaroError

    def broken(payload):
        raise KeitaroError(422, "bad stream")

    monkeypatch.setattr(keitaro, "create_stream", broken)
    assert create(client).status_code == 502
    assert keitaro.campaigns == {}


def test_add_and_remove_offers_rebalance_shares(client):
    campaign_id = create(client).json()["keitaro_id"]
    client.post(f"/api/campaigns/{campaign_id}/offers", json={"offer_id": 2})
    response = client.post(f"/api/campaigns/{campaign_id}/offers", json={"offer_id": 3})
    assert response.status_code == 201
    assert offer_shares(client, campaign_id) == {1: 34, 2: 33, 3: 33}

    response = client.delete(f"/api/campaigns/{campaign_id}/offers/1")
    assert response.status_code == 200
    assert offer_shares(client, campaign_id) == {2: 50, 3: 50}
    assert [item["action"] for item in response.json()["history"]] == ["removed", "added", "added"]


def test_duplicate_offer_conflicts(client):
    campaign_id = create(client).json()["keitaro_id"]
    assert client.post(f"/api/campaigns/{campaign_id}/offers", json={"offer_id": 1}).status_code == 409


def test_last_offer_cannot_be_removed(client):
    campaign_id = create(client).json()["keitaro_id"]
    assert client.delete(f"/api/campaigns/{campaign_id}/offers/1").status_code == 400


def test_update_shares_validates_sum(client):
    campaign_id = create(client).json()["keitaro_id"]
    client.post(f"/api/campaigns/{campaign_id}/offers", json={"offer_id": 2})
    url = f"/api/campaigns/{campaign_id}/shares"
    assert client.put(url, json={"shares": [{"offer_id": 1, "share": 60}, {"offer_id": 2, "share": 30}]}).status_code == 400
    assert client.put(url, json={"shares": [{"offer_id": 1, "share": 60}, {"offer_id": 2, "share": 40}]}).status_code == 200
    assert offer_shares(client, campaign_id) == {1: 60, 2: 40}


def test_offer_search(client):
    assert [offer["id"] for offer in client.get("/api/offers", params={"q": "two"}).json()] == [2]
    assert [offer["id"] for offer in client.get("/api/offers", params={"q": "3"}).json()] == [3]
