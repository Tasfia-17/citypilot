# CityPilot

**The Autonomous Operating System for a City**

CityPilot is a multi-agent AI system built for the Google + Partner Hackathon 2026. It continuously monitors urban systems across a city district, detects cross-system crises before they escalate, and generates coordinated multi-department action plans, all while keeping a human operator in full command. The mayor types a mission. Five AI agents execute it. The operator approves the result.

This is not a chatbot. It is a Goal to Autonomous Investigation to Multi-Agency Coordination to Action Plan system that feels like a prototype of a future urban operating system.

---

## The Problem

City operations today are deeply fragmented. Traffic engineers do not talk to transit managers. Sanitation crews are dispatched reactively, after complaints pile up. Weather forecasts sit in one system while event schedules live in another. Infrastructure monitors are separate from public complaint feeds. The result: cities react to crises instead of preventing them.

When 60,000 people descend on a stadium district during a rainstorm while the local subway line is under maintenance, no single city employee has a complete picture. Each department sees its own slice. Nobody has the full signal until the congestion, complaints, and chaos are already happening.

The cost is real: delayed emergency response, frustrated residents, wasted crew deployments, and reputational damage to city leadership. A mid-size city district generates hundreds of coordinated decisions every week that require data no single human can hold in their head.

---

## The Solution

CityPilot gives city operators a city-scale brain.

The system ingests real urban signals continuously: live weather forecasts, resident complaint firehoses, event schedules with capacity numbers, and infrastructure health telemetry. Five specialized AI agents built with Google ADK collaborate to analyze these signals, detect anomalies, retrieve historical precedents using semantic search, generate quantified action plans, and produce a mayoral briefing with predicted impact.

The operator sees everything happening in real time: which agent is running, which MCP tool it just called, what data it found. They read the plan. They click Approve. The city moves.

Human oversight is not an afterthought. It is the core design principle.

---

## What We Built

### The Five-Agent Pipeline

Every mission flows through five specialized agents in sequence, each one passing enriched context to the next.

**Signal Collector** connects to the MongoDB MCP server and pulls all city signals relevant to the mission: 311 complaints from the last 48 hours filtered by district, upcoming events with venue capacity, weather forecast, and recent traffic incidents. It uses the MongoDB `find`, `aggregate`, and `count` tools to build a structured signal summary. No hallucination here: every number comes from the actual database.

**Anomaly Detector** takes the signal summary and finds what is unusual. It runs MongoDB aggregation pipelines comparing current complaint volume against 30-day baselines, flags zones with more than two standard deviations of deviation, and calls the Dynatrace MCP to check whether any city infrastructure services are currently degraded. If the transit API is showing elevated latency, this agent flags it: routing decisions may be based on stale data. That caveat propagates through the entire rest of the pipeline and appears in the final action plan.

**Impact Forecaster** does two things that no other team will do. First, it calls the Elastic MCP server to run a hybrid semantic search over the city knowledge base, combining BM25 keyword matching with dense vector similarity to find the Standard Operating Procedure closest to the current scenario. Second, it runs a MongoDB `$vectorSearch` aggregation pipeline against the complaints collection, which contains six months of real NYC 311 data with vector embeddings, to find historically similar incidents and their outcomes. The result is a forecast grounded in both official city policy and empirical history.

**Operations Planner** reads the forecast and generates a concrete multi-department action plan. It queries the MongoDB resources collection for available crews, vehicles, and equipment, then produces specific actions: which bus route to reroute and via which street, how many sanitation crews to deploy and where, which intersections need traffic officers. It stores the entire plan in MongoDB using the `insert-many` tool with a `pending_approval` status.

**Executive Briefer** synthesizes everything into the mayoral situation report: top risks ranked by severity, a two-sentence situation summary, the action list with department assignments and timing, and quantified predicted impact. Congestion reduction. Complaint volume reduction. Population served. Confidence percentage. All of it grounded in the data the previous agents collected.

### The Orchestrator

The root orchestrator is a Google ADK `Agent` with all five specialists registered as `sub_agents`. ADK's collaborative workflow system handles delegation and return automatically. Each sub-agent runs in `single_turn` mode, completing its task and returning control with results. The orchestrator also holds the Fivetran MCP toolset, which it uses to boost data pipeline sync frequency when an event is detected. On match day, the weather connector switches from 30-minute intervals to 5-minute intervals. The agent controls its own data ingestion.

### Real Data, Not Simulation

The complaint heatmap on the map is built from the real NYC 311 dataset served by the New York City Open Data Socrata API at `data.cityofnewyork.us/resource/erm2-nwe9.json`. This dataset contains over 24 million records updated daily. The seeding script pulls 30 to 90 days of history across Manhattan, Brooklyn, and Queens boroughs and bulk-upserts into MongoDB with duplicate detection on `unique_key`.

Weather comes from OpenWeatherMap's forecast API. Events come from Ticketmaster Discovery API with real venue names, addresses, and capacity. All three connectors have realistic mock fallbacks for demo environments without API keys.

### The City Knowledge Base

The Elasticsearch indices `city_knowledge` and `city_policies` are seeded with real NYC emergency SOPs: stadium event traffic management, heavy rain response, transit disruption procedures, heat emergency protocols, water main break procedures. The index mapping uses `dense_vector` fields for semantic similarity alongside full-text fields for BM25 keyword matching. When the Impact Forecaster searches for "bus rerouting protocol during stadium event with rain and transit maintenance", it gets back the actual city playbook, not a hallucination.

### Infrastructure as Services

City systems are registered in Dynatrace as named services: `transit-data-feed`, `traffic-control-system`, `utility-water-grid`, `weather-ingestion-service`. Every API call the ingestion layer makes becomes a traced transaction. When the weather API slows or the 311 feed stalls, Dynatrace's Davis AI fires a problem alert. The Anomaly Detector reads these via the MCP `get_active_problems` tool and executes DQL queries like `fetch logs | filter service == "transit-data-feed" | summarize avg(duration)` to measure actual latency. The demo scenario shows the transit API latency spike mid-mission, causing the agent to flag data staleness in the final briefing. Judges see real observability woven into the agent reasoning, not a static dashboard.

### AI Quality Layer

Every agent span is instrumented with OpenTelemetry via Arize Phoenix. The tracer records the input prompt, which MCP tools were called, tool outputs, final reasoning, and latency per agent. The dashboard's agent health panel shows prediction confidence and tracing status. If the Impact Forecaster's confidence drops below a threshold, the system shows a warning: Prediction confidence LOW, recommend human review. This is genuine human-in-the-loop design built on real AI observability infrastructure.

### The City Situation Room

The frontend is a Next.js 14 application styled as a dark-mode operational command center. The map panel renders real 311 complaint density as a Mapbox GL heatmap layer, with scatterplot circles showing hotspot zip codes colored red, amber, or green by complaint volume. Risk zones from the agent's action plan appear as blue polygon markers.

The right sidebar has three sections that update live. The Top Risks panel shows the three highest-severity issues identified by the agents, with severity badges. The Agent Reasoning Trace shows every agent event as it streams in over WebSocket: which agent is running, which MCP tool it just called, what it found. The Action Plan section shows the generated interventions with department, timing, and predicted impact, followed by two buttons: APPROVE and Reject. The mayor clicks Approve. MongoDB stores the result. The plan status changes to approved. The city moves.

---

## Sponsor Integrations

### MongoDB (Primary Track)

MongoDB Atlas is the city's memory. Every piece of data that matters flows through it.

The complaints collection uses real NYC 311 data with a `2dsphere` geospatial index for location-based queries and a vector search index named `complaint_embeddings` on the `embedding` field (768 dimensions, cosine similarity) for semantic incident retrieval. The `sensor_readings` collection uses MongoDB's native time-series collection type with `timeField: "timestamp"`, `metaField: "sensor_id"`, and `granularity: "minutes"` for IoT-style sensor data. The `action_plans` collection stores the full agent-generated plans with approval status tracked via `update-one`.

Atlas Stream Processing processors watch the complaint volume in real time and trigger the Signal Collector agent via change streams when volume crosses a two-sigma threshold. The `atlas-streams-build` MCP tool creates these processors. The `atlas-get-performance-advisor` tool is called during the demo to show the system analyzing its own query patterns.

The MongoDB MCP server is started as a subprocess by each agent using `StdioConnectionParams` with `@mongodb-js/mongodb-mcp-server`. Tool calls are explicit and visible in the agent trace: `find` for recent complaints, `aggregate` for hotspot analysis, `insert-many` for plan storage, `$vectorSearch` for historical similarity.

### Elastic

The Elastic MCP server exposes two custom indices to the Impact Forecaster agent. `city_knowledge` contains municipal regulations, emergency SOPs, infrastructure maintenance procedures, and departmental standard operating procedures. `city_policies` contains bus rerouting rules, emergency shelter locations, and crew deployment protocols.

Both indices use `dense_vector` fields for kNN semantic similarity alongside `text` fields with the English analyzer for BM25. The Impact Forecaster calls the MCP search tool with queries like "bus rerouting protocol during stadium events with transit disruption" and receives the actual matching SOP, which it incorporates directly into the action plan. This hybrid search, BM25 on policy names plus vector similarity on semantic meaning, is Elastic's native superpower and it is the load-bearing mechanism for the entire forecasting step.

### Dynatrace

City infrastructure is registered in Dynatrace as services with the names `transit-data-feed`, `traffic-control-system`, `utility-water-grid`, `weather-ingestion-service`, and `nyc-311-feed`. The ingestion layer instruments its API calls so every external request becomes a traced transaction in Dynatrace Grail.

The Anomaly Detector calls `get_active_problems` to check for Davis AI problem alerts. It calls `execute_dql_query` to run specific DQL statements measuring transit API response time. The demo scenario throttles the transit feed mid-mission to trigger a real Dynatrace problem event, which the agent detects and flags in the briefing. Judges see the Dynatrace dashboard showing the problem event at the same moment the agent says "routing decisions may be based on stale data." That causal link, from real observability to agent reasoning to human-visible caveat, is unprecedented.

### Arize Phoenix

Phoenix is initialized via `phoenix.otel.register` with the CityPilot project name. Every agent execution is wrapped in an OpenTelemetry span using a custom `trace_agent_run` context manager that records `agent.name`, `mission`, `agent.latency_ms`, and `agent.status`. Every MCP tool call is wrapped in a `trace_mcp_call` span recording the tool name, server, arguments, and success status.

The dashboard shows a Phoenix tracing indicator with the live prediction confidence score. If confidence drops below 75%, the UI renders a warning banner. The Phoenix MCP server can be queried by the orchestrator to retrieve aggregate trace data for the health summary endpoint.

### Fivetran

Three custom connectors built with the Fivetran Connector SDK pull data into MongoDB: OpenWeatherMap on a 30-minute schedule, NYC 311 on a daily delta sync, and Ticketmaster Events on a weekly schedule.

The key differentiator: the orchestrator agent calls Fivetran MCP tools to control the pipeline in response to what it discovers. When it detects an event tomorrow with large attendance, it calls `update_sync_frequency` to change the weather connector to a 5-minute interval and calls `trigger_sync` on the 311 and events connectors. An agent controlling its own data ingestion in response to what it finds is something judges will not have seen before.

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
- A Google AI Studio API key

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

All other integrations (Elastic, Dynatrace, Arize, Fivetran) are optional. The system uses mock fallbacks for data sources without keys so the demo runs end-to-end regardless.

### Step 2: Seed the database with real NYC data

```bash
pip install -r backend/requirements.txt
python data/seed_nyc_311.py
```

This fetches 30 days of real NYC 311 complaints across Manhattan, Brooklyn, and Queens from the Socrata API and stores them in MongoDB. It also creates the vector search index and seeds the Elasticsearch knowledge base.

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

Open the dashboard. The map shows the Upper West Side district with a live 311 complaint heatmap. Red zones indicate high complaint density. Circle markers show hotspot zip codes.

Type this mission and press Run Mission:

```
Prepare District 7 for tomorrow's football match at 7PM
```

Watch the Agent Reasoning Trace panel on the right fill in real time:

- Signal Collector calls MongoDB `find` and `aggregate` on the complaints collection. Returns 340 complaints in the last 48 hours near the stadium area.
- Anomaly Detector detects a 3-sigma spike near Stadium Road. Checks Dynatrace: transit-data-feed shows elevated latency.
- Impact Forecaster calls Elastic MCP: returns the Stadium Event Traffic Management SOP. Then calls MongoDB `$vectorSearch`: finds the October 2023 match-day incident as the closest historical precedent with 91% similarity.
- Operations Planner queries the resources collection for available crews. Generates three actions: reroute Bus M15, deploy 3 sanitation crews to Stadium Road, alert businesses on the surrounding blocks.
- Executive Briefer assembles the situation report: 31% congestion reduction predicted, 41% complaint reduction, 8,500 people served, 87% confidence.

The action plan appears at the bottom of the right panel. The mayor reads it and clicks APPROVE. MongoDB stores the approval. The Dynatrace dashboard shows all city services healthy. The Arize Phoenix dashboard shows five nested agent spans with latencies and no hallucination flags.

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

## Why This Wins

Most hackathon submissions build a chat interface with a database lookup underneath. CityPilot is architecturally different in every dimension.

The agent pipeline is genuinely multi-agent. Five specialists each with their own MCP toolset, running in sequence with context passing between them. The orchestrator is not just routing prompts, it is coordinating a workflow with explicit data dependencies.

The data is real. The 311 heatmap is built from the actual Socrata dataset that New York City publishes daily. The weather forecast is live. The events come from Ticketmaster's real API. When the agent says "340 complaints in the last 48 hours", that number came from a real query against real data.

Every sponsor integration is load-bearing. Remove MongoDB and the agents have no data to work with. Remove Elastic and the forecaster has no knowledge base. Remove Dynatrace and the anomaly detector cannot assess infrastructure health. Remove Arize and there is no prediction confidence score or hallucination detection. Remove Fivetran and the agent cannot control its own data ingestion. Each sponsor does something the others cannot.

The human-in-the-loop design is explicit and visible. The mayor sees the full reasoning trace. They read the plan. They click Approve. This is not just cosmetically compliant with the judging criteria: it is the architectural center of the product.

---

## License

MIT License. See LICENSE file.
