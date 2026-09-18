"""Versioned review adapter for method diagnostics, not a financial oracle.

Reuse the production review wire contracts and quote matcher. The diagnostic
has MethodWorkResult objects, not CaseArtifacts papers, so navigation/lineage
validation is deliberately adapted here instead of creating a second reviewer.
"""
from copy import deepcopy
from difflib import SequenceMatcher
from typing import Literal

from pydantic import Field

from sec_agent.agent_runtime.case_review_agent import (
    CaseReviewFinding, FindingConfirmation, ReviewInspectionCheck, ReviewSourceCheck,
)
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from .method_execution import Contract
from .source_quotes import contains_source_quote
from sec_agent.agent_runtime.evidence_resolution import parsing_record, resolve_quote


class MethodFindingConfirmation(FindingConfirmation):
    paper_id: str = Field(min_length=1, description='Exact repair task ID, not the original task.')
    paper_digest: str = Field(min_length=1, description='Copy the runtime candidate digest.')


class MethodReview(Contract):
    inspection_checks: list[ReviewInspectionCheck] = Field(default_factory=list, max_length=160)
    findings: list[CaseReviewFinding] = Field(default_factory=list, max_length=80)
    finding_checks: list[MethodFindingConfirmation] = Field(default_factory=list, max_length=80)


class SubmittedMethodInspectionCheck(ReviewInspectionCheck):
    """Explicit model submission; permissive archived wire objects remain readable."""
    source_checks: list[ReviewSourceCheck] = Field(max_length=64,
        description='Required. checked/issue needs at least one exact original quote or span. Empty only for unresolved/not_applicable, with a reason; never invent evidence.')
    expressed_relationship: str = Field(min_length=1, max_length=1600,
        description='What the entire candidate field asserts, including period and causal/financial direction.')
    supported_relationship: str = Field(min_length=1, max_length=1600,
        description='What the cited original actually supports. State any evidence gap explicitly.')
    financial_verdict: Literal['supported','contradicted','insufficient']
    clarity_verdict: Literal['clear','needs_clarification','unassessed']
    clarity_reason: str = Field(min_length=1, max_length=2000,
        description='Explain whether the wording preserves the supported relationship and its limits.')
    calculation_check: Literal['none_added','bound','unresolved'] = Field(
        description='Required calculation scope; bound needs executed CALC IDs. unresolved cannot be checked/issue.')


class SubmittedMethodReview(MethodReview):
    inspection_checks: list[SubmittedMethodInspectionCheck] = Field(max_length=160,
        description='Explicit checks for current targets; omitted targets stay pending. Use unresolved honestly if not checked.')


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


def quote_location_candidates(source, quote, evidence):
    """Locate a quote in delivered windows of the same archived document.

    Suggestions only: never move a citation, rewrite a draft or infer support.
    Missing document identity/digest and another revision are not safe matches.
    """
    identity = source.get('source', {})
    if not identity.get('id') or not identity.get('digest') or not quote.strip():
        return []
    candidates = []
    for item in evidence.values():
        other = item.get('source', {})
        if item['id'] == source['id'] or any(other.get(k) != identity.get(k)
                for k in ('id', 'digest', 'published_at', 'known_at', 'vintage')):
            continue
        if not contains_source_quote(item['body'], quote):
            continue
        selected, _ = resolve_quote(item['body'], quote)
        start = item['body'].find(selected)
        # A repeated sentence within one window also needs model selection.
        if start < 0 or item['body'].find(selected, start + 1) >= 0:
            continue
        candidates.append({'source_id': item['id'], 'document_id': identity['id'],
            'document_digest': identity['digest'], 'quote': selected,
            'quote_span': {'source_digest': item['digest'], 'start': start, 'end': start + len(selected)},
            'locator': item.get('locator', '')})
    return candidates


def review_context(outputs, previous=None):
    previous = previous or {}
    targets = [t for r in outputs for t in review_targets(r)]
    return {'targets': targets, 'revision_comparisons': revision_comparisons(outputs),
            'previous_checks': list(previous.get('checks', {}).values()),
            'open_findings': [f for fid, f in previous.get('findings', {}).items()
                              if fid not in previous.get('closures', {})],
            'closures': list(previous.get('closures', {}).values()),
            'financial_semantics_checked_by_runtime': False}


def revision_comparisons(outputs):
    """Exact paragraph changes, not semantic labels or an answer key.

    Align steps by stable method step ID, never by reordered array positions.
    Findings have no stable cross-version ID: expose the entire new statements.
    """
    papers = {r['obligation']['obligation_id']: r for r in outputs}
    comparisons = []
    for repair in outputs:
        grouped = {}
        for request in repair.get('repair_targets', []):
            grouped.setdefault((request['paper_id'], request['paper_digest']), []).append(request)
        for (original_id, original_digest), requests in grouped.items():
            original = papers.get(original_id)
            item = {'original_paper_id': original_id, 'original_paper_digest': original_digest,
                    'paper_id': repair['obligation']['obligation_id'],
                    'paper_digest': canonical_sha256(repair['result']),
                    'repair_advice': [{'finding_id': r['finding_id'], 'text': r['requested_change'],
                                      'authority': 'fallible_reviewer_opinion_not_source'} for r in requests],
                    'changes': [], 'financial_semantics_checked_by_runtime': False}
            if not original or canonical_sha256(original['result']) != original_digest:
                item['comparison_status'] = 'original_missing_or_changed'
                comparisons.append(item)
                continue
            old, new = original['result'], repair['result']
            pairs = [('/summary', '/summary', old['summary'], new['summary'])]
            for i, step in enumerate(new['steps']):
                matches = [(j, s) for j, s in enumerate(old['steps']) if s['step_id'] == step['step_id']]
                j, before = matches[0] if len(matches) == 1 else (None, {})
                pairs.append((f'/steps/{j}/finding' if j is not None else None,
                              f'/steps/{i}/finding', before.get('finding', ''), step['finding']))
            new_step_ids = {s['step_id'] for s in new['steps']}
            pairs += [(f'/steps/{i}/finding', None, s['finding'], '')
                      for i, s in enumerate(old['steps']) if s['step_id'] not in new_step_ids]
            old_statements = {f['statement'] for f in old['findings']}
            new_statements = {f['statement'] for f in new['findings']}
            pairs += [(None, f'/findings/{i}/statement', '', f['statement'])
                      for i, f in enumerate(new['findings']) if f['statement'] not in old_statements]
            pairs += [(f'/findings/{i}/statement', None, f['statement'], '')
                      for i, f in enumerate(old['findings']) if f['statement'] not in new_statements]
            for before_path, after_path, before, after in pairs:
                if before == after:
                    continue
                a, b = before.splitlines(keepends=True), after.splitlines(keepends=True)
                edits = [{'removed_text': ''.join(a[i:j]), 'introduced_text': ''.join(b[k:l])}
                         for tag, i, j, k, l in SequenceMatcher(None, a, b, autojunk=False).get_opcodes()
                         if tag != 'equal']
                item['changes'].append({'original_field_path': before_path, 'field_path': after_path,
                    'before': before, 'after': after, 'paragraph_edits': edits,
                    'alignment': ('removed_or_rewritten_statement' if not after_path else
                                  'summary_or_step_id' if before_path else 'new_or_unaligned_statement')})
            item['comparison_status'] = 'current_versions_compared'
            comparisons.append(item)
    return comparisons


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
    # Never mutate the provider's archived submission while resolving wire links.
    review = review.model_copy(deep=True)
    runtime_parsing, source_quote_recovery = [], []
    # A later candidate cannot inherit closure of an older repair version.
    invalidated_closures = []
    for fid, closure in list(state['closures'].items()):
        repair = papers.get(closure['paper_id'])
        if not repair or canonical_sha256(repair['result']) != closure['paper_digest']:
            invalidated_closures.append(fid)
            del state['closures'][fid]

    def source_errors(checks, label):
        for index, check in enumerate(checks):
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
                source_quote_recovery.append({
                    'origin': 'runtime_compatibility_parse', 'target': label,
                    'source_check_index': index, 'original_source_id': check.source_id,
                    'candidates': quote_location_candidates(source, check.quote, evidence),
                    'draft_changed': False, 'citation_rebound': False,
                    'remedy': 'Candidate occurrence is not claim support. Check context, select the exact original, and repair any affected draft citation; the old review remains rejected.'})

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
            matches = [fid for fid, finding in new_findings.items()
                if finding['paper_id'] == check.paper_id and finding['paper_digest'] == check.paper_digest
                and finding['problematic_quote'] == check.target_quote
                and sum(t['paper_id'] == check.paper_id and finding['problematic_quote'] in t['text']
                        for t in targets.values()) == 1]
            if len(matches) == 1:
                check.finding_ids = matches
                runtime_parsing.append(parsing_record('unique_current_review_finding_link_v1', [], matches,
                    paper_id=check.paper_id, paper_digest=check.paper_digest, field_path=check.field_path,
                    basis='One current finding and one current target share the exact same quote.',
                    draft_changed=False, financial_verdict_changed=False))
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
    outstanding_contract_errors = []
    for paper_id, paper in papers.items():
        for error in paper['contract_errors']:
            parts = error['location'].split('/')
            # Only an explicitly reviewed repair of this exact result element
            # supersedes its diagnostic. Global/missing-step errors stay open.
            target = ('/' + '/'.join(parts[1:3]) + ('/statement' if parts[1]=='findings' else '/finding')
                      if len(parts)>3 and parts[1] in {'findings','steps'} and parts[2].isdigit() else None)
            covered = any(finding['paper_id']==paper_id and target in finding.get('field_paths', [])
                and finding['paper_digest']==canonical_sha256(paper['result']) and fid in state['closures']
                for fid,finding in state['findings'].items()) if target else False
            if not covered:
                outstanding_contract_errors.append({'paper_id':paper_id, **error})
    return {'state': state, 'errors': errors, 'pending_targets': pending, 'open_finding_ids': open_ids,
            'runtime_parsing': [{**r, 'operation_status': 'rejected' if errors else 'review_recorded'} for r in runtime_parsing],
            'source_quote_recovery': source_quote_recovery,
            'outstanding_contract_errors': outstanding_contract_errors,
            'complete': not errors and not pending and not open_ids and not outstanding_contract_errors,
            'invalidated_closures': invalidated_closures,
            'financial_semantics_checked_by_runtime': False}


METHOD_REVIEW_GUIDANCE = '''
review_context列出待审底稿的paper_id、paper_digest和精确field_path；这些是runtime导航，不是金融结论。
revision_comparisons按原版本/新版本列出修改前后全文及段落增删；不是runtime对语义的判定。
每处修订同时检查旧问题是否消失，以及新增的事实、必要条件、因果、期间限制是否成立。
repair_advice是先前复核者可能有错的建议，不能作为新增断言的依据；即使由你提出也重新按原文和共享方法核对。
expressed_relationship要覆盖修改后整个字段，包括“只有/必须/取决于”等限定；supported_relationship须说明证据究竟支持哪些限定。
原文只说明缺少当前数字，不足以支持新增的会计或业务必要条件。新增表述缺依据应记issue或unresolved，不能仅因旧句删除就resolved。
在review.inspection_checks逐项审阅summary、各步骤finding和各finding.statement；检查其整个字段的含义，
target_quote只需摘录一处精确文本。使用现有复核合同：明确expressed_relationship、supported_relationship、
financial_verdict、clarity_verdict、clarity_reason及原文source_checks。source_checks可引用review_evidence，
给简短原文quote，不用抄整段。只引用已提供的精确ID，不将专家结论当原文。
checked必须supported且clear；有证据的问题用issue，填写review.findings（具体diagnosis/requested_change）并关联finding_ids；
证据或时间不足用unresolved。not_applicable仅适用于原任务已标inapplicable的步骤，不得用来跳过重要判断。
计算沿用已有CALC绑定；不新增运算时calculation_check=none_added。有疑点先保留，不能为通过合同虚构已核验。
旧检查由runtime保留，省略不等于撤回；新版本必须重新检查。缺失或有误的审阅不构成研究收口。
结果中的contract_errors也需要按具体位置处理；类型或条件缺失不自动等于金融判断错，核对后合理修订，不能虚构假设过关。
需要修订时delegate一个有边界的新任务，在repair_finding_ids填已记录的问题ID，dependency_ids包含原任务。
worker会收到具体问题、原版本和准确位置，修改应覆盖这些位置及关联解释，无须重做无关研究。
修订结果返回后，先逐项检查新底稿，再用review.finding_checks确认每个已处理问题；填写新paper_id/paper_digest、
current_quote、source_checks和公开理由。resolved要求新底稿检查通过且clarity_verdict=clear；改了文字或作者自称完成不算关闭。
未能关闭保留still_open/unresolved；最终synthesis需遵守已核查的支持范围。预算上限到达可以stop，未核查与未解决仍由runtime保留。
'''
