"use client";

import React, { useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import {
  Plant,
  Export,
  DotsThree,
  ArrowsOut,
  Plus,
  Minus,
  NavigationArrow,
} from "@phosphor-icons/react";
import { FloatingTelemetry } from "./FloatingTelemetry";

interface DashboardMapProps {
  onExport?: () => void;
  activeParcelName?: string;
  cropName?: string;
}

export function DashboardMap({
  onExport,
  activeParcelName = "North Field A1",
  cropName = "Corn",
}: DashboardMapProps) {
  const mapContainerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [webglAvailable, setWebglAvailable] = useState<boolean>(true);

  useEffect(() => {
    if (!mapContainerRef.current) return;

    try {
      const map = new maplibregl.Map({
        container: mapContainerRef.current,
        style: {
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
              id: "esri-satellite-layer",
              type: "raster",
              source: "esri-satellite",
            },
          ],
        },
        center: [7.426, 36.463],
        zoom: 15,
        attributionControl: false,
      });

      map.on("error", () => {
        // Quietly absorb offline tile network errors
      });

      mapRef.current = map;

      return () => {
        map.remove();
      };
    } catch {
      setWebglAvailable(false);
    }
  }, []);

  const handleZoomIn = () => {
    if (mapRef.current) {
      mapRef.current.zoomIn();
    }
  };

  const handleZoomOut = () => {
    if (mapRef.current) {
      mapRef.current.zoomOut();
    }
  };

  const handleRecenter = () => {
    if (mapRef.current) {
      mapRef.current.flyTo({ center: [7.426, 36.463], zoom: 15 });
    }
  };

  return (
    <div className="relative h-[490px] w-full overflow-hidden rounded-2xl border border-[#E5E7EB] bg-[#3B4E2B] shadow-sm select-none">
      {/* MapLibre Satellite Viewport */}
      <div
        ref={mapContainerRef}
        className="absolute inset-0 h-full w-full"
        style={{ display: webglAvailable ? "block" : "none" }}
      />

      {/* Fallback Aerial Texture if MapLibre tiles are loading or WebGL disabled */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse at 40% 45%, #4B6334 0%, #354724 60%, #253319 100%)",
          opacity: 0.85,
        }}
      />

      {/* SVG Layer: Field Boundary Polygon & NDVI Heatmap Overlay */}
      <svg
        className="absolute inset-0 h-full w-full pointer-events-none"
        viewBox="0 0 570 490"
        preserveAspectRatio="none"
      >
        <defs>
          {/* NDVI Heatmap Multi-Stop Radial Gradients */}
          <radialGradient
            id="stress-hotspot-primary"
            cx="65%"
            cy="40%"
            r="45%"
            fx="65%"
            fy="40%"
          >
            <stop offset="0%" stopColor="#C03D05" stopOpacity="0.88" />
            <stop offset="25%" stopColor="#CA5609" stopOpacity="0.75" />
            <stop offset="50%" stopColor="#D97706" stopOpacity="0.60" />
            <stop offset="75%" stopColor="#84CC16" stopOpacity="0.45" />
            <stop offset="100%" stopColor="#22C55E" stopOpacity="0.10" />
          </radialGradient>

          <radialGradient
            id="stress-hotspot-secondary"
            cx="32%"
            cy="68%"
            r="38%"
            fx="32%"
            fy="68%"
          >
            <stop offset="0%" stopColor="#C75205" stopOpacity="0.85" />
            <stop offset="35%" stopColor="#D97706" stopOpacity="0.65" />
            <stop offset="70%" stopColor="#84CC16" stopOpacity="0.40" />
            <stop offset="100%" stopColor="#22C55E" stopOpacity="0.08" />
          </radialGradient>

          {/* Clip path matching field polygon */}
          <clipPath id="field-boundary-clip">
            <polygon points="120,70 380,55 490,140 450,380 280,440 90,390 70,220" />
          </clipPath>
        </defs>

        {/* Heatmap Overlay inside parcel clip */}
        <g clipPath="url(#field-boundary-clip)">
          <rect width="570" height="490" fill="url(#stress-hotspot-primary)" />
          <rect width="570" height="490" fill="url(#stress-hotspot-secondary)" />
        </g>

        {/* High-Contrast White Dashed Boundary Polygon for North Field A1 */}
        <polygon
          points="120,70 380,55 490,140 450,380 280,440 90,390 70,220"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2.2"
          strokeDasharray="6 4"
        />
      </svg>

      {/* Field Marker & Label inside Polygon */}
      <div className="absolute left-[135px] top-[140px] z-10 flex items-center gap-2 rounded-lg bg-black/40 px-2.5 py-1 backdrop-blur-sm pointer-events-none">
        <Plant size={17} weight="fill" className="text-[#84E875]" />
        <div>
          <div className="text-[12px] font-bold text-white leading-none">{activeParcelName}</div>
          <div className="text-[10px] text-white/80 leading-tight">{cropName}</div>
        </div>
      </div>

      {/* Top Right Map Action Controls */}
      <div className="absolute right-4 top-3.5 z-20 flex items-center gap-2">
        <button
          type="button"
          onClick={onExport}
          className="flex items-center gap-1.5 rounded-lg border border-[#E5E7EB] bg-white px-3 py-1.5 text-xs font-semibold text-[#111827] shadow-sm hover:bg-gray-50 transition"
        >
          <Export size={13} weight="bold" />
          <span>Export</span>
        </button>
        <button
          type="button"
          title="More options"
          className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white text-[#111827] shadow-sm hover:bg-gray-50 transition"
        >
          <DotsThree size={18} weight="bold" />
        </button>
      </div>

      {/* Floating Dark Glassmorphic Field Health Telemetry Card */}
      <FloatingTelemetry
        fieldZone={activeParcelName}
        cropType={`${cropName} Plantation`}
        healthScore={70}
        humidity="32%"
        phLevel="2.8"
        hectares="2.3"
        waterConsumption="1,250L"
        fertilizerEfficiency="87%"
        equipmentStatus="Active"
      />

      {/* Bottom Left Inset Mini-Map (Multi-spectral NDVI preview) */}
      <div className="absolute bottom-4 left-4 z-20 h-[64px] w-[64px] overflow-hidden rounded-xl border-2 border-white shadow-lg bg-black">
        <div
          className="h-full w-full"
          style={{
            background:
              "radial-gradient(circle at 60% 40%, #CA5609 0%, #15803D 50%, #00291B 100%)",
          }}
          title="NDVI Thermal Spectrum Preview"
        />
        <span className="absolute bottom-0.5 right-1 text-[8px] font-bold text-white/90 drop-shadow">
          NDVI
        </span>
      </div>

      {/* Bottom Right Floating Map Navigation Rail */}
      <div className="absolute bottom-4 right-4 z-20 flex flex-col items-center rounded-full border border-[#E5E7EB] bg-white/95 p-1 shadow-md backdrop-blur-md">
        <button
          type="button"
          onClick={() => {
            if (document.fullscreenElement) {
              document.exitFullscreen?.();
            } else {
              mapContainerRef.current?.requestFullscreen?.();
            }
          }}
          title="Fullscreen"
          className="flex h-7 w-7 items-center justify-center rounded-full text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <ArrowsOut size={14} weight="bold" />
        </button>
        <button
          type="button"
          onClick={handleZoomIn}
          title="Zoom In"
          className="flex h-7 w-7 items-center justify-center rounded-full text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <Plus size={14} weight="bold" />
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          title="Zoom Out"
          className="flex h-7 w-7 items-center justify-center rounded-full text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <Minus size={14} weight="bold" />
        </button>
        <button
          type="button"
          onClick={handleRecenter}
          title="Re-center"
          className="flex h-7 w-7 items-center justify-center rounded-full text-[#374151] hover:bg-gray-100 hover:text-[#111827] transition"
        >
          <NavigationArrow size={14} weight="bold" />
        </button>
      </div>
    </div>
  );
}
