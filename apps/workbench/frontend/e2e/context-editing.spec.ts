import {test,expect} from './identity-fixture';
for(const width of [1440,390]) test(`direct context and note edits at ${width}`,async({page})=>{
  await page.setViewportSize({width,height:1000});
  const id='00000000-0000-4000-8000-000000000095';let body='只列观察',version=1,noteBody='原始正文',noteVersion=1;
  const writes:string[]=[];
  const snapshot={thread_id:id,title:'直接编辑',status:'idle',messages:[],events:[],runs:[]};
  await page.route('**/api/v1/conversations**',async route=>{
    const url=new URL(route.request().url());let data:any=snapshot;
    if(url.pathname.endsWith('/conversations'))data=[snapshot];
    if(route.request().method()==='PUT'){
      const value=route.request().postDataJSON();writes.push(url.pathname);
      if(url.pathname.endsWith('/user-context')){expect(value.version).toBe(version);body=value.body;data={version:++version,notice:'已保存要求'};}
      else {expect(value.version).toBe(noteVersion);noteBody=value.body;data={version:++noteVersion,notice:'已保存新版本'};}
    }else if(url.pathname.endsWith('/user-context'))data={enabled:true,body,version};
    else if(url.pathname.endsWith('/working-notes'))data=url.searchParams.has('download')?{markdown:noteBody}:url.searchParams.has('note_id')?
      {found:true,id:'note',actor:'Q1_ISSUER_TRUTH',title:'现金观察',version:noteVersion,body:noteBody,is_current:true,next_offset:null}:
      {items:[{id:'note',actor:'Q1_ISSUER_TRUTH',title:'现金观察',version:noteVersion,preview:noteBody}],next_offset:null};
    expect(route.request().method()).not.toBe('POST');await route.fulfill({json:data});
  });
  await page.goto(`/workspace/assistant?thread=${id}`);
  await page.getByRole('button',{name:'研究设置与记忆',exact:true}).click();
  const settings=page.getByRole('dialog',{name:'研究设置与记忆'});
  await settings.getByLabel('我的研究要求').fill('等待附注，不继续检索');
  await page.keyboard.press('Escape');await expect(settings).toBeVisible();
  await settings.getByRole('button',{name:'保存要求',exact:true}).click();
  await expect(settings.getByRole('status')).toHaveText('已保存要求');
  await settings.getByRole('button',{name:'关闭研究设置'}).click();
  await page.getByRole('button',{name:'研究设置与记忆',exact:true}).click();
  await expect(settings.getByLabel('我的研究要求')).toHaveValue('等待附注，不继续检索');
  await settings.getByRole('button',{name:'关闭研究设置'}).click();
  await page.getByRole('button',{name:'工作底稿',exact:true}).click();
  const notes=page.getByRole('dialog',{name:'工作底稿',exact:true});
  await expect(notes.getByRole('navigation',{name:'底稿目录'})).toContainText('收入、利润与现金');
  await notes.getByRole('button',{name:/现金观察/}).click();
  await notes.getByRole('button',{name:'直接编辑正文'}).click();
  await notes.getByLabel('编辑底稿正文').fill('改为等待用户提供附注。');
  await notes.getByRole('button',{name:'保存新版本'}).click();
  await expect(notes.getByRole('article')).toContainText('改为等待用户提供附注。');
  expect(writes.length).toBe(2);
  expect(await notes.evaluate(e=>e.scrollWidth<=e.clientWidth+1)).toBeTruthy();
});
