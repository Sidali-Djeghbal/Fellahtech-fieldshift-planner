import fs from "node:fs";
import { chromium, defineConfig, devices } from "@playwright/test";

const fallbackChromePath = "/home/unknown/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
const defaultChromePath = chromium.executablePath();
const executablePath = fs.existsSync(defaultChromePath)
  ? undefined
  : fs.existsSync(fallbackChromePath)
    ? fallbackChromePath
    : undefined;

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 60_000,
  expect: {
    timeout: 15_000,
  },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:3100",
    trace: "on-first-retry",
    reducedMotion: "reduce",
    ...(executablePath ? { launchOptions: { executablePath } } : {}),
  },
  webServer: {
    command: "NEXT_PUBLIC_API_MODE=fixture npm run dev -- -p 3100 -H 127.0.0.1",
    url: "http://127.0.0.1:3100/dashboard",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "mobile-chromium",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
});
