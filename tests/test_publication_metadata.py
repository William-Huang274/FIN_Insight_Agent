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


def test_vitepress_native_lastupdated_is_modified_not_build_or_event_date():
    url='https://docs.example/product/pricing'
    html='''<html><head><meta name="generator" content="VitePress v2.0.0">
    <meta name="build-info" content="build 2027/01/01"></head><body><main><h1>Pricing</h1>
    <p>Current plan</p><footer class="VPDocFooter"><p class="VPLastUpdated">最后更新:
    <time datetime="2026-09-24T07:21:12.000Z"></time></p></footer></main></body></html>'''
    m=extract_publication_metadata(html,url=url)
    assert [(e.kind,e.day,e.syntax) for e in m.evidence] == [('modified',date(2026,9,24),'vitepress')]
    assert publisher_html_day(html,url=url) == date(2026,9,24)
    assert not extract_publication_metadata(html.replace('VPDocFooter','event'),url=url).evidence
    assert not extract_publication_metadata(html.replace('VitePress','Other'),url=url).evidence
    assert not extract_publication_metadata(html.replace('<head>','<head><link rel="canonical" href="https://docs.example/other">'),url=url).evidence
    assert publisher_html_day(html.replace('2026-09-24','2026-11-24'),url=url)>date(2026,11,9)
