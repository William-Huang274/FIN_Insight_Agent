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
const maxTurns = spec.qualification === '208-long-dialogue' && spec.TokenBudgetBasis ? 16 : 3;
if (base.hostname !== "127.0.0.1" || !Array.isArray(spec.turns) || spec.turns.length < 1 || spec.turns.length > maxTurns) throw Error("Only bounded loopback qualification allowed");
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
    const existing = spec.handoff_from || spec.thread_id;
    if (existing) {
      if (!/^[0-9a-f-]{36}$/.test(existing) || (spec.handoff_from && spec.thread_id)) throw Error("Invalid existing thread selection");
      entry.searchParams.set("thread", existing);
    }
    await page.goto(entry.href);
    if (spec.handoff_from) {
      if (!spec.handoff_note) throw Error("A reviewable handoff note is required");
      await page.getByRole("button",{name:"保留进度并开新对话",exact:true}).click();
      await page.getByLabel("接下来要做什么、必须保留哪些约束？",{exact:true}).fill(spec.handoff_note);
      await page.screenshot({path:path.join(output,"handoff-prepared.png"),fullPage:true});
      const response=page.waitForResponse(r=>r.request().method()==="POST" && new URL(r.url()).pathname===`/api/v1/conversations/${spec.handoff_from}/handoff`);
      await page.getByRole("button",{name:"创建接续窗口",exact:true}).click();
      const sent=await response, handoff=await sent.json();
      fs.writeFileSync(path.join(output,"handoff.json"),JSON.stringify({status:sent.status(),...handoff},null,2));
      if(!sent.ok())throw Error("Handoff failed, no retry");
      await page.waitForURL(u=>u.searchParams.get("thread")===handoff.thread_id);
    }
    for (let index=0; index<spec.turns.length; index++) {
      if (index) await page.reload(); // prove persistence, not retained component state
      await page.getByLabel("发送消息", {exact:true}).fill(spec.turns[index]);
      await page.getByRole("combobox", {name:"模型",exact:true}).selectOption(spec.models?.[index] || spec.model || "deepseek-v4-flash");
      await page.getByRole("combobox", {name:"权限",exact:true}).selectOption(spec.permission_mode || "request_standard");
      if (!existing && !index && spec.harness) await page.getByRole('combobox',{name:'执行方式',exact:true}).selectOption(spec.harness);
      if (!index && spec.attachments?.length) await page.getByLabel("添加对话资料",{exact:true}).setInputFiles(spec.attachments);
      const response = page.waitForResponse(r => r.request().method()==="POST" && /\/api\/v1\/conversations(?:\/[^/]+\/messages)?$/.test(new URL(r.url()).pathname));
      await page.getByRole("button", {name:"发送",exact:true}).click();
      const sent = await response;
      let identity = await sent.json(); receipts.push({index,status:sent.status(),...identity});
      fs.writeFileSync(path.join(output, "submissions.json"), JSON.stringify(receipts,null,2));
      if (!sent.ok()) throw Error("UI submission failed; no retry");
      const started = Date.now(); let state;
      while (Date.now()-started < 240000) {
        const result = await page.request.get(new URL(`/api/v1/conversations/${identity.thread_id}`,base).href);
        if (!result.ok()) throw Error("State read failed; preserve submitted run identity");
        state = await result.json();
        const run = state.runs.find(r => r.run_id === identity.run_id);
        if (state.approvals?.length && spec.knowledge_approval_source_ids && !receipts.some(r=>r.approval)) {
          const pending=state.approvals;
          const expected=[...spec.knowledge_approval_source_ids].sort();
          const actions=pending?.[0]?.value?.action_requests;
          if(pending?.length!==1 || actions?.length!==1 || actions[0].name!=="save_sources_to_knowledge" ||
              !Array.isArray(actions[0].args.source_ids) || JSON.stringify([...actions[0].args.source_ids].sort())!==JSON.stringify(expected) ||
              expected.some(id=>!state.approval_sources?.[id]?.preview)) throw Error("Knowledge approval differs from explicitly scoped qualification; leave pending");
          fs.writeFileSync(path.join(output,"approval-prepared.json"),JSON.stringify(state,null,2));
          await page.reload();
          await page.getByRole("region",{name:"待批准的工具操作"}).waitFor();
          await page.screenshot({path:path.join(output,"approval-prepared.png"),fullPage:true});
          const approvalResponse=page.waitForResponse(r=>r.request().method()==="POST" && new URL(r.url()).pathname===`/api/v1/conversations/${identity.thread_id}/approvals`);
          await page.getByRole("button",{name:"批准这些操作",exact:true}).click();
          const approved=await approvalResponse;
          const resumed=await approved.json();
          receipts.push({index,approval:true,status:approved.status(),...resumed});
          fs.writeFileSync(path.join(output,"submissions.json"),JSON.stringify(receipts,null,2));
          if(!approved.ok())throw Error("Knowledge approval failed; no retry");
          identity=resumed;
          continue;
        }
        if (run && !["pending","running"].includes(run.status)) break;
        await page.waitForTimeout(1500);
      }
      fs.writeFileSync(path.join(output, `turn-${index+1}.json`), JSON.stringify(state,null,2));
      fs.writeFileSync(path.join(output, `stream-${index+1}.json`), JSON.stringify({public_text_deltas:await page.evaluate(()=>window.__finPublicDeltas)}));
      await page.waitForTimeout(2700);
      await page.screenshot({path:path.join(output,`turn-${index+1}.png`),fullPage:true});
      const run = state.runs.find(r => r.run_id === identity.run_id);
      if (!run || run.status !== "success") throw Error(`Native run ended ${run?.status}; no paid retry`);
      const answer=state.messages.filter(m=>m.role==='assistant').at(-1);
      if(!answer?.final_answer || answer.delivery_status==='needs_attention' || /^\s*(<｜｜DSML|Tool call limit reached:)/.test(answer.content)) throw Error('Run ended but no complete public answer was delivered; preserve result for targeted review');
      if (spec.knowledge_approval_source_ids && !receipts.some(r=>r.approval)) throw Error("Model returned prose without the required native knowledge approval; nothing saved");
      if (errors.length) throw Error("Browser error; inspect receipt");
      console.log(JSON.stringify({turn:index+1,thread_id:identity.thread_id,run_id:identity.run_id,status:run.status}));
    }
    console.log(JSON.stringify({status:"runs_completed_pending_content_review",output,receipts}));
  } catch(e) {
    fs.writeFileSync(path.join(output,"failure.json"),JSON.stringify({error:String(e),browser_errors:errors,receipts},null,2));
    process.exitCode=1; console.error(String(e));
  } finally { await browser.close(); }
})();
