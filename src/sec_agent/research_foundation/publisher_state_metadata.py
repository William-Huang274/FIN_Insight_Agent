"""Date identity adapters for publisher-owned hydration data, never JS execution."""
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, urljoin


def hydration_incomplete(html, url):
    """Compare the page-bound publisher plain body with visible rendered content.

    Uses the publisher's existing Next payload only to detect missing hydration;
    actual source text still comes from the maintained browser/HTML extractor.
    """
    from bs4 import BeautifulSoup
    if urlsplit(url).hostname != 'cloud.tencent.com':
        return False
    soup = BeautifulSoup(html, 'html.parser')
    nodes = soup.select('script#__NEXT_DATA__[type="application/json"]')
    if len(nodes) != 1:
        return False
    try:
        fallback = json.loads(nodes[0].get_text())['props']['pageProps']['fallback']
    except (ValueError, KeyError, TypeError):
        return False
    if not isinstance(fallback, dict):
        return False
    for node in soup.select('script,style,noscript'):
        node.decompose()
    visible = re.sub(r'\s+', '', soup.get_text())
    for record in fallback.values():
        article = record.get('articleInfo', {}) if isinstance(record, dict) else {}
        if str(article.get('articleId')) != urlsplit(url).path.rsplit('/', 1)[-1]:
            continue
        plain = re.sub(r'\s+', '', article.get('plain', ''))
        if len(plain) > 500 and (plain[:80] not in visible or plain[-80:] not in visible):
            return True
    return False


def publication_fields(soup, url, identity_aliases=()):
    """Yield kind, ISO/raw date, syntax, field for the exact current document."""
    if not url:
        return
    parsed = urlsplit(url)
    identities = [t.get('href') for t in soup.select('head link[rel="canonical"][href]')]
    identities += [t.get('content') for t in soup.select('head meta[property="og:url"]')]
    allowed = {url.split('#')[0], *identity_aliases}
    if any(urljoin(url, value).split('#')[0] not in allowed for value in identities if value):
        return

    def epoch(value, milliseconds=False):
        if type(value) not in (int, float) or value <= 0:
            return None
        try:
            return datetime.fromtimestamp(value / (1000 if milliseconds else 1), timezone.utc).isoformat()
        except (OverflowError, ValueError, OSError):
            return None

    headings = soup.select('h1')
    if (parsed.hostname == 'developer.aliyun.com'
            and re.fullmatch(r'/article/\d+', parsed.path) and len(headings) == 1):
        # Community articles expose a byline plus head metadata, not an
        # article landmark (the site's article element is a footer card).
        # Bind generic `date` to this byline before attributing it to the page.
        from .publication_metadata import explicit_day
        roots = soup.select('#article-detail')
        published = soup.select('head meta[name="date"][content]')
        modified = soup.select('head meta[name="last-modified"][content]')
        if len(roots) == 1 and headings[0] in roots[0].descendants:
            root = roots[0]
            stamps = root.select('.article-info .article-info-time')
            bodies = root.select('.article-content')
            if (len(stamps) == len(bodies) == len(published) == 1
                    and stamps[0] not in bodies[0].descendants
                    and bodies[0].get_text(strip=True)):
                day = explicit_day(published[0]['content'])
                if day and day == explicit_day(stamps[0].get_text(' ', strip=True)):
                    yield 'published', published[0]['content'], 'aliyun-community', 'article-info-time+meta.date'
                    if len(modified) == 1:
                        yield 'modified', modified[0]['content'], 'aliyun-community', 'meta.last-modified'
    if parsed.hostname == 'help.aliyun.com' and len(headings) == 1:
        # ICE state includes this page's alias, title, content and document version.
        # Ignore other state objects and timestamps belonging to recommendations.
        for script in soup.select('script'):
            match = re.search(r'(?:^|\n)\s*window\.__ICE_PAGE_PROPS__\s*=\s*', script.get_text())
            if not match:
                continue
            try:
                state, _ = json.JSONDecoder().raw_decode(script.get_text()[match.end():])
                store = state['docDetailData']['storeData']
                data = store['data']
            except (ValueError, KeyError, TypeError):
                continue
            if not isinstance(store, dict) or not isinstance(data, dict) or not isinstance(store.get('alias'), str):
                continue
            if (urlsplit(urljoin(url, store.get('alias', ''))).path != parsed.path.removeprefix('/zh')
                    or data.get('docTitle') != headings[0].get_text(' ', strip=True)
                    or not data.get('content')):
                continue
            stamp = epoch(data.get('lastModifiedTime'), milliseconds=True)
            if stamp:
                yield 'modified', stamp, 'aliyun-ice', 'docDetailData.storeData.data.lastModifiedTime'

    if parsed.hostname == 'cloud.tencent.com' and re.fullmatch(r'/developer/article/\d+', parsed.path) and len(headings) == 1:
        nodes = soup.select('script#__NEXT_DATA__[type="application/json"]')
        if len(nodes) == 1:
            try:
                state = json.loads(nodes[0].get_text())
                fallback = state['props']['pageProps']['fallback']
            except (ValueError, KeyError, TypeError):
                fallback = {}
            if not isinstance(fallback, dict):
                fallback = {}
            for record in fallback.values():
                if not isinstance(record, dict):
                    continue
                article = record.get('articleInfo', {})
                if (str(article.get('articleId')) != parsed.path.rsplit('/', 1)[-1]
                        or article.get('title') != headings[0].get_text(' ', strip=True)):
                    continue
                for field, kind in [('publishTime','published'), ('updateTime','modified')]:
                    stamp = epoch(record.get(field) if field == 'publishTime' else article.get(field))
                    if stamp:
                        yield kind, stamp, 'tencent-next', 'articleInfo.' + field

    if parsed.hostname in {'www.alibabacloud.com', 'alibabacloud.com'} and '/news/product/' in parsed.path:
        articles = soup.select('article')
        if len(articles) == 1:
            article = articles[0]
            title = article.select(':scope > h2.title')
            date = article.select(':scope > div.date > p')
            news = article.select(':scope > .fund-breadcrumb a[href]')
            if (len(title) == len(date) == 1 and article.select_one(':scope > .main')
                    and any(urlsplit(a['href']).path.endswith('/news/product') for a in news)):
                yield 'published', date[0].get_text(' ', strip=True), 'alicloud-product-news', 'article.header.date'
