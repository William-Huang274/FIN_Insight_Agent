from hashlib import sha256
import json

import pytest

from sec_agent.research_foundation.organization_source_filter import source_metadata_details
from sec_agent.research_foundation.organization_query_plan import document_constraint_states
from retrieval.same_original_metadata import resolve

URL = 'https://www.sec.gov/Archives/edgar/data/123/000000012326000001/report.htm'
HEADER = 'UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION\nFORM 10-K\n'


def source(heading, *, end='2026-01-30', form='10-K', tail=''):
    return {'source': {'id':'source', 'url':URL, 'metadata':json.dumps({
        'category':'filing', 'form':form, 'period_end':end})},
        'text':HEADER+'For the fiscal year ended January 30, 2026\n'+heading+'\n'+tail}


@pytest.mark.parametrize('heading', [
    'Fiscal 2025 Annual Report on Form 10-K',
    '**Fiscal Year 2025 Annual Report**',
    'Fiscal\n2025\nAnnual Report on Form\n10-K',
])
def test_explicit_original_heading_not_end_or_publication_year(heading):
    bundle = source(heading)
    metadata, proof = source_metadata_details(bundle)
    assert metadata['fiscal_report_year'] == '2025'
    assert 'calendar_annual_year' not in metadata
    for item in proof['fiscal_report_year']['proofs']:
        assert bundle['text'][item['char_start']:item['char_end']] == item['quote']
        assert sha256(item['quote'].encode()).hexdigest() == item['quote_sha256']
    plan = {'policy':'conservative.v5', 'constraint':{'annual_report_year':'2025'}}
    assert document_constraint_states({'doc':metadata}, plan) == {'doc':'match'}
    plan['constraint']['annual_report_year'] = '2026'
    assert document_constraint_states({'doc':metadata}, plan) == {'doc':'mismatch'}


@pytest.mark.parametrize('heading', [
    'See our Fiscal 2025 Annual Report on Form 10-K.',
    'For fiscal 2025 we earned revenue.',
    'PART I\nFiscal 2025 Annual Report on Form 10-K',
    'x'*8192+'\nFiscal 2025 Annual Report on Form 10-K',
    'Fiscal 2025 Annual Report on Form 10-K/A',
    'Fiscal 2025 Annual Report on Form 10-K\nFiscal 2024 Annual Report on Form 10-K',
])
def test_missing_or_conflicting_heading_is_not_a_date_inference(heading):
    metadata, _ = source_metadata_details(source(heading))
    assert not metadata.get('fiscal_report_year')


def test_calendar_and_heading_conflict_cannot_be_refilled_by_another_parse():
    bundle = source('Fiscal 2025 Annual Report on Form 10-K', end='2026-12-31')
    bundle['text'] = bundle['text'].replace('January 30, 2026', 'December 31, 2026')
    metadata, proof = source_metadata_details(bundle)
    assert proof['fiscal_report_year']['status'] == 'conflict'
    alternate = {'original_filing_key':URL, 'calendar_annual_year':'2026', 'fiscal_report_year':'2025'}
    rows = resolve({'original':metadata, 'alternate':alternate})
    assert all(not row.get('calendar_annual_year') and not row.get('fiscal_report_year') for row in rows.values())


def test_heading_needs_own_cover_and_is_propagated_only_to_exact_original():
    bundle = source('Fiscal 2025 Annual Report on Form 10-K')
    bundle['text'] = bundle['text'].replace('SECURITIES AND EXCHANGE COMMISSION', 'Investor presentation')
    assert 'fiscal_report_year' not in source_metadata_details(bundle)[0]
    metadata, _ = source_metadata_details(source('Fiscal 2025 Annual Report on Form 10-K'))
    rows = resolve({'cover':metadata, 'same':{'original_filing_key':URL},
                    'annex':{'original_filing_key':URL.replace('report.htm', 'ex99.htm')}})
    assert rows['same']['fiscal_report_year'] == '2025'
    assert 'fiscal_report_year' not in rows['annex']


def test_cross_parse_calendar_and_explicit_label_conflict_is_unknown():
    rows = resolve({'a':{'original_filing_key':URL, 'calendar_annual_year':'2026'},
                    'b':{'original_filing_key':URL, 'fiscal_report_year':'2025'}})
    assert all(not row.get('calendar_annual_year') and not row.get('fiscal_report_year') for row in rows.values())


def test_reranker_receives_document_fiscal_label_without_changing_fact_period():
    from retrieval.rerank_document_context import with_document_context, document_context_text
    metadata, _ = source_metadata_details(source('Fiscal 2025 Annual Report on Form 10-K'))
    context = with_document_context([{'parent_document_id':'d'}], {'d':metadata})[0]['rerank_document_metadata']
    assert context['fiscal_report_year'] == '2025' and context['period_end'] == '2026-01-30'
    assert "NOT every fact's fiscal year" in document_context_text(context)
    for value in ('25', '２０２５', '2025-01-30', 'FY2025', '2100'):
        with pytest.raises(ValueError, match='invalid_fiscal_report_year'):
            document_context_text({'fiscal_report_year':value})
