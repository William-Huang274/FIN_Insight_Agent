// Real local Keycloak code + PKCE, HTTPS BFF, Java and PostgreSQL. No API stubs.
// No traces, token bodies, storage state or password screenshots are persisted.
import {chromium, expect} from 'playwright/test';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {randomUUID} from 'node:crypto';
const origin = process.env.FINSIGHT_PUBLIC_ORIGIN;
if (origin !== 'https://localhost:18866' || !process.env.FIN_OIDC_CREDENTIALS_FILE || !process.env.FIN_OIDC_EVIDENCE)
  throw Error('explicit_local_identity_acceptance_required');
const credentials = JSON.parse(await readFile(process.env.FIN_OIDC_CREDENTIALS_FILE, 'utf8'));
const output = process.env.FIN_OIDC_EVIDENCE;
await mkdir(output, {recursive:false});
const browser = await chromium.launch({headless:true});
const checks = [], identities = {};
const record = name => checks.push(name);
async function api(page, method, path, body) {
  return page.evaluate(async ({method, path, body}) => {
    const r = await fetch(path, {method, headers:{'Content-Type':'application/json', 'X-Workbench-Request':'1'},
      ...(body === undefined ? {} : {body:JSON.stringify(body)})});
    return {status:r.status, body:await r.json()};
  }, {method, path, body});
}
async function login(username, wrongPassword=false) {
  // TLS verification stays enabled. Windows current-user trust contains the CA.
  const context = await browser.newContext({baseURL:origin,viewport:{width:1440,height:1000}});
  const page = await context.newPage();
  await page.goto('/workspace');
  expect((await api(page,'GET','/api/v1/business/workspaces/projects')).status).toBe(401);
  await page.getByRole('link',{name:'安全登录'}).click();
  await expect(page.locator('#username')).toBeVisible();
  if (wrongPassword) {
    await page.locator('#username').fill(username);
    await page.locator('#password').fill('deliberately-wrong-acceptance-password');
    await page.locator('#kc-login').click();
    await expect(page.getByText('Invalid username or password.',{exact:true})).toBeVisible();
    record('incorrect_password_rejected');
  }
  await page.locator('#username').fill(username);
  await page.locator('#password').fill(credentials.users[username]);
  await page.locator('#kc-login').click();
  try { await page.waitForURL(origin+'/workspace', {timeout:30000}); }
  catch (error) {
    console.error(JSON.stringify({path:new URL(page.url()).pathname, text:(await page.locator('body').innerText()).slice(0,1500)}));
    throw error;
  }
  const status = await api(page,'GET','/auth/status');
  expect(status.body.authenticated).toBe(true);
  expect(status.body.owner).toMatch(/^oidc:[a-f0-9]{64}$/);
  identities[username] = status.body.owner;
  const cookie = (await context.cookies()).find(c=>c.name==='finsight_session');
  expect(cookie.httpOnly && cookie.secure && cookie.sameSite==='Lax').toBe(true);
  expect(await page.evaluate(()=>document.cookie.includes('finsight_session'))).toBe(false);
  return {context,page};
}
try {
  if (process.env.FIN_OIDC_RECOVERY_RESULT) {
    const previous = JSON.parse(await readFile(process.env.FIN_OIDC_RECOVERY_RESULT,'utf8'));
    for (const name of ['finsight-owner','finsight-reader']) {
      const account = await login(name);
      expect(identities[name]).toBe(previous.identities[name]);
      expect((await api(account.page,'GET','/api/v1/business/workspaces/projects/'+previous.project)).status).toBe(200);
      await account.page.goto('/workspace/projects?scope=organization&project='+previous.project);
      await expect(account.page.getByRole('heading',{name:'真实登录与项目权限验收',exact:true})).toBeVisible();
      if(name==='finsight-owner') await account.page.screenshot({path:output+'/project-after-restart.png',fullPage:true});
      await api(account.page,'POST','/auth/logout',{});
    }
    record('provider_restart_preserves_both_subjects');
    record('business_database_restart_preserves_membership');
    await writeFile(output+'/result.json',JSON.stringify({checks,identities,project:previous.project,
      tls_verification:true,provider_calls:0,browser_api_interceptions:0},null,2));
    console.log(JSON.stringify({passed:checks.length,provider_calls:0}));
  } else {
  const owner = await login('finsight-owner',true);
  record('real_authorization_code_pkce_login_secure_cookie');
  const prefix = '/api/v1/business/workspaces';
  const organization = randomUUID(), project = randomUUID();
  expect((await api(owner.page,'POST',prefix+'/organizations',{
    id:organization,name:'FinSight 本机验收组织',display_name:'验收负责人'})).status).toBe(200);
  expect((await api(owner.page,'POST',prefix+'/projects',{
    id:project,organization_id:organization,name:'真实登录与项目权限验收',description:'No model execution'})).status).toBe(200);
  record('verified_identity_creates_java_organization_and_project');
  const reader = await login('finsight-reader');
  expect(identities['finsight-reader']).not.toBe(identities['finsight-owner']);
  expect((await api(reader.page,'GET',prefix+'/projects/'+project)).status).toBe(404);
  record('second_identity_cannot_read_unshared_project');
  const invite = randomUUID();
  expect((await api(owner.page,'POST',prefix+`/organizations/${organization}/invites`,{token:invite})).status).toBe(200);
  expect((await api(reader.page,'POST',prefix+'/join',{token:invite,display_name:'验收成员'})).status).toBe(200);
  const before = await api(owner.page,'GET',prefix+'/projects/'+project);
  expect((await api(owner.page,'POST',prefix+`/projects/${project}/members`,{
    revision:before.body.revision, subject:identities['finsight-reader'], role:'viewer'})).status).toBe(200);
  expect((await api(reader.page,'GET',prefix+'/projects/'+project)).status).toBe(200);
  record('explicit_membership_grants_project_read');
  await owner.page.goto('/workspace/projects?scope=organization&project='+project);
  await expect(owner.page.getByRole('heading',{name:'真实登录与项目权限验收',exact:true})).toBeVisible();
  await owner.page.screenshot({path:output+'/project-1440.png',fullPage:true});
  await owner.page.reload();
  expect((await api(owner.page,'GET','/auth/status')).body.owner).toBe(identities['finsight-owner']);
  record('reload_preserves_verified_identity');
  const deniedLogout = await owner.context.request.post(origin+'/auth/logout',{
    headers:{Origin:'https://untrusted.example','X-Workbench-Request':'1'}});
  expect(deniedLogout.status()).toBe(403);
  record('cross_origin_logout_denied');
  expect((await api(owner.page,'POST','/auth/logout',{})).status).toBe(200);
  expect((await api(owner.page,'GET','/auth/status')).body.authenticated).toBe(false);
  expect((await api(owner.page,'GET',prefix+'/projects/'+project)).status).toBe(401);
  record('application_logout_removes_browser_authority');
  await owner.page.goto('/auth/callback?state=invalid&code=invalid');
  expect((await api(owner.page,'GET','/auth/status')).body.authenticated).toBe(false);
  record('invalid_callback_cannot_create_identity');
  await writeFile(output+'/result.json',JSON.stringify({checks,identities,organization,project,
    tls_verification:true, browser_api_interceptions:0, provider_calls:0,
    scope:'real local OIDC and Java membership; native research not executed'},null,2));
  console.log(JSON.stringify({passed:checks.length,provider_calls:0}));
  }
} catch (error) {
  // Playwright request errors may include Cookie headers. Persist only the
  // checkpoint names and error class, never a raw request log or stack.
  await writeFile(output+'/failure.json',JSON.stringify({checks,error:error.name},null,2));
  console.error(JSON.stringify({passed:checks.length,error:error.name,
    summary:String(error.message).split('\n')[0].replace(/https?:\/\/\S+/g,'[url]'),details:'see safe failure.json'}));
  process.exitCode = 1;
} finally { await browser.close(); }
