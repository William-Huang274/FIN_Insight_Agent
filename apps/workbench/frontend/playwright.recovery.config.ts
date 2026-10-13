import { defineConfig, devices } from "playwright/test";

// Build first. API fixtures are synthetic; no BFF or Agent Server is started.
const port = Number(process.env.FINSIGHT_E2E_FRONTEND_PORT || "4183");
if (!Number.isInteger(port) || port < 1024 || port > 65535) {
  throw new Error("FINSIGHT_E2E_FRONTEND_PORT must be an integer from 1024 to 65535");
}
export default defineConfig({
  testDir: "./e2e",
  testMatch: ["project-research.spec.ts", "run-workspace.spec.ts", "workspace-navigation.spec.ts",
    "organization-projects.spec.ts", "project-resource-links.spec.ts", "resource-spaces.spec.ts", "project-workspace.spec.ts"],
  retries: 0,
  workers: 1,
  reporter: "list",
  outputDir: "test-results/recovery",
  use: { baseURL: `http://127.0.0.1:${port}`, screenshot: "only-on-failure", trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `node node_modules/vite/bin/vite.js preview --config vite.config.ts --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}/workspace`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
