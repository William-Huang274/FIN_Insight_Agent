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


@pytest.mark.parametrize('text',["In Acme's fiscal 2024 annual report, did Beta complete its investment?",
                                'Acme 2024 年年报中 Beta 的投资是已完成还是计划？'])
def test_explicit_report_owner_is_not_confused_with_counterparty(text):
    plan=plan_query(text,catalog())
    assert plan['constraint']['issuer_id']=='ISSUER::acme'
    assert 'period_end' not in plan['constraint']
    assert any(e['basis']=='explicit_report_owner_not_counterparty' for e in plan['evidence'])
    assert 'issuer_id' not in plan_query('Compare '+text,catalog())['constraint']
    assert 'issuer_id' not in plan_query('比较 '+text,catalog())['constraint']


def test_two_report_owners_and_unknown_issuer_remain_broad():
    assert 'issuer_id' not in plan_query("Acme's annual report and Beta's annual report sales",catalog())['constraint']
    assert 'issuer_id' not in plan_query('Unknown fiscal 2024 annual report',catalog())['constraint']


def test_revision_and_unknown_metadata_preserved():
    data = catalog(); data['a']['form'] = '10-K/A'
    assert select_planned(data, plan_query('Acme 10-K revenue', data))[0] == {'unknown'}
    assert select_planned(data, plan_query('Acme 10-K/A revenue', data))[0] == {'a', 'unknown'}
    assert 'form' not in plan_query('Acme compare 10-K and 10-Q', data)['constraint']
    assert 'period_end' not in plan_query('Acme period ending 2024-02-30', data)['constraint']


@pytest.mark.parametrize('query', ['Acme FY2024 annual report revenue', 'Acme 2024 财年年报收入'])
def test_annual_report_kind_retains_foreign_annual_forms_and_unknowns(query):
    data = catalog()
    data['b'].update(issuer_id='ISSUER::acme', company_name='Acme Corporation')
    data['foreign'] = {**data['a'], 'form':'20-F'}
    data['amendment'] = {**data['a'], 'form':'10-K/A'}
    data['unclassified'] = {**data['a'], 'form':'custom-report'}
    plan = plan_query(query, data)
    assert plan['constraint']['report_kind'] == 'annual'
    assert 'period_end' not in plan['constraint'] and 'form' not in plan['constraint']
    assert select_planned(data, plan)[0] == {'a', 'unknown', 'foreign', 'amendment', 'unclassified'}
    assert 'report_kind' not in plan_query('Acme annual report and quarterly report',data)['constraint']
    assert plan_query('Acme quarterly report', data)['constraint']['report_kind'] == 'quarterly'


def test_old_wire_shape_and_invalid_combined_scope():
    plain = dict(source_space='organization', operation='search', query='Acme')
    assert 'organization_query_planning' not in SourceDocumentRequest(**plain).model_dump(mode='json')
    for extra in [dict(source_space='library'), dict(operation='catalog'), dict(organization_filter={'form':'10-K'})]:
        with pytest.raises(ValueError, match='query_planning_requires'):
            SourceDocumentRequest(**{**plain, **extra}, organization_query_planning='conservative.v1')


def test_report_year_filters_only_cover_verified_calendar_annuals():
    data = {'current':{'calendar_annual_year':'2025'}, 'old':{'calendar_annual_year':'2024'},
            'fiscal':{'period_end':'2025-01-31'}, 'unknown':{}}
    for query in ("Acme's 2025 annual report expected 2026 spending", 'Acme 2025 财年年报收入',
                  'Acme 2025 10-K revenue'):
        plan=plan_query(query,data)
        assert plan['constraint']['annual_report_year']=='2025'
        assert 'period_end' not in plan['constraint']
        assert select_planned(data,plan)[0]=={'current','fiscal','unknown'}
    for query in ('Acme FY2025 revenue', 'February 2025 investment announcement',
                  'Acme 2025 annual report versus 2024 annual report',
                  'Acme 2024 and 2025 annual reports', 'Acme 2024 与 2025 年年报'):
        assert 'annual_report_year' not in plan_query(query,data)['constraint']


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
