"use client";
import { useState } from "react";
import type { Briefing } from "@/types";
import { approvePlan } from "@/lib/api";

const DEPT_ICONS: Record<string, string> = {
  Transit: "🚌",
  Traffic: "🚦",
  Sanitation: "🗑️",
  Emergency: "🚨",
  Public_Affairs: "📢",
  Utilities: "⚡",
  DEP: "💧",
};

interface Props {
  briefing: Briefing | null;
  onApproved?: (status: string) => void;
}

export default function ActionPlan({ briefing, onApproved }: Props) {
  const [approving, setApproving] = useState(false);

  if (!briefing) {
    return (
      <div className="text-center py-8 text-gray-600">
        <p className="text-sm">No active action plan</p>
        <p className="text-xs mt-1">Run a mission to generate recommendations</p>
      </div>
    );
  }

  const handleApprove = async (approved: boolean) => {
    if (!briefing.plan_id) return;
    setApproving(true);
    try {
      await approvePlan(briefing.plan_id, approved);
      onApproved?.(approved ? "approved" : "rejected");
    } catch (e) {
      console.error("Approve error:", e);
    } finally {
      setApproving(false);
    }
  };

  const impact = briefing.predicted_impact;
  const isApproved = briefing.status === "approved";
  const isPending = briefing.status === "pending_approval";

  return (
    <div className="space-y-4">
      {/* Situation Summary */}
      {briefing.situation_summary && (
        <div className="p-3 bg-blue-950/30 border border-blue-900/50 rounded-lg">
          <p className="text-xs text-blue-300 leading-relaxed">{briefing.situation_summary}</p>
        </div>
      )}

      {/* Action items */}
      <div className="space-y-2">
        {briefing.action_plan.map((action, i) => {
          const icon = DEPT_ICONS[action.department] || "📌";
          return (
            <div key={action.id || i} className="flex gap-3 p-3 bg-city-panel border border-city-border rounded-lg">
              <span className="text-lg shrink-0 mt-0.5">{icon}</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-xs font-semibold text-white">{action.action}</span>
                  {action.priority === "HIGH" && (
                    <span className="text-xs text-red-400 border border-red-900/50 px-1.5 rounded shrink-0">HIGH</span>
                  )}
                </div>
                <div className="flex gap-3 mt-1">
                  <span className="text-xs text-gray-500">⏱ {action.timing}</span>
                  <span className="text-xs text-green-400">↓ {action.impact}</span>
                </div>
                <span className="text-xs text-gray-600">{action.department.replace(/_/g, " ")}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Predicted Impact */}
      {impact && (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-3 bg-city-panel border border-city-border rounded-lg text-center">
            <p className="text-2xl font-bold text-green-400">↓{impact.congestion_reduction_pct}%</p>
            <p className="text-xs text-gray-500 mt-1">Congestion</p>
          </div>
          <div className="p-3 bg-city-panel border border-city-border rounded-lg text-center">
            <p className="text-2xl font-bold text-blue-400">↓{impact.complaint_reduction_pct}%</p>
            <p className="text-xs text-gray-500 mt-1">Complaints</p>
          </div>
          <div className="p-3 bg-city-panel border border-city-border rounded-lg text-center">
            <p className="text-xl font-bold text-white">{impact.population_served?.toLocaleString()}</p>
            <p className="text-xs text-gray-500 mt-1">People served</p>
          </div>
          <div className="p-3 bg-city-panel border border-city-border rounded-lg text-center">
            <p className={`text-xl font-bold ${impact.confidence_pct >= 80 ? "text-green-400" : "text-amber-400"}`}>
              {impact.confidence_pct}%
            </p>
            <p className="text-xs text-gray-500 mt-1">Confidence</p>
          </div>
        </div>
      )}

      {/* Approval buttons */}
      {isPending && (
        <div className="flex gap-2 pt-2">
          <button
            onClick={() => handleApprove(true)}
            disabled={approving}
            className="flex-1 py-2.5 bg-green-600 hover:bg-green-500 disabled:opacity-50 text-white font-semibold text-sm rounded-lg transition-colors"
          >
            {approving ? "Processing..." : "✓ APPROVE PLAN"}
          </button>
          <button
            onClick={() => handleApprove(false)}
            disabled={approving}
            className="px-4 py-2.5 bg-red-900/50 hover:bg-red-900 border border-red-800 disabled:opacity-50 text-red-300 text-sm rounded-lg transition-colors"
          >
            ✗ Reject
          </button>
        </div>
      )}

      {isApproved && (
        <div className="py-2.5 text-center text-green-400 text-sm font-semibold border border-green-900/50 bg-green-950/30 rounded-lg">
          ✓ Plan Approved — Deploying to departments
        </div>
      )}
    </div>
  );
}
