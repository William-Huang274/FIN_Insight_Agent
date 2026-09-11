/** Actual Keycloak PKCE login and two isolated browser contexts, zero model runs. */
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const { createRequire } = require('node:module');
const { chromium } = createRequire(path.resolve(__dirname, '../../apps/workbench/frontend/package.json'))('playwright');
const args = process.argv.slice(2);
const option = name => args[args.indexOf(name) + 1];
const root = path.resolve(option('--identity'));
const output = path.resolve(option('--output'));
fs.mkdirSync(output);
const credentials = JSON.parse(fs.readFileSync(path.join(root, 'connection.private.json'), 'utf8'));
const cert = new crypto.X509Certificate(fs.readFileSync(path.join(root, 'server.pem')));
const pin = crypto.createHash('sha256').update(cert.publicKey.export({type:'spki',format:'der'})).digest('base64');
(async () => {
  // Trust only this ephemeral qualification certificate, not arbitrary TLS errors.
  const browser = await chromium.launch({headless:true,args:[`--ignore-certificate-errors-spki-list=${pin}`]});
  const receipts = [];
  try {
    for (const name of ['alice','bob']) {
      const context = await browser.newContext({viewport:{width:1440,height:1000}});
      const page = await context.newPage();
      await page.goto('https://localhost:18815/workspace');
      await page.getByRole('link',{name:'安全登录'}).click();
      await page.locator('#username').fill(name);
      await page.locator('#password').fill(credentials.users[name]);
      await page.locator('#kc-login').click();
      await page.waitForURL('https://localhost:18815/workspace', {timeout:30000});
      await page.getByRole('button',{name:'退出工作区'}).waitFor();
      const status = await page.evaluate(async()=> (await fetch('/auth/status')).json());
      if (!status.authenticated || !status.owner?.startsWith('oidc:')) throw Error('browser_identity_missing');
      const rows = await page.evaluate(async()=> (await fetch('/api/v1/research-sessions')).json());
      if (!rows.some(r=>r.title === '208 identity · '+name) || rows.some(r=>r.title === '208 identity · '+(name === 'alice'?'bob':'alice'))) throw Error('browser_resource_isolation');
      const cookies = await context.cookies('https://localhost:18815');
      const session = cookies.find(c=>c.name==='finsight_session');
      if (!session || !session.httpOnly || !session.secure) throw Error('session_cookie_not_protected');
      await page.screenshot({path:path.join(output, name+'.png'),fullPage:true,animations:'disabled'});
      await page.getByRole('button',{name:'退出工作区'}).click();
      await page.getByRole('heading',{name:'登录研究工作区'}).waitFor();
      receipts.push({user:name,login:'OIDC code with PKCE',owner:status.owner,own_resources:rows.length,logout:true,secure_httponly:true});
      await context.close();
    }
    if (receipts[0].owner === receipts[1].owner) throw Error('principals_equal');
    fs.writeFileSync(path.join(output,'result.json'),JSON.stringify({receipts,model_calls:0,tls:'ephemeral certificate SPKI pinned; Python API checks verify CA'},null,2));
    console.log(JSON.stringify({browser_users:receipts.length,passed:true,model_calls:0}));
  } finally { await browser.close(); }
})().catch(e=>{fs.writeFileSync(path.join(output,'failure.json'),JSON.stringify({error:e.message}));console.error(e.message);process.exitCode=1;});
