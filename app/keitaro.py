import httpx

from app.config import settings


class KeitaroError(Exception):
    def __init__(self, status: int, detail):
        super().__init__(str(detail))
        self.status = status
        self.detail = detail


class KeitaroClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self._http = httpx.Client(
            base_url=f"{(base_url or settings.keitaro_url).rstrip('/')}/admin_api/v1",
            headers={"Api-Key": api_key or settings.keitaro_api_key},
            timeout=30,
        )

    def _request(self, method: str, path: str, **kwargs):
        response = self._http.request(method, path, **kwargs)
        try:
            data = response.json()
        except ValueError:
            data = response.text
        if response.status_code >= 400:
            raise KeitaroError(response.status_code, data)
        return data

    def list_offers(self) -> list[dict]:
        return self._request("GET", "/offers")

    def get_offer(self, offer_id: int) -> dict:
        return self._request("GET", f"/offers/{offer_id}")

    def list_groups(self) -> list[dict]:
        return self._request("GET", "/groups", params={"type": "campaigns"})

    def list_domains(self) -> list[dict]:
        return self._request("GET", "/domains")

    def list_sources(self) -> list[dict]:
        return self._request("GET", "/traffic_sources")

    def create_campaign(self, payload: dict) -> dict:
        return self._request("POST", "/campaigns", json=payload)

    def get_campaign(self, campaign_id: int) -> dict:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def delete_campaign(self, campaign_id: int) -> None:
        self._request("DELETE", f"/campaigns/{campaign_id}")

    def create_stream(self, payload: dict) -> dict:
        return self._request("POST", "/streams", json=payload)

    def list_streams(self, campaign_id: int) -> list[dict]:
        return self._request("GET", f"/campaigns/{campaign_id}/streams")

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)

    def report(self, campaign_id: int, grouping: str) -> list[dict]:
        body = {
            "range": {"interval": "all_time"},
            "metrics": ["clicks", "campaign_unique_clicks", "bots", "conversions"],
            "grouping": [grouping],
            "filters": [{"name": "campaign_id", "operator": "EQUALS", "expression": campaign_id}],
        }
        return self._request("POST", "/report/build", json=body)["rows"]


def get_keitaro() -> KeitaroClient:
    return KeitaroClient()
