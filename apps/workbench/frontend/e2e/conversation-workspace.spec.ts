import { test, expect } from "./identity-fixture";

test('lost submission response retains one intent key across reload', async ({page}) => {
  const keys:string[]=[];
  const id='00000000-0000-4000-8000-000000000099';
  const snapshot={thread_id:id,title:'回执验证',status:'idle',messages:[],events:[],runs:[]};
  await page.route('**/api/v1/conversations**',async route=>{
    if(route.request().method()==='POST') {
      keys.push(route.request().headers()['idempotency-key']);
      if(keys.length===1) return route.abort('connectionreset');
      return route.fulfill({json:{thread_id:id,run_id:'same-server-run'}});
    }
    return route.fulfill({json:new URL(route.request().url()).pathname.endsWith('conversations')?[]:snapshot});
  });
  await page.goto('/workspace/assistant');
  await page.getByLabel('发送消息',{exact:true}).fill('保存同一个提交意图');
  await page.getByRole('button',{name:'发送',exact:true}).click();
  await expect.poll(()=>keys.length).toBe(1);
  await page.reload();
  await page.getByLabel('发送消息',{exact:true}).fill('保存同一个提交意图');
  await page.getByRole('button',{name:'发送',exact:true}).click();
  await expect(page).toHaveURL(new RegExp(id));
  expect(keys[0]).toMatch(/^[0-9a-f-]{36}$/);
  expect(keys[1]).toBe(keys[0]);
});

for (const width of [1440, 1024, 390]) test(`general conversation persists and selects controls at ${width}`, async ({page}) => {
  await page.setViewportSize({width,height:950});
  const id="00000000-0000-4000-8000-000000000090";
  const snapshot:any = {thread_id:id,title:"HTTP 缓存说明",status:"idle",messages:[{id:"a",role:"assistant",content:"**可继续的回答**\n\n缓存可以复用来源。"}],events:[],runs:[],permissions_notice:"只读工具；不授权修改用户原文件。"};
  const writes:any[]=[];
  await page.route("**/api/v1/conversations**",async route=>{
    if(route.request().method()==="POST"){const body=route.request().postDataJSON(); writes.push(body);snapshot.messages.push({id:"u",role:"user",content:body.message}); await route.fulfill({json:{thread_id:id,run_id:"run"}});return;}
    await route.fulfill({json:new URL(route.request().url()).pathname.endsWith("conversations")?[snapshot]:snapshot});
  });
  await page.goto("/workspace/assistant");
  await page.getByLabel("发送消息",{exact:true}).fill("改成给同事的三条说明");
  await page.getByRole("combobox",{name:"模型",exact:true}).selectOption("deepseek-v4-pro");
  await page.getByRole("combobox",{name:"权限",exact:true}).selectOption("approve_for_me");
  await page.getByRole("button",{name:"发送",exact:true}).click();
  await expect(page).toHaveURL(new RegExp(id));
  await expect(page.getByText("可继续的回答",{exact:true})).toBeVisible();
  expect(writes).toEqual([{message:"改成给同事的三条说明",model:"deepseek-v4-pro",permission_mode:"approve_for_me",harness:"native"}]);
  await page.reload(); await expect(page.getByText("改成给同事的三条说明",{exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth+1)).toBeTruthy();
  if(width===390) await page.getByRole("button",{name:"对话列表",exact:true}).click();
  await page.getByRole("button",{name:"新对话",exact:true}).click();
  await expect(page.getByRole("heading",{name:"从一个问题开始"})).toBeVisible();
});

for (const width of [1440, 1024, 390]) test(`handoff preview preserves checkpoint without starting a model at ${width}`, async ({page}) => {
  await page.setViewportSize({width,height:950});
  const parent="00000000-0000-4000-8000-000000000091", child="00000000-0000-4000-8000-000000000092";
  const checkpoint="00000000-0000-4000-8000-000000000093", writes:any[]=[];
  const snapshot={thread_id:parent,title:"收入单位更正",status:"idle",messages:[],events:[],runs:[],permissions_notice:"只读回溯"};
  await page.route("**/api/v1/conversations**",async route=>{
    const path=new URL(route.request().url()).pathname;
    if(route.request().method()==="POST") {
      writes.push({path,body:route.request().postDataJSON()});
      await route.fulfill({json:{thread_id:child}});return;
    }
    await route.fulfill({json:path.endsWith("handoff-preview") ? {
      source_thread:parent,checkpoint_id:checkpoint,title:snapshot.title,message_count:6,evidence_count:3,
      latest_user_request:"金额用十亿美元，保留原USD与期间。",notice:"回读原始记录，不把摘要当证据。"
    } : path.endsWith("conversations") ? [snapshot] : {...snapshot,thread_id:path.endsWith(child)?child:parent}});
  });
  await page.goto(`/workspace/assistant?thread=${parent}`);
  await page.getByRole("button",{name:"保留进度并开新对话",exact:true}).click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByLabel("接下来要做什么、必须保留哪些约束？")).toHaveValue("金额用十亿美元，保留原USD与期间。");
  expect(await page.getByRole("dialog").evaluate(e=>e.scrollWidth <= e.clientWidth+1)).toBeTruthy();
  await page.getByRole("button",{name:"关闭交接",exact:true}).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await page.getByRole("button",{name:"保留进度并开新对话",exact:true}).click();
  await page.getByRole("button",{name:"创建接续窗口",exact:true}).click();
  await expect(page).toHaveURL(new RegExp(child));
  expect(writes).toEqual([{path:`/api/v1/conversations/${parent}/handoff`,body:{checkpoint_id:checkpoint,note:"金额用十亿美元，保留原USD与期间。"}}]);
  await expect(page.getByLabel("发送消息",{exact:true})).toHaveValue("请根据交接说明继续，先核对原始约束和所需依据。");
});

for (const width of [1440,1024,390]) test(`review isolated code before native approval at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:950});
  const tid="00000000-0000-4000-8000-000000000094", checkpoint="00000000-0000-4000-8000-000000000095", writes:any[]=[];
  const snapshot:any={thread_id:tid,title:"隔离计算",status:"interrupted",messages:[],events:[],runs:[],checkpoint_id:checkpoint,
    approvals:[{id:"approve-1",value:{action_requests:[{name:"run_isolated_python",args:{code:"print(sum([1, 2, 3]))"},description:"空白临时容器，无网络或宿主文件。"}]}}],permissions_notice:"仅隔离临时目录"};
  await page.route("**/api/v1/conversations**",async route=>{
    if(route.request().method()==="POST"){writes.push(route.request().postDataJSON());snapshot.approvals=[];await route.fulfill({json:{thread_id:tid,run_id:"resumed"}});return;}
    await route.fulfill({json:new URL(route.request().url()).pathname.endsWith("conversations")?[snapshot]:snapshot});
  });
  await page.goto(`/workspace/assistant?thread=${tid}`);
  const card=page.getByRole("region",{name:"待批准的工具操作"});
  await expect(card.getByText("print(sum([1, 2, 3]))",{exact:true})).toBeVisible();
  await expect(page.getByRole("combobox",{name:"权限",exact:true})).toBeDisabled();
  await expect(page.getByRole("button",{name:"发送",exact:true})).toBeDisabled();
  expect(writes).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBeTruthy();
  await page.getByRole("button",{name:"拒绝这些操作",exact:true}).click();
  await expect(card).not.toBeVisible();
  expect(writes).toEqual([{checkpoint_id:checkpoint,interrupt_id:"approve-1",decisions:["reject"]}]);
});

for (const width of [1440,1024,390]) test(`review original source before knowledge admission at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:950});
  const tid="00000000-0000-4000-8000-000000000096", checkpoint="00000000-0000-4000-8000-000000000097", writes:any[]=[];
  const snapshot={thread_id:tid,title:"来源复用",status:"interrupted",messages:[],events:[],runs:[],checkpoint_id:checkpoint,
    approvals:[{id:"save-1",value:{action_requests:[{name:"save_sources_to_knowledge",args:{source_ids:["PASSAGE::source"],purpose:"后续核对缓存语义"},description:"保存到个人资料库，保留原始版本。"}]}}],
    approval_sources:{"PASSAGE::source":{title:"RFC 9111 HTTP Caching",preview:"Exact captured source window.",source_url:"https://www.rfc-editor.org/rfc/rfc9111.html"}},permissions_notice:"个人来源复用"};
  await page.route("**/api/v1/conversations**",async route=>{
    if(route.request().method()==="POST"){writes.push(route.request().postDataJSON());await route.fulfill({json:{run_id:"resumed"}});return;}
    await route.fulfill({json:new URL(route.request().url()).pathname.endsWith("conversations")?[snapshot]:snapshot});
  });
  await page.goto(`/workspace/assistant?thread=${tid}`);
  await expect(page.getByText("RFC 9111 HTTP Caching",{exact:true})).toBeVisible();
  await expect(page.getByText("Exact captured source window.",{exact:true})).toBeVisible();
  expect(writes).toEqual([]);
  await page.getByRole("button",{name:"批准这些操作",exact:true}).click();
  await expect.poll(()=>writes.length).toBe(1);
  expect(writes[0]).toEqual({checkpoint_id:checkpoint,interrupt_id:"save-1",decisions:["approve"]});
});
