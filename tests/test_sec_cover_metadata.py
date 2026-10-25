from hashlib import sha256
import json
import sqlite3

import pytest

from sec_agent.research_foundation.organization_source_filter import source_metadata_details
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from test_organization_candidate_index import prepared, query


HEADER = 'United States\nSECURITIES AND EXCHANGE COMMISSION\nWashington, D.C. 20549\n'
COVER = HEADER + 'FORM\n10-K\nAnnual Report\nfor the fiscal year ended June 30, 2026\n'


def bundle(text=COVER, **metadata):
    return {'source': {'id': 'SRC::cover', 'url': 'https://www.sec.gov/Archives/edgar/data/123/report.htm',
        'title': 'Do not infer 10-Q from title', 'metadata': json.dumps({'category': 'filing', **metadata})}, 'text': text}


def test_recover_explicit_cover_with_exact_original_span_not_fiscal_year():
    source = bundle(period_end='2026-06-30')
    descriptor, proof = source_metadata_details(source)
    assert descriptor['form'] == '10-K' and descriptor['period_end'] == '2026-06-30'
    assert 'fiscal_year' not in descriptor
    assert proof['status'] == 'recovered'
    assert source['text'][proof['char_start']:proof['char_end']] == proof['quote']
    assert sha256(proof['quote'].encode()).hexdigest() == proof['quote_sha256']
    assert json.loads(source['source']['metadata']).get('form') is None


@pytest.mark.parametrize('form', ['10-K', '10-Q', '8-K', '10-K/A', '10-Q/A', '8-K/A'])
def test_exact_forms_and_amendments(form):
    descriptor, proof = source_metadata_details(bundle(HEADER+'FORM '+form+'\n'))
    assert descriptor['form'] == proof['form'] == form


@pytest.mark.parametrize('text', [
    'Our discussion references Form 10-K.\n',
    'x'*2100 + COVER,
    HEADER + 'x'*350 + '\nFORM 10-K\n',
    HEADER + 'FORM 10-K\nFORM 10-Q\n',
    HEADER + 'See our previously filed Form 10-K.\n',
])
def test_references_late_or_ambiguous_headers_stay_unknown(text):
    descriptor, proof = source_metadata_details(bundle(text))
    assert descriptor['form'] is None and proof is None


@pytest.mark.parametrize('url,category', [
    ('https://sec.gov.evil.test/Archives/edgar/data/123/x', 'filing'),
    ('https://www.sec.gov/Archives/edgar/data/123/ex99.htm', 'filing_exhibit'),
    ('https://www.sec.gov/news/x', 'filing'),
    ('https://example.test/report', 'filing'),
])
def test_cover_recovery_is_only_for_original_sec_filings(url, category):
    source = bundle(category=category)
    source['source']['url'] = url
    descriptor, proof = source_metadata_details(source)
    assert descriptor['form'] is None and proof is None


def test_conflicting_metadata_is_not_silently_overwritten():
    descriptor, proof = source_metadata_details(bundle(form='10-Q'))
    assert descriptor['form'] is None
    assert proof['status'] == 'conflict' and proof['metadata_form'] == '10-Q' and proof['form'] == '10-K'
    assert source_metadata_details(bundle(form='10-K'))[1]['status'] == 'confirmed'


def test_calendar_annual_year_requires_exact_cover_and_matching_period():
    text=HEADER+'FORM\n10-K\nFor the fiscal year ended\nDecember 31\n, 2025\n'
    source=bundle(text,period_end='2025-12-31')
    descriptor, proof=source_metadata_details(source)
    assert descriptor['calendar_annual_year']=='2025'
    year=proof['calendar_annual_year']
    assert source['text'][year['char_start']:year['char_end']]==year['quote']
    for period in ('2024-12-31', None, '2025-06-30'):
        assert 'calendar_annual_year' not in source_metadata_details(bundle(text,period_end=period))[0]
    assert 'calendar_annual_year' not in source_metadata_details(bundle(text,form='10-Q',period_end='2025-12-31'))[0]
    assert 'calendar_annual_year' not in source_metadata_details(bundle(COVER,period_end='2026-06-30'))[0]


def test_calendar_annual_year_ignores_body_reference_and_multiple_dates():
    text=HEADER+'FORM 10-K\n'+('x'*2050)+'\nFor the fiscal year ended December 31, 2025'
    assert 'calendar_annual_year' not in source_metadata_details(bundle(text,period_end='2025-12-31'))[0]
    text=HEADER+'FORM 10-K\nFor the fiscal year ended December 31, 2025\nFor the fiscal year ended December 31, 2024'
    assert 'calendar_annual_year' not in source_metadata_details(bundle(text,period_end='2025-12-31'))[0]


def test_actual_capture_warmup_filter_and_readback_use_same_recovered_cover(tmp_path, monkeypatch):
    import test_organization_complete_sources as fixtures
    original = fixtures.database
    def database(path, text):
        source = original(path, COVER+text)
        with sqlite3.connect(path) as db:
            db.execute('UPDATE sources SET url=?,metadata=?',
                ('https://www.sec.gov/Archives/edgar/data/123/report.htm',
                 json.dumps({'category': 'filing', 'entity_id': 'ISSUER::A'})))
        return source
    monkeypatch.setattr(fixtures, 'database', database)
    nav, reader, state, *_ = prepared(tmp_path, monkeypatch)
    legacy = nav.navigate({'source_space': 'organization', 'operation': 'catalog'})
    assert all(r['organization_metadata']['form'] is None for r in legacy.items)
    assert all('organization_metadata_evidence' not in r for r in legacy.items)
    assert not nav.navigate(query(organization_filter={'form': '10-K'})).items
    catalog = nav.navigate({'source_space': 'organization', 'operation': 'catalog', 'organization_metadata_policy': 'sec_cover.v2'})
    assert all(r['organization_metadata']['form'] == '10-K' for r in catalog.items)
    assert all(r['organization_metadata_evidence']['status'] == 'recovered' for r in catalog.items)
    request = query(organization_filter={'issuer_id': 'ISSUER::A', 'form': '10-K'}, organization_metadata_policy='sec_cover.v2')
    original_read = reader._read_storage
    def no_originals(*args):
        raise AssertionError('a policy change must reuse verified descriptors, not reload source bodies')
    monkeypatch.setattr(reader, '_read_storage', no_originals)
    result = nav.navigate(request)
    assert result.items and result.organization_filter_receipt.matched_sources == 2
    assert result.organization_filter_receipt.metadata_policy == 'sec_cover.v2'
    assert not nav.navigate(query(organization_filter={'form': '10-K'})).items
    assert nav.navigate(request).items
    monkeypatch.setattr(reader, '_read_storage', original_read)
    read = nav.navigate(result.items[0]['readback'])
    assert read.items[0]['original_source']['source_id'] == 'SRC::fixture'
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(request)


def test_policy_is_explicit_serialized_and_separates_cache_identity():
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from sec_agent.research_foundation.organization_search_cache import OrganizationSearchCache
    legacy = SourceDocumentRequest.model_validate(query(organization_filter={'form': '10-K'}))
    recovered = SourceDocumentRequest.model_validate(query(organization_filter={'form': '10-K'}, organization_metadata_policy='sec_cover.v2'))
    assert legacy.organization_metadata_policy == 'original.v1'
    assert 'organization_metadata_policy' not in legacy.model_dump(mode='json')
    assert recovered.model_dump(mode='json')['organization_metadata_policy'] == 'sec_cover.v2'
    assert OrganizationSearchCache.key({}, legacy) != OrganizationSearchCache.key({}, recovered)
    for change in ({'source_space': 'library'}, {'operation': 'read', 'document_id': 'doc'}):
        with pytest.raises(ValueError, match='metadata_policy_requires'):
            SourceDocumentRequest.model_validate(query(organization_metadata_policy='sec_cover.v2', **change))
