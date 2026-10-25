import pytest

from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


def catalog():
    return {'a': dict(issuer_id='ISSUER::acme', company_name='Acme Corporation', form='10-K', period_end='2024-06-30'),
            'b': dict(issuer_id='ISSUER::beta', company_name='Beta Corporation', form='10-Q', period_end='2024-09-30'),
            'unknown': dict(issuer_id=None, company_name=None, form=None, period_end=None)}


def test_literal_issuer_form_and_explicit_period_without_answer_ids():
    data = catalog()
    plan = plan_query('Acme 10-K period ending 2024-06-30 revenue', data)
    selected, receipt = select_planned(data, plan)
    assert selected == {'a', 'unknown'} and receipt['unknown_sources_retained'] == 1
    assert plan['constraint']['issuer_id'] == 'ISSUER::acme'
    assert plan['constraint']['period_end'] == '2024-06-30'


@pytest.mark.parametrize('text', ['Acme FY2024 revenue', 'Acme February 2024 investment',
                                  'Acme as of 2024-06-30', 'Acme 2024 annual report'])
def test_years_and_publication_dates_not_converted_to_period_or_form(text):
    plan = plan_query(text, catalog())
    assert 'period_end' not in plan['constraint'] and 'form' not in plan['constraint']
    assert 'year_or_publication_date_not_mapped_to_period_end' in plan['unresolved']


def test_comparison_and_ambiguous_alias_do_not_drop_second_company():
    data = catalog()
    assert select_planned(data, plan_query('Acme versus Beta revenue', data))[0] == set(data)
    data['b']['company_name'] = 'Acme Corporation'
    assert 'issuer_id' not in plan_query('Acme Corporation revenue', data)['constraint']


def test_revision_and_unknown_metadata_preserved():
    data = catalog(); data['a']['form'] = '10-K/A'
    assert select_planned(data, plan_query('Acme 10-K revenue', data))[0] == {'unknown'}
    assert select_planned(data, plan_query('Acme 10-K/A revenue', data))[0] == {'a', 'unknown'}
    assert 'form' not in plan_query('Acme compare 10-K and 10-Q', data)['constraint']
    assert 'period_end' not in plan_query('Acme period ending 2024-02-30', data)['constraint']


def test_old_wire_shape_and_invalid_combined_scope():
    plain = dict(source_space='organization', operation='search', query='Acme')
    assert 'organization_query_planning' not in SourceDocumentRequest(**plain).model_dump(mode='json')
    for extra in [dict(source_space='library'), dict(operation='catalog'), dict(organization_filter={'form':'10-K'})]:
        with pytest.raises(ValueError, match='query_planning_requires'):
            SourceDocumentRequest(**{**plain, **extra}, organization_query_planning='conservative.v1')


def test_real_navigation_plan_cache_and_current_revoke(tmp_path, monkeypatch):
    from test_organization_source_filter import scoped_fixture, query
    text = 'Acme 10-K disclosure'
    nav, reader, state, _, _ = scoped_fixture(tmp_path, monkeypatch, queries=[text])
    request = query(query=text, organization_query_planning='conservative.v1', entity_id='COUNTERPARTY::X')
    result = nav.navigate(request)
    # Known Beta and Acme 10-Q are excluded before every candidate channel;
    # Acme with missing form stays eligible. Synthetic vectors test scope only.
    assert result.organization_query_plan['selected_sources'] == 2
    assert result.organization_query_plan['unknown_sources_retained'] == 1
    assert result.items
    receipt = result.items[0]['retrieval']
    for channel in ('dense_node_ids', 'lexical_node_ids', 'graph_node_ids', 'candidate_node_ids'):
        for node in receipt[channel]:
            meta = nav._candidate_index.source_metadata[nav._candidate_index.rows[node]['parent_document_id']]
            assert meta['company_name'] == 'Acme' and meta['form'] in ('10-K', None)
    cached = nav.navigate(request)
    assert cached.organization_query_plan == result.organization_query_plan
    assert cached.items[0]['retrieval']['response_cache_hit']
    # Fixture's authority callable is replaced to model a fresh Java denial.
    def deny(*args, **kwargs):
        raise RuntimeError('current_authority_denied')
    monkeypatch.setattr(reader, '_grant', deny)
    with pytest.raises(RuntimeError, match='current_authority_denied'):
        nav.navigate(request)
