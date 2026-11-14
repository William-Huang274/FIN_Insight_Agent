"""Full scripted tool replay plus adversarial version/surface checks; zero model calls."""
import argparse
import asyncio
import html
import json
import shutil
from pathlib import Path
from langchain_core.messages import ToolMessage
from scripts.engineering.replay_research_authoring import replay
from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers, ResearchWorkpaper, WorkpaperConflict
from sec_agent.agent_runtime.research_authoring import authoring_context_replacements, material_context_replacements
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256


def chars(value):return len(json.dumps(value,ensure_ascii=False,separators=(',',':')))


async def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise ValueError('Use a fresh output directory')
    baseline=await replay(output/'tool-chain')
    checks=dict(baseline['checks']);observations={}
    shutil.copy2(output/'tool-chain/workpapers.sqlite',output/'probe.sqlite')
    s=ResearchWorkpapers(output/'probe.sqlite',root_id='authoring-fixture',
        question='虚构验收：AI采购增长如何转化为客户价值与供应商收益？',as_of='2026-11-14',check=lambda:None)
    trace=json.loads((output/'tool-chain/trace.json').read_text(encoding='utf8'))
    reports=[r['arguments']['report'] for r in trace if r.get('tool')=='save_research_report']
    current=s.authoring.context();revision=current['revision']
    frozen=next(r['result'] for r in reversed(trace) if r.get('tool')=='prepare_research_synthesis')
    with s.connection() as db:
        reverted=s.authoring._issues(db,s.authoring._state(db),reports[0])
    checks['reverted_saved_prose_reopens_resolved_issues']=all(i['status']=='open' for i in reverted)
    noop=s.authoring.update(revision,{'reason':'No substantive changes'},'audit-noop')
    checks['empty_patch_keeps_revision']=noop['revision']==revision and noop['unchanged']
    customer=next(x for x in current['outline'] if x['id']=='customer')
    s.authoring.update(revision,{'reason':'Only presentation order','sections':[{**customer,'order':99}]},'audit-order')
    checks['order_preserves_synthesis']=not s.snapshot(frozen['snapshot_id'])['understanding_changed']
    checks['order_preserves_issue_dispositions']=all(i['status']=='resolved' for i in s.authoring.context(include_history=True)['issues'])
    cursor=s.catalog(limit=20)['next_cursor']
    s.register('optional','root','Synthetic unadopted branch')
    template=s.read('root',next(iter(frozen['selected'])),field='metadata')
    payload=ResearchWorkpaper.model_validate({k:v for k,v in template.items() if k in ResearchWorkpaper.model_fields}|{'body':'Synthetic probe'}).model_dump(mode='json')
    payload.update(body='Unrelated synthetic observation',dependencies=[],evidence_receipt_ids=[],change='Unadopted notification')
    s.publish('optional',0,payload,{},'audit-new')
    fresh=s.snapshot(frozen['snapshot_id'])
    checks['unrelated_arrival_not_invalidating']=not fresh['changed_topics'] and fresh['unselected_updates']==['optional']
    checks['catalog_incremental']=len(s.catalog(after=cursor)['topics'])==1
    local=s.authoring.context(['customer']);whole=s.authoring.context()
    checks['local_branch_not_expanding_other_arguments']=set(local['judgments'])=={'customer'} and set(local['lead_overview'])=={'thesis'}
    observations['context_characters']={'whole':chars(whole),'customer':chars(local)}
    msgs=[ToolMessage(name='read_authoring_context',tool_call_id=k,content=json.dumps(local)) for k in ['older','newer']]
    candidates=[{'receipt_id':m.tool_call_id} for m in msgs]
    compact=authoring_context_replacements(msgs,candidates,local)
    checks['same_view_deduplicated']=len(compact)==1
    checks['missing_active_replacement_keeps_original']=not authoring_context_replacements(msgs,candidates[:1],local)
    restored=authoring_context_replacements(msgs,[{'receipt_id':'older','retired':True}],local)
    checks['compacted_replacement_restores_original']=restored[0]['receipt']['result']['judgments']==local['judgments']
    observations['view_projection_characters']={'before':chars(local),'after':chars(compact[0]['receipt'])}
    topic=local['materials'][0]['topic_id'];full=s.read('root',topic)
    full['result_digest']=canonical_sha256(full)
    windows=[];offset=0
    while True:
        row=s.read('root',topic,offset=offset,max_characters=2200);row['result_digest']=canonical_sha256(row)
        windows.append(row)
        if row['next_offset'] is None:break
        offset=row['next_offset']
    materials=[ToolMessage(name='read_research_workpaper',tool_call_id='full',content=json.dumps(full))]+[
        ToolMessage(name='read_synthesis_material',tool_call_id=f'window{i}',content=json.dumps(w)) for i,w in enumerate(windows)]
    candidates=[{'receipt_id':m.tool_call_id} for m in materials]
    projected=material_context_replacements(materials,candidates)
    checks['research_to_writing_duplicate_retired']=len(projected)==1 and projected[0]['receipt_id']=='full'
    observations['material_projection_characters']={'before':chars(full),'after':chars(projected[0]['receipt'])}
    restore=material_context_replacements(materials,[{'receipt_id':'full','retired':True,'context_state':'duplicate_material_window'}])
    checks['material_restored_after_native_surface_compaction']=restore[0]['receipt']['result']['body']==full['body']
    review=s.authoring.review_handoff(1)
    checks['review_has_current_judgment_and_change_entry']=bool(review['lead_judgments'] and review['changed_judgments'] and review['readback'])
    checks['exact_history_preserved']=s.authoring.context(revision=1)['revision']==1
    result={'checks':checks,'observations':observations,'paid_model_calls':0,
        'scope':'Real tool contracts and scripted decisions; native surface replacement tested separately with Node. No semantic model or paid compaction evaluation.'}
    (output/'summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (output/'review-input.json').write_text(json.dumps(review,ensure_ascii=False,indent=2),encoding='utf8')
    (output/'surface-projections.json').write_text(json.dumps({'authoring':compact,'materials':projected,'restored_material':restore},ensure_ascii=False,indent=2),encoding='utf8')
    rows=''.join(f'<tr><td>{html.escape(k)}</td><td>{"PASS" if v else "FAIL"}</td></tr>' for k,v in checks.items())
    (output/'replay.html').write_text('<!doctype html><meta charset="utf-8"><title>研究链路完整离线验收</title>'
        '<style>body{font:16px/1.7 system-ui;max-width:1100px;margin:40px auto;padding:20px;background:#f5f7fb}table{border-collapse:collapse;width:100%;background:white}td{padding:10px;border:1px solid #dbe2ed}pre{white-space:pre-wrap}</style>'
        '<h1>研究链路完整离线验收</h1><p>虚构 AI 采购案例；工具、版本与交接验收，无付费模型调用。</p>'
        '<p><a href="tool-chain/replay.html">完整工具链回放</a> · <a href="summary.json">机器可读结果</a> · <a href="review-input.json">复核输入</a> · <a href="surface-projections.json">上下文替换与恢复</a></p>'
        '<table>'+rows+'</table><h2>输入大小（JSON 字符，不是 token）</h2><pre>'+html.escape(json.dumps(observations,ensure_ascii=False,indent=2))+'</pre>'
        '<p>正文映射不证明金融语义。未重写原生工具调用参数；完整写入参数保留协议配对，由原生 258k 压缩处理。此回放不冒充付费原生压缩。</p>',encoding='utf8')
    if not all(checks.values()):raise AssertionError(result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(asyncio.run(run(parser.parse_args().output)),ensure_ascii=False,indent=2))
