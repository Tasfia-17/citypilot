"use client";
import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { useCitySocket } from "@/lib/useSocket";
import Header from "@/components/dashboard/Header";
import RiskPanel from "@/components/dashboard/RiskPanel";
import AgentTrace from "@/components/agents/AgentTrace";
import ActionPlan from "@/components/dashboard/ActionPlan";
import { fetchMapData, fetchEvents, fetchHealth } from "@/lib/api";
import type { Risk } from "@/types";

// CityMap must be client-only (mapbox requires window)
const CityMap = dynamic(() => import("@/components/map/CityMap"), { ssr: false });

export default function SituationRoom() {
  const { connected, agentTrace, briefing, missionStatus } = useCitySocket();
  const [activeMission, setActiveMission] = useState<string>("");

  const { data: mapData, refetch: refetchMap } = useQuery({
    queryKey: ["mapData"],
    queryFn: fetchMapData,
    refetchInterval: 60_000, // refresh every minute
  });

  const { data: events } = useQuery({
    queryKey: ["events"],
    queryFn: fetchEvents,
    refetchInterval: 300_000,
  });

  const { data: health } = useQuery({
    queryKey: ["health"],
    queryFn: fetchHealth,
    refetchInterval: 30_000,
  });

  // Refresh map when mission completes
  useEffect(() => {
    if (missionStatus === "complete") {
      refetchMap();
    }
  }, [missionStatus, refetchMap]);

  // Extract top risks from briefing or show defaults
  const topRisks: Risk[] = briefing?.top_risks || (
    events?.length > 0 ? [
      {
        id: 1,
        name: events[0]?.name || "Upcoming Event",
        severity: "HIGH",
        description: `${events[0]?.capacity?.toLocaleString() || "Large"} attendees expected at ${events[0]?.venue_name || "venue"}`,
        zone: events[0]?.venue_city || "NYC",
      }
    ] : []
  );

  const infraStatus = health?.infrastructure || {};
  const anyDegraded = Object.values(infraStatus).some(v => v === "DEGRADED");

  return (
    <div className="h-screen flex flex-col bg-city-dark overflow-hidden">
      <Header
        connected={connected}
        missionStatus={missionStatus}
        onMissionStart={setActiveMission}
      />

      {/* Infrastructure warning banner */}
      {anyDegraded && (
        <div className="px-4 py-1.5 bg-amber-950/60 border-b border-amber-800/50 flex items-center gap-2">
          <span className="text-amber-400 text-xs">⚠</span>
          <span className="text-xs text-amber-300">
            Infrastructure alert: {Object.entries(infraStatus)
              .filter(([, v]) => v === "DEGRADED")
              .map(([k]) => k.replace(/-/g, " "))
              .join(", ")} — data may be stale
          </span>
        </div>
      )}

      {/* Main grid */}
      <div className="flex-1 grid grid-cols-[1fr_340px] overflow-hidden">

        {/* Left: Map */}
        <div className="relative border-r border-city-border">
          <CityMap data={mapData ?? null} />

          {/* Mission status overlay */}
          {activeMission && missionStatus === "running" && (
            <div className="absolute top-3 left-3 right-3 pointer-events-none">
              <div className="bg-city-dark/90 border border-blue-800/50 rounded-lg px-4 py-2.5 backdrop-blur-sm">
                <div className="flex items-center gap-2">
                  <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />
                  <span className="text-xs text-blue-300 font-mono">MISSION ACTIVE</span>
                </div>
                <p className="text-sm text-white mt-1 font-medium">{activeMission}</p>
              </div>
            </div>
          )}

          {/* Map legend */}
          <div className="absolute bottom-3 left-3 bg-city-dark/80 border border-city-border rounded-lg p-2.5 backdrop-blur-sm text-xs text-gray-400 space-y-1">
            <div className="flex items-center gap-2"><span className="w-3 h-1 bg-red-500 rounded" />High complaint density</div>
            <div className="flex items-center gap-2"><span className="w-3 h-1 bg-amber-500 rounded" />Medium density</div>
            <div className="flex items-center gap-2"><span className="w-2 h-2 rounded-full bg-blue-500" />Risk zone</div>
          </div>

          {/* Complaint count badge */}
          {mapData?.complaints?.length > 0 && (
            <div className="absolute top-3 right-3 bg-city-dark/80 border border-city-border rounded-lg px-3 py-1.5 backdrop-blur-sm">
              <p className="text-xs font-mono text-gray-400">
                <span className="text-white font-semibold">{mapData.complaints.length.toLocaleString()}</span> complaints (48h)
              </p>
            </div>
          )}
        </div>

        {/* Right sidebar */}
        <div className="flex flex-col overflow-hidden bg-city-panel">

          {/* Top risks */}
          <section className="p-3 border-b border-city-border">
            <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-2">
              Top Risks
            </h2>
            <RiskPanel risks={topRisks} loading={missionStatus === "running" && !briefing} />
          </section>

          {/* Agent reasoning trace */}
          <section className="p-3 border-b border-city-border" style={{ height: "220px", minHeight: "220px" }}>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
                Agent Reasoning
              </h2>
              {missionStatus === "running" && (
                <span className="text-xs text-blue-400 animate-pulse font-mono">● LIVE</span>
              )}
            </div>
            <div className="h-[calc(100%-24px)]">
              <AgentTrace trace={agentTrace} status={missionStatus} />
            </div>
          </section>

          {/* Action plan */}
          <section className="flex-1 overflow-y-auto p-3">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest">
                Action Plan
              </h2>
              {briefing && (
                <span className={`text-xs px-2 py-0.5 rounded font-mono border ${
                  briefing.status === "approved"
                    ? "text-green-400 border-green-800 bg-green-950/30"
                    : briefing.status === "pending_approval"
                    ? "text-amber-400 border-amber-800 bg-amber-950/30"
                    : "text-gray-500 border-gray-700"
                }`}>
                  {briefing.status.replace(/_/g, " ").toUpperCase()}
                </span>
              )}
            </div>
            <ActionPlan briefing={briefing} />
          </section>

          {/* Footer: Phoenix confidence */}
          {health?.agent_health?.prediction_confidence != null && (
            <div className="px-3 py-2 border-t border-city-border flex items-center justify-between">
              <span className="text-xs text-gray-600">Arize Phoenix</span>
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${
                  health.agent_health.tracing_enabled ? "bg-green-500" : "bg-gray-600"
                }`} />
                <span className="text-xs text-gray-500">
                  {health.agent_health.tracing_enabled ? "Tracing active" : "Tracing off"}
                </span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
