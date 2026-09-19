"""Native bounded worker tool cycle, reusing FIN's source-bound calculator.

Used by method qualification; no new arithmetic evaluator or research service.
"""
import operator
from copy import deepcopy
from typing import Annotated, Literal, TypedDict
from pydantic import Field, model_validator
from langgraph.graph import START, END, StateGraph

from .method_execution import Contract, MethodWorkResult
from .source_bound_calculator import SourceBoundCalculation, calculate_from_sources
from .method_submission import invoke_submission, SubmissionRejected
from sec_agent.agent_runtime.evidence_resolution import parsing_record
from sec_agent.agent_runtime.authoring_context import AuthoringBrief, bind_authoring, stage_methods, validate_authoring


class WorkerAction(Contract):
    action: Literal['calculate', 'finish']
    calculations: list[SourceBoundCalculation] = Field(default_factory=list, max_length=8)
    result: MethodWorkResult | None = None

    @classmethod
    def normalize_submission_envelope(cls, value):
        """Wrap a complete work result; no text repair, tool action or acceptance."""
        required = {name for name, field in MethodWorkResult.model_fields.items() if field.is_required()}
        if (required <= value.keys() <= MethodWorkResult.model_fields.keys()
                and not {'action', 'result', 'calculations'} & value.keys()):
            MethodWorkResult.model_validate(value)
            wrapped = {'action': 'finish', 'calculations': [], 'result': deepcopy(value)}
            return wrapped, [parsing_record(
                'complete_method_result_finish_envelope_v1', deepcopy(value), deepcopy(wrapped),
                content_unchanged=True, financial_acceptance=False, tool_execution=False)]
        return value, []

    @model_validator(mode='after')
    def exclusive_actions(self):
        if self.action == 'calculate' and (not self.calculations or self.result is not None):
            raise ValueError('calculate_requires_requests_and_null_result')
        if self.action == 'finish' and (self.calculations or self.result is None):
            raise ValueError('finish_requires_result_and_empty_calculations')
        return self


class WorkerState(TypedDict, total=False):
    action: dict
    tool_rounds: int
    observations: Annotated[list[dict], operator.add]
    submission_failure: dict
    runtime_parsing: Annotated[list[dict], operator.add]
    authoring_context: dict
    authoring_blocked: dict


NUMERIC_GUIDANCE = (' 新增数值运算（包括解释段中的加减、比例和代入数值的界限）应执行计算并绑定回执；'
    '原文直接披露的数字只需来源引用。纯符号恒等式、集合包含和一般界限可以写明推导及条件，无须为符号证明伪造CALC；'
    '一旦报告具体派生数值，就不能用“数学说明”豁免其计算留痕。计算正确与人群、分母、含义正确分别自查。')


def normalize_worker_receipts(action, observations):
    """Repair only an unambiguous receipt category, never infer claim support."""
    normalized=action.model_copy(deep=True)
    if normalized.action!='finish':
        return normalized,[]
    known={o['result']['calculation_id'] for o in observations if o['status']=='ok'}
    paper=normalized.result
    before=paper.model_dump(mode='json')
    for step in paper.steps:
        moved=[r for r in step.execution_receipt_refs if r in known]
        if moved:
            step.calculation_refs=list(dict.fromkeys([*step.calculation_refs,*moved]))
        step.execution_receipt_refs=[r for r in step.execution_receipt_refs if r not in known]
    bound={r for row in [*paper.steps,*paper.findings] for r in row.calculation_refs}
    # A task-wide unbound ID has no claim location: keep it for explicit review.
    paper.task_note.execution_receipt_refs=[r for r in paper.task_note.execution_receipt_refs
                                           if r not in known & bound]
    after=paper.model_dump(mode='json')
    records=[] if before==after else [parsing_record(
        'known_calculation_receipt_category_v1',before,after,
        claim_support_not_inferred=True,financial_acceptance=False,tool_execution=False)]
    return normalized,records


def compile_method_worker(*, call, actor, payload, record, max_tool_rounds=2,
                          completion_tool_rounds=0, runtime_submissions=False, authoring_stages=False,
                          entry_phase='research'):
    if entry_phase not in {'research','prepare_workpaper'} or (entry_phase!='research' and not authoring_stages):
        raise ValueError('invalid_worker_entry_phase')
    if max_tool_rounds<0 or completion_tool_rounds not in (0,1):
        raise ValueError('invalid_worker_calculation_limits')
    total_rounds=max_tool_rounds+completion_tool_rounds
    originals={p['id']:{'result_state':'source_bound_passage','writer_citable':True,
        'numeric_fact_authority':False,'passage':p['body'],'content_sha256':p['digest'],
        'source_url':r['source']['url'],'source_locator':p['locator']}
        for r in payload['read_results'] if r['status']=='readable' for p in r['items']}

    async def analyst(state):
        task={**payload,'tool_observations':state.get('observations',[]),
            'remaining_calculation_rounds':max(0,total_rounds-state.get('tool_rounds',0)),
            'calculation_budget':{'normal_rounds':max_tool_rounds,'completion_rounds':completion_tool_rounds,
                'used_rounds':state.get('tool_rounds',0),'total_round_limit':total_rounds,
                'phase':'completion' if state.get('tool_rounds',0)>=max_tool_rounds else 'analysis'},
            'receipt_catalog':{'calculation_refs':[o['result']['calculation_id'] for o in state.get('observations',[]) if o['status']=='ok'],
                'execution_receipt_refs':'Only source-access/execution receipts actually supplied in task; not CALC IDs.'}}
        task['instructions'] += (' 来源绑定计算器已启用。需要派生数值时action=calculate，calculations填原文数字绑定和公式，result=null；'
            'remaining_calculation_rounds大于0时，calculate会实际执行并将回执送入下一次模型调用；本次不必同时finish，已有工具回执也不表示禁止新增必要计算。'
            '读到实际工具结果后再action=finish，calculations=[]，result填最终任务结果。'
            '数字/引文必须来自read_results的精确段落或已有CALC；引用原文仍填source_ids，计算结果填findings.calculation_refs。'
            '工具轮次耗尽后finish并如实保留未决，不得编造计算结果；运算通过不证明金融解释正确。')+NUMERIC_GUIDANCE
        if completion_tool_rounds:
            task['instructions']+=' 预留补算轮用于成稿自查新发现的必要计算；它已计入总上限，不重置预算，不用于反复试答案。'
        if authoring_stages:
            task['authoring_phase']='research'
            task['instructions']+=' 此阶段提交经过专业自查的研究底稿；随后由你整理公开判断，再进入底稿成文阶段。不得把问题留给上游替你解决。'
        if runtime_submissions:
            try:
                action=await invoke_submission(call,actor,task,WorkerAction,record)
            except SubmissionRejected as exc:
                exc.receipt['tool_observations']=state.get('observations',[])
                return {'submission_failure':exc.receipt}
        else:
            action=WorkerAction.model_validate(await call(actor,task,WorkerAction))
        if action.action=='calculate' and state.get('tool_rounds',0)>=total_rounds:
            raise ValueError('worker_calculation_limit_unresolved')
        action,records=normalize_worker_receipts(action,state.get('observations',[]))
        for row in records:
            record('worker_runtime_compatibility_parse',row)
        return {'action':action.model_dump(mode='json'),'runtime_parsing':records}

    def calculate(state):
        lookup=dict(originals)
        for row in state.get('observations',[]):
            if row['status']=='ok':
                lookup[row['result']['calculation_id']]=row['result']
        observations=[]
        for raw in state['action']['calculations']:
            try:
                result=calculate_from_sources(SourceBoundCalculation.model_validate(raw),lambda sid:lookup.get(sid,{}))
                lookup[result['calculation_id']]=result
                observation={'status':'ok','request':raw,'result':result}
            except ValueError as exc:
                observation={'status':'rejected','request':raw,'error':str(exc),
                    'financial_semantics_checked':False,'retry_guidance':'Correct original source binding/formula; never relabel a source number as assumption.'}
            record('worker_calculation',observation);observations.append(observation)
        return {'observations':observations,'tool_rounds':state.get('tool_rounds',0)+1}

    def writing_basis(state):
        return {'research_result':deepcopy(state['action']['result']),
                'originals':deepcopy(payload['read_results']),
                'calculations':deepcopy(state.get('observations',[])),
                'assignment':deepcopy(payload.get('obligation')),
                'return_issues':deepcopy(payload.get('return_issues',[]))}

    async def prepare(state):
        if state.get('action',{}).get('action')!='finish':
            raise ValueError('authoring_resume_requires_saved_research_result')
        basis=writing_basis(state)
        task={'role':'survey_specialist_lead','authoring_phase':'prepare_workpaper',
              'instructions':'你仍是本专题负责人。整理当前专业研究状态、判断取舍、证据条件和未决项，不重做研究，不承担商业综合。ready判断的是能否交付本次有界专业底稿，不是所有信息是否齐全。正常覆盖限制、范围外未测量结果、精度不足可随有限判断交付；只有尚未解决的问题使核心受托结论无法负责任地表达时才ready=false，并说明影响哪个核心结论。不能把普通边界自动升级成全稿阻塞，也不能隐藏真正阻塞。',
              'stage_methods':stage_methods('prepare_workpaper',domain='survey_analysis'),
              'basis':basis}
        try:
            brief=await invoke_submission(call,actor,task,AuthoringBrief,record)
        except SubmissionRejected as exc:
            return {'submission_failure':exc.receipt}
        packet=bind_authoring(brief.model_dump(mode='json'),owner=actor,stage='workpaper',basis=basis)
        record('authoring_prepared',packet)
        if not brief.ready:
            return {'authoring_context':packet,'authoring_blocked':{'reason':'author_retains_material_research','brief':brief.model_dump(mode='json')}}
        return {'authoring_context':packet}

    async def write(state):
        validate_authoring(state['authoring_context'],owner=actor,basis=writing_basis(state))
        # Fresh payload: no Lead instructions, conversation transcript or research dispatch template.
        task={'role':'survey_specialist_lead','authoring_phase':'workpaper',
              'instructions':'依据你已整理的authoring_context完成可读且可交接的专题底稿，保留来源、计算身份、适用条件和关联步骤。保持原研究含义；新实质问题须如实保留未决，不得编造新计算或假装已解决。提交完整MethodWorkResult。',
              'stage_methods':stage_methods('workpaper',domain='survey_analysis'),
              'authoring_context':deepcopy(state['authoring_context'])}
        try:
            paper=await invoke_submission(call,actor,task,MethodWorkResult,record)
        except SubmissionRejected as exc:
            return {'submission_failure':exc.receipt}
        action,records=normalize_worker_receipts(WorkerAction(action='finish',result=paper),state.get('observations',[]))
        for row in records:record('worker_runtime_compatibility_parse',row)
        record('authoring_completed',{'owner':actor,'basis_digest':state['authoring_context']['basis_digest'],'result':action.result.model_dump(mode='json')})
        return {'action':action.model_dump(mode='json'),'runtime_parsing':records}

    graph=StateGraph(WorkerState)
    graph.add_node('analyst',analyst);graph.add_node('calculate',calculate)
    graph.add_node('prepare_workpaper',prepare);graph.add_node('write_workpaper',write)
    graph.add_edge(START,'prepare_workpaper' if entry_phase=='prepare_workpaper' else 'analyst')
    graph.add_conditional_edges('analyst',lambda s:END if s.get('submission_failure') else
        'calculate' if s['action']['action']=='calculate' else 'prepare_workpaper' if authoring_stages else END,['calculate','prepare_workpaper',END])
    graph.add_edge('calculate','analyst')
    graph.add_conditional_edges('prepare_workpaper',lambda s:END if s.get('submission_failure') or s.get('authoring_blocked') else 'write_workpaper',['write_workpaper',END])
    graph.add_edge('write_workpaper',END)
    return graph.compile()
