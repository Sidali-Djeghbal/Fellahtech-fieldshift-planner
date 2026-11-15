export type Lang = "en" | "fr" | "ar";

export type Priority = "balanced" | "water" | "soil" | "income";

export type LayerKey = "truecolor" | "ndvi" | "sm" | "rain" | "lst";

export type LegendKey = Exclude<LayerKey, "truecolor">;

export type StratId = "s0" | "s1" | "s2";

export type PresetId = "tidjelabine" | "guelma" | "constantine" | "mila" | "biskra";

export type ClimateKey = "inland" | "guelma" | "constantine" | "mila" | "biskra";

export type CropKey = "wheat" | "fallow" | "faba" | "barley" | "vetch" | "chickpea";

export type InspectorTab = "field" | "compare" | "audit";

export type MobilePane = "map" | "lab" | "field" | "compare" | "audit";

export interface GibsLayerDef {
  layer: string;
  tms: string;
  ext: "jpeg" | "png";
  maxzoom: number;
  day: number;
  daily: boolean;
}

export interface LegendDef {
  title: string;
  src: string;
  lo: string;
  hi: string;
  bar: string;
}

export interface ClimateData {
  label: string;
  annual: number;
  cv: number;
  frost: number;
  et0: number;
  heat35: number;
  heatLast5: number;
  dryMonths: number;
  powerElev: number;
  rain: number[];
}

export interface SoilBaseData {
  soc: string;
  ph: string;
}

export interface MonthPoint {
  y: number;
  m: number;
}

export interface PresetCoord {
  lon: number;
  lat: number;
}

export interface Preset {
  id: PresetId;
  short: string;
  name: string;
  zone: string;
  climate: ClimateKey;
  elev: number;
  slope: number;
  overviewZoom: number;
  focusZoom: number;
  pitch: number;
  bearing: number;
  note: string;
  ring: [number, number][];
  center: PresetCoord;
  liveSlope: number;
  liveElev: number;
}

export interface CropTrait {
  label: string;
  cover: number[];
  waterUse: number;
  nfix: number;
  nKgHa: number;
  rootM: number;
  residue: number;
  market: number;
  forage: number;
  drought: number;
  heat: number;
}

export interface StrategyDef {
  id: StratId;
  name: string;
  tag: string;
  current?: boolean;
  crops: CropKey[];
  conf: string;
  why: string;
  benefits: string[];
  gaps: string[];
  risks: string[];
}

export interface PriorityWeights {
  water: number;
  soil: number;
  erosion: number;
  income: number;
  risk: number;
}

export interface MonthlyExposureItem {
  rain: number;
  cover: number;
  exp: number;
}

export interface EvalResult {
  water: number;
  soil: number;
  erosion: number;
  income: number;
  risk: number;
  total: number;
  cover: number[];
  monthlyExposure: MonthlyExposureItem[];
  avgNKgHa: number;
  exposureDays: number;
  wetDaysTotal: number;
}

export interface ProtoState {
  lang: Lang;
  priority: Priority;
  rain: number;
  temp: number;
  selected: StratId;
  irrigated: boolean;
  lowInput: boolean;
  plainMode: boolean;
}

