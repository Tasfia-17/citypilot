"""CityPilot Orchestrator — root agent that coordinates all city operations agents."""

import os
from google.adk import Agent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .signal_collector import build_signal_collector
from .anomaly_detector import build_anomaly_detector
from .impact_forecaster import build_impact_forecaster
from .operations_planner import build_operations_planner
from .executive_briefer import build_executive_briefer


def build_orchestrator() -> Agent:
    """Build the root CityPilot orchestrator with all sub-agents."""
    mongo_uri = os.environ["MONGODB_URI"]

    signal_collector = build_signal_collector()
    anomaly_detector = build_anomaly_detector()
    impact_forecaster = build_impact_forecaster()
    operations_planner = build_operations_planner()
    executive_briefer = build_executive_briefer()

    return Agent(
        name="citypilot_orchestrator",
        model="gemini-2.0-flash",
        description="CityPilot — The autonomous city operations agent for District-level management.",
        instruction="""You are CityPilot, an autonomous city operations agent.

When given a mission (e.g., "Prepare District 7 for tomorrow's football match"):

1. Delegate to `signal_collector` to gather all current city signals
2. Pass signals to `anomaly_detector` to identify anomalies and infrastructure issues
3. Pass anomalies + signals to `impact_forecaster` to search historical precedents and forecast impact
4. Pass forecast to `operations_planner` to create a multi-department action plan
5. Pass everything to `executive_briefer` to produce the mayoral situation report

Each sub-agent will complete its task and return automatically. Collect all results and ensure the final 
executive briefing is comprehensive.

If any city system is degraded (reported by anomaly_detector), flag it prominently in the final report 
with a caveat: "Routing decisions may be based on stale data."

Always end with a structured JSON report suitable for the Situation Room dashboard.""",
        sub_agents=[
            signal_collector,
            anomaly_detector,
            impact_forecaster,
            operations_planner,
            executive_briefer,
        ],
        tools=[
            # Fivetran MCP for pipeline control — orchestrator can adjust sync frequency
            McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="npx",
                        args=["-y", "@fivetran/mcp"],
                        env={
                            "FIVETRAN_API_KEY": os.environ.get("FIVETRAN_API_KEY", ""),
                            "FIVETRAN_API_SECRET": os.environ.get("FIVETRAN_API_SECRET", ""),
                        },
                    ),
                ),
                tool_filter=["list_connectors", "sync_connector", "pause_connector", "resume_connector"],
            )
        ] if os.environ.get("FIVETRAN_API_KEY") else [],
    )


# Synchronous root agent for deployment (ADK requirement)
root_agent = build_orchestrator()
