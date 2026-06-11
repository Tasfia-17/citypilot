"""
CityPilot FastAPI server — REST + WebSocket endpoints for the Situation Room dashboard.
"""

import asyncio
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from .agents.orchestrator import build_orchestrator
from .mcp_clients.mongodb_client import MongoDBClient
from .mcp_clients.dynatrace_client import DynatraceClient
from .mcp_clients.arize_client import setup_phoenix_tracing, get_agent_health_summary
from .mcp_clients.fivetran_client import FivetranClient
from .ingestion import run_full_sync


# ─── Settings ─────────────────────────────────────────────────────────────────

class Settings(BaseSettings):
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "citypilot"
    google_api_key: str = ""
    elastic_url: str = ""
    elastic_api_key: str = ""
    dynatrace_url: str = ""
    dynatrace_api_token: str = ""
    phoenix_collector_endpoint: str = ""
    fivetran_api_key: str = ""
    fivetran_api_secret: str = ""
    openweather_api_key: str = ""
    ticketmaster_api_key: str = ""
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = "backend/.env"


settings = Settings()

# Push settings to env for ADK agents
os.environ.update({
    "MONGODB_URI": settings.mongodb_uri,
    "MONGODB_DB": settings.mongodb_db,
    "GOOGLE_API_KEY": settings.google_api_key,
    "ELASTIC_URL": settings.elastic_url,
    "ELASTIC_API_KEY": settings.elastic_api_key,
    "ELASTIC_MCP_URL": f"{settings.elastic_url}/_mcp" if settings.elastic_url else "",
    "DYNATRACE_URL": settings.dynatrace_url,
    "DYNATRACE_API_TOKEN": settings.dynatrace_api_token,
    "DYNATRACE_MCP_URL": f"{settings.dynatrace_url}/mcp" if settings.dynatrace_url else "",
    "PHOENIX_COLLECTOR_ENDPOINT": settings.phoenix_collector_endpoint,
    "FIVETRAN_API_KEY": settings.fivetran_api_key,
    "FIVETRAN_API_SECRET": settings.fivetran_api_secret,
    "OPENWEATHER_API_KEY": settings.openweather_api_key,
    "TICKETMASTER_API_KEY": settings.ticketmaster_api_key,
})


# ─── Lifespan ─────────────────────────────────────────────────────────────────

mongo = MongoDBClient()
dynatrace = DynatraceClient()
fivetran = FivetranClient()
ws_connections: set[WebSocket] = set()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Startup: init DB, tracing, run initial sync."""
    print("CityPilot starting up...")
    await mongo.setup_collections()
    setup_phoenix_tracing()

    # Run initial data sync in background
    asyncio.create_task(run_full_sync())

    # Schedule periodic sync (every 30 minutes)
    asyncio.create_task(_periodic_sync())

    yield

    mongo.close()
    await dynatrace.close()
    await fivetran.close()


async def _periodic_sync():
    """Run data sync every 30 minutes."""
    while True:
        await asyncio.sleep(30 * 60)
        try:
            await run_full_sync()
            await _broadcast({"type": "data_updated", "timestamp": datetime.now(timezone.utc).isoformat()})
        except Exception as e:
            print(f"Periodic sync error: {e}")


async def _broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    if not ws_connections:
        return
    dead = set()
    for ws in ws_connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)
    ws_connections -= dead


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="CityPilot API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request / Response Models ────────────────────────────────────────────────

class MissionRequest(BaseModel):
    mission: str
    district: str = "district_7"


class ApproveRequest(BaseModel):
    plan_id: str
    approved: bool
    notes: str = ""


# ─── Mission Endpoint ─────────────────────────────────────────────────────────

@app.post("/api/mission")
async def run_mission(req: MissionRequest, background_tasks: BackgroundTasks):
    """
    Main endpoint: execute a city mission using the multi-agent system.
    Streams progress via WebSocket while running.
    """
    background_tasks.add_task(_execute_mission, req.mission, req.district)
    return {"status": "started", "mission": req.mission, "district": req.district}


async def _execute_mission(mission: str, district: str):
    """Run the full agent pipeline and broadcast progress."""
    await _broadcast({"type": "mission_started", "mission": mission, "district": district})

    try:
        # Boost Fivetran pipelines if it's an event day
        await fivetran.boost_for_event()

        # Import and run ADK runner
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        orchestrator = build_orchestrator()
        session_service = InMemorySessionService()
        session = await session_service.create_session(
            state={}, app_name="citypilot", user_id="mayor"
        )
        runner = Runner(app_name="citypilot", agent=orchestrator, session_service=session_service)

        user_msg = types.Content(role="user", parts=[types.Part(text=mission)])

        agent_trace = []
        final_result = None

        async for event in runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=user_msg,
        ):
            # Broadcast each agent event for live trace UI
            if hasattr(event, "author") and event.author:
                trace_entry = {
                    "type": "agent_event",
                    "agent": event.author,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            trace_entry["message"] = part.text[:500]
                        if hasattr(part, "function_call"):
                            trace_entry["tool_call"] = part.function_call.name
                agent_trace.append(trace_entry)
                await _broadcast(trace_entry)

            # Capture final result
            if hasattr(event, "content") and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        final_result = part.text

        # Try to parse JSON result
        briefing = None
        if final_result:
            try:
                # Find JSON in the output
                start = final_result.find("{")
                end = final_result.rfind("}") + 1
                if start >= 0 and end > start:
                    briefing = json.loads(final_result[start:end])
            except json.JSONDecodeError:
                briefing = {"raw_output": final_result}

        await _broadcast({
            "type": "mission_complete",
            "briefing": briefing,
            "agent_trace": agent_trace,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    except Exception as e:
        await _broadcast({
            "type": "mission_error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        raise


# ─── Map Data ─────────────────────────────────────────────────────────────────

@app.get("/api/map")
async def get_map_data():
    """Return all data needed for the deck.gl map layers."""
    return await mongo.get_map_data()


@app.get("/api/complaints")
async def get_complaints(hours: int = 48, limit: int = 2000):
    """Return recent complaints for heatmap layer."""
    complaints = await mongo.get_recent_complaints(hours=hours, limit=limit)
    return [
        {
            "lat": c.get("latitude"),
            "lng": c.get("longitude"),
            "type": c.get("complaint_type"),
            "zip": c.get("incident_zip"),
            "borough": c.get("borough"),
            "created_date": c.get("created_date", "").isoformat() if c.get("created_date") else "",
        }
        for c in complaints
        if c.get("latitude") and c.get("longitude")
    ]


@app.get("/api/hotspots")
async def get_hotspots(hours: int = 48):
    """Return complaint hotspots for the map."""
    return await mongo.get_complaint_hotspots(hours=hours)


# ─── Action Plans ─────────────────────────────────────────────────────────────

@app.get("/api/plans/active")
async def get_active_plan():
    """Get the current pending/approved action plan."""
    plan = await mongo.get_active_plan()
    if not plan:
        return {"plan": None}
    plan["_id"] = str(plan["_id"])
    return {"plan": plan}


@app.post("/api/plans/approve")
async def approve_plan(req: ApproveRequest):
    """Mayor approves or rejects an action plan."""
    success = await mongo.approve_action_plan(req.plan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Plan not found")

    status = "approved" if req.approved else "rejected"
    await _broadcast({
        "type": "plan_approved",
        "plan_id": req.plan_id,
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"status": status, "plan_id": req.plan_id}


# ─── System Health ─────────────────────────────────────────────────────────────

@app.get("/api/health")
async def get_system_health():
    """System health: infrastructure status + agent health from Phoenix."""
    infra = await dynatrace.get_service_health_summary()
    fivetran_status = await fivetran.get_connector_status()
    agent_health = get_agent_health_summary()
    complaint_stats = {}
    try:
        from .ingestion.complaints_connector import ComplaintsConnector
        complaint_stats = await ComplaintsConnector().get_stats()
    except Exception:
        pass

    return {
        "status": "operational",
        "infrastructure": infra,
        "data_pipelines": fivetran_status,
        "agent_health": agent_health,
        "complaint_stats": complaint_stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/events")
async def get_upcoming_events():
    """Return upcoming events for the next 24 hours."""
    from .ingestion.events_connector import EventsConnector
    connector = EventsConnector()
    events = await connector.get_upcoming_events(hours_ahead=24)
    return [
        {
            **{k: v for k, v in e.items() if k != "_id"},
            "start_date": e.get("start_date", "").isoformat() if e.get("start_date") else "",
        }
        for e in events
    ]


# ─── WebSocket ────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Live WebSocket for real-time agent trace and map updates."""
    await ws.accept()
    ws_connections.add(ws)
    try:
        # Send initial state
        await ws.send_json({"type": "connected", "message": "CityPilot Situation Room connected"})
        while True:
            # Keep alive + handle client messages
            data = await ws.receive_json()
            if data.get("type") == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_connections.discard(ws)


# ─── Sync Trigger ─────────────────────────────────────────────────────────────

@app.post("/api/sync")
async def trigger_sync(background_tasks: BackgroundTasks):
    """Manually trigger a full data ingestion sync."""
    background_tasks.add_task(run_full_sync)
    return {"status": "sync_started"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api.server:app", host="0.0.0.0", port=8000, reload=True)
