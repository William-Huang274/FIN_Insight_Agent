/** Submit one explicit, local report revision using the product controls. */
const fs = require("node:fs"), path = require("node:path"), {createRequire} = require("node:module");
const {chromium} = createRequire(path.resolve(__dirname, "../../apps/workbench/frontend/package.json"))("playwright");
const args = process.argv.slice(2), option = key => args[args.indexOf(key) + 1];
if (!["--execute", "--case", "--output", "--base-url"].every(key => args.includes(key))) throw Error("Explicit execution, case and fresh output required");
const spec = JSON.parse(fs.readFileSync(option("--case"), "utf8")), base = new URL(option("--base-url")), output = path.resolve(option("--output"));
if (base.hostname !== "127.0.0.1" || !/^[a-f0-9-]{36}$/.test(spec.thread_id) || !spec.message || !spec.budget_basis) throw Error("Bounded local revision and budget basis required");
fs.mkdirSync(output); fs.writeFileSync(path.join(output,"case.json"), JSON.stringify(spec,null,2));
(async () => {
  const browser = await chromium.launch({headless:true}), page = await browser.newPage({viewport:{width:1440,height:1000}});
  let receipt;
  try {
    await page.goto(new URL(`/workspace?thread=${spec.thread_id}&view=conversation`,base).href);
    await page.getByRole("button",{name:"定向修订",exact:true}).click();
    await page.getByLabel("问题或修订意见",{exact:true}).fill(spec.message);
    await page.getByRole("combobox",{name:"协作模式",exact:true}).selectOption(spec.mode || "auto");
    await page.getByRole("combobox",{name:"研究模型",exact:true}).selectOption(spec.model || "deepseek-v4-flash");
    await page.screenshot({path:path.join(output,"prepared.png"),fullPage:true});
    const response = page.waitForResponse(r => r.request().method()==="POST" && new URL(r.url()).pathname === `/api/v1/research-sessions/${spec.thread_id}/actions`);
    await page.getByRole("button",{name:"发送",exact:true}).click();
    const sent = await response; receipt = {status:sent.status(),body:await sent.json()};
    fs.writeFileSync(path.join(output,"submission.json"), JSON.stringify(receipt,null,2));
    if (!sent.ok()) throw Error("Submission failed; no retry");
    await page.waitForTimeout(1500);
    await page.screenshot({path:path.join(output,"started.png"),fullPage:true});
    console.log(JSON.stringify({output,receipt}));
  } catch (e) {
    fs.writeFileSync(path.join(output,"failure.json"),JSON.stringify({error:String(e),receipt},null,2));
    console.error(String(e)); process.exitCode=1;
  } finally { await browser.close(); }
})();
