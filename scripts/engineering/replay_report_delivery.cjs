// Offline SSR of real public delivery payloads; never calls a model or a service.
const {createRequire}=require('node:module');
const {resolve}=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const req=createRequire(resolve(__dirname,'../../apps/workbench/frontend/package.json'));
const {buildSync}=req('esbuild'),React=req('react'),{renderToStaticMarkup}=req('react-dom/server');
function load(file){
  const built=buildSync({entryPoints:[resolve(__dirname,'../../apps/workbench/frontend/vite/src/app',file)],
    bundle:true,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','react-dom'],loader:{'.css':'empty'},write:false});
  const mod={exports:{}};new Function('require','module','exports',built.outputFiles[0].text)(req,mod,mod.exports);return mod.exports;
}
const {ResearchDeliveryLayout}=load('ResearchDeliveryLayout.tsx');
const {AnswerReviewResult}=load('AnswerChallenge.tsx');
const {BoundCitationMarkdown}=load('BoundCitationMarkdown.tsx');
const payload=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
assert(payload.report?.narrative_markdown,'current report required');
const reviews=(payload.conversation||[]).filter(r=>r.answer_review);
const history=React.createElement('section',null,...reviews.map((r,i)=>React.createElement(AnswerReviewResult,
  {key:i,result:r.answer_review,onCitation:()=>{}})));
const report=React.createElement(BoundCitationMarkdown,{text:payload.report.narrative_markdown,citations:payload.report.citations,onCitation:()=>{}});
const render=(hasReport,historyOpen)=>renderToStaticMarkup(React.createElement(ResearchDeliveryLayout,
  {report,history,hasReport,historyOpen,onHistoryToggle:()=>{}}));
const html=render(true,false);
assert(html.indexOf('当前研究成果')<html.indexOf('历史交流与版本修改'));
assert(!html.match(/<details aria-label="历史交流与版本修改"[^>]*\bopen/));
assert(render(true,true).match(/<details aria-label="历史交流与版本修改"[^>]*\bopen/));
assert(render(false,false).match(/<details aria-label="历史交流与版本修改"[^>]*\bopen/));
assert(!html.includes('作者保留了原稿。'),'missing report edit array must not become unchanged verdict');
console.log(JSON.stringify({status:'pass',real_reviews:reviews.length,report_characters:payload.report.narrative_markdown.length,
  cases:['report_first','history_collapsed','history_open_on_request','no_report_history_visible','full_report_review_compatible']}));
