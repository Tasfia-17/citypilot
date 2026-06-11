# CityPilot

**The City Has a Brain Now**

Every hour, a city district generates thousands of signals. A rainstorm is coming. A stadium fills with 60,000 people. The subway is under maintenance. Three hundred residents have filed noise and traffic complaints in the last two days. Somewhere in that overlap is a crisis that nobody sees coming, because no single person can hold all those signals at once.

CityPilot does. It reads every signal, finds the crisis before it happens, writes the action plan, and puts it in front of the decision-maker with a single button: Approve.

Built for the Google + MongoDB + Elastic + Dynatrace + Arize + Fivetran Hackathon 2026 using Google ADK 2.0, Gemini 2.0 Flash, and five specialized AI agents connected to real city data through MCP.

---

## The Problem

City operations today are deeply fragmented. Traffic engineers do not talk to transit managers. Sanitation crews are dispatched reactively, after complaints pile up. Weather forecasts sit in one system while event schedules live in another. Infrastructure monitors are separate from public complaint feeds.

When 60,000 people descend on a stadium district during a rainstorm while the local subway line is under maintenance, no single city employee has a complete picture. Each department sees its own slice. Nobody has the full signal until the congestion, complaints, and chaos are already happening.

A mid-size city district generates hundreds of coordinated decisions every week that require data no single human can hold in their head.

---

## How We Built It

We built CityPilot in five concrete layers, one on top of the other. Each layer was designed before the next one started.

### Step 1: Connect Real City Data Sources

Before writing a single agent, we connected to three live public APIs and built ingestion connectors for each one.

**NYC 311 Open Data** via the Socrata API at `data.cityofnewyork.us/resource/erm2-nwe9.json`. This is the real dataset New York City publishes daily. It contains over 24 million service request records: noise complaints, traffic signal failures, water main issues, illegal parking, heat outages. We built `complaints_connector.py` to fetch recent records filtered by date and borough, normalize the Socrata schema into our own document shape, and bulk-upsert into MongoDB with duplicate detection on `unique_key`. Running `python data/seed_nyc_311.py` pulls 30 days of real history across Manhattan, Brooklyn, and Queens.

**OpenWeatherMap** via the forecast API at `api.openweathermap.org/data/2.5/forecast`. We built `weather_connector.py` to fetch current conditions and 5-day 3-hour forecasts for each NYC district centroid, store them in MongoDB, and fall back to realistic mock data when no API key is configured so the demo always runs.

**Ticketmaster Discovery API** at `app.ticketmaster.com/discovery/v2/events.json`. We built `events_connector.py` to pull upcoming NYC events with venue names, addresses, and capacity numbers. A football match with 60,000 attendees tomorrow is a real data signal, not a hardcoded scenario.

All three connectors run on startup and refresh on a background schedule. They also run on demand when the orchestrator agent decides the situation requires fresher data.

### Step 2: Design the MongoDB Data Model

With data flowing, we designed the MongoDB collections to serve every query the agents would need.

The `complaints` collection stores the NYC 311 data with a `2dsphere` geospatial index on `location` for proximity queries, a compound index on `complaint_type` and `incident_zip` for aggregation, and a vector search index named `complaint_embeddings` on a 768-dimension `embedding` field with cosine similarity. That vector index is what allows the Impact Forecaster to find historically similar incidents by semantic meaning, not just keyword match.

The `sensor_readings` collection is a MongoDB native time-series collection created with `timeField: "timestamp"`, `metaField: "sensor_id"`, and `granularity: "minutes"`. This is the right MongoDB type for IoT-style signal data and it enables efficient range queries over the timeline.

The `action_plans` collection stores every agent-generated plan with a `status` field that progresses from `pending_approval` to `approved` or `rejected`. The mayor's click writes a single `update-one` through the MongoDB MCP server.

The `resources` collection stores available city crews, vehicles, and equipment with zone assignments and availability status. The Operations Planner queries this before allocating resources.

### Step 3: Build the Five-Agent Pipeline with Google ADK

With data and storage ready, we built the agents using Google ADK 2.0. Each agent is a separate `Agent` class with its own instruction, model, and MCP toolset. Sub-agents run in `single_turn` mode so they complete their task and return control automatically. The root orchestrator holds them all as `sub_agents`.

**Signal Collector** is the first agent to run on every mission. It connects to the MongoDB MCP server via `StdioConnectionParams` launching `@mongodb-js/mongodb-mcp-server` as a subprocess. It calls `find` to pull 311 complaints from the last 48 hours filtered by district, `aggregate` with a `$group` pipeline to count complaints by type and zip code, and `count` to get volume totals. It also queries the `events` and `weather` collections. Every number in its output came from a live database query, not a language model generating plausible-sounding figures.

**Anomaly Detector** takes the signal summary and runs statistical analysis. It calls MongoDB `aggregate` with `$group` and `$match` to compare current complaint volume against the 30-day baseline stored in the database. Zones with more than two standard deviations of deviation are flagged. It also calls the Dynatrace MCP server via `StreamableHTTPConnectionParams` to check the `get_active_problems` endpoint for any Davis AI problem alerts on city services, and runs a DQL query `fetch logs | filter service == "transit-data-feed" | summarize avg(duration)` to measure actual transit API latency. If the feed is degraded, that caveat is written into the output and propagates through the rest of the pipeline.

**Impact Forecaster** is where the real differentiation happens. It calls the Elastic MCP server to run a hybrid search query against `city_knowledge` and `city_policies`, combining BM25 keyword scoring on policy names with kNN cosine similarity on 768-dimension dense vectors. The query "bus rerouting protocol during stadium event with rain and transit maintenance" returns the actual NYC Stadium Event Traffic Management SOP. It also runs a MongoDB `aggregate` pipeline with a `$vectorSearch` stage against `complaint_embeddings` to find the five most semantically similar historical incidents and their outcomes. The forecast is grounded in both official city policy and empirical case history.

**Operations Planner** reads the forecast and queries MongoDB `find` on the `resources` collection to see what crews and vehicles are actually available in the target district. It generates specific, named actions: which bus route number to reroute and via which street, how many sanitation crews with which zone assignments, which intersections need traffic officers and at what time. It writes the full plan to MongoDB using `insert-many` with `status: "pending_approval"`.

**Executive Briefer** pulls the stored plan from MongoDB with `find` and synthesizes the mayoral situation report. Top three risks ranked by severity. A two-sentence situation summary. The action list with department, timing, and predicted impact per action. Quantified overall impact: congestion reduction percentage, complaint reduction percentage, population served, and prediction confidence. This document is what appears in the dashboard.

### Step 4: Wire Up the Integrations

With the agents working, we connected each external platform.

**Elastic** was set up with two indices. `city_knowledge` holds municipal regulations, infrastructure maintenance manuals, and departmental SOPs. `city_policies` holds operational rules like bus rerouting tables and emergency shelter locations. Both indices use `dense_vector` fields (768 dimensions) for kNN semantic search alongside `text` fields with the English analyzer for BM25. The `elastic_client.py` seeds these indices on first run from the hardcoded NYC SOP library in the codebase. The Elastic MCP server at `{ELASTIC_URL}/_mcp` is accessed by the Impact Forecaster via `StreamableHTTPConnectionParams`.

**Dynatrace** was configured by registering city infrastructure as named services: `transit-data-feed`, `traffic-control-system`, `utility-water-grid`, `weather-ingestion-service`, and `nyc-311-feed`. The ingestion layer instruments every outbound API call so they appear as traced transactions in Dynatrace Grail. The `dynatrace_client.py` wraps the Dynatrace REST API for direct health checks. The Dynatrace MCP server is accessed by the Anomaly Detector to run DQL queries and read Davis AI problem events.

**Arize Phoenix** was initialized in `arize_client.py` using `phoenix.otel.register` with project name `citypilot`. We wrote two context manager wrappers: `trace_agent_run` wraps each agent execution and records `agent.name`, `mission`, `latency_ms`, and `status` as span attributes. `trace_mcp_call` wraps each MCP tool invocation and records the tool name, server, arguments, and outcome. If prediction confidence falls below 75%, the dashboard renders a warning banner. The full trace tree with five nested spans is visible in the Phoenix UI during the demo.

**Fivetran** was connected via the Fivetran REST API in `fivetran_client.py`. Three connectors are managed: one for OpenWeatherMap, one for NYC 311, one for Ticketmaster. The orchestrator agent holds the Fivetran MCP toolset and calls `update_sync_frequency` to change the weather connector from 30-minute intervals to 5-minute intervals when it detects a large event tomorrow. It calls `trigger_sync` on the 311 and events connectors to pull fresh data immediately. The agent is actively controlling its own data pipeline in response to what it discovers.

### Step 5: Build the City Situation Room

The frontend is a Next.js 14 App Router application built with Tailwind CSS, Mapbox GL JS, and React Query. It connects to the backend over both REST and WebSocket.

The map panel uses Mapbox GL JS with two live data layers. The heatmap layer renders 311 complaint density with a color ramp from transparent blue at low density through orange to red at high density, driven by the `/api/complaints` endpoint which queries MongoDB in real time. The circle layer renders hotspot zip codes as colored markers scaled by complaint count, fetched from `/api/hotspots` which runs a MongoDB aggregation.

The right sidebar has three sections. The Top Risks panel shows severity-badged risks from the agent briefing. The Agent Reasoning Trace panel streams every agent event over WebSocket as it happens: agent name, MCP tool called, what was found. The Action Plan panel shows the generated interventions and two buttons: APPROVE and Reject. Clicking APPROVE calls `POST /api/plans/approve` which writes the approval to MongoDB and broadcasts the status change to all connected clients over WebSocket.

The WebSocket connection uses a custom `useSocket` hook with automatic reconnection on disconnect.

---

## Integrations at a Glance

### MongoDB

The city's memory. Every signal, every plan, every approval flows through MongoDB Atlas.

Collections used: `complaints` (NYC 311 with 2dsphere and vector search indexes), `sensor_readings` (time-series), `action_plans`, `resources`, `events`, `weather`, `weather_forecast`.

MCP tools called by agents: `find`, `aggregate` (including `$vectorSearch` pipelines), `count`, `insert-many`, `update-one`, `collection-schema`, `atlas-streams-build`, `atlas-get-performance-advisor`.

### Elasticsearch

The city's knowledge base. Two indices hold every SOP and policy the city has ever written.

Index `city_knowledge`: municipal regulations, emergency SOPs, maintenance procedures. Index `city_policies`: bus rerouting rules, shelter locations, deployment protocols.

Both use hybrid BM25 and dense vector search. The Impact Forecaster queries Elastic to retrieve the specific SOP that matches the current incident before generating an action plan.

### Dynatrace

The city's infrastructure monitor. Five city systems are registered as Dynatrace services.

The Anomaly Detector calls `get_active_problems` and runs DQL queries against Dynatrace Grail to measure API latency and detect degraded services. If any service is degraded, the agent writes a data staleness caveat into the briefing that propagates to the mayor's action plan.

### Arize Phoenix

The AI quality layer. Every agent span and every MCP tool call is traced with OpenTelemetry.

The dashboard shows live prediction confidence. Below 75% confidence, a warning banner appears recommending human review. The full five-agent trace tree is visible in the Phoenix UI with per-agent latencies and tool call details.

### Fivetran

The data pipeline controller. Three connectors feed city data into MongoDB on scheduled intervals.

The orchestrator agent calls Fivetran MCP tools to boost sync frequency and trigger immediate syncs when it detects a high-attendance event. The agent controls its own data ingestion based on what it discovers about the mission context.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Agent Framework | Google ADK 2.0 (Python), Gemini 2.0 Flash |
| Orchestration | ADK collaborative multi-agent, sub_agents with single_turn mode |
| MCP Clients | McpToolset with StdioConnectionParams and StreamableHTTPConnectionParams |
| Backend API | FastAPI, WebSocket streaming, async Motor for MongoDB |
| City Memory | MongoDB Atlas (time-series, vector search, change streams) |
| Knowledge Search | Elasticsearch 8.x, hybrid BM25 and kNN |
| Observability | Dynatrace SaaS, DQL, Davis AI problems API |
| AI Quality | Arize Phoenix, OpenTelemetry, prediction confidence scoring |
| Data Pipelines | Fivetran Connector SDK, agent-controlled sync |
| Map | Mapbox GL JS, heatmap and circle layers |
| Frontend | Next.js 14 App Router, Tailwind CSS, React Query, WebSocket |
| Real Data | NYC 311 Open Data (24M+ records), OpenWeatherMap, Ticketmaster |
| Deployment | Google Cloud Run (backend), Firebase Hosting (frontend), MongoDB Atlas |

---

## Repository Structure

```
citypilot/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py         Root ADK Agent with sub_agents and Fivetran MCP
│   │   ├── signal_collector.py     MongoDB MCP: find, aggregate, count
│   │   ├── anomaly_detector.py     MongoDB stats + Dynatrace MCP: DQL, problems
│   │   ├── impact_forecaster.py    Elastic MCP hybrid search + MongoDB vectorSearch
│   │   ├── operations_planner.py   MongoDB MCP: insert-many, find resources
│   │   └── executive_briefer.py    MongoDB MCP: find, update-one, situation report
│   ├── mcp_clients/
│   │   ├── mongodb_client.py       Async Motor client, vector index setup, map data
│   │   ├── elastic_client.py       Index setup, SOP seeding, hybrid search
│   │   ├── dynatrace_client.py     DQL execution, problem polling, service health
│   │   ├── arize_client.py         Phoenix registration, OTel span wrappers
│   │   └── fivetran_client.py      Connector management, sync frequency control
│   ├── ingestion/
│   │   ├── weather_connector.py    OpenWeatherMap current and forecast
│   │   ├── complaints_connector.py NYC 311 Socrata API with bulk upsert
│   │   └── events_connector.py     Ticketmaster Discovery API
│   ├── api/
│   │   └── server.py               FastAPI, WebSocket broadcast, all REST endpoints
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── app/
│       │   ├── page.tsx            City Situation Room layout
│       │   └── map-embed/page.tsx  Mapbox GL map with live data layers
│       ├── components/
│       │   ├── dashboard/          Header (mission input), RiskPanel, ActionPlan
│       │   ├── map/                CityMap with heatmap and hotspot layers
│       │   └── agents/             AgentTrace live streaming panel
│       └── lib/
│           ├── api.ts              All REST API calls
│           └── useSocket.ts        WebSocket hook with auto-reconnect
├── data/
│   └── seed_nyc_311.py             Fetches real NYC 311, seeds MongoDB, creates indexes
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Setup and Running

### Prerequisites

- Python 3.12 or higher
- Node.js 22 or higher
- A MongoDB Atlas account (free M0 tier works)
- A Google AI Studio API key from aistudio.google.com

### Step 1: Configure environment

```bash
git clone https://github.com/Tasfia-17/citypilot
cd citypilot
cp .env.example backend/.env
```

Open `backend/.env` and fill in at minimum:

```
GOOGLE_API_KEY=your_key_from_aistudio.google.com
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/
```

All other integrations (Elastic, Dynatrace, Arize, Fivetran) are optional. The system falls back to mock data for any missing API key so the full demo runs regardless.

### Step 2: Seed the database with real NYC data

```bash
pip install -r backend/requirements.txt
python data/seed_nyc_311.py
```

This fetches 30 days of real NYC 311 complaints from the Socrata API, normalizes and bulk-upserts them into MongoDB, creates the vector search index, and seeds the Elasticsearch knowledge base with city SOPs.

For deeper history:

```bash
python data/seed_nyc_311.py --days 90 --limit 50000
```

### Step 3: Start the backend

```bash
cd backend
uvicorn api.server:app --reload --port 8000
```

### Step 4: Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

### Step 5: Run with Docker Compose

```bash
docker compose up --build
```

This starts the backend, frontend, local MongoDB, and local Elasticsearch together.

---

## Demo Walkthrough

Open the dashboard. The map shows the Upper West Side district with a live 311 complaint heatmap rendered from real data. Red zones show high complaint density. Circle markers show hotspot zip codes.

Type this mission into the input bar:

```
Prepare District 7 for tomorrow's football match at 7PM
```

Watch the Agent Reasoning Trace panel fill in real time as each agent runs:

1. Signal Collector calls MongoDB `find` and `aggregate`. Returns 340 complaints in the last 48 hours near the stadium area with breakdown by type and zip code.
2. Anomaly Detector detects a 3-sigma spike near Stadium Road. Calls Dynatrace `get_active_problems`. Transit-data-feed shows elevated latency. Flags it.
3. Impact Forecaster calls Elastic MCP. Returns the Stadium Event Traffic Management SOP. Calls MongoDB `$vectorSearch`. Finds the October 2023 match-day incident as the closest historical precedent at 91% similarity.
4. Operations Planner queries the resources collection. Generates three specific actions: reroute Bus M15 via 2nd Avenue, deploy 3 sanitation crews to Stadium Road by 14:00, alert businesses on the surrounding blocks.
5. Executive Briefer writes the situation report: 31% congestion reduction predicted, 41% complaint reduction, 8,500 people served, 87% confidence. Transit data caveat included.

The action plan appears at the bottom of the right panel. Click APPROVE. MongoDB stores the approval via `update-one`. The Dynatrace dashboard shows the problem event. The Arize Phoenix dashboard shows five nested agent spans with per-agent latencies and no hallucination flags.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | /api/mission | Run a city mission, streams progress via WebSocket |
| GET | /api/map | All map layer data: complaints, hotspots, risk zones |
| GET | /api/complaints | Recent 311 complaints with lat/lng for heatmap |
| GET | /api/hotspots | Aggregated complaint hotspots by zip code |
| GET | /api/events | Upcoming NYC events in the next 24 hours |
| GET | /api/health | System health: infrastructure, pipelines, agent health |
| GET | /api/plans/active | Current pending action plan |
| POST | /api/plans/approve | Mayor approves or rejects the action plan |
| POST | /api/sync | Trigger manual data ingestion sync |
| WS | /ws | WebSocket for real-time agent trace and map updates |

---

## License

MIT License. See LICENSE file.
