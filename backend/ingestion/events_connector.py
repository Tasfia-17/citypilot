"""Events connector — fetches NYC events from Ticketmaster Discovery API."""

import os
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from ..mcp_clients.mongodb_client import MongoDBClient

TICKETMASTER_BASE = "https://app.ticketmaster.com/discovery/v2"


class EventsConnector:
    """Pulls upcoming NYC events from Ticketmaster and stores in MongoDB."""

    def __init__(self):
        self.api_key = os.environ.get("TICKETMASTER_API_KEY", "")
        self.mongo = MongoDBClient()

    async def fetch_nyc_events(self, days_ahead: int = 7) -> list[dict]:
        """Fetch upcoming NYC events from Ticketmaster Discovery API."""
        start = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).strftime("%Y-%m-%dT%H:%M:%SZ")

        params: dict[str, Any] = {
            "apikey": self.api_key,
            "city": "New York",
            "stateCode": "NY",
            "startDateTime": start,
            "endDateTime": end,
            "size": 50,
            "sort": "date,asc",
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{TICKETMASTER_BASE}/events.json", params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get("_embedded", {}).get("events", [])

    def normalize(self, raw: dict) -> dict:
        """Normalize Ticketmaster event to CityPilot schema."""
        venue = raw.get("_embedded", {}).get("venues", [{}])[0]
        lat = float(venue.get("location", {}).get("latitude", 0) or 0)
        lng = float(venue.get("location", {}).get("longitude", 0) or 0)
        start_str = raw.get("dates", {}).get("start", {}).get("dateTime", "")

        return {
            "event_id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "type": raw.get("type", "event"),
            "classifications": [
                c.get("segment", {}).get("name", "")
                for c in raw.get("classifications", [])
            ],
            "start_date": (
                datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                if start_str else None
            ),
            "venue_name": venue.get("name", ""),
            "venue_address": venue.get("address", {}).get("line1", ""),
            "venue_city": venue.get("city", {}).get("name", ""),
            "venue_zip": venue.get("postalCode", ""),
            "capacity": int(raw.get("pleaseNote", "").split("capacity")[0].split()[-1])
            if "capacity" in raw.get("pleaseNote", "").lower() else None,
            "url": raw.get("url", ""),
            "latitude": lat if lat != 0 else None,
            "longitude": lng if lng != 0 else None,
            "location": (
                {"type": "Point", "coordinates": [lng, lat]}
                if lat and lng else None
            ),
            "source": "ticketmaster",
            "ingested_at": datetime.now(timezone.utc),
        }

    async def sync(self):
        """Fetch and upsert upcoming NYC events."""
        if not self.api_key:
            print("TICKETMASTER_API_KEY not set — inserting mock events.")
            await self._insert_mock_events()
            return

        try:
            events = await self.fetch_nyc_events()
        except Exception as e:
            print(f"Ticketmaster API error: {e} — inserting mock events.")
            await self._insert_mock_events()
            return

        if not events:
            print("No events found.")
            return

        from pymongo import UpdateOne
        docs = [self.normalize(e) for e in events]
        ops = [
            UpdateOne(
                {"event_id": d["event_id"]},
                {"$set": d},
                upsert=True,
            )
            for d in docs
        ]
        result = await self.mongo.async_db.events.bulk_write(ops, ordered=False)
        print(f"Events sync: {result.upserted_count} new, {result.modified_count} updated.")

    async def _insert_mock_events(self):
        """Insert realistic mock events for demo."""
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        mock_events = [
            {
                "event_id": "mock_football_001",
                "name": "NY Football Classic — District 7 Stadium",
                "type": "Sports",
                "classifications": ["Sports"],
                "start_date": tomorrow.replace(hour=19, minute=0),
                "venue_name": "District 7 Stadium",
                "venue_address": "4 Pennsylvania Plaza",
                "venue_city": "New York",
                "venue_zip": "10001",
                "capacity": 60000,
                "latitude": 40.7505,
                "longitude": -73.9934,
                "location": {"type": "Point", "coordinates": [-73.9934, 40.7505]},
                "source": "mock",
                "ingested_at": datetime.now(timezone.utc),
            },
            {
                "event_id": "mock_concert_001",
                "name": "Summer Concert Series",
                "type": "Music",
                "classifications": ["Music"],
                "start_date": tomorrow.replace(hour=20, minute=30),
                "venue_name": "Central Park Amphitheater",
                "venue_address": "Central Park",
                "venue_city": "New York",
                "venue_zip": "10024",
                "capacity": 15000,
                "latitude": 40.7812,
                "longitude": -73.9665,
                "location": {"type": "Point", "coordinates": [-73.9665, 40.7812]},
                "source": "mock",
                "ingested_at": datetime.now(timezone.utc),
            },
        ]
        from pymongo import UpdateOne
        ops = [UpdateOne({"event_id": d["event_id"]}, {"$set": d}, upsert=True) for d in mock_events]
        await self.mongo.async_db.events.bulk_write(ops, ordered=False)
        print(f"Inserted {len(mock_events)} mock events.")

    async def get_upcoming_events(self, hours_ahead: int = 24) -> list[dict]:
        """Get events starting within the next N hours."""
        window_end = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
        cursor = self.mongo.async_db.events.find(
            {"start_date": {"$gte": datetime.now(timezone.utc), "$lte": window_end}}
        ).sort("start_date", 1)
        return await cursor.to_list(length=20)
