"""Host-only transfer of accepted Lead calculation receipts to an author.

This is artifact handoff, not a model source-registration endpoint. Recheck the
saved arithmetic against the same case sources; never infer a period, rewrite a
claim, or turn Lead's rationale into financial verification.
"""
from copy import deepcopy
import json

from .research_graph_contracts import RuntimeReceipt, canonical_sha256


def _same_calculation(saved, recomputed):
    # These fields are attached by source/tool transport after calculation.
    # Preserve them in the receipt; they are not outputs of arithmetic replay.
    # Unknown extras still fail rather than silently dropping future semantics.
    transport = {"fact_id", "cell_binding_used", "mcp_receipt_chain", "source_tool_lane_receipt_id"}
    if "fact_id" in saved and saved["fact_id"] != saved["calculation_id"]:
        return False
    return {k: v for k, v in saved.items() if k not in transport} == recomputed


def restore_revision_calculations(state, decision, artifacts, paper_id):
    from .specialist_graph import SpecialistNotebook, SpecialistToolObservation, _replace_notebook
    from .specialist_composition import _reference_from_item
    from sec_agent.research_foundation.source_bound_calculator import (
        CalculationOperand, SourceBoundCalculation, calculate_from_sources)

    ids = sorted({ref for row in decision.get('dispositions', [])
        if row.get('paper_id') == paper_id and row.get('disposition') == 'repair'
        for ref in row.get('citation_ids', []) if ref.startswith('CALC::')})
    if not ids:
        restored = deepcopy(state)
        if isinstance(restored.get('task_context'), dict):
            restored['task_context'].pop('revision_calculation_handoff', None)
        return restored
    # Artifacts and the decision must come from the same trusted parent graph.
    # Exact source resolution and recomputation below also catch stale aliases.
    if (state['task']['case_id'] != artifacts.case_id
            or state['task']['research_as_of'] != artifacts.research_as_of):
        raise ValueError('revision_calculation_case_scope_mismatch')
    owner = artifacts._author_states.get(paper_id) or {}
    if (owner.get('agent_id') != state['agent_id']
            or owner.get('task', {}).get('task_id') != state['task']['task_id']):
        raise ValueError('revision_calculation_author_scope_mismatch')
    citations = decision.get('citations', {})
    if any(ref not in citations for ref in ids):
        raise ValueError('revision_calculation_receipt_missing')
    store = artifacts.with_saved_calculations({ref: citations[ref] for ref in ids})
    notebook = SpecialistNotebook.model_validate_json(json.dumps(state['notebook']))
    known = {ref.ref_id: item for obs in notebook.observations for item in obs.content
             for ref in obs.references if ref.ref_id in [item.get(k) for k in
                ('passage_id', 'evidence_id', 'numeric_fact_id', 'calculation_id', 'fact_id')]}
    additions, receipts = [], {}
    for ref in ids:
        calculation = store.source_item(ref)
        operands = {name: {k: v for k, v in value.items() if k in CalculationOperand.model_fields}
                    for name, value in calculation['operands'].items()}
        for name, value in calculation['operands'].items():
            if not value.get('source_id') and value.get('authority') == 'assumption':
                operands[name]['literal'] = value['value_decimal']
        request = SourceBoundCalculation.model_validate({
            **{k: calculation[k] for k in ('expression', 'result_unit', 'rationale')}, 'operands': operands})
        recomputed = calculate_from_sources(request, store.source_item)
        if not _same_calculation(calculation, recomputed):
            raise ValueError('revision_calculation_original_mismatch:' + ref)
        sources = {op.source_id: store.source_item(op.source_id)
                   for op in request.operands.values() if op.source_id}
        # Original identity is never replaced by the case-local Pxx:Sxxx alias.
        content = []
        for item in [*sources.values(), calculation]:
            reference = _reference_from_item(item)
            if reference is None:
                raise ValueError('revision_calculation_operand_not_citable:' + ref)
            previous = known.get(reference.ref_id)
            if previous is not None:
                if _reference_from_item(previous) != reference:
                    raise ValueError('revision_calculation_source_conflict:' + reference.ref_id)
                continue
            known[reference.ref_id] = item
            content.append(deepcopy(item))
        binding = {'operation': 'accepted_lead_calculation_handoff',
            'decision_digest': canonical_sha256(decision), 'paper_id': paper_id,
            'agent_id': state['agent_id'], 'task_id': state['task']['task_id'],
            'calculation_id': ref, 'calculation_digest': canonical_sha256(calculation),
            'operand_sources_digest': canonical_sha256(sources)}
        digest = canonical_sha256(binding)
        receipts[ref] = {'binding': binding, 'calculation': deepcopy(calculation),
            'operand_sources': deepcopy(sources), 'arithmetic_recheck': 'exact_original_match',
            'recheck_scope': 'calculation_content_and_identity; original_transport_metadata_preserved',
            'financial_semantics_verified': False}
        if content:
            payload = dict(schema_version='fin_ia_specialist_tool_observation_v1_0',
                action_attempt_id='saved-calculation-handoff:' + digest, kind='finance',
                provenance_kind='direct_tool', status='success', request_digest=digest,
                references=[_reference_from_item(item).model_dump(mode='json') for item in content],
                content=content, route_completions=[], failure=None, source_runtime_receipt=None)
            payload['runtime_receipt'] = RuntimeReceipt(receipt_id='saved-calculation-handoff:' + digest,
                kind='tool', actor='finance_tool', status='success', request_digest=digest,
                output_digest=canonical_sha256(payload), elapsed_ms=0).model_dump(mode='json')
            payload['observation_digest'] = canonical_sha256(payload)
            additions.append(SpecialistToolObservation.model_validate_json(json.dumps(payload)))
    restored = deepcopy(state)
    restored['notebook'] = _replace_notebook(notebook,
        observations=(*notebook.observations, *additions)).model_dump(mode='json')
    restored['task_context'] = {**(restored.get('task_context') or {}),
        'revision_calculation_handoff': {'receipts': receipts,
            'notice': 'Saved Lead calculation artifacts, locally rechecked against the same case sources. '
                'Available for author evaluation; neither adopted conclusions nor financial verification.'}}
    return restored
