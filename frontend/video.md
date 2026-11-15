# AI Agent Prompt: Record a 30-Second NASA Space Apps Challenge Demo Video for FELLAH TECH

> **Copy/paste this entire document (or point your browser/coding agent directly to `video.md`) to autonomously navigate `https://fieldshift-planner.sidalidjeghbal.workers.dev/`, drive every feature cleanly, and render a publication-ready ≤ 30s MP4 demonstration video.**

---

## 1. Mission & Strict Competition Rules

You are an autonomous **Browser Automation & Video Production Agent**. Your task is to navigate the live web application **FELLAH TECH · Guelma Edition** (`https://fieldshift-planner.sidalidjeghbal.workers.dev/`) and record a **single, continuous, crystal-clear demonstration video** formatted for the **NASA Space Apps Challenge Global Award**:

- **Hard Duration Ceiling:** **`<= 30.0 seconds`** total runtime. **Target exact edited runtime: `28.0 – 29.0 seconds`** so video container rounding never violates the 30-second limit.
- **Zero Auth Walls in Video:** Use the live sandbox/fixture controls already enabled on `https://fieldshift-planner.sidalidjeghbal.workers.dev/` (no signup/login prompts).
- **Clear Earth-Observation & AI Value:** Within 29 seconds, visually demonstrate:
  1. **Liquid Glass Geospatial Command Center** covering all 34 communes of Wilaya 24 (Guelma, Algeria) over live satellite orthophotography.
  2. **Precision Satellite Field Border CAD Editor** showing real cultivated field polygons (`Seybouse`, `Héliopolis`, `Bouchegouf`, `Oued Zenati`, `Hammam Debagh`, plus real demo parcel `F1` in `Boumahra Ahmed · 9.36 ha`), `NDVI` / `Soil Moisture` overlays, and `2D Ortho / 3D Relief` tilt.
  3. **Orbital 3D Terrain & NASA GIBS Simulator** showing `NDVI`, `Soil Moisture`, `Climate Shock (-25% rain, +2.5°C)` impact scoring, and 12-month animated crop-cover / rainfall timeline.
  4. **AI Agronomic Rotation Intelligence Studio** showing unverified parcel guardrails (`DEMO_PARCEL_UNVERIFIED`), 12-month bare-soil & drought stress calendar, 3-strategy comparison (`Existing Cereal Baseline` vs recommended `Chickpea & Drip Forage Balanced Rotation` vs `Market Cereal & Legume Cash Focus`), 4-season rotation timeline, and instant **English / French / Arabic RTL** localization.

---

## 2. Capture Environment & Visual Quality Standards

Follow these strict technical rules so the recorded video looks studio-grade and smooth (not jittery or half-loaded):

1. **Resolution & Aspect Ratio:** `1920x1080` (16:9 desktop landscape, `deviceScaleFactor: 1`, `reducedMotion: "no-preference"` so CSS Liquid Glass & MapLibre camera fly-to animations glide smoothly).
2. **Smooth Human Cursor Overlay:** Before recording each scene, inject a subtle translucent green/white halo cursor indicator via `page.addInitScript` and move the Playwright mouse smoothly (`steps: 18` over `220–320ms`) before every click so viewers visually track every button press.
3. **Never Capture Blank Loading Tiles (Two-Pass Pre-Warm Strategy):**
   - **Pre-warm before recording or use trimmed lead-in:** Satellite basemaps (Esri World Imagery & NASA GIBS WMTS tiles) and WebGL shaders take `2–4s` on cold load. Either:
     - **Option A (Recommended — Multi-clip seamless cut / trim with `ffmpeg`):** Record the Playwright browser session from launch through the full choreography (e.g., ~34s raw `.webm` including cold loads), **cut out dead tile-loading waits or speed up empty waits slightly (`<= 1.15x` max so natural interactions don't look rushed)** using `ffmpeg`, and verify final output is strictly **`28.0s – 29.0s`**.
     - **Option B (Pre-warmed cache in persistent Chromium profile — Recommended with Playwright):** Run a warm-up pass inside a shared `userDataDir` (`chromium.launchPersistentContext`) visiting `/` -> Border Editor -> 3D Simulator so Chromium writes Esri & NASA GIBS tiles to disk cache, call `localStorage.clear()`, close that context, and then launch the recording `launchPersistentContext` against that same `userDataDir` for one clean uninterrupted `~28.5s` pass!
4. **Keep Scrollbar Clean & Theme Consistent:** Stay in default **Light Liquid Glass** mode on Command Center & CAD Editor (ultra-legible daylight crispness), letting the **3D Orbital Simulator** bring contrast and depth naturally. Use dark/AR-RTL only as a purposeful `1.2s` showcase beat at the end.

---

## 3. Verified Live UI Map & Exact Selectors (Zero Guessing)

All selectors below are verified directly against the deployed codebase on `https://fieldshift-planner.sidalidjeghbal.workers.dev/`:

### A. Command Center Overview (`/` & `/dashboard`)
- Root dashboard marker: `[data-testid="guelma-farmer-dashboard"]`
- Empty-state map card: `[data-testid="empty-workspace-card"]`
- Populate 4 fitted Guelma farms/fields: `[data-testid="load-samples-btn"]` (`"Load sample parcels"`)
- Open/load demo parcel `F1` (`9.36 ha`, `Boumahra Ahmed`) + AI evaluation: `[data-testid="preview-demo-intelligence-btn"]` (`"Load Guelma Demo Intelligence"`)
- Map HUD (`[data-testid="guelma-overview-map"]`):
  - Step to next field: `button[aria-label="Next parcel"]`
  - Fit all parcels: `[data-testid="map-fit-extent-btn"]`
- Field Inspector card (`[data-testid="parcel-inspector-panel"]`):
  - Edit borders in Precision CAD: `[data-testid="inspector-edit-borders-btn"]` (`"Borders"`)
  - Launch 3D NASA Orbital Simulator: `button[title="3D Inspect"]` (`"3D Inspect"`)
- Header language radio pills (`role="radio"` inside the `en / fr / ar` switcher):
  - `[data-testid="dash-lang-en"]`, `[data-testid="dash-lang-fr"]`, `[data-testid="dash-lang-ar"]`
- Sidebar theme toggle (Light/Dark Liquid Glass): `[data-testid="rail-theme-btn"]`

### B. Precision CAD Border Editor (`[data-testid="guelma-border-editor"]`)
- Quick fitted satellite parcel presets (top-left overlay):
  - `[data-testid="quick-border-seybouse"]` (`Guelma · 2.3 ha`)
  - `[data-testid="quick-border-heliopolis"]` (`Héliopolis · 8.9 ha`)
  - `[data-testid="quick-border-bouchegouf"]` (`Bouchegouf · 10.4 ha`)
  - `[data-testid="quick-border-oz"]` (`Oued Zenati · 4.8 ha`)
  - `[data-testid="quick-border-bouhamdane"]` (`Hammam Debagh · 3.0 ha`)
- 34-Commune searchable fly-to combobox: `[data-testid="commune-search-input"]`
- Top-right spectral & view toggles:
  - `page.getByRole("button", { name: "NDVI", exact: true })`
  - `page.getByRole("button", { name: "SM", exact: true })`
  - `page.getByRole("button", { name: "RGB", exact: true })`
  - `page.getByRole("button", { name: /2D Ortho|3D Relief/i })`
- Live telemetry readouts: `[data-testid="cad-area-value"]`, `[data-testid="cad-perim-value"]`, `[data-testid="cad-vertices-count"]`
- Return to Command Center: `[data-testid="border-editor-back"]` (`"Back to Dashboard"`)

### C. 3D Orbital NASA Terrain Simulator (`[data-testid="fieldshift-prototype-root"]`)
- Top toolbar layer toggles (`nav.layer-dock`):
  - `button[data-layer="truecolor"]`
  - `button[data-layer="ndvi"]`
  - `button[data-layer="sm"]`
  - `button[data-layer="rain"]`
  - `button[data-layer="lst"]`
- Camera & view controls:
  - `#tilt-btn` (`3D` relief tilt)
  - `#focus` (`Parcel` vs `Guelma` province focus)
- Rotation Lab (`#lab`):
  - Climate shock chip `-25% rain, +2.5°C`: `button[data-scen="-25,2.5"]`
  - Dry `-20% rain`: `button[data-scen="-20,0"]`
  - Baseline reset: `button[data-scen="0,0"]` (`#reset`)
  - Strategy comparison buttons: `button[data-id]` inside `#strats`
- Timeline Capsule (bottom dock):
  - Animate 12-month climate/vegetation scrubber: `#play`
  - Scrub slider directly: `#slider`
- Return to Dashboard: `[data-testid="proto-back-dashboard"]` (`"Back to Command Center"`)

### D. AI Agronomic Intelligence & Studio (`[data-testid="ai-intelligence-section"]`)
- Unverified parcel provenance warning: `[data-testid="warning-DEMO_PARCEL_UNVERIFIED"]`
- Executive summary card: `[data-testid="analysis-summary-card"]`
- 12-month bare-soil calendar & stress matrix: `[data-testid="field-insights-timeline"]`, `[data-testid="stress-matrix"]`
- 3-strategy grid: `[data-testid="strategy-comparison-grid"]`
  - Cards: `strategy-card-S1_baseline_cereal`, `strategy-card-S2_water_resilient`, `strategy-card-S3_income_diversified`
- 4-season timeline nodes: `[data-testid="rotation-timeline-S2_water_resilient"]`, `[data-testid="timeline-node-S2_water_resilient-1"]`
- Scientific evidence tabs: `[data-testid="explanation-tabs-S2_water_resilient"]`
- Plain-language farmer toggle: `[data-testid="toggle-plain-mode-btn"]`

---

## 4. Exact 28.5-Second Choreography & Shot List

Execute this **5-beat script** carefully. Dwell times assume tile caches are pre-warmed (see Section 5):

| Beat | Window | Route / View | Exact Agent Actions | What Viewer Sees on Screen |
| :--- | :--- | :--- | :--- | :--- |
| **1. Guelma Command Center** | `0.0s – 5.0s` | `/` (Overview) | • Hold `0.8s` on `"FELLAH TECH · Guelma Edition"` Liquid Glass overview map.<br>• Smoothly move cursor to `[data-testid="load-samples-btn"]` and click.<br>• Wait `1.2s` for parcels, KPI cards (`1` farm, `4` parcels, `26.4 ha`), and the spatial readiness donut to animate.<br>• Click `button[aria-label="Next parcel"]` once (`+1.2s`) to glide camera smoothly to `Heliopolis Hillside` (`8.9 ha`). | Satellite mosaic across Wilaya 24 -> instant geospatial telemetry population -> glassy parcel callout flying across real cropped farmland. |
| **2. Precision Satellite CAD** | `5.0s – 11.5s` | CAD Border Editor | • Click `[data-testid="inspector-edit-borders-btn"]` (`"Borders"`). Wait `0.9s`.<br>• Click `[data-testid="quick-border-bouchegouf"]` (`Bouchegouf · 10.4 ha`). Camera flies over Bouchegouf Valley (`10.40 ha`). Wait `1.2s`.<br>• Click `NDVI` pill, wait `0.9s`, then click `2D Ortho` button to engage **`3D Relief`**. Wait `1.4s`.<br>• Click `[data-testid="border-editor-back"]`. | Sub-meter Esri imagery + numbered draggable parcel vertices hugging real agricultural hedges, live geodesic area (`10.40 ha`), NDVI canopy map, and pitched 3D relief. |
| **3. 3D NASA GIBS Simulator** | `11.5s – 19.0s` | 3D Prototype (`/dashboard` overlay) | • Wait `0.5s` back on overview, then click `button[title="3D Inspect"]` on the Field Inspector.<br>• Wait `1.2s` for bootsplash fade-out & 3D parcel mesh.<br>• Click `button[data-layer="ndvi"]` (`NDVI`), then `button[data-layer="sm"]` (`Soil moisture`), wait `0.9s`.<br>• Click `button[data-scen="-25,2.5"]` (`Climate Shock: +2.5°C, -25% rain`) — highlight live strategy re-scoring (`#strats`).<br>• Click `#play` (Timeline Capsule) for `1.6s` so seasonal rainfall/NDVI curve & 3D terrain scrub through dry summer months.<br>• Click `[data-testid="proto-back-dashboard"]`. | Authentic Apple-grade Liquid Glass 3D terrain relief draped in real NASA Earthdata GIBS overlays, dynamic drought stress testing, and animated seasonal climate playback. |
| **4. AI Rotation Intelligence** | `19.0s – 26.0s` | `/` AI Studio (`intelligence` view) | • Click `[data-testid="preview-demo-intelligence-btn"]` (`"Load Guelma Demo Intelligence"`), which switches to the full AI Intelligence Studio.<br>• Wait for `[data-testid="analysis-summary-card"]` (`Boumahra Ahmed · F1 · 9.36 ha`), then smoothly scroll `[data-testid="stress-matrix"]` into view (`1.2s`).<br>• Smoothly scroll `[data-testid="strategy-comparison-grid"]` into view (`S1` 140d bare soil vs **`S2 Chickpea & Drip Forage Balanced Rotation`** 55d bare soil & 84% fit) (`1.7s`).<br>• Smoothly scroll to `[data-testid="rotation-timeline-S2_water_resilient"]` and click `[data-testid="timeline-node-S2_water_resilient-3"]` (`Vetch Forage`) (`1.2s`). | Full agronomic AI output tailored to real unverified field `F1`: scientific provenance transparency (`DEMO_PARCEL_UNVERIFIED`), 12-month bare-soil calendar, 7-axis spider radar, and seasonal planting schedule. |
| **5. Trilingual AR RTL Closing** | `26.0s – 28.5s` | Top Bar -> Arabic RTL -> Hero Lock | • Smoothly scroll back to top (`window.scrollTo({ top: 0, behavior: "smooth" })`). Wait `0.4s`.<br>• Click topbar Arabic radio pill (`[data-testid="dash-lang-ar"]`). Wait `1.0s` showing instant right-to-left Arabic translation (`القطعة التجريبية لفريق قالمة`, full RTL mirror).<br>• Hold `0.8s` clean final frame showing the `FELLAH TECH` logo + bilingual/trilingual field intelligence hero, then stop recording cleanly (`<= 28.5s`). | Demonstrates full accessibility for Algerian & North African farmers (`EN / FR / AR RTL`) alongside technical precision, ending cleanly on brand identity. |

---

## 5. Turnkey Playwright + FFmpeg Recording Reference Script

An AI coding/browser agent should use this production-tested workflow (adapt path/executable for the local OS):

```javascript
// record_demo.mjs — Run with Playwright + post-process with ffmpeg to guarantee <= 29.0s
import { chromium } from "playwright";
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const APP_URL = "https://fieldshift-planner.sidalidjeghbal.workers.dev/";
const RAW_DIR = "./tmp-video-raw";
const PROFILE_DIR = "./tmp-chromium-profile";
fs.rmSync(PROFILE_DIR, { recursive: true, force: true });
fs.mkdirSync(RAW_DIR, { recursive: true });
fs.mkdirSync(PROFILE_DIR, { recursive: true });

// Helper: install crisp animated pointer indicator so viewer sees every click cleanly
const CURSOR_SCRIPT = `
(() => {
  const dot = document.createElement('div');
  dot.id = '__demo_cursor';
  Object.assign(dot.style, {
    position: 'fixed', left: '-40px', top: '-40px', width: '20px', height: '20px',
    borderRadius: '9999px', border: '2px solid #0B3D2E', background: 'rgba(34,197,94,0.28)',
    boxShadow: '0 0 0 2px rgba(255,255,255,0.85), 0 4px 12px rgba(0,0,0,0.25)',
    pointerEvents: 'none', zIndex: '999999', transform: 'translate(-50%, -50%) scale(1)',
    transition: 'transform 120ms ease, background 120ms ease'
  });
  const mount = () => { if (!document.getElementById('__demo_cursor')) document.body?.appendChild(dot); };
  window.addEventListener('DOMContentLoaded', mount);
  if (document.body) mount();
  window.addEventListener('mousemove', (e) => {
    dot.style.left = e.clientX + 'px';
    dot.style.top = e.clientY + 'px';
  }, { passive: true });
  window.addEventListener('mousedown', () => {
    dot.style.transform = 'translate(-50%, -50%) scale(0.75)';
    dot.style.background = 'rgba(21,128,61,0.55)';
  }, { passive: true });
  window.addEventListener('mouseup', () => {
    dot.style.transform = 'translate(-50%, -50%) scale(1)';
    dot.style.background = 'rgba(34,197,94,0.28)';
  }, { passive: true });
})();
`;

async function smoothClick(page, locator, pauseAfterMs = 600) {
  await locator.waitFor({ state: "visible", timeout: 15000 });
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) {
    await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 18 });
    await page.waitForTimeout(140);
  }
  await locator.click();
  if (pauseAfterMs > 0) await page.waitForTimeout(pauseAfterMs);
}

async function smoothScrollTo(page, locator, pauseAfterMs = 1100) {
  await locator.waitFor({ state: "visible", timeout: 15000 });
  await locator.evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "center" }));
  if (pauseAfterMs > 0) await page.waitForTimeout(pauseAfterMs);
}

(async () => {
  const launchOpts = {
    headless: true,
    viewport: { width: 1920, height: 1080 },
    reducedMotion: "no-preference",
    args: ["--use-gl=angle", "--use-angle=swiftshader"], // remove if running with native GPU
  };

  // 1) PRE-WARM PERSISTENT PROFILE (not recorded) so Esri/NASA GIBS tiles + WebGL cache on disk
  const warmCtx = await chromium.launchPersistentContext(PROFILE_DIR, launchOpts);
  const warmPage = warmCtx.pages()[0] || (await warmCtx.newPage());
  await warmPage.goto(APP_URL, { waitUntil: "networkidle" });
  await warmPage.getByTestId("load-samples-btn").click();
  await warmPage.waitForTimeout(2000);
  await warmPage.getByTestId("inspector-edit-borders-btn").click();
  await warmPage.getByTestId("guelma-border-editor").waitFor({ state: "visible" });
  await warmPage.waitForTimeout(1800);
  await warmPage.getByTestId("quick-border-bouchegouf").click();
  await warmPage.waitForTimeout(1400);
  await warmPage.getByTestId("border-editor-back").click();
  await warmPage.waitForTimeout(800);
  await warmPage.locator('button[title="3D Inspect"]').first().click();
  await warmPage.getByTestId("fieldshift-prototype-root").waitFor({ state: "visible" });
  await warmPage.waitForTimeout(2200);
  await warmPage.evaluate(() => localStorage.clear()); // reset app state, keep Chromium HTTP disk cache
  await warmCtx.close();

  // 2) RECORDING PASS IN SAME PERSISTENT PROFILE (1920x1080 crisp 16:9 desktop)
  const recCtx = await chromium.launchPersistentContext(PROFILE_DIR, {
    ...launchOpts,
    recordVideo: { dir: RAW_DIR, size: { width: 1920, height: 1080 } },
  });
  await recCtx.addInitScript(CURSOR_SCRIPT);
  const page = recCtx.pages()[0] || (await recCtx.newPage());
  const ctxCreatedAt = Date.now();

  // Pre-load page cleanly before marking Beat 1 timestamp
  await page.goto(APP_URL, { waitUntil: "networkidle" });
  await page.getByTestId("guelma-farmer-dashboard").waitFor({ state: "visible" });
  await page.waitForTimeout(900);
  const beat1StartMs = Date.now() - ctxCreatedAt;

  // --- BEAT 1: Command Center & Multi-Parcel Overview (0.0s - 5.0s) ---
  await page.waitForTimeout(700);
  await smoothClick(page, page.getByTestId("load-samples-btn"), 1300);
  await smoothClick(page, page.locator('button[aria-label="Next parcel"]').first(), 1300);

  // --- BEAT 2: Precision Satellite CAD Editor (5.0s - 11.5s) ---
  await smoothClick(page, page.getByTestId("inspector-edit-borders-btn"), 900);
  await page.getByTestId("guelma-border-editor").waitFor({ state: "visible" });
  await smoothClick(page, page.getByTestId("quick-border-bouchegouf"), 1200);
  await smoothClick(page, page.getByRole("button", { name: "NDVI", exact: true }), 900);
  await smoothClick(page, page.getByRole("button", { name: /2D Ortho|3D Relief/i }).first(), 1300);
  await smoothClick(page, page.getByTestId("border-editor-back"), 600);

  // --- BEAT 3: 3D NASA GIBS Terrain Simulator (11.5s - 19.0s) ---
  await smoothClick(page, page.locator('button[title="3D Inspect"]').first(), 1300);
  await page.getByTestId("fieldshift-prototype-root").waitFor({ state: "visible" });
  await smoothClick(page, page.locator('button[data-layer="ndvi"]'), 700);
  await smoothClick(page, page.locator('button[data-layer="sm"]'), 900);
  await smoothClick(page, page.locator('button[data-scen="-25,2.5"]'), 900);
  await smoothClick(page, page.locator("#play"), 1600);
  await smoothClick(page, page.getByTestId("proto-back-dashboard"), 600);

  // --- BEAT 4: AI Rotation Intelligence on Real F1 Field (19.0s - 26.0s) ---
  await smoothClick(page, page.getByTestId("preview-demo-intelligence-btn"), 900);
  await page.getByTestId("analysis-summary-card").waitFor({ state: "visible" });
  await smoothScrollTo(page, page.getByTestId("stress-matrix"), 1200);
  await smoothScrollTo(page, page.getByTestId("strategy-comparison-grid"), 1600);
  await smoothScrollTo(page, page.getByTestId("rotation-timeline-S2_water_resilient"), 400);
  await smoothClick(page, page.getByTestId("timeline-node-S2_water_resilient-3"), 1100);

  // --- BEAT 5: Arabic RTL Accessibility Showcase & Closing Hold (26.0s - 28.5s) ---
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.waitForTimeout(500);
  await smoothClick(page, page.getByTestId("dash-lang-ar").first(), 1100);
  await page.waitForTimeout(800);

  const rawWebm = await page.video().path();
  await recCtx.close();

  // 3) FFmpeg Frame-Accurate Trim + Even Re-Timing so all 5 beats ALWAYS fit inside <= 28.5s H.264 MP4
  const trimStartSec = Math.max(0, beat1StartMs / 1000 - 0.15);
  const rawDur = Number(
    execSync(`ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${rawWebm}"`)
      .toString()
      .trim()
  );
  const usableDur = Math.max(1, rawDur - trimStartSec);
  const targetDur = Math.min(28.5, usableDur);
  const ptsFactor = targetDur / usableDur; // <= 1.0 speeds up slightly so Beat 5 is never truncated
  const outMp4 = "fellah-tech-nasa-demo-30s.mp4";
  execSync(
    `ffmpeg -y -i "${rawWebm}" -ss ${trimStartSec.toFixed(2)} -vf "setpts=${ptsFactor.toFixed(4)}*(PTS-STARTPTS),fps=30,scale=1920:1080" -t ${targetDur.toFixed(2)} -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -movflags +faststart "${outMp4}"`,
    { stdio: "inherit" }
  );

  const finalDur = execSync(
    `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${outMp4}"`
  ).toString().trim();
  console.log({ trimStartSec, rawDur, ptsFactor, finalDur });
})();
```

> **Important Post-Check for the Agent:** Verify both `rawDur` and `finalDur`. Notice the script passes `setpts=(targetDur/usableDur)*PTS` automatically so slow tile/network pauses are mildly compressed while keeping **all 5 beats including the Beat 5 Arabic RTL closing** cleanly inside **`<= 28.5 seconds`** (if `ptsFactor < 0.78`, trim extra `page.waitForTimeout(...)` pauses and re-run so motion stays calm).

---

## 6. Optional Concise Voiceover / Burned-In Captions (62 Words, 28s Pace)

If adding narration or crisp bottom-lower-third subtitles in `ffmpeg`, keep text minimal and aligned to each beat:

- **0–5s:** *"Welcome to FELLAH TECH — an Earth-observation crop rotation platform built for farmers in Guelma, Algeria."*
- **5–12s:** *"Trace exact farm borders over sub-meter satellite imagery, inspect NDVI vigor, and compute real terrain metrics."*
- **12–19s:** *"Explore 3D elevation draped with NASA GIBS soil moisture and stress-test rotations under future drought scenarios."*
- **19–26s:** *"Our AI engine recommends water-resilient legume-cereal rotations backed by 12-month bare-soil analytics."*
- **26–29s:** *"Fully bilingual and Arabic RTL ready — FELLAH TECH turns orbital data into field action."*

---

## 7. Pre-Submission Quality & NASA Space Apps Checklist

Before uploading the final `MP4` to YouTube / Google Drive / GitHub / OneDrive:
1. Run `ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 fellah-tech-nasa-demo-30s.mp4` and confirm duration is **strictly `<= 29.8` seconds**.
2. Inspect extracted frames (`0s`, `6s`, `13s`, `21s`, `27s`) to confirm zero blank tiles, zero console overlay banners, clear contrast, sharp **FELLAH TECH** logo, real `Bouchegouf` / `F1 Boumahra Ahmed` fitted crop borders, and complete Beat 5 ending.
3. Verify the hosting link is **publicly viewable in an incognito browser** with **no password, registration, or access request required**.
