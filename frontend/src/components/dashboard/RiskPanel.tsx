"use client";
import type { Risk } from "@/types";

const SEVERITY_CONFIG = {
  HIGH: { icon: "🔴", color: "text-red-400", border: "border-red-900/50", bg: "bg-red-950/30" },
  MEDIUM: { icon: "🟡", color: "text-amber-400", border: "border-amber-900/50", bg: "bg-amber-950/30" },
  LOW: { icon: "🟢", color: "text-green-400", border: "border-green-900/50", bg: "bg-green-950/30" },
  NORMAL: { icon: "🟢", color: "text-green-400", border: "border-green-900/50", bg: "bg-green-950/30" },
};

interface Props {
  risks: Risk[];
  loading?: boolean;
}

export default function RiskPanel({ risks, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-2">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-14 bg-city-border/50 rounded animate-pulse" />
        ))}
      </div>
    );
  }

  if (!risks.length) {
    return (
      <div className="text-center py-6 text-gray-600">
        <p className="text-sm">No active risks detected</p>
        <p className="text-xs mt-1">Run a mission to analyze the district</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {risks.map((risk) => {
        const cfg = SEVERITY_CONFIG[risk.severity] || SEVERITY_CONFIG.LOW;
        return (
          <div
            key={risk.id}
            className={`p-3 rounded-lg border ${cfg.border} ${cfg.bg} transition-all`}
          >
            <div className="flex items-start gap-2">
              <span className="text-base mt-0.5">{cfg.icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className={`text-sm font-semibold ${cfg.color} truncate`}>
                    {risk.name}
                  </span>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-mono shrink-0 ${cfg.bg} ${cfg.color} border ${cfg.border}`}>
                    {risk.severity}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">{risk.description}</p>
                {risk.zone && (
                  <p className="text-xs text-gray-600 mt-0.5">📍 {risk.zone}</p>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
