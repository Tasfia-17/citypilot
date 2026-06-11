"use client";
import { useState } from "react";
import { runMission } from "@/lib/api";

interface Props {
  onMissionStart?: (mission: string) => void;
  connected: boolean;
  missionStatus: string;
}

const PRESET_MISSIONS = [
  "Prepare District 7 for tomorrow's football match at 7PM",
  "Address the water main break on Upper West Side",
  "Heat emergency response for Districts 5 and 7",
];

export default function Header({ onMissionStart, connected, missionStatus }: Props) {
  const [mission, setMission] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [now, setNow] = useState(() => new Date());

  // Update clock every second
  useState(() => {
    const interval = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(interval);
  });

  const handleSubmit = async (e: React.FormEvent | null, preset?: string) => {
    e?.preventDefault();
    const text = preset || mission.trim();
    if (!text || submitting || missionStatus === "running") return;

    setSubmitting(true);
    try {
      await runMission(text);
      onMissionStart?.(text);
      if (!preset) setMission("");
    } catch (err) {
      console.error("Mission error:", err);
    } finally {
      setSubmitting(false);
    }
  };

  const isRunning = missionStatus === "running";

  return (
    <header className="bg-city-panel border-b border-city-border px-4 py-3">
      <div className="flex items-center gap-4">
        {/* Logo */}
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xl">🏛️</span>
          <div>
            <h1 className="text-white font-bold text-base leading-none">CITYPILOT</h1>
            <p className="text-gray-500 text-xs">Situation Room</p>
          </div>
        </div>

        {/* Mission Input */}
        <form onSubmit={handleSubmit} className="flex-1 flex gap-2">
          <div className="relative flex-1">
            <input
              type="text"
              value={mission}
              onChange={e => setMission(e.target.value)}
              placeholder={isRunning ? "Agent pipeline running..." : "Enter mission (e.g. Prepare District 7 for tomorrow's football match)"}
              disabled={isRunning || submitting}
              className="w-full bg-city-dark border border-city-border rounded-lg px-4 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-blue-600 disabled:opacity-60 transition-colors"
            />
            {/* Preset dropdown */}
            <div className="absolute top-full left-0 right-0 mt-1 z-50 hidden group-focus-within:block">
              {PRESET_MISSIONS.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSubmit(null, p)}
                  className="w-full text-left px-4 py-2 text-xs text-gray-300 hover:bg-city-border bg-city-dark border-x border-b border-city-border"
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          <button
            type="submit"
            disabled={!mission.trim() || isRunning || submitting}
            className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold text-sm rounded-lg transition-colors whitespace-nowrap"
          >
            {isRunning ? (
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 bg-white rounded-full animate-bounce" />
                Running
              </span>
            ) : "▶ Run Mission"}
          </button>
        </form>

        {/* Quick presets */}
        <div className="hidden lg:flex gap-1.5 shrink-0">
          {PRESET_MISSIONS.slice(0, 2).map((p, i) => (
            <button
              key={i}
              onClick={() => handleSubmit(null, p)}
              disabled={isRunning}
              className="px-2.5 py-1.5 text-xs text-gray-400 hover:text-white border border-city-border hover:border-blue-700 rounded-md bg-city-dark transition-colors disabled:opacity-50 max-w-[120px] truncate"
              title={p}
            >
              {["⚽", "💧", "🌡️"][i]} Demo {i + 1}
            </button>
          ))}
        </div>

        {/* Status indicators */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${connected ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
            <span className="text-xs text-gray-500">{connected ? "LIVE" : "OFFLINE"}</span>
          </div>
          <div className="text-xs text-gray-600 font-mono">
            {now.toLocaleTimeString("en-US", { hour12: false })}
          </div>
        </div>
      </div>
    </header>
  );
}
