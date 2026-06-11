export type RiskLevel = "HIGH" | "MEDIUM" | "LOW" | "NORMAL";
export type AgentStatus = "idle" | "running" | "complete" | "error";

export interface Risk {
  id: number;
  name: string;
  severity: RiskLevel;
  description: string;
  zone: string;
}

export interface Action {
  id: string;
  department: string;
  action: string;
  timing: string;
  impact: string;
  priority?: "HIGH" | "MEDIUM" | "LOW";
  coordinates?: { lat: number; lng: number } | null;
}

export interface PredictedImpact {
  congestion_reduction_pct: number;
  complaint_reduction_pct: number;
  population_served: number;
  confidence_pct: number;
}

export interface AgentTrace {
  agent: string;
  status: "running" | "complete" | "error";
  latency_ms?: number;
  message?: string;
  tool_call?: string;
  timestamp?: string;
}

export interface Briefing {
  briefing_id: string;
  mission: string;
  situation_summary: string;
  top_risks: Risk[];
  action_plan: Action[];
  predicted_impact: PredictedImpact;
  agent_trace: AgentTrace[];
  data_freshness: "FRESH" | "STALE" | "UNKNOWN";
  requires_approval: boolean;
  status: "pending_approval" | "approved" | "rejected";
  plan_id?: string;
}

export interface Complaint {
  lat: number;
  lng: number;
  type: string;
  zip?: string;
  borough?: string;
}

export interface Hotspot {
  _id: string;
  count: number;
  avg_lat: number;
  avg_lng: number;
  complaint_types: string[];
}

export interface CityEvent {
  event_id: string;
  name: string;
  start_date: string;
  venue_name: string;
  capacity?: number;
  latitude?: number;
  longitude?: number;
}

export interface MapData {
  complaints: Complaint[];
  hotspots: Hotspot[];
  risk_zones: { zone: string; action: string; lat: number; lng: number }[];
}

export interface WsMessage {
  type: string;
  agent?: string;
  message?: string;
  tool_call?: string;
  briefing?: Briefing;
  agent_trace?: AgentTrace[];
  error?: string;
  timestamp?: string;
}
