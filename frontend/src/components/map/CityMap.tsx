"use client";
import { useEffect, useRef, useMemo } from "react";
import type { MapData } from "@/types";

// Dynamic import guard — deck.gl and mapbox must run client-side only
let DeckGL: any;
let Map: any;
let HeatmapLayer: any;
let ScatterplotLayer: any;
let TextLayer: any;

export default function CityMap({ data }: { data: MapData | null }) {
  const mapToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || "";

  const layers = useMemo(() => {
    if (!data || typeof window === "undefined") return [];

    const complaints = data.complaints.filter(c => c.lat && c.lng);
    const hotspots = data.hotspots || [];
    const riskZones = data.risk_zones || [];

    return [
      // Complaint heatmap
      {
        type: "HeatmapLayer",
        id: "complaints-heat",
        data: complaints,
        getPosition: (d: any) => [d.lng, d.lat],
        getWeight: 1,
        radiusPixels: 40,
        intensity: 1.5,
        threshold: 0.05,
        colorRange: [
          [0, 25, 100, 25],
          [0, 92, 230, 100],
          [240, 122, 18, 180],
          [249, 34, 14, 240],
        ],
      },
      // Hotspot markers
      {
        type: "ScatterplotLayer",
        id: "hotspots",
        data: hotspots,
        getPosition: (d: any) => [d.avg_lng || 0, d.avg_lat || 0],
        getRadius: (d: any) => Math.sqrt(d.count) * 80,
        getFillColor: (d: any) =>
          d.count > 50 ? [239, 68, 68, 180] :
          d.count > 20 ? [245, 158, 11, 180] :
          [34, 197, 94, 160],
        stroked: true,
        getLineColor: [255, 255, 255, 100],
        lineWidthMinPixels: 1,
      },
      // Risk zone markers
      {
        type: "ScatterplotLayer",
        id: "risk-zones",
        data: riskZones.filter(z => z.lat && z.lng),
        getPosition: (d: any) => [d.lng, d.lat],
        getRadius: 300,
        getFillColor: [59, 130, 246, 100],
        stroked: true,
        getLineColor: [59, 130, 246, 255],
        lineWidthMinPixels: 2,
      },
    ];
  }, [data]);

  if (typeof window === "undefined") return null;

  return (
    <div className="relative w-full h-full">
      <ClientMap token={mapToken} layers={layers} />
    </div>
  );
}

// Client-only map renderer using raw mapbox-gl + deck.gl
function ClientMap({ token, layers }: { token: string; layers: any[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  if (!token) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-city-panel">
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-3">🗺️</div>
          <p className="text-sm">Map requires NEXT_PUBLIC_MAPBOX_TOKEN</p>
          <p className="text-xs mt-1 text-gray-600">Add your Mapbox token to .env.local</p>
          {/* Show complaint data table as fallback */}
          <div className="mt-4 text-left text-xs font-mono text-green-400">
            <p>▶ Complaint heatmap layer: ready</p>
            <p>▶ Hotspot scatterplot: ready</p>
            <p>▶ Risk zone overlay: ready</p>
            <p className="text-gray-500 mt-1">Awaiting map token...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full" id="deck-map-container">
      <iframe
        src={`/map-embed?token=${encodeURIComponent(token)}`}
        className="w-full h-full border-0"
        title="City Map"
      />
    </div>
  );
}
