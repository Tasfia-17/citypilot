"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import type { WsMessage, AgentTrace, Briefing } from "@/types";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";
const RECONNECT_DELAY = 3000;

export function useCitySocket() {
  const ws = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [agentTrace, setAgentTrace] = useState<AgentTrace[]>([]);
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [missionStatus, setMissionStatus] = useState<"idle" | "running" | "complete" | "error">("idle");
  const reconnectTimer = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) return;

    const socket = new WebSocket(WS_URL);
    ws.current = socket;

    socket.onopen = () => {
      setConnected(true);
      clearTimeout(reconnectTimer.current);
    };

    socket.onclose = () => {
      setConnected(false);
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    socket.onerror = () => {
      socket.close();
    };

    socket.onmessage = (event) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      switch (msg.type) {
        case "mission_started":
          setMissionStatus("running");
          setAgentTrace([]);
          setBriefing(null);
          break;

        case "agent_event":
          setAgentTrace((prev) => {
            const entry: AgentTrace = {
              agent: msg.agent ?? "unknown",
              status: "running",
              message: msg.message,
              tool_call: msg.tool_call,
              timestamp: msg.timestamp,
            };
            // Mark previous entries for same agent as complete
            return [...prev.map(t => 
              t.agent === entry.agent ? { ...t, status: "complete" } : t
            ), entry];
          });
          break;

        case "mission_complete":
          setMissionStatus("complete");
          if (msg.briefing) setBriefing(msg.briefing);
          if (msg.agent_trace) {
            setAgentTrace(msg.agent_trace.map(t => ({ ...t, status: "complete" })));
          }
          break;

        case "mission_error":
          setMissionStatus("error");
          break;

        case "plan_approved":
          setBriefing(prev => prev ? { ...prev, status: msg.status as any } : prev);
          break;
      }
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [connect]);

  const ping = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: "ping" }));
    }
  }, []);

  return { connected, agentTrace, briefing, missionStatus, ping };
}
