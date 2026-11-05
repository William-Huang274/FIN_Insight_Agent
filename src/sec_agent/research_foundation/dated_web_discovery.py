"""Resolve the publication day before handing any ranked hit to a dated task."""
import asyncio
from collections import Counter, OrderedDict
from datetime import date, datetime
import re
from urllib.parse import urljoin, urlsplit

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from .external_sources import (DiscoveryReceipt, ExternalSourceDiscovery, ExternalSourceError,
                               ProviderHit, PublicURLGuard, _host_in_domains)


def is_url_query(query):
    return query.lower().startswith(('http://', 'https://')) and not any(c.isspace() for c in query)


class PublicLocator:
    provider_id = 'direct_public_url'

    async def search(self, request):
        url = await asyncio.to_thread(PublicURLGuard().validate, request.query)
        return (ProviderHit(url=url, title=url),)


async def census_publication_page(candidate, fetcher, domains):
    """Return the separately dated catalog page, only if it links to this exact file."""
    from bs4 import BeautifulSoup
    parsed = urlsplit(candidate.canonical_url)
    match = re.fullmatch(r'/library/publications/(\d{4}/[^/]+/[\w-]+)\.pdf', parsed.path)
    if (parsed.hostname != 'www2.census.gov' or not match or parsed.query
            or (domains and not _host_in_domains('www.census.gov', domains))):
        return None
    url = f'https://www.census.gov/library/publications/{match[1]}.html'
    try:
        page = await fetcher.fetch(url, timeout_seconds=15)
        if page.final_url != url or not page.html:
            return None
        soup = BeautifulSoup(page.html, 'html.parser')
        if not any(urljoin(url, a['href']) == candidate.canonical_url for a in soup.select('a[href]')):
            return None
        day = publisher_html_day(page.html)
        title = soup.find('h1')
        if day and title:
            return candidate.model_copy(update={'canonical_url':url, 'source_domain':'www.census.gov',
                'title':title.get_text(' ', strip=True)[:512],
                'candidate_id':canonical_digest({'file_candidate':candidate.candidate_id,'publication_page':url})}), day
    except (ExternalSourceError, TimeoutError, ValueError):
        pass
    return None


# Release series published in the Department of Labor's economic-data archive.
_DOL_SERIES = {
    'cpi': 'Consumer Price Index', 'realer': 'Real Earnings',
    'empsit': 'Employment Situation', 'ppi': 'Producer Price Index',
    'eci': 'Employment Cost Index', 'prod2': 'Productivity and Costs',
    'ximpim': 'Import and Export Price Indexes',
}
_BLS_EMBARGO = re.compile(
    r'Transmission of material in this release is embargoed until\s+'
    r'(?:USDL-\s*\d{2}-\d+\s+)?\d{1,2}:\d{2}\s*[ap]\.m\.\s*\(ET\)\s+'
    r'(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
    r'([A-Za-z]+ \d{1,2}, \d{4})', re.I)


async def dol_archive_copy(candidate, fetcher, domains):
    url = urlsplit(candidate.canonical_url)
    if url.hostname != 'www.bls.gov' or (domains and not _host_in_domains('www.dol.gov', domains)):
        return None
    match = re.fullmatch(r'/news\.release/archives/([a-z0-9]+)_(\d{8})\.(?:htm|pdf)', url.path)
    if not match or match[1] not in _DOL_SERIES:
        return None
    series, stamp = match.groups()
    mirror = f'https://www.dol.gov/newsroom/economicdata/{series}_{stamp}.pdf'
    try:
        page = await fetcher.fetch(mirror, timeout_seconds=15)
        text = page.extracted_text or ''
        masthead = ' '.join(text[:1400].split())
        release = _BLS_EMBARGO.search(masthead)
        if (page.final_url != mirror or page.content_type != 'application/pdf' or not release
                or _DOL_SERIES[series].casefold() not in masthead.casefold()
                or 'bls.gov' not in masthead.lower()):
            return None
        day = publisher_day(text)
        if datetime.strptime(release[1], '%B %d, %Y').strftime('%m%d%Y') != stamp or day is None:
            return None
    except (ExternalSourceError, TimeoutError, ValueError):
        return None
    # The mirror has its own locator. Bind all subsequent navigation to the file actually read.
    fields = {'canonical_url': mirror, 'source_domain': 'www.dol.gov', 'title': _DOL_SERIES[series],
              'candidate_id': canonical_digest({'discovered_candidate': candidate.candidate_id, 'official_copy': mirror})}
    return candidate.model_copy(update=fields), day


def filing_index(url):
    parsed = urlsplit(url)
    if parsed.hostname not in {'sec.gov', 'www.sec.gov'}:
        return None
    match = re.fullmatch(r'/Archives/edgar/data/(\d+)/(\d{10})(\d{2})(\d{6})/[^/]+', parsed.path, re.I)
    if match:
        cik, filer, year, sequence = match.groups()
        accession = f'{filer}-{year}-{sequence}'
        return f'https://www.sec.gov/Archives/edgar/data/{cik}/{filer}{year}{sequence}/{accession}-index.htm'
    return None


def publisher_day(text, index=False):
    # Skip the fetch provider's own URL/Published header. Reporting period,
    # copyright and arbitrary dates embedded in narrative are not release dates.
    body = text.partition('\n\n')[2] if text.startswith('#') and '\nURL:' in text.partition('\n\n')[0] else text
    if index:
        match = re.search(r'\bFiling Date\s+(\d{4}-\d{2}-\d{2})\s+Accepted\b',body)
        return date.fromisoformat(match[1]) if match else None
    dates = set()
    release_label = (r'(?im)^\s*(?:last update(?:d)?\s*:|release date\s*:|'
                     r'embargoed until release[^\n]{0,80}?\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),)'
                     r'\s*([A-Za-z]{3,9} \d{1,2}, \d{4})\b')
    for value in re.findall(release_label, body) + _BLS_EMBARGO.findall(body[:1400]):
        for fmt in ('%B %d, %Y','%b %d, %Y'):
            try:
                dates.add(datetime.strptime(value,fmt).date())
                break
            except ValueError:
                continue
    dateline = (r'^(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),[ \t]+'
                r'|(?i:Published|Updated)(?: on)?[: ]+|[A-Z][A-Z .,]{1,40}, )'
                r'([A-Z][a-z]{2,8} \d{1,2}, \d{4})(?=[ \t]*$|[ \t]+[–—|]|[ \t]+/PRNewswire)')
    for match in re.finditer(dateline, body[:3200], re.MULTILINE | re.ASCII):
        for fmt in ('%B %d, %Y','%b %d, %Y'):
            try:
                dates.add(datetime.strptime(match[1],fmt).date())
                break
            except ValueError:
                continue
    return max(dates,default=None)


def publisher_html_day(html, index=False):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    day = publisher_day(soup.get_text('\n',strip=True), index)
    if index:
        return day
    dates = [day] if day else []
    for tag in soup.select('head meta[property="article:published_time"], head meta[property="article:modified_time"]'):
        try:
            dates.append(date.fromisoformat(tag.get('content','')[:10]))
        except ValueError:
            continue
    headings = soup.find_all('h1')
    if len(headings) == 1:
        heading = headings[0]
        label = heading.find_previous(string=lambda s:s and s.strip())
        after = heading.find_next_sibling()
        while after and not after.get_text(' ',strip=True):
            after = after.find_next_sibling()
        if label and label.strip().lower() in {'press release','news release'} and after and label.parent in heading.parent.descendants:
            try:
                dates.append(datetime.strptime(after.get_text(' ',strip=True), '%B %d, %Y').date())
            except ValueError:
                pass
    return max(dates,default=None)


def corroborated_dateline(markdown, html):
    """Require a hosted dateline to occur between the same heading and lede on the original."""
    from bs4 import BeautifulSoup
    heading = re.search(r'(?m)^# (.+)\n+([^\n]+)\n+([^\n]{32,})', markdown)
    if not heading:
        return None
    try:
        day = datetime.strptime(heading[2].strip(), '%B %d, %Y').date()
    except ValueError:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    label = ' '.join(heading[1].split())
    headings = soup.find_all('h1')
    if len(headings) != 1 or ' '.join(headings[0].stripped_strings) != label:
        return None
    start = ' '.join(heading[3].split())[:48]
    original = ' '.join(' '.join(soup.stripped_strings).split())
    return day if f'{label} {heading[2].strip()} {start}' in original else None


class SearchReadOrigin:
    """Keep a bounded window of exact successful origin GETs within this tool session.
    Discovery and capture see the same response; capture still validates and issues its own receipt."""
    def __init__(self, fetcher, *, max_bytes=8_000_000, max_entries=16):
        self.fetcher = fetcher
        self.max_bytes, self.max_entries = max_bytes, max_entries
        self.pages, self.used = OrderedDict(), 0

    async def fetch(self, url, *, timeout_seconds):
        if url in self.pages:
            self.pages.move_to_end(url)
            return self.pages[url][0]
        page = await self.fetcher.fetch(url, timeout_seconds=timeout_seconds)
        size = sum(len((v or '').encode()) for v in (page.html, page.extracted_text))
        if page.final_url == url and size and size <= self.max_bytes:
            previous = self.pages.pop(url, None)
            self.used += size - (previous[1] if previous else 0)
            self.pages[url] = (page, size)
            while self.used > self.max_bytes or len(self.pages) > self.max_entries:
                _, (_, evicted) = self.pages.popitem(last=False)
                self.used -= evicted
        return page


class DatedWebDiscovery:
    """Only admitted locators enter navigation, receipts and model input."""
    def __init__(self, discovery, fetcher, *, fallback_discovery=None, origin_fetcher=None, search_backup=None):
        self.discovery = discovery
        self.fetcher = fetcher
        self.fallback_discovery = fallback_discovery
        self.origin_fetcher = origin_fetcher
        self.search_backup = search_backup
        self.verified = {}

    async def search(self, request):
        cutoff = request.run_scope.research_as_of.date()
        direct = is_url_query(request.query)
        # For one unambiguous positive site filter, enforce it locally even
        # when a fallback engine ignores the search operator. Leave Boolean
        # and quoted expressions to the provider, not our own query parser.
        sites = re.findall(r'(?i)(?:^|\s)site:([a-z0-9.-]+)(?=\s|$)', request.query)
        if (len(sites) == 1 and not request.include_domains and not direct
                and not re.search(r'(?i)\bOR\b|["()|]', request.query)):
            request = request.model_copy(update={'include_domains':(sites[0].strip('.').lower(),)})

        async def verify(candidate):
            url = candidate.canonical_url
            if candidate.provider_id == 'deepseek_search':
                # An index title can change after the cutoff even for an old URL.
                candidate = candidate.model_copy(update={'title':url})
            index = filing_index(url)
            locator = index or url
            origin_failure = None
            origin_read = False
            try:
                if candidate.published_at:
                    try:
                        if date.fromisoformat(candidate.published_at[:10]) > cutoff:
                            return 'after_cutoff'
                    except ValueError:
                        pass  # Use the publisher lookup for an unusable provider date.
                if locator not in self.verified:
                    day = None
                    if self.origin_fetcher:
                        try:
                            page = await self.origin_fetcher.fetch(locator, timeout_seconds=15)
                            if page.final_url == locator:
                                origin_read = True
                                if candidate.provider_id == 'deepseek_search' and not index and page.html:
                                    from bs4 import BeautifulSoup
                                    title = BeautifulSoup(page.html, 'html.parser').find('h1')
                                    if title and title.get_text(strip=True):
                                        candidate = candidate.model_copy(update={'title':title.get_text(' ',strip=True)[:512]})
                                day = (publisher_day(page.extracted_text, bool(index)) if getattr(page, 'extracted_text', None)
                                       else publisher_html_day(page.html, bool(index)))
                                if (not day and self.search_backup and candidate.provider_rank == 1
                                        and candidate.provider_id == 'deepseek_search' and page.html and not index):
                                    try:
                                        markdown = await self.search_backup.primary.fetch_markdown(locator)
                                        day = corroborated_dateline(markdown, page.html)
                                    except ExternalSourceError:
                                        pass
                            else:
                                origin_failure = 'redirect'
                        except (ExternalSourceError, TimeoutError) as exc:
                            status = re.fullmatch(r'capture_http_status_(\d{3})', getattr(exc,'code',''))
                            origin_failure = f'origin_{status[1]}' if status else 'origin_unavailable'
                            if origin_failure == 'origin_403':
                                copy = await dol_archive_copy(candidate, self.origin_fetcher, request.include_domains)
                                if copy:
                                    candidate, day = copy
                                    locator = candidate.canonical_url
                    if day is None and self.origin_fetcher:
                        publication = await census_publication_page(candidate, self.origin_fetcher, request.include_domains)
                        if publication:
                            candidate, day = publication
                            locator = candidate.canonical_url
                    if day is None and direct:
                        return origin_failure or 'date_unverified'
                    if day is None:
                        page = await self.fetcher.fetch(locator, timeout_seconds=15)
                        if page.final_url != locator:
                            return 'redirect'
                        day = publisher_day(page.extracted_text or '',bool(index))
                    if day:
                        self.verified[locator] = day
                day = self.verified.get(locator)
            except (ExternalSourceError, ValueError, TimeoutError):
                return origin_failure or ('date_unverified' if origin_read else 'date_lookup_unavailable')
            if not day:
                return origin_failure or 'date_unverified'
            if day > cutoff:
                return 'after_cutoff'
            # The provider's search snippet may draw on other, newer content.
            return candidate.model_copy(update={'published_at':day.isoformat(),'snippet':''})

        attempts = []
        providers = (ExternalSourceDiscovery(primary=PublicLocator()),) if direct else (self.discovery, self.search_backup, self.fallback_discovery)
        for provider in providers:
            if provider is None:
                continue
            receipt = await provider.search(request)
            checked = await asyncio.gather(*(verify(c) for c in receipt.candidates))
            admitted = [row for row in checked if not isinstance(row, str)]
            admitted = list({row.canonical_url: row for row in admitted}.values())
            for attempt in receipt.attempted_providers:
                counts = Counter(result if isinstance(result,str) else 'admitted'
                                 for candidate,result in zip(receipt.candidates,checked)
                                 if candidate.provider_id == attempt.provider_id)
                attempts.append(attempt.model_copy(update={'date_filter_counts':dict(counts)}) if counts else attempt)
            if admitted:
                break
        body = receipt.model_dump(mode='json',exclude={'receipt_digest'})
        body['attempted_providers'] = [row.model_dump(mode='json') for row in attempts]
        body['candidates'] = [row.model_dump(mode='json') for row in admitted]
        if not admitted and body['status'] == 'ok':
            body['status'] = 'zero_results'
        return DiscoveryReceipt(**body,receipt_digest=canonical_digest(body))
