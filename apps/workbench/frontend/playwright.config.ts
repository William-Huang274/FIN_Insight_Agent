import { defineConfig, devices } from "playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, "../../..");
const productDataRoot = process.env.FINSIGHT_E2E_DATA_ROOT;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: "http://127.0.0.1:5173",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: "python scripts/dev/run_workbench_backend.py",
      cwd: repoRoot,
      env: {
        ...process.env,
        ...(productDataRoot ? { FINSIGHT_DATA_ROOT: productDataRoot } : {}),
      },
      url: "http://127.0.0.1:8765/api/health",
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: "node node_modules/vite/bin/vite.js --config vite.config.ts",
      cwd: frontendRoot,
      url: "http://127.0.0.1:5173/workspace",
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
