"""Impact Forecaster Agent — semantic search Elastic + MongoDB vector search for historical precedents."""

import os
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams, StreamableHTTPConnectionParams
from mcp import StdioServerParameters


def build_impact_forecaster() -> Agent:
    """Return a single-turn agent that forecasts impact using Elastic + MongoDB vector search."""
    mongo_uri = os.environ["MONGODB_URI"]
    elastic_url = os.environ.get("ELASTIC_MCP_URL", "")
    elastic_api_key = os.environ.get("ELASTIC_API_KEY", "")

    tools = [
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=["-y", "@mongodb-js/mongodb-mcp-server", "--connectionString", mongo_uri],
                ),
            ),
            tool_filter=["find", "aggregate", "collection-schema"],
        )
    ]

    # Add Elastic MCP if configured
    if elastic_url and elastic_api_key:
        tools.append(
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=elastic_url,
                    headers={
                        "Authorization": f"ApiKey {elastic_api_key}",
                        "Content-Type": "application/json",
                    },
                ),
            )
        )

    return Agent(
        name="impact_forecaster",
        model="gemini-2.0-flash",
        mode="single_turn",
        description="Forecasts city impact by searching historical incidents and city knowledge base.",
        instruction="""You are CityPilot's Impact Forecaster.

Given anomalies and current signals, forecast the impact using historical precedent:

1. **Semantic Search (Elastic)** — if available:
   - Search `city_knowledge` index for SOPs matching current scenario
     e.g., "bus rerouting protocol during stadium event with rain and transit maintenance"
   - Search `city_policies` for emergency procedures relevant to detected anomalies
   - Use hybrid search combining BM25 + vector for best recall
   - Extract: affected_zones, recommended_actions, past_outcomes

2. **Historical Vector Search (MongoDB)**:
   - Use `aggregate` with $vectorSearch on complaints collection
     Pipeline: [{$vectorSearch: {index: "complaint_embeddings", path: "embedding",
     queryVector: <embed current scenario>, numCandidates: 100, limit: 5}}]
   - Find incidents from same zone in similar conditions (past 2 years)
   - Calculate: average complaint spike duration, resolution time, affected population

3. **Impact Calculation**:
   - Based on event size (from events collection), weather severity, and historical patterns
   - Estimate: congestion increase %, complaint volume spike %, affected population
   - Confidence score based on historical data availability

Return:
{
  "scenario_description": "...",
  "historical_precedents": [{"date": "...", "similarity": 0.95, "outcome": "..."}],
  "elastic_sop": {"title": "...", "key_actions": [...], "source": "..."},
  "impact_forecast": {
    "congestion_increase_pct": 45,
    "complaint_spike_pct": 60,
    "affected_population": 12000,
    "peak_window": "14:00-20:00",
    "confidence": 0.87
  },
  "risk_zones": [{"zone": "...", "risk_level": "HIGH", "lat": ..., "lng": ...}]
}""",
        tools=tools,
    )
