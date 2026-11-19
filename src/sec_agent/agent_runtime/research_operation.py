"""One version-bound research operation, not a prescribed workflow.

The parent chooses the operation. Host readers own identities and versions;
native checkpoints own work in progress. No task store or model is created here.
"""
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .research_graph_contracts import canonical_sha256


class ResearchOperation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: Literal['synthesize', 'compose', 'review_report', 'review_synthesis', 'review_workpaper', 'revise_workpaper']
    purpose: str = Field(min_length=1, max_length=4000)
    # Values come from the runtime catalog, never model-generated source bodies.
    basis: dict[str, str] = Field(min_length=1, max_length=32)
    paper_id: str | None = None
    reviewer: Literal['verifier', 'counter'] = 'verifier'
    findings: list[dict] = Field(default_factory=list, max_length=40)
    review_scope: Literal['whole', 'selected'] = 'whole'
    quotes: list[str] = Field(default_factory=list, max_length=24)

    @model_validator(mode='after')
    def shape(self):
        import re
        if any(not re.fullmatch(r'[a-f0-9]{64}', v) for v in self.basis.values()):
            raise ValueError('copy_exact_digest_from_research_object_catalog')
        reviewing = self.action.startswith('review_')
        if (self.paper_id is not None) != (self.action in {'revise_workpaper', 'review_workpaper'}):
            raise ValueError('paper_id_required_only_for_workpaper_review_or_revision')
        if self.reviewer != 'verifier' and self.action != 'review_workpaper':
            raise ValueError('counter_role_available_for_workpaper_review')
        if self.action == 'review_workpaper' and self.review_scope != 'whole':
            raise ValueError('workpaper_review_scope_is_the_selected_paper_with_necessary_dependencies')
        if self.findings and self.action != 'revise_workpaper':
            raise ValueError('findings_belong_to_requested_workpaper_revision')
        if self.action == 'revise_workpaper' and not self.findings:
            raise ValueError('revision_requires_concrete_findings')
        if self.review_scope == 'selected':
            if not reviewing or not self.quotes or any(not q.strip() for q in self.quotes):
                raise ValueError('selected_review_requires_literal_target_quotes')
        elif self.quotes:
            raise ValueError('quotes_require_selected_review')
        return self


def source_collection_digest(sources):
    # Transport attestations are retained in the journal, but opening a new
    # authorized reader must not turn identical originals into a new version.
    values = {}
    for ref, source in sources.items():
        value = {k: v for k, v in source.items() if k not in {'mcp_receipt_chain', 'source_tool_lane_receipt_id'}}
        if value.get('cell_binding_used') is False:
            value.pop('cell_binding_used')
        if value.get('operand_source_aliases') == {}:
            value.pop('operand_source_aliases')
        if value.get('calculation_id') and value.get('fact_id') == value['calculation_id']:
            value.pop('fact_id')  # Exact redundant alias, not a numeric fact.
        values[ref] = value
    return canonical_sha256(values)


def object_catalog(artifacts, state):
    current = artifacts.with_revisions(state.get('revisions', {}))
    rows = [{'id': 'paper:' + r['paper_id'], 'kind': 'workpaper',
             'digest': canonical_sha256(current.read_paper(r['paper_id'])),
             'read': {'tool': 'read_research_object', 'object_id': 'paper:' + r['paper_id']}}
            for r in current.catalog()['papers']]
    sources = current.source_snapshot()
    if sources:
        rows.append({'id': 'observed_sources', 'kind': 'source_collection', 'digest': source_collection_digest(sources),
            'read': {'tool': 'read_research_object', 'object_id': 'observed_sources'}})
    for key in ('synthesis', 'report'):
        if state.get(key):
            rows.append({'id': key, 'kind': key, 'digest': canonical_sha256(state[key]),
                         'read': {'tool': 'read_research_object', 'object_id': key}})
    return rows


def bind_operation(request, artifacts, state):
    """Check exact versions before resource/model use; never interpret findings."""
    request = ResearchOperation.model_validate(request)
    available = {r['id']: r['digest'] for r in object_catalog(artifacts, state)}
    if any(available.get(key) != digest for key, digest in request.basis.items()):
        raise ValueError('research_object_version_changed_read_current_catalog')
    required = ('paper:' + request.paper_id if request.paper_id else
                'report' if request.action == 'review_report' else
                'synthesis' if request.action == 'review_synthesis' else None)
    if required and required not in request.basis:
        raise ValueError('operation_target_missing_from_basis')
    if request.action == 'compose' and state.get('report') and 'report' not in request.basis:
        raise ValueError('existing_report_revision_requires_current_report_basis')
    locations = []
    if request.review_scope == 'selected':
        text = state[required]['narrative_markdown']
        for quote in request.quotes:
            if text.count(quote) != 1:
                raise ValueError('review_quote_must_match_one_location_read_more_context')
            start = text.index(quote)
            locations.append({'quote': quote, 'start': start, 'end': start + len(quote)})
    if request.action == 'revise_workpaper':
        # Native author tooling expects identified findings; no inferred IDs,
        # invented verdict or automatic categorization is added by the host.
        ids = [f.get('finding_id') for f in request.findings]
        if any(not isinstance(x, str) or not x for x in ids) or len(set(ids)) != len(ids):
            raise ValueError('revision_findings_require_unique_ids')
        if any(not f.get('requested_change') or not f.get('diagnosis') for f in request.findings):
            raise ValueError('revision_findings_require_diagnosis_and_requested_change')
    return {**request.model_dump(mode='json'), 'locations': locations,
            'input_versions': available,
            'operation_digest': canonical_sha256({'request': request.model_dump(mode='json'), 'input_versions': available})}


def operation_input(bound, state):
    """Current objects only. Prior review is version-bound background, not a route."""
    value = {key: deepcopy(state[key]) for key in ('revisions', 'report', 'synthesis') if state.get(key)}
    for record in reversed(state.get('operation_records', [])):
        key = {'review_report': 'report_review', 'review_synthesis': 'synthesis_review'}.get(record['action'])
        if key and key not in value:
            target = 'report' if key == 'report_review' else 'synthesis'
            if (record.get('status') == 'submitted' and record['basis'].get(target) == canonical_sha256(state.get(target))
                    and all(bound['input_versions'].get(k) == v for k, v in record.get('input_versions', record['basis']).items())):
                value[key] = deepcopy(record['output'])
    return {**value, 'pending_feedback': {bound['paper_id']: deepcopy(bound['findings'])} if bound['action'] == 'revise_workpaper' else {},
            'correction_round': 0, 'stop_reason': None}
