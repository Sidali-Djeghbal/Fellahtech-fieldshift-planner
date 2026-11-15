import area from "@turf/area";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import booleanWithin from "@turf/boolean-within";
import centroid from "@turf/centroid";
import { point, polygon } from "@turf/helpers";
import type { BoundaryFeature } from "@/lib/schemas";

export interface GuelmaParcelPreset {
  id: string;
  zoneName: { en: string; fr: string; ar: string };
  center: [number, number]; // [lon, lat]
  areaHectares: number;
  ring: [number, number][]; // [lon, lat][]
}

export const GUELMA_DEFAULT_CENTER: [number, number] = [7.44, 36.46];
export const ALGERIA_ORBITAL_CENTER: [number, number] = [7.44, 36.46];

export const GUELMA_FALLBACK_BOUNDARY: BoundaryFeature = {
  type: "Feature",
  properties: { id: 1, code: "guelma", name: "Guelma" },
  geometry: {
    type: "MultiPolygon",
    coordinates: [
      [
        [
          [7.12, 36.08],
          [7.38, 36.05],
          [7.68, 36.07],
          [7.9, 36.22],
          [7.88, 36.48],
          [7.72, 36.63],
          [7.42, 36.65],
          [7.14, 36.58],
          [7.0, 36.36],
          [7.12, 36.08],
        ],
      ],
    ],
  },
  bbox: [7.0, 36.05, 7.9, 36.65],
};

// 6 Satellite-verified Guelma quick-pick test parcels (task.md Part 5)
// Only geometry, centroid, and geodesic area are populated; soil & elevation_m stay farmer-controlled (ADR-5).
export const GUELMA_PARCEL_PRESETS: GuelmaParcelPreset[] = [
  {
    id: "seybouse",
    zoneName: {
      en: "Seybouse Alluvial Plain",
      fr: "Plaine alluviale de la Seybouse",
      ar: "سهل سيبوس الرسوبي",
    },
    center: [7.465915, 36.475014],
    areaHectares: 2.4,
    ring: [
      [7.465811, 36.476114],
      [7.466969, 36.4757],
      [7.465993, 36.473901],
      [7.464888, 36.474341],
      [7.465811, 36.476114],
    ],
  },
  {
    id: "heliopolis",
    zoneName: {
      en: "Heliopolis Hillside",
      fr: "Coteau d'Héliopolis",
      ar: "مرتفعات هيليوبوليس",
    },
    center: [7.475853, 36.495139],
    areaHectares: 7.9,
    ring: [
      [7.47685, 36.49692],
      [7.47755, 36.49622],
      [7.47788, 36.49562],
      [7.47748, 36.49495],
      [7.47522, 36.49352],
      [7.47462, 36.49402],
      [7.474, 36.49468],
      [7.47322, 36.49518],
      [7.47685, 36.49692],
    ],
  },
  {
    id: "bouchegouf",
    zoneName: {
      en: "Bouchegouf Valley",
      fr: "Vallée de Bouchegouf",
      ar: "وادي بوشقوف",
    },
    center: [7.72791, 36.461771],
    areaHectares: 10.5,
    ring: [
      [7.72705, 36.46336],
      [7.72855, 36.46338],
      [7.72948, 36.46332],
      [7.72988, 36.4616],
      [7.73018, 36.46018],
      [7.72895, 36.45998],
      [7.728, 36.46],
      [7.7273, 36.46032],
      [7.7267, 36.4611],
      [7.72622, 36.46225],
      [7.72606, 36.46266],
      [7.72655, 36.4631],
      [7.72705, 36.46336],
    ],
  },
  {
    id: "oz",
    zoneName: {
      en: "Oued Zenati Slope",
      fr: "Versant d'Oued Zenati",
      ar: "منحدر وادي الزناتي",
    },
    center: [7.150591, 36.320187],
    areaHectares: 5.2,
    ring: [
      [7.14896, 36.32086],
      [7.15202, 36.32128],
      [7.1523, 36.32055],
      [7.15226, 36.31962],
      [7.1506, 36.31942],
      [7.14908, 36.31938],
      [7.14892, 36.3202],
      [7.14896, 36.32086],
    ],
  },
  {
    id: "bouhamdane",
    zoneName: {
      en: "Bouhamdane Dam Basin",
      fr: "Bassin du barrage Bouhamdane",
      ar: "حوض سد بوحمدان",
    },
    center: [7.270168, 36.465938],
    areaHectares: 2.9,
    ring: [
      [7.26904, 36.46696],
      [7.26972, 36.4669],
      [7.27065, 36.46652],
      [7.27182, 36.46552],
      [7.27112, 36.46542],
      [7.27082, 36.46515],
      [7.26968, 36.46506],
      [7.26962, 36.46595],
      [7.26904, 36.46596],
      [7.26904, 36.46696],
    ],
  },
  {
    id: "tamlouka",
    zoneName: {
      en: "Tamlouka High Plains",
      fr: "Hautes plaines de Tamlouka",
      ar: "الهضاب العليا لتملوكة",
    },
    center: [7.12595, 36.148317],
    areaHectares: 4.3,
    ring: [
      [7.125, 36.14975],
      [7.12572, 36.14902],
      [7.12558, 36.1488],
      [7.12862, 36.14644],
      [7.12782, 36.14585],
      [7.12426, 36.14894],
      [7.12465, 36.14942],
      [7.125, 36.14975],
    ],
  },
];

// Edge-case outside boundary test coordinates (Setif, §9.2)
export const SETIF_OUTSIDE_TEST_COORD = {
  latitude: 36.19,
  longitude: 5.41,
  label: "Setif (Ain Arnat) · Outside Guelma MVP",
};

export function closeRing(ring: [number, number][]): [number, number][] {
  if (ring.length === 0) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (first[0] === last[0] && first[1] === last[1]) return ring;
  return [...ring, first];
}

export function ringToGeoJsonPolygon(ring: [number, number][]): Record<string, unknown> | null {
  if (ring.length < 3) return null;
  const closed = closeRing(ring);
  return {
    type: "Polygon",
    coordinates: [closed],
  };
}

export function computePolygonAreaHectares(ring: [number, number][]): number {
  if (ring.length < 3) return 0;
  const poly = polygon([closeRing(ring)]);
  const sqMeters = area(poly);
  return Math.max(0.01, Number((sqMeters / 10_000).toFixed(2)));
}

export function computePolygonCentroid(
  ring: [number, number][]
): { latitude: number; longitude: number } | null {
  if (ring.length < 3) return null;
  const poly = polygon([closeRing(ring)]);
  const c = centroid(poly);
  const [longitude, latitude] = c.geometry.coordinates;
  return {
    latitude: Number(latitude.toFixed(6)),
    longitude: Number(longitude.toFixed(6)),
  };
}

export function isInsideGuelmaBoundary(
  latitude: number,
  longitude: number,
  boundary: BoundaryFeature = GUELMA_FALLBACK_BOUNDARY,
  parcelRing?: [number, number][] | null
): boolean {
  try {
    const geom = boundary.geometry;
    const polygonList =
      geom.type === "MultiPolygon"
        ? (geom.coordinates as number[][][][]).map((coords) => polygon(coords))
        : [polygon(geom.coordinates as number[][][])];

    const pt = point([longitude, latitude]);
    const pointCovered = polygonList.some((poly) => booleanPointInPolygon(pt, poly));
    if (!pointCovered) return false;

    if (parcelRing && parcelRing.length >= 3) {
      const parcelPoly = polygon([closeRing(parcelRing)]);
      return polygonList.some((poly) => booleanWithin(parcelPoly, poly));
    }
    return true;
  } catch {
    return false;
  }
}
