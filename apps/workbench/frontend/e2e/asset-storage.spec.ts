import {test,expect} from 'playwright/test';

for(const width of [1440,390])test(`长期项目容量与分页 ${width}`,async({page},info)=>{
  test.setTimeout(90000);await page.setViewportSize({width,height:1000});
  const headers={'X-Workbench-Request':'1'};
  const saved=await(await page.request.get('/api/v1/projects')).json();
  const project=crypto.randomUUID();
  await page.request.put('/api/v1/projects',{headers,data:{...saved,projects:[...saved.projects,{id:project,name:`持续阅读 ${width}`}]}});
  for(let i=0;i<35;i++){
    const response=await page.request.post(`/api/v1/projects/${project}/documents`,{headers:{...headers,'X-File-Name':`Note-${i}.md`},data:`Saved original ${i}. 留存率核验，用户笔记，不是金融结论。`});
    expect(response.ok()).toBe(true);
  }
  await page.goto(`/workspace/session?view=project&project=${project}`);
  await expect(page.getByRole('heading',{name:`持续阅读 ${width}`,exact:true})).toBeVisible();
  const pages=page.getByRole('navigation',{name:'项目资料分页'});
  await expect(pages).toContainText('共 35 个版本 · 第 1 页');
  await expect(page.locator('.fs-project-documents article')).toHaveCount(30);
  await pages.getByRole('button',{name:'下一页',exact:true}).click();
  await expect(page.locator('.fs-project-documents article')).toHaveCount(5);
  await page.getByLabel('选择资料 Note-34.md',{exact:true}).check();
  await pages.getByRole('button',{name:'上一页',exact:true}).click();
  await expect(page.getByText('已选 1 份资料。',{exact:false})).toBeVisible();
  await page.getByLabel('查找项目资料').fill('留存率');
  await page.getByRole('button',{name:'查找',exact:true}).click();
  await expect(pages).toContainText('共 35 个版本');
  await expect(page.getByRole('status').filter({hasText:'正在处理资料'})).toHaveCount(0);
  await page.locator('.project-storage summary').click();
  await expect(page.locator('.project-storage')).toContainText('35 / 2000');
  await expect(page.locator('.project-storage p')).toBeVisible();
  await page.screenshot({path:info.outputPath(`project-storage-${width}.png`),fullPage:true,animations:'disabled'});
  await page.goto(`/workspace/assets?project=${project}`);
  await expect(page.getByRole('button',{name:'显示更多资料（30 / 35）'})).toBeVisible();
  await page.getByRole('button',{name:'显示更多资料（30 / 35）'}).click();
  await expect(page.locator('.aw-selectable-asset')).toHaveCount(35);
  await page.locator('.project-storage summary').click();
  await expect(page.locator('.project-storage')).toContainText('35 / 2000');
  await page.getByLabel('搜索资产').fill('Note-34');
  await expect(page.locator('.aw-asset-list')).toContainText('Note-34.md');
});
