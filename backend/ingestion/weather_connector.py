"""Weather connector — fetches OpenWeatherMap forecasts for NYC districts."""

import os
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx

from ..mcp_clients.mongodb_client import MongoDBClient

OWM_BASE = "https://api.openweathermap.org/data/2.5"

# NYC district coordinates
DISTRICTS = {
    "district_7": {"lat": 40.7831, "lon": -73.9712, "name": "Upper West Side"},
    "district_5": {"lat": 40.7580, "lon": -73.9855, "name": "Midtown"},
    "district_1": {"lat": 40.7127, "lon": -74.0059, "name": "Lower Manhattan"},
}


class WeatherConnector:
    """Pulls weather + forecast from OpenWeatherMap and stores in MongoDB."""

    def __init__(self):
        self.api_key = os.environ.get("OPENWEATHER_API_KEY", "")
        self.mongo = MongoDBClient()

    async def fetch_current(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch current weather for a location."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{OWM_BASE}/weather",
                params={"lat": lat, "lon": lon, "appid": self.api_key, "units": "imperial"},
            )
            resp.raise_for_status()
            return resp.json()

    async def fetch_forecast(self, lat: float, lon: float) -> dict[str, Any]:
        """Fetch 5-day 3-hour forecast."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{OWM_BASE}/forecast",
                params={"lat": lat, "lon": lon, "appid": self.api_key, "units": "imperial", "cnt": 16},
            )
            resp.raise_for_status()
            return resp.json()

    def parse_weather(self, data: dict, district_id: str, district_info: dict) -> dict:
        """Normalize OWM response to our schema."""
        return {
            "source": "openweathermap",
            "district_id": district_id,
            "district_name": district_info["name"],
            "timestamp": datetime.now(timezone.utc),
            "temperature_f": data.get("main", {}).get("temp"),
            "feels_like_f": data.get("main", {}).get("feels_like"),
            "humidity_pct": data.get("main", {}).get("humidity"),
            "wind_speed_mph": data.get("wind", {}).get("speed"),
            "condition": data.get("weather", [{}])[0].get("main", "Unknown"),
            "description": data.get("weather", [{}])[0].get("description", ""),
            "rain_1h_in": data.get("rain", {}).get("1h", 0),
            "visibility_m": data.get("visibility", 10000),
            "location": {"type": "Point", "coordinates": [district_info["lon"], district_info["lat"]]},
        }

    def parse_forecast_item(self, item: dict, district_id: str) -> dict:
        """Normalize a single forecast item."""
        return {
            "source": "openweathermap_forecast",
            "district_id": district_id,
            "forecast_time": datetime.fromtimestamp(item["dt"], tz=timezone.utc),
            "fetched_at": datetime.now(timezone.utc),
            "temperature_f": item.get("main", {}).get("temp"),
            "condition": item.get("weather", [{}])[0].get("main", "Unknown"),
            "rain_3h_in": item.get("rain", {}).get("3h", 0),
            "pop": item.get("pop", 0),  # Probability of precipitation
        }

    async def sync_all_districts(self):
        """Sync weather for all NYC districts."""
        if not self.api_key:
            print("OPENWEATHER_API_KEY not set — inserting mock weather data.")
            await self._insert_mock_weather()
            return

        for district_id, info in DISTRICTS.items():
            try:
                current = await self.fetch_current(info["lat"], info["lon"])
                forecast = await self.fetch_forecast(info["lat"], info["lon"])

                # Store current conditions
                doc = self.parse_weather(current, district_id, info)
                await self.mongo.async_db.weather.replace_one(
                    {"district_id": district_id},
                    doc,
                    upsert=True,
                )

                # Store forecast items
                forecast_docs = [
                    self.parse_forecast_item(item, district_id)
                    for item in forecast.get("list", [])
                ]
                if forecast_docs:
                    await self.mongo.async_db.weather_forecast.delete_many({"district_id": district_id})
                    await self.mongo.async_db.weather_forecast.insert_many(forecast_docs)

                print(f"Weather synced for {info['name']}: {doc['condition']}, {doc['temperature_f']}°F")
                await asyncio.sleep(0.5)  # Rate limiting
            except Exception as e:
                print(f"Weather sync error for {district_id}: {e}")

    async def _insert_mock_weather(self):
        """Insert realistic mock weather data for demo when no API key."""
        for district_id, info in DISTRICTS.items():
            doc = {
                "source": "mock",
                "district_id": district_id,
                "district_name": info["name"],
                "timestamp": datetime.now(timezone.utc),
                "temperature_f": 68.0,
                "condition": "Rain",
                "description": "light rain",
                "rain_1h_in": 0.3,
                "humidity_pct": 82,
                "wind_speed_mph": 12.0,
                "visibility_m": 6000,
                "location": {"type": "Point", "coordinates": [info["lon"], info["lat"]]},
            }
            await self.mongo.async_db.weather.replace_one({"district_id": district_id}, doc, upsert=True)
        print("Mock weather data inserted.")

    async def get_district_weather(self, district_id: str = "district_7") -> dict | None:
        """Get current weather for a specific district."""
        return await self.mongo.async_db.weather.find_one({"district_id": district_id})
