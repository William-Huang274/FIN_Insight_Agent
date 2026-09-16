"""Declared review needs -> existing findings and calculator provenance.

This adapter does not infer financial correctness or discover all numeric prose.
Native calculator receipts own arithmetic; reviewers own scope and semantics.
"""
from copy import deepcopy
import json
import re

from langchain_core.messages import ToolMessage
from sec_agent.research_foundation.source_bound_calculator import source_items_from_tool
from .evidence_resolution import parsing_record
from .research_graph_contracts import canonical_sha256


def calculation_lineage(artifacts, messages, reference):
    observed = {}
    for message in messages:
        if isinstance(message, ToolMessage) and message.status == 'success' and isinstance(message.artifact, dict):
            observed.update(source_items_from_tool(message.name, message.artifact))

    def lookup(ref):
        return deepcopy(observed[ref]) if ref in observed else artifacts.source_item(ref)

    leaves, calculations, assumptions = [], [], []

    def visit(ref, stack):
        item = lookup(ref)
        if (item.get('result_state') != 'non_authoritative_metric' or item.get('arithmetic_verified') is not True
                or item.get('numeric_fact_authority') is not False):
            raise ValueError('calculation_requires_saved_verified_receipt:' + ref)
        identity = item.get('calculation_id')
        if not identity or identity in stack or len(stack) >= 16:
            raise ValueError('calculation_lineage_cycle_or_invalid_identity:' + ref)
        calculations.append({k:deepcopy(item[k]) for k in
            ('calculation_id','expression','result_unit','value_decimal','operands','rationale','authority_note') if k in item})
        for name, operand in item['operands'].items():
            source = operand.get('source_id')
            if not source:
                if not operand.get('assumption_note'):
                    raise ValueError('calculation_operand_missing_source_or_assumption:' + name)
                assumptions.append({'operand':name, **operand})
                continue
            original = lookup(source)
            if original.get('result_state') == 'non_authoritative_metric':
                visit(source, {*stack,identity})
                continue
            quote = operand.get('quote') or str(original.get('value_decimal', ''))
            body = str(original.get('passage') or original.get('bounded_excerpt') or original.get('value_decimal', ''))
            if not quote or quote not in body:
                raise ValueError('calculation_operand_source_unavailable_or_changed:' + name + ':' + source)
            leaves.append({'source_id':source,'quote':quote})

    visit(reference,set())
    return {'calculation_id':reference,'calculations':calculations,
        'source_checks':list({(r['source_id'],r['quote']):r for r in leaves}.values()),
        'assumptions':assumptions,'financial_semantics_verified':False}


# Narrow arithmetic navigation hint, not a classifier. A slash alone may mean
# current/prior values or source locators. Only a slash with an explicit result
# marker is an arithmetic hint; unmarked ratios still need model declaration.
_NUMBER = r'\d(?:[\d,.]*\d)?'
ARITHMETIC = re.compile(
    _NUMBER + r'\s*(?:(?:÷|\*|×|\+|=)\s*[−-]?' + _NUMBER
    + r'|/\s*[−-]?' + _NUMBER + r'(?=\s*[=≈≃]))')


def arithmetic_hint(text):
    return ARITHMETIC.search(text) is not None


def prepare_review_claims(review, artifacts, messages, *, parsing_records=None):
    from .case_review_agent import CaseReviewFinding, ReviewSourceCheck
    from .review_inspection import text_locations, resolve_location
    records = parsing_records if parsing_records is not None else []
    errors, generated = [], {}
    for index, check in enumerate(review.inspection_checks):
        where = {'inspection_check_index':index,'paper_id':check.paper_id,'field_path':check.field_path}
        def error(code, **details):
            errors.append({**where,'code':code,**details})

        public_text = '\n'.join((check.result,check.expressed_relationship,check.supported_relationship,check.clarification))
        if check.calculation_check is None:
            error('declare_new_calculation_scope',remedy='Set none_added, bound with saved calculation_ids, or unresolved with unfinished work.')
        elif check.calculation_check == 'none_added' and (check.calculation_ids or arithmetic_hint(public_text)):
            error('calculation_declaration_conflicts_with_added_arithmetic',remedy='Reuse/call calculate_research_metric and supply the saved ID, or leave this new claim unresolved.')
        elif check.calculation_check == 'unresolved':
            if check.status != 'unresolved' or not review.unresolved_data_requests:
                error('unresolved_calculation_requires_explicit_unfinished_check')
        elif check.calculation_check == 'bound':
            if not check.calculation_ids:
                error('bound_calculation_requires_saved_ids')
            original = [s.model_dump(mode='json') for s in check.source_checks]
            for ref in check.calculation_ids:
                try:
                    lineage = calculation_lineage(artifacts,messages,ref)
                    for row in lineage['source_checks']:
                        if not any(s.source_id==row['source_id'] and s.quote==row['quote'] for s in check.source_checks):
                            check.source_checks.append(ReviewSourceCheck(**row))
                    records.append(parsing_record('review_calculation_lineage_v1',
                        {'calculation_id':ref,'source_checks':original},lineage,**where))
                except (ValueError,KeyError) as exc:
                    error('calculation_binding_unavailable',calculation_id=ref,reason=str(exc),
                        remedy='Read the source and use calculate_research_metric; arbitrary IDs and copied numbers cannot supply a receipt.')
            if len(check.source_checks)>64:
                error('source_bindings_exceed_check_capacity',remedy='Split independent calculations; retain every operand.')

        if check.dimension != 'prose_consistency':
            continue
        if check.financial_verdict is None or check.clarity_verdict is None or not check.clarity_reason.strip():
            error('separate_financial_and_clarity_assessments_required',
                remedy='Assess support and reader-facing clarity separately, with a concise clarity reason. Legacy semantic_verdict is not sufficient.')
        if check.clarity_verdict != 'needs_clarification':
            if check.clarification.strip():
                error('clarification_text_requires_needs_clarification')
            continue
        if not check.clarification.strip() or not check.clarity_reason.strip():
            error('clarification_requires_reason_and_precise_change')
            continue
        try:
            paper=artifacts.read_paper(check.paper_id)
            path=resolve_location(paper,check.field_path,check.target_quote)
            if check.paper_digest!=canonical_sha256(paper) or check.target_quote not in dict(text_locations(paper))[path]:
                raise ValueError('stale_or_nonexact_clarification_target')
        except ValueError as exc:
            error('clarification_target_invalid',reason=str(exc))
            continue
        fid='runtime_clarity_'+canonical_sha256([check.paper_digest,path,check.semantic_target_id or check.target_quote])[:20]
        finding=CaseReviewFinding(finding_id=fid,paper_id=check.paper_id,claim_ids=check.claim_ids,
            severity='material',finding_type='clarification',problematic_quote=check.target_quote,
            diagnosis='Reader-facing clarification required: '+check.clarity_reason,
            requested_change='Preserve supported financial conclusions; clarify this local passage: '+check.clarification,
            source_checks=check.source_checks)
        generated[fid]=finding
        before={'status':check.status,'finding_ids':list(check.finding_ids),'financial_verdict':check.financial_verdict,
                'clarity_verdict':check.clarity_verdict,'clarity_reason':check.clarity_reason,'clarification':check.clarification}
        if fid not in check.finding_ids:
            check.finding_ids.append(fid)
        if check.financial_verdict!='insufficient' and check.calculation_check!='unresolved':
            check.status='issue'
        records.append(parsing_record('review_clarification_handoff_v1',before,
            {'finding':finding.model_dump(mode='json'),'status':check.status},**where,
            notice='Material means this declared delivery issue must be resolved; clarification is not a proved financial error.'))
    if errors:
        raise ValueError(json.dumps({'review_contract_errors':errors},ensure_ascii=False))
    existing={f.finding_id:f for f in review.findings}
    for fid,finding in generated.items():
        if fid in existing and existing[fid] != finding:
            raise ValueError('runtime_clarification_id_collision:' + fid)
        existing[fid]=finding
    review.findings=list(existing.values())
