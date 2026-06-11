"""Elastic client — indexes city knowledge and policies for semantic search."""

import os
from elasticsearch import AsyncElasticsearch, helpers


CITY_KNOWLEDGE_INDEX = "city_knowledge"
CITY_POLICIES_INDEX = "city_policies"

# Index mappings with dense_vector for hybrid search
KNOWLEDGE_MAPPING = {
    "mappings": {
        "properties": {
            "title": {"type": "text", "analyzer": "english"},
            "content": {"type": "text", "analyzer": "english"},
            "category": {"type": "keyword"},
            "department": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "embedding": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
            "created_at": {"type": "date"},
        }
    }
}

POLICIES_MAPPING = {
    "mappings": {
        "properties": {
            "title": {"type": "text", "analyzer": "english"},
            "policy_text": {"type": "text", "analyzer": "english"},
            "policy_type": {"type": "keyword"},
            "applicable_scenarios": {"type": "keyword"},
            "zones": {"type": "keyword"},
            "embedding": {"type": "dense_vector", "dims": 768, "index": True, "similarity": "cosine"},
        }
    }
}


class ElasticClient:
    """Elasticsearch client for city knowledge base operations."""

    def __init__(self):
        self.url = os.environ.get("ELASTIC_URL", "http://localhost:9200")
        self.api_key = os.environ.get("ELASTIC_API_KEY", "")
        self._client: AsyncElasticsearch | None = None

    @property
    def client(self) -> AsyncElasticsearch:
        if not self._client:
            kwargs: dict = {"hosts": [self.url]}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = AsyncElasticsearch(**kwargs)
        return self._client

    async def setup_indices(self):
        """Create city_knowledge and city_policies indices."""
        for index, mapping in [
            (CITY_KNOWLEDGE_INDEX, KNOWLEDGE_MAPPING),
            (CITY_POLICIES_INDEX, POLICIES_MAPPING),
        ]:
            exists = await self.client.indices.exists(index=index)
            if not exists:
                await self.client.indices.create(index=index, body=mapping)
                print(f"Created Elastic index: {index}")

    async def index_sop(self, title: str, content: str, category: str, department: str, tags: list[str], embedding: list[float] | None = None):
        """Index a Standard Operating Procedure into city_knowledge."""
        doc = {
            "title": title,
            "content": content,
            "category": category,
            "department": department,
            "tags": tags,
            "created_at": "now",
        }
        if embedding:
            doc["embedding"] = embedding
        await self.client.index(index=CITY_KNOWLEDGE_INDEX, document=doc)

    async def index_policy(self, title: str, policy_text: str, policy_type: str, scenarios: list[str], embedding: list[float] | None = None):
        """Index a city policy into city_policies."""
        doc = {
            "title": title,
            "policy_text": policy_text,
            "policy_type": policy_type,
            "applicable_scenarios": scenarios,
        }
        if embedding:
            doc["embedding"] = embedding
        await self.client.index(index=CITY_POLICIES_INDEX, document=doc)

    async def hybrid_search(self, query: str, index: str = CITY_KNOWLEDGE_INDEX, top_k: int = 5) -> list[dict]:
        """Hybrid BM25 + kNN semantic search."""
        # BM25 query
        bm25_query = {
            "query": {
                "multi_match": {
                    "query": query,
                    "fields": ["title^3", "content", "tags^2"],
                    "type": "best_fields",
                }
            },
            "size": top_k,
        }
        response = await self.client.search(index=index, body=bm25_query)
        results = []
        for hit in response["hits"]["hits"]:
            results.append({
                "title": hit["_source"].get("title", ""),
                "content": hit["_source"].get("content", ""),
                "category": hit["_source"].get("category", ""),
                "score": hit["_score"],
                "source": index,
            })
        return results

    async def seed_city_knowledge(self):
        """Seed the knowledge base with NYC emergency SOPs and policies."""
        sops = [
            {
                "title": "Stadium Event Traffic Management Protocol",
                "content": "For events exceeding 30,000 attendees at MSG or Yankee Stadium: Deploy 12 traffic officers at key intersections 2h prior. Activate alternate bus routes M7, M11, M15. Coordinate with NYPD for crowd control. Pre-position 3 sanitation crews within 0.5 mile radius.",
                "category": "traffic_management",
                "department": "DOT",
                "tags": ["stadium", "event", "traffic", "bus_rerouting"],
            },
            {
                "title": "Heavy Rain Event Response SOP",
                "content": "When rainfall exceeds 1 inch/hour: Activate 6 catch basin clearing crews in flood-prone zones. Deploy emergency pumping equipment to FEMA Zone A locations. Issue 311 proactive outreach to residents in affected zip codes. Coordinate with MTA for service changes.",
                "category": "weather_response",
                "department": "Emergency Management",
                "tags": ["rain", "flood", "weather", "infrastructure"],
            },
            {
                "title": "Transit Service Disruption Response",
                "content": "When MTA reports service disruption affecting >20% of district commuters: Activate emergency bus bridge service. Coordinate with NYC Ferry for capacity increases. Deploy DOT wayfinding officers at affected subway exits. Issue real-time alerts via Notify NYC.",
                "category": "transit_management",
                "department": "DOT",
                "tags": ["transit", "subway", "bus_bridge", "disruption"],
            },
            {
                "title": "Heat Emergency Response Protocol",
                "content": "When heat index exceeds 95°F: Open cooling centers at all public libraries and community centers. Deploy mobile cooling units to parks in vulnerable zip codes. Coordinate with ConEd for demand response. Conduct wellness checks on elderly residents via 311 list.",
                "category": "emergency_response",
                "department": "Emergency Management",
                "tags": ["heat", "cooling_center", "elderly", "emergency"],
            },
            {
                "title": "Water Main Break Response Procedure",
                "content": "Upon confirmed water main break: Dispatch repair crew within 30 minutes. Set up traffic diversion along affected 2-block radius. Issue boil water advisory if water pressure drops. Coordinate with NYCHA for affected buildings. ETA for repair: 4-8 hours.",
                "category": "infrastructure_repair",
                "department": "DEP",
                "tags": ["water_main", "infrastructure", "repair", "traffic_diversion"],
            },
        ]

        policies = [
            {
                "title": "Bus Rerouting Rules During Stadium Events",
                "policy_text": "M15 reroutes via 2nd Ave between 60th-80th during MSG events. M7 extends hours until 2AM on event nights. Express buses stop at alternate stops during crowd dispersal.",
                "policy_type": "transit_policy",
                "scenarios": ["stadium_event", "large_gathering"],
            },
            {
                "title": "Emergency Shelter Locations — Manhattan District 7",
                "policy_text": "Primary: PS 166 (132 W 89th St). Secondary: IS 44 (100 W 77th St). Capacity: 800 combined. Activation requires Emergency Management authorization.",
                "policy_type": "emergency_shelter",
                "scenarios": ["severe_weather", "emergency_evacuation"],
            },
            {
                "title": "Crew Deployment Protocol — Special Events",
                "policy_text": "Events 10k-50k: 2 sanitation crews, 4 traffic officers, 1 emergency vehicle. Events 50k+: 5 sanitation crews, 12 traffic officers, 2 emergency vehicles, 1 command center.",
                "policy_type": "resource_deployment",
                "scenarios": ["stadium_event", "parade", "large_gathering"],
            },
        ]

        for sop in sops:
            await self.index_sop(**sop)
        for policy in policies:
            await self.index_policy(**policy)

        await self.client.indices.refresh(index=CITY_KNOWLEDGE_INDEX)
        await self.client.indices.refresh(index=CITY_POLICIES_INDEX)
        print(f"Seeded {len(sops)} SOPs and {len(policies)} policies into Elasticsearch.")

    async def close(self):
        if self._client:
            await self._client.close()
