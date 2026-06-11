"""Dynatrace client — registers city systems as services and provides DQL query helpers."""

import os
import httpx
from typing import Any


class DynatraceClient:
    """Client for Dynatrace Grail API — queries observability data for city systems."""

    # City systems registered as Dynatrace services
    CITY_SERVICES = {
        "transit-data-feed": "Public Transit APIs",
        "traffic-control-system": "Traffic Signal Network",
        "utility-water-grid": "Water Distribution",
        "weather-ingestion-service": "Weather Data Pipeline",
        "nyc-311-feed": "311 Complaint Feed",
    }

    def __init__(self):
        self.base_url = os.environ.get("DYNATRACE_URL", "")
        self.api_token = os.environ.get("DYNATRACE_API_TOKEN", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict:
        return {
            "Authorization": f"Api-Token {self.api_token}",
            "Content-Type": "application/json",
        }

    @property
    def client(self) -> httpx.AsyncClient:
        if not self._client:
            self._client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers, timeout=30)
        return self._client

    async def get_active_problems(self) -> list[dict]:
        """Fetch active Dynatrace problems for city systems."""
        if not self.base_url:
            return []
        try:
            resp = await self.client.get("/api/v2/problems", params={"status": "OPEN"})
            resp.raise_for_status()
            problems = resp.json().get("problems", [])
            # Filter to city-related services
            city_problems = [
                p for p in problems
                if any(svc in str(p) for svc in self.CITY_SERVICES)
            ]
            return city_problems
        except Exception as e:
            print(f"Dynatrace get_active_problems error: {e}")
            return []

    async def execute_dql(self, query: str) -> dict[str, Any]:
        """Execute a DQL query against Dynatrace Grail."""
        if not self.base_url:
            return {"results": []}
        try:
            resp = await self.client.post(
                "/platform/storage/query/v1/query:execute",
                json={"query": query},
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Dynatrace DQL error: {e}")
            return {"results": []}

    async def check_transit_api_health(self) -> dict:
        """Check transit-data-feed latency using DQL."""
        dql = (
            'fetch logs | filter service == "transit-data-feed" '
            '| summarize avg_latency = avg(duration), count = count() '
            '| fields avg_latency, count'
        )
        result = await self.execute_dql(dql)
        records = result.get("result", {}).get("records", [])
        if records:
            avg_lat = records[0].get("avg_latency", 0)
            return {
                "service": "transit-data-feed",
                "avg_latency_ms": avg_lat,
                "status": "DEGRADED" if avg_lat > 5000 else "HEALTHY",
            }
        return {"service": "transit-data-feed", "status": "UNKNOWN"}

    async def get_service_health_summary(self) -> dict[str, str]:
        """Get health status for all registered city services."""
        problems = await self.get_active_problems()
        degraded_services = {
            p.get("affectedEntities", [{}])[0].get("name", ""): p.get("title", "")
            for p in problems
        }

        health = {}
        for service_id, service_name in self.CITY_SERVICES.items():
            health[service_id] = "DEGRADED" if any(service_id in k for k in degraded_services) else "HEALTHY"

        return health

    async def simulate_transit_latency_spike(self):
        """For demo: log a simulated latency spike to Dynatrace."""
        if not self.base_url:
            print("[DEMO] Simulated transit API latency spike: 8500ms")
            return
        # In real deployment, this would push a custom metric
        await self.client.post(
            "/api/v2/metrics/ingest",
            content="transit.api.response_time,service=transit-data-feed 8500",
        )

    async def close(self):
        if self._client:
            await self._client.aclose()
