/** Capture actual local product pages. No fixture substitution or model runs.
 * node scripts/dev/capture_product_screenshots.cjs --base-url http://127.0.0.1:8793 --thread UUID --output-directory NEW_DIR
 */
const { parseArgs } = require('node:util');
const { resolve } = require('node:path');
const { mkdirSync, writeFileSync } = require('node:fs');
const { chromium } = require('../../apps/workbench/frontend/node_modules/playwright');

async function main() {
  const { values } = parseArgs({ options: {
    'base-url': { type: 'string' }, thread: { type: 'string' },
    'output-directory': { type: 'string' },
  }});
  if (!values['base-url'] || !values.thread || !values['output-directory']) {
    throw new Error('Required: --base-url, --thread, --output-directory (new directory)');
  }
  const base = new URL(values['base-url']);
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(base.hostname) || base.username || base.password) {
    throw new Error('Capture requires a local workbench URL without credentials.');
  }
  const output = resolve(values['output-directory']);
  mkdirSync(output); // Fail if prior evidence exists.
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  const errors = [], writes = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', route => {
    if (['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) return route.continue();
    writes.push(route.request().method()); return route.abort();
  });
  try {
    const session = `/workspace/session?thread=${encodeURIComponent(values.thread)}`;
    for (const [name, path, ready] of [
      ['research-start', '/workspace', '这次，你想弄清楚什么？'],
      ['research-map', session + '&view=graph&level=overview', '报告总览'],
      ['research-studio', '/workspace?view=studio', '保存为新版本'],
      ['research-runtime', session + '&view=activity', '研究中的节点'],
    ]) {
      const sessionsLoaded = page.waitForResponse(response => new URL(response.url()).pathname.endsWith('/research-sessions') && response.request().method() === 'GET');
      await page.goto(new URL(path, base).href);
      await sessionsLoaded;
      await page.getByText(ready, { exact: true }).first().waitFor();
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: resolve(output, `${name}.png`), animations: 'disabled' });
    }
    writeFileSync(resolve(output, 'capture.json'), JSON.stringify({ captured_at: new Date().toISOString(),
      viewport: { width: 1600, height: 1000 }, synthetic: false, model_calls: 0, errors, blocked_writes: writes }, null, 2));
    if (errors.length || writes.length) throw new Error('Capture had page errors or blocked writes; inspect capture.json.');
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
