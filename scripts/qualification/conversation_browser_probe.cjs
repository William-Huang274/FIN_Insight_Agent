/** Explicit paid local qualification, submitted through the real UI. No retries. */
const fs = require("node:fs");
const path = require("node:path");
const { createRequire } = require("node:module");
const { chromium } = createRequire(path.resolve(__dirname, "../../apps/workbench/frontend/package.json"))("playwright");
const args = process.argv.slice(2);
function option(name) { return args[args.indexOf(name) + 1]; }
if (!args.includes("--execute") || !args.includes("--case") || !args.includes("--output")) throw Error("Explicit --execute --case --output required; calls incur provider usage");
const spec = JSON.parse(fs.readFileSync(option("--case"), "utf8"));
const output = path.resolve(option("--output"));
const base = new URL(option("--base-url"));
if (base.hostname !== "127.0.0.1" || !Array.isArray(spec.turns) || spec.turns.length < 1 || spec.turns.length > 3) throw Error("Only bounded loopback qualification allowed");
fs.mkdirSync(output); // immutable attempt, never overwrite a prior run
fs.writeFileSync(path.join(output, "case.json"), JSON.stringify(spec, null, 2));
(async () => {
  const browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width:1440,height:1000}});
  await page.addInitScript(() => {
    window.__finPublicDeltas = 0;
    const NativeEventSource = window.EventSource;
    window.EventSource = class extends NativeEventSource {
      constructor(...params) { super(...params); this.addEventListener("assistant_delta", () => { window.__finPublicDeltas++; }); }
    };
  });
  const errors = [], receipts = [];
  page.on("pageerror", e => errors.push(e.message));
  try {
    const entry = new URL("/workspace/assistant", base);
    if (spec.thread_id) {
      if (!/^[0-9a-f-]{36}$/.test(spec.thread_id)) throw Error("Invalid existing thread ID");
      entry.searchParams.set("thread", spec.thread_id);
    }
    await page.goto(entry.href);
    for (let index=0; index<spec.turns.length; index++) {
      if (index) await page.reload(); // prove persistence, not retained component state
      await page.getByLabel("发送消息", {exact:true}).fill(spec.turns[index]);
      await page.getByRole("combobox", {name:"模型",exact:true}).selectOption(spec.model || "deepseek-v4-flash");
      await page.getByRole("combobox", {name:"权限",exact:true}).selectOption(spec.permission_mode || "request_standard");
      const response = page.waitForResponse(r => r.request().method()==="POST" && /\/api\/v1\/conversations(?:\/[^/]+\/messages)?$/.test(new URL(r.url()).pathname));
      await page.getByRole("button", {name:"发送",exact:true}).click();
      const sent = await response;
      const identity = await sent.json(); receipts.push({index,status:sent.status(),...identity});
      fs.writeFileSync(path.join(output, "submissions.json"), JSON.stringify(receipts,null,2));
      if (!sent.ok()) throw Error("UI submission failed; no retry");
      const started = Date.now(); let state;
      while (Date.now()-started < 240000) {
        const result = await page.request.get(new URL(`/api/v1/conversations/${identity.thread_id}`,base).href);
        if (!result.ok()) throw Error("State read failed; preserve submitted run identity");
        state = await result.json();
        const run = state.runs.find(r => r.run_id === identity.run_id);
        if (run && !["pending","running"].includes(run.status)) break;
        await page.waitForTimeout(1500);
      }
      fs.writeFileSync(path.join(output, `turn-${index+1}.json`), JSON.stringify(state,null,2));
      fs.writeFileSync(path.join(output, `stream-${index+1}.json`), JSON.stringify({public_text_deltas:await page.evaluate(()=>window.__finPublicDeltas)}));
      await page.waitForTimeout(2700);
      await page.screenshot({path:path.join(output,`turn-${index+1}.png`),fullPage:true});
      const run = state.runs.find(r => r.run_id === identity.run_id);
      if (!run || run.status !== "success") throw Error(`Native run ended ${run?.status}; no paid retry`);
      if (errors.length) throw Error("Browser error; inspect receipt");
    }
    console.log(JSON.stringify({status:"runs_completed_pending_content_review",output,receipts}));
  } catch(e) {
    fs.writeFileSync(path.join(output,"failure.json"),JSON.stringify({error:String(e),browser_errors:errors,receipts},null,2));
    process.exitCode=1; console.error(String(e));
  } finally { await browser.close(); }
})();
