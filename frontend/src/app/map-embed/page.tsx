"use client";
import { useEffect, useRef } from "react";

// This page is loaded in an iframe inside CityMap component
// It's a self-contained deck.gl + mapbox map
export default function MapEmbedPage() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const url = new URL(window.location.href);
    const token = url.searchParams.get("token") || "";

    if (!token) return;

    // Dynamically load mapbox-gl
    const loadMap = async () => {
      const mapboxgl = (await import("mapbox-gl")).default;
      (mapboxgl as any).accessToken = token;

      const map = new mapboxgl.Map({
        container: containerRef.current!,
        style: "mapbox://styles/mapbox/dark-v11",
        center: [-73.9712, 40.7831], // NYC District 7 (Upper West Side)
        zoom: 13,
        pitch: 30,
      });

      // Fetch complaint data and add heatmap
      map.on("load", async () => {
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const [complaintsRes, hotspotsRes] = await Promise.all([
            fetch(`${apiUrl}/api/complaints?hours=48&limit=2000`),
            fetch(`${apiUrl}/api/hotspots?hours=48`),
          ]);

          const complaints = complaintsRes.ok ? await complaintsRes.json() : [];
          const hotspots = hotspotsRes.ok ? await hotspotsRes.json() : [];

          // Add complaint heatmap source
          map.addSource("complaints", {
            type: "geojson",
            data: {
              type: "FeatureCollection",
              features: complaints.map((c: any) => ({
                type: "Feature",
                geometry: { type: "Point", coordinates: [c.lng, c.lat] },
                properties: { type: c.type },
              })),
            },
          });

          // Heatmap layer
          map.addLayer({
            id: "complaints-heat",
            type: "heatmap",
            source: "complaints",
            paint: {
              "heatmap-weight": 1,
              "heatmap-intensity": ["interpolate", ["linear"], ["zoom"], 11, 1, 15, 3],
              "heatmap-color": [
                "interpolate", ["linear"], ["heatmap-density"],
                0, "rgba(0,25,100,0)",
                0.2, "rgba(0,92,230,0.6)",
                0.5, "rgba(240,122,18,0.8)",
                1, "rgba(249,34,14,1)",
              ],
              "heatmap-radius": ["interpolate", ["linear"], ["zoom"], 11, 20, 15, 40],
              "heatmap-opacity": 0.8,
            },
          });

          // Hotspot circles
          if (hotspots.length > 0) {
            map.addSource("hotspots", {
              type: "geojson",
              data: {
                type: "FeatureCollection",
                features: hotspots
                  .filter((h: any) => h.avg_lat && h.avg_lng)
                  .map((h: any) => ({
                    type: "Feature",
                    geometry: { type: "Point", coordinates: [h.avg_lng, h.avg_lat] },
                    properties: { count: h.count, zip: h._id },
                  })),
              },
            });

            map.addLayer({
              id: "hotspot-circles",
              type: "circle",
              source: "hotspots",
              paint: {
                "circle-radius": ["interpolate", ["linear"], ["get", "count"], 1, 8, 100, 40],
                "circle-color": [
                  "interpolate", ["linear"], ["get", "count"],
                  0, "#22c55e",
                  20, "#f59e0b",
                  50, "#ef4444",
                ],
                "circle-opacity": 0.7,
                "circle-stroke-width": 2,
                "circle-stroke-color": "#ffffff",
                "circle-stroke-opacity": 0.4,
              },
            });

            // Labels
            map.addLayer({
              id: "hotspot-labels",
              type: "symbol",
              source: "hotspots",
              layout: {
                "text-field": ["to-string", ["get", "count"]],
                "text-size": 11,
                "text-anchor": "center",
              },
              paint: { "text-color": "#ffffff" },
            });
          }
        } catch (e) {
          console.error("Map data load error:", e);
        }
      });
    };

    loadMap();
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ width: "100%", height: "100vh", background: "#0a0f1e" }}
    />
  );
}
