import { expect, Page, test } from "@playwright/test";

async function assertNoHorizontalOverflow(page: Page, routeLabel: string) {
  const { scrollWidth, innerWidth } = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
  }));
  expect(
    scrollWidth,
    `Horizontal overflow detected on ${routeLabel}: scrollWidth=${scrollWidth} > innerWidth=${innerWidth}`
  ).toBeLessThanOrEqual(innerWidth);
}

async function assertNoYellowOnLightContrastViolation(page: Page, routeLabel: string) {
  const violations = await page.evaluate(() => {
    function parseRgb(str: string): [number, number, number, number] | null {
      const m = str.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
      if (!m) return null;
      return [Number(m[1]), Number(m[2]), Number(m[3]), m[4] ? Number(m[4]) : 1];
    }

    function effectiveBg(el: Element | null): [number, number, number] {
      let cur: Element | null = el;
      while (cur) {
        const bg = parseRgb(getComputedStyle(cur).backgroundColor);
        if (bg && bg[3] > 0.2) {
          return [bg[0], bg[1], bg[2]];
        }
        cur = cur.parentElement;
      }
      return [7, 23, 63];
    }

    const found: string[] = [];
    const nodes = document.querySelectorAll("body *");
    nodes.forEach((node) => {
      if ((node as HTMLElement).getClientRects().length === 0) return;
      const style = getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden") return;
      const fg = parseRgb(style.color);
      if (!fg) return;
      const isYellow = fg[0] > 210 && fg[1] > 220 && fg[2] < 60;
      if (!isYellow) return;

      const bg = effectiveBg(node);
      const isLightBg = bg[0] > 200 && bg[1] > 200 && bg[2] > 200;
      if (isLightBg) {
        found.push(`${node.tagName}:${(node.textContent || "").trim().slice(0, 30)}`);
      }
    });
    return found;
  });

  expect(
    violations,
    `#EAFE07 yellow text on light background found on ${routeLabel}`
  ).toEqual([]);
}

test.describe("Field Shift Guelma MVP E2E Flow", () => {
  test("traverses all 5 pages, validates constraints, degraded replay, print brief, and RTL without console errors or overflow", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];

    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        // MapLibre GL can emit benign WebGL initialization warnings in headless software mode
        // before triggering the clean SVG orbital fallback.
        if (!/webgl|Failed to initialize WebGL|maplibre/i.test(text)) {
          consoleErrors.push(text);
        }
      }
    });

    // 1. Verify /dashboard maps cleanly to the Guelma Command Center (no legacy Purwokerto fallback)
    await page.goto("/dashboard");
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/dashboard");

    // 2. Navigate to Select Field & Quick Launch Demo (F1 DEMO_PARCEL_UNVERIFIED)
    await page.goto("/select-field");
    await expect(page.getByTestId("fixture-mode-pill")).toBeVisible();

    const quickLaunch = page.getByTestId("quick-launch-demo");
    if (await quickLaunch.isVisible()) {
      await quickLaunch.click();
    }

    await expect(page.getByTestId("warning-DEMO_PARCEL_UNVERIFIED")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/select-field");
    await assertNoYellowOnLightContrastViolation(page, "/select-field");

    // 3. Check PostGIS Guelma boundary + Setif 422
    await expect(page).toHaveURL(/\/select-field/);
    await expect(page.getByTestId("boundary-status-pill")).toBeVisible();

    await page.getByTestId("load-setif-outside-btn").click();
    await page.getByTestId("save-parcel-continue-btn").click();
    await expect(page.getByTestId("api-error-OUTSIDE_DEMO_BOUNDARY")).toBeVisible();

    // 4. Guest limit enforcement check (403 GUEST_LIMIT_REACHED on 4th farm)
    const farmNameInput = page.getByPlaceholder("New Farm Name");
    const createFarmBtn = page.getByTestId("create-farm-btn");

    await farmNameInput.fill("Bouchegouf Estate");
    await createFarmBtn.click();
    await expect(page.getByRole("button", { name: /Bouchegouf Estate/ })).toBeVisible();

    await farmNameInput.fill("Heliopolis Annex");
    await createFarmBtn.click();
    await expect(page.getByRole("button", { name: /Heliopolis Annex/ })).toBeVisible();

    await farmNameInput.fill("Tamlouka Over-Quota");
    await createFarmBtn.click();
    await expect(page.getByTestId("api-error-GUEST_LIMIT_REACHED")).toBeVisible();
    await expect(
      page.getByRole("button", { name: /Create Free Account & Claim Data/i })
    ).toBeVisible();

    // 5. Select verified Seybouse parcel preset & save -> /farm-profile
    await page.getByTestId("preset-seybouse").click();
    await expect(page.getByTestId("boundary-status-pill")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/select-field");
    await page.getByTestId("save-parcel-continue-btn").click();

    // 6. Farm Profile -> USDA texture converter -> submit analysis -> /comparison
    await expect(page).toHaveURL(/\/farm-profile/);
    await expect(page.getByTestId("weights-sum-badge")).toContainText("100 / 100");
    await assertNoHorizontalOverflow(page, "/farm-profile");

    await page.getByTestId("usda-converter-btn").click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await page.getByRole("button", { name: /Apply Derived Soil Type/i }).click();
    await expect(page.getByRole("dialog")).toHaveCount(0);

    await page.getByTestId("run-analysis-submit-btn").click();
    await expect(page).toHaveURL(/\/comparison\?analysisId=analysis_[0-9a-f]{12}/, {
      timeout: 20_000,
    });

    // 7. Strategy Comparison + Degraded mode banner toggle (ADR-8) -> Selection PATCH -> @media print check
    const degradedToggle = page.getByTestId("toggle-degraded-preview");
    await degradedToggle.click();
    await expect(page.getByTestId("degraded-mode-banner")).toBeVisible();
    await degradedToggle.click();
    await expect(page.getByTestId("degraded-mode-banner")).toHaveCount(0);

    await expect(page.getByTestId("strategy-card-S1_baseline_cereal")).toBeVisible();
    await expect(page.getByTestId("strategy-card-S2_water_resilient")).toBeVisible();
    await expect(page.getByTestId("strategy-card-S3_income_diversified")).toBeVisible();

    await page.getByTestId("select-strategy-S1_baseline_cereal").click();
    await expect(page.getByTestId("selected-badge-S1_baseline_cereal")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/comparison");
    await assertNoYellowOnLightContrastViolation(page, "/comparison");

    await page.emulateMedia({ media: "print" });
    await expect(page.getByTestId("printable-brief")).toBeVisible();
    await assertNoYellowOnLightContrastViolation(page, "/comparison@print");
    await page.emulateMedia({ media: "screen" });

    // 8. Evidence Ledger -> Dual-source toggles
    await page.locator('a[href="/evidence"]:visible').first().click();
    await expect(page).toHaveURL(/\/evidence/);
    await expect(page.getByTestId("evidence-card-farmer_input").first()).toBeVisible();
    await expect(page.getByTestId("evidence-card-dataset").first()).toBeVisible();

    await page.getByTestId("filter-farmer-input").click();
    await expect(page.getByTestId("evidence-card-farmer_input").first()).toBeVisible();
    await expect(page.getByTestId("evidence-card-dataset")).toHaveCount(0);

    await page.getByTestId("filter-dataset").click();
    await expect(page.getByTestId("evidence-card-dataset").first()).toBeVisible();
    await assertNoHorizontalOverflow(page, "/evidence");

    // 9. Trilingual RTL Switcher check (en -> ar -> en)
    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

    await page.getByTestId("dash-lang-en").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

    expect(pageErrors, "Uncaught page errors detected").toEqual([]);
    expect(consoleErrors, "Console errors detected").toEqual([]);
  });

  test("completes full Guelma farmer workflow: empty dashboard -> draw borders -> save farm info -> persist -> edit -> simulate -> remove & RTL", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    const failedLocalRequests: string[] = [];

    page.on("pageerror", (err) => {
      pageErrors.push(err.message);
    });
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          !/webgl|Failed to initialize WebGL|maplibre|ERR_NAME_NOT_RESOLVED|Failed to fetch|terrarium|arcgisonline|gibs|demotiles/i.test(
            text
          )
        ) {
          const srcUrl = msg.location()?.url || "";
          const isExternalTileAbort =
            /ERR_FAILED/i.test(text) && srcUrl !== "" && !srcUrl.startsWith("http://127.0.0.1:3100");
          if (!isExternalTileAbort) {
            consoleErrors.push(`${text}${srcUrl ? ` [${srcUrl}]` : ""}`);
          }
        }
      }
    });
    page.on("response", (res) => {
      if (res.url().startsWith("http://127.0.0.1:3100") && res.status() >= 400) {
        failedLocalRequests.push(`${res.status()} ${res.url()}`);
      }
    });

    // Clear workspace storage so we always verify clean initial landing state
    await page.addInitScript(() => {
      try {
        if (!sessionStorage.getItem("__e2e_reset_done")) {
          localStorage.removeItem("fieldshift.guelma.workspace.v1");
          sessionStorage.setItem("__e2e_reset_done", "1");
        }
      } catch {
        /* ignore */
      }
    });

    await page.goto("/");
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();
    await expect(page.getByTestId("empty-workspace-card")).toBeVisible();
    await expect(page.getByTestId("kpi-farms")).toHaveText("0");
    await expect(page.getByTestId("kpi-fields")).toHaveText("0");
    await assertNoHorizontalOverflow(page, "/ (dashboard empty)");

    // Trilingual RTL check on Dashboard (EN -> AR -> EN)
    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.getByTestId("dash-lang-en").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

    // 1. Open interactive border selection map
    await page.getByTestId("empty-add-farm-btn").click();
    await expect(page.getByTestId("guelma-border-editor")).toBeVisible();

    // 2. Search & jump to Bouchegouf across 34 Guelma communes
    await page.getByTestId("commune-search-input").fill("Bouchegouf");
    await page.getByTestId("commune-dropdown").getByRole("button", { name: /Bouchegouf/i }).first().click();

    // 3. Draw 4 corners interactively on canvas (SVG fallback or MapLibre canvas)
    const svgCanvas = page.getByTestId("border-editor-svg-canvas");
    if (await svgCanvas.isVisible()) {
      const box = await svgCanvas.boundingBox();
      if (box) {
        await page.mouse.click(box.x + box.width * 0.35, box.y + box.height * 0.35);
        await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.35);
        await page.mouse.click(box.x + box.width * 0.55, box.y + box.height * 0.58);
        await page.mouse.click(box.x + box.width * 0.35, box.y + box.height * 0.58);
      }
      await page.getByTestId("cad-close-poly-btn").click();
    } else {
      await page.getByTestId("quick-border-bouchegouf").click();
    }

    await expect(page.getByTestId("save-my-farm-btn")).toBeEnabled();
    await page.getByTestId("save-my-farm-btn").click();

    // 4. Complete Farm & Field Info Onboarding Modal
    await expect(page.getByTestId("farm-field-info-modal")).toBeVisible();
    await page.getByTestId("input-farm-name").fill("Domaine Bouchegouf E2E");
    await page.getByTestId("input-field-name").fill("Parcelle Nord A1");
    await page.getByTestId("soil-mode-known").click();
    await page.getByTestId("submit-farm-field-form").click();

    // 5. Verify farm & field rendered cleanly on Dashboard and persist across reload
    await expect(page.getByTestId("kpi-farms")).toHaveText("1");
    await expect(page.getByTestId("kpi-fields")).toHaveText("1");
    await expect(page.getByTestId("field-card-F-1")).toContainText("Parcelle Nord A1");

    await page.reload();
    await expect(page.getByTestId("field-card-F-1")).toContainText("Parcelle Nord A1");
    await assertNoHorizontalOverflow(page, "/ (dashboard populated)");

    // 6. Edit Field Info
    await page.getByTestId("edit-info-F-1").click();
    await expect(page.getByTestId("farm-field-info-modal")).toBeVisible();
    await page.getByTestId("input-field-name").fill("Parcelle Nord A1 Amended");
    await page.getByTestId("submit-farm-field-form").click();
    await expect(page.getByTestId("field-card-F-1")).toContainText("Parcelle Nord A1 Amended");

    // 7. Add a second field to the existing farm
    await page.getByTestId("add-field-farm-farm_1").click();
    await expect(page.getByTestId("guelma-border-editor")).toBeVisible();
    await page.getByTestId("quick-border-heliopolis").click();
    await page.getByTestId("save-my-farm-btn").click();
    await page.getByTestId("input-field-name").fill("Coteau Sud B2");
    await page.getByTestId("submit-farm-field-form").click();
    await expect(page.getByTestId("kpi-fields")).toHaveText("2");

    // 8. Inspect & Simulate saved parcel in FieldShift 3D GIBS studio, then return
    await page.getByTestId("inspect-field-F-1").click();
    await expect(page.getByTestId("fieldshift-prototype-root")).toBeVisible();
    const mobLabBtn = page.locator('[data-mob="lab"]');
    if (await mobLabBtn.isVisible()) {
      await mobLabBtn.click();
    }
    await page.locator('[data-prio="water"]').click();
    await expect(page.locator('[data-prio="water"]')).toHaveAttribute("aria-pressed", "true");
    await page.getByTestId("proto-back-dashboard").click();
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();

    // 9. Remove second field and confirm KPI drops back to 1
    await page.getByTestId("remove-field-F-2").click();
    await expect(page.getByTestId("confirm-delete-modal")).toBeVisible();
    await page.getByTestId("confirm-delete-btn").click();
    await expect(page.getByTestId("kpi-fields")).toHaveText("1");

    expect(pageErrors, "Uncaught page errors on /").toEqual([]);
    expect(consoleErrors, "Console errors on /").toEqual([]);
    expect(failedLocalRequests, "Failed local asset requests on /").toEqual([]);
  });

  test("executes AI crop-rotation analysis inside Liquid Glass dashboard, persists strategy selection, explores insights/evidence/quality without overflow", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];

    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          !/webgl|Failed to initialize WebGL|maplibre|ERR_NAME_NOT_RESOLVED|Failed to fetch|terrarium|arcgisonline|gibs|demotiles/i.test(
            text
          )
        ) {
          const srcUrl = msg.location()?.url || "";
          const isExternalTileAbort =
            /ERR_FAILED/i.test(text) && srcUrl !== "" && !srcUrl.startsWith("http://127.0.0.1:3100");
          if (!isExternalTileAbort) {
            consoleErrors.push(`${text}${srcUrl ? ` [${srcUrl}]` : ""}`);
          }
        }
      }
    });

    await page.addInitScript(() => {
      try {
        if (!sessionStorage.getItem("__e2e_ai_reset")) {
          localStorage.removeItem("fieldshift.guelma.workspace.v1");
          localStorage.removeItem("fieldshift-app-storage");
          sessionStorage.setItem("__e2e_ai_reset", "1");
        }
      } catch {
        /* ignore */
      }
    });

    await page.goto("/");
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();
    await expect(page.getByTestId("guelma-overview-map")).toBeVisible();
    await expect(page.getByTestId("map-fit-extent-btn")).toBeVisible();
    await expect(page.getByTestId("empty-workspace-card")).toBeVisible();

    await page.getByTestId("load-samples-btn").click();
    await expect(page.getByTestId("kpi-fields")).toHaveText("4");
    await expect(page.getByTestId("parcel-inspector-panel")).toContainText(
      "Seybouse Alluvial Plain"
    );

    // Selecting a row in the table synchronizes the Field Inspector panel
    await page.getByTestId("field-card-G-2").click();
    await expect(page.getByTestId("parcel-inspector-panel")).toContainText("Heliopolis Hillside");
    await page.getByTestId("field-card-G-1").click();
    await expect(page.getByTestId("parcel-inspector-panel")).toContainText(
      "Seybouse Alluvial Plain"
    );
    await page.getByTestId("map-fit-extent-btn").click();

    // Open and close Workstation Settings drawer cleanly
    const desktopSettingsBtn = page.getByTestId("header-settings-btn");
    if (await desktopSettingsBtn.isVisible()) {
      await desktopSettingsBtn.click();
    } else {
      await page.getByTestId("header-settings-mobile-btn").click();
    }
    await expect(page.getByTestId("settings-drawer")).toBeVisible();
    await expect(page.getByTestId("reset-workspace-btn")).toBeVisible();
    await page.getByTestId("close-settings-drawer-btn").click();
    await expect(page.getByTestId("settings-drawer")).toHaveCount(0);

    // 1. Configure & Launch AI Crop-Rotation Analysis directly from Dashboard
    await page.getByTestId("run-ai-analysis-btn").click();
    await expect(page.getByTestId("analysis-runner-modal")).toBeVisible();
    await page.getByTestId("submit-ai-analysis-btn").click();

    // 2. Verify full ML Result surfaces render cleanly
    await expect(page.getByTestId("analysis-summary-card")).toBeVisible({
      timeout: 20_000,
    });
    await expect(page.getByTestId("analysis-status-pill")).toBeVisible();
    await expect(page.getByTestId("field-insights-timeline")).toBeVisible();
    await expect(page.getByTestId("stress-matrix")).toBeVisible();
    await expect(page.getByTestId("strategy-comparison-grid")).toBeVisible();
    await expect(page.getByTestId("recommended-badge-S2_water_resilient")).toBeVisible();
    await expect(page.getByTestId("baseline-badge-S1_baseline_cereal")).toBeVisible();

    // 3. Persist Strategy Selection & inspect Timeline + Scientific Evidence + Data Quality
    await page.getByTestId("select-strategy-S1_baseline_cereal").click();
    await expect(page.getByTestId("intelligence-toast")).toBeVisible();
    await expect(page.getByTestId("selection-status-S1_baseline_cereal")).toContainText(
      /Selected Plan/i
    );

    await page.getByTestId("explanation-tab-evidence").click();
    await expect(page.getByTestId("evidence-item-farmer_input").first()).toBeVisible();

    await page.getByTestId("strategy-card-S2_water_resilient").click();
    await expect(page.getByTestId("evidence-item-dataset").first()).toBeVisible();

    await page.getByTestId("explanation-tab-risks").click();
    await expect(page.getByTestId("requested-crops-section")).toBeVisible();
    await expect(page.getByTestId("data-quality-farm")).toBeVisible();
    await expect(page.getByTestId("data-quality-field")).toBeVisible();

    // 4. Verify Plain Language toggle & RTL Arabic mode without overflow
    await page.getByTestId("toggle-plain-mode-btn").click();
    await assertNoHorizontalOverflow(page, "/ (AI Intelligence LTR)");

    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await assertNoHorizontalOverflow(page, "/ (AI Intelligence AR RTL)");

    await page.getByTestId("dash-lang-en").click();

    expect(pageErrors, "Uncaught page errors during AI dashboard flow").toEqual([]);
    expect(consoleErrors, "Console errors during AI dashboard flow").toEqual([]);
  });

  test("Light/Dark mode system listener, quick toggle, settings selector, and zero-FOUC reload persistence", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];
    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.emulateMedia({ colorScheme: "light" });

    // Record early dataset.theme at DOMContentLoaded (before/at hydration) to verify zero FOUC on reload
    await page.addInitScript(() => {
      try {
        if (!sessionStorage.getItem("__theme_test_reset")) {
          localStorage.removeItem("fieldshift-planner-v32");
          localStorage.removeItem("fieldshift.guelma.workspace.v1");
          sessionStorage.setItem("__theme_test_reset", "1");
        }
        document.addEventListener("DOMContentLoaded", () => {
          (window as unknown as { __domLoadedTheme?: string }).__domLoadedTheme =
            document.documentElement.dataset.theme;
        });
      } catch {
        /* ignore */
      }
    });

    await page.goto("/");
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();

    // 1. Default system preference resolves to Light Mode
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await expect(page.locator("html")).not.toHaveClass(/\bdark\b/);
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(238, 243, 239)");
    await assertNoHorizontalOverflow(page, "/ (Light Mode default)");

    // 2. While in system mode, live OS prefers-color-scheme change updates theme immediately
    await page.emulateMedia({ colorScheme: "dark" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("html")).toHaveClass(/\bdark\b/);
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(18, 23, 19)");

    await page.emulateMedia({ colorScheme: "light" });
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");

    // 3. Quick toggle on desktop rail (or mobile settings drawer) switches Light <-> Dark cleanly
    const railThemeBtn = page.getByTestId("rail-theme-btn");
    if (await railThemeBtn.isVisible()) {
      await railThemeBtn.click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      await railThemeBtn.click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    } else {
      await page.getByTestId("header-settings-mobile-btn").click();
      await expect(page.getByTestId("settings-drawer")).toBeVisible();
      await page.getByTestId("settings-theme-dark").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
      await page.getByTestId("settings-theme-light").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
      await page.getByTestId("close-settings-drawer-btn").click();
    }

    // 4. Settings Drawer 3-way selector persists Dark Mode across reload with zero FOUC
    const desktopSettingsBtn = page.getByTestId("header-settings-btn");
    if (await desktopSettingsBtn.isVisible()) {
      await desktopSettingsBtn.click();
    } else {
      await page.getByTestId("header-settings-mobile-btn").click();
    }
    await expect(page.getByTestId("settings-drawer")).toBeVisible();

    // After explicit quick toggles in step 3, active preference is Light
    await expect(page.getByTestId("settings-theme-light")).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("settings-theme-dark").click();
    await expect(page.getByTestId("settings-theme-dark")).toHaveAttribute("aria-checked", "true");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");

    await page.reload();
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();
    const domLoadedTheme = await page.evaluate(
      () => (window as unknown as { __domLoadedTheme?: string }).__domLoadedTheme
    );
    expect(domLoadedTheme, "Blocking head script must set data-theme=dark before paint").toBe(
      "dark"
    );
    await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
    await expect(page.locator("body")).toHaveCSS("background-color", "rgb(18, 23, 19)");
    await assertNoHorizontalOverflow(page, "/ (Dark Mode persisted after reload)");

    // Return to Light/System via Settings Drawer
    if (await desktopSettingsBtn.isVisible()) {
      await desktopSettingsBtn.click();
    } else {
      await page.getByTestId("header-settings-mobile-btn").click();
    }
    await page.getByTestId("settings-theme-light").click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await page.getByTestId("settings-theme-system").click();
    await expect(page.getByTestId("settings-theme-system")).toHaveAttribute("aria-checked", "true");
    await page.getByTestId("close-settings-drawer-btn").click();

    expect(pageErrors, "Uncaught page errors during theme test").toEqual([]);
    expect(consoleErrors, "Console errors during theme test").toEqual([]);
  });

  test("verifies EN / FR / AR translations, RTL layout, 3D prototype, AuthModal, and all studio routes without overflow", async ({
    page,
  }) => {
    const pageErrors: string[] = [];
    const consoleErrors: string[] = [];

    page.on("pageerror", (err) => pageErrors.push(err.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const text = msg.text();
        if (
          !/webgl|Failed to initialize WebGL|maplibre|ERR_NAME_NOT_RESOLVED|Failed to fetch|terrarium|arcgisonline|gibs|demotiles/i.test(
            text
          )
        ) {
          const srcUrl = msg.location()?.url || "";
          const isExternalTileAbort =
            /ERR_FAILED/i.test(text) && srcUrl !== "" && !srcUrl.startsWith("http://127.0.0.1:3100");
          if (!isExternalTileAbort) {
            consoleErrors.push(`${text}${srcUrl ? ` [${srcUrl}]` : ""}`);
          }
        }
      }
    });

    await page.addInitScript(() => {
      try {
        if (!sessionStorage.getItem("__e2e_i18n_reset")) {
          localStorage.removeItem("fieldshift.guelma.workspace.v1");
          localStorage.removeItem("fieldshift-app-storage");
          sessionStorage.setItem("__e2e_i18n_reset", "1");
        }
      } catch {
        /* ignore */
      }
    });

    // 1. Dashboard / FR -> AR RTL + 3D Prototype
    await page.goto("/");
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();
    await page.getByTestId("load-samples-btn").click();
    await expect(page.getByTestId("kpi-fields")).toHaveText("4");

    await page.getByTestId("dash-lang-fr").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
    await assertNoHorizontalOverflow(page, "/ (FR)");

    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await assertNoHorizontalOverflow(page, "/ (AR RTL)");

    await page.getByTestId("inspect-field-G-1").click();
    await expect(page.getByTestId("fieldshift-prototype-root")).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.getByTestId("proto-back-dashboard").click();
    await expect(page.getByTestId("guelma-farmer-dashboard")).toBeVisible();

    // 2. /select-field + quick launch in FR & AR RTL
    await page.goto("/select-field");
    const quickLaunch = page.getByTestId("quick-launch-demo");
    if (await quickLaunch.isVisible()) {
      await quickLaunch.click();
    }
    await expect(page.getByTestId("warning-DEMO_PARCEL_UNVERIFIED")).toBeVisible();
    await expect(page.getByTestId("boundary-status-pill")).toBeVisible();
    await page.getByTestId("dash-lang-fr").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await assertNoHorizontalOverflow(page, "/select-field (FR)");
    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await assertNoHorizontalOverflow(page, "/select-field (AR RTL)");

    // 3. /farm-profile FR & AR localized weights + presets + submit to /comparison
    await page.locator('a[href="/farm-profile"]:visible').first().click();
    await expect(page).toHaveURL(/\/farm-profile/);
    await expect(page.getByTestId("weights-sum-badge")).toBeVisible();
    await page.getByTestId("dash-lang-fr").click();
    await expect(page.getByRole("button", { name: "Résilience Hydrique" })).toBeVisible();
    await expect(page.locator("body")).toContainText("Économie d'eau");
    await assertNoHorizontalOverflow(page, "/farm-profile (FR)");

    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await expect(page.getByRole("button", { name: "مقاومة الجفاف والمياه" })).toBeVisible();
    await expect(page.locator("body")).toContainText("توفير المياه");
    await assertNoHorizontalOverflow(page, "/farm-profile (AR RTL)");

    await page.getByTestId("run-analysis-submit-btn").click();
    await expect(page).toHaveURL(/\/comparison\?analysisId=analysis_[0-9a-f]{12}/, {
      timeout: 20_000,
    });

    // 4. /comparison in AR RTL & FR
    await expect(page.getByTestId("strategy-card-S2_water_resilient")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/comparison (AR RTL)");
    await page.getByTestId("dash-lang-fr").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "fr");
    await assertNoHorizontalOverflow(page, "/comparison (FR)");

    // 5. /evidence + AuthModal in FR/AR + cleanup back to EN
    await page.locator('a[href="/evidence"]:visible').first().click();
    await expect(page).toHaveURL(/\/evidence/);
    await expect(page.getByTestId("evidence-card-farmer_input").first()).toBeVisible();
    await assertNoHorizontalOverflow(page, "/evidence (FR)");
    await page.getByTestId("dash-lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await assertNoHorizontalOverflow(page, "/evidence (AR RTL)");

    const headerAuthBtn = page.getByTestId("header-auth-btn");
    if (await headerAuthBtn.isVisible()) {
      await headerAuthBtn.click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
    }

    await page.getByTestId("dash-lang-en").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

    expect(pageErrors, "Uncaught page errors during trilingual E2E flow").toEqual([]);
    expect(consoleErrors, "Console errors during trilingual E2E flow").toEqual([]);
  });
});
