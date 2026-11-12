import asyncio
import json

from test_company_disclosures import request
from sec_agent.research_foundation.company_disclosures import CompanySources, issuer_match


def test_pbc_legal_suffix_does_not_hide_existing_ticker_directory_entry():
    row = dict(title='Example Research, PBC', ticker='EXR', cik_str=1234)
    assert issuer_match([row], 'Example Research S-1 2026') == row


def indexed(name, cik, filed='2026-10-26'):
    return {'_source': {'display_names': [name + ' (CIK ' + cik + ')'],
                        'ciks': [cik], 'file_date': filed}}


def discover(query, hits):
    client = CompanySources(None, None)
    seen = []
    async def get(url, timeout=10):
        seen.append(url)
        return json.dumps({'hits': {'hits': hits}})
    client.get = get
    result = asyncio.run(client.registration_issuer(request(query, '2026-11-12')))
    return result, seen


def test_non_ticker_registrant_is_identity_matched_not_keyword_mention():
    row, urls = discover('site:sec.gov Example Research S-1 2026', [
        indexed('Another Issuer Ltd', '1234'),
        indexed('Example Research, PBC', '2130357')])
    assert row['cik_str'] == '0002130357'
    assert row['ticker'] == 'CIK:0002130357'
    assert 'enddt=2026-11-12' in urls[0]
    assert 'q=Example+Research' in urls[0]


def test_multiple_issuers_or_future_index_hits_are_not_selected():
    row, _ = discover('Example Research S-1', [indexed('Example Research PBC', '1'),
                                              indexed('Example Research Ltd', '2')])
    assert row is None
    row, _ = discover('Example Research S-1', [indexed('Example Research PBC', '1', '2026-11-13')])
    assert row is None


def test_non_registration_query_does_not_add_a_network_lookup():
    row, urls = discover('Example Research earnings', [])
    assert row is None and urls == []


def test_unrelated_fulltext_hits_do_not_establish_company_identity():
    row, _ = discover('Example Research S-1', [indexed('Other Cloud PBC', '1')])
    assert row is None
