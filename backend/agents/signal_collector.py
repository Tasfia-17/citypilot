"""Signal Collector Agent — fetches live urban signals via MCP tools."""

import os
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def build_signal_collector() -> Agent:
    """Return a single-turn agent that collects city signals from MongoDB."""
    mongo_uri = os.environ["MONGODB_URI"]

    return Agent(
        name="signal_collector",
        model="gemini-2.0-flash",
        mode="single_turn",
        description="Fetches live urban signals: 311 complaints, weather, events, transit status.",
        instruction="""You are CityPilot's Signal Collector.

Given a mission context (district, time window, event info), use the MongoDB MCP tools to:
1. Query recent 311 complaints (last 48h) in the target district using `find` tool
   - Filter by: created_date >= 48h ago, borough/district
   - Collect: complaint_type, descriptor, incident_zip, latitude, longitude, created_date
2. Query recent traffic incidents using `find` tool on traffic_incidents collection
3. Query upcoming events using `find` tool on events collection
4. Use `count` tool to get complaint volume by type
5. Use `aggregate` tool for complaint hotspot analysis by zip code

Return a structured JSON summary:
{
  "complaints": {"total": N, "by_type": {...}, "hotspots": [...]},
  "events": [...],
  "traffic_incidents": [...],
  "collection_window": "48h",
  "district": "..."
}""",
        tools=[
            McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "@mongodb-js/mongodb-mcp-server", "--connectionString", mongo_uri],
                    ),
                ),
                tool_filter=["find", "aggregate", "count", "collection-schema"],
            )
        ],
    )
