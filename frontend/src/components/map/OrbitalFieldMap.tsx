"use client";

import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import type { BoundaryFeature } from "@/lib/schemas";
import {
  ALGERIA_ORBITAL_CENTER,
  GUELMA_FALLBACK_BOUNDARY,
  closeRing,
} from "@/lib/geo/guelma";

interface OrbitalFieldMapProps {
  boundaryFeature?: BoundaryFeature;
  targetCenter: [number, number]; // [lon, lat]
  parcelRing: [number, number][];
  drawMode: boolean;
  onAddVertex: (coord: [number, number]) => void;
  attributionText: string;
  instantJumpLabel: string;
}

export function OrbitalFieldMap({
  boundaryFeature = GUELMA_FALLBACK_BOUNDARY,
  targetCenter,
  parcelRing,
  drawMode,
  onAddVertex,
  attributionText,
  instantJumpLabel,
}: OrbitalFieldMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const drawModeRef = useRef(drawMode);
  const onAddVertexRef = useRef(onAddVertex);
  const [webglFallback, setWebglFallback] = useState(false);
  const [flightSettled, setFlightSettled] = useState(false);

  drawModeRef.current = drawMode;
  onAddVertexRef.current = onAddVertex;

  // Mount MapLibre GL v5 cleanly WITHOUT 3D terrain during the 2.25s flight
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    let map: maplibregl.Map | null = null;
    try {
      const style: maplibregl.StyleSpecification = {
        version: 8,
        sources: {
          "esri-satellite": {
            type: "raster",
            tiles: [
              "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            ],
            tileSize: 256,
            maxzoom: 19,
          },
        },
        layers: [
          {
            id: "satellite-base",
            type: "raster",
            source: "esri-satellite",
          },
        ],
      };

      map = new maplibregl.Map({
        container: el,
        style,
        center: ALGERIA_ORBITAL_CENTER,
        zoom: 5.2,
        pitch: 0,
        bearing: 0,
        attributionControl: false,
      });

      map.on("error", () => {
        // Suppress external tile load noise in offline environments without crashing
      });

      map.on("load", () => {
        if (!map) return;

        map.addSource("guelma-boundary", {
          type: "geojson",
          data: boundaryFeature as unknown as GeoJSON.GeoJSON,
        });

        map.addLayer({
          id: "guelma-boundary-fill",
          type: "fill",
          source: "guelma-boundary",
          paint: {
            "fill-color": "#137135",
            "fill-opacity": 0.08,
          },
        });

        map.addLayer({
          id: "guelma-boundary-line",
          type: "line",
          source: "guelma-boundary",
          paint: {
            "line-color": "#137135",
            "line-width": 2.5,
            "line-dasharray": [3, 2],
          },
        });

        map.addSource("active-parcel", {
          type: "geojson",
          data: {
            type: "FeatureCollection",
            features: [],
          },
        });

        map.addLayer({
          id: "active-parcel-fill",
          type: "fill",
          source: "active-parcel",
          paint: {
            "fill-color": "#84E875",
            "fill-opacity": 0.25,
          },
        });

        map.addLayer({
          id: "active-parcel-line",
          type: "line",
          source: "active-parcel",
          paint: {
            "line-color": "#FFFFFF",
            "line-width": 2.5,
            "line-dasharray": [3, 2],
          },
        });

        const reducedMotion =
          typeof window !== "undefined" &&
          window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

        // Deferred 3D DEM hillshade strictly attached ONLY on moveend after 2.25s dive
        map.once("moveend", () => {
          setFlightSettled(true);
          try {
            if (map && !map.getSource("aws-terrarium-dem")) {
              map.addSource("aws-terrarium-dem", {
                type: "raster-dem",
                tiles: [
                  "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png",
                ],
                tileSize: 256,
                encoding: "terrarium",
                maxzoom: 15,
              });
              map.setTerrain({ source: "aws-terrarium-dem", exaggeration: 1.25 });
            }
          } catch {
            // Optional visual 3D DEM layer
          }
        });

        if (reducedMotion) {
          map.jumpTo({
            center: targetCenter,
            zoom: 16.5,
            pitch: 42,
            bearing: -12,
          });
        } else {
          // Single uninterrupted 2.25s GTA-V orbital sky-dive
          map.flyTo({
            center: targetCenter,
            zoom: 16.5,
            pitch: 42,
            bearing: -12,
            duration: 2250,
            curve: 1.35,
            essential: true,
            easing: (t) => 1 - Math.pow(1 - t, 3.2),
          });
        }
      });

      map.on("click", (e) => {
        if (!drawModeRef.current) return;
        onAddVertexRef.current([
          Number(e.lngLat.lng.toFixed(6)),
          Number(e.lngLat.lat.toFixed(6)),
        ]);
      });

      mapRef.current = map;
    } catch {
      setWebglFallback(true);
      setFlightSettled(true);
    }

    return () => {
      if (map) {
        try {
          map.remove();
        } catch {
          // ignore cleanup error
        }
      }
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update active boundary & target center smoothly when presets or clicks change
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) return;

    const boundarySource = map.getSource("guelma-boundary") as maplibregl.GeoJSONSource | undefined;
    if (boundarySource) {
      boundarySource.setData(boundaryFeature as unknown as GeoJSON.GeoJSON);
    }
  }, [boundaryFeature]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const updateParcel = () => {
      const src = map.getSource("active-parcel") as maplibregl.GeoJSONSource | undefined;
      if (!src) return;
      const features: GeoJSON.Feature[] = [];
      if (parcelRing.length >= 3) {
        features.push({
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [closeRing(parcelRing)],
          },
        });
      }
      features.push({
        type: "Feature",
        properties: {},
        geometry: {
          type: "Point",
          coordinates: targetCenter,
        },
      });
      src.setData({
        type: "FeatureCollection",
        features,
      });
    };

    if (map.isStyleLoaded()) {
      updateParcel();
    } else {
      map.once("load", updateParcel);
    }
  }, [parcelRing, targetCenter]);

  const prevCenterRef = useRef<[number, number]>(targetCenter);
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const [prevLon, prevLat] = prevCenterRef.current;
    if (prevLon === targetCenter[0] && prevLat === targetCenter[1]) return;
    prevCenterRef.current = targetCenter;

    const reducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) {
      map.jumpTo({ center: targetCenter, zoom: 16.0 });
    } else {
      map.flyTo({
        center: targetCenter,
        zoom: 16.0,
        pitch: 42,
        bearing: -12,
        duration: 1400,
        essential: true,
      });
    }
  }, [targetCenter]);

  function handleInstantJump() {
    const map = mapRef.current;
    if (!map) {
      setFlightSettled(true);
      return;
    }
    map.jumpTo({
      center: targetCenter,
      zoom: 16.5,
      pitch: 42,
      bearing: -12,
    });
    setFlightSettled(true);
  }

  return (
    <div className="relative h-[420px] w-full overflow-hidden rounded-2xl border border-[#E5E7EB] bg-[#3B4E2B] lg:h-[560px]">
      {!webglFallback ? (
        <div
          ref={containerRef}
          data-testid="orbital-map-canvas"
          className={`h-full w-full ${drawMode ? "cursor-crosshair" : "cursor-grab"}`}
        />
      ) : (
        /* Graceful fallback SVG map when WebGL is disabled in headless browser */
        <div
          data-testid="orbital-map-fallback"
          onClick={(e) => {
            if (!drawMode) return;
            const rect = e.currentTarget.getBoundingClientRect();
            const relX = (e.clientX - rect.left) / rect.width;
            const relY = (e.clientY - rect.top) / rect.height;
            const lon = Number((7.0 + relX * 0.9).toFixed(6));
            const lat = Number((36.68 - relY * 0.65).toFixed(6));
            onAddVertex([lon, lat]);
          }}
          className="flex h-full w-full flex-col items-center justify-center bg-[#2D3C21] p-4"
        >
          <svg viewBox="0 0 400 260" className="h-full w-full max-w-xl">
            <polygon
              points={
                (
                  (boundaryFeature.geometry.coordinates as number[][][][])?.[0]?.[0] ?? []
                )
                  .map(([lon, lat]) => {
                    const x = ((lon - 6.9) / 1.1) * 380 + 10;
                    const y = ((36.72 - lat) / 0.72) * 240 + 10;
                    return `${x},${y}`;
                  })
                  .join(" ")
              }
              fill="rgba(95, 168, 125, 0.14)"
              stroke="#5FA87D"
              strokeWidth="2"
              strokeDasharray="6 3"
            />
            {parcelRing.length >= 3 && (
              <polygon
                points={parcelRing
                  .map(([lon, lat]) => {
                    const x = ((lon - 6.9) / 1.1) * 380 + 10;
                    const y = ((36.72 - lat) / 0.72) * 240 + 10;
                    return `${x},${y}`;
                  })
                  .join(" ")}
                fill="rgba(132, 232, 117, 0.3)"
                stroke="#84E875"
                strokeWidth="2.5"
                strokeDasharray="4 4"
              />
            )}
            <circle
              cx={Math.max(10, Math.min(390, ((targetCenter[0] - 6.9) / 1.1) * 380 + 10))}
              cy={Math.max(10, Math.min(250, ((36.72 - targetCenter[1]) / 0.72) * 240 + 10))}
              r="7"
              fill="#84E875"
              stroke="#00291B"
              strokeWidth="2"
            />
          </svg>
        </div>
      )}

      {/* Top Overlay Controls */}
      <div className="pointer-events-none absolute inset-x-3 top-3 flex flex-wrap items-center justify-between gap-2">
        <div className="pointer-events-auto rounded-lg border border-[#E5E7EB] bg-white/90 px-3 py-1.5 text-[11px] font-semibold text-[#111827] shadow-sm backdrop-blur-sm">
          <span dir="ltr" className="tabular-nums">
            {targetCenter[1].toFixed(5)}°N, {targetCenter[0].toFixed(5)}°E
          </span>
          {!flightSettled && " · Descending to parcel..."}
        </div>
        <button
          type="button"
          onClick={handleInstantJump}
          className="pointer-events-auto rounded-lg bg-[#00291B] px-3 py-1.5 text-xs font-bold text-white shadow-sm hover:bg-[#04421B] transition"
        >
          {instantJumpLabel}
        </button>
      </div>

      {/* Mandatory Map Attribution Pill */}
      <div className="pointer-events-none absolute bottom-3 start-3 rounded-lg border border-[#E5E7EB] bg-white/90 px-3 py-1.5 text-[11px] text-[#374151] shadow-sm backdrop-blur-sm">
        {attributionText}
      </div>
    </div>
  );
}
