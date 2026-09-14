import { test, expect } from 'playwright/test';

for(const width of [1440,390]) test(`项目保存上传与新浏览器重查 ${width}`,async({page,browser},testInfo)=>{
  await page.setViewportSize({width,height:950});
  const name=`持久项目 ${width}`;
  await page.goto('/workspace/session');
  if(width<760) await page.getByRole('button',{name:'打开导航',exact:true}).click();
  const nav=page.locator(width<760?'.fs-nav-dialog':'.fs-sidebar');
  await nav.getByRole('button',{name:'管理项目',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'管理项目'});
  await expect(dialog.getByLabel('新项目名称')).toBeEnabled();
  await dialog.getByLabel('新项目名称').fill(name);
  await dialog.getByRole('button',{name:'创建项目',exact:true}).click();
  await expect(dialog.getByLabel('新项目名称')).toHaveValue('');
  await dialog.getByLabel('关闭项目管理').click();
  if(width<760)await page.getByRole('button',{name:'打开导航',exact:true}).click();
  await nav.getByRole('button',{name:`打开项目 ${name}`,exact:true}).click();
  await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();
  await page.getByLabel('添加项目资料',{exact:true}).setInputFiles({name:'合成资料.md',mimeType:'text/markdown',buffer:Buffer.from('# 留存率线索\n\n合成文本：留存率需要交叉核对。<script>window.projectInjected=true</script>')});
  await expect(page.getByRole('status')).toContainText('已保存到项目');
  await page.getByRole('textbox',{name:'查找项目资料'}).fill('留存率');
  await page.getByRole('button',{name:'查找',exact:true}).click();
  await expect(page.locator('.fs-project-documents article')).toHaveCount(1);
  await page.getByRole('button',{name:'阅读已保存正文',exact:true}).click();
  await expect(page.getByLabel('项目资料正文')).toContainText('留存率需要交叉核对');
  expect(await page.evaluate(()=>(window as any).projectInjected)).toBeUndefined();
  const url=page.url();
  await page.locator('.rs-main').evaluate(el=>{el.scrollTop=0;});
  await page.screenshot({path:testInfo.outputPath(`project-${width}.png`),fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  const second=await browser.newContext({viewport:{width,height:950}});
  try {const other=await second.newPage();await other.goto(url);
    await expect(other.getByRole('heading',{name,exact:true})).toBeVisible();
    await expect(other.locator('.fs-project-documents article')).toContainText('合成资料.md');
    expect(await other.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('finsight.project-index')))).toBe(false);
    await other.reload();await expect(other.locator('.fs-project-documents article')).toHaveCount(1);
  } finally {await second.close();}
});
