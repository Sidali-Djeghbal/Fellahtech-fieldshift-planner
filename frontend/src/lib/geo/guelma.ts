import area from "@turf/area";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import booleanWithin from "@turf/boolean-within";
import centroid from "@turf/centroid";
import { point, polygon } from "@turf/helpers";
import type { BoundaryFeature } from "@/lib/schemas";

export interface GuelmaParcelPreset {
  id: string;
  zoneName: { en: string; fr: string; ar: string };
  commune: string;
  climateZone: GuelmaClimateZone;
  center: [number, number]; // [lon, lat]
  areaHectares: number;
  ring: [number, number][]; // [lon, lat][]
}

export type GuelmaClimateZone =
  | "seybouse_valley"
  | "heliopolis_hills"
  | "bouchegouf_basin"
  | "oued_zenati"
  | "tamlouka_plains";

export interface GuelmaCommune {
  id: string;
  name: { en: string; fr: string; ar: string };
  daira: { en: string; fr: string; ar: string };
  center: [number, number]; // [lon, lat]
  climateZone: GuelmaClimateZone;
}

export const GUELMA_DEFAULT_CENTER: [number, number] = [7.4333, 36.4667];
export const ALGERIA_ORBITAL_CENTER: [number, number] = [7.4333, 36.4667];

// Wilaya 24 (Guelma Province) bounding envelope covering all 34 communes (~36.05-36.68 N, 6.96-7.92 E)
// while keeping Setif (36.19 N, 5.41 E), Constantine (36.36 N, 6.61 E), and coastal Annaba outside.
export const GUELMA_FALLBACK_BOUNDARY: BoundaryFeature = {
  type: "Feature",
  properties: { id: 1, code: "guelma", name: "Wilaya of Guelma" },
  geometry: {
    type: "MultiPolygon",
    coordinates: [
      [
        [
          [7.04, 36.06],
          [7.38, 36.04],
          [7.68, 36.07],
          [7.92, 36.24],
          [7.90, 36.52],
          [7.74, 36.66],
          [7.42, 36.68],
          [7.12, 36.60],
          [6.96, 36.38],
          [7.04, 36.06],
        ],
      ],
    ],
  },
  bbox: [6.96, 36.04, 7.92, 36.68],
};

// Complete 34 Communes of Wilaya of Guelma (Wilaya 24), Algeria
export const GUELMA_COMMUNES: GuelmaCommune[] = [
  {
    id: "guelma",
    name: { en: "Guelma", fr: "Guelma", ar: "قالمة" },
    daira: { en: "Guelma", fr: "Guelma", ar: "قالمة" },
    center: [7.4333, 36.4667],
    climateZone: "seybouse_valley",
  },
  {
    id: "heliopolis",
    name: { en: "Héliopolis", fr: "Héliopolis", ar: "هيليوبوليس" },
    daira: { en: "Héliopolis", fr: "Héliopolis", ar: "هيليوبوليس" },
    center: [7.436, 36.502],
    climateZone: "heliopolis_hills",
  },
  {
    id: "belkheir",
    name: { en: "Belkheir", fr: "Belkheir", ar: "بلخير" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.4787, 36.4588],
    climateZone: "seybouse_valley",
  },
  {
    id: "ben_djerrah",
    name: { en: "Ben Djerrah", fr: "Ben Djerrah", ar: "بن جراح" },
    daira: { en: "Guelma", fr: "Guelma", ar: "قالمة" },
    center: [7.3713, 36.4319],
    climateZone: "heliopolis_hills",
  },
  {
    id: "boumahra_ahmed",
    name: { en: "Boumahra Ahmed", fr: "Boumahra Ahmed", ar: "بومهرة أحمد" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.5125, 36.458],
    climateZone: "seybouse_valley",
  },
  {
    id: "beni_mezline",
    name: { en: "Beni Mezline", fr: "Beni Mezline", ar: "بني مزلين" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.6031, 36.4808],
    climateZone: "seybouse_valley",
  },
  {
    id: "djeballah_khemissi",
    name: { en: "Djeballah Khemissi", fr: "Djeballah Khemissi", ar: "جبالة لخميسي" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.5689, 36.4644],
    climateZone: "seybouse_valley",
  },
  {
    id: "guelaat_bou_sbaa",
    name: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.4704, 36.544],
    climateZone: "heliopolis_hills",
  },
  {
    id: "el_fedjoudj",
    name: { en: "El Fedjoudj", fr: "El Fedjoudj", ar: "الفجوج" },
    daira: { en: "Héliopolis", fr: "Héliopolis", ar: "هيليوبوليس" },
    center: [7.3994, 36.5048],
    climateZone: "heliopolis_hills",
  },
  {
    id: "bouati_mahmoud",
    name: { en: "Bouati Mahmoud", fr: "Bouati Mahmoud", ar: "بوعاتي محمود" },
    daira: { en: "Héliopolis", fr: "Héliopolis", ar: "هيليوبوليس" },
    center: [7.3281, 36.5922],
    climateZone: "heliopolis_hills",
  },
  {
    id: "nechmaya",
    name: { en: "Nechmaya", fr: "Nechmaya", ar: "النشماية" },
    daira: { en: "Guelaat Bou Sbaa", fr: "Guelaat Bou Sbaa", ar: "قلعة بوصبع" },
    center: [7.5133, 36.6112],
    climateZone: "heliopolis_hills",
  },
  {
    id: "bouchegouf",
    name: { en: "Bouchegouf", fr: "Bouchegouf", ar: "بوشقوف" },
    daira: { en: "Bouchegouf", fr: "Bouchegouf", ar: "بوشقوف" },
    center: [7.729, 36.471],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "ain_ben_beida",
    name: { en: "Aïn Ben Beida", fr: "Aïn Ben Beida", ar: "عين بن بيضاء" },
    daira: { en: "Bouchegouf", fr: "Bouchegouf", ar: "بوشقوف" },
    center: [7.6953, 36.6177],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "oued_fragha",
    name: { en: "Oued Fragha", fr: "Oued Fragha", ar: "وادي فراغة" },
    daira: { en: "Bouchegouf", fr: "Bouchegouf", ar: "بوشقوف" },
    center: [7.7118, 36.5568],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "medjez_sfa",
    name: { en: "Medjez Sfa", fr: "Medjez Sfa", ar: "مجاز الصفاء" },
    daira: { en: "Bouchegouf", fr: "Bouchegouf", ar: "بوشقوف" },
    center: [7.7824, 36.434],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "hammam_nbails",
    name: { en: "Hammam N'Bails", fr: "Hammam N'Bails", ar: "حمام النبائل" },
    daira: { en: "Hammam N'Bails", fr: "Hammam N'Bails", ar: "حمام النبائل" },
    center: [7.6413, 36.3247],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "oued_cheham",
    name: { en: "Oued Cheham", fr: "Oued Cheham", ar: "وادي الشحم" },
    daira: { en: "Hammam N'Bails", fr: "Hammam N'Bails", ar: "حمام النبائل" },
    center: [7.7644, 36.3789],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "dahouara",
    name: { en: "Dahouara", fr: "Dahouara", ar: "الدهوارة" },
    daira: { en: "Hammam N'Bails", fr: "Hammam N'Bails", ar: "حمام النبائل" },
    center: [7.7331, 36.3514],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "hammam_debagh",
    name: { en: "Hammam Debagh", fr: "Hammam Debagh", ar: "حمام دباغ" },
    daira: { en: "Hammam Debagh", fr: "Hammam Debagh", ar: "حمام دباغ" },
    center: [7.2721, 36.4591],
    climateZone: "heliopolis_hills",
  },
  {
    id: "roknia",
    name: { en: "Roknia", fr: "Roknia", ar: "الركنية" },
    daira: { en: "Hammam Debagh", fr: "Hammam Debagh", ar: "حمام دباغ" },
    center: [7.2307, 36.5478],
    climateZone: "heliopolis_hills",
  },
  {
    id: "bou_hamdane",
    name: { en: "Bou Hamdane", fr: "Bou Hamdane", ar: "بوحمدان" },
    daira: { en: "Hammam Debagh", fr: "Hammam Debagh", ar: "حمام دباغ" },
    center: [7.1111, 36.4628],
    climateZone: "heliopolis_hills",
  },
  {
    id: "medjez_amar",
    name: { en: "Medjez Amar", fr: "Medjez Amar", ar: "مجاز عمار" },
    daira: { en: "Houari Boumediene", fr: "Houari Boumediene", ar: "هواري بومدين" },
    center: [7.3105, 36.4452],
    climateZone: "seybouse_valley",
  },
  {
    id: "houari_boumediene",
    name: { en: "Houari Boumediene", fr: "Houari Boumediene", ar: "هواري بومدين" },
    daira: { en: "Houari Boumediene", fr: "Houari Boumediene", ar: "هواري بومدين" },
    center: [7.3291, 36.4778],
    climateZone: "seybouse_valley",
  },
  {
    id: "ras_el_agba",
    name: { en: "Ras El Agba", fr: "Ras El Agba", ar: "رأس العقبة" },
    daira: { en: "Houari Boumediene", fr: "Houari Boumediene", ar: "هواري بومدين" },
    center: [7.2228, 36.3729],
    climateZone: "oued_zenati",
  },
  {
    id: "sellaoua_announa",
    name: { en: "Sellaoua Announa", fr: "Sellaoua Announa", ar: "سلاوة عنونة" },
    daira: { en: "Houari Boumediene", fr: "Houari Boumediene", ar: "هواري بومدين" },
    center: [7.2507, 36.3868],
    climateZone: "oued_zenati",
  },
  {
    id: "khezaras",
    name: { en: "Khezaras", fr: "Khézaras", ar: "لخزارة" },
    daira: { en: "Khezaras", fr: "Khézaras", ar: "لخزارة" },
    center: [7.5292, 36.3694],
    climateZone: "bouchegouf_basin",
  },
  {
    id: "bou_hachana",
    name: { en: "Bou Hachana", fr: "Bou Hachana", ar: "بوحشانة" },
    daira: { en: "Khezaras", fr: "Khézaras", ar: "لخزارة" },
    center: [7.5078, 36.3069],
    climateZone: "oued_zenati",
  },
  {
    id: "ain_sandel",
    name: { en: "Aïn Sandel", fr: "Aïn Sandel", ar: "عين صندل" },
    daira: { en: "Khezaras", fr: "Khézaras", ar: "لخزارة" },
    center: [7.5125, 36.2447],
    climateZone: "tamlouka_plains",
  },
  {
    id: "oued_zenati",
    name: { en: "Oued Zenati", fr: "Oued Zenati", ar: "وادي الزناتي" },
    daira: { en: "Oued Zenati", fr: "Oued Zenati", ar: "وادي الزناتي" },
    center: [7.163, 36.32],
    climateZone: "oued_zenati",
  },
  {
    id: "ain_reggada",
    name: { en: "Aïn Reggada", fr: "Aïn Reggada", ar: "عين رقادة" },
    daira: { en: "Oued Zenati", fr: "Oued Zenati", ar: "وادي الزناتي" },
    center: [7.0739, 36.2594],
    climateZone: "oued_zenati",
  },
  {
    id: "bordj_sabath",
    name: { en: "Bordj Sabath", fr: "Bordj Sabath", ar: "برج صباط" },
    daira: { en: "Oued Zenati", fr: "Oued Zenati", ar: "وادي الزناتي" },
    center: [7.0485, 36.4029],
    climateZone: "oued_zenati",
  },
  {
    id: "ain_makhlouf",
    name: { en: "Aïn Makhlouf", fr: "Aïn Makhlouf", ar: "عين مخلوف" },
    daira: { en: "Aïn Makhlouf", fr: "Aïn Makhlouf", ar: "عين مخلوف" },
    center: [7.2507, 36.2434],
    climateZone: "tamlouka_plains",
  },
  {
    id: "ain_larbi",
    name: { en: "Aïn Larbi", fr: "Aïn Larbi", ar: "عين العربي" },
    daira: { en: "Aïn Makhlouf", fr: "Aïn Makhlouf", ar: "عين مخلوف" },
    center: [7.3967, 36.2661],
    climateZone: "tamlouka_plains",
  },
  {
    id: "tamlouka",
    name: { en: "Tamlouka", fr: "Tamlouka", ar: "تاملوكة" },
    daira: { en: "Aïn Makhlouf", fr: "Aïn Makhlouf", ar: "عين مخلوف" },
    center: [7.144, 36.1558],
    climateZone: "tamlouka_plains",
  },
];

// 6 Satellite-verified Guelma quick-pick test parcels
// Only geometry, centroid, and geodesic area are populated; soil & elevation_m stay farmer-controlled (ADR-5).
export const GUELMA_PARCEL_PRESETS: GuelmaParcelPreset[] = [
  {
    id: "seybouse",
    zoneName: {
      en: "Seybouse Alluvial Plain",
      fr: "Plaine alluviale de la Seybouse",
      ar: "سهل سيبوس الرسوبي",
    },
    commune: "Guelma",
    climateZone: "seybouse_valley",
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
    commune: "Héliopolis",
    climateZone: "heliopolis_hills",
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
    commune: "Bouchegouf",
    climateZone: "bouchegouf_basin",
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
    commune: "Oued Zenati",
    climateZone: "oued_zenati",
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
    commune: "Hammam Debagh",
    climateZone: "heliopolis_hills",
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
    commune: "Tamlouka",
    climateZone: "tamlouka_plains",
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

export function stripClosingPoint(ring: [number, number][]): [number, number][] {
  if (ring.length < 2) return ring;
  const first = ring[0];
  const last = ring[ring.length - 1];
  if (Math.abs(first[0] - last[0]) < 1e-8 && Math.abs(first[1] - last[1]) < 1e-8) {
    return ring.slice(0, -1);
  }
  return ring;
}

export function ringToGeoJsonPolygon(ring: [number, number][]): Record<string, unknown> | null {
  const vertices = stripClosingPoint(ring);
  if (vertices.length < 3) return null;
  const closed = closeRing(vertices);
  return {
    type: "Polygon",
    coordinates: [closed],
  };
}

export function extractRingFromBoundary(
  boundary: Record<string, unknown> | null | undefined
): [number, number][] {
  if (!boundary) return [];
  const type = boundary.type;
  const coords = boundary.coordinates;
  if (type === "Polygon" && Array.isArray(coords) && Array.isArray(coords[0])) {
    return stripClosingPoint(
      (coords[0] as number[][])
        .filter((pt) => Array.isArray(pt) && pt.length >= 2)
        .map((pt) => [Number(pt[0]), Number(pt[1])] as [number, number])
    );
  }
  return [];
}

export function haversineMeters(a: [number, number], b: [number, number]): number {
  const R = 6371000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLon = toRad(b[0] - a[0]);
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
}

export function computePerimeterMeters(ring: [number, number][], closed = true): number {
  const pts = stripClosingPoint(ring);
  if (pts.length < 2) return 0;
  let total = 0;
  for (let i = 0; i < pts.length - 1; i++) {
    total += haversineMeters(pts[i], pts[i + 1]);
  }
  if (closed && pts.length >= 3) {
    total += haversineMeters(pts[pts.length - 1], pts[0]);
  }
  return Math.round(total);
}

export interface EdgeMidpointHandle {
  insertIndex: number;
  coord: [number, number];
  lengthMeters: number;
}

export function computeEdgeMidpoints(
  ring: [number, number][],
  closed = true
): EdgeMidpointHandle[] {
  const pts = stripClosingPoint(ring);
  if (pts.length < 2) return [];
  const count = closed && pts.length >= 3 ? pts.length : pts.length - 1;
  const handles: EdgeMidpointHandle[] = [];
  for (let i = 0; i < count; i++) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    handles.push({
      insertIndex: i + 1,
      coord: [
        Number(((a[0] + b[0]) / 2).toFixed(6)),
        Number(((a[1] + b[1]) / 2).toFixed(6)),
      ],
      lengthMeters: Math.round(haversineMeters(a, b)),
    });
  }
  return handles;
}

function segmentsIntersect(
  p1: [number, number],
  p2: [number, number],
  q1: [number, number],
  q2: [number, number]
): boolean {
  const orient = (a: [number, number], b: [number, number], c: [number, number]) =>
    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);

  const o1 = orient(p1, p2, q1);
  const o2 = orient(p1, p2, q2);
  const o3 = orient(q1, q2, p1);
  const o4 = orient(q1, q2, p2);

  return ((o1 > 0 && o2 < 0) || (o1 < 0 && o2 > 0)) &&
    ((o3 > 0 && o4 < 0) || (o3 < 0 && o4 > 0));
}

export function ringSegmentsSelfIntersect(ring: [number, number][]): boolean {
  const pts = stripClosingPoint(ring);
  const n = pts.length;
  if (n < 4) return false;
  for (let i = 0; i < n; i++) {
    const a1 = pts[i];
    const a2 = pts[(i + 1) % n];
    for (let j = i + 2; j < n; j++) {
      if (i === 0 && j === n - 1) continue; // Adjacent closing segment
      const b1 = pts[j];
      const b2 = pts[(j + 1) % n];
      if (segmentsIntersect(a1, a2, b1, b2)) {
        return true;
      }
    }
  }
  return false;
}

export function computePolygonAreaHectares(ring: [number, number][]): number {
  const pts = stripClosingPoint(ring);
  if (pts.length < 3) return 0;
  const poly = polygon([closeRing(pts)]);
  const sqMeters = area(poly);
  return Math.max(0.01, Number((sqMeters / 10_000).toFixed(2)));
}

export function computePolygonCentroid(
  ring: [number, number][]
): { latitude: number; longitude: number } | null {
  const pts = stripClosingPoint(ring);
  if (pts.length < 3) return null;
  const poly = polygon([closeRing(pts)]);
  const c = centroid(poly);
  const [longitude, latitude] = c.geometry.coordinates;
  return {
    latitude: Number(latitude.toFixed(6)),
    longitude: Number(longitude.toFixed(6)),
  };
}

export function computePolygonBbox(
  ring: [number, number][]
): [number, number, number, number] | null {
  const pts = stripClosingPoint(ring);
  if (pts.length === 0) return null;
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const [lon, lat] of pts) {
    if (lon < minLon) minLon = lon;
    if (lat < minLat) minLat = lat;
    if (lon > maxLon) maxLon = lon;
    if (lat > maxLat) maxLat = lat;
  }
  return [minLon, minLat, maxLon, maxLat];
}

export function findNearestGuelmaCommune(lat: number, lon: number): GuelmaCommune {
  let best = GUELMA_COMMUNES[0];
  let bestDist = Infinity;
  for (const c of GUELMA_COMMUNES) {
    const d = haversineMeters([lon, lat], c.center);
    if (d < bestDist) {
      bestDist = d;
      best = c;
    }
  }
  return best;
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

    const cleanRing = parcelRing ? stripClosingPoint(parcelRing) : [];
    if (cleanRing.length >= 3) {
      const parcelPoly = polygon([closeRing(cleanRing)]);
      return polygonList.some((poly) => booleanWithin(parcelPoly, poly));
    }
    return true;
  } catch {
    return false;
  }
}
