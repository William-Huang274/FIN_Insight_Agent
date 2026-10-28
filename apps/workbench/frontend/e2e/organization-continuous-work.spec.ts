import {test,expect} from './identity-fixture';
const project='20000000-0000-4000-8000-000000000002',execution='30000000-0000-4000-8000-000000000003';
const checkpoint='60000000-0000-4000-8000-000000000006';
for(const width of [1440,390])test(`continuous root answer, follow-up, note and stop at ${width}`,async({page},info)=>{
  let posts=0,closed=false,continued=false;const commands:any[]=[];
  const root=`/api/v1/organization-projects/${project}/research/${execution}`;
  await page.setViewportSize({width,height:960});
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),url=new URL(request.url()),p=url.pathname;let result:any={};
    if(p==='/api/v1/business/config')result={organization_projects:true};
    else if(p==='/api/v1/projects')result={revision:0,projects:[],assignments:{},pinned:[]};
    else if(p==='/api/v1/research-sessions')result=[];
    else if(p===`/api/v1/business/workspaces/projects/${project}`)result={id:project,organization_id:'org',name:'连续研究项目',role:'researcher',can_manage:false,archived:false};
    else if(p.endsWith('/members'))result=[];
    else if(p===root+'/control')result={can_operate:!closed,execution_closed:closed,enabled:true,runtime_contract:'on_demand.v1',preparation:'received',start:'received',continuation:'absent'};
    else if(p===root+'/task-commands'&&request.method()==='GET')result={enabled:true,items:commands};
    else if(p===root+'/task-action-preview')result={previous_run_id:'40000000-0000-4000-8000-000000000004',checkpoint_id:checkpoint,state_digest:'sha256:'+'a'.repeat(64)};
    else if(p===root+'/task-commands'){
      posts++;const body=request.postDataJSON();expect(body.message).toBe('解释计算依据');
      expect(body.action).toBe('continue');expect(body.report_version).toBeUndefined();
      expect(body.delivery_intent).toBe('workpaper');expect(body.require_report_review).toBe(false);
      commands.push({id:body.id,status:'unknown'});await route.abort('failed');return;
    }else if(p.endsWith('/reconcile')){
      expect(posts).toBe(1);commands[0].status='received';continued=true;result=commands[0];
    }else if(p===root+'/stop'){
      closed=true;result={execution_closed:true,native_stop_pending:[],new_model_requests_authorized:false};
    }else if(p===root+'/workpaper'){
      expect(url.searchParams.get('checkpoint_id')).toBe(checkpoint);
      result={title:'已保存底稿',body:'保留准确期间的分析正文',version:2,next_offset:null};
    }else if(p===root)result={title:'解释一项指标',runtime_contract:'on_demand.v1',status:'idle',checkpoint_id:checkpoint,
      task_outcome:{execution_status:'submitted',artifact_kind:continued?'workpaper':'answer'},
      conversation:[{role:'assistant',content:continued?'已解释并保留底稿':'这是针对问题的简短回答'}]};
    else if(p===`/api/v1/organization-projects/${project}/research`)result={items:[{execution_id:execution,title:'解释一项指标'}],next_offset:null};
    else throw Error('Unexpected API '+p);
    await route.fulfill({json:result});
  });
  await page.goto(`/workspace/projects?scope=organization&project=${project}&view=results&execution=${execution}`);
  await expect(page.getByText('这是针对问题的简短回答',{exact:true})).toBeVisible();
  await expect(page.getByText('这项研究尚无报告。已保存的预研究内容不作为报告导出。')).toHaveCount(0);
  await page.getByRole('textbox',{name:'继续提问或交代下一步'}).fill('解释计算依据');
  await page.getByLabel('这一步的成果',{exact:true}).selectOption('workpaper');
  await page.getByRole('button',{name:'准备继续任务',exact:true}).click();
  expect(posts).toBe(0);
  await page.getByRole('button',{name:'确认继续任务',exact:true}).click();
  await expect(page.getByRole('button',{name:'核对原任务操作'})).toBeVisible();
  await page.reload();expect(posts).toBe(1);
  await page.getByRole('button',{name:'核对原任务操作'}).click();
  await expect(page.getByText('已解释并保留底稿',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'读取已提交底稿'}).click();
  await expect(page.getByText('保留准确期间的分析正文',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'结束本次执行',exact:true}).click();
  expect(closed).toBe(false);
  await page.getByRole('button',{name:'确认结束本次执行',exact:true}).click();
  await expect(page.getByRole('textbox',{name:'继续提问或交代下一步'})).toHaveCount(0);
  await expect(page.getByText('本次执行已结束，已保存成果仍可阅读。')).toBeVisible();
  expect(posts).toBe(1);expect(closed).toBe(true);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  await page.screenshot({path:info.outputPath(`continuous-root-${width}.png`),fullPage:true});
});
