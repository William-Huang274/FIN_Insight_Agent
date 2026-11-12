import json
from datetime import date

from sec_agent.research_foundation.publication_metadata import extract_publication_metadata, explicit_day
from sec_agent.research_foundation.dated_web_discovery import publisher_html_day


def test_headless_publisher_document_keeps_bound_jsonld_without_inventing_date():
    url='https://publisher.example/article'
    plain='<html><body><h1>Research release</h1><p>2026-11-11 is an event date.</p></body></html>'
    assert not extract_publication_metadata(plain,url=url).evidence
    graph={'@context':'https://schema.org','@type':'NewsArticle','url':url,'datePublished':'2026-06-01'}
    body=plain.replace('</body>','<script type="application/ld+json">'+json.dumps(graph)+'</script></body>')
    meta=extract_publication_metadata(body,url=url)
    assert [(e.kind,e.day,e.syntax) for e in meta.evidence]==[('published',date(2026,6,1),'json-ld')]
    assert not extract_publication_metadata(body,url='https://publisher.example/other').evidence


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


def test_explicit_cms_publication_field_does_not_adopt_search_or_event_date():
    url='https://publisher.example/release'
    html='''<html><head><meta property="og:url" content="https://publisher.example/release">
    <meta name="w_published_date" content="2026-10-22T00:00:00.000Z">
    <meta name="w_search_date" content="2027-01-01"></head><body><h1>Release</h1></body></html>'''
    assert publisher_html_day(html,url=url)==date(2026,10,22)
    assert publisher_html_day(html,url='https://publisher.example/other') is None
    assert not extract_publication_metadata(html.replace('w_published_date','eventDate'),url=url).evidence


def test_article_pubdate_preserves_identity_and_excludes_related_articles():
    url='https://publisher.example/post'
    html='''<html><head><title>Product release</title></head><body><main><article>
    <header><h1>Product release</h1><time pubdate datetime="2026-08-26">08.26.26</time></header>
    <p>Text</p><time datetime="2027-01-01">Event</time>
    <article><h2>Related</h2><time pubdate datetime="2026-11-05">Later article</time></article>
    </article></main></body></html>'''
    meta=extract_publication_metadata(html,url=url)
    assert [(e.kind,e.day,e.field) for e in meta.evidence]==[('published',date(2026,8,26),'time.pubdate')]
    assert publisher_html_day(html.replace('2026-08-26','2026-12-26'),url=url)>date(2026,11,9)
    assert not extract_publication_metadata(html.replace('<h1>Product release</h1>','<h2>Product release</h2>'),url=url).evidence
    assert not extract_publication_metadata(html.replace('<head>','<head><link rel="canonical" href="https://publisher.example/other">'),url=url).evidence
    assert not extract_publication_metadata(html.replace('<p>Text</p>','<time pubdate datetime="2026-09-01">Ambiguous</time>'),url=url).evidence


def test_preceding_press_release_dateline_excludes_event_body_and_wrong_identity():
    url = 'https://publisher.example/news/release'
    html = '''<html><head><title>Release</title></head><body><main><div>
    <p class="page-content__date">2026.03.04</p><h1>プレスリリース：企業導入</h1>
    <p>Event scheduled for 2027.01.01</p></div></main></body></html>'''
    meta = extract_publication_metadata(html, url=url)
    assert [(e.kind, e.day, e.field) for e in meta.evidence] == [
        ('published', date(2026,3,4), 'press_release.preceding_dateline')]
    assert publisher_html_day(html.replace('2026.03.04','2026.12.04'),url=url) > date(2026,11,12)
    for changed in [html.replace('プレスリリース：','Event: '),
                    html.replace('</p><h1>','</p><p>Other prose</p><h1>'),
                    html.replace('page-content__date','event'),
                    html.replace('<head>','<head><link rel="canonical" href="https://publisher.example/other">'),
                    html.replace('<head>','<head><meta property="og:url" content="https://publisher.example/other">')]:
        assert not extract_publication_metadata(changed,url=url).evidence


def test_news_detail_header_date_requires_news_navigation_and_local_label():
    url='https://publisher.example/jp/news/123/'
    html='''<html><head><title>Release</title></head><body><main>
    <div class="detail__head"><nav><a href="/jp/news/">News</a></nav><h1>Deployment</h1>
    <div><span>DATE :</span><span>2026.03.04</span></div></div><p>Event 2027.01.01</p></main></body></html>'''
    assert publisher_html_day(html,url=url)==date(2026,3,4)
    for changed in [html.replace('/jp/news/','/jp/events/'), html.replace('detail__head','detail__body'),
                    html.replace('DATE :','EVENT DATE :'), html.replace('<head>', '<head><meta property="og:url" content="https://publisher.example/other">')]:
        assert not extract_publication_metadata(changed,url=url).evidence
def test_q4_detail_dateline_is_bound_to_title_not_site_heading():
    from sec_agent.research_foundation.publication_metadata import extract_publication_metadata
    html = '''<html><head><title>Example Reports Results</title>
    <meta property="og:title" content="Example Reports Results"></head><body>
    <h1>Learn More</h1><div class="evergreen-news-details">
    <div class="evergreen-news-details-item">
    <div class="evergreen-news-headline"><h3 class="evergreen-news-title">Example Reports Results</h3></div>
    <div class="evergreen-news-date-time"><span class="evergreen-news-date-text">October 21, 2026</span></div>
    <div class="evergreen-news-body">Quarter ended September 30, 2026.</div>
    </div></div></body></html>'''
    def evidence(value):
        return [e for e in extract_publication_metadata(value, url='https://example.com/results').evidence
                if e.syntax == 'q4-evergreen']
    assert [e.day.isoformat() for e in evidence(html)] == ['2026-10-21']
    assert not evidence(html.replace('content="Example Reports Results"', 'content="News overview"'))
    assert not evidence(html.replace('class="evergreen-news-date-time"', 'class="body-quote"'))
    assert not evidence(html.replace('<body>', '<body><aside>').replace('</body>', '</aside></body>'))
