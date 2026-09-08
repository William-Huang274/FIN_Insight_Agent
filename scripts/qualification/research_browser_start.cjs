/** Start one explicitly authorized research case through real controls; no retries. */
const fs=require("node:fs"), path=require("node:path"), {createRequire}=require("node:module");
const {chromium}=createRequire(path.resolve(__dirname,"../../apps/workbench/frontend/package.json"))("playwright");
const args=process.argv.slice(2), option=n=>args[args.indexOf(n)+1];
if(!args.includes("--execute") || !args.includes("--case") || !args.includes("--output")) throw Error("Explicit --execute --case --output required");
const spec=JSON.parse(fs.readFileSync(option("--case"),"utf8")), output=path.resolve(option("--output")), base=new URL(option("--base-url"));
if(base.hostname!=="127.0.0.1") throw Error("Loopback only");
fs.mkdirSync(output); fs.writeFileSync(path.join(output,"case.json"),JSON.stringify(spec,null,2));
(async()=>{const browser=await chromium.launch({headless:true}),page=await browser.newPage({viewport:{width:1440,height:1000}});const submissions=[];
page.on("response",async r=>{if(r.request().method()==="POST" && /\/api\/v1\/research-sessions(?:\/[^/]+\/(?:start|attachments))?$/.test(new URL(r.url()).pathname)){
  const receipt={path:new URL(r.url()).pathname,status:r.status()};
  try {receipt.body=await r.json();} catch(e) {receipt.body_read_error=String(e);}
  submissions.push(receipt);fs.writeFileSync(path.join(output,"submissions.json"),JSON.stringify(submissions,null,2));}});
try {
 await page.goto(new URL("/workspace?view=new",base).href);
 await page.getByLabel("这次你想研究什么？",{exact:true}).fill(spec.question);
 await page.getByLabel("协作模式",{exact:true}).selectOption(spec.execution.mode);
 await page.getByLabel("研究模型",{exact:true}).selectOption(spec.execution.model);
 for(const label of spec.scope_labels || []) await page.getByRole("checkbox",{name:label,exact:true}).check();
 if(spec.attachments?.length) await page.locator('input[type="file"][multiple]').setInputFiles(spec.attachments);
 await page.screenshot({path:path.join(output,"prepared.png"),fullPage:true});
 const started=page.waitForResponse(r=>r.request().method()==="POST" && (spec.attachments?.length ? /\/research-sessions\/[^/]+\/start$/.test(new URL(r.url()).pathname) : new URL(r.url()).pathname.endsWith("/research-sessions")),{timeout:60000});
 await page.getByRole("button",{name:"开始全新研究",exact:true}).click();
 const response=await started;
 fs.writeFileSync(path.join(output,"start-response.json"),JSON.stringify(await response.json(),null,2));
 if(!response.ok()) throw Error("Native start failed; inspect submissions, no retry");
 await page.waitForTimeout(2000);await page.screenshot({path:path.join(output,"started.png"),fullPage:true});
 console.log(JSON.stringify({output,url:page.url(),submissions}));
}catch(e){fs.writeFileSync(path.join(output,"failure.json"),JSON.stringify({error:String(e),submissions},null,2));process.exitCode=1;console.error(String(e));}
finally{await browser.close();}})();
