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

    // 1. Dashboard + Quick Launch Demo (F1 DEMO_PARCEL_UNVERIFIED)
    await page.goto("/dashboard");
    await expect(page.getByTestId("fixture-mode-pill")).toBeVisible();

    const quickLaunch = page.getByTestId("quick-launch-demo");
    if (await quickLaunch.isVisible()) {
      await quickLaunch.click();
    }

    await expect(page.getByTestId("warning-DEMO_PARCEL_UNVERIFIED")).toBeVisible();
    await assertNoHorizontalOverflow(page, "/dashboard");
    await assertNoYellowOnLightContrastViolation(page, "/dashboard");

    // 2. Degraded mode simulation banner check (ADR-8)
    const degradedToggle = page.getByTestId("toggle-degraded-preview");
    await degradedToggle.click();
    await expect(page.getByTestId("degraded-mode-banner")).toBeVisible();
    await expect(page.getByTestId("degraded-mode-banner")).toContainText("analysis_4f9a8c120e3b");
    await expect(page.getByTestId("degraded-mode-banner")).toContainText("18420s");
    await degradedToggle.click();
    await expect(page.getByTestId("degraded-mode-banner")).toHaveCount(0);

    // 3. Navigate to Select Field & check PostGIS Guelma boundary + Setif 422
    await page.locator('a[href="/select-field"]:visible').first().click();
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

    // 7. Strategy Comparison -> Selection PATCH -> @media print check
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
    await page.getByTestId("lang-ar").click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");

    await page.getByTestId("lang-en").click();
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
          consoleErrors.push(text);
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
});
