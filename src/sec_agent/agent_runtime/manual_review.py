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


class ManualReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    base_version: int = Field(ge=1)
    report_markdown: str = Field(min_length=1, max_length=200000)
    reason: str = Field(min_length=1, max_length=4000)
    paper_edits: list[PaperEdit] = Field(default_factory=list, max_length=30)
    confirmed: bool


def manual_review_available(state):
    review = state.get('report_review') or {}
    return bool(state.get('report') and not state.get('research_stop_reason')
        and not review.get('unresolved_data_requests')
        and not any(f.get('responsibility') == 'data_tool' for f in review.get('findings', [])))


def apply_manual_review(state, decision, artifacts, *, owner='local-pilot'):
    from .dell_case_convergence_agent import answer_citations
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
        if before != edit.body:
            edits.append({'paper_id': edit.paper_id, 'actor': catalog[edit.paper_id].get('branch_id') or catalog[edit.paper_id].get('agent_id', 'specialist'),
                'title': catalog[edit.paper_id].get('thesis', edit.paper_id), 'before': before, 'after': edit.body})
    old = state['report']
    if old['narrative_markdown'] == decision.report_markdown and not edits:
        raise ValueError('没有正文修改；请使用原有审阅入口')
    # Bind direct SQL/passage/calculation references to saved receipts as well as
    # claim IDs. Unknown references fail here, before a no-model resume is sent.
    prose = '\n\n'.join([decision.report_markdown, *[c.get('interpretation', '') for c in old.get('charts', [])]])
    citations = answer_citations(prose, artifacts, [], prior_citations=old.get('citations', {}))
    history = {'number': len(state.get('human_edits', [])) + 1, 'owner': owner,
        'recorded_at': datetime.now(timezone.utc).isoformat(), 'reason': decision.reason,
        'base_version': decision.base_version, 'papers': edits,
        'report_before': old['narrative_markdown'], 'report_after': decision.report_markdown}
    return {'report': {**deepcopy(old), 'narrative_markdown': decision.report_markdown, 'citations': citations},
        'report_version': decision.base_version + 1, 'report_revision_reason': '人工修改：' + decision.reason,
        'phase': 'human_completed', 'human_edits': [*state.get('human_edits', []), history],
        'last_output_kind': 'report', 'conversation': [{'role': 'system',
            'content': f"人工修改 {history['number']} 次后确认完成：{decision.reason}。原始模型审查与运行记录保留；这不是模型自动核验通过。"}]}
