"""Native HTML metadata extraction with FIN publication/version attribution.

Candidates from htmldate are diagnostic, not proof of historical availability.
Never pass the research cutoff to a date extractor: doing so can hide an update.
"""
from dataclasses import dataclass
from datetime import date
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class DateEvidence:
    kind: str
    day: date
    raw: str
    syntax: str
    field: str
    identity: str | None


@dataclass(frozen=True)
class PublicationMetadata:
    title: str | None
    candidate_day: str | None
    evidence: tuple[DateEvidence, ...]

    @property
    def version_day(self):
        return max((e.day for e in self.evidence), default=None)


def explicit_day(value):
    """Parse a complete publisher field; never fill a missing date from today."""
    if not isinstance(value, str) or len(value) > 160:
        return None
    import dateparser
    parsed = dateparser.parse(value, settings={
        'STRICT_PARSING': True, 'REQUIRE_PARTS': ['year', 'month', 'day'],
        'PARSERS': ['absolute-time'], 'RETURN_AS_TIMEZONE_AWARE': False,
    })
    return parsed.date() if parsed else None


def extract_publication_metadata(html, *, url=None):
    # Trafilatura uses htmldate natively. Its broad candidate is retained separately
    # from attributed evidence; no URL fetch is permitted through this interface.
    import extruct
    from lxml.html import document_fromstring
    from trafilatura.metadata import extract_metadata
    native = extract_metadata(html, default_url=url, extensive=False,
        date_config={'extensive_search': False, 'original_date': True})
    # extruct's OpenGraph reader requires document.head. Valid body-only HTML
    # (including fragments returned by publishers) has no such element. Keep
    # JSON-LD/microdata extraction, but do not invent a head or a publication date.
    tree = document_fromstring(html)
    syntaxes = ['json-ld', 'microdata']
    if tree.head is not None:
        syntaxes.append('opengraph')
    structured = extruct.extract(tree, base_url=url or '', syntaxes=syntaxes, uniform=True)
    evidence = []

    def same_page(identity):
        return bool(url and isinstance(identity, str)
                    and urljoin(url, identity).split('#')[0] == url.split('#')[0])

    def values(value):
        return value if isinstance(value, list) else [value]

    def add(kind, value, syntax, field, identity):
        for raw in values(value):
            day = explicit_day(raw)
            if day:
                item = DateEvidence(kind, day, raw, syntax, field, identity)
                if item not in evidence:
                    evidence.append(item)

    def nodes(value):
        # extruct parses the syntax. Only graph members are peers; do not promote
        # dates from nested related articles, publishers or events to this page.
        for node in values(value):
            if isinstance(node, dict):
                yield node
                if '@graph' in node:
                    yield from nodes(node['@graph'])

    for syntax in ('json-ld', 'microdata'):
        for node in nodes(structured.get(syntax, [])):
            identities = values(node.get('mainEntityOfPage', node.get('url')))
            identities = [v.get('@id') if isinstance(v, dict) else v for v in identities]
            if not identities or not all(same_page(v) for v in identities):
                continue
            for field, kind in (('datePublished', 'published'), ('dateModified', 'modified')):
                add(kind, node.get(field), syntax, field, identities[0])

    for node in structured.get('opengraph', []):
        identities = values(node.get('og:url'))
        if url and node.get('og:url') and not all(same_page(v) for v in identities):
            continue
        for field, kind in (('article:published_time', 'published'), ('article:modified_time', 'modified')):
            add(kind, node.get(field), 'opengraph', field, url)

    # Explicit publisher header semantics absent from the three structured
    # formats. Generic dc.date / date / archival and event dates stay candidates.
    soup = BeautifulSoup(html, 'html.parser')
    og_urls = [t.get('content') for t in soup.select('head meta[property="og:url"]')]
    if not url or not og_urls or all(same_page(v) for v in og_urls):
        fields = {'date.posted': 'published', 'datepublished': 'published',
                  'pubdate': 'published', 'publishdate': 'published',
                  'w_published_date': 'published',
                  'dcterms.issued': 'published', 'dc.date.issued': 'published',
                  'datemodified': 'modified', 'dcterms.modified': 'modified',
                  'dc.date.modified': 'modified'}
        for tag in soup.select('head meta[name][content]'):
            field = tag['name'].casefold()
            if field in fields:
                add(fields[field], tag['content'], 'meta', field, url)
        # HTML's explicit pubdate attribute belongs to the nearest article.
        # Require that article to contain the page's sole h1; recommendation
        # cards and ordinary event time elements cannot date the current page.
        headings = soup.find_all('h1')
        canonical = soup.select('head link[rel="canonical"][href]')
        # A consensus publication has a dated edition heading before its table.
        # This is snapshot/edition metadata, not a date in the forecast rows.
        # Do not borrow dates from arbitrary headings, related articles or events.
        if (len(headings) == 1 and re.fullmatch(r'(?:Analyst\s+)?Consensus|一致预期', headings[0].get_text(' ', strip=True), re.I)
                and all(same_page(t['href']) for t in canonical)):
            first = headings[0].find_next(['h2', 'table', 'article'])
            if first and first.name == 'h2':
                text = first.get_text(' ', strip=True)
                match = re.fullmatch(r'[^\n]{0,80}\bconsensus\s*[-–—:]\s*(.{8,40})', text, re.I)
                if match:
                    add('modified', match[1], 'html', 'consensus.edition_heading', url)
        if len(headings) == 1 and all(same_page(t['href']) for t in canonical):
            # Documentation footer's explicitly labelled update time. Attribute
            # only a short metadata container, never an event/body date or quote.
            for stamp in soup.select('time[datetime]'):
                parent = stamp.parent
                label = parent.get_text(' ', strip=True)
                if (not parent.find_parent(['blockquote', 'aside', 'nav'])
                        and any(re.match(r'(?i)^update[-_]?time(?:[-_]|$)', c)
                                for c in parent.get('class', []))
                        and len(label) < 100
                        and re.match(r'^(?:更新时间|最后更新|Last updated)\s*[:：]', label, re.I)
                        and len(parent.select('time')) == 1):
                    add('modified', stamp['datetime'], 'html', 'document_footer.updated', url)
            # A news-detail header labels DATE beside CATEGORY, separate from
            # the article prose. Require the publisher's news-index breadcrumb
            # and an explicit header container, not an arbitrary event date.
            header = headings[0].parent
            news_links = [a for a in header.select('nav a[href]')
                          if re.search(r'/(?:news|press)/?$', a['href'])]
            if (news_links and (header.name == 'header' or any(
                    re.search(r'(?:^|[-_])head(?:er)?$', c, re.I) for c in header.get('class', [])))
                    and len(header.get_text(' ', strip=True)) < 700):
                labels = header.find_all(string=re.compile(r'^\s*DATE\s*:\s*$', re.I))
                if len(labels) == 1:
                    stamp = labels[0].parent.find_next_sibling()
                    if stamp and not stamp.find(['a','p','div']):
                        add('published', stamp.get_text(' ', strip=True), 'html',
                            'news_header.labelled_date', url)
            # A labelled press-release title can have its publication dateline
            # immediately before it (common in Japanese publisher mastheads).
            # Attribute only that sibling, never another date in the article.
            heading = headings[0]
            previous = heading.find_previous_sibling()
            if (re.match(r'^(?:Press Release\s*[:：]|プレスリリース\s*[:：]|新闻稿\s*[:：])',
                         heading.get_text(' ', strip=True), re.I)
                    and previous is not None and previous.name in {'p', 'time'}
                    and any(re.search(r'(?:^|[-_])date$', c, re.I) for c in previous.get('class', []))
                    and not previous.find(['a', 'time', 'p'])):
                add('published', previous.get_text(' ', strip=True), 'html',
                    'press_release.preceding_dateline', url)
            article = headings[0].find_parent('article')
            stamps = [t for t in article.select('time[pubdate][datetime]')
                      if t.find_parent('article') is article] if article else []
            if len(stamps) == 1:
                add('published', stamps[0]['datetime'], 'html', 'time.pubdate', url)
        # VitePress owns this page-level lastUpdated component. Its empty time
        # element is populated in the browser; datetime is the native contract.
        # Do not infer publication from the site build timestamp or any time tag.
        generator = soup.select_one('head meta[name="generator"]')
        canonical = soup.select('head link[rel="canonical"][href]')
        if (generator and generator.get('content', '').startswith('VitePress ')
                and all(same_page(t['href']) for t in canonical)):
            stamps = soup.select('.VPDocFooter .VPLastUpdated time[datetime]')
            if len(stamps) == 1:
                add('modified', stamps[0]['datetime'], 'vitepress', 'lastUpdated', url)
    return PublicationMetadata(native.title if native else None,
                               native.date if native else None, tuple(evidence))
