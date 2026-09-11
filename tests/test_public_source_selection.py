import pytest
from scripts.data_retrieval.expand_case_source_library import selected_public_sources, public_source_parser


def source(**updates):
    return dict({'url': 'https://example.com/disclosure', 'publication_date': '2026-07-29',
                 'title': 'Quarterly results', 'publisher': 'Issuer IR', 'issuer_id': 'issuer',
                 'company': 'Issuer', 'source_role': 'issuer_earnings_release',
                 'document_kind': 'html'}, **updates)


def test_time_boundary_deduplication_and_source_authority_are_preserved():
    item = source()
    result = selected_public_sources({'sources': [item, item, source(url='https://example.com/future', publication_date='2026-09-12')]}, '2026-09-11')
    assert result == [item]
    assert result[0]['source_role'] == 'issuer_earnings_release'


@pytest.mark.parametrize('updates', [{'publication_date': 'yesterday'}, {'url': 'http://example.com/a'},
    {'url': 'https://user:secret@example.com/a'}, {'publisher': ''}, {'document_kind': 'exe'}])
def test_invalid_source_metadata_is_rejected(updates):
    with pytest.raises(ValueError):
        selected_public_sources({'sources': [source(**updates)]}, '2026-09-11')


def test_sec_6k_uses_filing_parser_instead_of_article_extractor():
    assert public_source_parser(source(url='https://www.sec.gov/Archives/edgar/data/1/report.htm')) == 'sec2md_filing'
    assert public_source_parser(source(url='https://www.sec.gov.evil.test/Archives/edgar/data/1/report.htm')) == 'trafilatura_xml'
    assert public_source_parser(source(document_kind='pdf')) == 'pypdf_pages'
