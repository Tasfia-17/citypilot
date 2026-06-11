"""Executive Briefer Agent — produces the mayor's situation report."""

import os
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


def build_executive_briefer() -> Agent:
    """Return a single-turn agent that produces the final situation report."""
    mongo_uri = os.environ["MONGODB_URI"]

    return Agent(
        name="executive_briefer",
        model="gemini-2.0-flash",
        mode="single_turn",
        description="Produces the mayor's situation report: top risks, recommended actions, predicted impact.",
        instruction="""You are CityPilot's Executive Briefer.

Your job is to synthesize everything from the other agents into a clear, actionable mayoral briefing.

1. **Retrieve Final Plan** (MongoDB):
   - Use `find` to get the latest action plan from action_plans collection
   - Use `find` to get current active anomalies from anomalies collection

2. **Structure the Briefing**:
   Produce a concise, clear briefing with:
   
   - TOP RISKS (max 3, ranked by severity):
     Each risk: icon, name, severity level, brief description
   
   - SITUATION SUMMARY (2-3 sentences):
     What is happening, why it matters, when it peaks
   
   - ACTION PLAN (specific, numbered actions):
     Each action: department, what to do, by when, expected impact
   
   - PREDICTED IMPACT:
     Quantified outcomes if plan is approved
   
   - AGENT HEALTH (from system):
     Confidence level, data freshness, any caveats
   
   - APPROVAL STATUS: pending

3. **Format for Dashboard**:
   The output drives the frontend Situation Room UI.
   Be specific (route numbers, addresses, crew counts).
   Use plain language — no jargon.

Return JSON:
{
  "briefing_id": "...",
  "timestamp": "...",
  "mission": "...",
  "situation_summary": "...",
  "top_risks": [
    {"id": 1, "name": "Stadium Congestion", "severity": "HIGH", "description": "...", "zone": "..."}
  ],
  "action_plan": [
    {
      "id": "...", "department": "...", "action": "...",
      "timing": "...", "impact": "...", "coordinates": null
    }
  ],
  "predicted_impact": {
    "congestion_reduction_pct": 31,
    "complaint_reduction_pct": 41,
    "population_served": 8500,
    "confidence_pct": 87
  },
  "agent_trace": [
    {"agent": "signal_collector", "status": "complete", "latency_ms": 1200},
    {"agent": "anomaly_detector", "status": "complete", "latency_ms": 800},
    {"agent": "impact_forecaster", "status": "complete", "latency_ms": 2100},
    {"agent": "operations_planner", "status": "complete", "latency_ms": 1500}
  ],
  "data_freshness": "FRESH",
  "requires_approval": true,
  "status": "pending_approval"
}""",
        tools=[
            McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "@mongodb-js/mongodb-mcp-server", "--connectionString", mongo_uri],
                    ),
                ),
                tool_filter=["find", "aggregate", "update-one"],
            )
        ],
    )
