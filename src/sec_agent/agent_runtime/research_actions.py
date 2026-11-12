"""Version-bound research actions projected from the existing tool journal.

Models judge coverage and materiality. The host checks identity and disposition,
not whether a financial interpretation is correct. No second task/state store.
"""
import json
from typing import Literal

from langchain_core.messages import AIMessage, ToolMessage
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
                                  resolved_action_ids: list[str] | None = None, finding: str | None = None):
        """Save your investigation/review findings before returning your final opinion.
        Explain which parts of the original question the actual evidence supports and what
        could change the main answer. Record only consequential unresolved issues as actions;
        an empty list is valid when justified. You may investigate first and record only residual
        gaps. Do not infer coverage from source counts. This records your judgment, not approval.
        Repeated calls replace this task's assessment; prior receipts remain readable.
        A review of the current report may resolve prior action IDs actually supplied in its
        handoff, after checking the author's text and evidence. Explain why in scope_explanation.
        Never mark an issue resolved just because the author acknowledged it.
        finding may explain the substantive result: what the comparison established,
        what changed relative to the starting explanation, and its decision implication.
        Check both unjustified certainty and failure to choose despite sufficient evidence.
        Explain why one conditional outlook is better supported than the strongest alternative,
        or which discriminating observation is still missing. A sensitivity table alone does not
        establish a baseline. Do not invent probabilities or treat a failed read as nondisclosure.
        Include source/calculation handles. Preserve supported positive findings, not
        only objections. This is public research prose, not private reasoning or a checklist.
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
        if finding and finding.strip():
            value['finding'] = finding
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
            from .research_disposition_binding import scope_unchanged
            current = bool(response and (response.get('report_digest') == digest
                or scope_unchanged(state.get('report') or {}, response)))
            response_view = {k: v for k, v in response.items() if k != 'disposition_scope'} if response else None
            actions.append({**action, 'task_id': task_id, 'review_receipt': message.tool_call_id,
                'reviewed_report_digest': result.get('reviewed_report_digest'),
                'author_response': response_view, 'response_current': current,
                'response_binding': ('exact_report' if response and response.get('report_digest') == digest
                    else 'unchanged_textual_scope' if current else 'requires_recheck'),
                'status': 'author_disposition_not_independent_clearance' if current else 'needs_author_decision',
                'review_readback': {'tool': 'read_research_agent_result', 'arguments': {'task_id': task_id}}})
        for action_id in assessment.get('resolved_action_ids', []):
            resolutions[action_id] = {'task_id':task_id,'review_receipt':message.tool_call_id,
                'report_digest':result.get('reviewed_report_digest'),
                'status':'reviewer_reported_resolved_not_runtime_certification'}
    for action in actions:
        if action['action_id'] in resolutions:
            action['reviewer_resolution'] = resolutions[action['action_id']]
            action['resolution_current'] = bool(digest and
                action['reviewer_resolution']['report_digest'] == digest)
            if action['resolution_current']:
                action['status'] = 'reviewer_reported_resolved'
    return {'actions': actions, 'unstructured_results': unstructured,
        'pending_material': [a['action_id'] for a in actions if a.get('material') and not a['response_current']
                             and not a.get('resolution_current')],
        'awaiting_independent_resolution': [a['action_id'] for a in actions
            if a.get('material') and not a.get('resolution_current')],
        'report_digest': digest, 'coverage': 'recorded_model_issues_only_not_exhaustive',
        'readback': {'tool': 'read_current_report', 'arguments': {'field': 'research_actions'}}}


def compact_action_view(view):
    """All issue identities remain; settled response prose is read on demand."""
    rows = []
    for action in view.get('actions', []):
        row = dict(action)
        if row.get('review_receipt'):
            row['review_readback'] = {'tool': 'read_saved_result',
                'arguments': {'tool_call_id': row['review_receipt']}}
        response = row.get('author_response')
        if response and response.get('receipt_id'):
            row['author_response'] = {k: response.get(k) for k in
                ('disposition', 'current_quote', 'report_version', 'report_digest', 'receipt_id')}
            row['author_response']['readback'] = {'tool': 'read_saved_result',
                'arguments': {'tool_call_id': response['receipt_id']}}
        rows.append(row)
    return {**view, 'actions': rows}


def synthesis_working_view(state):
    """Project current bindings, never generate or choose the author's conclusions."""
    view = compact_action_view(research_action_view(state))
    # Retain binding and navigation, not settled audit prose, in the writing entry.
    # Version changes reactivate an old issue automatically through the existing view.
    active = []
    for action in view['actions']:
        if action.get('resolution_current'):
            continue
        row = dict(action)
        if row.get('response_current') and row.get('author_response'):
            response = row['author_response']
            row['author_response'] = {k: response.get(k) for k in
                ('disposition', 'report_version', 'report_digest', 'receipt_id')}
            row['author_response']['readback'] = {'tool': 'read_saved_result',
                'arguments': {'tool_call_id': response['receipt_id']}}
        active.append(row)
    resolved = [{'action_id': a['action_id'], 'status': a['status'],
                 'reviewer_resolution': a['reviewer_resolution']}
                for a in view['actions'] if a.get('resolution_current')]
    current_actions = {**view, 'actions': active, 'resolved_actions': resolved}
    from .source_acquisition_view import acquisition_snapshot
    return {'question': state.get('question'), 'report_version': state.get('report_version', 0),
        'report_digest': view['report_digest'], 'current_title': (state.get('report') or {}).get('title'),
        'research_actions': current_actions,
        'current_research': research_working_view(state),
        'acquisition': acquisition_snapshot(state.get('messages', [])),
        'report_readback': {'tool': 'read_current_report', 'arguments': {'field': 'all'}},
        'related_changes_readback': {'tool': 'read_current_report', 'arguments': {'field': 'revision_context'}},
        'working_understanding': 'Read/update current notes; replace superseded accounts rather than append correction history. Historical note versions, full research_actions and revision_context remain readable. No text is automatically rewritten or certified.',
        'responsibility': 'Re-answer the original question from current evidence: state the outlook you favor, why it is better supported than alternatives, and what would change it. A sensitivity or return hurdle is not a baseline forecast. Investigate answer-changing access failures; do not call them exhausted public information. Test replacement explanations. Old titles and structure are not constraints; author dispositions are not independent resolutions.'}


def research_working_view(state):
    """Journal navigation for current understanding, not another summary or state store.

    Exact duplicate requests are observable; their usefulness and the completeness of
    research are not. Never stop a run or certify a thesis from these counters.
    Note versions remain in WorkingMemory and are read under the caller's authority.
    """
    messages = state.get('messages', [])
    calls = {call['id']: call for message in messages if isinstance(message, AIMessage)
             for call in message.tool_calls}
    notes, investigations, repeated, observed = {}, {}, {}, {}
    from .context_records import RESULT_REGIONS
    for message, value in receipts(messages):
        if message.name == 'WriteWorkingNote' and value.get('saved') and value.get('note_id'):
            key = value['note_id']
            prior = notes.get(key)
            if prior and prior['observed_version'] > value.get('version', 0):
                continue
            notes[key] = {'note_id': key, 'observed_version': value.get('version', 0),
                'title': calls.get(message.tool_call_id, {}).get('args', {}).get('title'),
                'receipt_id': message.tool_call_id,
                'write_mode': value.get('write_mode', calls.get(message.tool_call_id, {}).get('args', {}).get('mode', 'unknown')),
                'readback': {'tool': 'ReadWorkingNote', 'arguments': {'note_id': key}},
                'observed_version_readback': {'tool': 'ReadWorkingNote', 'arguments': {
                    'note_id': key, 'version': value.get('version', 0)}},
                'notice': 'Read current version; a colleague or user may have updated it since this receipt.'}
        if message.name == 'read_research_agent_result' and value.get('status') == 'completed':
            key = value.get('task_id')
            if key:
                assessment = value.get('assessment') or {}
                investigations[key] = {'task_id': key, 'purpose': value.get('purpose'),
                    'finding': assessment.get('finding'),
                    'scope_explanation': assessment.get('scope_explanation'),
                    'readback': {'tool': 'read_saved_result', 'arguments': {'tool_call_id': message.tool_call_id}},
                    'status': 'investigator_proposal_not_author_adoption'}
        if message.name in RESULT_REGIONS and message.tool_call_id in calls:
            call = calls[message.tool_call_id]
            key = canonical_sha256({'tool': message.name, 'arguments': call.get('args', {})})
            if key in observed:
                repeated.setdefault(key, {'tool': message.name, 'receipt_ids': [observed[key]]})['receipt_ids'].append(message.tool_call_id)
            else:
                observed[key] = message.tool_call_id
    return {'working_notes': list(notes.values()), 'investigations': list(investigations.values()),
        'repeated_observations': list(repeated.values()),
        'notes_discovery': {'tool': 'SearchWorkingNotes', 'arguments': {'query': ''}},
        'evidence_discovery': {'tool': 'browse_context', 'arguments': {'region': 'sources'}},
        'progress_interpretation': 'Repeated exact reads may be legitimate. Decide whether new evidence changed the explanation, its scope, magnitude or investment implication. Counts and empty issues do not establish adequacy.',
        'stopping_decision': 'Investigate a material, answer-changing uncertainty when a useful next observation is available. Otherwise deliver the supported answer and its specific remaining conditions; do not manufacture a precise forecast or search indefinitely.'}


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
        from .research_disposition_binding import disposition_scope
        value['disposition_scope'] = disposition_scope(report, current_quote)
        return Command(update={'messages': [ToolMessage(name='respond_research_action',
            tool_call_id=runtime.tool_call_id, content=json.dumps(value, ensure_ascii=False))]})

    return GrantedTool(respond_research_action, 'task_artifact_write',
        '把作者处理意见绑定到实际稿件；不自动认可金融结论', recovery_semantics='checkpoint_only')
