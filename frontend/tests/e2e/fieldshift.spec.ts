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

  test("renders the TSX FieldShift workspace at the root route with full interactivity and zero ARD branding", async ({
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
        if (!/webgl|Failed to initialize WebGL|maplibre|ERR_NAME_NOT_RESOLVED|Failed to fetch|terrarium|arcgisonline|gibs/i.test(text)) {
          consoleErrors.push(text);
        }
      }
    });
    page.on("response", (res) => {
      if (res.url().startsWith("http://127.0.0.1:3100") && res.status() >= 400) {
        failedLocalRequests.push(`${res.status()} ${res.url()}`);
      }
    });

    await page.goto("/#still");
    await expect(page.getByTestId("fieldshift-prototype-root")).toBeVisible();
    await expect(page).toHaveTitle("FieldShift — Algeria");
    await expect(page.locator(".brand-title")).toContainText("FieldShift");
    await expect(page.locator("#map")).toBeVisible();

    const bodyText = await page.locator("body").innerText();
    expect(bodyText).not.toContain("ARD");

    // Open mobile Field drawer if viewport is mobile
    const mobFieldBtn = page.locator('[data-mob="field"]');
    if (await mobFieldBtn.isVisible()) {
      await mobFieldBtn.click();
    }
    await expect(page.locator("#f-name")).toContainText("Tidjelabine");

    // Switch preset to Guelma
    const guelmaPill = page.locator('[data-preset="guelma"]');
    if (await guelmaPill.isVisible()) {
      await guelmaPill.click();
    } else {
      await page.locator("#preset-select").selectOption("guelma");
    }
    await expect(page.locator("#f-name")).toContainText("Seybouse");

    // Switch to Rotation Lab (on mobile via dock), change priority & open Compare + Audit
    const mobLabBtn = page.locator('[data-mob="lab"]');
    if (await mobLabBtn.isVisible()) {
      await mobLabBtn.click();
    }
    await page.locator('[data-prio="water"]').click();
    await expect(page.locator('[data-prio="water"]')).toHaveAttribute("aria-pressed", "true");

    const mobCompareBtn = page.locator('[data-mob="compare"]');
    if (await mobCompareBtn.isVisible()) {
      await mobCompareBtn.click();
    } else {
      await page.locator("#tab-compare").click();
    }
    await expect(page.locator("#cmp-title")).toContainText("Guelma");

    // Open & close Guide modal
    await page.locator("#guide-btn").click();
    await expect(page.locator("#guide-modal")).toHaveClass(/open/);
    await page.locator("#guide-close").click();
    await expect(page.locator("#guide-modal")).not.toHaveClass(/open/);

    // Trilingual RTL switch check
    await page.locator('[data-lang="ar"]').click();
    await expect(page.locator("html")).toHaveAttribute("lang", "ar");
    await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
    await page.locator('[data-lang="en"]').click();
    await expect(page.locator("html")).toHaveAttribute("lang", "en");
    await expect(page.locator("html")).toHaveAttribute("dir", "ltr");

    await assertNoHorizontalOverflow(page, "/");
    expect(pageErrors, "Uncaught page errors on /").toEqual([]);
    expect(consoleErrors, "Console errors on /").toEqual([]);
    expect(failedLocalRequests, "Failed local asset requests on /").toEqual([]);
  });
});
