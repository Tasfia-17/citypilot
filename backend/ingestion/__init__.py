"""Ingestion layer — runs all data connectors."""

import asyncio
from .weather_connector import WeatherConnector
from .complaints_connector import ComplaintsConnector
from .events_connector import EventsConnector


async def run_full_sync():
    """Run all three connectors in parallel."""
    weather = WeatherConnector()
    complaints = ComplaintsConnector()
    events = EventsConnector()

    await asyncio.gather(
        weather.sync_all_districts(),
        complaints.sync(hours=48, limit=2000),
        events.sync(),
        return_exceptions=True,
    )
    print("Full ingestion sync complete.")


__all__ = ["WeatherConnector", "ComplaintsConnector", "EventsConnector", "run_full_sync"]
