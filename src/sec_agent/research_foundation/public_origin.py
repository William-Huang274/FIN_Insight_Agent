"""Bounded static-to-browser transport; version admission stays with discovery."""
import asyncio
import re
import time
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .external_sources import ExternalSourceError


def visible_text(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup.select('script,style,noscript,nav,header,footer'):
        tag.decompose()
    return soup.get_text(' ', strip=True)


def needs_render(html):
    """Only a thin scripted shell warrants a browser, not every undated page."""
    soup = BeautifulSoup(html, 'html.parser')
    return bool(soup.find('script') and len(visible_text(html)) < 500)


def observed_navigation(html, url, limit=12):
    """URLs only: undated titles/snippets must not leak through the date gate."""
    soup = BeautifulSoup(html, 'html.parser')
    links = {}
    for a in soup.select('a[href]'):
        target = urljoin(url, a['href']).split('#')[0]
        p = urlsplit(target)
        if (p.scheme != 'https' or not p.hostname or p.username or p.password
                or target == url or target in links):
            continue
        # Prefer document/help/pricing routes and article links over global
        # navigation. Use URL structure only, not undated link titles/snippets.
        rank = (0 if re.search(r'(?:docs?\.|/(?:docs?|help|support|pricing)(?:/|$)|billing|plans)',
                               p.hostname + p.path, re.I) else
                1 if a.find_parent(['main', 'article']) else 2)
        links[target] = rank
    # Navigation is selected by the model; never silently fetch every link.
    return [{'url': target, 'writer_citable': False, 'publication_date_inherited': False,
             'readback': {'tool': 'read_public_source', 'arguments': {
                 'operation': 'search', 'query': target}}}
            for target in sorted(links, key=links.get)[:limit]]


class PublicOriginFetcher:
    """One render attempt per fetch; no login, cookie import or CAPTCHA solver."""
    def __init__(self, static, browser):
        self.static, self.browser = static, browser
        self._slots = asyncio.Semaphore(2)

    async def fetch(self, url, *, timeout_seconds):
        started = time.monotonic()
        try:
            page = await self.static.fetch(url, timeout_seconds=timeout_seconds)
            if page.extracted_text is not None or not needs_render(page.html):
                return page
            failure = 'capture_dynamic_shell'
        except ExternalSourceError as exc:
            # Retrying a rate limit in a new browser does not respect its meaning.
            if exc.code not in {'capture_http_status_400', 'capture_http_status_403',
                                'capture_http_status_406', 'capture_access_challenge'}:
                raise
            failure = exc.code
        remaining = timeout_seconds - (time.monotonic() - started)
        if remaining < 1:
            raise ExternalSourceError(failure + ';browser:capture_browser_deadline')
        try:
            async with asyncio.timeout(remaining):
                async with self._slots:
                    page = await self.browser.fetch(url, timeout_seconds=remaining)
            if needs_render(page.html):
                raise ExternalSourceError('capture_browser_content_incomplete')
            return page.model_copy(update={'origin_failure_code': failure})
        except (ExternalSourceError, TimeoutError) as exc:
            raise ExternalSourceError(failure + ';browser:' +
                getattr(exc, 'code', 'capture_browser_timeout')) from exc
