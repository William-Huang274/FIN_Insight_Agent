import { defineConfig, devices } from 'playwright/test';
import { delimiter, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const state=process.env.FINSIGHT_LOCAL_STATE_ROOT;
const backendPort=Number(process.env.FINSIGHT_E2E_BACKEND_PORT||'8767');
if(!Number.isInteger(backendPort)||backendPort<1024||backendPort>65535)throw new Error('Invalid local backend port');
const repo=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const python=process.env.FINSIGHT_E2E_PYTHON||resolve(repo,'.venv','Scripts','python.exe');
const direct=process.env.FINSIGHT_E2E_DIRECT_BFF==='1';
const fixture=process.env.FIN_ASSET_WORKSPACE_FIXTURE?'asset_workspace_web':process.env.FIN_PROJECT_REPORT_SOURCE?'project_report_web':process.env.FIN_PROJECT_VERSIONS_FIXTURE?'project_versions_web':'project_library_web';
if(!state) throw new Error('Use a new isolated FINSIGHT_LOCAL_STATE_ROOT for each attempt.');
export default defineConfig({
  testDir:'./e2e',testMatch:['asset-conversation.spec.ts','task-asset-updates.spec.ts','asset-storage.spec.ts','source-captures.spec.ts','unified-assets.spec.ts','asset-workspace.spec.ts','project-library.spec.ts','project-sec.spec.ts','project-report.spec.ts','project-versions.spec.ts'],workers:1,retries:0,reporter:'list',
  outputDir:resolve(state,'browser'),
  use:{baseURL:direct?`http://127.0.0.1:${backendPort}`:'http://127.0.0.1:5173',screenshot:'only-on-failure',trace:'retain-on-failure'},
  projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],
  webServer:[
    {command:`"${python}" -m uvicorn tests.integration.fixtures.${fixture}:app --host 127.0.0.1 --port ${backendPort}`,cwd:repo,env:{...process.env,PYTHONPATH:[resolve(repo,'src'),repo,process.env.PYTHONPATH].filter(Boolean).join(delimiter)},url:`http://127.0.0.1:${backendPort}/auth/status`,reuseExistingServer:false,timeout:60000},
    ...(!direct?[{command:'node node_modules/vite/bin/vite.js --config vite.config.ts --host 127.0.0.1 --port 5173 --strictPort',env:{...process.env,FINSIGHT_E2E_BACKEND_PORT:String(backendPort)},url:'http://127.0.0.1:5173/workspace',reuseExistingServer:false,timeout:60000}]:[]),
  ],
});
