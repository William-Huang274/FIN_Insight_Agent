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
                          completion_tool_rounds=0, runtime_submissions=False):
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

    graph=StateGraph(WorkerState)
    graph.add_node('analyst',analyst);graph.add_node('calculate',calculate)
    graph.add_edge(START,'analyst')
    graph.add_conditional_edges('analyst',lambda s:END if s.get('submission_failure') else
        'calculate' if s['action']['action']=='calculate' else END,['calculate',END])
    graph.add_edge('calculate','analyst')
    return graph.compile()
