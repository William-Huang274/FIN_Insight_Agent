"""Reconcile saved reader projections, never merge different evidence versions."""
from copy import deepcopy
import json


def resolve_citation_snapshot(records):
    first = records[0]
    source_id = first['source_id']
    if any(r.get('source_id') != source_id for r in records):
        raise ValueError('citation_snapshot_conflict')
    if source_id.startswith('CALC::') and all(isinstance(r.get('calculation'), dict) for r in records):
        calculation = first['calculation']
        if calculation.get('calculation_id') != source_id or any(r['calculation'] != calculation for r in records):
            raise ValueError('citation_snapshot_conflict')
        # Report previews and final-answer bindings have different display
        # schemas. Their complete immutable calculator payload is the identity.
        result = deepcopy(first)
        result.update(text=json.dumps(calculation, ensure_ascii=False, indent=2),
                      offset=0, next_offset=None, unit=calculation['result_unit'])
        return result
    full = [r for r in records if isinstance(r.get('passage'), str)
            and r.get('source_role') == 'external_public_source_unverified']
    if full:
        from sec_agent.agent_runtime.public_source_restore import validated_public_source
        from sec_agent.agent_runtime.case_artifacts import CaseArtifacts
        original = validated_public_source(full[0])
        summary = CaseArtifacts._source_summary(source_id, original)
        text = original['passage']
        for row in records:
            if CaseArtifacts._source_summary(source_id, row) != summary:
                raise ValueError('citation_snapshot_conflict')
            if 'passage' in row and row['passage'] != text:
                raise ValueError('citation_snapshot_conflict')
            start = row.get('offset', 0)
            excerpt = row.get('text', row.get('passage', ''))
            if type(start) is not int or start < 0 or text[start:start+len(excerpt)] != excerpt:
                raise ValueError('citation_snapshot_conflict')
        result = deepcopy(first)
        result.update(text=text, offset=0, next_offset=None, captured_characters=len(text))
        return result
    if any(row != first for row in records[1:]):
        raise ValueError('citation_snapshot_conflict')
    return deepcopy(first)
