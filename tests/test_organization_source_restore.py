"""Host checkpoint restoration against fixed originals; no model or remote search."""
import asyncio
from copy import deepcopy

import pytest

from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_at, runtime_grant
from test_organization_source_navigation import read_first
from test_organization_data_composition import organization, specialist


def observations(*items):
    return [{'status':'success', 'content':list(items)}]


def fresh(nav):
    return OrganizationSourceNavigation(nav.reader, workbench_url=nav.workbench_url)


@pytest.fixture
def archive(tmp_path):
    shared, preparation = fixture(tmp_path, body=b'Revenue 123.40 USD in 2025.')
    reader, state = runtime_at(shared, runtime_grant(preparation))
    nav = OrganizationSourceNavigation(reader, workbench_url='https://workbench.example.test')
    passage = read_first(nav).items[0]
    calc = nav.calculate(SourceBoundCalculation(expression='revenue * scale', operands={
        'revenue':{'source_id':passage['passage_id'], 'quote':passage['passage'], 'literal':'123.40'},
        'scale':{'literal':'2', 'assumption_note':'Synthetic scenario; not an issuer forecast'}},
        result_unit='USD', rationale='Static arithmetic fixture, not financial validation'))
    chained = nav.calculate(SourceBoundCalculation(expression='previous / 2', operands={
        'previous':{'source_id':calc['calculation_id']}}, result_unit='USD', rationale='Static inverse arithmetic'))
    return nav, state, shared, passage, calc, chained


def test_new_session_reloads_original_and_recomputes_chain_in_dependency_order(archive):
    nav, _, _, passage, calc, chained = archive
    restored = fresh(nav)
    saved = observations(chained, calc, {**passage, 'mcp_receipt_chain':[{'unverified':'transport-only'}]})
    result = restored.restore(saved)
    assert set(result) == {passage['passage_id'], calc['calculation_id'], chained['calculation_id']}
    assert restored.source(passage['passage_id']) == passage
    assert restored.source(chained['calculation_id']) == chained
    assert chained['value_decimal'] == '123.40'
    assert calc['operands']['revenue']['source_provenance']['organization_source'] == passage['organization_source']
    assert chained['operands']['previous']['source_provenance']['organization_execution'] == nav.execution_scope
    assert not chained['financial_semantics_verified']
    result[chained['calculation_id']]['value_decimal'] = '999'
    assert restored.source(chained['calculation_id']) == chained


def test_shared_calculator_identity_restores_via_verified_dependencies(archive):
    from sec_agent.research_foundation.source_bound_calculator import calculate_from_sources
    nav, state, _, passage, _, _ = archive
    plain = calculate_from_sources(SourceBoundCalculation(expression='revenue * 2', operands={
        'revenue':{'source_id':passage['passage_id'],'quote':passage['passage'],'literal':'123.40'}},
        result_unit='USD',rationale='Shared calculator'), lambda key: passage)
    chain = calculate_from_sources(SourceBoundCalculation(expression='previous / 2', operands={
        'previous':{'source_id':plain['calculation_id']}},result_unit='USD',rationale='Shared chain'),lambda key:plain)
    assert 'organization_execution' not in plain
    result = fresh(nav).restore(observations(passage,plain,chain))
    assert result[plain['calculation_id']] == plain
    assert result[chain['calculation_id']] == chain
    corrupt=deepcopy(plain); corrupt['value_decimal']='0'
    with pytest.raises(ValueError,match='mismatch'):
        fresh(nav).restore(observations(passage,corrupt))
    state['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):
        fresh(nav).restore(observations(passage,plain,chain))


def public_calculation_fixture():
    from hashlib import sha256
    from sec_agent.research_foundation.source_bound_calculator import calculate_from_sources
    text = 'Group activities\n(4,467) (7,655)'
    digest = sha256(text.encode()).hexdigest()
    doc = 'WEB::public-fixture'
    passage = {'result_state':'source_bound_passage', 'writer_citable':True,
        'source_role':'external_public_source_unverified', 'numeric_fact_authority':False,
        'source_url':'https://example.test/filing', 'document_id':doc, 'passage':text,
        'passage_id':f'PASSAGE::{doc}::0::{digest[:16]}', 'content_sha256':digest,
        'publication_date':'2026-10-28',
        'source_locator':{'document_id':doc, 'source_url':'https://example.test/filing',
            'content_sha256':digest, 'character_start':0, 'character_end':len(text),
            'captured_at':'2026-11-07T12:00:00+00:00', 'capture_receipt_digest':'a'*64}}
    calculation = calculate_from_sources(SourceBoundCalculation(expression='a * 2', operands={
        'a':{'source_id':passage['passage_id'], 'quote':'Group activities\n(4,467)\n(7,655)',
             'literal':'7,655'}}, result_unit='USD million', rationale='Fixture'), lambda key:passage)
    chain = calculate_from_sources(SourceBoundCalculation(expression='a / 2', operands={
        'a':{'source_id':calculation['calculation_id']}}, result_unit='USD million',
        rationale='Chained fixture'), lambda key:calculation)
    return passage, calculation, chain


def test_public_recapture_and_quote_compatibility_preserve_calculation_identity(archive):
    from sec_agent.agent_runtime.public_source_restore import validated_public_source
    nav, *_ = archive
    original, calc, chain = public_calculation_fixture()
    later = deepcopy(original)
    later['source_locator'].update(captured_at='2026-11-07T14:00:00+00:00',
                                   capture_receipt_digest='b'*64)
    result = fresh(nav).restore(observations(later, calc, chain),
        external_source_lookup=lambda key:validated_public_source(later))
    assert result[calc['calculation_id']] == calc
    assert result[chain['calculation_id']] == chain
    assert result[later['passage_id']] == later
    assert result[calc['calculation_id']]['operands']['a']['quote_layout_recovery']


@pytest.mark.parametrize('field', ['publication_date','source_url','value','unit','recovery'])
def test_recapture_does_not_hide_semantic_or_receipt_changes(archive, field):
    from sec_agent.agent_runtime.public_source_restore import validated_public_source
    nav, *_ = archive
    passage, calc, chain = public_calculation_fixture()
    if field == 'publication_date': passage[field]='2027-01-01'
    elif field == 'source_url': passage[field]='https://example.test/other'
    elif field == 'value': calc['value_decimal']='0'
    elif field == 'unit': calc['result_unit']='percent'
    else: calc['operands']['a']['quote_layout_recovery']['basis']['start']=999
    with pytest.raises(ValueError):
        fresh(nav).restore(observations(passage, calc, chain),
            external_source_lookup=lambda key:validated_public_source(passage))


def test_unscoped_assumptions_do_not_establish_organization_authority(archive):
    from sec_agent.research_foundation.source_bound_calculator import calculate_from_sources
    nav,*_ = archive
    value=calculate_from_sources(SourceBoundCalculation(expression='a * 2',operands={
        'a':{'literal':'3','assumption_note':'Scenario'}},result_unit='USD',rationale='Scenario'), lambda key:None)
    with pytest.raises(ValueError,match='scope_unproven'):
        fresh(nav).restore(observations(value))


@pytest.mark.parametrize('fault', ['text','reference','execution','missing_scope','value','unit','formula','quote','provenance','authority','duplicate'])
def test_tampered_batch_never_partially_publishes(archive, fault):
    nav, _, _, passage, calc, chained = archive
    saved = observations(deepcopy(passage), deepcopy(calc), deepcopy(chained))
    p, c, _ = saved[0]['content']
    if fault == 'text': p['passage'] = 'Different original'
    elif fault == 'reference': p['organization_source']['ref']['version_id'] = 'different'
    elif fault == 'execution': c['organization_execution']['execution_id'] = 'other-execution'
    elif fault == 'missing_scope': p['organization_source'].pop('execution_id')
    elif fault == 'value': c['value_decimal'] = '1000'
    elif fault == 'unit': c['result_unit'] = 'EUR'
    elif fault == 'formula': c['expression'] = 'revenue + scale'
    elif fault == 'quote': c['operands']['revenue']['quote'] = 'Invented revenue 123.40'
    elif fault == 'provenance': c['operands']['revenue']['source_provenance']['organization_source']['resource_id'] = 'other'
    elif fault == 'authority': c['numeric_fact_authority'] = True
    elif fault == 'duplicate': saved[0]['content'].append({**p, 'passage':'Conflicting duplicate'})
    restored = fresh(nav)
    with pytest.raises(ValueError): restored.restore(saved)
    for item in (passage, calc, chained):
        with pytest.raises(ValueError, match='not_observed'):
            restored.source(item.get('passage_id') or item['calculation_id'])


def test_cross_execution_is_rejected_even_when_manifest_is_identical(archive):
    nav, state, shared, passage, _, _ = archive
    from uuid import uuid4
    grant = deepcopy(state['grant'])
    grant['execution_id'] = grant['thread_id'] = str(uuid4())
    reader, _ = runtime_at(shared, grant)
    other = OrganizationSourceNavigation(reader, workbench_url=nav.workbench_url)
    with pytest.raises(ValueError, match='scope_mismatch'): other.restore(observations(passage))


def test_small_decimal_assumptions_roundtrip_without_losing_precision(archive):
    nav, _, _, _, _, _ = archive
    calc = nav.calculate(SourceBoundCalculation(expression='small * 2', operands={
        'small':{'literal':'0.000000001', 'assumption_note':'Synthetic small decimal'}},
        result_unit='USD', rationale='Static exact decimal roundtrip'))
    assert calc['operands']['small']['value_decimal'] == '1E-9'
    restored = fresh(nav)
    restored.restore(observations(calc))
    assert restored.source(calc['calculation_id']) == calc


@pytest.mark.parametrize('value', ['1E+999999999','0E-999999999','NaN','Infinity'])
def test_corrupt_assumption_is_rejected_before_expanding_decimal(archive, value):
    nav, _, _, passage, calc, _ = archive
    corrupt = deepcopy(calc)
    corrupt['operands']['scale']['value_decimal'] = value
    restored = fresh(nav)
    with pytest.raises(ValueError, match='assumption_out_of_range'):
        restored.restore(observations(passage, corrupt))
    assert restored.observed.get(passage['passage_id']) is None


def test_missing_dependency_and_cycles_cannot_be_imported(archive):
    nav, _, _, passage, calc, chained = archive
    with pytest.raises(ValueError, match='not_observed'): fresh(nav).restore(observations(calc))
    cycle = deepcopy(chained)
    cycle['operands']['previous']['source_id'] = cycle['calculation_id']
    with pytest.raises(ValueError, match='calculation_cycle'): fresh(nav).restore(observations(passage, cycle))
    # A previously verified source in this same session is a valid dependency.
    restored = fresh(nav)
    restored.restore(observations(passage))
    restored.restore(observations(calc, chained))
    assert restored.source(chained['calculation_id']) == chained


@pytest.mark.parametrize('fault', ['revoked','outage','bytes','mid_restore'])
def test_permissions_and_original_storage_are_rechecked_before_atomic_publish(archive, monkeypatch, fault):
    nav, state, shared, passage, calc, _ = archive
    restored = fresh(nav)
    if fault == 'revoked': state['status'] = 404
    elif fault == 'outage': state['timeout'] = True
    elif fault == 'bytes':
        get = shared.workspace.library.documents.get
        monkeypatch.setattr(shared.workspace.library.documents, 'get', lambda *a, **k: {**get(*a, **k), 'body':b'Corrupt'})
    else:
        read = nav.reader.workspace.read_source
        def revoke_after_read(*args):
            result = read(*args)
            state['status'] = 404
            return result
        monkeypatch.setattr(nav.reader.workspace, 'read_source', revoke_after_read)
    with pytest.raises(OrganizationExecutionUnavailable): restored.restore(observations(passage, calc))
    assert restored.observed.get(passage['passage_id']) is None
    assert restored.observed.get(calc['calculation_id']) is None


def test_navigation_failed_results_and_foreign_authority_never_become_citations(archive):
    nav, _, _, passage, _, _ = archive
    restored = fresh(nav)
    assert restored.restore([{'status':'tool_failure','content':[passage]},
        {'status':'success','failure':{'reason':'denied'},'content':[passage]},
        {'status':'success','content':[{'result_state':'navigation_preview','passage_id':'fake'}]}]) == {}
    for kind in ('numeric_fact','reviewed_evidence'):
        with pytest.raises(ValueError, match='authority_not_supported'):
            restored.restore(observations(passage, {'result_state':kind}))
    assert restored.observed.get(passage['passage_id']) is None


def test_actual_expert_observation_can_feed_reopened_factory_and_mcp(organization):
    from mcp import Client
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from test_specialist_tool_batch import _handoff
    factory, state = organization
    turns = []
    def model(request):
        turns.append(request)
        if len(turns) > 1: return _handoff(request)
        return {'action':'request_source', 'context_digest':request['context_digest'],
            'reason_summary':'Read selected original for deterministic continuation.',
            'selection':{'source_space':'organization','operation':'read','document_id':document}}
    with specialist(factory, model) as opened:
        catalog = opened.source_reader(SourceDocumentRequest(source_space='organization',operation='catalog'))
        assert catalog.get('status') == 'success', catalog
        document = next(row['document_id'] for row in catalog['items'] if 'document_id' in row)
        result = opened.graph.invoke(opened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    saved = result['notebook']['observations']
    passage = next(row for row in saved[0]['content'] if row.get('result_state') == 'source_bound_passage')
    with specialist(factory, recovery_state=result) as reopened:
        continued = reopened.graph.invoke(reopened.graph_input.model_dump(mode='json'), {'recursion_limit':32})
    assert continued['notebook']['observations'] == saved
    assert continued['notebook']['model_turn_count'] == result['notebook']['model_turn_count'] + 1
    with factory(run_invocation_id='resume-attempt', source_read_enabled=True, restored_observations=saved) as data:
        async def exercise():
            async with Client(data.mcp_server, raise_exceptions=False) as client:
                restored = await client.call_tool('read_research_source', {'source_id':passage['passage_id']})
                assert not restored.is_error and 'Pinned original evidence.' in str(restored)
                state['status'] = 404
                denied = await client.call_tool('read_research_source', {'source_id':passage['passage_id']})
                assert denied.is_error and 'Pinned original evidence.' not in str(denied)
        asyncio.run(exercise())
    with pytest.raises(OrganizationExecutionUnavailable):
        with factory(run_invocation_id='denied-attempt', source_read_enabled=True, restored_observations=saved): pass
