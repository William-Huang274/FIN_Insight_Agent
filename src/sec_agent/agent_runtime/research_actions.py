"""Version-bound research actions projected from the existing tool journal.

Models judge coverage and materiality. The host checks identity and disposition,
not whether a financial interpretation is correct. No second task/state store.
"""
import json
from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, Field

from .conversation_agent import GrantedTool
from .research_graph_contracts import canonical_sha256


class ResearchAction(BaseModel):
    question_or_claim: str = Field(min_length=1)
    gap: str = Field(min_length=1)
    consequence: str = Field(min_length=1, description='How resolving this gap could change the answer.')
    next_action: str = Field(min_length=1, description='Discriminating investigation, calculation, rewrite or justified narrowing; not just be cautious.')
    material: bool = True


def receipts(messages, name=None):
    for message in messages:
        if not isinstance(message, ToolMessage) or message.status != 'success':
            continue
        if name and message.name != name:
            continue
        try:
            value = json.loads(message.content)
        except (TypeError, ValueError):
            continue
        if isinstance(value, dict):
            yield message, value


def assessment_tool(task_id, request, prior_actions=()):
    known_prior = {row['action_id'] for row in prior_actions}
    @tool
    def record_research_assessment(scope_explanation: str, actions: list[ResearchAction], runtime: ToolRuntime,
                                  resolved_action_ids: list[str] | None = None):
        """Save your investigation/review findings before returning your final opinion.
        Explain which parts of the original question the actual evidence supports and what
        could change the main answer. Record only consequential unresolved issues as actions;
        an empty list is valid when justified. You may investigate first and record only residual
        gaps. Do not infer coverage from source counts. This records your judgment, not approval.
        Repeated calls replace this task's assessment; prior receipts remain readable.
        A review of the current report may resolve prior action IDs actually supplied in its
        handoff, after checking the author's text and evidence. Explain why in scope_explanation.
        Never mark an issue resolved just because the author acknowledged it.
        """
        if not scope_explanation.strip():
            return {'recorded': False, 'feedback': 'Explain the scope actually supported by the evidence.'}
        resolved = list(dict.fromkeys(resolved_action_ids or []))
        if resolved and (request.get('purpose') != 'review' or not request.get('report')
                         or any(key not in known_prior for key in resolved)):
            return {'recorded':False, 'feedback':'Only a current-report review can resolve IDs from its supplied prior_actions.'}
        rows = []
        for action in actions:
            row = action.model_dump()
            row['action_id'] = task_id + ':' + canonical_sha256(row)[:16]
            rows.append(row)
        value = dict(recorded=True, task_id=task_id, scope_explanation=scope_explanation,
                     actions=rows, resolved_action_ids=resolved, target_digest=canonical_sha256(request),
                     reviewed_report_digest=canonical_sha256(request['report']) if request.get('report') else None,
                     status='model_assessment_not_runtime_certification')
        return Command(update={'messages': [ToolMessage(name='record_research_assessment',
            tool_call_id=runtime.tool_call_id, content=json.dumps(value, ensure_ascii=False))]})

    return GrantedTool(record_research_assessment, 'task_artifact_write',
        '委派者保存自身研究意见；不能修改作者稿件', recovery_semantics='checkpoint_only')


def latest_assessment(messages, task_id):
    matches = [value for _, value in receipts(messages, 'record_research_assessment')
               if value.get('recorded') and value.get('task_id') == task_id]
    return matches[-1] if matches else None


def research_action_view(state):
    """Only imported task results create author obligations; child journal copies do not."""
    messages = state.get('messages', [])
    imported = {}
    for message, value in receipts(messages, 'read_research_agent_result'):
        if value.get('status') == 'completed' and value.get('task_id'):
            imported[value['task_id']] = (message, value)
    responses = {}
    for message, value in receipts(messages, 'respond_research_action'):
        if value.get('recorded'):
            responses[value['action_id']] = {**value, 'receipt_id': message.tool_call_id}
    digest = canonical_sha256(state['report']) if state.get('report') else None
    actions, unstructured, resolutions = [], [], {}
    for task_id, (message, result) in imported.items():
        assessment = result.get('assessment')
        if not assessment:
            unstructured.append({'task_id': task_id, 'purpose': result.get('purpose'),
                'readback': {'tool': 'read_research_agent_result', 'arguments': {'task_id': task_id}}})
            continue
        for action in assessment.get('actions', []):
            response = responses.get(action['action_id'])
            current = bool(response and response.get('report_digest') == digest)
            actions.append({**action, 'task_id': task_id, 'review_receipt': message.tool_call_id,
                'reviewed_report_digest': result.get('reviewed_report_digest'),
                'author_response': response, 'response_current': current,
                'status': 'author_disposition_not_independent_clearance' if current else 'needs_author_decision',
                'review_readback': {'tool': 'read_research_agent_result', 'arguments': {'task_id': task_id}}})
        for action_id in assessment.get('resolved_action_ids', []):
            resolutions[action_id] = {'task_id':task_id,'review_receipt':message.tool_call_id,
                'report_digest':result.get('reviewed_report_digest'),
                'status':'reviewer_reported_resolved_not_runtime_certification'}
    for action in actions:
        if action['action_id'] in resolutions:
            action['reviewer_resolution'] = resolutions[action['action_id']]
            action['status'] = 'reviewer_reported_resolved'
    return {'actions': actions, 'unstructured_results': unstructured,
        'pending_material': [a['action_id'] for a in actions if a.get('material') and not a['response_current']
                             and not a.get('reviewer_resolution')],
        'report_digest': digest, 'coverage': 'recorded_model_issues_only_not_exhaustive',
        'readback': {'tool': 'read_current_report', 'arguments': {'field': 'research_actions'}}}


def author_action_tool():
    @tool
    def respond_research_action(action_id: str, disposition: Literal['revised', 'rebutted', 'narrowed', 'unresolved'],
                                rationale: str, current_quote: str, evidence_receipts: list[str],
                                report_version: int, runtime: ToolRuntime):
        """Record how a material investigation/review action is handled in the saved current report.
        First investigate/change the report as needed. Cite the exact current wording, your reason
        and successful source/calculation receipt IDs (read_saved_result/browse_context provide them).
        Rebuttal requires evidence. Unresolved is valid only as an explicit remaining limitation
        in the quoted report wording; it is not a claim of research success. The host checks binding,
        not truth. After editing the report, recheck affected decisions at the new version.
        """
        state = runtime.state
        view = research_action_view(state)
        action = next((a for a in view['actions'] if a['action_id'] == action_id), None)
        errors = []
        if not action:
            errors.append('Unknown action_id; read research_actions for actual imported issues.')
        report = state.get('report') or {}
        if not report or report_version != state.get('report_version'):
            errors.append('Read the saved current report and use its report_version.')
        text = '\n'.join([report.get('title', ''), report.get('narrative_markdown', ''),
                          *[c.get('interpretation', '') for c in report.get('charts', [])]])
        if not current_quote.strip() or current_quote not in text:
            errors.append('current_quote must be verbatim wording from the saved current report, not proposed prose.')
        if not rationale.strip():
            errors.append('Give a reason for this disposition; saved is not resolved.')
        from .context_records import RESULT_REGIONS
        source_names = {name for name, (region, _) in RESULT_REGIONS.items()
                        if region in {'sources', 'numbers'}} | {'read_saved_result'}
        source_names -= {'discover_source_tools'}
        successful = {m.tool_call_id for m in state.get('messages', [])
                      if isinstance(m, ToolMessage) and m.status == 'success' and m.name in source_names}
        unknown = [rid for rid in evidence_receipts if rid not in successful]
        if unknown:
            errors.append('Evidence receipt IDs are not successful source/calculation observations: ' + ', '.join(unknown))
        if disposition == 'rebutted' and not evidence_receipts:
            errors.append('A rebuttal needs a successful evidence receipt as well as reasoning.')
        if errors:
            return {'recorded': False, 'feedback': errors, 'readback': view['readback']}
        value = {'recorded': True, 'action_id': action_id, 'disposition': disposition,
            'rationale': rationale, 'current_quote': current_quote, 'evidence_receipts': evidence_receipts,
            'report_version': report_version, 'report_digest': view['report_digest'],
            'status': 'author_disposition_not_independent_clearance'}
        return Command(update={'messages': [ToolMessage(name='respond_research_action',
            tool_call_id=runtime.tool_call_id, content=json.dumps(value, ensure_ascii=False))]})

    return GrantedTool(respond_research_action, 'task_artifact_write',
        '把作者处理意见绑定到实际稿件；不自动认可金融结论', recovery_semantics='checkpoint_only')
