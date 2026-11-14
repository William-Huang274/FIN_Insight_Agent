"""Scripted authoring discontinuities through real native tool contracts; no model/network calls."""
import argparse
import asyncio
from contextlib import nullcontext
import html
import json
from pathlib import Path
from langchain_core.messages import messages_to_dict
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
from sec_agent.agent_runtime.conversation_agent import GrantedTool, research_system_prompt
from sec_agent.agent_runtime.harness_artifact_tools import artifact_tools
from sec_agent.agent_runtime.harness_business_tools import HarnessBusinessTools
from sec_agent.agent_runtime.harness_consultations import HarnessConsultations
from sec_agent.agent_runtime.harness_delegate import delegation_payload, delegate_prompt
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers
from sec_agent.agent_runtime.research_workpaper_tools import workpaper_tools
from sec_agent.agent_runtime.working_memory import WorkingMemory


def judgment(key, statement, refs=(), depends=()):
    return dict(id=key,statement=statement,rationale='虚构比较：已观察的任务表现结合采购条件形成预测；续约与盈利需分别判断。',
        conditions='同期间、同风险任务；价格及复核成本按明确情景',counterevidence='重试成本和价格竞争可能改变价值归属',
        remaining='实际续约仍需后续观察',workpapers=list(refs),depends_on=list(depends))


def section(key, ids, order):
    return dict(id=key,title=key,question='这一关系怎样影响采购与价值归属？',role='从已研究关系推进总问题',judgment_ids=ids,order=order)


def paper(finding, receipt):
    return dict(finding=finding,body=(finding+'。虚构完整论证：原始观察、客户和供应商口径分别比较；'
        '任务节省需扣除复核和重试，采购扩张与供应商盈利存在价格传导这一环。\n')*50,
        conditions='虚构样本；保持任务风险可比',counterevidence='客户试点不等于续约；价格下降可能压缩供应商收益',
        remaining='未来续约没有发生',next_decision='比较净成本和价格传导，更新原题判断',
        disposition='bounded_answer',change='当前派发调查所得结果',evidence_receipt_ids=[receipt])


async def replay(directory):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    if any(directory.iterdir()):raise ValueError('Use a fresh directory; preserve replay artifacts.')
    question='虚构验收：AI采购增长如何转化为客户价值与供应商收益？'
    workspace=ResearchWorkpapers(directory/'workpapers.sqlite',root_id='authoring-fixture',question=question,as_of='2026-11-14',check=lambda:None)
    captures=[]; checks={}; jobs={}; source_reads=[]
    @tool(response_format='content_and_artifact')
    def read_source_document(query: str):
        """Read one fictional fixture, preserving exact source and version."""
        source_reads.append(query)
        source={'source_id':'PASSAGE::authoring-fixture','passage_id':'PASSAGE::authoring-fixture',
                'title':'Fictional procurement observation','result_state':'source_bound_passage',
                'writer_citable':True,'numeric_fact_authority':False,
                'passage':'Synthetic observation for engineering replay only. Not real financial evidence.',
                'period':'2026Q3','revision':'fixture-v1'}
        artifact={'operation':'read','items':[source]}
        return json.dumps({'query':query,**source}),artifact

    async def call(bridge,name,args,*,error=None):
        result=await bridge.execute(name,args)
        assert result.status=='success',(name,result.content)
        value=json.loads(result.content)
        captures.append({'tool':name,'arguments':args,'result':value})
        if error:assert value.get('error')==error,(name,value)
        else:assert not value.get('error'),(name,value)
        return value,result

    async def dependency(root,topic):
        row,_=await call(root,'read_research_workpaper',{'topic_id':topic})
        return {k:row[k] for k in ('topic_id','revision','digest')}|{'use':'qualified','rationale':'采用这一调查的明确范围和条件'}

    async def native(**kwargs):
        bridge=kwargs['bridge'];request=kwargs['request']
        captures.append({'native_prompt':delegate_prompt(request,bridge.tools,topic_lead=False),
                         'native_assignment':delegation_payload(request),'tool_names':list(bridge.tools)})
        issue=(request.get('authoring_issue') or {}).get('issue')
        if issue:
            assert issue['quote'] in initial_report['narrative_markdown']
            assert request['authoring_issue']['judgments']
            checks['delegation_has_exact_issue_and_current_basis']=True
        _,source=await call(bridge,'read_source_document',{'query':request['question']})
        findings={'customer':'试点节省尚未扣完复核成本','pricing':'价格竞争将部分节省转给客户','energy':'能源约束因部署地区而异',
                  'customer_followup':'低风险任务净节省仍在；高风险任务返工抵消收益，采购应分层',
                  'pricing_followup':'降价也来自竞争，供应商利润取决于利用率与产品差异'}
        topic=request['current_topic_id']
        base=next(t['current_revision'] or 0 for t in workspace.catalog()['topics'] if t['topic_id']==topic)
        await call(bridge,'publish_research_workpaper',{'base_revision':base,'workpaper':paper(findings[request['question']],source.tool_call_id)})
        return '完整论证已保存，包含当前条件判断。'

    initial_report={'title':'虚构工程回放：采购增长与价值归属','narrative_markdown':
        '## 总判断\n采用增长将普遍带来供应商收益。\n## 客户\n节省直接转化为续费。\n'
        '## 定价\n价格下降全部来自规模。\n## 能源\n能源成本是价格。\n'
        '本段仅为虚构工程案例，验证出处与交接，不是现实行业结论。客户分支关注任务成本及后续采购，'
        '定价分支关注供给竞争与价值归属，能源分支解释部署条件。案例故意保留三处不连贯判断，'
        '用于检查作者补查后能否更新局部分析及其总括，同时保留准确来源和历史版本。[PASSAGE::authoring-fixture]'}
    async with AsyncSqliteSaver.from_conn_string(str(directory/'state.sqlite')) as saver:
        grants=[GrantedTool(read_source_document,'read','fictional original')]
        service=HarnessConsultations(directory=directory/'jobs',saver=saver,grants=grants,tid='authoring',rid='fixture',
            check=lambda:None,scope=nullcontext,budget=object(),environment={},model='fixture',basis={},as_of='2026-11-14',
            public_sink=lambda _:None,research_question=question,native_delegate=native,workspace=workspace,topic_delegate=native)
        memory=WorkingMemory(directory/'notes.sqlite',owner='fixture',workspace='authoring',actor='lead')
        root=HarnessBusinessTools(grants=grants+workpaper_tools(workspace)+service.tools()+artifact_tools(
            artifacts=lambda _:CaseArtifacts.from_observed_sources({},case_id='authoring',research_as_of='2026-11-14'),
            memory=memory,delivery_intent='report',require_review=False,research_workspace=workspace),
            checkpointer=saver,thread_id='authoring',check=lambda:None)
        service.parent=root
        await root.initialize({'question':question,'messages':[]})
        (directory/'root-tool-entry.json').write_text(json.dumps({
            'scope':'Actual common prompt builder and admitted fixture tools; no provider request was sent.',
            'system_prompt':research_system_prompt(root.tools),
            'tools':{name:tool.tool_call_schema.model_json_schema() for name,tool in root.tools.items()}},
            ensure_ascii=False,indent=2),encoding='utf8')
        try:
            for key in ['customer','pricing','energy']:
                job,_=await call(root,'consult_research_agent',dict(question=key,context='虚构初始调查',purpose='investigate'))
                jobs[key]=job
            await asyncio.gather(*(service.tasks[j['task_id']] for j in jobs.values()))
            refs={}
            for key,job in jobs.items():
                result,_=await call(root,'read_research_agent_result',{'task_id':job['task_id']})
                refs[key]=await dependency(root,job['topic_id'])
                await call(root,'read_workpaper_evidence',{'receipt_id':result['workpaper']['evidence_receipt_ids'][0]})
            nodes={key:judgment(key,key,[ref]) for key,ref in refs.items()}
            nodes['thesis']=judgment('thesis','采用增长将普遍带来供应商收益',depends=['customer','pricing'])
            sections=[section('summary',['thesis'],0),section('customer',['customer'],1),section('pricing',['pricing'],2),section('energy',['energy'],3)]
            await call(root,'update_research_understanding',{'base_revision':0,'patch':dict(reason='形成初始认识及暂定骨架',
                judgments=list(nodes.values()),sections=sections,lead_judgment_ids=['thesis'])})
            initial_view,old_receipt=await call(root,'read_authoring_context',{})
            (directory/'understanding-v1.json').write_text(json.dumps(initial_view,ensure_ascii=False,indent=2),encoding='utf8')
            await call(root,'save_research_report',{'report':initial_report,'base_version':0})
            for key,kind,quote in [('customer','missing_link','节省直接转化为续费。'),('pricing','stale_basis','价格下降全部来自规模。'),('energy','expression','能源成本是价格。')]:
                await call(root,'open_authoring_issue',dict(base_revision=1,report_version=1,
                    issue=dict(id=key,section_ids=[key],kind=kind,question='核对这处判断为何成立以及对总判断的影响',quote=quote)))
            await call(root,'resolve_authoring_issue',dict(issue_id='customer',base_revision=1,disposition='bounded_answer',
                explanation='尚未补查',result_workpapers=[],report_version=1),error='investigation_result_required_even_for_bounded_answer')
            # Two independently linked investigations; wording is repaired locally.
            followups={}
            for key in ['customer','pricing']:
                job,_=await call(root,'consult_research_agent',dict(question=key+'_followup',context='请调查相关关系，允许修改原解释。',
                    purpose='investigate',topic_id=jobs[key]['topic_id'],authoring_issue_id=key))
                followups[key]=job
            await asyncio.gather(*(service.tasks[j['task_id']] for j in followups.values()))
            for key,job in followups.items():
                await call(root,'read_research_agent_result',{'task_id':job['task_id']})
                refs[key]=await dependency(root,job['topic_id'])
            stale,_=await call(root,'read_authoring_context',{})
            checks['multiple_impacts_preserve_unaffected_branch']=set(stale['requires_reassessment'])=={'customer','pricing','thesis'} and stale['judgments']['energy']==initial_view['judgments']['energy']
            nodes['customer']=judgment('customer','低风险任务更可能扩大采购，高风险任务取决于返工成本',[refs['customer']])
            nodes['pricing']=judgment('pricing','成本节省优先流向客户，供应商收益需产品差异与利用率支撑',[refs['pricing']])
            await call(root,'update_research_understanding',dict(base_revision=1,patch=dict(reason='两项补查改变局部认识',judgments=[nodes['customer'],nodes['pricing']])))
            partial,_=await call(root,'read_authoring_context',{})
            checks['summary_remains_pending_after_local_updates']=set(partial['requires_reassessment'])=={'thesis'}
            await call(root,'prepare_research_synthesis',dict(topic_ids=[r['topic_id'] for r in refs.values()],scope_rationale='成文选择'),error='reassess_judgments_before_synthesis')
            nodes['thesis']=judgment('thesis','采购分层增长，价值更先体现为客户净节省；供应商分化',depends=['customer','pricing'])
            await call(root,'update_research_understanding',dict(base_revision=2,patch=dict(reason='新的比较改变总判断',judgments=[nodes['thesis']])))
            current,new_receipt=await call(root,'read_authoring_context',{})
            projection=await service.context_projection([{'receipt_id':old_receipt.tool_call_id}])
            checks['old_same_scope_context_retires_after_current_read']=bool(projection['replacements'])
            captures.append({'native_context_projection':projection})
            excerpts={'summary':'采购将分层增长，客户净节省比供应商普遍增利更有依据。',
                'customer':'在复核成本受控的低风险任务中，我倾向采购扩张；高风险任务的返工可能抵消节省。',
                'pricing':'竞争降价使部分收益转向客户，供应商获益更依赖利用率与产品差异。',
                'energy':'能源是部署成本的一项，区域供给约束影响成本与交付时点。'}
            final={'title':'虚构工程回放：采购分层增长，价值先向客户转移',
                   'narrative_markdown':'\n\n'.join('## '+key+'\n'+text for key,text in excerpts.items())+
                   '\n\n这是一份虚构工程回放，用于检验版本、条件和交接；不是现实行业观点。[PASSAGE::authoring-fixture]'}
            await call(root,'save_research_report',{'report':final,'base_version':1})
            for key in ['customer','pricing','energy']:
                await call(root,'resolve_authoring_issue',dict(issue_id=key,base_revision=3,disposition='revised',
                    explanation='补查后更新相关认识和正文；表达问题只澄清定义。',result_workpapers=[refs[key]] if key!='energy' else [],report_version=2))
            frozen,_=await call(root,'prepare_research_synthesis',dict(topic_ids=[r['topic_id'] for r in refs.values()],scope_rationale='根据新比较组织当前认识，保留原题范围'))
            windows=[]
            for key,ref in refs.items():
                view,_=await call(root,'read_authoring_context',{'section_ids':[key]})
                windows.append(view)
                offset=0
                while True:
                    value,_=await call(root,'read_synthesis_material',dict(snapshot_id=frozen['snapshot_id'],topic_id=ref['topic_id'],offset=offset,max_characters=2200))
                    windows.append(value)
                    if value['next_offset'] is None:break
                    offset=value['next_offset']
            bound,_=await call(root,'bind_research_synthesis',dict(snapshot_id=frozen['snapshot_id'],report_version=2,
                section_uses=[dict(section_id=k,excerpt=v) for k,v in excerpts.items()]))
            checks['actual_prose_has_judgment_and_exact_basis']=len(bound['authoring']['sections'])==4
            mapping=[];offset=0
            while True:
                chunk,_=await call(root,'read_current_report',dict(field='argument_map',offset=offset,max_characters=12000))
                mapping.append(chunk['text'])
                if chunk['next_offset'] is None:break
                offset=chunk['next_offset']
            argument_map=json.loads(''.join(mapping))
            checks['saved_prose_traceable_after_binding']=argument_map['found'] and argument_map['understanding_revision']==3
            await call(root,'deliver_current_report',{'version':2})
            checks['actual_delivery_succeeds']=bool((await root.state()).get('delivery'))
            checks['unchanged_judgment_not_rewritten']=current['judgments']['energy']==initial_view['judgments']['energy']
            restored=ResearchWorkpapers(workspace.path,root_id='authoring-fixture',question=question,as_of='2026-11-14',check=lambda:None)
            checks['restart_retains_history_and_all_resolutions']=restored.authoring.context(revision=1)['judgments']==initial_view['judgments'] and all(i['status']=='resolved' for i in restored.authoring.context()['issues'])
            old_result,_=await call(root,'read_research_agent_result',{'task_id':jobs['customer']['task_id']})
            checks['old_job_returns_original_version']=old_result['workpaper']['revision']==1
            (directory/'authoring-input.json').write_text(json.dumps(windows,ensure_ascii=False,indent=2),encoding='utf8')
            (directory/'current-understanding.json').write_text(json.dumps(restored.authoring.context(),ensure_ascii=False,indent=2),encoding='utf8')
            (directory/'report-binding.json').write_text(json.dumps(bound,ensure_ascii=False,indent=2),encoding='utf8')
            (directory/'argument-map.json').write_text(json.dumps(argument_map,ensure_ascii=False,indent=2),encoding='utf8')
            (directory/'final-report.md').write_text(final['narrative_markdown'],encoding='utf8')
            (directory/'root-business-messages.json').write_text(json.dumps(messages_to_dict((await root.state())['messages']),
                ensure_ascii=False,indent=2),encoding='utf8')
        finally:await service.close()
    summary={'paid_model_calls':0,'checks':checks,'source_reads':source_reads,'tool_calls':len([c for c in captures if 'tool' in c]),
             'scope':'Scripted decisions through real tools and SQLite/consultation contracts; not financial or live model quality.'}
    (directory/'trace.json').write_text(json.dumps(captures,ensure_ascii=False,indent=2),encoding='utf8')
    (directory/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>增量认识与成文断点回放</title><style>body{max-width:1100px;margin:36px auto;padding:0 20px;font:16px/1.65 system-ui;color:#223}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f6fa;padding:16px}details{margin:14px 0}summary{cursor:pointer;font-weight:600}table{border-collapse:collapse;width:100%}td,th{padding:12px;border:1px solid #ccd;text-align:left;vertical-align:top}th{background:#eef3fc}.table{overflow:auto}</style><h1>增量认识与成文断点回放</h1><p>虚构工程案例；没有模型调用。脚本规定研究发现，不证明模型会自行发现问题。</p>'
    page+='<h2>这次实际走过的回路</h2><p>保存初稿 → 同时登记三处断点 → 两项独立补查、一项表达澄清 → 更新局部认识 → 发现总判断仍待重评 → 更新总判断与正文 → 逐项处理断点 → 读取完整论证 → 绑定并交付。</p>'
    page+='<div class="table"><table><tr><th>位置</th><th>原判断</th><th>更新后交付正文</th></tr>'
    before={'summary':'采用增长将普遍带来供应商收益。','customer':'节省直接转化为续费。','pricing':'价格下降全部来自规模。','energy':'能源成本是价格。'}
    for key in excerpts:
        page+='<tr>'+''.join('<td>'+html.escape(value)+'</td>' for value in (key,before[key],excerpts[key]))+'</tr>'
    page+='</table></div><p>能源判断的研究记录未变，只澄清表达；客户与定价更新使总判断重新评估。正文可以按下方 argument-map 回到判断、底稿与原始材料。</p><h2>工程检查</h2><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'
    for name in ['root-tool-entry.json','understanding-v1.json','current-understanding.json','authoring-input.json','report-binding.json','argument-map.json','final-report.md','trace.json']:
        page+='<details><summary>'+html.escape(name)+'</summary><pre>'+html.escape((directory/name).read_text(encoding='utf8'))+'</pre></details>'
    (directory/'replay.html').write_text(page+'</html>',encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    print(json.dumps(asyncio.run(replay(parser.parse_args().output)),ensure_ascii=False,indent=2))
