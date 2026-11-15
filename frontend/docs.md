# FELLAH TECH — Frontend Documentation Module (NASA Space Apps Challenge)

> **Purpose:** Modular **frontend-only** submission documentation (`fieldshift-frontend`, v3.2.0) designed to be **merged with your Backend and AI/ML team docs** before pasting into the final NASA Space Apps Challenge form.
>
> Text snippets below intentionally stay concise so combined team answers (Frontend + Backend + AI Model) remain well within form limits (such as the `50–200` word / `1,500`-character `Summary *`), while all frontend dependencies, NASA layers, and partner datasets are listed completely for attribution.

---

## 1. Project Summary *(Mergeable Frontend Slice)*

### Project Name Component

- **Frontend / Product Name:** `FELLAH TECH`

### Summary \* — Frontend Contribution *(`50 words` / `343 characters` — leaves room for Backend + AI)*

Combine this concise paragraph with ~50–120 words describing your Backend & AI Model:

> **Frontend (`FELLAH TECH`):** A trilingual (**EN / FR / AR RTL**) **Next.js, MapLibre GL JS, and Turf.js** geospatial workspace enabling farmers in **Guelma, Algeria (34 communes)** to trace parcels on satellite imagery, explore **NASA GIBS** layers and **3D Terrarium terrain**, inspect **Plain-Language / Scientific** rotation plans, and track data-completeness warnings.

---

## 2. Project Links *(Frontend URLs — Merge with Repo / Demo)*

- **Live Deployed Frontend (`Project *` candidate — verified HTTP `200`, public, no auth wall):**
  `https://fieldshift-planner.sidalidjeghbal.workers.dev/`
- **GitHub Repository (`origin` remote):**
  `https://github.com/Sidali-Djeghbal/fieldshift-planner`
  *(Note: returned HTTP `404` unauthenticated during verification; switch repository visibility to **Public** before adding it to the portal.)*
- **Demonstration Video Workflow (`Project Demonstration *` helper):**
  See [video.md](./video.md) for the `<= 30s` live frontend capture script (`record_demo.mjs` + `ffmpeg`); insert the final public YouTube / Drive / GitHub link once uploaded.

---

## 3. Project Details \* *(Frontend Section — Ready to Merge Before/After Backend & AI)*

Append your **Backend** and **AI/ML Engine** subsections cleanly alongside the frontend details below:

### Frontend: What It Does & How It Works

The **FELLAH TECH** web client (`fieldshift-frontend`, v3.2.0) turns Earth observation, elevation data, and multi-year rotation outputs into an accessible spatial workflow across five core modules:

1. **Guelma Command Center (`/` & `/dashboard`):** Renders farm/parcel KPIs, commune coverage across all **34 communes** of Wilaya 24, soil/irrigation readiness gauges, spatial health donuts, and a sandbox sample loader (`4` sample parcels totaling `26.4 ha`, plus unstudied demo parcel `F1` — `9.36 ha` in Boumahra Ahmed).
2. **Precision Satellite CAD Border Editor (`GuelmaBorderEditorMap`):** Interactive polygon drawing, draggable vertex & midpoint handles, undo/redo, live geodesic area (`ha`) & perimeter (`m`) calculation, self-intersection checks, and Wilaya 24 containment validation via **Turf.js** (`@turf/*`), paired with searchable 34-commune fly-to, **NASA GIBS NDVI / GLDAS Soil Moisture** toggles, and `2D Ortho / 3D Relief` terrain pitch.
3. **Orbital 3D Terrain & NASA GIBS Simulator (`FieldShiftPrototypeApp`, `engine.ts`):** Interactive **MapLibre GL JS v5** 3D terrain viewer streaming five **NASA GIBS WMTS** layers, a **22-month (`2025–2026`) timeline scrubber**, client-side **AWS/Mapzen Terrarium (`z=12`)** RGB elevation/slope decoding in Canvas (`measureCoordFromDem`, cached in `sessionStorage`), and live drought/warming/priority stress testing across three baseline crop sequences.
4. **AI Intelligence Studio & Multi-Route Views:**
   - **Embedded Studio (`FieldShiftAiIntelligenceSection`):** Displays unverified parcel banners (`DEMO_PARCEL_UNVERIFIED`), executive summaries, requested-crop disposition tracking, data completeness meters (`0–100%`) with missing soil inputs (`soil_ph`, `organic_matter_percent`), 4-season timeline rails, and 7 scientific explanation tabs.
   - **`/comparison`:** 7-axis SVG spider radar (`ScoreRadarChart`), 12-month bare-soil & climatic stress matrix (`AgronomicRiskCalendar`), strategy selection/rejection persistence, climate what-if sliders, and 1-page print brief (`PrintableBrief`).
   - **`/evidence`, `/farm-profile`, `/select-field`:** Searchable Earth-observation evidence ledger (`EvidencePage`), CRUD farm/field forms with balanced 100%-sum priority sliders and **USDA Soil Texture Triangle** modal (`UsdaTextureModal`), and parcel boundary selector (`OrbitalFieldMap`).
5. **Typed Backend/AI Contract Layer (`src/lib/api/`):** Consumes **33 typed REST endpoints** (`/api/v1` across Auth, Demo, Farms, Fields, Analysis async polling/cancellation, Catalog cursor pagination, and Health) validated at runtime with **Zod**, supporting both `live` API transport and offline `fixture` sandbox fallback.

### Frontend Impact, Accessibility & Creative Decisions

- **Trilingual Farmer Accessibility:** Full runtime switching across **English (`en`)**, **French (`fr`)**, and **Arabic (`ar`) with RTL layout mirroring**, plus a **Plain-Language / Scientific Mode** toggle (`plainMode`).
- **Dual-Theme Liquid Glass UI & Progressive Fallback:** Light/Dark frosted HUD tokens tuned for contrast over sunlit satellite imagery, offline-safe self-hosted typography, and automatic geo-projected **SVG map fallback** when WebGL is unavailable (`canUseWebgl()`).
- **Epistemic Guardrails:** Surfacing `DEMO_PARCEL_UNVERIFIED` provenance banners, completeness scores, and pre-submit validation (`zod`, weight sum = 100%, disjoint target/excluded crops) ensures unstudied demo inputs are never mistaken for lab soil tests.

### Complete Frontend Stack Inventory (`package.json` & Repo Assets)

- **Core Dependencies:**
  - Framework & UI: `next` (`^15.5.4`), `react` (`^19.1.1`), `react-dom` (`^19.1.1`), `@phosphor-icons/react` (`^2.1.10`), `clsx` (`^2.1.1`)
  - Mapping & Geodesy: `maplibre-gl` (`^5.9.0`), `@turf/area`, `@turf/boolean-point-in-polygon`, `@turf/boolean-within`, `@turf/centroid`, `@turf/helpers` (`^7.3.1`)
  - State, Data & Validation: `zustand` (`^5.0.8`), `@tanstack/react-query` (`^5.90.0`), `zod` (`^3.25.0`)
- **Language, Styling, Lint & Test DevDependencies:**
  - `typescript` (`^5.9.2`), `tailwindcss` (`^4.1.13`), `@tailwindcss/postcss` (`^4.1.13`)
  - `eslint` (`^9.36.0`), `eslint-config-next` (`^15.5.4`), `@eslint/eslintrc` (`^3.3.1`)
  - `vitest` (`^3.2.4`), `@vitejs/plugin-react` (`^5.0.3`), `@testing-library/react` (`^16.3.0`), `@testing-library/jest-dom` (`^6.9.1`), `jsdom` (`^27.0.0`), `@playwright/test` (`^1.56.0`)
  - `@types/node` (`^22.18.0`), `@types/react` (`^19.1.16`), `@types/react-dom` (`^19.1.11`)
- **Self-Hosted Static Assets & Hosting:**
  - Self-hosted WOFF2 fonts (`src/app/fonts/`): **Plus Jakarta Sans** (`latin`, `latin-ext`), **IBM Plex Sans Arabic** (`400`, `500`, `600`, `700`), **JetBrains Mono** (`latin`, `latin-ext`)
  - Custom vector branding (`public/assets/logo.svg`, `src/app/icon.svg`) for **FELLAH TECH**
  - Edge static/web deployment: **Cloudflare Workers** (`workers.dev`)

---

## 4. Use of Super Intelligence (SI) \* *(Frontend Disclosure Snippet)*

Merge this frontend note with your Backend & AI Model SI statement, then select the matching checkboxes on the form:

- **Brand Compliance Verified:** No SI tools or frontend assets use, generate, or modify any NASA logos, flags, or mission identifiers; custom branding is **FELLAH TECH** (`public/assets/logo.svg`).
- **UI Transparency Verified:** Mock/fixture datasets and unstudied demo parcels display explicit UI banners (`DEMO_PARCEL_UNVERIFIED`) and agronomic disclaimers (`ProvenanceBanners.tsx`, `AnalysisOverviewCard.tsx`).
- **Short Mergeable Frontend SI Sentence:**
  > *"In the frontend, SI coding/writing assistants supported TypeScript/React UI development, trilingual i18n dictionaries (`EN/FR/AR`), unit/E2E test authoring, and documentation drafting; all NASA GIBS/Terrarium tile integrations, Turf.js geometry calculations, schema validations, and UI behaviors were reviewed and verified by the team."*

---

## 5. NASA Data \* *(Frontend Resources — Deduplicate Against Backend/AI When Pasting)*

Every NASA resource directly streamed as tiles or attributed in frontend (`src/lib/prototype/data.ts`, `src/lib/prototype/i18n.ts`, `src/components/guelma/GuelmaBorderEditorMap.tsx`), with official URLs verified **HTTP `200`**:

| Link Text | Link Url | Exact Frontend Usage |
| :--- | :--- | :--- |
| **NASA GIBS (Global Imagery Browse Services) WMTS** | `https://gibs.earthdata.nasa.gov/` | Live `WMTS epsg3857` tile service (`gibsUrl`) streaming MODIS, GLDAS, and IMERG rasters in 3D Simulator & CAD Editor. |
| **NASA MODIS (Terra Surface Reflectance, NDVI & Daytime LST)** | `https://terra.nasa.gov/about/terra-instruments/modis` | Streams `MODIS_Terra_CorrectedReflectance_TrueColor`, `MODIS_Terra_L3_NDVI_Monthly`, and `MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day` via GIBS. |
| **NASA GLDAS (Underground Root-Zone Soil Moisture)** | `https://ldas.gsfc.nasa.gov/gldas` | Streams `GLDAS_Underground_Soil_Moisture_Monthly` (`0.25°`) in 3D Simulator & CAD Border Editor (`SM` toggle). |
| **NASA GPM IMERG (Multi-Satellite Precipitation Rate)** | `https://gpm.nasa.gov/data/imerg` | Streams `IMERG_Precipitation_Rate` (`0.1°`) rainfall overlay in 3D Simulator. |
| **NASA POWER (Agroclimatology Normals Reference 1996–2025)** | `https://power.larc.nasa.gov/` | Source attribution for sub-regional Guelma climate normals (`CLIMATES`: annual rainfall, CV, frost days, `ET₀`, heat trends) used by client-side rotation evaluator. |
| **NASA SMAP (Soil Moisture Reference)** | `https://smap.jpl.nasa.gov/` | Scientific reference alongside GLDAS in 3D Inspector metrics/glossary (`GLDAS / SMAP 9 km`). |
| **NASA SRTM (Shuttle Radar Topography Mission Reference)** | `https://www.earthdata.nasa.gov/data/instruments/srtm` | Provenance attribution (`AWS Terrarium / SRTM 30 m grid`) for DEM terrain elevation/slope readouts. |

---

## 6. Space Agency Partner & Other Data *(Frontend Resources — Add Backend/AI Tools Below)*

All non-NASA basemaps, external tile services, geospatial libraries, and frontend frameworks used in `/home/unknown/fieldshift-planner/frontend` (listed URLs verified **HTTP `200`**):

| Link Text | Link Url | Role in Frontend |
| :--- | :--- | :--- |
| **Esri World Imagery (ArcGIS Online)** | `https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9` | Satellite basemap tiles (`server.arcgisonline.com/.../World_Imagery`) across all maps. |
| **AWS Open Data Terrain Tiles (Mapzen Terrarium DEM)** | `https://registry.opendata.aws/terrain-tiles/` | Serves `terrarium/{z}/{x}/{y}.png` elevation tiles for MapLibre 3D relief & browser RGB slope decoding. |
| **ISRIC SoilGrids (250 m Soil Property Reference)** | `https://soilgrids.org/` | Regional baseline `soc` and `pH` reference attribution (`SOILS` in `data.ts`) when field lab data is missing. |
| **MapLibre GL JS** | `https://maplibre.org/` | Open-source WebGL 2D/3D mapping engine (`^5.9.0`). |
| **MapLibre Demo Tiles Fonts** | `https://demotiles.maplibre.org/` | Supplies open PBF map glyphs (`demotiles.maplibre.org/font/...`) in CAD Border Editor. |
| **Turf.js** | `https://turfjs.org/` | Geodesic area, centroid, and polygon containment geometry (`^7.3.1`). |
| **Next.js** | `https://nextjs.org/` | App Router framework, build system, and API rewrite proxy (`^15.5.4`). |
| **React** | `https://react.dev/` | UI component runtime (`^19.1.1`). |
| **Tailwind CSS** | `https://tailwindcss.com/` | Styling & RTL layout utilities (`^4.1.13`). |
| **TanStack Query** | `https://tanstack.com/query` | Async API query/cache management (`^5.90.0`). |
| **Zod** | `https://zod.dev/` | Runtime form and OpenAPI schema validation (`^3.25.0`). |
| **Phosphor Icons** | `https://phosphoricons.com/` | Open-source UI icon library (`^2.1.10`). |

*Bundled/self-hosted frontend packages & open fonts (npm/local build assets, no extra external URL link required unless team wishes to add them):* `TypeScript` (`^5.9.2`), `Zustand` (`^5.0.8`), `clsx` (`^2.1.1`), `Vitest` (`^3.2.4`), `Playwright` (`^1.56.0`), `Testing Library`, `ESLint`, **Plus Jakarta Sans**, **IBM Plex Sans Arabic**, and **JetBrains Mono**.
