"use client";

import React from "react";
import {
  computePerimeterMeters,
  extractRingFromBoundary,
  stripClosingPoint,
} from "@/lib/geo/guelma";

interface FieldPolygonThumbnailProps {
  boundary?: Record<string, unknown> | null;
  ring?: [number, number][];
  latitude: number;
  longitude: number;
  active?: boolean;
  insideGuelma?: boolean;
  areaHectares?: number;
  className?: string;
}

export function FieldPolygonThumbnail({
  boundary,
  ring,
  latitude,
  longitude,
  active = false,
  insideGuelma = true,
  areaHectares,
  className = "",
}: FieldPolygonThumbnailProps) {
  const rawPts = ring?.length
    ? stripClosingPoint(ring)
    : extractRingFromBoundary(boundary);

  const pts: [number, number][] =
    rawPts.length >= 3
      ? rawPts
      : [
          [longitude - 0.001, latitude - 0.0008],
          [longitude + 0.001, latitude - 0.0008],
          [longitude + 0.0008, latitude + 0.0009],
          [longitude - 0.0009, latitude + 0.0008],
        ];

  const width = 128;
  const height = 84;
  const pad = 12;

  let minLon = Infinity;
  let maxLon = -Infinity;
  let minLat = Infinity;
  let maxLat = -Infinity;
  for (const [lon, lat] of pts) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }

  // Compensate longitudinal scale for Guelma latitude (~36.45 N)
  const cosLat = Math.cos((latitude * Math.PI) / 180);
  const spanX = Math.max((maxLon - minLon) * cosLat, 1e-6);
  const spanY = Math.max(maxLat - minLat, 1e-6);
  const scale = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanY);

  const cx = (minLon + maxLon) / 2;
  const cy = (minLat + maxLat) / 2;

  const projected = pts.map(([lon, lat]) => {
    const x = width / 2 + (lon - cx) * cosLat * scale;
    const y = height / 2 - (lat - cy) * scale;
    return [Number(x.toFixed(1)), Number(y.toFixed(1))] as [number, number];
  });

  const pointsAttr = projected.map(([x, y]) => `${x},${y}`).join(" ");
  const perimM = Math.round(computePerimeterMeters(pts, true));
  const strokeCol = !insideGuelma ? "#DC2626" : active ? "#0B4B2E" : "#15803D";
  const fillCol = !insideGuelma ? "rgba(220,38,38,0.16)" : active ? "rgba(19,113,53,0.24)" : "rgba(34,197,94,0.18)";

  return (
    <div
      className={`relative overflow-hidden rounded-xl border bg-[#0E1E17] ${
        active ? "border-[#137135] ring-2 ring-[#137135]/20" : "border-[#D5DED8]"
      } ${className}`}
      title={`${pts.length} vertices · ${perimM} m perimeter`}
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="block h-full w-full"
        aria-hidden="true"
      >
        <defs>
          <pattern id="thumb-grid" width="16" height="16" patternUnits="userSpaceOnUse">
            <path d="M 16 0 L 0 0 0 16" fill="none" stroke="rgba(148,180,160,0.12)" strokeWidth="0.7" />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="url(#thumb-grid)" />
        <polygon
          points={pointsAttr}
          fill={fillCol}
          stroke={strokeCol}
          strokeWidth={active ? 2.2 : 1.7}
          strokeLinejoin="round"
        />
        {projected.map(([vx, vy], idx) => (
          <circle
            key={idx}
            cx={vx}
            cy={vy}
            r={idx === 0 ? 2.6 : 1.9}
            fill={idx === 0 ? "#86EFAC" : "#ECFDF5"}
            stroke="#064E3B"
            strokeWidth="0.7"
          />
        ))}
      </svg>
      {areaHectares !== undefined ? (
        <span className="absolute bottom-1.5 right-1.5 rounded-md bg-black/70 px-1.5 py-0.5 font-mono text-[10px] font-semibold text-[#D1FAE5] backdrop-blur-sm">
          {areaHectares.toFixed(1)} ha
        </span>
      ) : null}
    </div>
  );
}

