"""Versioned review adapter for method diagnostics, not a financial oracle.

Reuse the production review wire contracts and quote matcher. The diagnostic
has MethodWorkResult objects, not CaseArtifacts papers, so navigation/lineage
validation is deliberately adapted here instead of creating a second reviewer.
"""
from copy import deepcopy

from pydantic import Field

from sec_agent.agent_runtime.case_review_agent import (
    CaseReviewFinding, FindingConfirmation, ReviewInspectionCheck,
)
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from .method_execution import Contract
from .source_quotes import contains_source_quote


class MethodFindingConfirmation(FindingConfirmation):
    paper_id: str = Field(min_length=1, description='Exact repair task ID, not the original task.')
    paper_digest: str = Field(min_length=1, description='Copy the runtime candidate digest.')


class MethodReview(Contract):
    inspection_checks: list[ReviewInspectionCheck] = Field(default_factory=list, max_length=160)
    findings: list[CaseReviewFinding] = Field(default_factory=list, max_length=80)
    finding_checks: list[MethodFindingConfirmation] = Field(default_factory=list, max_length=80)


def review_targets(output):
    """Exact field selectors and candidate identity; no inferred error labels."""
    result = output['result']
    digest = canonical_sha256(result)
    paper_id = output['obligation']['obligation_id']
    items = [('/summary', result['summary'], None)]
    items += [(f'/steps/{i}/finding', s['finding'], s['status']) for i, s in enumerate(result['steps'])]
    items += [(f'/findings/{i}/statement', f['statement'], None) for i, f in enumerate(result['findings'])]
    return [dict(paper_id=paper_id, paper_digest=digest, field_path=path,
                 text=text, step_status=status) for path, text, status in items if text.strip()]


def _key(paper_id, path):
    return paper_id + ':' + path


def review_context(outputs, previous=None):
    previous = previous or {}
    targets = [t for r in outputs for t in review_targets(r)]
    return {'targets': targets, 'previous_checks': list(previous.get('checks', {}).values()),
            'open_findings': [f for fid, f in previous.get('findings', {}).items()
                              if fid not in previous.get('closures', {})],
            'closures': list(previous.get('closures', {}).values()),
            'financial_semantics_checked_by_runtime': False}


def assess_method_review(outputs, review, previous=None):
    """Validate exact review coverage, references and repair lineage.

    A valid model verdict can still be financially wrong. Missing checks remain
    pending; invalid submissions do not overwrite the last valid review state.
    """
    state = deepcopy(previous or {'checks': {}, 'findings': {}, 'closures': {}})
    targets = {_key(t['paper_id'], t['field_path']): t for r in outputs for t in review_targets(r)}
    papers = {r['obligation']['obligation_id']: r for r in outputs}
    evidence = {p['id']: p for r in outputs for p in r.get('review_evidence', [])}
    errors = []
    # A later candidate cannot inherit closure of an older repair version.
    invalidated_closures = []
    for fid, closure in list(state['closures'].items()):
        repair = papers.get(closure['paper_id'])
        if not repair or canonical_sha256(repair['result']) != closure['paper_digest']:
            invalidated_closures.append(fid)
            del state['closures'][fid]

    def source_errors(checks, label):
        for check in checks:
            source = evidence.get(check.source_id)
            if not source:
                errors.append('review_source_not_delivered:' + label + ':' + check.source_id)
            elif check.quote_span is not None:
                span = check.quote_span
                if (span.source_digest != source['digest'] or span.end > len(source['body'])
                        or span.end <= span.start
                        or (check.quote.strip() and not contains_source_quote(source['body'][span.start:span.end], check.quote))):
                    errors.append('review_source_span_mismatch:' + label)
            elif not contains_source_quote(source['body'], check.quote):
                errors.append('review_source_quote_not_exact:' + label)

    new_findings = {}
    for finding in review.findings:
        fid = finding.finding_id
        if fid in state['findings'] or fid in new_findings:
            errors.append('review_finding_id_reused:' + fid)
        matching = [t for t in targets.values() if t['paper_id'] == finding.paper_id
                    and finding.problematic_quote in t['text']]
        if not matching:
            errors.append('review_finding_quote_not_current:' + fid)
        if not finding.source_checks:
            errors.append('review_finding_requires_source:' + fid)
        source_errors(finding.source_checks, fid)
        new_findings[fid] = {**finding.model_dump(mode='json'),
                            'paper_digest': matching[0]['paper_digest'] if matching else '', 'field_paths': []}
    state['findings'].update(new_findings)

    seen = set()
    linked_new_findings = set()
    for check in review.inspection_checks:
        key = _key(check.paper_id, check.field_path)
        target = targets.get(key)
        if key in seen:
            errors.append('review_duplicate_target:' + key)
        seen.add(key)
        if not target or check.paper_digest != target['paper_digest']:
            errors.append('review_candidate_version_or_target_mismatch:' + key)
            continue
        if not check.target_quote.strip() or check.target_quote not in target['text']:
            errors.append('review_target_quote_not_exact:' + key)
        if check.status in {'checked', 'issue'}:
            if not check.source_checks:
                errors.append('review_checked_requires_original:' + key)
            if (not check.expressed_relationship.strip() or not check.supported_relationship.strip()
                    or not check.financial_verdict or not check.clarity_verdict
                    or not check.clarity_reason.strip()):
                errors.append('review_requires_explicit_semantic_comparison:' + key)
            if check.calculation_check not in {'none_added', 'bound'}:
                errors.append('review_calculation_scope_missing:' + key)
            if check.calculation_check == 'bound':
                known = {cid for r in outputs for cid in r.get('calculations', {})}
                if not check.calculation_ids or not set(check.calculation_ids) <= known:
                    errors.append('review_calculation_not_bound:' + key)
        if check.status == 'checked' and (check.financial_verdict != 'supported' or check.clarity_verdict != 'clear'):
            errors.append('review_checked_verdict_mismatch:' + key)
        if check.status == 'not_applicable' and target['step_status'] != 'inapplicable':
            errors.append('review_cannot_skip_required_target:' + key)
        if check.status == 'issue' and not check.finding_ids:
            errors.append('review_issue_requires_actionable_finding:' + key)
        if check.status != 'issue' and check.finding_ids:
            errors.append('review_nonissue_links_findings:' + key)
        for fid in check.finding_ids:
            finding = state['findings'].get(fid)
            if (not finding or finding['paper_id'] != check.paper_id
                    or finding['paper_digest'] != check.paper_digest
                    or finding['problematic_quote'] not in target['text']):
                errors.append('review_issue_target_mismatch:' + key + ':' + fid)
            if fid in new_findings:
                linked_new_findings.add(fid)
                state['findings'][fid]['field_paths'].append(check.field_path)
        source_errors(check.source_checks, key)
        state['checks'][key] = check.model_dump(mode='json')
    for fid in new_findings.keys() - linked_new_findings:
        errors.append('review_finding_not_linked_to_target:' + fid)

    seen_confirmations = set()
    for confirmation in review.finding_checks:
        fid = confirmation.finding_id
        if fid in seen_confirmations or fid in state['closures']:
            errors.append('review_duplicate_or_closed_confirmation:' + fid)
        seen_confirmations.add(fid)
        original = state['findings'].get(fid)
        repair = papers.get(confirmation.paper_id)
        lineage = next((r for r in (repair or {}).get('repair_targets', []) if r['finding_id'] == fid), None)
        if (not original or not repair or not lineage
                or lineage['paper_digest'] != original['paper_digest']
                or lineage['paper_id'] != original['paper_id']
                or confirmation.paper_digest != canonical_sha256(repair['result'])):
            errors.append('review_confirmation_requires_exact_repair_lineage:' + fid)
            continue
        if not confirmation.current_quote.strip() or not any(
                confirmation.current_quote in t['text'] for t in review_targets(repair)):
            errors.append('review_confirmation_requires_current_quote:' + fid)
        source_errors(confirmation.source_checks, fid)
        if not confirmation.source_checks:
            errors.append('review_confirmation_requires_original:' + fid)
        if confirmation.status == 'resolved':
            checks = [state['checks'].get(_key(t['paper_id'], t['field_path'])) for t in review_targets(repair)]
            if (repair['contract_errors'] or not checks or any(not c or c['status'] != 'checked'
                    or c['paper_digest'] != confirmation.paper_digest for c in checks)
                    or confirmation.clarity_verdict != 'clear' or confirmation.related_finding_ids):
                errors.append('review_resolution_requires_checked_current_repair:' + fid)
            state['closures'][fid] = confirmation.model_dump(mode='json')
        elif confirmation.status == 'still_open':
            if not confirmation.related_finding_ids or any(
                    related not in state['findings'] or state['findings'][related]['paper_id'] != confirmation.paper_id
                    for related in confirmation.related_finding_ids):
                errors.append('review_still_open_requires_current_finding:' + fid)

    if errors:
        state = deepcopy(previous or {'checks': {}, 'findings': {}, 'closures': {}})
    pending = []
    for key, target in targets.items():
        check = state['checks'].get(key)
        if not check or check['paper_digest'] != target['paper_digest'] or check['status'] == 'unresolved':
            pending.append(key)
        elif check['status'] == 'issue' and not all(fid in state['closures'] for fid in check['finding_ids']):
            pending.append(key)
    open_ids = sorted(set(state['findings']) - set(state['closures']))
    return {'state': state, 'errors': errors, 'pending_targets': pending, 'open_finding_ids': open_ids,
            'complete': not errors and not pending and not open_ids,
            'invalidated_closures': invalidated_closures,
            'financial_semantics_checked_by_runtime': False}


METHOD_REVIEW_GUIDANCE = '''
review_context列出待审底稿的paper_id、paper_digest和精确field_path；这些是runtime导航，不是金融结论。
在review.inspection_checks逐项审阅summary、各步骤finding和各finding.statement；检查其整个字段的含义，
target_quote只需摘录一处精确文本。使用现有复核合同：明确expressed_relationship、supported_relationship、
financial_verdict、clarity_verdict、clarity_reason及原文source_checks。source_checks可引用review_evidence，
给简短原文quote，不用抄整段。只引用已提供的精确ID，不将专家结论当原文。
checked必须supported且clear；有证据的问题用issue，填写review.findings（具体diagnosis/requested_change）并关联finding_ids；
证据或时间不足用unresolved。not_applicable仅适用于原任务已标inapplicable的步骤，不得用来跳过重要判断。
计算沿用已有CALC绑定；不新增运算时calculation_check=none_added。有疑点先保留，不能为通过合同虚构已核验。
旧检查由runtime保留，省略不等于撤回；新版本必须重新检查。缺失或有误的审阅不构成研究收口。
需要修订时delegate一个有边界的新任务，在repair_finding_ids填已记录的问题ID，dependency_ids包含原任务。
worker会收到具体问题、原版本和准确位置，修改应覆盖这些位置及关联解释，无须重做无关研究。
修订结果返回后，先逐项检查新底稿，再用review.finding_checks确认每个已处理问题；填写新paper_id/paper_digest、
current_quote、source_checks和公开理由。resolved要求新底稿检查通过且clarity_verdict=clear；改了文字或作者自称完成不算关闭。
未能关闭保留still_open/unresolved；最终synthesis需遵守已核查的支持范围。预算上限到达可以stop，未核查与未解决仍由runtime保留。
'''
