# FieldShift Frontend — Pixel-Perfect Redesign & Implementation Specification (`v4.1`)

> **Document Purpose:** This file is the single source of truth for transforming `/home/unknown/fieldshift-planner/frontend/` into the **FieldShift** botanical precision-agronomy interface matching [`media_1794688666510_26d21f97.jpg`](file:///home/unknown/.gemini/antigravity/brain/6f7fcbc5-d247-4ab1-9b30-a90b32ea367d/.user_uploaded/media_1794688666510_26d21f97.jpg) pixel-for-pixel, while preserving 100% of the verified `v3.2` API contracts, validation rules, provenance telemetry, i18n/RTL behavior, and E2E test workflows.

---

## Part 1 — Master Prompt & Hard Architectural Constraints

### 1.1 Role & Mission
You are a Senior Frontend Design Systems & Geospatial UI Engineer transforming `/home/unknown/fieldshift-planner/frontend/` into a pixel-faithful **FieldShift** agronomic workspace modeled directly after [`media_1794688666510_26d21f97.jpg`](file:///home/unknown/.gemini/antigravity/brain/6f7fcbc5-d247-4ab1-9b30-a90b32ea367d/.user_uploaded/media_1794688666510_26d21f97.jpg).

Your work must accomplish **all five objectives simultaneously**:
1. **New Brand & Replaceable Mark:** Establish **FieldShift** as an independent precision-agronomy brand with a minimal, standalone two-primitive geometric `<BrandLogo />` component and matching XML-valid `icon.svg` designed to be swapped effortlessly later.
2. **Legacy Theme & Interim Prototype Purge:** Remove every remaining NASA Space Apps visual artifact (`.sa-*`, `#07173F`, `#0042A6`, `#EAFE07`, `#2E96F5`, `#8E1100`, `#E43700`, `#0960E1`, `#0B1E4E`, `Fira Sans`, `Overpass`, `Mission Control` / `Orbital` copy), and unify all interim `#00291B` / `#137135` / `#F8FAF8` / `#E5E7EB` prototype classes across `frontend/src/` and `frontend/tests/` onto one cohesive `--fs-*` FieldShift token system. *(Root `/home/unknown/README.md` sits outside `frontend/` and is out of scope unless explicitly requested.)*
3. **Pixel-Faithful Dashboard Transformation:** Replace the prototype widgets on `/dashboard` (`NavigationSidebar`, `DashboardMap`, `FloatingTelemetry`, `FieldOverviewTable`, and right-column analytics cards) with a crisp `#EAECEB` / `#FFFFFF` / `#0B4B2E` botanical bento workspace matching the reference image's exact proportions, spacing, glassmorphism, typography, and data visualizations.
4. **Honest `v3.2` Data Binding (Zero Static Mockups):** Replace every prototype placeholder string (`North Field A1`, `East Field B2`, `Purwokerto`, `Corn`, `2.8`, `1,250L`, `87%`, `June 2026`, `Stocks/Bonds/Other`, `$830,451`, static `"NDVI"` stamps, fake `"100%"` donut hole text) with deterministic derivations from live `useAppStore`, React Query API/fixture responses, and pure typed selectors.
5. **100% Contract & E2E Preservation:** Keep every `ADR-0`–`ADR-9`, `schema-v5.0.json`, `Visual I/O §9.1–9.4`, `INPUT-01`–`INPUT-03`, RTL (`dir="rtl"`), and `NEXT_PUBLIC_API_MODE=fixture` behavior operational with zero functional regressions.

### 1.2 Hard Constraints (Non-Negotiable)
- **Light Botanical Mode is the Mandatory Default:** `theme` defaults strictly to `"light"` (`#EAECEB` canvas, `#FFFFFF` cards). A secondary `[data-theme="dark"]` palette may be toggled via the sidebar `Moon`/`Sun` button (`useAppStore.toggleTheme`), separate from `togglePlainMode`.
- **Preserve All `v3.2` Modules Untouched in Behavior:** Do **not** alter payload shapes, error codes, math, or contracts in `src/lib/schemas/index.ts`, `src/lib/validation/index.ts`, `src/lib/geo/guelma.ts`, `src/lib/api/client.ts`, `src/lib/api/endpoints.ts`, `src/lib/api/errors.ts`, or `src/lib/api/fixtures.ts`.
- **Single-Flight Auth Refresh:** All `401` retries go through `src/lib/api/client.ts`'s mutex calling `POST /api/v1/auth/refresh`; guest token stays persisted in `useAppStore`.
- **Zero Static Domain Values or `NaN` Leakage:** Every KPI, chart slice, calendar cell, and table row must trace back to `HealthResponse`, `FarmPublic`, `FieldPublic` / `FieldDetailPublic`, `AnalysisEnvelope.result.field_plans[0]` (`FieldPlan` containing `strategies[]`, `suggested_strategy_id`, `field_insights.{bare_field_periods, stress_periods, climate_trend_summary}`, `requested_crop_results[]`, and nested `strategy.explanation.evidence[]` / `requested_crop_results[].evidence[]`), `AnalysisSubmitRequest.priorities.weights`, or clean empty-state fallbacks (`"—"` / neutral `#E6E8E7` ring). Division by zero (`0 / 0`) MUST be guarded in every selector and SVG renderer.
- **No Uninstalled Chart/Drawing Libraries:** Do **not** assume or require `recharts`, `lucide-react`, or `terra-draw` (none are installed). Build all charts cleanly with custom responsive SVG + CSS, and use `@phosphor-icons/react` (plus custom SVG for `BrandLogo` and the weather sun-cloud emblem).
- **RTL-First Logical CSS:** Never use directional margin/padding/border/position utilities (`ml-*`, `mr-*`, `pl-*`, `pr-*`, `left-*`, `right-*`, `border-l`, `border-r`, `text-left`, `text-right`) for layout geometry. Always use logical Tailwind v4 utilities (`ms-*`, `me-*`, `ps-*`, `pe-*`, `start-*`, `end-*`, `border-s`, `border-e`, `text-start`, `text-end`).

---

## Part 2 — Verified Codebase Baseline & File Consolidation Map

### 2.1 Installed Dependencies (`frontend/package.json`)
- **Framework & Styling:** `next ^15.5.4` (App Router), `react ^19.1.1`, `react-dom ^19.1.1`, `tailwindcss ^4.1.13` (`@tailwindcss/postcss`), `clsx ^2.1.1`.
- **Geospatial:** `maplibre-gl ^5.9.0`, `@turf/area ^7.3.1`, `@turf/boolean-point-in-polygon ^7.3.1`, `@turf/boolean-within ^7.3.1`, `@turf/centroid ^7.3.1`, `@turf/helpers ^7.3.1`.
- **State, Queries, Forms, Icons:** `zustand ^5.0.8`, `@tanstack/react-query ^5.90.0`, `zod ^3.25.0`, `@phosphor-icons/react ^2.1.10`.
- **Testing:** `vitest ^3.2.4` (`jsdom`), `@playwright/test ^1.56.0`.

### 2.2 Verified On-Disk Baseline & Known Prototype Defects
Note on brand cleanup already completed: `BootSplash.tsx` and `SpaceAppsPatternOverlay.tsx` have **already been deleted** from `src/components/brand/` (do not recreate them or leave stale references to them). Note also that `select-field/page.tsx`, `farm-profile/page.tsx`, `comparison/page.tsx`, and `evidence/page.tsx` have already been partially updated in parallel to interim light classes (`#00291B`, `#137135`, `#F8FAF8`, `#E5E7EB`), though `farm-profile/page.tsx` and `evidence/page.tsx` retain illegible `text-white` / `text-[#E2ECFF]` hero titles against the light background and `evidence/page.tsx` still renders `"Mission tag:"`.

| Verification Command | Current Disk Baseline | Required Target Gate |
|---|---|---|
| `npm run typecheck` | Passes (`tsc --noEmit`, exit `0`) | Pass (`0` errors) |
| `npm run lint` | Passes (`eslint .`, exit `0`, `0` warnings) | Pass (`0` errors, `0` warnings) |
| `npm test` | Exits `0` (`11/11` pass: `validation.test.ts` `8/8`, `tests/unit/branding.test.ts` `3/3` — `branding.test.ts` still asserts a hardcoded `30+23+18+17+12 = 100` mock array, expects `brandTitle === "FIELD SHIFT"`, and omits `Fira`/`Overpass`/`MISSION CONTROL`/`CONTRÔLE MISSION`/`Mission tag:` checks) | Pass all `8` preserved + upgraded `branding.test.ts` (real `selectAllocationSlices()` assertions + dynamic forbidden-token checks) + new selector/SVG unit tests |
| Legacy SpaceApps grep (`sa-\|#07173F\|#0042A6\|#EAFE07\|#2E96F5\|#8E1100\|#E43700\|#0960E1\|#0B1E4E\|SpaceApps\|NASA\|Overpass\|Fira`) | Matches `src/app/globals.css` (`"Fira Sans"`, `"Overpass"`), `tests/e2e/fieldshift.spec.ts` (`#EAFE07`, `[7, 23, 63]` RGB), and `tests/unit/branding.test.ts` (`legacyPattern` literal) | Zero matches in `src/` and `tests/` |
| Interim prototype grep (`#00291B\|#04421B\|#137135\|#5FA87D\|#84E875\|#F8FAF8\|#003523\|#18664C\|#AFDA8A\|#D0A034\|#BC4C4B\|#151A06\|#EF4444\|#D97706\|#E2ECFF\|#072B1F\|#1B8A5F\|#98EA70\|#D4F9B3\|#EFFEDF`) | Matches `24` files across `src/app/` and `src/components/` | Unified onto `--fs-*` / AA-passing design tokens (`0` un-tokenized matches) |

**Specific Prototype Bugs Already Identified on Disk (Must Fix):**
1. **`src/app/icon.svg`:** Contains invalid React JSX comments (`{/* ... */}`) inside raw XML SVG; replace with `<!-- ... -->` and update colors to `#0B4B2E` / `#B8FCA7`.
2. **`src/app/layout.tsx` & `src/app/globals.css`:** Missing `next/font/google` imports (`Plus_Jakarta_Sans`, `IBM_Plex_Sans_Arabic`); `@theme inline` still lists `"Fira Sans"` and `"Overpass"`.
3. **`src/store/useAppStore.ts`:** Exposes `lang`, `plainMode`, `authMode`, `accessToken`, `refreshToken`, `guestToken`, `guestExpiresAt`, `user`, `activeFarmId`, `activeFieldId`, `activeAnalysisId`, `activeRequestId`, `bootSplashSeen`, and `simulateDegradedReplay` (persisted under `"fieldshift-planner-v32"`), but lacks `theme: "light" | "dark"`, `setTheme`, `toggleTheme`, and optional `activePriorityWeights` (for live chart reflection of `/farm-profile` weights; `clearSession()` must also reset `activePriorityWeights: null` so signed-out/guest sessions never inherit stale weights).
4. **`src/components/layout/AppShell.tsx`:** Uses non-RTL `pl-[60px]`, renders a sticky top `<header>` above `/dashboard` (breaking the flush top bento edge), and still carries `#F8FAF8`/`#00291B`/`#137135`/`#84E875`/`#E5E7EB` interim prototype styling.
5. **`src/components/brand/NavigationSidebar.tsx`:** Uses non-RTL `left-0` / `border-r`, wires `Moon` to `togglePlainMode`, includes dead `isMock` `/weather` & `/community` buttons, leaves `Gear`/`Info` non-interactive, uses AA-failing `bg-[#EF4444]` (`3.76:1` with white icon) on the sign-out button instead of `--fs-danger` (`#C04446`, `5.05:1`), renders a static cartoon SVG operator avatar instead of initials from `user?.full_name`, and needs alignment to `--fs-*` tokens while keeping the 3-control bottom stack (`Moon`/`Sun` toggle, coral-red circular sign-out/session button, circular initials avatar).
6. **`src/app/dashboard/page.tsx`:** Renders an extra white control bar above the bento grid, narrows the right rail to `272px`–`280px` instead of the `~68% / ~31%` reference split, and passes static strings (`"North Field A1"`, `"Corn"`, `"Purwokerto"`, `"$830,451"`) to widgets.
7. **`src/components/dashboard/DashboardMap.tsx`:** Renders an `opacity: 0.85` gradient `<div>` *over* MapLibre even when WebGL initializes (hiding real satellite tiles), draws an unprojected static `<svg>` polygon that drifts on pan/zoom, puts `Plant` horizontally inside a dark `bg-black/40` pill, uses horizontal `<DotsThree />` instead of vertical `<DotsThreeVertical />`, stamps fake `"NDVI"` text on the bottom-left inset, and renders a white pill bottom-right zoom bar instead of dark glass controls.
8. **`src/components/dashboard/FloatingTelemetry.tsx`:** Hardcodes `"North Field A1"`, `"Corn Plantation"`, `70%`, `"32%"`, `"2.8"`, `"2.3"`, `"1,250L"`, `"87%"`, `"Active"`, wraps the 3-column KPI row inside a `bg-white/5` box, and renders uneven `[19, 16, 14, 12]` dots across a `180°` arc instead of an aligned radial-spoke `~210°–220°` open-bottom horseshoe gauge.
9. **`src/components/dashboard/FieldOverviewTable.tsx`:** Hardcodes `DEFAULT_RECORDS` and `"June 2026"`, shows visible `"Action"` header text instead of `sr-only`, leaves toolbar buttons (`June 2026`, `Filter`, `⋮`) non-interactive, and uses `rounded-full` status pills with AA-failing `#FEF3C7`/`#D97706` (`2.86:1`) instead of `rounded-md` and `#FEF3C7`/`#B45309` (`4.51:1`).
10. **`WeatherWidget.tsx`, `ResourceDonutChart.tsx`, `WeeklyHeatmap.tsx`, `AnalyticsCard.tsx`:** Hardcode `Purwokerto` weather, a static mock donut (`30+23+18+17+12 = 100`) with interim `#003523`/`#18664C`/`#AFDA8A`/`#D0A034`/`#BC4C4B` fills, `"100%"` in the center hole, duplicate legend `%` values, and no inside-arc `%` labels or `2px` white gap strokes, static 7×6 green cells, and `"Stocks/Bonds/Other"` `$830,451` sparklines instead of rounded-top vertical bars.
11. **Secondary Routes & Shared Components:** `src/app/evidence/page.tsx`, `select-field/page.tsx`, `farm-profile/page.tsx`, `comparison/page.tsx`, `OrbitalFieldMap.tsx`, `UsdaTextureModal.tsx`, `ScoreRadarChart.tsx`, `AgronomicRiskCalendar.tsx`, `PrintableBrief.tsx`, `AuthModal.tsx`, and `ProvenanceBanners.tsx` use interim `#00291B` / `#137135` / `#E5E7EB` / `#F8FAF8` / AA-failing `#FEF3C7`+`#D97706` (`2.86:1`) tokens instead of unified `--fs-*` FieldShift variables; in addition, `farm-profile/page.tsx` (`<h1>`/`<p>`) and `evidence/page.tsx` (`<h1>`/`<p>`) have an invisible `text-white` / `text-[#E2ECFF]` title contrast bug against the light canvas, and `evidence/page.tsx` still displays `"Mission tag:"`.
12. **`src/lib/i18n/index.ts` & `src/app/evidence/page.tsx`:** Contain leftover `"MISSION CONTROL"`, `"CONTRÔLE MISSION"`, `"Mission Workspace"`, `"Mission tag:"`, and `"Orbital Map"` / `"Carte orbitale"` / `"خريطة قالمة المدارية"` copy, and lack localized keys for the new `/dashboard` analytics cards and telemetry rows.

### 2.3 Prototype-to-Target File Consolidation Matrix
Do **not** leave duplicate/dead prototype components behind. Perform exact replacements:

| Current File on Disk | Action | Target / Replacement File |
|---|---|---|
| `src/components/brand/FieldShiftLogo.tsx` | **Replace & Delete** | `src/components/brand/BrandLogo.tsx` (single-file replaceable mark) |
| `src/components/dashboard/WeatherWidget.tsx` | **Replace & Delete** | `src/components/dashboard/LocationClimateCard.tsx` |
| `src/components/dashboard/ResourceDonutChart.tsx` | **Replace & Delete** | `src/components/dashboard/AllocationDonutCard.tsx` |
| `src/components/dashboard/WeeklyHeatmap.tsx` | **Replace & Delete** | `src/components/dashboard/AgronomyHeatmapCard.tsx` |
| `src/components/dashboard/AnalyticsCard.tsx` | **Replace & Delete** | `src/components/dashboard/ScenarioBarsCard.tsx` |
| *(New)* | **Create** | `src/components/dashboard/DotMatrixGauge.tsx` |
| *(New)* | **Create** | `src/lib/telemetry/dashboardSelectors.ts` |
| *(New)* | **Create** | `tests/unit/dashboardSelectors.test.ts` |
| `NavigationSidebar.tsx`, `AppShell.tsx`, `DashboardMap.tsx`, `FloatingTelemetry.tsx`, `FieldOverviewTable.tsx`, `dashboard/page.tsx` | **Refactor in Place** | Upgraded in existing paths |
| `evidence/page.tsx`, `comparison/page.tsx`, `farm-profile/page.tsx`, `select-field/page.tsx`, `PrintableBrief.tsx`, `AgronomicRiskCalendar.tsx`, `ScoreRadarChart.tsx`, `OrbitalFieldMap.tsx`, `AuthModal.tsx`, `UsdaTextureModal.tsx`, `ProvenanceBanners.tsx` | **Align Visual Tokens** | Audit and convert all legacy/interim styles to unified `--fs-*` FieldShift tokens |

*(Note: `BootSplash.tsx` and `SpaceAppsPatternOverlay.tsx` were already deleted from `src/components/brand/`.)*

---

## Part 3 — Brand Identity, Replaceable Logo & Empirical Design System

### 3.1 Brand Identity & Minimal Replaceable Logo
- **Brand Name:** **FieldShift** (use `FieldShift` across navigation, print header, modals, and metadata; zero `ARD ·`, `NASA`, `Space Apps`, `Mission Control`, or `Orbital` copy).
- **Standalone Logo (`src/components/brand/BrandLogo.tsx`):**
  - Renders inside a `32×32px` container at the top of `NavigationSidebar` (also reusable in `AuthModal` and `PrintableBrief`).
  - Keep it deliberately simple and self-contained inside **one file** so swapping a final logo later requires changing only `BrandLogo.tsx` and `src/app/icon.svg`:
    - `<svg viewBox="0 0 32 32" className="h-8 w-8" aria-hidden="true">`
    - Primitive 1: Clean rounded-corner tilted parcel frame or terraced field arc in `--fs-primary` (`#0B4B2E` on light, `#B8FCA7` on dark surfaces).
    - Primitive 2: Crisp geometric sprout/leaf stem in `#157853` / `#84E875` (`strokeLinecap="round"`).
  - Supports optional `size?: number` and `variant?: "mark" | "lockup"` (for `PrintableBrief` / `AuthModal` headers).
- **App Icon (`src/app/icon.svg`):**
  - Pure XML SVG (`<!-- FieldShift placeholder geometric mark -->`), `#0B4B2E` rounded background (`rx="8"`) with `#B8FCA7` contour-leaf mark. Zero JSX `{/* ... */}` syntax.

### 3.2 Empirical Color Tokens (Calibrated to `media_1794688666510_26d21f97.jpg`)
Define semantic CSS variables in `src/app/globals.css` under `:root` (default Light Mode) and `[data-theme="dark"]` (secondary Dark Mode):

| Semantic Token | Light Mode (Default, Reference Image) | Secondary Dark Mode (`[data-theme="dark"]`) | Usage |
|---|---|---|---|
| `--fs-canvas` | `#EAECEB` | `#0D1410` | App viewport outer canvas |
| `--fs-surface` | `#FFFFFF` | `#141E19` | Sidebar, bento cards, table surface, search pill |
| `--fs-surface-muted` | `#F6F7F6` | `#1B2721` | Weather sub-trays, segmented pill track, table header bar |
| `--fs-border` | `#E6E8E7` | `#26352D` | 1px card strokes, hairline dividers |
| `--fs-ink` | `#141916` | `#EEF4F0` | Headings, active metric values, body text |
| `--fs-ink-muted` | `#6B736E` | `#A4B3AA` | Card subtitles, inactive rail icons, legend labels |
| `--fs-ink-subtle` | `#5E6762` | `#92A198` | Axis labels, timestamps, muted metadata (`>= 4.9:1` AA on light canvas/surface and `>= 6.3:1` on dark surface) |
| `--fs-primary` | `#0B4B2E` | `#157853` | Active rail icon circle, checked checkbox, primary button (`>= 5.46:1` with `#FFFFFF` in both modes) |
| `--fs-primary-hover` | `#093D25` | `#116244` | Button hover state |
| `--fs-accent-mint` | `#B8FCA7` | `#B8FCA7` | Active rail icon stroke inside `#0B4B2E` pill |
| `--fs-danger` | `#C04446` | `#C04446` | Coral-red sidebar session exit button (`5.05:1` with `#FFFFFF`), error borders (`#F87171` for dark-mode outlined text/borders) |
| `--fs-chart-forest` | `#0B4B2E` | `#0F5C39` | Donut slice 1 (Forest, `#FFFFFF` label text: `10.19:1` light / `8.05:1` dark) |
| `--fs-chart-emerald` | `#157853` | `#157853` | Donut slice 2 (Emerald), secondary active bar / heatmap dark step (`5.46:1` with `#FFFFFF`) |
| `--fs-chart-lime` | `#B8F088` | `#9EE06E` | Highlight bar / donut slice 3 (Lime), gauge active dots (`#141916` label text: `13.43:1` light / `11.30:1` dark) |
| `--fs-chart-amber` | `#F2A93B` | `#E59D2C` | Donut slice 4 (Warm Amber/Gold, `#141916` label text: `8.91:1` light / `7.79:1` dark) |
| `--fs-chart-coral` | `#C04446` | `#C04446` | Donut slice 5 (Coral Red, `#FFFFFF` label text: `5.05:1`, aligned with `--fs-danger`) |
| `--fs-chart-sage` | `#227961` / `#7FB69E` / `#B8D9CE` | `#246954` / `#55947B` / `#85B4A3` | Baseline comparison bars, avatar borders & neutral secondary series (`#FFFFFF` on `#227961`/`#246954`; `#141916` on `#7FB69E`/`#B8D9CE`/`#55947B`/`#85B4A3`) |
| `--fs-glass-telemetry` | `rgba(28, 34, 18, 0.86)` | `rgba(18, 24, 16, 0.90)` | `FloatingTelemetry` card (`backdrop-blur-[14px]`, border `rgba(255,255,255,0.14)`) |
| `--fs-glass-control` | `rgba(22, 26, 18, 0.82)` | `rgba(14, 18, 12, 0.88)` | Bottom-right map controls (`backdrop-blur-[10px]`, border `rgba(255,255,255,0.14)`) |

**Status Pill Semantics (`rounded-md`, `6px` radius — NOT `rounded-full`):**
- **Healthy / Recommended / Valid:** `bg-[#E7F6EC] text-[#147A42]`
- **Moderate / Stable / Pending:** `bg-[#FEF3C7] text-[#B45309]`
- **Critical / Unverified / Error:** `bg-[#FEE2E2] text-[#B91C1C]`

**Parcel Thermal/Stress Overlay Gradient Stops (rendered inside MapLibre polygon fill/raster layers):**
- Cool healthy vegetation `#3E6E3A` -> Moderate warm gold `#B89B5E` -> Elevated stress amber `#C97A3C` -> Peak heat/stress terracotta `#A85432` (at `0.45–0.65` translucency over crisp ESRI satellite imagery).

### 3.3 Typography & Scale (`next/font/google`)
Configure in `src/app/layout.tsx`:
- `Plus_Jakarta_Sans({ subsets: ["latin"], weight: ["400", "500", "600", "700"], variable: "--font-jakarta", display: "swap" })`
- `IBM_Plex_Sans_Arabic({ subsets: ["arabic"], weight: ["400", "500", "600", "700"], variable: "--font-arabic", display: "swap" })`
- Map both `--font-sans` and `--font-heading` in `globals.css` (`@theme inline`) to `var(--font-jakarta), var(--font-arabic), system-ui, sans-serif`, and override `[dir="rtl"]` font priority to `var(--font-arabic), var(--font-jakarta), system-ui, sans-serif`.
- Enforce `tabular-nums` (`font-variant-numeric: tabular-nums`) on **all** percentages, coordinates, scores, areas, rainfall numbers, and table cells.

---

## Part 4 — Pixel-Accurate `/dashboard` 3-Region Bento & Honest `v3.2` Binding

### 4.1 Overall Bento Grid Proportions & Chrome Placement
Match [`media_1794688666510_26d21f97.jpg`](file:///home/unknown/.gemini/antigravity/brain/6f7fcbc5-d247-4ab1-9b30-a90b32ea367d/.user_uploaded/media_1794688666510_26d21f97.jpg) layout proportions (`53px : 569px : 262px` within the `901px` reference frame):
- **Desktop (`>= 1024px`) & Responsive Shell — NO sticky top `<header>` on `/dashboard`:**
  - `NavigationSidebar` is fixed horizontally at the bottom on `< 768px` (`fixed inset-x-0 bottom-0 h-16`) and switches at `md:` (`>= 768px`) to fixed `start-0 inset-y-0 w-16` (`64px`) (`bg-[var(--fs-surface)] border-t md:border-t-0 md:border-e border-[var(--fs-border)] z-40`).
  - `<main>` has `pb-20 md:pb-0 md:ps-16 min-h-screen bg-[var(--fs-canvas)]` (never unconditional `ps-16`, so mobile `390×844` has zero dead left gutter and zero bottom-bar overlap across `/dashboard` and all secondary routes).
  - Inner `/dashboard` wrapper uses `p-3 sm:p-4 gap-4 grid grid-cols-1 lg:grid-cols-[minmax(0,68fr)_minmax(340px,31fr)] max-w-[1600px] mx-auto items-start`, with `min-w-0` on both left and right column wrappers so wide tables scroll internally (`overflow-x-auto`) without expanding the document past `390px`.
  - Crucially: the top edge of `DashboardMap` and the top edge of the Search Pill align **flush (`y = 0` inside the `16px` canvas padding)**—no global top bar, warning bar, or utility banner sits above them.
- **Secondary Routes (`/select-field`, `/farm-profile`, `/comparison`, `/evidence`):**
  - Render a clean slim light-mode `<header>` (`h-14 bg-[var(--fs-surface)] border-b border-[var(--fs-border)] px-6 flex items-center justify-between`) with route title/breadcrumb, `EN | FR | عربي` (`lang-en`, `lang-fr`, `lang-ar`), `plain-mode-toggle`, and `auth-modal-trigger`.
- **Responsive Navigation Rail (`< 768px` -> `>= 768px` Single DOM `<nav>`):**
  - Implement `NavigationSidebar` as **one single responsive `<nav>` element** (avoid duplicating mobile and desktop `<nav>` trees so no `data-testid` or `<Link>` ever duplicates in the DOM): on `< 768px` it docks horizontally at the bottom (`fixed inset-x-0 bottom-0 h-16 px-2 flex-row items-center justify-around border-t overflow-hidden`), and at `md:` (`>= 768px`) it switches seamlessly to the `64px` vertical `start-0` rail (`md:inset-x-auto md:inset-y-0 md:start-0 md:w-16 md:h-screen md:px-0 md:py-4 md:flex-col md:justify-between md:border-t-0 md:border-e`). On `< 768px`, keep the 5 route links (`w-10 h-10` on mobile, `md:w-11 md:h-11` on desktop), Theme toggle, Coral-red Session/SignOut trigger, and Settings/Avatar controls compactly fitted (`<= 360px` total width) while hiding `BrandLogo`, horizontal hairline dividers, and the `Info` shortcut (`hidden md:flex`) so the horizontal bar never overflows `390px`. All 5 real route links (`a[href="/dashboard"]:visible`, `a[href="/select-field"]:visible`, `a[href="/farm-profile"]:visible`, `a[href="/comparison"]:visible`, `a[href="/evidence"]:visible`) remain visible across all viewports.

### 4.2 Region 1 — Left Icon Rail (`src/components/brand/NavigationSidebar.tsx`)
1. **Top Brand Slot:** `<Link href="/dashboard" aria-label="FieldShift Home">` containing `<BrandLogo size={32} />` followed by a subtle hairline divider (`w-8 h-px bg-[var(--fs-border)]`).
2. **Primary Navigation Group (5 real routes ONLY — remove dead `isMock` `/weather` & `/community` buttons):**
   - `/dashboard` (`SquaresFour` icon)
   - `/select-field` (`MapPin` / `MapTrifold` icon)
   - `/farm-profile` (`SlidersHorizontal` / `Plant` icon)
   - `/comparison` (`ChartBar` icon)
   - `/evidence` (`FileText` icon)
   - Active state: `w-10 h-10 rounded-full bg-[var(--fs-primary)] text-[var(--fs-accent-mint)] flex items-center justify-center shadow-xs`.
   - Inactive state: `w-10 h-10 rounded-full text-[var(--fs-ink-muted)] hover:bg-[var(--fs-surface-muted)] hover:text-[var(--fs-ink)] flex items-center justify-center transition-colors`.
   - Tooltip: `hidden md:group-hover:block md:group-focus-visible:block` appearing on `start-full ms-2.5` (RTL-safe; suppressed on `< 768px` horizontal mobile bar so tooltips never clip past `390px`).
3. **Middle Divider + Utility Popovers:**
   - Subtle divider (`w-8 h-px bg-[var(--fs-border)]`).
   - `Gear` button (`aria-label="Workspace settings"`): opens a clean anchored popover (`start-full bottom-28 ms-2`) with quick toggles for Language (`EN`/`FR`/`AR`), `Plain Agronomy Mode`, and `Re-run Demo`. *(Avoid duplicating global `data-testid` values here so Playwright strict-mode locators stay unique.)*
   - `Info` button (`aria-label="Data provenance"`): opens a compact provenance popover showing active `dataset_version_used` / `ml_engine_version`, `apiMode`, health status, and direct link to `/evidence`.
4. **Bottom 3-Control Stack (matching reference screenshot bottom rail):**
   - **Theme Toggle (`Moon` / `Sun`, `data-testid="theme-toggle"`):** calls `useAppStore.toggleTheme()` (`light` <-> `dark`) — **never** `togglePlainMode`.
   - **Coral-Red Circular Session / Sign-Out Trigger (`w-7 h-7 rounded-full bg-[#C04446] hover:bg-[#A63537] text-white shadow-xs` with `<SignOut className="rtl:rotate-180" />` / `<ArrowLeft className="rtl:rotate-180" />` icon):** positioned directly between the theme toggle and the avatar, matching the reference image's coral-red circular exit control (`5.05:1` white-icon contrast). Calls `clearSession()` (or opens `AuthModal` if `authMode === "none"`), with localized `aria-label` (`Sign Out` / `Session`).
   - **Operator Avatar Trigger (`data-testid="sidebar-auth-trigger"`):** `36×36px` rounded-full badge (`bg-[#E7F6EC] text-[#0B4B2E] font-semibold text-xs border border-[#B8D9CE]`) rendering initials from `user?.full_name` (or `"G"` when `authMode === "guest"`, `"—"` when `authMode === "none"`) that opens `AuthModal`. Never render a static hardcoded cartoon face SVG.

### 4.3 Region 2 — Center Primary Workspace

#### 2A. Satellite Parcel Hero (`src/components/dashboard/DashboardMap.tsx`)
- **Container:** `relative w-full h-[430px] xl:h-[520px] rounded-[20px] overflow-hidden bg-[#263022] border border-[var(--fs-border)]`.
- **Live MapLibre Satellite Canvas (Fix existing tile-blocking bug):**
  - Initialize `maplibregl.Map` with ESRI World Imagery raster source (`https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`). When `activeField?.location.boundary` is non-null, render its GeoJSON polygon and smoothly `fitBounds`; when `activeField?.location.boundary` is `null` (as in demo parcel `F1`), derive a clean `area_hectares`-scaled GeoJSON polygon centered on `[activeField.location.longitude, activeField.location.latitude]` (falling back to `GUELMA_DEFAULT_CENTER` when no field is loaded) so every parcel—including `F1`—renders a sharp parcel outline on both the satellite map and inset minimap.
  - **Delete the unconditional `opacity: 0.85` gradient overlay** that currently covers `<div ref={mapContainerRef} />`. Render the SVG fallback canvas **only** if WebGL fails (`mapError === true`), handling synchronous `new maplibregl.Map()` throws, MapLibre WebGL/context `error` events, and `webglcontextcreationerror` on the map container (without falsely hiding a live WebGL map on transient offline tile fetch errors).
  - **Geo-Projected Parcel & Thermal Stress Layers (`map.addSource("parcel-polygon")`):**
    - Polygon fill layer (with multi-stop thermal/stress shading when stress overlay is active) + crisp **dashed white outline** (`line-color: "#FFFFFF"`, `line-width: 2`, `line-dasharray: [4, 4]`, `line-opacity: 0.95`).
    - Never use an unprojected screen-fixed `<svg>` polygon overlay when MapLibre is active—pan/zoom must keep the white dashed parcel boundary locked 1:1 to earth coordinates.
- **Borderless Centered Parcel Identity Stack (over parcel centroid):**
  - Positioned cleanly at the projected parcel screen center (`pointer-events-none select-none flex flex-col items-center text-center gap-0.5 drop-shadow-[0_2px_6px_rgba(0,0,0,0.75)]`):
    - White `<Plant size={20} weight="fill" className="text-white" />` stacked vertically above the text
    - Parcel name (`text-[15px] font-semibold text-white leading-tight`, e.g., `activeField?.field_name ?? "Select or Launch Parcel"`)
    - Area / Crop subtitle (`text-[12px] text-white/90 tabular-nums`, e.g., `${activeField.area_hectares.toFixed(1)} ha · ${activeCropName}`).
  - **No `bg-black/40` rectangle background** behind this label!
- **Top-Left Area:** Clean, completely unobstructed satellite imagery (no badges, chips, or banners overlapping the top-left edge).
- **Top-Right Action Controls (`top-4 end-4 flex items-center gap-2 z-20`):**
  - `Export` crisp white button (`h-9 px-3.5 rounded-xl bg-white text-[#141916] text-[12px] font-semibold shadow-sm border border-[var(--fs-border)] hover:bg-[#F6F7F6] flex items-center gap-1.5`): downloads active GeoJSON / opens `/comparison#print` export options.
  - `⋮` (`DotsThreeVertical`) white square-rounded `36×36px` icon button (`rounded-xl bg-white text-[#141916] border border-[var(--fs-border)] shadow-sm`): opens a compact dropdown menu (`Switch Parcel`, `Toggle Stress Shading`, `Fit Parcel Bounds`, `Edit Boundary -> /select-field`).
  - Do **not** place language buttons, `Aa`, or `FIXTURE MODE` badges inside top-right map controls.
- **Bottom-Left Minimap Inset (`bottom-4 start-4 w-16 h-16 rounded-xl overflow-hidden border-2 border-white/90 shadow-md z-20`):**
  - Interactive `64×64px` toggle button (`aria-label="Toggle basemap layer"`): toggles between Satellite Imagery and Clean Terrain/Contour view on click. Render a genuine miniature aerial/terrain swatch—**never** stamp fake `"NDVI"` text on top of it.
- **Bottom-Right Dark-Glass Map Controls (`bottom-4 end-4 flex flex-col gap-1.5 z-20`):**
  - `Expand` button (`36×36px`, `rounded-xl bg-[var(--fs-glass-control)] backdrop-blur-md text-white border border-white/15`, expands map height or toggles fullscreen panel).
  - Connected vertical `+` / `-` zoom stack (`w-9 rounded-xl bg-[var(--fs-glass-control)] backdrop-blur-md text-white border border-white/15 divide-y divide-white/15 overflow-hidden`), calling `map.zoomIn()` / `map.zoomOut()`.
  - `Locate` (`NavigationArrow` / `Crosshairs`) button (`36×36px`, `rounded-xl bg-[var(--fs-glass-control)] backdrop-blur-md text-white border border-white/15`), re-centering onto active parcel bounds.

#### 2B. Floating Dark-Olive Telemetry Card & Horseshoe Dot-Matrix Gauge (`FloatingTelemetry.tsx` + `DotMatrixGauge.tsx`)
- **Position:** Anchored at `top-14 end-3 sm:top-16 sm:end-16 z-20` inside the map frame (with `min-h-[380px] sm:min-h-[430px]` on the map container so top-right `Export`/`⋮`, bottom-left inset minimap, and bottom-right zoom/locate controls stay completely clear on both `1440×900` and `390×844`). Dismissible via `X` button; when closed, show a compact `"Telemetry"` dark-glass reopen pill at `top-14 end-3 sm:top-16 sm:end-4`.
- **Surface:** `w-[224px] sm:w-[238px] max-w-[calc(100%-1.5rem)] rounded-[16px] bg-[var(--fs-glass-telemetry)] backdrop-blur-[14px] border border-white/14 p-3.5 sm:p-4 text-white shadow-xl`.
- **Header:** Truncated `activeField?.field_name` (`text-[13px] font-semibold`) + localized active crop/strategy subtitle (`text-[11px] text-white/70`) + dismiss `X` button.
- **`DotMatrixGauge.tsx` (Open-Bottom Horseshoe Arc with 4 Aligned Radial-Spoke Rings):**
  - Match [`media_1794688666510_26d21f97.jpg`](file:///home/unknown/.gemini/antigravity/brain/6f7fcbc5-d247-4ab1-9b30-a90b32ea367d/.user_uploaded/media_1794688666510_26d21f97.jpg) **open-bottom horseshoe / semi-circular arc** (`~210°–220°` sweep, NOT a closed `360°` ring!):
    - `<svg viewBox="0 0 180 124" className="w-[176px] h-[120px] mx-auto overflow-visible">` centered around `(cx = 90, cy = 78)`.
    - Sweep clockwise from lower-left (`startDeg = -197.5°`) over the top (`-90°`) to lower-right (`endDeg = +17.5°`, total `215°` sweep), leaving the bottom open!
    - **28 aligned radial spokes** (`step = 215° / 27`) × **4 concentric dot rings** (`r = 44, 52, 60, 68`) = **112 aligned polar ticks** (`circle r="2.2"` or aligned radial pill dots).
    - Pure clamping helper: `safeScore = clampGaugeScore(activeStrategy?.scores.priority_fit)`.
    - When `safeScore !== null`: activate the first `Math.round((safeScore / 100) * spokes)` radial spokes using a smooth `#58A070 -> #C0E8A0` gradient across active spokes; render unfilled ticks in crisp bright `#D7DAD1` at `0.85` opacity so the inactive portion remains clearly visible against dark olive glass.
    - Center lower cradle readout (`y ≈ 66..102` inside the open horseshoe bottom): `{safeScore}%` (`24px font-bold tabular-nums leading-none`) + `"Health Score"` (`11px text-white/75 mt-1`).
    - When `safeScore === null` (`activeAnalysis === null`): all ticks render muted `rgba(215, 218, 209, 0.25)` and the cradle displays `"—"` + `"Pending Run"`.
- **Boxless 3-Column Bottom KPI Row (`grid grid-cols-3 gap-2 pt-2 text-center` — NO `bg-white/5` nested card):**
  - Column 1: `Soil pH` -> `activeField?.soil.soil_ph !== null && activeField?.soil.soil_ph !== undefined ? activeField.soil.soil_ph.toFixed(1) : "—"`
  - Column 2: `Rain / yr` -> extracted and compactly formatted from `activeStrategy?.explanation.evidence` (`parameter === "precipitation"`, stripping `/year` / `/an` to `"312 mm"` so the 3-column KPI never wraps) or `"—"`
  - Column 3: `Area (ha)` -> `activeField ? activeField.area_hectares.toFixed(1) : "—"`
- **Horizontal Divider + 3-Row Key-Value Telemetry Breakdown (`border-t border-white/12 mt-3 pt-2.5 space-y-1.5 text-[11px]`):**
  - Matches the reference image's bottom key-value breakdown with green status dot, mapped strictly to real `v3.2` data (zero hardcoded `"1,250L"` / `"87%"` / `"Active"`):
    1. `Irrigation` -> `activeField ? `${IRRIGATION_SYSTEM_LABELS[lang][activeField.water.irrigation_system]}` : "—"` (render value with `truncate max-w-[110px]` + `title` attribute so long localized strings never expand or wrap the `224–238px` card)
    2. `Water Efficiency` -> `activeStrategy ? `${Math.round(activeStrategy.scores.water_efficiency)}%` : "—"`
    3. `Parcel Status` -> status indicator dot + localized status (`bg-[#4ADE80]` + `"Verified"` when `!activeField.is_unverified_demo_parcel`, `bg-[#FBBF24]` + `"Unstudied Demo"` when `activeField.is_unverified_demo_parcel === true`, or muted dot + `"—"` when unset).

#### 2C. Provenance Banners (`WarningsBanner` & `DegradedReplayBanner`)
- Render cleanly **between** `DashboardMap` and `FieldOverviewTable` (in normal document flow with `gap-3`), preserving exact E2E selectors `warning-DEMO_PARCEL_UNVERIFIED` and `degraded-mode-banner`. This guarantees banners never push the Map Hero out of horizontal alignment with the right Search Pill.

#### 2D. Field Overview Table (`src/components/dashboard/FieldOverviewTable.tsx`)
- **Card:** `rounded-[20px] bg-[var(--fs-surface)] border border-[var(--fs-border)] p-5`.
- **Toolbar (Match all 3 right toolbar buttons in reference image):**
  - `start`: Heading (`Field Overview`, `15px font-semibold text-[var(--fs-ink)]`).
  - `end`:
    1. Interactive **`Season Scope`** button with trailing `<Calendar />` icon (`All Seasons`, `Spring`, `Autumn`, `Winter` — **never** static `"June 2026"`).
    2. Interactive **`Filter`** button with trailing `<CaretDown />` icon (toggles Status filter: `All`, `Healthy`, `Moderate`, `Unverified`).
    3. Interactive **`⋮`** (`<DotsThreeVertical />`) icon button opening table actions (`Reset Filters`, `Export JSON`, `Add Parcel -> /select-field`).
- **Table Header (`bg-[var(--fs-surface-muted)] rounded-lg` — 7 visible columns + `sr-only` Actions column matching reference image):**
  1. Select-all checkbox (`w-4 h-4 rounded border border-[#D0D5D2] checked:bg-[var(--fs-primary)] checked:border-[var(--fs-primary)]`)
  2. `Field Zone` (`text-start text-[12px] font-medium text-[var(--fs-ink-muted)]`)
  3. `Crop Type` (for the active field row, `activeStrategy?.seasons[0]?.crop_name` or `activeFieldDetail?.crop_history?.at(-1)?.crop_name` or `"—"`; note `FieldPublic` from `listFields()` has NO `crop_history` field—only `FieldDetailPublic` from `getField()` exposes `crop_history`—so never access `field.crop_history` directly on `FieldPublic[]` items)
  4. `Status`
  5. `Water / Moisture` (`WATER_AVAILABILITY_LABELS[lang][field.water.availability]`, `water_efficiency` %, or `soil_moisture_surface` if present in evidence)
  6. `Climate / Elevation` (`${field.area_hectares.toFixed(1)} ha` · `${field.elevation_m !== null ? `${field.elevation_m} m` : "—"}`, or `t2m` if present in future `5.x` evidence for the active row)
  7. `Stage / Horizon` (active season/year from `activeStrategy.seasons[0]` e.g., `"Spring 2027"` or `"Pending Run"`)
  8. Action column: `<th scope="col" className="w-10"><span className="sr-only">Actions</span></th>` (visually blank header cell matching reference screenshot, while accessible to screen readers!).
- **Table Rows (`<= 5` visible rows per page):**
  - Strictly bound to `FieldPublic[]` (`fieldsQuery.data.items`) + active `FieldPlan` + right-column Search Pill query. Clicking a row selects `setActiveFieldId(field.field_id)` and syncs the map & telemetry popover.
  - Status badges strictly use **`rounded-md px-2.5 py-0.5 text-[11px] font-medium`** (6px corners matching reference, NOT `rounded-full`):
    - `Healthy` (`!field.is_unverified_demo_parcel && priorityFit >= 70`): `bg-[#E7F6EC] text-[#147A42]`
    - `Moderate` (`!field.is_unverified_demo_parcel && (priorityFit === null || priorityFit >= 45)`): `bg-[#FEF3C7] text-[#B45309]`
    - `Unverified` (`field.is_unverified_demo_parcel || (priorityFit !== null && priorityFit < 45)`): `bg-[#FEE2E2] text-[#B91C1C]`
  - `⋮` row action menu: `Focus on Map`, `Edit Profile (/farm-profile)`, `Compare (/comparison)`, `View Evidence (/evidence)`.

#### 2E. Slim Workspace Utility & E2E Bar (Bottom of Center Column, below `FieldOverviewTable`)
To keep **zero** visual clutter on the hero map top edge AND keep every Playwright `data-testid` immediately discoverable on `/dashboard` without needing hidden menus:
- Render a compact, subtle `px-2 py-1.5 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--fs-ink-subtle)]` footer strip beneath `FieldOverviewTable` (using `--fs-ink-subtle` `#5E6762` / `#92A198`, passing WCAG AA `4.93:1` directly over the `#EAECEB` canvas, unlike `#6B736E` at `4.11:1`) hosting **unique (single-instance)** E2E/utility triggers:
  - Left: `fixture-mode-pill` (`API: FIXTURE` / `LIVE`) + `toggle-degraded-preview` button + `quick-launch-demo` button (visible whenever `authMode === "none"`, never duplicated elsewhere on the page so Playwright strict-mode locators match exactly 1 element) + compact guest quota/claim pill when `authMode === "guest"` (preserving guest remaining-run feedback and `"Save / Claim Account"` trigger since `/dashboard` removes the top `<header>`).
  - Right: compact `plain-mode-toggle`, `EN` / `FR` / `AR` buttons (`lang-en`, `lang-fr`, `lang-ar`), and `auth-modal-trigger` (`Guest` / `Sign in`) — rendered here **only** on `/dashboard` (on secondary routes, the slim `<header>` owns those testids; Settings popover in `NavigationSidebar` avoids reusing the same `data-testid` values).

---

### 4.4 Region 3 — Right Analytics Column (`src/components/dashboard/`)

All 5 right-rail cards share `gap-3.5` vertical spacing and clean `rounded-[20px] bg-[var(--fs-surface)] border border-[var(--fs-border)]` geometry. All data transformations live in pure unit-tested functions inside **`src/lib/telemetry/dashboardSelectors.ts`**.

#### 3A. Search Pill (Top of Right Rail)
- `<div className="h-11 rounded-full bg-[var(--fs-surface)] border border-[var(--fs-border)] px-4 flex items-center gap-2.5">` (**full `rounded-full` capsule**, matching reference!).
- MagnifyingGlass (`16px`) + bound `<input type="search">` filtering `FieldOverviewTable` parcels, crops, and evidence items live with clear (`X`) button.

#### 3B. `LocationClimateCard.tsx` (Replaces `WeatherWidget.tsx`)
- **Top Location Line:** `<MapPin />` + region title (`activeField ? `${activeField.field_name} · Guelma` : "Guelma, Algeria"` — zero hardcoded `Purwokerto`).
- **Middle Hero Split (`mt-2.5 flex items-center justify-between gap-3` — Match Reference Left-Hero / Right-Condition Orientation):**
  - **Left / Start (`text-start`):** Large bold hero numeric readout (`text-3xl font-bold tracking-tight text-[var(--fs-ink)] tabular-nums`), derived via `selectLocationClimateMetrics(analysisResult, fieldPlan, activeStrategy, activeField)` (`t2m` if present in `5.x` evidence, otherwise annual `precipitation` e.g. `312 mm`, or `"—"` when unavailable).
  - **Right / End (`text-end`):** Custom minimalist `<svg viewBox="0 0 64 48">` warm amber sun + soft cloud emblem alongside condition headline (`text-xs font-semibold text-[var(--fs-ink)]`, e.g., `"Dry Quantile"` / `"Local Baseline"`) and muted localized date + dataset line (`Intl.DateTimeFormat(lang)` from `analysisResult?.generated_at` + `dataset_version_used`, `text-[11px] text-[var(--fs-ink-muted)]`).
- **Bottom 3-Column `divide-x` Metrics Tray (`mt-3 grid grid-cols-3 divide-x divide-[var(--fs-border)] rounded-xl bg-[var(--fs-surface-muted)] py-2.5 text-center`):**
  - Priority-ordered extraction from `strategy.explanation.evidence` (and `requested_crop_results[].evidence`) via `selectLocationClimateMetrics(analysisResult, fieldPlan, activeStrategy, activeField)`:
    1. `Water` (`rh2m` if present, else `water_availability` / `activeField?.water.availability` e.g. `Moderate`)
    2. `Anomaly` (`precipitation_anomaly`, e.g., `-18%`)
    3. `Soil pH` (`wind_2m` if present, else `activeField?.soil.soil_ph?.toFixed(1)` or `"—"`)
    - **Never** invent fake `"26°C"`, `"35%"`, or `"8m/s"` values when those parameters are absent from evidence!

#### 3C. `AllocationDonutCard.tsx` (Replaces `ResourceDonutChart.tsx`)
- **Title:** `Factor Allocation` (`15px font-semibold text-[var(--fs-ink)]`).
- **Pill Segmented Control (`bg-[var(--fs-surface-muted)] rounded-full p-1 mt-2.5 grid grid-cols-3 gap-1` — NOT underline tabs):**
  - `Weights` | `Scores` | `Evidence`
  - Active tab: `bg-[var(--fs-surface)] text-[var(--fs-ink)] font-medium rounded-full py-1 text-[12px] shadow-2xs`.
- **Tab Bindings (`selectAllocationSlices(tab, priorityWeights, activeStrategy, activeFieldPlan)`):**
  - `Weights`: 5 slices from `PriorityWeights` (`AnalysisSubmitRequest.priorities.weights`, synced from `useAppStore.activePriorityWeights` or `FIXTURE_INPUT_9_1.priorities.weights` when demo/session is active — note `FarmPublic` stores no priority weight object!): `water_saving` (`Water Saving`), `soil_improvement` (`Soil Health`), `income` (`Income`), `risk_reduction` (`Risk Reduction`), `forage_value` (`Forage Value`), summing strictly to `100`.
  - `Scores`: top 5 normalized 0–100 strategy pillar scores from `activeStrategy.scores` (ranked across `priority_fit`, `water_efficiency`, `erosion_protection`, `organic_matter_gain`, `nitrogen_contribution`, `pest_cycle_disruption`, and `income_forage_value`, excluding `bare_field_days_per_year` which is measured in days) rounded via largest-remainder allocation (`allocatePercentages()`) so integer labels sum strictly to `100%`.
  - `Evidence`: grouped citation counts collected across `activeFieldPlan.strategies[].explanation.evidence` and `activeFieldPlan.requested_crop_results[].evidence` by parameter category (`Climate`, `Water`, `Soil & Crop`, `Vegetation`, `Other`), normalized to `100%`.
  - **Zero-Data & Zero-Slice Guard:** When `sum === 0` or `activeFieldPlan === null` on `Scores`/`Evidence`, render a clean `var(--fs-border)` (`#E6E8E7`) hollow donut ring (`aria-label="No analysis data yet"`) + muted `"Run analysis to populate"` caption—zero `NaN`. Filter out segments where normalized `value <= 0` before computing arc coordinates so `0%` categories never draw phantom gap-stroke slivers on the SVG donut, and handle a single `100%` slice (`activeSlices.length === 1`) via a full annular `<circle>` or two `180°` `<path>` arcs so SVG `A`-command endpoints never collapse to zero length.
- **Visual Spec (Match Reference Exactly):**
  - Left side: Vertical color legend (`w-2.5 h-2.5 rounded-[2px]` swatch + label only — **do NOT duplicate `%` numbers in the legend**).
  - Right side: `136×136px` SVG hollow donut (`outer r=64`, `inner r=28`, **clean empty `var(--fs-surface)` center hole — do NOT render `"100%"` inside the hole**):
    - Crisp **`2px` `var(--fs-surface)` gap separators** between slices (`stroke="var(--fs-surface)" strokeWidth="2"`).
    - Palette (clockwise from 12 o'clock & top-to-bottom legend order, matching reference image): Forest `var(--fs-chart-forest)` (`#0B4B2E`), Emerald `var(--fs-chart-emerald)` (`#157853`), Lime `var(--fs-chart-lime)` (`#B8F088`), Warm Amber `var(--fs-chart-amber)` (`#F2A93B`), Coral Red `var(--fs-chart-coral)` (`#C04446`).
    - **Render `%` labels directly inside each arc segment** (`>= 7%`), using `#FFFFFF` text on Forest/Emerald/Coral (`#0B4B2E` `10.19:1`, `#157853` `5.46:1`, `#C04446` `5.05:1`) and `#141916` text on Lime/Amber (`#B8F088` `13.43:1`, `#F2A93B` `8.91:1`) so WCAG AA (`>= 4.5:1`) contrast passes on every slice.

#### 3D. `AgronomyHeatmapCard.tsx` (Replaces `WeeklyHeatmap.tsx`)
- **Header (`flex items-center justify-between`):**
  - Left: `Agronomy Risk` (`15px font-semibold text-[var(--fs-ink)]`).
  - Right: **Top-right `↗` (`w-7 h-7 rounded-full bg-[var(--fs-surface-muted)] flex items-center justify-center` wrapping `<ArrowUpRight size={15} />`) `<Link href="/comparison" aria-label="Open full agronomic risk calendar">` expand link button** matching `Weekly Performance` in the reference image.
- **Matrix (6 row labels × 7 bi-monthly/seasonal columns + bottom-right `Less [4 squares: #EAF7DE, #B8F088, #157853, #0B4B2E] More` legend):**
  - Row labels on `start`: `Drought`, `Heat`, `Frost`, `Waterlog`, `Salinity`, `Bare Soil` (derived strictly from `fieldPlan.field_insights.stress_periods[]` and `fieldPlan.field_insights.bare_field_periods[]`, properly wrapping winter spans where `start_month > end_month` such as Nov–Feb `11..12` and `1..2`).
  - 7 columns across the year (`J–F`, `Mar`, `Apr`, `M–J`, `Jul`, `A–S`, `O–D`).
  - **Cell Geometry (Match Reference):** Wide low-profile rounded rectangles (`h-4 rounded-[5px]`, `gap-1.5` horizontal & vertical), NOT tall squares.
  - Mapped cleanly from `selectAgronomyHeatmap(activeFieldPlan)` with neutral `var(--fs-surface-muted)` (`#F6F7F6`) cells + clear caption when `activeFieldPlan === null`. Hover/focus reveals exact stress type, severity, and window evidence tooltip.

#### 3E. `ScenarioBarsCard.tsx` (Replaces `AnalyticsCard.tsx`)
- **Header (`flex items-center justify-between pb-2.5 border-b border-[var(--fs-border)]`):**
  - Left: `Scenario Performance` (`15px font-semibold text-[var(--fs-ink)]`).
  - Right: **Top-right `↗` (`w-7 h-7 rounded-full bg-[var(--fs-surface-muted)] flex items-center justify-center` wrapping `<ArrowUpRight size={15} />`) `<Link href="/comparison" aria-label="Open full strategy comparison">` expand link button** matching `Analytics Performance` in the reference image.
- **3-Swatch Legend Row (`pt-2.5 flex flex-wrap items-center gap-3 text-[11px] text-[var(--fs-ink-muted)]`):** Top 3 strategies from `activeFieldPlan.strategies` (matching `baseline`, secondary alternative, and `suggested_strategy_id`).
- **3-Bar Column Chart (NO sparklines, NO stock tickers, NO `$830,451`):**
  - Left y-axis scale (`100`, `50`, `0` in `10px text-[var(--fs-ink-subtle)] tabular-nums`).
  - Up to 3 distinct rounded-top vertical bars (`rounded-t-[10px]`, `max-w-[56px] w-full flex-1`, deduplicated by `strategy_id` so the same strategy never renders twice if selected matches baseline/first) scaled strictly `0..100` from `strategy.scores.priority_fit` inside a bar container with `pt-7` top headroom (so even `100%` never clips the headline readout into the legend):
    - Bar 1 (Baseline / #3): `#C5CDC8` / `#7FB69E`
    - Bar 2 (Alternative / #2): `#0B4B2E`
    - Bar 3 (Highlighted / Suggested or Selected Strategy): tall vibrant lime `#B8F088` bar with **bold `20px font-bold text-[var(--fs-ink)] tabular-nums` headline readout positioned cleanly directly above the top of the lime bar** (e.g., `84%`, matching the reference screenshot's bold readout above the rightmost highlighted bar!).
  - Clicking any bar focuses/previews that strategy in `FloatingTelemetry`. When `activeFieldPlan === null`, render 3 baseline `#EAECEB` placeholder bars with `"No active analysis"` subtle label.

---

## Part 5 — Secondary Pages, Modals & Unified FieldShift Theme

Every secondary route and shared component must be audited and migrated completely onto `--fs-*` tokens (`#EAECEB`, `#FFFFFF`, `#F6F7F6`, `#E6E8E7`, `#0B4B2E`, `#157853`, `#B8F088`, `#B8FCA7`), removing both remaining SpaceApps styles AND interim `#00291B` / `#137135` / `#F8FAF8` / `#E5E7EB` hex values while preserving 100% of existing E2E functional flows:

1. **`/select-field` & `src/components/map/OrbitalFieldMap.tsx`:**
   - Preserve exact `2.25s` `flyTo` + deferred `moveend` DEM elevation lookup, polygon GeoJSON validation, Guelma `F1` presets, and Setif outside-boundary `422` (`api-error-OUTSIDE_DEMO_BOUNDARY`) behavior.
   - Align all interim `#00291B`/`#137135`/`#E5E7EB` classes to `--fs-*` tokens (`rounded-[20px] bg-[var(--fs-surface)] border-[var(--fs-border)]`, `bg-[var(--fs-primary)]`, `rounded-md` / pill `boundary-status-pill`, dark-glass/clean white map controls, `load-setif-outside-btn`, and `save-parcel-continue-btn`).
2. **`/farm-profile` & `src/components/profile/UsdaTextureModal.tsx`:**
   - Align `src/app/farm-profile/page.tsx` and `UsdaTextureModal.tsx` onto `--fs-*` light design tokens (`var(--fs-surface)`, `var(--fs-surface-muted)`, `var(--fs-border)`, `var(--fs-primary)`, `#E7F6EC`/`#147A42` `weights-sum-badge`), and **fix the invisible `text-white` / `text-[#E2ECFF]` page header `<h1>`/`<p>` contrast bug** to `text-[var(--fs-ink)]` / `text-[var(--fs-ink-muted)]`.
   - Preserve `New Farm Name` placeholder, `create-farm-btn`, `api-error-GUEST_LIMIT_REACHED`, `"Create Free Account & Claim Data"`, `preset-seybouse`, `INPUT-01` priority weight `100` balancer, `INPUT-02` disjoint crop validation, `INPUT-03` Northern Hemisphere season/month validation, `usda-converter-btn`, `"Apply Derived Soil Type"`, and `run-analysis-submit-btn`.
3. **`/comparison` + `ScoreRadarChart.tsx` + `AgronomicRiskCalendar.tsx` + `PrintableBrief.tsx`:**
   - Align `src/app/comparison/page.tsx`, `AgronomicRiskCalendar.tsx`, and `ScoreRadarChart.tsx` onto `--fs-*` tokens (`#0B4B2E` / `#157853` / `#B8F088` strategy highlights, `strategy-card-*`, `select-strategy-*`, `selected-badge-*`).
   - Upgrade `PrintableBrief.tsx` (`data-testid="printable-brief"`): clean botanical FieldShift print header (`<BrandLogo variant="lockup" />`), zero `ARD ·` or Space Apps references, high-contrast `#141916` on `#FFFFFF` `@media print` typography.
4. **`/evidence` (`src/app/evidence/page.tsx`):**
   - Audit and convert remaining interim `#00291B` / `#137135` / `#F8FAF8` / `#E5E7EB` tokens (and any residual SpaceApps terms) to `--fs-*` rounded cards (`var(--fs-surface)`) with `var(--fs-surface-muted)` metadata trays and `var(--fs-primary)` active filter pills, **fix the invisible `text-white` / `text-[#E2ECFF]` hero `<h1>`/`<p>` contrast bug** to `text-[var(--fs-ink)]` / `text-[var(--fs-ink-muted)]`, and replace `"Mission tag:"` with `"Agronomic tag:"` while keeping `filter-farmer-input`, `filter-dataset`, and `evidence-card-*` intact.
5. **`AuthModal.tsx` & `ProvenanceBanners.tsx`:**
   - Align `AuthModal.tsx` (with `<BrandLogo variant="lockup" />`) and `ProvenanceBanners.tsx` onto `--fs-*` surface, border, primary, and `#E7F6EC`/`#FEF3C7`/`#FEE2E2` semantic badge tokens cleanly.

---

## Part 6 — `v3.2` Contracts, i18n/RTL & E2E Test Alignment

### 6.1 Preserved `v3.2` Backend & Store Contracts
- Keep all 33 API endpoint functions (+ `fetchAllCatalogItems`), `AnalysisResultSchema` (`5.x` tolerant reader), `FieldWriteRequest` sanitization, `19` canonical error codes, and `useAppStore` session/persistence keys working identically (`theme` / `setTheme` / `toggleTheme` and optional `activePriorityWeights` added purely as non-breaking store fields, with `clearSession()` resetting `activePriorityWeights: null`).

### 6.2 `src/lib/i18n/index.ts` Updates
- Remove all `"MISSION CONTROL"`, `"CONTRÔLE MISSION"`, `"Mission Workspace"`, `"Espace Mission"`, `"Orbital Map"`, `"Carte orbitale"`, `"خريطة قالمة المدارية"`, and NASA references across `en`, `fr`, and `ar` dictionaries; standardize `brandTitle` cleanly (`"FieldShift"` or `"FIELDSHIFT"`, synced with `tests/unit/branding.test.ts`), replace `heroEyebrow`/`welcomeTitle`/`selectField.title` with `"WILAYA OF GUELMA · FIELD WORKSPACE"` / `"WILAYA DE GUELMA · ESPACE PARCELLAIRE"`, `"FieldShift Workspace"`, `"Field Boundary"`, `"Carte parcellaire"`, `"خريطة القطع الزراعية"`.
- Add full `en` / `fr` / `ar` translations for all new `/dashboard` labels:
  - `Field Overview`, `Field Zone`, `Crop Type`, `Status`, `Water / Moisture`, `Climate / Elevation`, `Stage / Horizon`, `Season Scope`, `All Seasons`, `Spring`, `Autumn`, `Winter`, `Filter`, `Healthy`, `Moderate`, `Unverified`
  - `Location & Climate`, `Factor Allocation`, `Weights`, `Scores`, `Evidence`, `Agronomy Risk`, `Less`, `More`, `Scenario Performance`
  - `Export`, `Show Telemetry`, `Health Score`, `Pending Run`, `Soil pH`, `Rain / yr`, `Area (ha)`, `Irrigation`, `Water Efficiency`, `Parcel Status`, `Verified`, `Unstudied Demo`
  - `Dark Mode`, `Light Mode`, `Sign Out`, `Search parcels, crops, evidence...`
- Verify `<html lang="ar" dir="rtl">` swaps `NavigationSidebar` to the right (`start-0`), mirrors tooltips, keeps map numbers/units LTR (`dir="ltr"` on coordinate/ratio chips if needed), and leaves zero horizontal overflow.

### 6.3 `tests/e2e/fieldshift.spec.ts` Brand/Theme Expectation Fixes (Zero Test Weakening!)
Update **only** the two legacy Space Apps color assertions in `tests/e2e/fieldshift.spec.ts` while keeping every single functional step (`quick-launch-demo`, `warning-DEMO_PARCEL_UNVERIFIED`, `toggle-degraded-preview`, `degraded-mode-banner`, Setif `422`, Guest Limit `403`, USDA apply, strategy selection, printable brief, evidence filters, `ar`/`en` RTL) 100% strict:
- **Line 31:** Update fallback canvas RGB check from `[7, 23, 63]` (`#07173F`) to FieldShift light canvas `[234, 236, 235]` (`#EAECEB`) / dark `[13, 20, 16]` when dark mode is toggled.
- **Line 56:** Replace the `#EAFE07` yellow button assertion with real WCAG AA contrast verification (`>= 4.5:1`) against the computed background/text colors (`#0B4B2E`/`#FFFFFF`, `#157853`/`#FFFFFF`, or `#B8F088`/`#141916`) on `/select-field` and `/dashboard` interactive controls.
- **`tests/unit/branding.test.ts` Upgrade:** Sync `expect(dict.brandTitle)` with the standardized `"FieldShift"` / `"FIELDSHIFT"` title (replacing `"FIELD SHIFT"` if unified), replace the hardcoded mock segment array (`30, 23, 18, 17, 12`) with real `selectAllocationSlices(...)` assertions across `Weights`, `Scores`, and `Evidence` summing strictly to `100`, extend its `src/` scanner to include `"Fira"`, `"Overpass"`, `"MISSION CONTROL"`, `"CONTRÔLE MISSION"`, and `"Mission tag:"`, and construct the forbidden token list dynamically (e.g. `"#" + "07173F"`) so the Part 8 `grep` over `src tests` cleanly yields `0` false-positive self-matches.

---

## Part 7 — Clean Architecture & Engineering Standards

- **Pure Selectors (`src/lib/telemetry/dashboardSelectors.ts`):**
  - `selectLocationClimateMetrics(analysisResult, fieldPlan, strategy, field)`: priority-ordered lookup across `strategy?.explanation.evidence` and `fieldPlan?.requested_crop_results[].evidence` (`t2m` if present, `precipitation`, `rh2m` / `water.availability`, `precipitation_anomaly`, `wind_2m` / `soil.soil_ph` fallback), plus `analysisResult?.dataset_version_used` & `analysisResult?.generated_at`.
  - `selectAllocationSlices(tab, weights, strategy, fieldPlan)`: returns `{ items, total, isEmpty }` using largest-remainder integer rounding (`allocatePercentages()`) so rendered `%` slices strictly sum to `100` (or `isEmpty: true` when `total === 0`). Maps `weights` (`PriorityWeights`), `scores` (`StrategyScores`), and `evidence` (`EvidenceItem[]`).
  - `selectAgronomyHeatmap(fieldPlan)`: maps `fieldPlan.field_insights.stress_periods[]` and `fieldPlan.field_insights.bare_field_periods[]` onto a stable `6 × 7` matrix (`Drought`, `Heat`, `Frost`, `Waterlog`, `Salinity`, `Bare Soil` × 7 seasonal columns) with zero uninitialized holes.
  - `selectScenarioBars(fieldPlan)`: extracts up to 3 distinct strategies (deduplicated by `strategy_id`) from `fieldPlan.strategies` ordered `[baseline, alternative, suggested/selected]` scaled `0..100` strictly from `strategy.scores.priority_fit` so the highlighted lime `#B8F088` bar + headline sits on the rightmost position matching the reference layout.
  - `clampGaugeScore(score)`: normalizes numeric scores to `[0, 100]` integer or `null`.
- **Accessibility & Craft:**
  - Every icon-only button (`NavigationSidebar`, map `⋮`, zoom `+`/`-`, `Locate`, `Expand`, telemetry `X`, table row `⋮`, card `↗` links) must include clear localized `aria-label` attributes.
  - Maintain WCAG AA (`>= 4.5:1`) contrast on all text, including inside donut slices (`#FFFFFF` on `#0B4B2E` `10.19:1`, `#157853` `5.46:1`, `#C04446` `5.05:1`; `#141916` on `#B8F088` `13.43:1`, `#F2A93B` `8.91:1`), muted axis labels (`#5E6762`), sidebar coral-red exit control (`#C04446` + `#FFFFFF`), dark-glass telemetry cards, and `rounded-md` status badges.
  - Zero TypeScript `any` escapes, zero unused imports/variables (`0` ESLint warnings), and clean component props with narrow types.

---

## Part 8 — Execution Sequence & Mandatory Verification Gates

Execute in this order:
1. **Foundation & Theme Tokens:** Fix `src/app/icon.svg` XML comments; configure `Plus_Jakarta_Sans` + `IBM_Plex_Sans_Arabic` in `src/app/layout.tsx`; update `src/app/globals.css` with Light default & `[data-theme="dark"]` `--fs-*` tokens; add `theme` / `setTheme` / `toggleTheme` (and optional `activePriorityWeights`) to `src/store/useAppStore.ts` and sync `data-theme` in `src/app/providers.tsx`; create single-file `src/components/brand/BrandLogo.tsx` (delete `FieldShiftLogo.tsx`).
2. **Pure Selectors & Unit Tests:** Implement `src/lib/telemetry/dashboardSelectors.ts` + `tests/unit/dashboardSelectors.test.ts` covering `0/0` NaN safety, `100%` sum invariant, missing-evidence fallback, `FieldInsights` heatmap mapping, `StrategyScores.priority_fit` bars, and gauge clamping; update `src/lib/i18n/index.ts`.
3. **Shell & Bento Workspace (`/dashboard`):** Upgrade `NavigationSidebar.tsx` (single responsive `<nav>`, 5 real routes, `Gear`/`Info` popovers, `Moon`/`Sun` `theme-toggle`, coral-red circular sign-out button, initials avatar), `AppShell.tsx`, `DashboardMap.tsx` (removing the tile-covering gradient div + adding GeoJSON dashed parcel via `location.boundary` + thermal shading + borderless centered vertical stack + white `Export`/`⋮` + `64×64` inset + dark-glass zoom stack), `DotMatrixGauge.tsx` (`~215°` open-bottom horseshoe arc with 4 aligned radial-spoke rings, `#58A070 -> #C0E8A0` active gradient, `#D7DAD1` inactive ticks), `FloatingTelemetry.tsx` (boxless 3 KPIs + horizontal divider + 3-row key-value telemetry breakdown), `FieldOverviewTable.tsx` (`Season Scope`, `Filter`, `⋮` toolbar + 7-col/`sr-only` Actions + `rounded-md` badges), and the 4 right-column analytics cards (`LocationClimateCard`, `AllocationDonutCard`, `AgronomyHeatmapCard` with `↗`, `ScenarioBarsCard` with `↗`); delete replaced prototype files.
4. **Secondary Routes, Shared Components & Test Alignment:** Fix the invisible `text-white`/`text-[#E2ECFF]` hero title contrast bug in `farm-profile/page.tsx` and `evidence/page.tsx`, replace `"Mission tag:"` in `evidence/page.tsx`, and unify `evidence/page.tsx`, `comparison/page.tsx`, `farm-profile/page.tsx`, `select-field/page.tsx`, `OrbitalFieldMap.tsx`, `UsdaTextureModal.tsx`, `ScoreRadarChart.tsx`, `AgronomicRiskCalendar.tsx`, `PrintableBrief.tsx`, `AuthModal.tsx`, and `ProvenanceBanners.tsx` onto `--fs-*` tokens; update lines 31 & 56 of `tests/e2e/fieldshift.spec.ts` and upgrade `tests/unit/branding.test.ts` (replacing the hardcoded `30, 23, 18, 17, 12` mock segment array with real `selectAllocationSlices()` assertions and dynamic forbidden-token checks).
5. **Run All Verification Gates (Zero Shortcuts):**
   - `grep -rlE "sa-|#07173F|#0042A6|#EAFE07|#2E96F5|#8E1100|#E43700|#0960E1|#0B1E4E|SpaceApps|NASA|Overpass|Fira|Purwokerto|North Field A1|East Field B2|June 2026|Stocks/Bonds|830,451|MISSION CONTROL|CONTRÔLE MISSION|Mission tag:" src tests` -> **0 matches**
   - `grep -rlE "#00291B|#04421B|#137135|#5FA87D|#84E875|#F8FAF8|#003523|#18664C|#AFDA8A|#D0A034|#BC4C4B|#151A06|#EF4444|#D97706|#E2ECFF|#072B1F|#1B8A5F|#98EA70|#D4F9B3|#EFFEDF" src tests` -> **0 matches** (all interim/AA-failing prototype & widget colors migrated to `--fs-*`)
   - `npm run typecheck` -> **exit 0 (`0` errors)**
   - `npm run lint` -> **exit 0 (`0` errors, `0` warnings)**
   - `npm test` -> **exit 0 (all unit tests pass)**
   - `npm run build` -> **exit 0 (production Next.js build succeeds)**
   - `npx playwright test` -> **exit 0 (all E2E tests pass on desktop + mobile + RTL `ar`)**
   - **Visual Pixel Audit:** Capture screenshots of `/dashboard` at `1440×900`, `1280×800`, and `390×844` (plus RTL `ar` and `[data-theme="dark"]`) and inspect side-by-side against [`media_1794688666510_26d21f97.jpg`](file:///home/unknown/.gemini/antigravity/brain/6f7fcbc5-d247-4ab1-9b30-a90b32ea367d/.user_uploaded/media_1794688666510_26d21f97.jpg) to confirm flush bento alignment, satellite tile visibility, white dashed parcel boundary, open-bottom horseshoe 4-ring aligned dot-matrix gauge, 3-row telemetry breakdown below divider, sidebar 3-control bottom stack (including coral-red circular exit button), LocationClimateCard left-hero/right-condition split, FieldOverviewTable 3 toolbar buttons + 7-col/`sr-only` Actions, hollow white-gapped donut with internal `%` labels, wide 7×6 heatmap pills with `↗`, and 3-column vertical bars with `↗`.
