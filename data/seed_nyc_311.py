#!/usr/bin/env python3
"""
Seed MongoDB with real NYC 311 data from NYC Open Data.

Usage:
    python data/seed_nyc_311.py              # Seed last 30 days, 10k records
    python data/seed_nyc_311.py --days 90    # Seed last 90 days
    python data/seed_nyc_311.py --limit 50000

This uses the real Socrata API: https://data.cityofnewyork.us/resource/erm2-nwe9.json
"""

import asyncio
import argparse
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / "backend" / ".env")

from backend.mcp_clients.mongodb_client import MongoDBClient
from backend.mcp_clients.elastic_client import ElasticClient

NYC_311_URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
APP_TOKEN = os.environ.get("NYC_OPEN_DATA_APP_TOKEN", "")

BOROUGH_FOCUS = ["MANHATTAN", "BROOKLYN", "QUEENS"]
COMPLAINT_TYPES_OF_INTEREST = [
    "Noise - Commercial", "Street Light Condition", "HEAT/HOT WATER",
    "Blocked Driveway", "Illegal Parking", "Traffic Signal Condition",
    "Water System", "Pothole", "Sidewalk Condition", "Homeless Encampment",
    "Noise - Residential", "Air Quality", "Unsanitary Condition",
    "Sewer", "Snow or Ice", "Derelict Vehicle",
]


async def fetch_batch(
    client: httpx.AsyncClient,
    offset: int,
    limit: int,
    cutoff: str,
    borough: str,
) -> list[dict]:
    """Fetch one batch of 311 complaints."""
    headers = {"Accept": "application/json"}
    if APP_TOKEN:
        headers["X-App-Token"] = APP_TOKEN

    params = {
        "$where": f"created_date >= '{cutoff}' AND borough='{borough}'",
        "$limit": limit,
        "$offset": offset,
        "$order": "created_date DESC",
        "$select": (
            "unique_key,created_date,complaint_type,descriptor,incident_zip,"
            "borough,city,status,latitude,longitude"
        ),
    }

    try:
        resp = await client.get(NYC_311_URL, params=params, headers=headers)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Batch error (offset={offset}, borough={borough}): {e}")
        return []


def normalize_complaint(raw: dict) -> dict | None:
    """Normalize a Socrata record."""
    try:
        lat = float(raw.get("latitude") or 0)
        lng = float(raw.get("longitude") or 0)
        created_str = raw.get("created_date", "")

        # Parse various date formats from Socrata
        for fmt in ["%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"]:
            try:
                created = datetime.strptime(created_str[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
                break
            except ValueError:
                continue
        else:
            return None

        return {
            "unique_key": raw["unique_key"],
            "created_date": created,
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
            "source": "nyc_311_seed",
            "ingested_at": datetime.now(timezone.utc),
        }
    except (KeyError, ValueError, TypeError):
        return None


async def seed_complaints(days: int = 30, total_limit: int = 10000):
    """Main seeding function — fetches real NYC 311 data and stores in MongoDB."""
    mongo = MongoDBClient()
    await mongo.setup_collections()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    per_borough = total_limit // len(BOROUGH_FOCUS)
    batch_size = 1000

    print(f"Seeding NYC 311 data: last {days} days, ~{total_limit} records total")
    print(f"Boroughs: {', '.join(BOROUGH_FOCUS)}")
    print()

    grand_total = 0

    async with httpx.AsyncClient(timeout=60) as client:
        for borough in BOROUGH_FOCUS:
            inserted = 0
            offset = 0
            print(f"Fetching {borough}...")

            while inserted < per_borough:
                batch = await fetch_batch(client, offset, batch_size, cutoff, borough)
                if not batch:
                    break

                docs = [normalize_complaint(r) for r in batch]
                docs = [d for d in docs if d and d.get("unique_key")]

                if not docs:
                    break

                # Bulk upsert
                from pymongo import UpdateOne
                ops = [
                    UpdateOne(
                        {"unique_key": d["unique_key"]},
                        {"$set": d},
                        upsert=True,
                    )
                    for d in docs
                ]
                try:
                    result = await mongo.async_db.complaints.bulk_write(ops, ordered=False)
                    batch_inserted = result.upserted_count + result.modified_count
                    inserted += batch_inserted
                    grand_total += batch_inserted
                    print(f"  {borough}: +{batch_inserted} (total: {inserted})")
                except Exception as e:
                    print(f"  Write error: {e}")

                offset += len(batch)
                if len(batch) < batch_size:
                    break

                await asyncio.sleep(0.3)  # Rate limiting

            print(f"  {borough} complete: {inserted} records\n")

    print(f"Seeding complete! Total records: {grand_total}")

    # Create vector search index after seeding
    print("Setting up vector search index...")
    await mongo.setup_vector_index()

    # Seed Elasticsearch knowledge base
    print("Seeding Elastic knowledge base...")
    elastic = ElasticClient()
    try:
        await elastic.setup_indices()
        await elastic.seed_city_knowledge()
    except Exception as e:
        print(f"Elastic seeding skipped (not configured): {e}")
    finally:
        await elastic.close()

    mongo.close()
    print("\nAll done! CityPilot database is ready.")


async def seed_resources():
    """Seed city resources (crews, vehicles) into MongoDB."""
    mongo = MongoDBClient()
    resources = [
        {"type": "sanitation_crew", "id": "crew_001", "status": "available", "zone": "district_7", "capacity": 4},
        {"type": "sanitation_crew", "id": "crew_002", "status": "available", "zone": "district_7", "capacity": 4},
        {"type": "traffic_officer", "id": "officer_001", "status": "available", "zone": "district_7"},
        {"type": "traffic_officer", "id": "officer_002", "status": "available", "zone": "district_7"},
        {"type": "traffic_officer", "id": "officer_003", "status": "available", "zone": "district_5"},
        {"type": "repair_crew", "id": "repair_001", "status": "available", "zone": "district_7", "specialty": "water"},
        {"type": "repair_crew", "id": "repair_002", "status": "available", "zone": "district_5", "specialty": "electrical"},
        {"type": "emergency_vehicle", "id": "emv_001", "status": "available", "zone": "district_7"},
    ]
    from pymongo import UpdateOne
    ops = [UpdateOne({"id": r["id"]}, {"$set": r}, upsert=True) for r in resources]
    await mongo.async_db.resources.bulk_write(ops, ordered=False)
    print(f"Seeded {len(resources)} city resources.")
    mongo.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed CityPilot MongoDB with real NYC 311 data")
    parser.add_argument("--days", type=int, default=30, help="Days of history to fetch (default: 30)")
    parser.add_argument("--limit", type=int, default=10000, help="Total records to fetch (default: 10000)")
    args = parser.parse_args()

    async def main():
        await seed_complaints(days=args.days, total_limit=args.limit)
        await seed_resources()

    asyncio.run(main())
