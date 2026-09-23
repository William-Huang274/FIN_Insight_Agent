import {test,expect,type Page} from './identity-fixture';

const a='10000000-0000-4000-8000-000000000001',b='20000000-0000-4000-8000-000000000002',id='30000000-0000-4000-8000-000000000003';
async function fixture(page:Page,{drop=false,enabled=true}={}){
  const writes:{path:string;key:string|undefined;body:any}[]=[];
  let task:any=null;
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),u=new URL(request.url());
    if(request.method()!=='GET')writes.push({path:u.pathname,key:request.headers()['idempotency-key'],body:request.postDataJSON()});
    let body:any={};
    if(u.pathname==='/api/v1/projects')body={revision:1,projects:[{id:b,name:'AI 基础设施'},{id:a,name:'AI 基础设施'}],assignments:{},pinned:[]};
    else if(u.pathname.endsWith('/documents'))body={items:[{document_id:'UPLOAD::synthetic',name:`${u.pathname.includes(a)?'A':'B'} 项目季度资料.pdf`,access_status:'active'}],next_offset:null};
    else if(u.pathname.endsWith('/business/config'))body={enabled};
    else if(u.pathname.endsWith('/research-session-config'))body={fresh_research_enabled:true,research_as_of:'2025-12-31',branch_topics:[]};
    else if(u.pathname==='/api/v1/business/tasks'&&request.method()==='POST'){
      const input=request.postDataJSON();task={...input,id,submission_key:request.headers()['idempotency-key'],created_at:'2026-09-23T01:00:00Z',binding:{snapshot_ref:'sha256:'+'a'.repeat(64),research_as_of:'2025-12-31T00:00:00+00:00'},thread_id:id,
        prepare:{status:'received',operation_id:a},start:{status:'ready',operation_id:b}};
      if(drop){drop=false;await route.abort('failed');return;}body=task;
    }else if(u.pathname==='/api/v1/business/tasks')body={items:task&&task.project_id===u.searchParams.get('project_id')?[task]:[],next_offset:null};
    else if(u.pathname.endsWith('/start')){task.start.status='unknown';body=task;}
    else if(u.pathname.endsWith('/reconcile')){task.start={...task.start,status:'received',result:{run_id:b,status:'pending'}};body=task;}
    else if(u.pathname.endsWith(id))body=task;
    else throw Error('Unexpected request '+u.pathname);
    await route.fulfill({json:body});
  });return writes;
}
for(const width of [1440,390])test(`project IDs, prepare, unknown start and original research at ${width}`,async({page},testInfo)=>{
  await page.setViewportSize({width,height:960});const writes=await fixture(page);
  await page.goto('/workspace/projects');await expect(page.getByRole('heading',{name:'选择一个项目开始'})).toBeVisible();
  const picker=page.getByRole('combobox',{name:'切换项目'});
  await expect(picker.locator('option')).toHaveText(['选择项目','AI 基础设施 · 10000000','AI 基础设施 · 20000000']);
  await picker.selectOption(a);await expect(page.getByText('A 项目季度资料.pdf')).toBeVisible();
  await picker.selectOption(b);await expect(page.getByText('B 项目季度资料.pdf')).toBeVisible();await expect(page.getByText('A 项目季度资料.pdf')).toHaveCount(0);
  await picker.selectOption(a);await page.getByLabel('研究标题',{exact:true}).fill('资本开支与现金流研究');await page.getByLabel('研究问题',{exact:true}).fill('研究 AI 基础设施公司的资本开支变化及现金流覆盖情况。');
  await page.getByLabel('A 项目季度资料.pdf').check();
  await page.screenshot({path:testInfo.outputPath(`project-intake-form-${width}.png`),fullPage:true});
  await page.getByRole('button',{name:'保存并准备草稿',exact:true}).click();await expect(page.getByRole('button',{name:'确认并启动研究'})).toBeVisible();
  expect(writes).toHaveLength(1);expect(writes[0].body.project_id).toBe(a);expect(writes[0].body.document_ids).toEqual(['UPLOAD::synthetic']);
  await page.reload();await expect(page.getByRole('button',{name:'确认并启动研究'})).toBeVisible();expect(writes).toHaveLength(1);
  await page.getByRole('button',{name:'确认并启动研究'}).click();await expect(page.getByRole('button',{name:'核对原提交'})).toBeVisible();await expect(page.getByRole('button',{name:'确认并启动研究'})).toHaveCount(0);
  await page.getByRole('button',{name:'核对原提交'}).click();await expect(page.getByRole('link',{name:'打开原研究'})).toHaveAttribute('href',`/workspace/session?thread=${id}&view=activity`);
  expect(writes.filter(w=>w.path.endsWith('/start'))).toHaveLength(1);
  await page.screenshot({path:testInfo.outputPath(`project-intake-result-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await picker.selectOption(b);await expect(page.getByText('这个项目还没有业务研究任务。')).toBeVisible();await expect(page.getByText('资本开支与现金流研究',{exact:true})).toHaveCount(0);
});
test('lost browser response preserves exact submission across refresh',async({page})=>{
  const writes=await fixture(page,{drop:true});await page.goto(`/workspace/projects?project=${a}`);
  await page.getByLabel('研究标题',{exact:true}).fill('不确定提交');await page.getByLabel('研究问题',{exact:true}).fill('用于验证网络异常后仍然使用原始提交凭证。');
  await page.getByRole('button',{name:'保存并准备草稿'}).click();await expect(page.getByText('上次提交尚待核对')).toBeVisible();
  await page.reload();await expect(page.getByText('上次提交尚待核对')).toBeVisible();await page.getByRole('button',{name:'核对并恢复原提交'}).click();
  await expect(page.getByRole('button',{name:'确认并启动研究'})).toBeVisible();expect(writes).toHaveLength(2);expect(writes[0]).toEqual(writes[1]);
});
test('invalid project and disabled service do not silently fall back to a default project',async({page})=>{
  await fixture(page);await page.goto(`/workspace/projects?project=${id}`);await expect(page.getByRole('heading',{name:'此项目不存在或不可访问'})).toBeVisible();
  await expect(page.getByRole('button',{name:'保存并准备草稿'})).toHaveCount(0);
  await page.unroute('**/api/v1/**');await fixture(page,{enabled:false});await page.goto(`/workspace/projects?project=${a}`);
  await expect(page.getByRole('heading',{name:'研究业务服务尚未启用'})).toBeVisible();await expect(page.getByRole('button',{name:'保存并准备草稿'})).toHaveCount(0);
});
