"""Fivetran client — manages data pipeline connectors for weather, events, and 311."""

import os
import httpx
from typing import Any


class FivetranClient:
    """Fivetran REST API client for pipeline management."""

    BASE_URL = "https://api.fivetran.com/v1"

    # Connector IDs (set after creating connectors in Fivetran dashboard)
    CONNECTOR_IDS = {
        "weather": os.environ.get("FIVETRAN_WEATHER_CONNECTOR_ID", ""),
        "nyc_311": os.environ.get("FIVETRAN_311_CONNECTOR_ID", ""),
        "ticketmaster": os.environ.get("FIVETRAN_EVENTS_CONNECTOR_ID", ""),
    }

    def __init__(self):
        self.api_key = os.environ.get("FIVETRAN_API_KEY", "")
        self.api_secret = os.environ.get("FIVETRAN_API_SECRET", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def auth(self) -> tuple[str, str]:
        return (self.api_key, self.api_secret)

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                auth=self.auth,
                timeout=30,
            )
        return self._client

    async def list_connectors(self) -> list[dict]:
        """List all Fivetran connectors."""
        if not self.api_key:
            return []
        try:
            resp = await self.client.get("/connectors")
            resp.raise_for_status()
            return resp.json().get("data", {}).get("items", [])
        except Exception as e:
            print(f"Fivetran list_connectors error: {e}")
            return []

    async def trigger_sync(self, connector_name: str) -> bool:
        """Trigger an immediate sync for a connector."""
        connector_id = self.CONNECTOR_IDS.get(connector_name, "")
        if not connector_id or not self.api_key:
            print(f"[Fivetran] Trigger sync: {connector_name} (no connector ID configured)")
            return False
        try:
            resp = await self.client.post(f"/connectors/{connector_id}/sync")
            resp.raise_for_status()
            print(f"Fivetran sync triggered for {connector_name}")
            return True
        except Exception as e:
            print(f"Fivetran trigger_sync error: {e}")
            return False

    async def update_sync_frequency(self, connector_name: str, frequency_minutes: int) -> bool:
        """Update sync frequency for a connector — used by orchestrator for event days."""
        connector_id = self.CONNECTOR_IDS.get(connector_name, "")
        if not connector_id or not self.api_key:
            print(f"[Fivetran] Update sync frequency: {connector_name} → {frequency_minutes}min")
            return False
        try:
            resp = await self.client.patch(
                f"/connectors/{connector_id}",
                json={"sync_frequency": frequency_minutes},
            )
            resp.raise_for_status()
            print(f"Fivetran {connector_name} sync frequency updated to {frequency_minutes}min")
            return True
        except Exception as e:
            print(f"Fivetran update_sync_frequency error: {e}")
            return False

    async def boost_for_event(self):
        """Boost weather sync to 5min and trigger events sync — called on match day detection."""
        print("[Fivetran] Event detected: boosting data pipeline sync frequencies.")
        await self.update_sync_frequency("weather", frequency_minutes=5)
        await self.trigger_sync("nyc_311")
        await self.trigger_sync("ticketmaster")

    async def get_connector_status(self) -> dict[str, Any]:
        """Get sync status for all city data connectors."""
        connectors = await self.list_connectors()
        status = {}
        for name, cid in self.CONNECTOR_IDS.items():
            connector_data = next((c for c in connectors if c.get("id") == cid), None)
            if connector_data:
                status[name] = {
                    "id": cid,
                    "status": connector_data.get("status", {}).get("sync_state", "unknown"),
                    "last_sync": connector_data.get("succeeded_at", "never"),
                }
            else:
                status[name] = {"id": cid or "not_configured", "status": "not_configured"}
        return status

    async def close(self):
        if self._client:
            await self._client.aclose()
