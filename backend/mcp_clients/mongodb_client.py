"""MongoDB MCP client — direct PyMongo wrapper for non-agent code (seeding, API layer)."""

import os
from typing import Any
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.operations import SearchIndexModel


class MongoDBClient:
    """Async MongoDB client for CityPilot operations."""

    def __init__(self):
        self.uri = os.environ["MONGODB_URI"]
        self.db_name = os.environ.get("MONGODB_DB", "citypilot")
        self._async_client: AsyncIOMotorClient | None = None
        self._sync_client: MongoClient | None = None

    @property
    def async_db(self):
        if not self._async_client:
            self._async_client = AsyncIOMotorClient(self.uri)
        return self._async_client[self.db_name]

    @property
    def sync_db(self):
        if not self._sync_client:
            self._sync_client = MongoClient(self.uri)
        return self._sync_client[self.db_name]

    async def setup_collections(self):
        """Create collections with proper indexes for city operations."""
        db = self.async_db

        # Time-series for sensor readings
        existing = await db.list_collection_names()
        if "sensor_readings" not in existing:
            await db.create_collection(
                "sensor_readings",
                timeseries={
                    "timeField": "timestamp",
                    "metaField": "sensor_id",
                    "granularity": "minutes",
                },
            )

        # Complaints with geo index
        await db.complaints.create_index([("location", "2dsphere")])
        await db.complaints.create_index([("created_date", DESCENDING)])
        await db.complaints.create_index([("complaint_type", ASCENDING), ("incident_zip", ASCENDING)])

        # Action plans
        await db.action_plans.create_index([("created_at", DESCENDING)])
        await db.action_plans.create_index([("status", ASCENDING)])

        # Infrastructure
        await db.infrastructure.create_index([("location", "2dsphere")])

        # Events
        await db.events.create_index([("start_date", ASCENDING)])
        await db.events.create_index([("venue.location", "2dsphere")])

        print("MongoDB collections and indexes created.")

    async def setup_vector_index(self):
        """Create vector search index on complaints collection for semantic similarity."""
        db = self.async_db
        index_model = SearchIndexModel(
            definition={
                "fields": [
                    {"type": "vector", "path": "embedding", "numDimensions": 768, "similarity": "cosine"},
                    {"type": "filter", "path": "incident_zip"},
                    {"type": "filter", "path": "complaint_type"},
                ]
            },
            name="complaint_embeddings",
            type="vectorSearch",
        )
        try:
            await db.complaints.create_search_index(index_model)
            print("Vector search index created on complaints.")
        except Exception as e:
            print(f"Vector index may already exist: {e}")

    async def get_recent_complaints(
        self, hours: int = 48, borough: str | None = None, limit: int = 1000
    ) -> list[dict]:
        """Fetch recent complaints with optional borough filter."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        query: dict[str, Any] = {"created_date": {"$gte": cutoff}}
        if borough:
            query["borough"] = borough.upper()
        cursor = self.async_db.complaints.find(query).sort("created_date", DESCENDING).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_complaint_hotspots(self, hours: int = 48) -> list[dict]:
        """Aggregate complaint hotspots by zip code in the time window."""
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        pipeline = [
            {"$match": {"created_date": {"$gte": cutoff}}},
            {"$group": {
                "_id": "$incident_zip",
                "count": {"$sum": 1},
                "complaint_types": {"$addToSet": "$complaint_type"},
                "avg_lat": {"$avg": "$latitude"},
                "avg_lng": {"$avg": "$longitude"},
            }},
            {"$sort": {"count": -1}},
            {"$limit": 20},
        ]
        return await self.async_db.complaints.aggregate(pipeline).to_list(length=20)

    async def store_action_plan(self, plan: dict) -> str:
        """Store an action plan and return its ID."""
        plan["created_at"] = datetime.now(timezone.utc)
        plan["status"] = plan.get("status", "pending_approval")
        result = await self.async_db.action_plans.insert_one(plan)
        return str(result.inserted_id)

    async def approve_action_plan(self, plan_id: str) -> bool:
        """Mark an action plan as approved."""
        from bson import ObjectId
        result = await self.async_db.action_plans.update_one(
            {"_id": ObjectId(plan_id)},
            {"$set": {"status": "approved", "approved_at": datetime.now(timezone.utc)}},
        )
        return result.modified_count > 0

    async def get_active_plan(self) -> dict | None:
        """Get the most recent pending or approved action plan."""
        return await self.async_db.action_plans.find_one(
            {"status": {"$in": ["pending_approval", "approved"]}},
            sort=[("created_at", DESCENDING)],
        )

    async def get_map_data(self) -> dict:
        """Fetch all data needed for the map layers."""
        complaints = await self.get_recent_complaints(hours=48, limit=2000)
        hotspots = await self.get_complaint_hotspots(hours=48)

        # Active action plans with coordinates
        plan = await self.get_active_plan()
        risk_zones = []
        if plan and "actions" in plan:
            for action in plan["actions"]:
                if action.get("coordinates"):
                    risk_zones.append({
                        "zone": action.get("department", ""),
                        "action": action.get("action", ""),
                        "lat": action["coordinates"].get("lat"),
                        "lng": action["coordinates"].get("lng"),
                    })

        return {
            "complaints": [
                {
                    "lat": c.get("latitude"),
                    "lng": c.get("longitude"),
                    "type": c.get("complaint_type"),
                    "zip": c.get("incident_zip"),
                }
                for c in complaints
                if c.get("latitude") and c.get("longitude")
            ],
            "hotspots": hotspots,
            "risk_zones": risk_zones,
        }

    def close(self):
        if self._async_client:
            self._async_client.close()
        if self._sync_client:
            self._sync_client.close()
