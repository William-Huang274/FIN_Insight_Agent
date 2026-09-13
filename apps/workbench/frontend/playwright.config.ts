import { defineConfig, devices } from "playwright/test";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(frontendRoot, "../../..");
const productDataRoot = process.env.FINSIGHT_E2E_DATA_ROOT;
const effectiveDataRoot = productDataRoot || resolve(frontendRoot, "test-results", "no-data-root");
const frontendPort = Number(process.env.FINSIGHT_E2E_FRONTEND_PORT || "4173");
const backendPort = Number(process.env.FINSIGHT_E2E_BACKEND_PORT || "8765");

if (!Number.isInteger(frontendPort) || frontendPort < 1024 || frontendPort > 65535) {
  throw new Error("FINSIGHT_E2E_FRONTEND_PORT must be an integer from 1024 to 65535");
}
if (!Number.isInteger(backendPort) || backendPort < 1024 || backendPort > 65535) {
  throw new Error("FINSIGHT_E2E_BACKEND_PORT must be an integer from 1024 to 65535");
}

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 2,
  retries: 0,
  reporter: [["list"]],
  outputDir: "test-results",
  use: {
    baseURL: `http://127.0.0.1:${frontendPort}`,
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "chromium-desktop", use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "chromium-mobile", use: { ...devices["Pixel 7"] } },
  ],
  webServer: [
    {
      command: `python scripts/dev/run_workbench_backend.py --port ${backendPort}`,
      cwd: repoRoot,
      env: {
        ...process.env,
        FINSIGHT_DATA_ROOT: effectiveDataRoot,
      },
      url: `http://127.0.0.1:${backendPort}/api/health`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `node node_modules/vite/bin/vite.js --config vite.config.ts --host 127.0.0.1 --port ${frontendPort} --strictPort`,
      cwd: frontendRoot,
      url: `http://127.0.0.1:${frontendPort}/workspace`,
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
