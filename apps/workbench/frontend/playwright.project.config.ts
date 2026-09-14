import { defineConfig, devices } from 'playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const state=process.env.FINSIGHT_LOCAL_STATE_ROOT;
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const python=resolve(repo,'.venv','Scripts','python.exe');
if(!state) throw new Error('Use a new isolated FINSIGHT_LOCAL_STATE_ROOT for each attempt.');
export default defineConfig({
  testDir:'./e2e',testMatch:'project-library.spec.ts',workers:1,retries:0,reporter:'list',
  outputDir:resolve(state,'browser'),
  use:{baseURL:'http://127.0.0.1:5173',screenshot:'only-on-failure',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
  webServer:[
    {command:`"${python}" -m uvicorn tests.qualification.fixtures.project_library_web:app --host 127.0.0.1 --port 8767`,cwd:repo,url:'http://127.0.0.1:8767/auth/status',reuseExistingServer:false,timeout:60000},
    {command:'node node_modules/vite/bin/vite.js --config vite.config.ts --host 127.0.0.1 --port 5173 --strictPort',env:{...process.env,FINSIGHT_E2E_BACKEND_PORT:'8767'},url:'http://127.0.0.1:5173/workspace',reuseExistingServer:false,timeout:60000},
  ],
});
