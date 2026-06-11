"""NYC 311 complaints connector — pulls real data from NYC Open Data Socrata API."""

import os
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from ..mcp_clients.mongodb_client import MongoDBClient

# NYC Open Data Socrata endpoint — real live data, updated daily
NYC_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
APP_TOKEN = os.environ.get("NYC_OPEN_DATA_APP_TOKEN", "")  # Optional, increases rate limit


class ComplaintsConnector:
    """Pulls NYC 311 complaints from Socrata API and stores in MongoDB."""

    def __init__(self):
        self.mongo = MongoDBClient()

    def _build_headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if APP_TOKEN:
            headers["X-App-Token"] = APP_TOKEN
        return headers

    async def fetch_recent(self, hours: int = 48, limit: int = 2000, borough: str | None = None) -> list[dict]:
        """Fetch recent 311 complaints from NYC Open Data."""
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%S")
        params: dict[str, Any] = {
            "$where": f"created_date >= '{cutoff}'",
            "$limit": limit,
            "$order": "created_date DESC",
            "$select": (
                "unique_key,created_date,complaint_type,descriptor,incident_zip,"
                "borough,city,status,latitude,longitude,location"
            ),
        }
        if borough:
            params["$where"] += f" AND borough='{borough.upper()}'"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(NYC_311_URL, params=params, headers=self._build_headers())
            resp.raise_for_status()
            return resp.json()

    def normalize(self, raw: dict) -> dict | None:
        """Normalize a Socrata 311 record to CityPilot schema."""
        try:
            lat = float(raw.get("latitude") or 0)
            lng = float(raw.get("longitude") or 0)
            return {
                "unique_key": raw.get("unique_key", ""),
                "created_date": datetime.fromisoformat(
                    raw["created_date"].replace("T", " ").split(".")[0]
                ).replace(tzinfo=timezone.utc),
                "complaint_type": raw.get("complaint_type", "Unknown"),
                "descriptor": raw.get("descriptor", ""),
                "incident_zip": raw.get("incident_zip", ""),
                "borough": raw.get("borough", ""),
                "status": raw.get("status", ""),
                "latitude": lat if lat != 0 else None,
                "longitude": lng if lng != 0 else None,
                "location": (
                    {"type": "Point", "coordinates": [lng, lat]}
                    if lat and lng else None
                ),
                "source": "nyc_311",
                "ingested_at": datetime.now(timezone.utc),
            }
        except Exception:
            return None

    async def sync(self, hours: int = 48, limit: int = 2000):
        """Fetch and upsert recent 311 complaints into MongoDB."""
        print(f"Fetching NYC 311 complaints (last {hours}h, limit {limit})...")
        try:
            records = await self.fetch_recent(hours=hours, limit=limit)
        except Exception as e:
            print(f"NYC 311 API error: {e} — inserting mock complaints.")
            await self._insert_mock_complaints()
            return

        docs = [self.normalize(r) for r in records]
        docs = [d for d in docs if d]

        if not docs:
            print("No complaints fetched.")
            return

        # Upsert by unique_key to avoid duplicates
        from pymongo import UpdateOne
        ops = [
            UpdateOne(
                {"unique_key": d["unique_key"]},
                {"$set": d},
                upsert=True,
            )
            for d in docs
        ]
        result = await self.mongo.async_db.complaints.bulk_write(ops, ordered=False)
        print(f"NYC 311 sync: {result.upserted_count} new, {result.modified_count} updated, {len(docs)} total.")

    async def _insert_mock_complaints(self):
        """Insert realistic mock complaints for demo when API unavailable."""
        import random
        # Stadium area complaints (Upper West Side)
        complaint_types = ["Noise - Commercial", "Street Light Condition", "HEAT/HOT WATER",
                           "Blocked Driveway", "Illegal Parking", "Traffic Signal Condition"]
        # Real NYC zip codes around Stadium area
        zips = ["10023", "10024", "10025", "10019", "10036"]
        # Rough lat/lng range for Upper West Side
        docs = []
        for i in range(300):
            lat = round(40.770 + random.uniform(-0.03, 0.03), 6)
            lng = round(-73.985 + random.uniform(-0.02, 0.02), 6)
            created = datetime.now(timezone.utc) - timedelta(hours=random.randint(0, 47))
            docs.append({
                "unique_key": f"mock_{i:05d}",
                "created_date": created,
                "complaint_type": random.choice(complaint_types),
                "descriptor": "Mock complaint for demo",
                "incident_zip": random.choice(zips),
                "borough": "MANHATTAN",
                "status": "Open",
                "latitude": lat,
                "longitude": lng,
                "location": {"type": "Point", "coordinates": [lng, lat]},
                "source": "mock",
                "ingested_at": datetime.now(timezone.utc),
            })
        await self.mongo.async_db.complaints.insert_many(docs)
        print(f"Inserted {len(docs)} mock complaints.")

    async def get_stats(self) -> dict:
        """Get summary stats for the complaints collection."""
        total = await self.mongo.async_db.complaints.count_documents({})
        recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        recent = await self.mongo.async_db.complaints.count_documents(
            {"created_date": {"$gte": recent_cutoff}}
        )
        return {"total": total, "last_48h": recent}
