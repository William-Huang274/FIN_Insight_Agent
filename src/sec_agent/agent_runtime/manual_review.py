"""Human editorial decisions at the existing report review checkpoint.

FIN owns the meaning of human completion. LangGraph owns checkpoint history;
source bindings remain server-owned and are never supplied by the browser.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, Field


class PaperEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paper_id: str = Field(pattern=r'^P\d+$')
    body: str = Field(min_length=1, max_length=100000)


class ChartEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    chart_index: int = Field(ge=0)
    interpretation: str = Field(min_length=1, max_length=12000)


class ManualReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: int = Field(ge=1)
    report_markdown: str = Field(min_length=1, max_length=200000)
    reason: str = Field(min_length=1, max_length=4000)
    paper_edits: list[PaperEdit] = Field(default_factory=list, max_length=30)
    chart_edits: list[ChartEdit] = Field(default_factory=list, max_length=32)
    confirmed: bool


def manual_review_available(state):
    review = state.get('report_review') or {}
    return bool(state.get('report') and not state.get('research_stop_reason')
        and not review.get('unresolved_data_requests')
        and not any(f.get('responsibility') == 'data_tool' for f in review.get('findings', [])))


def paper_owner_role(state, paper):
    saved = next((p for p in state.get('case_papers', []) if p.get('agent_id') == paper.get('author')), {})
    task_id = saved.get('task', {}).get('task_id')
    return next((t['owner_role'] for t in state.get('research_tasks', [])
                 if t.get('task_id') == task_id and t.get('owner_role')),
                paper.get('branch_id') or paper.get('author', 'specialist'))


def apply_manual_review(state, decision, artifacts, *, owner='local-pilot'):
    from .report_synthesis_agent import answer_citations, answer_reference_ids
    if not manual_review_available(state):
        raise ValueError('数据或运行问题尚未解决，不能通过人工修改标记完成')
    if not decision.confirmed or not decision.reason.strip() or not decision.report_markdown.strip():
        raise ValueError('请确认已检查报告、图表和剩余意见，并填写修改说明')
    if state.get('report_version') != decision.base_version:
        raise ValueError('报告已更新，请重新打开后修改')
    if len({p.paper_id for p in decision.paper_edits}) != len(decision.paper_edits):
        raise ValueError('同一底稿不能重复提交')
    catalog = {p['paper_id']: p for p in artifacts.catalog()['papers']}
    previous = {p['paper_id']: p['after'] for h in state.get('human_edits', []) for p in h['papers']}
    edits = []
    for edit in decision.paper_edits:
        if edit.paper_id not in catalog:
            raise ValueError('底稿不属于当前研究')
        before = previous.get(edit.paper_id, artifacts.read_paper(edit.paper_id)['narrative_markdown'])
        if answer_reference_ids(edit.body):
            answer_citations(edit.body, artifacts, [], prior_citations=state['report'].get('citations', {}))
        if before != edit.body:
            edits.append({'paper_id': edit.paper_id, 'actor': paper_owner_role(state, catalog[edit.paper_id]),
                'title': catalog[edit.paper_id].get('thesis', edit.paper_id), 'before': before, 'after': edit.body})
    old = state['report']
    charts = deepcopy(old.get('charts', []))
    chart_edits = []
    if len({e.chart_index for e in decision.chart_edits}) != len(decision.chart_edits):
        raise ValueError('同一图表不能重复提交')
    for edit in decision.chart_edits:
        if edit.chart_index >= len(charts) or not edit.interpretation.strip():
            raise ValueError('请选择当前报告的图表并填写说明')
        chart = charts[edit.chart_index]
        before = chart.get('interpretation', '')
        if before != edit.interpretation:
            chart_edits.append({'chart_index': edit.chart_index, 'title': chart.get('title', '图表'),
                'before': before, 'after': edit.interpretation})
            chart['interpretation'] = edit.interpretation
    if old['narrative_markdown'] == decision.report_markdown and not edits and not chart_edits:
        raise ValueError('没有正文修改；请使用原有审阅入口')
    # Bind direct SQL/passage/calculation references to saved receipts as well as
    # claim IDs. Unknown references fail here, before a no-model resume is sent.
    prose = '\n\n'.join([decision.report_markdown, *[c.get('interpretation', '') for c in charts]])
    citations = answer_citations(prose, artifacts, [], prior_citations=old.get('citations', {}))
    history = {'number': len(state.get('human_edits', [])) + 1, 'owner': owner,
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'reason': decision.reason,
        'base_version': decision.base_version, 'papers': edits, 'charts': chart_edits,
        'report_before': old['narrative_markdown'], 'report_after': decision.report_markdown}
    return {'report': {**deepcopy(old), 'narrative_markdown': decision.report_markdown, 'citations': citations, 'charts': charts},
        'report_version': decision.base_version + 1, 'report_revision_reason': '人工修改：' + decision.reason,
        'phase': 'human_completed', 'human_edits': [*state.get('human_edits', []), history],
        'last_output_kind': 'report', 'conversation': [{'role': 'system',
            'content': f"人工修改 {history['number']} 次后确认完成：{decision.reason}。原始模型审查与运行记录保留；这不是模型自动核验通过。"}]}
