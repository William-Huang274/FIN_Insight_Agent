import json
from datetime import date

from sec_agent.research_foundation.publication_metadata import extract_publication_metadata, explicit_day
from sec_agent.research_foundation.dated_web_discovery import publisher_html_day


def test_native_graph_extraction_keeps_attribution_and_newer_version():
    url = 'https://publisher.example/article'
    graph = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'NewsArticle', 'mainEntityOfPage': {'@id': url},
         'datePublished': '2026-06-01', 'dateModified': '2026-07-02'},
        {'@type': 'NewsArticle', 'url': 'https://publisher.example/related',
         'datePublished': '2027-02-01'}]}
    html = '<html><head><title>Release</title><script type="application/ld+json">'+json.dumps(graph)+'</script></head><body><h1>Release</h1></body></html>'
    result = extract_publication_metadata(html, url=url)
    assert [(e.kind, e.day, e.identity) for e in result.evidence] == [
        ('published', date(2026,6,1), url), ('modified', date(2026,7,2), url)]
    assert result.version_day == date(2026,7,2)
    assert publisher_html_day(html, url=url) > date(2026,6,30)
    assert publisher_html_day(html, url=url) <= date(2026,7,2)
    assert result.title == 'Release'
    assert result.evidence[0].syntax == 'json-ld'


def test_native_date_candidate_is_not_publication_evidence():
    html = '<html><head><meta name="dc.date" content="2026-06-01"></head><body><h1>Release</h1><p>Meeting on July 2, 2026.</p></body></html>'
    result = extract_publication_metadata(html, url='https://example.com/2026/06/01/release')
    assert result.candidate_day == '2026-06-01'
    assert not result.evidence and result.version_day is None
    for value in ['June 2026', 'June 1', 'yesterday', '', 'invalid']:
        assert explicit_day(value) is None


def test_header_semantics_and_open_graph_identity_are_separate():
    html = '<html><head><meta name="dcterms.issued" content="2026-06-01"><meta name="dcterms.modified" content="2026-07-02"></head><body>Text</body></html>'
    assert publisher_html_day(html, url='https://example.com/a') == date(2026,7,2)
    assert publisher_html_day(html.replace('<head>', '<head><meta property="og:url" content="https://example.com/b">'),url='https://example.com/a') is None
    assert publisher_html_day(html.replace('dcterms.issued','eventDate').replace('dcterms.modified','date.archived')) is None
