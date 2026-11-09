import asyncio
from datetime import datetime, date

import pytest

from connectors.sec_edgar_connector import SecEdgarConnector, SecEdgarConnectorError
from sec_agent.research_foundation.company_disclosures import (
    FilingSearch,
    Issuer,
    WebsiteSearch,
    issuer_match,
)
from sec_agent.research_foundation.external_sources import ProviderHit


def request(query, cutoff="2026-06-30"):
    from test_web_source_navigation import _run_scope, BRANCH
    from sec_agent.research_foundation.external_sources import ExternalSearchRequest

    scope = _run_scope(BRANCH)
    return ExternalSearchRequest(
        query=query,
        run_scope=scope,
        branch_id=scope.selected_branch_ids[0],
        purpose="issuer disclosures",
    ).model_copy(
        update={
            "run_scope": scope.model_copy(
                update={"research_as_of": datetime.fromisoformat(cutoff)}
            )
        }
    )


def fake_issuer():
    docs = {
        "form": ["10-Q", "8-K", "10-Q"],
        "filingDate": ["2026-07-31", "2026-04-23", "2026-04-23"],
        "reportDate": ["2026-06-30", "2026-04-22", "2026-03-31"],
        "items": ["", "2.02,9.01", ""],
        "accessionNumber": [
            "0000000001-26-000040",
            "0000000001-26-000021",
            "0000000001-26-000023",
        ],
        "primaryDocument": ["late.htm", "earn.htm", "first.htm"],
    }
    return Issuer(
        "EX",
        {"cik": 1, "fiscalYearEnd": "0930", "filings": {"recent": docs}},
        ["https://ir.example.com/"],
        "",
        None,
    )


def test_fiscal_quarter_and_exhibit_identity_checked_before_returning_sec_locators():
    class SEC:
        async def get(self, url):
            assert url.endswith("0000000001-26-000021-index.htm")
            return b'<table class="tableFile"><tr><td>1</td><td>release</td><td><a href="original.htm">link</a></td><td>EX-99.1</td></tr></table>'

    search = FilingSearch(fake_issuer(), SEC())
    hits = asyncio.run(search.search(request("EX fiscal second quarter 2026 results")))
    assert [h.url.split("/")[-1] for h in hits] == [
        "original.htm",
        "earn.htm",
        "first.htm",
    ]
    assert all(search.dates[h.url] == date(2026, 4, 23) for h in hits)
    assert not asyncio.run(search.search(request("EX Q2 2026 results", "2026-04-20")))
    assert [r[0] for r in fake_issuer().filings(request("EX fiscal Q2 2026 10-Q"))] == [
        "10-Q"
    ]


def test_domain_search_filters_third_party_even_if_engine_ignores_restriction():
    class Engine:
        provider_id = "test"

        async def search(self, req):
            assert req.include_domains == ("example.com",)
            return [
                ProviderHit(title="release", url=u)
                for u in (
                    "https://example.com.evil.org/release",
                    "https://ir.example.com/release",
                )
            ]

    hits = asyncio.run(
        WebsiteSearch(Engine(), ("example.com",)).search(
            request("EX quarterly earnings")
        )
    )
    assert [h.url for h in hits] == ["https://ir.example.com/release"]


def test_sec_identity_never_sent_to_nonsec_url_or_redirect():
    sec = SecEdgarConnector(user_agent="fixture", rate_limit=0)

    class Response:
        status_code = 302

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    class Session:
        def get(self, url, **kwargs):
            assert (
                url.startswith("https://www.sec.gov/")
                and kwargs["allow_redirects"] is False
            )
            return Response()

    sec.session = Session()
    for url, code in [
        ("https://www.sec.gov.evil.org/files/list", "sec_url_outside_contract"),
        ("https://www.sec.gov/files/list", "sec_http_302"),
    ]:
        with pytest.raises(SecEdgarConnectorError) as err:
            sec.read_public_resource(url, timeout=3)
        assert err.value.reason_code == code


def test_distinct_issuers_cannot_be_silently_resolved_to_one():
    rows = [
        dict(title="PulteGroup, Inc.", ticker="PHM", cik_str=1),
        dict(title="Lennar Corp", ticker="LEN", cik_str=2),
    ]
    assert issuer_match(rows, "PulteGroup一季度业绩")["ticker"] == "PHM"
    assert issuer_match(rows, "PulteGroup and Lennar earnings") is None


def test_ticker_topic_does_not_hijack_another_company_disclosure_search():
    rows = [dict(title='C3.ai, Inc.', ticker='AI', cik_str=1),
            dict(title='FactSet Research Systems Inc', ticker='FDS', cik_str=2)]
    for query in (
        'FactSet Q1 2026 earnings call transcript AI adoption renewals December 2025',
        'Cursor gross margin model costs negative 2026 AI coding startup unit economics',
        'AI coding industry gross margin',
    ):
        assert issuer_match(rows, query) is None
    for query in ('AI quarterly earnings', '$AI earnings', 'NYSE:AI earnings', 'C3.ai earnings'):
        assert issuer_match(rows, query) == rows[0]
    assert issuer_match(rows, 'FactSet Research Systems AI adoption quarterly earnings') == rows[1]
    assert issuer_match(rows, 'FactSet Research Systems versus $AI earnings') is None
    assert issuer_match(rows, 'FDS Q1 2026 earnings') == rows[1]


def test_known_alias_preserves_sec_row_identity_and_issuer_ambiguity():
    rows = [
        dict(title="HORTON D R INC /DE/", ticker="DHI", cik_str=882184),
        dict(title="Toll Brothers, Inc.", ticker="TOL", cik_str=794170),
    ]
    assert (
        issuer_match(rows, "D.R. Horton fiscal 2026 second quarter results") == rows[0]
    )
    assert issuer_match(rows, "D.R. Horton and Toll Brothers orders") is None


def test_sec_initials_jurisdiction_and_nested_names_preserve_actual_issuer():
    rows = [dict(cik_str=36104, ticker='USB', title='US BANCORP DE'),
            dict(cik_str=1295401, ticker='TBBK', title='Bancorp, Inc.')]
    for query in ('U.S. Bancorp third quarter 2026 earnings net interest margin provision',
                  'US Bancorp quarterly earnings', 'U S Bancorp results'):
        assert issuer_match(rows, query) == rows[0]
    assert issuer_match(rows, 'Bancorp, Inc. quarterly earnings') == rows[1]
    assert issuer_match(rows, 'U.S. Bancorp and Bancorp, Inc. quarterly earnings') is None
    assert issuer_match(rows, 'U.S. Bancorp versus $TBBK earnings') is None
    assert rows[0]['title'] == 'US BANCORP DE'


def test_nested_name_rule_is_span_based_not_global_longest_name_choice():
    rows = [dict(cik_str=1, ticker='HBC', title='Harbor Bank Corp'),
            dict(cik_str=2, ticker='NHB', title='Northern Harbor Bank Inc')]
    assert issuer_match(rows, 'Northern Harbor Bank earnings') == rows[1]
    assert issuer_match(rows, 'Northern Harbor Bank and Harbor Bank earnings') is None


def test_sec_tables_and_inline_numbers_survive_without_hidden_xbrl():
    from sec_agent.research_foundation.company_disclosures import edgar_text

    html = '<head><style>CSS</style></head><ix:header><ix:hidden>999</ix:hidden></ix:header><table><tr><td>Orders</td><td>8,<ix:nonfraction>034</ix:nonfraction></td></tr><tr><td>Gross margin</td><td>24.4%</td></tr></table><div style="display:none"><b style="display:none">other</b></div>'
    assert edgar_text(html).splitlines() == ["Orders 8,034", "Gross margin 24.4%"]


def test_declared_company_domains_need_a_dated_original_not_an_analyst_email():
    from sec_agent.research_foundation.company_disclosures import CompanySources

    company = Issuer("EX", {}, [], "", None)
    sources = CompanySources(None, None)
    filing = "https://www.sec.gov/Archives/edgar/data/1/annual.htm"
    sources.learn_websites(
        company,
        "Our corporate website, www.example.com, and our investor relations website, ir.example.com. Analyst: person@broker.com",
        filing,
    )
    assert company.roots == ["https://www.example.com/", "https://ir.example.com/"]
    assert company.evidence == dict.fromkeys(company.roots, filing)


def test_company_press_release_date_is_not_taken_from_an_unrelated_card():
    from sec_agent.research_foundation.dated_web_discovery import publisher_html_day

    label = '<div><span>Press release</span><span class="category__date">April 30, 2026</span></div>'
    assert publisher_html_day(label + "<h1>Results</h1>") == date(2026, 4, 30)
    assert publisher_html_day("<h1>Results</h1><footer>" + label + "</footer>") is None


def test_one_search_preserves_sec_and_ir_documents_and_never_promotes_a_blocked_site():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    from sec_agent.research_foundation.external_sources import (
        FetchedPage,
        ExternalSourceError,
        ExternalSourceDiscovery,
    )

    issuer = fake_issuer()

    class Sources:
        async def lookup(self, request):
            return issuer

        async def get(self, url):
            return b"<html/>"

        def learn_websites(self, *args):
            pass

    class Web:
        provider_id = "fixture_search"

        async def search(self, request):
            return [ProviderHit(title="IR release", url="https://ir.example.com/news")]

    class Origin:
        blocked = False

        async def fetch(self, url, **kwargs):
            if self.blocked and url.startswith("https://ir."):
                raise ExternalSourceError("capture_http_status_403")
            return FetchedPage(
                final_url=url, html="<h1>Results</h1><p>Published: April 23, 2026</p>"
            )

    def check(origin):
        reader, _, _ = _reader()
        reader.discovery = DatedWebDiscovery(
            ExternalSourceDiscovery(primary=Web()),
            None,
            origin_fetcher=origin,
            companies=Sources(),
        )
        return _call(reader, "search", query="EX fiscal second quarter 2026 earnings")

    origin = Origin()
    found = check(origin)
    assert set(x["source_url"].split("/")[2] for x in found.items) == {
        "www.sec.gov",
        "ir.example.com",
    }
    origin.blocked = True
    found = check(origin)
    assert all(
        x["source_url"].startswith("https://www.sec.gov/Archives") for x in found.items
    )
    attempts = found.execution_receipt.attempts
    assert attempts[-1]["date_filter_counts"] == {"origin_403": 1}
    assert attempts[-1]["issuer_navigation"]["websites"] == ["https://ir.example.com/"]


def test_syndicated_article_cannot_use_the_parent_sites_older_timestamp():
    from sec_agent.research_foundation.dated_web_discovery import publisher_html_day

    url = "https://example.org/business/article"
    html = """<head><meta property="og:url" content="https://example.org/contact"><meta property="article:modified_time" content="2025-08-14"></head>
    <article><script type="application/ld+json">{"mainEntityOfPage":{"@id":"https://example.org/business/article"},"datePublished":"2026-07-22T06:30:00-04:00"}</script><h1>Second quarter results</h1></article>"""
    assert publisher_html_day(html, url=url) == date(2026, 7, 22)
    assert publisher_html_day(html, url="https://example.org/another") is None


def test_call_transcript_search_reaches_web_even_after_sec_and_blocked_ir():
    from test_web_source_navigation import _reader, _call
    from sec_agent.research_foundation.dated_web_discovery import DatedWebDiscovery
    from sec_agent.research_foundation.external_sources import FetchedPage, ExternalSourceError, ExternalSourceDiscovery
    issuer = fake_issuer()
    class Sources:
        async def lookup(self, request): return issuer
        async def get(self, url): return b'<html/>'
        def learn_websites(self, *args): pass
    class Web:
        provider_id='fixture_search'
        def __init__(self): self.scopes=[]
        async def search(self, request):
            self.scopes.append(request.include_domains)
            url = 'https://ir.example.com/call' if request.include_domains else 'https://transcripts.example/call'
            return [ProviderHit(title='Earnings call transcript',url=url)]
    class Origin:
        async def fetch(self,url,**_):
            if url.startswith('https://ir.'): raise ExternalSourceError('capture_http_status_403')
            return FetchedPage(final_url=url,html='<head><meta name="date.posted" content="2026-04-23"></head><h1>Call transcript</h1>')
    web=Web();reader,_,_=_reader()
    reader.discovery=DatedWebDiscovery(ExternalSourceDiscovery(primary=web),None,origin_fetcher=Origin(),companies=Sources())
    found=_call(reader,'search',query='EX fiscal second quarter 2026 earnings call transcript')
    assert any(not scope for scope in web.scopes)
    assert any(x['source_url']=='https://transcripts.example/call' for x in found.items)
    assert any(x['source_url'].startswith('https://www.sec.gov/') for x in found.items)
