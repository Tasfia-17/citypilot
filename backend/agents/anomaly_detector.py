"""Anomaly Detector Agent — detects cross-system anomalies via Dynatrace + MongoDB."""

import os
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams, StreamableHTTPConnectionParams
from mcp import StdioServerParameters


def build_anomaly_detector() -> Agent:
    """Return a single-turn agent that detects infrastructure and data anomalies."""
    mongo_uri = os.environ["MONGODB_URI"]
    dt_url = os.environ.get("DYNATRACE_MCP_URL", "")
    dt_token = os.environ.get("DYNATRACE_API_TOKEN", "")

    tools = [
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@mongodb-js/mongodb-mcp-server", "--connectionString", mongo_uri],
                ),
            ),
            tool_filter=["find", "aggregate", "count"],
        )
    ]

    # Add Dynatrace MCP if configured
    if dt_url and dt_token:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=dt_url,
                    headers={"Authorization": f"Api-Token {dt_token}"},
                ),
                tool_filter=["execute_dql_query", "get_active_problems", "get_entities", "get_metrics"],
            )
        )

    return Agent(
        name="anomaly_detector",
        model="gemini-2.0-flash",
        mode="single_turn",
        description="Detects anomalies in city systems using statistical analysis and Dynatrace observability.",
        instruction="""You are CityPilot's Anomaly Detector.

Given signal data from the Signal Collector, detect anomalies:

1. **Statistical Detection** (MongoDB):
   - Use `aggregate` with $group and $count to calculate complaint volume per zone
   - Compare current 48h volume against 30-day baseline using $lookup or multiple queries
   - Flag zones with >2σ deviation as anomalies
   - Query for infrastructure anomalies in sensor_readings collection

2. **Infrastructure Monitoring** (Dynatrace if available):
   - Call `get_active_problems` to check for degraded city systems
   - Use `execute_dql_query` to check transit API latency:
     `fetch logs | filter service == "transit-data-feed" | summarize avg(duration)`
   - Use `get_metrics` for traffic signal network health

3. **Pattern Detection**:
   - Identify co-occurring signals (event + weather + complaints)
   - Flag data staleness if APIs haven't updated in >30 minutes

Return structured anomalies:
{
  "anomalies": [
    {
      "type": "complaint_spike|infrastructure_degraded|data_stale|pattern",
      "zone": "...",
      "severity": "HIGH|MEDIUM|LOW",
      "description": "...",
      "evidence": {...},
      "system_health": "NOMINAL|DEGRADED|UNKNOWN"
    }
  ],
  "infrastructure_status": {
    "transit_api": "HEALTHY|DEGRADED",
    "traffic_signals": "HEALTHY|DEGRADED",
    "data_freshness": "FRESH|STALE"
  }
}""",
        tools=tools,
    )
