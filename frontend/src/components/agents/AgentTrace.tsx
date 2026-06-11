"use client";
import { useEffect, useRef } from "react";
import type { AgentTrace } from "@/types";

const AGENT_COLORS: Record<string, string> = {
  signal_collector: "text-blue-400",
  anomaly_detector: "text-orange-400",
  impact_forecaster: "text-purple-400",
  operations_planner: "text-cyan-400",
  executive_briefer: "text-green-400",
  citypilot_orchestrator: "text-yellow-400",
};

const AGENT_ICONS: Record<string, string> = {
  signal_collector: "📡",
  anomaly_detector: "🔍",
  impact_forecaster: "🔮",
  operations_planner: "📋",
  executive_briefer: "📊",
  citypilot_orchestrator: "🏛️",
};

interface Props {
  trace: AgentTrace[];
  status: "idle" | "running" | "complete" | "error";
}

export default function AgentTracePanel({ trace, status }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [trace]);

  if (status === "idle") {
    return (
      <div className="h-full flex items-center justify-center text-gray-600">
        <div className="text-center">
          <p className="text-xs font-mono">AWAITING MISSION</p>
          <p className="text-xs mt-1 text-gray-700">Type a mission above to start</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto space-y-1 pr-1">
      {trace.map((entry, i) => {
        const color = AGENT_COLORS[entry.agent] || "text-gray-400";
        const icon = AGENT_ICONS[entry.agent] || "⚡";
        return (
          <div key={i} className="trace-entry flex gap-2 text-xs font-mono">
            <span className="text-gray-600 shrink-0 mt-0.5">
              {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString("en-US", { 
                hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" 
              }) : "--:--:--"}
            </span>
            <span className="shrink-0">{icon}</span>
            <div className="min-w-0">
              <span className={`font-semibold ${color}`}>
                [{entry.agent.replace(/_/g, " ").toUpperCase()}]
              </span>
              {entry.tool_call && (
                <span className="text-yellow-600 ml-1">→ {entry.tool_call}()</span>
              )}
              {entry.message && (
                <p className="text-gray-400 mt-0.5 leading-relaxed break-words">
                  {entry.message.slice(0, 200)}
                  {entry.message.length > 200 ? "..." : ""}
                </p>
              )}
            </div>
            <span className="ml-auto shrink-0">
              {entry.status === "running" ? (
                <span className="text-yellow-500 animate-pulse">●</span>
              ) : entry.status === "complete" ? (
                <span className="text-green-500">✓</span>
              ) : (
                <span className="text-red-500">✗</span>
              )}
            </span>
          </div>
        );
      })}

      {status === "running" && (
        <div className="flex gap-2 text-xs font-mono text-gray-500">
          <span className="w-16 shrink-0">
            {new Date().toLocaleTimeString("en-US", { hour12: false })}
          </span>
          <span className="cursor-blink">Processing</span>
        </div>
      )}

      {status === "complete" && (
        <div className="text-xs font-mono text-green-500 mt-2 pt-2 border-t border-city-border">
          ✓ Mission complete — review the action plan below
        </div>
      )}

      {status === "error" && (
        <div className="text-xs font-mono text-red-500 mt-2 pt-2 border-t border-city-border">
          ✗ Mission failed — check API configuration
        </div>
      )}
    </div>
  );
}
