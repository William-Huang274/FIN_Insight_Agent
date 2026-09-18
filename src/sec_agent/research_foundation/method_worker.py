"""Native bounded worker tool cycle, reusing FIN's source-bound calculator.

Used by method qualification; no new arithmetic evaluator or research service.
"""
import operator
from typing import Annotated, Literal, TypedDict
from pydantic import Field, model_validator
from langgraph.graph import START, END, StateGraph

from .method_execution import Contract, MethodWorkResult
from .source_bound_calculator import SourceBoundCalculation, calculate_from_sources
from .method_submission import invoke_submission, SubmissionRejected


class WorkerAction(Contract):
    action: Literal['calculate', 'finish']
    calculations: list[SourceBoundCalculation] = Field(default_factory=list, max_length=8)
    result: MethodWorkResult | None = None

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


def compile_method_worker(*, call, actor, payload, record, max_tool_rounds=2, runtime_submissions=False):
    originals={p['id']:{'result_state':'source_bound_passage','writer_citable':True,
        'numeric_fact_authority':False,'passage':p['body'],'content_sha256':p['digest'],
        'source_url':r['source']['url'],'source_locator':p['locator']}
        for r in payload['read_results'] if r['status']=='readable' for p in r['items']}

    async def analyst(state):
        task={**payload,'tool_observations':state.get('observations',[]),
            'remaining_calculation_rounds':max_tool_rounds-state.get('tool_rounds',0)}
        task['instructions'] += (' 来源绑定计算器已启用。需要派生数值时action=calculate，calculations填原文数字绑定和公式，result=null；'
            '读到实际工具结果后再action=finish，calculations=[]，result填最终任务结果。'
            '数字/引文必须来自read_results的精确段落或已有CALC；引用原文仍填source_ids，计算结果填findings.calculation_refs。'
            '工具轮次耗尽后finish并如实保留未决，不得编造计算结果；运算通过不证明金融解释正确。')
        if runtime_submissions:
            try:
                action=await invoke_submission(call,actor,task,WorkerAction,record)
            except SubmissionRejected as exc:
                exc.receipt['tool_observations']=state.get('observations',[])
                return {'submission_failure':exc.receipt}
        else:
            action=WorkerAction.model_validate(await call(actor,task,WorkerAction))
        if action.action=='calculate' and state.get('tool_rounds',0)>=max_tool_rounds:
            raise ValueError('worker_calculation_limit_unresolved')
        return {'action':action.model_dump(mode='json')}

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
