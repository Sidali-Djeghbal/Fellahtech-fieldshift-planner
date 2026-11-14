# FieldShift Planner — API to UI Integration Map & Inspection Report

## 1. Executive Summary of Current Project & Stitch State

### 1.1 Android Project Inspection (`/home/void/Project/hackthon`)
- **Current Codebase State**: The repository currently contains a stock Android Studio **"Empty Activity" template** (`package com.example.myapplication`, `rootProject.name = "My Application"`).
- **Existing Source Files**:
  - `app/src/main/java/com/example/myapplication/MainActivity.kt` — Renders a static `Greeting("Android")` composable.
  - `app/src/main/java/com/example/myapplication/ui/theme/{Color.kt, Theme.kt, Type.kt}` — Default Material 3 purple/pink template theme (not yet using the FieldShift Earth Observation dark palette `#0C1511` / `#EAB34D`).
  - `gradle/libs.versions.toml` & `app/build.gradle.kts` — Only basic Compose + Material 3 dependencies are configured (`compileSdk = 37`, `minSdk = 30`). Retrofit, OkHttp, Kotlinx Serialization, Hilt, DataStore, and Navigation Compose are not yet added.
- **Git Repository State**: `/home/void/Project/hackthon` is **not yet initialized as a Git repository** (`fatal: not a git repository`).
- **Contract Files Status (Blocker to Resolve Before DTO Coding)**:
  - **FieldShift OpenAPI v3.2 specification**: Not found in `/home/void/Project/hackthon`.
  - **FieldShift ML Contract JSON Schema v5.0**: Not found in `/home/void/Project/hackthon`.

### 1.2 Stitch Project Inspection (`projects/17008084723533360241`)
All Stitch screen designs, screenshots, and the `FieldShift Earth Observation` design system have been downloaded to `docs/stitch/`:
1. **FieldShift Dashboard** (`fb8678385f7340ae8a926b4376443705`) — `docs/stitch/fb8678385f7340ae8a926b4376443705_dashboard.html` & `.png`
2. **Field Registration — GPS & Soil** (`505ae2251b3e4c249215bd4998c533a2`) — `docs/stitch/505ae2251b3e4c249215bd4998c533a2_field_registration.html` & `.png`
3. **Analysis Configuration** (`6445fae3819d40dc9c87f3c3bbcefad0`) — `docs/stitch/6445fae3819d40dc9c87f3c3bbcefad0_analysis_config.html` & `.png`
4. **Strategy Audit & Recommendation** (`b93e0a612e8140ad91da7a7cf6aa89f2`) — `docs/stitch/b93e0a612e8140ad91da7a7cf6aa89f2_strategy_audit.html` & `.png`
5. **Design System Specification** — `docs/stitch/DESIGN.md`

---

## 2. Screen-by-Screen API to UI Integration Map

| Screen | UI component | Required data | API endpoint | HTTP method | Status |
|---|---|---|---|---|---|
| **Global / App Shell** | Top App Bar — Sync Status Badge (`SYNC`, Quadrant subtitle) | Active session state, selected farm/field context | `GET /api/v1/auth/me` / `GET /api/v1/demo/session` | `GET` | Designed (Needs Auth/Session Binding) |
| **Global / App Shell** | Top App Bar — Profile Avatar Button | Current user profile or guest session state | `GET /api/v1/auth/me` | `GET` | Designed (Needs Binding) |
| **Global / App Shell** | Top App Bar — Notifications Icon Button | Notification/alert state (no backend notification endpoint in `/api/v1`) | None (Contract Mismatch — see Section 5) | N/A | Contract Mismatch |
| **Global / App Shell** | Bottom Navigation Bar (`Home`, `Farms`, `Analysis`, `History`, `Profile`) | Navigation route state | Client-side Navigation Compose | N/A | Designed (Static UI Labels Allowed) |
| **1. FieldShift Dashboard** (`fb8678385f7340ae8a926b4376443705`) | Active Farm Switcher Card (`Domaine El-Merdja`, region, field count, active rotation count) | List of user farms, selected farm details, field count, active analyses count | `GET /api/v1/farms`<br>`GET /api/v1/farms/{farm_id}`<br>`GET /api/v1/farms/{farm_id}/fields`<br>`GET /api/v1/farms/{farm_id}/analyses` | `GET` | Designed (Currently Static HTML Mock) |
| **1. FieldShift Dashboard** | Farm Switcher Bottom Sheet / Modal (triggered by Farm Switcher Card) | All farms owned by user + Create/Edit/Delete Farm actions + Demo Locations | `GET /api/v1/farms`<br>`POST /api/v1/farms`<br>`PATCH /api/v1/farms/{farm_id}`<br>`DELETE /api/v1/farms/{farm_id}`<br>`GET /api/v1/demo/locations` | `GET`, `POST`, `PATCH`, `DELETE` | Trigger Designed (Sheet UI Needed) |
| **1. FieldShift Dashboard** | Weather & Climate Stress Banner (`Seasonal Stress Alert`, `≥35°C PEAK`, `ET₀`, `Soil Moisture Index`) | Climate/thermal stress summary & telemetry from latest farm/field analysis or ML result | `GET /api/v1/farms/{farm_id}/analyses` -> `GET /api/v1/analysis/{analysis_id}` | `GET` | Partial / Contract Check Needed (See Section 5) |
| **1. FieldShift Dashboard** | Quick Agronomic Stats Row (`AREA ha`, `AVG FIT /100`, `DEFICIT`) | Sum of `fields[].area_ha`, average strategy fit score across latest farm analyses, water deficit status | `GET /api/v1/farms/{farm_id}/fields`<br>`GET /api/v1/farms/{farm_id}/analyses` | `GET` | Designed (Derived from Real Farm/Analysis Data) |
| **1. FieldShift Dashboard** | Quick Action Chip: `New Field` | Navigates to Field Registration flow for active `farm_id` | `POST /api/v1/farms/{farm_id}/fields` (target flow) | `POST` | Designed |
| **1. FieldShift Dashboard** | Quick Action Chip: `Rotation Lab` | Navigates to Analysis Configuration screen | `POST /api/v1/analysis` (target flow) | `POST` | Designed |
| **1. FieldShift Dashboard** | Quick Action Chip: `Sync Offline (1)` | Refresh/retry pending state or pull-to-refresh repository state | Repository refresh (`GET /api/v1/farms/{farm_id}/...`) | `GET` | Contract Check (No offline queue in spec; map to Refresh) |
| **1. FieldShift Dashboard** | Active Field Highlights List (`Field Card 1`, `Field Card 2`, `View All`) | Farm fields list (name, area, irrigation/water regime, soil type, GPS coordinates) + selected strategy & fit score | `GET /api/v1/farms/{farm_id}/fields`<br>`GET /api/v1/farms/{farm_id}/analyses` | `GET` | Designed (Currently Static HTML Mock) |
| **1. FieldShift Dashboard** | NASA IMERG & Soil Audits Card (`Annual Rain Baseline`, `Organic Matter SOM`, `14-Day Moisture Sparkline`) | Climatology & topsoil metrics returned inside analysis/field environmental audit payload | `GET /api/v1/analysis/{analysis_id}`<br>`GET /api/v1/farms/{farm_id}/fields/{field_id}` | `GET` | Partial / Contract Check Needed (See Section 5) |
| **1. FieldShift Dashboard** | Extended FAB: `New Crop Rotation Analysis` | Navigates to Analysis Configuration screen | `POST /api/v1/analysis` (target flow) | `POST` | Designed |
| **2. Field Registration — GPS & Soil** (`505ae2251b3e4c249215bd4998c533a2`) | Stepper Bar (`1. Basic`, `2 & 3. Location & Soil`, `4. Water`, `5. History`) | Multi-step field creation/editing form state | `POST /api/v1/farms/{farm_id}/fields`<br>`PUT /api/v1/farms/{farm_id}/fields/{field_id}`<br>`PATCH /api/v1/farms/{farm_id}/fields/{field_id}` | `POST`, `PUT`, `PATCH` | Steps 2 & 3 Designed; Steps 1, 4, 5 Need Form Views |
| **2. Field Registration — GPS & Soil** | Step 1: Basic Info (Referenced in Stepper) | Field name, area (ha), slope/topography notes | `POST /api/v1/farms/{farm_id}/fields` | `POST` | Referenced in Stepper (Needs Step 1 View) |
| **2. Field Registration — GPS & Soil** | Step 2: GPS Satellite Signal Card (`Latitude`, `Longitude`, `Elevation`, `Recalculate GPS Position`) | Device GNSS location fix (Android Location API) or Demo Location coordinates | Android `FusedLocationProviderClient` + `GET /api/v1/demo/locations` | `GET` | Designed (Currently Fake JS `setTimeout` Jitter) |
| **2. Field Registration — GPS & Soil** | Step 2: Manual Coordinate Inputs (`Latitude`, `Longitude`, `Elevation`) | User-entered `latitude`, `longitude`, `elevation_m` | `POST /api/v1/farms/{farm_id}/fields`<br>`PATCH /api/v1/farms/{farm_id}/fields/{field_id}` | `POST`, `PATCH` | Designed |
| **2. Field Registration — GPS & Soil** | Step 2: Satellite Tile Context Banner (`Tile`, `Slope %`) | Field elevation/slope metadata (if returned by backend/analysis) or static informational notice | `GET /api/v1/farms/{farm_id}/fields/{field_id}` | `GET` | Contract Check Needed (See Section 5) |
| **2. Field Registration — GPS & Soil** | Step 3: Primary Texture Class Selector (`Clay-Loam`, `Sandy`, `Loamy`, `Silty`, `Unknown`) | Allowed soil types from catalog or OpenAPI enum | `GET /api/v1/catalog`<br>`POST /api/v1/farms/{farm_id}/fields` | `GET`, `POST` | Designed |
| **2. Field Registration — GPS & Soil** | Step 3: Soil Reaction (`pH` Slider `4.5–9.5`) & `SOC %` Input | Field soil parameters (`soil_ph`, `soil_organic_carbon_pct` / soil profile fields) | `POST /api/v1/farms/{farm_id}/fields`<br>`PATCH /api/v1/farms/{farm_id}/fields/{field_id}` | `POST`, `PATCH` | Designed |
| **2. Field Registration — GPS & Soil** | Step 3: Soil Core Sample Verification Date | Optional soil test date metadata | `POST /api/v1/farms/{farm_id}/fields` | `POST` | Contract Check Needed (See Section 5) |
| **2. Field Registration — GPS & Soil** | Step 4: Water Info & Step 5: Crop History (Referenced in Stepper) | Irrigation/water availability, historical crops grown on field | `GET /api/v1/catalog`<br>`POST /api/v1/farms/{farm_id}/fields` | `GET`, `POST` | Referenced in Stepper (Needs Step 4 & 5 Views) |
| **2. Field Registration — GPS & Soil** | Bottom Sticky Bar: `Save Draft` & `Proceed to Water Info` | Local form state persistence / final submission to `POST /farms/{farm_id}/fields` | `POST /api/v1/farms/{farm_id}/fields`<br>`PUT /api/v1/farms/{farm_id}/fields/{field_id}` | `POST`, `PUT` | Designed |
| **3. Analysis Configuration** (`6445fae3819d40dc9c87f3c3bbcefad0`) | Top Parcel Context Banner (`Tidjelabine Hillside`, area, water regime, soil type) | Selected field details | `GET /api/v1/farms/{farm_id}/fields/{field_id}` | `GET` | Designed (Currently Static HTML Mock) |
| **3. Analysis Configuration** | Section 1: Initial Seeding Window (`Autumn / Winter`, `Spring`) | Supported start seasons from catalog/OpenAPI enum | `GET /api/v1/catalog`<br>`POST /api/v1/analysis` | `GET`, `POST` | Designed |
| **3. Analysis Configuration** | Section 1: Planning Horizon Slider (`1–6 Seasons`) | Horizon length (`horizon_seasons` / planning cycle count) | `POST /api/v1/analysis` | `POST` | Designed |
| **3. Analysis Configuration** | Section 1: Rotational Mechanism Toggle (`Consecutive Seasons`, `Annual Crop Rotation`) | Cycle mode enum in analysis request | `GET /api/v1/catalog`<br>`POST /api/v1/analysis` | `GET`, `POST` | Designed |
| **3. Analysis Configuration** | Section 1: Drought Simulation Mode Toggle (`-20% rainfall deficit`) | Climate stress / scenario parameter (if supported by OpenAPI `POST /analysis`) | `POST /api/v1/analysis` | `POST` | Contract Check Needed (See Section 5) |
| **3. Analysis Configuration** | Section 2: 5 Priority Sliders (`Water Saving`, `Soil Organic Matter`, `Economic Yield`, `Risk Reduction`, `Livestock Forage` 0–100) | Multi-objective optimization priority weights in analysis request | `POST /api/v1/analysis` | `POST` | Designed |
| **3. Analysis Configuration** | Section 3: Off-Take Destination Chips (`Local`, `Export`, `Subsistence`, `Mixed`) | Market intent enum in analysis request | `GET /api/v1/catalog`<br>`POST /api/v1/analysis` | `GET`, `POST` | Designed |
| **3. Analysis Configuration** | Section 3: Candidate Crops Matrix (`Durum Wheat`, `Chickpea`, `Common Vetch`, `Faba Bean`, `+ Add Pulse`) | Available crops from catalog & selected candidate/preferred crops for analysis | `GET /api/v1/catalog`<br>`POST /api/v1/analysis` | `GET`, `POST` | Designed (Currently Hardcoded Crop Chips) |
| **3. Analysis Configuration** | Section 3: Machinery & Input Boundaries (`No-till / Low-input`, `Mechanized Harvest`) | Agronomic constraint flags in analysis request | `POST /api/v1/analysis` | `POST` | Contract Check Needed (See Section 5) |
| **3. Analysis Configuration** | Sticky Action Button: `Run ML Rotation Lab` + Async Polling Overlay | Submits `POST /analysis` (with `Idempotency-Key`), polls `GET /analysis/requests/{request_id}` respecting `poll_interval_ms` & `Retry-After`, supports `POST .../cancel` | `POST /api/v1/analysis`<br>`GET /api/v1/analysis/requests/{request_id}`<br>`POST /api/v1/analysis/requests/{request_id}/cancel` | `POST`, `GET` | Button Designed (Currently Fake `setTimeout`; Needs Real Async Polling State UI) |
| **4. Strategy Audit & Recommendation** (`b93e0a612e8140ad91da7a7cf6aa89f2`) | Plot Context Ribbon (`Field Name`, `Audit Complete` status badge) | Field name & analysis status | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed |
| **4. Strategy Audit & Recommendation** | Match Score Hero Card (`Strategy Title`, `Subtitle`, Radial Score Gauge `74/100`, `Confidence & Data Source Chip`, Key Impact Telemetry Pills) | Recommended strategy object: name, description, overall fit score, confidence level, data sources, key impact metrics | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed (Currently Static HTML Mock) |
| **4. Strategy Audit & Recommendation** | Rotation Sequence Timeline (`Phase 1..N`: Crop name, role badge, months/season window, agronomic note) | Strategy `seasonal_plan` / sequence items | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed (Currently Static HTML Mock) |
| **4. Strategy Audit & Recommendation** | Accordion 1: `Why This Was Recommended` | Strategy rationale / summary explanation from ML contract | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed |
| **4. Strategy Audit & Recommendation** | Accordion 2: `Performance Breakdown` (Progress bars: `Water Efficiency`, `Erosion Protection`, `Soil Nitrogen Gain`, `Profit Index`) | Strategy sub-scores / dimension breakdown from ML contract | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed |
| **4. Strategy Audit & Recommendation** | Accordion 3: `Supporting Evidence & Climatology` | Strategy `evidence` list, climatology & soil capacity metrics from ML contract | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed |
| **4. Strategy Audit & Recommendation** | Alert Card 4: `Information Gaps & Ground Risks` | Strategy `risks`, `information_gaps`, and `data_quality` warnings from ML contract | `GET /api/v1/analysis/{analysis_id}` | `GET` | Designed |
| **4. Strategy Audit & Recommendation** | Bottom Action Dock: `Adopt This Strategy` | Persists user's selected strategy for the analysis | `PATCH /api/v1/analysis/{analysis_id}/selection` | `PATCH` | Designed (Currently Fake JS `setTimeout`) |
| **4. Strategy Audit & Recommendation** | Bottom Action Dock: `Compare with Alternative Strategies` | Switches between candidate strategies returned in `GET /analysis/{analysis_id}` | `GET /api/v1/analysis/{analysis_id}` | `GET` | Button Designed (Needs Strategy Switcher/Comparison Sheet) |
| **Supporting Tab: Farms** (`data-path="farms-grid"`) | Farms & Fields Management Screen | List/Create/Update/Delete farms and their fields | `GET /api/v1/farms`<br>`POST /api/v1/farms`<br>`PUT /api/v1/farms/{farm_id}`<br>`DELETE /api/v1/farms/{farm_id}`<br>`GET /api/v1/farms/{farm_id}/fields`<br>`DELETE /api/v1/farms/{farm_id}/fields/{field_id}` | `GET`, `POST`, `PUT`, `DELETE` | Linked in Bottom Nav (Needs Compose Screen using Design System) |
| **Supporting Tab: History** (`data-path="field-history"`) | Farm Analyses History Screen | Historical analyses for active farm, status, selected strategy, link to Strategy Audit | `GET /api/v1/farms/{farm_id}/analyses`<br>`GET /api/v1/analysis/{analysis_id}` | `GET` | Linked in Bottom Nav (Needs Compose Screen using Design System) |
| **Supporting Tab: Profile & Auth** (`data-path="operator-profile"`) | Auth (Login, Register, Guest, Claim Guest) + Operator Profile (Me, Export Data, Delete Account, Demo Session, Logout) | User profile, guest session token, account export, demo session status | `POST /api/v1/auth/guest`<br>`POST /api/v1/auth/register`<br>`POST /api/v1/auth/login`<br>`POST /api/v1/auth/refresh`<br>`POST /api/v1/auth/logout`<br>`GET /api/v1/auth/me`<br>`POST /api/v1/auth/claim-guest`<br>`GET /api/v1/auth/me/export`<br>`DELETE /api/v1/auth/me`<br>`GET /api/v1/demo/session`<br>`DELETE /api/v1/demo/session` | `GET`, `POST`, `DELETE` | Linked in Bottom Nav & Top Bar (Needs Compose Screens using Design System) |

---

## 3. Identified Static Mock Data Inventory

### 3.1 Android Source Code (`app/src/main/java/...`)
- `MainActivity.kt`: Hardcoded `Greeting(name = "Android")` placeholder text. No Stitch screens or mock domain repositories exist in Kotlin yet.

### 3.2 Stitch HTML Screen Designs (`docs/stitch/*.html`)
Every piece of business data below is hardcoded in the Stitch HTML templates and **must be replaced with live backend/sensor state** when implementing the Jetpack Compose screens:

1. **FieldShift Dashboard (`fb8678385f7340ae8a926b4376443705`)**:
   - Hardcoded header subtitle: `"NORTH QUADRANT #04"`.
   - Hardcoded active farm: `"Domaine El-Merdja"`, `"Boumerdès, DZ"`, `"3 Fields · 1 Active Rotation"`.
   - Hardcoded weather banner: `"≥35°C PEAK"`, `"4 consecutive hot days forecasted across Lower Mitidja basin. Evapotranspiration ET₀ surging to 6.2 mm/day."`, `"Soil Moisture Index: 31% (Depleting)"`.
   - Hardcoded quick stats: `AREA: 42.5 ha ("Managed basin")`, `AVG FIT: 68/100 ("+4 vs last cycle")`, `DEFICIT: Moderate ("Clay buffer ok")`.
   - Hardcoded offline chip count: `"Sync Offline (1)"`.
   - Hardcoded field cards (`"2 parcels"`):
     - Card 1: `"Tidjelabine Hillside"`, `"36°43'12\"N 3°29'08\"E"`, `"PARCEL 04"`, `"12.4 ha · Rainfed Cereal Slope · Clay-Loam"`, `"Durum Wheat + Vetch Cover"`, `"Fit 74/100"`, `"-28 days bare-wet erosion risk"`, `"Fall 2025 Plan"`.
     - Card 2: `"Mitidja Plain Lower"`, `"36°41'55\"N 3°26'40\"E"`, `"PARCEL 01"`, `"18.0 ha · Alluvial Loam · Drip Irrigated"`, `"Audited & Verified"`, `"Chickpea rotation active (Week 6)"`, `"NDVI 0.62"`.
   - Hardcoded NASA IMERG & Soil Audits card: `"Boumerdès Climatology Cross-Match"`, `"T-6h"`, `ANNUAL RAIN BASELINE: 647 mm/yr ("IMERG anomaly +12mm")`, `ORGANIC MATTER (SOM): 1.82% topsoil ("Target ≥ 2.4%")`, `Synthetic Moisture Depletion: -18.4% Net` with hardcoded SVG path `M0,10 Q40,5 80,18...`.

2. **Field Registration — GPS & Soil (`505ae2251b3e4c249215bd4998c533a2`)**:
   - Hardcoded GPS lock telemetry: `"High Accuracy Fix"`, `"Locked ±3.2m · 14 SV in view"`, `"HDOP 0.82"`, `Latitude: 36.7266° N`, `Longitude: 3.4837° E`, `Elevation: 142 m`.
   - **Fake interaction**: Clicking `Recalculate GPS Position` runs a `950ms` `setTimeout` that mutates DOM text to hardcoded `'36.7268° N'`, `'3.4839° E'`, `'141 m'`.
   - Hardcoded satellite tile banner: `"Tile: NASA-SRTM-Z14-X8432"`, `"Slope: 1.8% (Gentle)"`.
   - Hardcoded soil defaults: `Clay-Loam` pre-selected, `pH 7.4 (Slightly Alkaline)`, `SOC: 1.85 % w/w`, `"Regional baseline: 1.4% · Target: >2.2% for dryland grains"`.
   - Hardcoded soil verification lab record: `"14 Nov 2024"`, `"ITGC Regional Agronomy Lab (#894)"`.

3. **Analysis Configuration (`6445fae3819d40dc9c87f3c3bbcefad0`)**:
   - Hardcoded parcel banner: `"MOD-ROT-2025"`, `"Tidjelabine Hillside"`, `"12.4 ha · Rainfed Terraces · Clay-Loam Subsoil"`, `"Sentinel-2 Sync: 2d ago"`, `"Moisture: 24%"`.
   - Hardcoded initial seeding window labels: `"Autumn / Winter 2025"`, `"Spring 2026"`.
   - Hardcoded candidate crops list: `"Durum Wheat"`, `"Chickpea"`, `"Common Vetch"`, `"Faba Bean"` (must come from `GET /api/v1/catalog`).
   - Hardcoded runtime estimate footer: `"Agronomic AI Engine: 4,096 Monte Carlo Cycles"`, `"Est. 4.2s runtime"`.
   - **Fake interaction**: Clicking `Run ML Rotation Lab` runs a `1200ms` `setTimeout` displaying `"Compiling Heuristics..."` followed by `"Job Dispatched #4092"` instead of submitting `POST /api/v1/analysis` and polling `GET /api/v1/analysis/requests/{request_id}`.

4. **Strategy Audit & Recommendation (`b93e0a612e8140ad91da7a7cf6aa89f2`)**:
   - Hardcoded header ribbon: `"Tidjelabine Hillside · Sector 4B"`, `"Audit Complete"`.
   - Hardcoded hero score card: `"Balanced Water & Soil"`, `"Optimized for semiarid clay-loam topography"`, score `74 / 100`, `"Medium-High Confidence · NASA IMERG & POWER"`, `Runoff Risk Mitigation: -29 days/yr`, `Substrate Moisture: +38 mm`.
   - Hardcoded 3-phase rotation sequence (`20-Month Arc`): `Durum Wheat (Oct – Jun · 9 mos)`, `Vetch Cover Crop (Jul – Nov · 5 mos, +N2 Fixation)`, `Chickpea (Nov – May · 6 mos)`.
   - Hardcoded explainability accordions:
     - Rationale text (`38mm additional moisture`, `12% slope gradient`).
     - Performance breakdown bars (`Water Efficiency: 82/100`, `Erosion Protection: 88/100`, `Soil Nitrogen Gain: +24 kg N/ha`, `Profit Index: 76/100`).
     - Supporting evidence (`NASA POWER 30-year climatology... Field AWC: 140mm, 36.72° N, 3.48° E`).
     - Information gaps & ground risks (`Subsurface hardpan depth unknown... ITGC Boumerdès`).
   - **Fake interaction**: Clicking `Adopt This Strategy` runs an `1100ms` `setTimeout` changing button text to `"Applying Sequence..."` -> `"Strategy Activated"` without calling `PATCH /api/v1/analysis/{analysis_id}/selection`.

---

## 4. Endpoint Coverage Report (`/api/v1`)

| Category | Endpoint | HTTP Method | Target UI Screen / Flow | Coverage Status |
|---|---|---|---|---|
| **Authentication** | `/auth/guest` | `POST` | Auth Welcome / Onboarding Screen ("Continue as Guest" using `X-Guest-Token`) | Needs Screen |
| **Authentication** | `/auth/register` | `POST` | Auth Register Screen | Needs Screen |
| **Authentication** | `/auth/login` | `POST` | Auth Login Screen | Needs Screen |
| **Authentication** | `/auth/refresh` | `POST` | OkHttp `Authenticator` / Token Refresh Interceptor | Infrastructure |
| **Authentication** | `/auth/logout` | `POST` | Operator Profile Screen -> Logout Action | Needs Screen |
| **Authentication** | `/auth/me` | `GET` | Operator Profile Screen & App Session Bootstrap | Needs Screen |
| **Authentication** | `/auth/claim-guest` | `POST` | Operator Profile / Upgrade Guest Account Flow | Needs Screen |
| **Authentication** | `/auth/me/export` | `GET` | Operator Profile Screen -> Export Account Data Action | Needs Screen |
| **Authentication** | `/auth/me` | `DELETE` | Operator Profile Screen -> Delete Account Action (with confirmation dialog) | Needs Screen |
| **Demo** | `/demo/locations` | `GET` | Dashboard Empty State / Demo Mode Picker & Field Registration Location Preset Picker | Needs Sheet/Dialog |
| **Demo** | `/demo/session` | `GET` | Operator Profile / Dashboard Demo Banner | Needs Binding |
| **Demo** | `/demo/session` | `DELETE` | Operator Profile / Dashboard Demo Banner -> Reset/Exit Demo Session | Needs Binding |
| **Farms** | `/farms` | `GET` | Dashboard Farm Switcher & Farms Tab | Designed (Dashboard) |
| **Farms** | `/farms` | `POST` | Dashboard Empty State ("Create Farm") & Farm Switcher Sheet | Needs Dialog/Sheet |
| **Farms** | `/farms/{farm_id}` | `GET` | Dashboard Active Farm Header & Farm Detail | Designed (Dashboard) |
| **Farms** | `/farms/{farm_id}` | `PUT` | Edit Farm Dialog/Screen (full replacement) | Needs Dialog/Screen |
| **Farms** | `/farms/{farm_id}` | `PATCH` | Edit Farm Dialog/Screen (partial update) | Needs Dialog/Screen |
| **Farms** | `/farms/{farm_id}` | `DELETE` | Farms Tab / Farm Switcher Sheet -> Delete Farm | Needs Action/Dialog |
| **Fields** | `/farms/{farm_id}/fields` | `GET` | Dashboard Active Field Highlights & Farms Tab | Designed (Dashboard) |
| **Fields** | `/farms/{farm_id}/fields` | `POST` | Screen 1: Field Registration — GPS & Soil (multi-step wizard) | Designed (Screen 1) |
| **Fields** | `/farms/{farm_id}/fields/{field_id}` | `GET` | Field Detail / Analysis Configuration Header / Edit Field | Designed (Screen 2) |
| **Fields** | `/farms/{farm_id}/fields/{field_id}` | `PUT` | Screen 1: Field Registration (Edit mode, full update) | Designed (Screen 1) |
| **Fields** | `/farms/{farm_id}/fields/{field_id}` | `PATCH` | Screen 1: Field Registration (Partial step update) | Designed (Screen 1) |
| **Fields** | `/farms/{farm_id}/fields/{field_id}` | `DELETE` | Field Detail / Farms Tab -> Delete Field Action | Needs Action/Dialog |
| **Catalog** | `/catalog` | `GET` | Field Registration (soil/water/crop enums) & Analysis Configuration (crops, seasons, options) | Designed (Screens 1 & 2) |
| **Analysis** | `/analysis` | `POST` | Screen 2: Analysis Configuration (`Run ML Rotation Lab` button) | Designed (Screen 2) |
| **Analysis** | `/analysis/requests/{request_id}` | `GET` | Async Analysis Polling State View (respecting `poll_interval_ms` & `Retry-After`) | Needs Polling View |
| **Analysis** | `/analysis/requests/{request_id}/cancel` | `POST` | Async Analysis Polling State View -> `Cancel Analysis` button | Needs Polling View |
| **Analysis** | `/analysis/{analysis_id}` | `GET` | Screen 3: Strategy Audit & Recommendation | Designed (Screen 3) |
| **Analysis** | `/analysis/{analysis_id}/selection` | `PATCH` | Screen 3: Strategy Audit (`Adopt This Strategy` button) | Designed (Screen 3) |
| **Analysis** | `/farms/{farm_id}/analyses` | `GET` | Dashboard Summary & History Tab | Designed (Dashboard) |

---

## 5. API Contract Mismatch & Missing Capabilities Report

### 5.1 Critical Missing Inputs in Workspace
1. **OpenAPI v3.2 & ML Contract JSON Schema v5.0 Files Not Present in Repo**:
   - The prompt references *"3. The authoritative FieldShift OpenAPI v3.2 specification"* and *"4. The FieldShift ML contract JSON Schema v5.0"*, as well as an existing git repo.
   - However, `/home/void/Project/hackthon` only contains a newly generated Android Studio `My Application` template and is not yet a git repository.
   - **Action Required**: Please provide the path to (or paste/copy into the workspace) the **OpenAPI v3.2 spec** and **ML JSON Schema v5.0**, and confirm the backend base URL (e.g., `http://10.0.2.2:8000/api/v1` or a hosted URL) so we can verify every exact property name, enum value, and nullable field before writing DTOs.

### 5.2 UI-to-Backend Mismatches Identified in Stitch Screens
Even before inspecting the raw OpenAPI YAML/JSON file, comparing the Stitch HTML components against the `/api/v1` endpoint list reveals the following architectural mismatches and proposed minimal solutions:

1. **Dashboard Real-Time Satellite / Weather Telemetry Widgets (`fb8678385f7340ae8a926b4376443705`)**:
   - **Mismatch**: The Dashboard displays a live `"Seasonal Stress Alert (≥35°C PEAK, ET₀ 6.2 mm/day, Soil Moisture Index: 31%)"`, `"NDVI 0.62"`, `"Sentinel-2 Sync: 2d ago"`, and a `"14-Day Synthetic Moisture Depletion"` sparkline. There is **no dedicated `/weather` or `/satellite/telemetry` endpoint** in `/api/v1`.
   - **Smallest Appropriate Solution**: Populate environmental/climatology metrics on the Dashboard from the most recent completed `Analysis` (`GET /analysis/{analysis_id}` environmental/data-quality/evidence blocks) for the active farm. When a farm has no completed analyses yet, display an honest "Run an analysis to view satellite & climatology audit metrics" empty state card rather than fabricated weather numbers.

2. **Dashboard `Sync Offline (1)` Quick Action Chip**:
   - **Mismatch**: The API contract is online REST-based (`/api/v1`) without an offline mutation sync protocol.
   - **Smallest Appropriate Solution**: Repurpose this chip as a **Refresh Data (`Sync Now`)** action that triggers a real repository refresh (`GET /farms`, `GET /farms/{farm_id}/fields`, `GET /farms/{farm_id}/analyses`) with a pull-to-refresh / loading indicator.

3. **Top App Bar `Notifications` Bell Button**:
   - **Mismatch**: No `/notifications` endpoint exists in `/api/v1`.
   - **Smallest Appropriate Solution**: Keep the visual icon to preserve the Stitch header or show a sheet/popover listing active analysis request statuses (e.g., ongoing or recently completed analysis jobs) without inventing mock notifications.

4. **Field Registration Stepper (`Steps 1, 4, 5`) vs Single Stitch Screen (`Steps 2 & 3`)**:
   - **Mismatch**: Stitch screen `505ae2251b3e4c249215bd4998c533a2` only shows `Steps 2 & 3: Location & Soil`, while its stepper header shows `1. Basic`, `2 & 3. Location & Soil`, `4. Water`, and `5. History`. Creating a field via `POST /farms/{farm_id}/fields` requires basic field attributes (such as `name`, `area_ha`) and potentially water/crop history fields defined in the OpenAPI schema.
   - **Smallest Appropriate Solution**: Implement the full 4-view stepper flow inside the Field Registration screen (using the exact same Stitch surface cards, chips, and inputs from `DESIGN.md`) so the user can enter `1. Basic` (Name, Area), `2 & 3. Location & Soil`, `4. Water`, and `5. History`, then submit the complete payload to `POST /farms/{farm_id}/fields` (and support local draft saving in DataStore for the `Save Draft` button).

5. **Field Registration GPS Signal Metrics (`±3.2m`, `14 SV in view`, `HDOP 0.82`) & Soil Lab Record (`ITGC Lab #894`)**:
   - **Mismatch**: Satellite count/HDOP are hardware GNSS telemetry, not backend API fields; `"ITGC Regional Agronomy Lab (#894)"` is static flavor text unless the `Field` schema includes a soil sample date/notes field.
   - **Smallest Appropriate Solution**: Bind `Latitude`, `Longitude`, `Elevation`, and accuracy (`±Xm`) to real Android `FusedLocationProviderClient` / `LocationManager` readings (when location permission is granted) or manual coordinate inputs / `GET /demo/locations`. Only show fields supported by real device location or the OpenAPI `Field` schema.

6. **Analysis Configuration Extra Controls (`Drought Simulation Mode`, `Machinery & Input Boundaries`, `4,096 Monte Carlo Cycles`)**:
   - **Mismatch**: Need to verify against the OpenAPI v3.2 `POST /analysis` request schema whether `drought_simulation`, `no_till`, and `mechanized_harvest` exist as request fields, or if `POST /analysis` only accepts field ID, start season, horizon, cycle mode, priority weights, market intent, and crop preferences.
   - **Smallest Appropriate Solution**: Bind every control that maps to a real `POST /analysis` field; if any toggle is not in OpenAPI v3.2, report/disable or map only to valid schema fields once OpenAPI v3.2 is inspected. Remove the hardcoded `"4,096 Monte Carlo Cycles / Est. 4.2s runtime"` fake metric or replace it with a static informational note about asynchronous processing.

---

## 6. Proposed Implementation Sequence

Once the OpenAPI v3.2 specification and ML Contract JSON Schema v5.0 are provided and this integration map is approved:

1. **Step 1 — Git & Project Foundation**:
   - Initialize Git repository (or verify branch setup) and create dedicated feature branch `feat/stitch-backend-integration`.
   - Configure `gradle/libs.versions.toml` and `app/build.gradle.kts` with Hilt, Retrofit, OkHttp, Kotlinx Serialization, DataStore Preferences, Jetpack Navigation Compose, Lifecycle ViewModel Compose, and Play Services Location.
   - Implement the **FieldShift Earth Observation** Material 3 Theme (`Color.kt`, `Type.kt`, `Theme.kt`) matching `docs/stitch/DESIGN.md` (`#0C1511` surface, `#EAB34D` primary container, Space Grotesk / Inter / Space Mono typography).

2. **Step 2 — Network, Auth & Session Infrastructure**:
   - Implement DataStore-backed `SessionManager` storing Bearer `access_token`, `refresh_token`, `X-Guest-Token`, active `farm_id`, and ongoing `analysis_request_id`.
   - Implement OkHttp Auth Interceptor (injecting `Authorization: Bearer` or `X-Guest-Token`), Token Refresh `Authenticator` (`POST /auth/refresh` with rotation & session expiry handling), and `Idempotency-Key` header support.
   - Ensure zero logging of sensitive tokens or credentials.

3. **Step 3 — API DTOs, Domain Models & Repositories**:
   - Create exact Kotlinx Serialization DTOs matching OpenAPI v3.2 and ML Schema v5.0 for Auth, Demo, Catalog, Farms, Fields, and Analysis.
   - Implement `AuthRepository`, `DemoRepository`, `CatalogRepository`, `FarmRepository`, `FieldRepository`, and `AnalysisRepository` with clean `UiState<T>` (`Loading`, `Success`, `Empty`, `Error`, `Refreshing`).

4. **Step 4 — Auth, Onboarding, Demo & Profile Screens**:
   - Implement Guest login (`POST /auth/guest`), Login (`POST /auth/login`), Register (`POST /auth/register`), Claim Guest (`POST /auth/claim-guest`), and Profile (`GET /auth/me`, `GET /auth/me/export`, `DELETE /auth/me`, `POST /auth/logout`, Demo Session management).

5. **Step 5 — FieldShift Dashboard & Farms Management (`fb8678385f7340ae8a926b4376443705`)**:
   - Implement the Stitch Dashboard screen driven by `FarmRepository`, `FieldRepository`, and `AnalysisRepository`.
   - Include meaningful Empty States ("No farms yet — Create Farm" or "Load Demo Location") and Farm Switcher/Creation bottom sheet.

6. **Step 6 — Field Registration Wizard (`505ae2251b3e4c249215bd4998c533a2`)**:
   - Implement the Stitch Field Registration screen with real device GPS acquisition / manual coordinate entry, catalog-backed soil/water/crop selectors, and `POST` / `PUT` / `PATCH` `/farms/{farm_id}/fields` integration.

7. **Step 7 — Analysis Configuration & Async Polling Workflow (`6445fae3819d40dc9c87f3c3bbcefad0`)**:
   - Implement the Stitch Analysis Configuration screen populated from `GET /catalog` and `GET /farms/{farm_id}/fields/{field_id}`.
   - Implement real `POST /analysis` submission with `Idempotency-Key`, persistent `request_id` in DataStore, coroutine polling loop on `GET /analysis/requests/{request_id}` respecting `poll_interval_ms` and `Retry-After` headers, and cancellation via `POST /analysis/requests/{request_id}/cancel`.

8. **Step 8 — Strategy Audit, Comparison & Selection (`b93e0a612e8140ad91da7a7cf6aa89f2`)**:
   - Implement the Stitch Strategy Audit & Recommendation screen rendering real ML strategies, seasonal plans, fit scores, performance breakdown, evidence, information gaps, risks, and data quality from `GET /analysis/{analysis_id}`.
   - Wire `Adopt This Strategy` to `PATCH /analysis/{analysis_id}/selection` and `Compare with Alternative Strategies` to switch/compare strategies from the analysis response.

