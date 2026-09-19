"""Bounded role-isolated qualification path over existing LangGraph workers.

Not the production report graph. Context is projected explicitly per role;
checkpoint state and archived messages are never wholesale model inputs.
"""
from copy import deepcopy
from typing import Literal, TypedDict

from langgraph.graph import START, END, StateGraph
from pydantic import Field, model_validator

from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from .method_execution import (Contract, ResearchObligation, MethodWorkResult,
    EvidencePointer, assess_result_contract, method_payload)
from .method_handoffs import judgment_directory
from .method_submission import invoke_submission, SubmissionRejected
from .method_worker import compile_method_worker, NUMERIC_GUIDANCE


LEAD_GUIDANCE = '''你是上游研究负责人。按总问题委派专业任务，审阅交付能否回答派工问题、是否违反常识、是否存在证据越界或可疑推断；不替下游重写专业底稿。
返修应指出具体疑点并保留正确事实，但不得以“只改格式、不需改结论”免除下游的全稿专业自查；下游发现关联错误应自行修复。数字留痕问题与算术错误分别判断。
问卷角色只负责问卷设计、统计口径、变化与关系判断，自行完成计算和一致性检查。把商业综合留在上游，不要求它证明调查没有测量的收入、留存或投资价值。
交接中的判断、限定、支撑步骤和版本须一起阅读。机械合同通过、下游自报完成不是正确性保证。证据不足时收窄可用结论，不抹掉已成立的观察。
contract_errors是当前候选的机械问题，不是金融判错；可以连同内容疑点一起返修，但不能在仍有合同问题时接受交付。来源计算回执和来源获取回执分别使用其已有字段，不创造工具结果。
发现疑点可inspect具体原文段/页，返回原文只作为证据，不加载下游提示词或会话历史。需要修专业内容时return具体判断和问题，不给预写答案，不自己补成正确稿。无法在边界内解决则stop。
judgment_tables是runtime无损去重后的步骤、范围与来源目录；按每条判断的引用连同限定一起阅读，不可只看statement。
evidence_access明确本轮实际提供的原文页。下游public_basis/步骤说明是作者陈述，source_catalog是目录，均不等于你已核对原文。计算回执只能支持其中实际执行的计算，不能覆盖正文新增的算式。仅审阅交付内部一致性时如实写明；需声称与原文一致时先inspect对应原文。无需替下游重做全部工作，但不能把未读原文报为已核查。
accept须逐项记录当前主张是否合理以及允许的使用范围；不得把曾用当活跃/付费、不同人群当同一分母，或把相关性直接升级为因果。报告的是公开审阅依据，不索取私有推理。'''


class SpecialistAssignment(Contract):
    question: str = Field(min_length=1, max_length=2500)
    purpose: str = Field(min_length=1, max_length=1500)
    success_criteria: list[str] = Field(min_length=1, max_length=8)


class JudgmentCheck(Contract):
    judgment_ref: str = Field(min_length=1)
    disposition: Literal['usable','limited','needs_repair']
    reason: str = Field(min_length=1)


class SpecialistReview(Contract):
    action: Literal['inspect','accept','return','stop']
    paper_digest: str = Field(pattern=r'^[0-9a-f]{64}$')
    checks: list[JudgmentCheck] = Field(max_length=40)
    evidence_requests: list[str] = Field(default_factory=list, max_length=4)
    issues: list[str] = Field(default_factory=list, max_length=12)
    accepted_use: str
    remaining_questions: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode='after')
    def action_fields(self):
        if bool(self.evidence_requests) != (self.action=='inspect'):
            raise ValueError('only_inspect_requests_evidence')
        if self.action=='return' and not self.issues:
            raise ValueError('return_requires_issue')
        if self.action=='accept' and (not self.accepted_use.strip() or any(c.disposition=='needs_repair' for c in self.checks)):
            raise ValueError('accept_requires_use_scope_and_no_unrepaired_check')
        return self


def specialist_context(assignment, *, task_id, as_of, reads, repair=None):
    """Build anew from explicit fields, never copy a Lead payload or history."""
    obligation=ResearchObligation(obligation_id=task_id,parent_question=assignment.purpose,
        question=assignment.question,business_scope='问卷专业责任；不承担上游商业综合。',
        as_of=as_of,method_ids=['survey_analysis'],required_steps=['S1','S2','S3','S4'],
        expectation='conditional',materiality='core',source_requirements=[r['source']['url'] for r in reads])
    payload={**method_payload(obligation,shared_method_ids=()),'read_results':deepcopy(reads),
        'success_criteria':deepcopy(assignment.success_criteria),
        'capabilities':['read_results完整原文','source_bound_calculator']}
    payload['instructions']+=' 本角色负责专业底稿完整且内部一致；完成后返回上级审阅，不代做商业综合。'
    if repair:
        payload['current_workpaper']=deepcopy(repair['result'])
        payload['return_issues']=deepcopy(repair['issues'])
        payload['instructions']+=' 本次只修本专业问题及所有受影响内容，保留有效内容。上级意见可错，必须以原件核验。允许补充必要计算。'
    return payload


def factor_judgments(directory):
    """Intern repeated objects, preserving every field and list order exactly."""
    judgments=deepcopy(directory)
    tables={'steps':{},'scopes':{},'sources':{}}

    def intern(table,value):
        ref=canonical_sha256(value)
        tables[table][ref]=deepcopy(value)
        return ref

    for judgment in judgments.values():
        judgment['basis_step_refs']=[intern('steps',s) for s in judgment.pop('basis_steps')]
        judgment['scope_ref']=intern('scopes',judgment.pop('scope'))
        judgment['source_pointer_refs']=[intern('sources',s) for s in judgment.pop('source_pointers')]
    return judgments,tables


def expand_judgments(judgments,tables):
    """Deterministic inverse, also usable when inspecting an archived handoff."""
    directory=deepcopy(judgments)
    for judgment in directory.values():
        judgment['basis_steps']=[deepcopy(tables['steps'][r]) for r in judgment.pop('basis_step_refs')]
        judgment['scope']=deepcopy(tables['scopes'][judgment.pop('scope_ref')])
        judgment['source_pointers']=[deepcopy(tables['sources'][r]) for r in judgment.pop('source_pointer_refs')]
    return directory


def delivery_context(assignment, obligation, result, reads, observations):
    """Lossless findings/qualifiers/steps; no specialist methods or messages."""
    passages=[{**deepcopy(p),'source':deepcopy(r['source'])} for r in reads for p in r['items']]
    body=result.model_dump(mode='json')
    output={'obligation':obligation,'result':body,'review_evidence':passages}
    judgments,tables=factor_judgments(judgment_directory([output]))
    return {'format':'specialist_delivery.v2','assignment':assignment.model_dump(mode='json'),'paper_digest':canonical_sha256(body),
        'summary':result.summary,'execution':result.execution,'unresolved':deepcopy(result.unresolved),
        'task_note':result.task_note.model_dump(mode='json'),
        'judgments':judgments,'judgment_tables':tables,
        'source_catalog':[{k:v for k,v in p.items() if k!='body'} for p in passages],
        'calculations':[deepcopy(o['result']) for o in observations if o['status']=='ok'],
        'financial_semantics_checked_by_runtime':False}


class DelegationState(TypedDict, total=False):
    assignment: dict
    worker_result: dict
    delivery: dict
    review: dict
    inspected: list[dict]
    inspection_rounds: int
    repair_rounds: int
    terminal: str
    failure: dict


def compile_specialist_delegation(*, question, as_of, reads, call, record,
                                  checkpointer=None, max_inspections=1, max_repairs=1,
                                  initial_worker_result=None, initial_assignment=None):
    """One specialist task with bounded evidence inspection/return branches."""
    if max_inspections<0 or max_repairs<0:
        raise ValueError('negative_delegation_limit')
    if (initial_worker_result is None)!=(initial_assignment is None):
        raise ValueError('resume_requires_assignment_and_original_worker_result')
    sources={p['id']:p for r in reads for p in r['items']}
    if len(sources)!=sum(len(r['items']) for r in reads):
        raise ValueError('duplicate_source_id')

    async def plan(state):
        if initial_worker_result is not None:
            assignment=SpecialistAssignment.model_validate(initial_assignment)
            record('resume_existing_delivery',{'assignment_origin':'provided_previous_task_not_new_model_dispatch',
                'original_digest':canonical_sha256(initial_worker_result)})
            payload=specialist_context(assignment,task_id=initial_worker_result['action']['result']['obligation_id'],as_of=as_of,reads=reads)
            return {'assignment':assignment.model_dump(mode='json'),**package(assignment,payload,deepcopy(initial_worker_result))}
        payload={'role':'upstream_planner','instructions':LEAD_GUIDANCE,'question':question,
            'as_of':as_of,'specialist_scope':'survey_analysis: S1设计、S2变化、S3关系、S4一致交付',
            'source_catalog':[{'url':r['source']['url'],'pages':len(r['items'])} for r in reads]}
        try:
            assignment=await invoke_submission(call,'lead-plan',payload,SpecialistAssignment,record)
        except SubmissionRejected as exc:
            return {'terminal':'plan_format_failure','failure':exc.receipt}
        return {'assignment':assignment.model_dump(mode='json')}

    def package(assignment,payload,result):
        if result.get('submission_failure'):
            return {'terminal':'specialist_format_failure','worker_result':result}
        paper=MethodWorkResult.model_validate(result['action']['result'])
        evidence={p['id']:EvidencePointer(source_id=p['id'],digest=p['digest'],locator=p['locator'],
            published_at=None,known_at=as_of,observation_period='provided survey period; current capture',
            vintage='known_as_of',access_state='readable') for r in reads for p in r['items']}
        calc={o['result']['calculation_id']:o['result'] for o in result['observations'] if o['status']=='ok'}
        errors=assess_result_contract(ResearchObligation.model_validate(payload['obligation']),paper,evidence,calculations=calc)
        record('specialist_contract',{'errors':errors,'financial_semantics_checked':False})
        packet=delivery_context(assignment,payload['obligation'],paper,reads,result['observations'])
        packet['contract_errors']=errors
        record('role_handoff',packet)
        return {'worker_result':result,'delivery':packet,'inspected':[]}

    async def worker(state):
        assignment=SpecialistAssignment.model_validate(state['assignment'])
        repair=None; observations=[]
        if state.get('repair_rounds',0):
            repair={'result':state['worker_result']['action']['result'],'issues':state['review']['issues']}
            observations=state['worker_result']['observations']
        task_id=state['worker_result']['action']['result']['obligation_id'] if repair else 'survey-delegated'
        payload=specialist_context(assignment,task_id=task_id,as_of=as_of,reads=reads,repair=repair)
        result=await compile_method_worker(call=call,actor='survey-specialist',payload=payload,
            record=record,runtime_submissions=True,max_tool_rounds=2,completion_tool_rounds=1).ainvoke({'observations':observations,'tool_rounds':0})
        return package(assignment,payload,result)

    async def review(state):
        payload={'role':'upstream_reviewer','instructions':LEAD_GUIDANCE+NUMERIC_GUIDANCE,'question':question,
            'delivery':deepcopy(state['delivery']),'requested_evidence':deepcopy(state.get('inspected',[])),
            'evidence_access':{'original_passage_ids_in_this_request':[p['id'] for p in state.get('inspected',[])],
                'author_basis_is_original_evidence':False,'source_catalog_is_original_evidence':False,
                'calculation_receipts_cover_only_their_recorded_operations':True},
            'remaining_inspections':max_inspections-state.get('inspection_rounds',0),
            'remaining_returns':max_repairs-state.get('repair_rounds',0)}
        try:
            result=await invoke_submission(call,'lead-review',payload,SpecialistReview,record)
        except SubmissionRejected as exc:
            return {'terminal':'review_format_failure','failure':exc.receipt}
        refs=[c.judgment_ref for c in result.checks]
        current=state['delivery']['judgments']
        if result.paper_digest!=state['delivery']['paper_digest'] or len(refs)!=len(set(refs)) or not set(refs)<=current.keys():
            return {'terminal':'review_identity_failure','review':result.model_dump(mode='json')}
        if result.action=='accept' and (set(refs)!=set(current) or state['delivery']['execution']!='completed'
                                       or state['delivery']['contract_errors']):
            return {'terminal':'review_incomplete_acceptance','review':result.model_dump(mode='json')}
        if result.action=='return' and not state['delivery']['contract_errors'] and not any(c.disposition=='needs_repair' for c in result.checks):
            return {'terminal':'return_without_located_problem','review':result.model_dump(mode='json')}
        terminal=''
        if result.action in {'accept','stop'}:
            terminal='lead_accepted_pending_host_semantic_review' if result.action=='accept' else 'lead_stopped'
        elif result.action=='inspect' and state.get('inspection_rounds',0)>=max_inspections:
            terminal='inspection_limit'
        elif result.action=='return' and state.get('repair_rounds',0)>=max_repairs:
            terminal='repair_limit'
        return {'review':result.model_dump(mode='json'),'terminal':terminal}

    def inspect(state):
        ids=state['review']['evidence_requests']
        if len(ids)!=len(set(ids)) or any(s not in sources for s in ids):
            return {'terminal':'unknown_or_duplicate_evidence_request'}
        evidence=[deepcopy(sources[s]) for s in ids]
        record('scoped_evidence_inspection',{'paper_digest':state['delivery']['paper_digest'],'items':evidence})
        return {'inspected':evidence,'inspection_rounds':state.get('inspection_rounds',0)+1}

    def returned(state):
        record('specialist_return',state['review'])
        return {'repair_rounds':state.get('repair_rounds',0)+1}

    graph=StateGraph(DelegationState)
    for name,node in [('plan',plan),('worker',worker),('review',review),('inspect',inspect),('returned',returned)]:
        graph.add_node(name,node)
    graph.add_edge(START,'plan')
    graph.add_conditional_edges('plan',lambda s:END if s.get('terminal') else 'review' if initial_worker_result is not None else 'worker',[END,'worker','review'])
    graph.add_conditional_edges('worker',lambda s:END if s.get('terminal') else 'review',[END,'review'])
    graph.add_conditional_edges('review',lambda s:END if s.get('terminal') else 'inspect' if s['review']['action']=='inspect' else 'returned',[END,'inspect','returned'])
    graph.add_conditional_edges('inspect',lambda s:END if s.get('terminal') else 'review',[END,'review'])
    graph.add_edge('returned','worker')
    return graph.compile(checkpointer=checkpointer)
