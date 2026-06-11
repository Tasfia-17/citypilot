const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function fetchMapData() {
  const res = await fetch(`${API_URL}/api/map`);
  if (!res.ok) throw new Error("Failed to fetch map data");
  return res.json();
}

export async function fetchComplaints(hours = 48, limit = 2000) {
  const res = await fetch(`${API_URL}/api/complaints?hours=${hours}&limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch complaints");
  return res.json();
}

export async function fetchHotspots(hours = 48) {
  const res = await fetch(`${API_URL}/api/hotspots?hours=${hours}`);
  if (!res.ok) throw new Error("Failed to fetch hotspots");
  return res.json();
}

export async function fetchActivePlan() {
  const res = await fetch(`${API_URL}/api/plans/active`);
  if (!res.ok) throw new Error("Failed to fetch plan");
  return res.json();
}

export async function fetchHealth() {
  const res = await fetch(`${API_URL}/api/health`);
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}

export async function fetchEvents() {
  const res = await fetch(`${API_URL}/api/events`);
  if (!res.ok) throw new Error("Failed to fetch events");
  return res.json();
}

export async function runMission(mission: string, district = "district_7") {
  const res = await fetch(`${API_URL}/api/mission`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mission, district }),
  });
  if (!res.ok) throw new Error("Failed to run mission");
  return res.json();
}

export async function approvePlan(planId: string, approved: boolean, notes = "") {
  const res = await fetch(`${API_URL}/api/plans/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plan_id: planId, approved, notes }),
  });
  if (!res.ok) throw new Error("Failed to approve plan");
  return res.json();
}
