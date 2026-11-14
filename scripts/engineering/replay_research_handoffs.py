"""Offline scripted decisions through real tools/checkpoints; no network/model calls.

Run with --output <private artifact directory>. The fixture is fictional research,
not evidence about AI adoption. Artifacts distinguish captured tool input from
native provider traffic (which this replay never sends).
"""
import argparse
import asyncio
from contextlib import nullcontext
import html
import json
from pathlib import Path

from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sec_agent.agent_runtime.conversation_agent import GrantedTool
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
from sec_agent.agent_runtime.harness_delegate import delegation_payload, delegate_prompt
from sec_agent.agent_runtime.research_workpaper_tools import workpaper_tools
from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers, WorkpaperConflict


def paper(finding, **overrides):
    return dict(finding=finding, body=(finding+'。完整论证：比较同风险任务的交付成本、复核负担和客户采购安排。'
        '材料只覆盖试点；续约尚未发生。保留客户和供应商的不同立场，模型假设不能变成实际观测。\n')*90,
        conditions='同风险任务；复核成本受控；试点与续约分开', counterevidence='返工可能抵消节省；降价也可能来自竞争',
        remaining='续约未发生；新的实际成本比较仍会影响判断', next_decision='完成成本对比后再决定适用范围',
        disposition='continue', change='首次研究', dependencies=[], evidence_receipt_ids=[]) | overrides


async def replay(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if (directory/'state.sqlite').exists():
        raise ValueError('Choose a fresh output directory; preserve prior replay records.')
    question='虚构验收：AI采购能否增长，收益由客户还是供应商获得？'
    workspace=ResearchWorkpapers(directory/'workpapers.sqlite',root_id='offline',question=question,
        as_of='2026-11-14',check=lambda:None)
    events=[]; captures=[]; jobs={}; gate=asyncio.Event(); fast_gate=asyncio.Event()

    @tool
    def read_source_document(query: str):
        """Read a fictional authorized fixture with exact source identity."""
        return {'source_id':'FIXTURE::cost-v1','period':'2026Q3','unit':'CNY/task','revision':'v1',
                'text':'FICTIONAL: matched pilot tasks save 20% before customer review; renewals unobserved.',
                'query':query}

    async def call(bridge,name,args):
        result=await bridge.execute(name,args)
        assert result.status=='success', result.content
        payload=json.loads(result.content)
        assert not payload.get('error'), payload
        captures.append({'tool':name,'arguments':args,'result':payload})
        return payload, result

    async def dependency(bridge,topic):
        row,_=await call(bridge,'read_research_workpaper',{'topic_id':topic})
        return {k:row[k] for k in ('topic_id','revision','digest')} | {'use':'qualified','rationale':'试点成本只支持有条件的采用判断'}

    async def native(**kwargs):
        bridge=kwargs['bridge']; request=kwargs['request']; key=kwargs['key']; actor=request['current_topic_id']
        jobs[request['question']]={'key':key,'actor':actor,'bridge':bridge}
        captures.append({'native_input_projection':delegation_payload(request),
                         'tool_names':list(bridge.tools),'system_prompt':delegate_prompt(request,bridge.tools,topic_lead=kwargs['consultations'] is not None)})
        if request['question']=='客户采购专题':
            assert 'consult_research_agent' in bridge.tools
            await gate.wait()
            child,_=await call(bridge,'consult_research_agent',dict(question='完整交付成本',context='核对复核和返工成本',purpose='investigate'))
            nested=kwargs['consultations']
            await nested.tasks[child['task_id']]
            await call(bridge,'read_research_agent_result',{'task_id':child['task_id']})
            deps=[await dependency(bridge,child['topic_id'])]
            body=paper('采购可能增长，适用范围取决于交付总成本',dependencies=deps)
        else:
            assert 'consult_research_agent' not in bridge.tools
            if request['question']=='供应商竞争':
                await fast_gate.wait()
            _,receipt=await call(bridge,'read_source_document',{'query':request['question']})
            body=paper('成本下降有利于采用' if request['question']=='完整交付成本' else '竞争降价可能把收益转给客户',
                       evidence_receipt_ids=[receipt.tool_call_id])
        await call(bridge,'publish_research_workpaper',{'base_revision':0,'workpaper':body})
        events.append(request['question'])
        return '已保存完整底稿；研究限制见版本化成果。'

    async with AsyncSqliteSaver.from_conn_string(str(directory/'state.sqlite')) as saver:
        grants=[GrantedTool(read_source_document,'read','fictional fixture')]
        service=HarnessConsultations(directory=directory/'jobs',saver=saver,grants=grants,tid='offline',rid='r1',
            check=lambda:None,scope=nullcontext,budget=object(),environment={},model='deepseek-flash',basis={},
            as_of='2026-11-14',public_sink=lambda _:None,research_question=question,
            native_delegate=native,workspace=workspace,topic_delegate=native)
        root=HarnessBusinessTools(grants=grants+workpaper_tools(workspace)+service.tools(),checkpointer=saver,
                                  thread_id='offline',check=lambda:None)
        service.parent=root
        await root.initialize({'question':question,'messages':[]})
        try:
            customer,_=await call(root,'consult_research_agent',dict(question='客户采购专题',context='持续判断采购条件',purpose='investigate',topic_lead=True))
            competitor,_=await call(root,'consult_research_agent',dict(question='供应商竞争',context='检验定价权',purpose='investigate'))
            waiting,_=await call(root,'read_next_research_result',{'task_ids':[customer['task_id'],competitor['task_id']]})
            assert waiting['status']=='waiting'
            fast_gate.set()
            assert (await service.dispatch_ready(timeout=5))['status']=='ready'
            first,_=await call(root,'read_next_research_result',{'task_ids':[customer['task_id'],competitor['task_id']]})
            assert first['task_id']==competitor['task_id']
            assert not service.tasks[customer['task_id']].done()
            assert 'body' not in first['workpaper'] and 'opinion' not in first
            # Parent did not absorb child source journal; explicit evidence read imports exact identity.
            state=await root.state()
            assert not any(getattr(m,'name',None)=='read_source_document' for m in state['messages'])
            evidence_id=first['workpaper']['evidence_receipt_ids'][0]
            await call(root,'read_workpaper_evidence',{'receipt_id':evidence_id})
            assert any(getattr(m,'tool_call_id',None)==evidence_id for m in (await root.state())['messages'])
            gate.set(); await service.tasks[customer['task_id']]
            customer_result,_=await call(root,'read_research_agent_result',{'task_id':customer['task_id']})
            deps=[await dependency(root,c['topic_id']) for c in (customer,competitor)]
            cost=jobs['完整交付成本']
            cost_evidence=workspace.read('root',cost['actor'],field='metadata')['evidence_receipt_ids'][0]
            await call(root,'read_workpaper_evidence',{'receipt_id':cost_evidence})
            await call(root,'assess_research_result',dict(task_id=customer['task_id'],result_digest=customer_result['result_digest'],
                disposition='accepted',finding='采购结论在试点范围内成立',scope_and_conditions='同风险任务；复核负担受控',
                counterevidence='续约未知；返工可能抵消节省',unresolved='原题的供应商价值归属仍需综合',evidence_receipt_ids=[cost_evidence]))
            candidates=[{'receipt_id':m.tool_call_id} for m in (await root.state())['messages']
                        if getattr(m,'name',None) in {'read_research_workpaper','read_workpaper_evidence'}]
            retired=await service.context_projection(candidates)
            assert any(r['receipt']['result'].get('context_state')=='accepted_result_summary' for r in retired['replacements'])
            assert all(r['receipt']['result']['workpaper_conditions']['counterevidence'] for r in retired['replacements'])
            captures.append({'accepted_context_projection':retired})
            reread=await root.execute('read_research_workpaper',{'topic_id':customer['topic_id']})
            assert not (await service.context_projection([{'receipt_id':reread.tool_call_id}]))['replacements']
            await call(root,'publish_research_workpaper',{'base_revision':0,'workpaper':paper('采用增长，价值归属仍取决于成本和竞争',dependencies=deps)})
            before,_=await call(root,'prepare_research_synthesis',{'topic_ids':['root'],'scope_rationale':'覆盖采购、成本和竞争；续约仍未发生'})
            assert len(before['selected'])==4
            for topic in before['selected']:
                await call(root,'read_synthesis_material',{'snapshot_id':before['snapshot_id'],'topic_id':topic})
            workspace.bind(before['snapshot_id'],'fictional-report-v1')
            await call(cost['bridge'],'publish_research_workpaper',{'base_revision':1,
                'workpaper':paper('返工成本抵消试点节省',change='新增同口径复核成本改变原假设',
                                 counterevidence='部分低风险任务仍节省',disposition='bounded_answer')})
            stale=workspace.catalog()
            restored=await service.context_projection([{'receipt_id':r['receipt_id'],'retired':True} for r in retired['replacements']])
            assert all(r['receipt'].get('context_notice') for r in restored['replacements'])
            captures.append({'reopened_context_projection':restored})
            assert next(t for t in stale['topics'] if t['topic_id']=='root')['status']=='needs_reassessment'
            try:
                workspace.require_current_binding('fictional-report-v1')
                raise AssertionError('Old report was allowed')
            except WorkpaperConflict as exc:
                assert str(exc)=='research_changed_refresh_synthesis'
            blocked=await root.execute('prepare_research_synthesis',{'topic_ids':['root'],'scope_rationale':'旧认识尚未重评'})
            assert blocked.status=='success' and json.loads(blocked.content)['error']=='synthesis_dependency_stale'
            cb=jobs['客户采购专题']['bridge']
            await call(cb,'publish_research_workpaper',{'base_revision':1,'workpaper':paper('采用集中在复核负担较低的任务',
                dependencies=[await dependency(cb,cost['actor'])],change='缩小增长适用范围')})
            await call(root,'publish_research_workpaper',{'base_revision':1,'workpaper':paper('采用分化；供应商定价权仍承压',
                dependencies=[await dependency(root,c['topic_id']) for c in (customer,competitor)],change='成本证据更新了采购解释')})
            # Reading an old job returns its own original artifact, not the current replacement.
            old,_=await call(root,'read_research_agent_result',{'task_id':customer['task_id']})
            assert old['workpaper']['revision']==1 and old['workpaper']['current_revision']==2
            final,_=await call(root,'prepare_research_synthesis',{'topic_ids':['root'],'scope_rationale':'成本与采购改判；供应商竞争保留独立判断'})
            authoring=[]
            for topic in final['selected']:
                offset=0
                while offset is not None:
                    material,_=await call(root,'read_synthesis_material',{'snapshot_id':final['snapshot_id'],'topic_id':topic,'offset':offset,'max_characters':2000})
                    authoring.append(material); offset=material['next_offset']
            workspace.bind(final['snapshot_id'],'fictional-report-v2')
            workspace.require_current_binding('fictional-report-v2')
            await service.ensure_finished()
            summary={'mode':'offline_scripted_decisions_no_model_or_network', 'completion_order':events,
                'checks':{'first_completion_without_wave_barrier':True,'three_level_and_cross_branch_adoption':True,
                    'no_automatic_child_journal_import':True,'exact_evidence_readback':True,'changed_premise_propagation':True,
                    'stale_report_rejected':True,'old_job_keeps_original_version':True,'full_paginated_authoring_readback':True,
                    'accepted_windows_retired_and_changed_premises_reopened':True},
                'first_handoff_characters':len(json.dumps(first,ensure_ascii=False)),
                'full_competitor_body_characters':workspace.read('root',competitor['topic_id'])['total_characters'],
                'final_selected_versions':final['selected'],'authoring_window_characters':sum(len(m['body']) for m in authoring),
                'authoring_response_characters':sum(len(json.dumps(m,ensure_ascii=False)) for m in authoring),
                'limitations':['Scripted decisions do not demonstrate model research quality.',
                    'Authoring inputs are captured business-tool outputs, not a paid provider request.',
                    'Read records prove windows were supplied, not model comprehension.']}
        finally:
            gate.set(); fast_gate.set(); await service.close()
    # Reopen the durable database after all actor sessions are gone.
    reopened=ResearchWorkpapers(directory/'workpapers.sqlite',root_id='offline',question=question,as_of='2026-11-14',check=lambda:None)
    assert reopened.read('root',cost['actor'],1)['body']!=reopened.read('root',cost['actor'],2)['body']
    for name,value in [('summary',summary),('handoffs',captures),('authoring-input',authoring),('stale-state',stale)]:
        (directory/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
    sections=[('验收结果',summary),('实际交接与工具输入输出',captures),('成文读取窗口（精确版本）',authoring),('底层改判后的状态',stale)]
    page='<!doctype html><meta charset="utf-8"><title>研究交接离线回放</title><style>body{max-width:1100px;margin:40px auto;font:16px/1.7 system-ui;padding:0 24px;color:#192b42}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6fa;padding:18px}summary{cursor:pointer;font-weight:600;margin:20px 0}</style><h1>研究交接离线回放</h1><p>虚构材料、脚本化决策，运行真实工具、SQLite检查点和成文版本校验。没有调用模型或联网；不评价研究结论是否正确。</p>'
    page+=('<h2>本次实际走过的路径</h2><ol><li>总负责人同时派发客户采购专题与供应商竞争调查。</li>'
           '<li>竞争调查先返回。客户采购尚未完成时，总负责人即可读取竞争成果；子任务原始日志未自动进入父状态。</li>'
           '<li>采购负责人继续派发交付成本调查，读取其完整论证，保存自己的专题成果。总负责人采用精确版本形成当前认识。</li>'
           '<li>成本底稿新增返工观察，采购专题与总判断进入待重评；竞争专题保持原版。旧任务入口仍返回自己的原始交付版。</li>'
           '<li>旧成文快照被拒绝。采购与总判断完成版本更新后，重新冻结目录，按窗口读完整论证并绑定新稿。</li></ol>'
           '<p>首次交接 '+str(summary['first_handoff_characters'])+' 字符；对应底稿正文 '+str(summary['full_competitor_body_characters'])+
           ' 字符。成文实际读取 '+str(summary['authoring_window_characters'])+' 字符论证，含版本与条件元数据的回执共 '+str(summary['authoring_response_characters'])+
           ' 字符，分窗口供给。这里只统计字符，不冒充 token 或付费节省。</p>'
           '<p>下列明细分别保留实际工具参数、交接回执、版本变化及成文窗口，可展开核查。脚本预设的研究判断没有经过真实模型生成。</p>')
    page+=''.join('<details'+(' open' if i==0 else '')+'><summary>'+title+'</summary><pre>'+html.escape(json.dumps(value,ensure_ascii=False,indent=2))+'</pre></details>' for i,(title,value) in enumerate(sections))
    (directory/'replay.html').write_text(page,encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--output',required=True)
    args=parser.parse_args(); print(json.dumps(asyncio.run(replay(args.output)),ensure_ascii=False,indent=2))
