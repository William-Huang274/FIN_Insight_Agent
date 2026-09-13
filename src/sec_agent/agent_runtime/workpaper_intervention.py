"""Human correction of a saved specialist submission at a native interrupt."""
from copy import deepcopy
from datetime import datetime, timezone
import json

from .specialist_graph import SubmitWorkpaperAction, SpecialistNotebook, _replace_notebook, _submission_errors
from .research_graph_contracts import canonical_sha256
from .case_artifacts import CaseArtifacts
from .workpaper_delivery import decode_workpaper_arguments


def review_saved_workpapers(state, decision, *, owner):
    """Human scope decision starts review; it does not certify the report."""
    from .lead_research_graph import SubmitResearchHandoffAction
    papers = state.get('case_papers', [])
    done = {p['task']['task_id'] for p in papers}
    required = {t['task_id'] for t in state.get('research_tasks', [])}
    if not papers or required - done:
        raise ValueError('human_scope_review_requires_all_original_workpapers')
    if not decision.get('confirmed') or len(decision.get('reason', '').strip()) < 20:
        raise ValueError('human_scope_review_requires_explicit_reason')
    if decision.get('base_papers_digest') != canonical_sha256(papers):
        raise ValueError('human_scope_review_stale_workpapers')
    CaseArtifacts(papers)
    handoff = SubmitResearchHandoffAction.model_validate_json(json.dumps({
        'context_digest': canonical_sha256(papers), 'reason_summary': decision['reason'],
        'disposition': 'ready_for_review', 'execution_plan': decision['execution_plan'],
        'synthesis_notes': '人工确认研究范围后进入独立审查，底稿尚非审查通过的报告。' + decision['reason'],
        'acknowledged_incomplete_task_ids': [], 'question_coverage': [{
            'question_quote': state['question'][:2000], 'status': 'answered',
            'supporting_task_ids': sorted(done),
            'rationale': '人工确认已有底稿覆盖本题应交给下游审查的研究范围；这不代表其中财务含义已核验通过。' + decision['reason']}]}))
    return {'research_handoff': {**handoff.model_dump(mode='json'), 'origin': 'human_scope_confirmation', 'owner': owner},
        'phase': 'research_reviewing', 'research_stop_reason': None, 'continue_remaining_research': False,
        'conversation': [{'role': 'system', 'content': '人工确认研究范围并交独立审查：' + decision['reason']}]}


def public_paper_body(candidate):
    body = candidate.get('narrative_markdown', '')
    for claim in candidate.get('claims', []):
        body += '\n\n### ' + claim['claim_id'] + ' · ' + claim['statement']
        for ref, quotes in claim.get('citation_quotes', {}).items():
            body += '\n\n' + ref + '\n\n' + '\n\n'.join(
                '> ' + q for q in (quotes if isinstance(quotes, list) else [quotes]))
    return body


def amend_reviewed_workpapers(state, decision, *, owner):
    """Version human prose and dispositions, then write for final human review.

    This does not mark model findings resolved, mutate source evidence, or
    certify a report. Every blocking finding/request requires an explicit
    human disposition tied to the current immutable review snapshot.
    """
    review = state.get('case_review', {})
    papers = state.get('case_papers', [])
    if (state.get('research_stop_reason') != 'independent_review_incomplete_no_report_acceptance'
            or review.get('phase') != 'case_review_incomplete'):
        raise ValueError('human_paper_amendment_requires_review_interrupt')
    if (not decision.get('confirmed') or len(decision.get('reason', '').strip()) < 20
            or decision.get('base_review_digest') != canonical_sha256(review)
            or decision.get('base_papers_digest') != canonical_sha256(papers)
            or decision.get('base_edits_digest') != canonical_sha256(state.get('human_edits', []))):
        raise ValueError('human_paper_amendment_unconfirmed_or_stale')
    blockers = {}
    for role in ('counter', 'verifier'):
        row = review.get(role, {})
        for finding in [*row.get('review', {}).get('findings', []), *row.get('recorded_findings', {}).values()]:
            if finding.get('severity') == 'material':
                blockers[f"{role}:finding:{finding['finding_id']}"] = finding.get('paper_id')
        for index, request in enumerate(row.get('review', {}).get('unresolved_data_requests', [])):
            blockers[f'{role}:request:{index}'] = None
    dispositions = decision.get('dispositions', {})
    if set(dispositions) != set(blockers):
        raise ValueError('human_paper_amendment_requires_every_blocker_disposition')
    current = CaseArtifacts(papers).with_human_edits(state.get('human_edits', []))
    catalog = {p['paper_id']: p for p in current.catalog()['papers']}
    edits = []
    for edit in decision.get('papers', []):
        paper = current.read_paper(edit['paper_id'])
        after = edit.get('after', '').strip()
        if not after or len(after) > 100000 or after == paper['narrative_markdown']:
            raise ValueError('human_paper_amendment_requires_changed_readable_prose')
        task = papers[list(catalog).index(edit['paper_id'])]['task']
        role = next((t['owner_role'] for t in state.get('research_tasks', []) if t['task_id'] == task['task_id']), catalog[edit['paper_id']]['author'])
        edits.append({'paper_id': edit['paper_id'], 'actor': role,
            'title': paper['thesis'], 'before': paper['narrative_markdown'], 'after': after})
    edited_ids = {e['paper_id'] for e in edits}
    if not edits or len(edited_ids) != len(edits):
        raise ValueError('human_paper_amendment_requires_unique_papers')
    for key, item in dispositions.items():
        if (item.get('decision') not in {'corrected', 'outside_requested_scope', 'retained_limitation'}
                or len(item.get('reason', '').strip()) < 20):
            raise ValueError('human_paper_amendment_requires_specific_disposition')
        if item['decision'] == 'corrected' and blockers[key] and blockers[key] not in edited_ids:
            raise ValueError('human_paper_amendment_missing_responsible_paper')
    history = deepcopy(state.get('human_edits', []))
    history.append({'number': len(history)+1, 'owner': owner, 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'reason': decision['reason'], 'base_version': state.get('report_version', 0), 'papers': edits,
        'report_before': '', 'report_after': '', 'stage': 'reviewed_workpaper',
        'review_digest': canonical_sha256(review), 'review_dispositions': deepcopy(dispositions)})
    handoff = deepcopy(state.get('research_handoff') or {})
    handoff['human_review_direction'] = {'owner': owner, 'reason': decision['reason'],
        'review_status': 'incomplete_retained', 'final_human_confirmation_required': True,
        'dispositions': deepcopy(dispositions), 'edited_paper_ids': sorted(edited_ids)}
    return {'human_edits': history, 'research_handoff': handoff, 'phase': 'research_writing',
        'research_stop_reason': None, 'continue_remaining_research': False, 'author_feedback': {},
        'conversation': [{'role': 'system', 'content': '人工修订角色底稿并说明审查处置，原审查保留，最终报告仍需人工确认：' + decision['reason']}]}


def write_after_incomplete_review(state, decision, *, owner):
    """An explicit human direction permits writing, never certifies review."""
    review = state.get('case_review', {})
    if (state.get('research_stop_reason') != 'independent_review_incomplete_no_report_acceptance'
            or review.get('phase') != 'case_review_incomplete'):
        raise ValueError('human_writer_handoff_requires_incomplete_review')
    if (not decision.get('confirmed') or len(decision.get('reason', '').strip()) < 20
            or decision.get('base_review_digest') != canonical_sha256(review)
            or decision.get('base_papers_digest') != canonical_sha256(state.get('case_papers', []))):
        raise ValueError('human_writer_handoff_unconfirmed_or_stale')
    CaseArtifacts(state['case_papers'])
    # This recovery handles a reviewer that did not submit, not an identified
    # missing-data dependency or a material finding requiring author correction.
    for role in ('counter', 'verifier'):
        row = review.get(role, {})
        submitted = row.get('review') or {}
        findings = [*submitted.get('findings', []), *row.get('recorded_findings', {}).values()]
        if submitted.get('unresolved_data_requests') or any(f.get('severity') == 'material' for f in findings):
            raise ValueError('human_writer_handoff_requires_resolution_of_material_or_data_findings')
    handoff = deepcopy(state['research_handoff'])
    handoff['human_review_direction'] = {'owner': owner, 'reason': decision['reason'],
        'review_status': 'incomplete_retained', 'final_human_confirmation_required': True}
    return {'research_handoff': handoff, 'phase': 'research_writing',
        'research_stop_reason': None, 'continue_remaining_research': False, 'author_feedback': {},
        'conversation': [{'role': 'system', 'content': '人工要求保留未完成审查并交写作，尚未确认报告：' + decision['reason']}]}


def recover_workpaper(state, decision, *, owner):
    if not decision.get('confirmed') or not str(decision.get('reason', '')).strip():
        raise ValueError('workpaper_intervention_requires_confirmation_and_reason')
    task_id = decision['task_id']
    saved = next((r['agent_state'] for r in reversed(state.get('research_failed_workpapers', []))
                  if r['task_id'] == task_id), None)
    if saved is None or canonical_sha256(saved) != decision.get('base_agent_digest'):
        raise ValueError('workpaper_intervention_stale_or_unknown_task')
    if any(p['task']['task_id'] == task_id for p in state.get('case_papers', [])):
        raise ValueError('workpaper_already_submitted')
    prior = (saved.get('last_submission_attempt') or {}).get('arguments')
    # Legacy recovery may supply the explicitly selected public tool arguments
    # from the provider audit. It remains labeled an operator recovery import.
    if not prior and decision.get('original_tool_arguments'):
        prior, complete, _ = decode_workpaper_arguments(decision['original_tool_arguments'])
        if not complete:
            raise ValueError('legacy_workpaper_recovery_requires_complete_object')
    if not prior:
        prior = (saved.get('last_submission_attempt') or {}).get('readable_candidate') or {}
    candidate = SubmitWorkpaperAction.model_validate_json(json.dumps({
        **decision['submission'], 'context_digest': canonical_sha256(saved)}))
    notebook = SpecialistNotebook.model_validate_json(json.dumps(saved['notebook']))
    errors = _submission_errors(candidate, notebook, enforce_case_route_requirements=
        (saved.get('task_context') or {}).get('instruction_source') != 'current_user_research_request')
    if errors:
        raise ValueError('workpaper_intervention_invalid_references:' + '; '.join(errors))
    restored = {**deepcopy(saved), 'final_submission': candidate.model_dump(mode='json'),
        'pending_action': None, 'phase': 'specialist_submission_accepted',
        'human_review_handoff': None, 'review_reason': None, 'review_trigger': None,
        'notebook': _replace_notebook(notebook, status='submitted').model_dump(mode='json'),
        'last_submission_attempt': {'arguments': candidate.model_dump(mode='json'), 'accepted': True,
            'feedback': [], 'validation_issues': [], 'origin': 'human_workpaper_intervention'}}
    papers = [*deepcopy(state.get('case_papers', [])), restored]
    catalog = CaseArtifacts(papers).catalog()['papers']  # all source gates remain
    paper_id = catalog[-1]['paper_id']
    role = next((t['owner_role'] for t in state.get('research_tasks', []) if t['task_id'] == task_id), saved['agent_id'])
    # Normalize quote placement for an honest before/after; no syntax fix is a
    # counted manual edit. The actual source/wording correction is counted once.
    try:
        prior = SubmitWorkpaperAction.model_validate_json(json.dumps({**prior, 'context_digest': canonical_sha256(saved)})).model_dump(mode='json')
    except ValueError:
        pass
    before, after = public_paper_body(prior), public_paper_body(candidate.model_dump(mode='json'))
    history = deepcopy(state.get('human_edits', []))
    if before != after:
        history.append({'number': len(history)+1, 'owner': owner, 'recorded_at': datetime.now(timezone.utc).isoformat(),
            'reason': decision['reason'], 'base_version': state.get('report_version', 0),
            'papers': [{'paper_id': paper_id, 'actor': role, 'title': candidate.thesis, 'before': before, 'after': after}],
            'report_before': '', 'report_after': '', 'stage': 'workpaper',
            'source_candidate_digest': canonical_sha256(prior), 'source_agent_digest': canonical_sha256(saved)})
    return {'case_papers': papers, 'human_edits': history, 'continue_remaining_research': True,
        'case_review': {}, 'research_stop_reason': None}
