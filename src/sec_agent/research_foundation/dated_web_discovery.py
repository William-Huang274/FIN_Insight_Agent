"""Resolve the publication day before handing any ranked hit to a dated task."""
import asyncio
import json
from collections import Counter, OrderedDict
from datetime import date, datetime
import re
from urllib.parse import urljoin, urlsplit, parse_qsl

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from .external_sources import (DiscoveryReceipt, ExternalSourceDiscovery, ExternalSourceError,
                               ProviderHit, PublicURLGuard, _host_in_domains)


def is_url_query(query):
    return query.lower().startswith(('http://', 'https://')) and not any(c.isspace() for c in query)


def filtered_publication_catalog(url):
    """Drupal faceted collection queries identify a listing, not a dated release."""
    return any(re.fullmatch(r'f\[\d+\]', key) and re.match(r'facet_[a-z_]+:', value)
               for key,value in parse_qsl(urlsplit(url).query))


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
    r'Transmission of material in this (?:news )?release is embargoed until\s+'
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


def publisher_day(text, index=False, *, pdf=False):
    # Skip the fetch provider's own URL/Published header. Reporting period,
    # copyright and arbitrary dates embedded in narrative are not release dates.
    body = text.partition('\n\n')[2] if text.startswith('#') and '\nURL:' in text.partition('\n\n')[0] else text
    if index:
        match = re.search(r'\bFiling Date\s+(\d{4}-\d{2}-\d{2})\s+Accepted\b',body)
        return date.fromisoformat(match[1]) if match else None
    dates = set()
    release_label = (r'(?im)^\s*(?:last update(?:d)?\s*:|release date\s*:|notice date\s*:|'
                     r'embargoed until release[^\n]{0,80}?\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),)'
                     r'\s*([A-Za-z]{3,9} \d{1,2}, \d{4})\b')
    masthead_dates = []
    if pdf:
        # A monthly report label followed by a separate full dateline in the
        # masthead. Dates in data tables and the survey month alone do not qualify.
        masthead_dates = re.findall(
            r'(?im)^[ \t]*[A-Z][a-z]{2,8} 20\d{2} survey results[ \t]+'
            r'([A-Z][a-z]{2,8} \d{1,2}, 20\d{2})[ \t]*$', body[:600])
        # Document issue metadata in the cover/header, distinct from dates
        # mentioned in findings, effective dates or the observation period.
        masthead_dates += re.findall(
            r'(?im)^[ \t]*Date:[ \t]*([A-Z][a-z]{2,8} \d{1,2}, 20\d{2})[ \t]*$', body[:1200])
        if re.search(r'(?m)^FROM:',body[:1000]) and re.search(r'(?m)^SUBJECT:',body[:1000]):
            masthead_dates += re.findall(
                r'(?m)^[ \t]*([A-Z][a-z]{2,8} \d{1,2}, 20\d{2})[ \t]*\n[ \t]*MEMORANDUM (?:FOR|TO)\b', body[:1000])
    for value in re.findall(release_label, body) + _BLS_EMBARGO.findall(body[:1400]) + masthead_dates:
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


def publisher_markdown_day(text):
    """Explicit transcription masthead, not a search date or narrative date."""
    day = publisher_day(text)
    lines = [s.strip() for s in text[:600].splitlines() if s.strip()]
    # Image placeholders carry no prose and may sit between a release heading
    # and its dateline in a hosted transcription. Never skip arbitrary text.
    lines = [s for s in lines if s != 'Image' and not re.fullmatch(r'!\[[^\]]*\]\([^\n]+\)', s)]
    if len(lines) < 2:
        return day
    # Publishers put the dateline immediately before or after the article title.
    stamp = lines[0] if lines[1].startswith('# ') else lines[1] if lines[0].startswith('# ') else ''
    stamp = re.sub(r'(\d)(?:st|nd|rd|th)\b', r'\1', stamp)
    for fmt in ('%B %d, %Y', '%b %d, %Y'):
        try:
            parsed = datetime.strptime(stamp, fmt).date()
            return max(day,parsed) if day else parsed
        except ValueError:
            continue
    return day


def publisher_html_day(html, index=False, *, url=None):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    day = publisher_day(soup.get_text('\n',strip=True), index)
    if index:
        return day
    dates = [day] if day else []
    # Explicit document modification metadata (e.g. Plone), not the copyright
    # year or a date mentioned by the article. Preserve the newer-version gate.
    for stamp in soup.select('.contentModifiedDate'):
        parent = stamp.parent
        if parent and re.fullmatch(r'Last Modified\s+\d{4}-\d{2}-\d{2}', parent.get_text(' ',strip=True), re.I):
            try:
                dates.append(date.fromisoformat(stamp.get_text(strip=True)))
            except ValueError:
                pass
    # A release masthead may follow a nested heading rather than be its sibling.
    # Require a single h1, a short labelled metadata element and no prose between.
    main = soup.find('main')
    if main and len(main.find_all('h1')) == 1:
        h1 = main.find('h1')
        stamp = h1.find_next(['p', 'time'])
        if stamp and stamp in main.descendants:
            value = ' '.join(stamp.stripped_strings)
            # Publisher-labelled publication time before the article body.
            # Exclude listing cards, event dates and unrelated footer times;
            # the visible date must agree with the machine-readable date.
            publication = stamp.find_parent(class_=re.compile(r'^(?:published|publication-date|published-date)$', re.I))
            if (stamp.name == 'time' and publication and publication in main.descendants
                    and len(main.select('time[datetime]')) == 1
                    and len(publication.get_text(' ', strip=True)) < 180):
                try:
                    declared = date.fromisoformat(stamp.get('datetime', '')[:10])
                    printed = datetime.strptime(value, '%B %d, %Y').date()
                    if declared == printed:
                        dates.append(declared)
                except ValueError:
                    pass
            if len(value) < 180 and re.search(r'\bPress Release\b', value, re.I):
                match = re.fullmatch(r'([A-Za-z]+ \d{1,2}, \d{4})\s*\|[^|]{1,60}\|\s*Press Release', value, re.I)
                if match:
                    try:
                        dates.append(datetime.strptime(match[1], '%B %d, %Y').date())
                    except ValueError:
                        pass
    def same_page(value):
        return isinstance(value,str) and urljoin(url,value).split('#')[0] == url.split('#')[0]
    if url:
        # Schema.org microdata is equivalent to JSON-LD, but properties belong
        # to their nearest itemscope. A related article's date must not qualify
        # the current page; require its own exact mainEntityOfPage identity.
        for article in soup.select('[itemscope][itemtype]'):
            kinds = article.get('itemtype', '').split()
            if not any(re.fullmatch(r'https?://schema.org/(?:Article|NewsArticle|Report)', k) for k in kinds):
                continue
            props = [p for p in article.select('[itemprop]') if p.find_parent(attrs={'itemscope':True}) is article]
            identities = [p.get('href') or p.get('content') for p in props
                          if 'mainEntityOfPage' in p.get('itemprop','').split()]
            if not identities or not all(same_page(value) for value in identities):
                continue
            for prop in props:
                if not set(prop.get('itemprop','').split()) & {'datePublished','dateModified'}:
                    continue
                try:
                    dates.append(date.fromisoformat((prop.get('content') or prop.get('datetime') or '')[:10]))
                except ValueError:
                    continue
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                raw = json.loads(script.string or '')
            except (ValueError,RecursionError):
                continue
            nodes = raw if isinstance(raw,list) else [raw]
            for node in nodes:
                if not isinstance(node,dict):
                    continue
                identity = node.get('mainEntityOfPage',node.get('url'))
                if isinstance(identity,dict):
                    identity=identity.get('@id')
                if not same_page(identity):
                    continue
                for key in ('datePublished','dateModified'):
                    try:
                        dates.append(date.fromisoformat(str(node.get(key))[:10]))
                    except ValueError:
                        continue
    og_url = soup.select_one('head meta[property="og:url"]')
    if not url or not og_url or same_page(og_url.get('content')):
        for tag in soup.select('head meta[property="article:published_time"], head meta[property="article:modified_time"]'):
            try:
                dates.append(date.fromisoformat(tag.get('content','')[:10]))
            except ValueError:
                continue
    # A press-release label and its dateline in the same masthead, not a
    # timestamp from navigation, related articles or a search snippet.
    for label in soup.find_all(string=re.compile(r'^\s*press release\s*$', re.I)):
        masthead = label.parent.parent
        if not masthead or len(masthead.get_text(' ',strip=True)) > 220:
            continue
        headings_nearby = soup.find_all('h1')
        if len(headings_nearby) != 1 or masthead.find_next('h1') is not headings_nearby[0]:
            continue
        stamp = masthead.find(['time','span','div'],class_=re.compile(r'date',re.I))
        if stamp:
            for fmt in ('%B %d, %Y','%b %d, %Y','%m/%d/%Y'):
                try:
                    dates.append(datetime.strptime(stamp.get_text(' ',strip=True),fmt).date())
                    break
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


def publisher_canonical_url(html, url):
    """Follow a publisher-declared query-free locator, never strip query fields by guess."""
    from bs4 import BeautifulSoup
    parsed = urlsplit(url)
    if not parsed.query:
        return None
    links = BeautifulSoup(html, 'html.parser').select('head link[rel="canonical"][href]')
    targets = {urljoin(url, link['href']) for link in links}
    if len(targets) != 1:
        return None
    target = targets.pop()
    other = urlsplit(target)
    if (other.scheme == parsed.scheme == 'https' and other.netloc == parsed.netloc
            and other.path == parsed.path and not other.query and not other.fragment):
        return target
    return None


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
    def __init__(self, discovery, fetcher, *, fallback_discovery=None, origin_fetcher=None, search_backup=None, companies=None, legislation=None):
        self.discovery = discovery
        self.fetcher = fetcher
        self.fallback_discovery = fallback_discovery
        self.origin_fetcher = origin_fetcher
        self.companies = companies
        self.search_backup = search_backup
        self.verified = {}
        from .legislation_discovery import LegislationDiscovery
        self.legislation = legislation or LegislationDiscovery()

    async def search(self, request):
        cutoff = request.run_scope.research_as_of.date()
        direct = is_url_query(request.query)
        # For one unambiguous positive site filter, enforce it locally even
        # when a fallback engine ignores the search operator. Leave Boolean
        # and quoted expressions to the provider, not our own query parser.
        sites = re.findall(r'(?i)(?:^|\s)site:([a-z0-9.-]+(?:/[^\s"()|]*)?)(?=\s|$)', request.query)
        site_path = None
        if (len(sites) == 1 and not request.include_domains and not direct
                and not re.search(r'(?i)\bOR\b|[()|]', request.query)):
            scope = urlsplit('https://' + sites[0])
            request = request.model_copy(update={'include_domains':(scope.hostname.strip('.').lower(),)})
            site_path = scope.path.rstrip('/') or None

        filing_source = None
        issuer = None if direct or not self.companies else await self.companies.lookup(request)
        legislation_navigation = {}
        verification_failures = {}
        def failed(candidate, stage, exc):
            counts = verification_failures.setdefault(candidate.provider_id, Counter())
            counts[stage + ':' + getattr(exc, 'code', type(exc).__name__)] += 1
        async def verify(candidate, visited=()):
            url = candidate.canonical_url
            parsed = urlsplit(url)
            if request.include_domains and not _host_in_domains(parsed.hostname or '', request.include_domains):
                return 'outside_requested_domains'
            if site_path and not (parsed.path == site_path or parsed.path.startswith(site_path+'/')):
                return 'outside_requested_path'
            if filtered_publication_catalog(url):
                return 'publisher_directory_not_dated_document'
            if url in visited or len(visited) >= 6:
                return 'publisher_navigation_cycle'
            visited = (*visited, url)
            navigation = await self.legislation.resolve(url, cutoff)
            if navigation is not None:
                if isinstance(navigation, dict):
                    legislation_navigation[url] = navigation
                    return 'official_api_navigation_available'
                return navigation
            if candidate.provider_id == 'deepseek_search':
                # An index title can change after the cutoff even for an old URL.
                candidate = candidate.model_copy(update={'title':url})
            if candidate.provider_id == 'sec_edgar_filings':
                # SEC submissions binds this accession to its public filing day;
                # the index binds exhibits to the exact accession directory.
                day = filing_source.dates[url]
                if day > cutoff:
                    return 'after_cutoff'
                try:
                    page = await self.origin_fetcher.fetch(url, timeout_seconds=12)
                except (ExternalSourceError, TimeoutError) as exc:
                    return getattr(exc, 'code', 'sec_origin_unavailable')
                if page.final_url != url or not (page.extracted_text or page.html).strip():
                    return 'sec_original_unavailable'
                if page.html and ('EX-99' in candidate.title or (not issuer.roots and any(f in candidate.title for f in ('10-K', '20-F', '40-F')))):
                    self.companies.learn_websites(issuer,page.html,url)
                return candidate.model_copy(update={'published_at':day.isoformat(),'snippet':''})
            index = filing_index(url)
            from .government_publications import bill_package, resolve_bill
            if bill_package(url) and self.origin_fetcher:
                try:
                    resolved, day = await resolve_bill(candidate, self.origin_fetcher)
                    return resolved if day <= cutoff else 'after_cutoff'
                except ExternalSourceError as exc:
                    return exc.code
            from .public_posts import post_locator
            if post_locator(url) and self.origin_fetcher:
                # The embed response binds the exact post ID, author and version.
                # Do not replace unavailable/late original text with hosted snippets.
                try:
                    page = await self.origin_fetcher.fetch(url, timeout_seconds=15)
                    if page.extraction_method != 'x_public_embed':
                        return 'x_original_not_verified'
                    # The body may discuss future dates; only adapter metadata
                    # identifies the publication/edit version of this exact post.
                    day = publisher_html_day(page.html.partition('</head>')[0] + '</head></html>', url=url)
                    if not day:
                        return 'date_unverified'
                    if day > cutoff:
                        return 'after_cutoff'
                    return candidate.model_copy(update={'published_at': day.isoformat(), 'snippet':'',
                                                       'title': url})
                except ExternalSourceError as exc:
                    return exc.code
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
                                canonical = publisher_canonical_url(page.html, locator) if page.html and not index else None
                                if canonical:
                                    # Fetch and date the declared page independently. Keep a
                                    # distinct candidate identity for its actual citation URL.
                                    return await verify(candidate.model_copy(update={
                                        'canonical_url':canonical,
                                        'candidate_id':canonical_digest({'original_candidate':candidate.candidate_id,
                                            'publisher_canonical_url':canonical})}), visited)
                                origin_read = True
                                if candidate.provider_id == 'deepseek_search' and not index and page.html:
                                    from bs4 import BeautifulSoup
                                    title = BeautifulSoup(page.html, 'html.parser').find('h1')
                                    if title and title.get_text(strip=True):
                                        candidate = candidate.model_copy(update={'title':title.get_text(' ',strip=True)[:512]})
                                day = (publisher_markdown_day(page.extracted_text) if getattr(page,'extraction_method',None)=='deepseek_hosted_publication' else
                                       publisher_day(page.extracted_text, bool(index), pdf=getattr(page, 'content_type', None) == 'application/pdf') if getattr(page, 'extracted_text', None)
                                       else publisher_html_day(page.html, bool(index), url=locator))
                                if (not day and self.search_backup and candidate.provider_rank == 1
                                        and candidate.provider_id == 'deepseek_search' and page.html and not index):
                                    try:
                                        markdown = await self.search_backup.primary.fetch_markdown(locator)
                                        day = corroborated_dateline(markdown, page.html)
                                    except ExternalSourceError as exc:
                                        failed(candidate, 'deepseek_fetch', exc)
                            else:
                                # The guarded HTTP reader followed a real redirect. Date
                                # the resulting original under its own identity; retain
                                # explicit site scope instead of treating all redirects
                                # as unresolvable publication dates.
                                host = urlsplit(page.final_url).hostname or ''
                                if request.include_domains and not _host_in_domains(host, request.include_domains):
                                    return 'redirect_outside_requested_domains'
                                return await verify(candidate.model_copy(update={
                                    'canonical_url':page.final_url, 'source_domain':host,
                                    'candidate_id':canonical_digest({'original_candidate':candidate.candidate_id,
                                        'publisher_redirect_url':page.final_url})}), visited)
                        except (ExternalSourceError, TimeoutError) as exc:
                            failed(candidate, 'original_read', exc)
                            status = re.fullmatch(r'(?:capture_http_status_|sec_http_)(\d{3})', getattr(exc,'code',''))
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
                    if day is None and (direct or self.fetcher is None):
                        return origin_failure or 'date_unverified'
                    if day is None:
                        page = await self.fetcher.fetch(locator, timeout_seconds=15)
                        if page.final_url != locator:
                            return 'redirect'
                        day = publisher_day(page.extracted_text or '',bool(index))
                    if day:
                        self.verified[locator] = day
                day = self.verified.get(locator)
            except (ExternalSourceError, ValueError, TimeoutError) as exc:
                failed(candidate, 'date_verification', exc)
                return origin_failure or ('date_unverified' if origin_read else 'date_lookup_unavailable')
            if not day:
                return origin_failure or 'date_unverified'
            if day > cutoff:
                return 'after_cutoff'
            # The provider's search snippet may draw on other, newer content.
            return candidate.model_copy(update={'published_at':day.isoformat(),'snippet':''})

        attempts = []
        providers = (ExternalSourceDiscovery(primary=PublicLocator()),) if direct else (self.discovery, self.search_backup, self.fallback_discovery)
        if not direct and self.origin_fetcher:
            from .publisher_catalogs import CatalogSearch, PublisherCatalog
            catalog = PublisherCatalog.match(request)
            if catalog:
                providers = (ExternalSourceDiscovery(primary=CatalogSearch(catalog, self.origin_fetcher)), *providers)
        sites = ()
        saved_filings = []
        if issuer:
            from .company_disclosures import FilingSearch, WebsiteSearch, _WEB
            domains = issuer.domains
            if request.include_domains:
                domains = tuple(h for h in request.include_domains if _host_in_domains(h, issuer.domains))
            sites = tuple(ExternalSourceDiscovery(primary=WebsiteSearch(p.primary,domains))
                          for p in providers if p is not None and domains)
            filings = ()
            if not request.include_domains or _host_in_domains('www.sec.gov',request.include_domains):
                filing_source = FilingSearch(issuer,self.companies)
                filings = (ExternalSourceDiscovery(primary=filing_source),)
            if _WEB.search(request.query):
                # A website request must reach a web search even when EDGAR has a filing.
                providers = ((*sites, *filings, *providers) if sites else (*providers, *filings))
            else:
                providers = (*filings, *sites, *providers)
        for provider in providers:
            if saved_filings and provider not in sites:
                admitted = saved_filings
                break
            if provider is None:
                continue
            verification_failures.clear()
            receipt = await provider.search(request)
            checked = await asyncio.gather(*(verify(c) for c in receipt.candidates))
            admitted = [row for row in checked if not isinstance(row, str)]
            admitted = list({row.canonical_url: row for row in admitted}.values())
            for attempt in receipt.attempted_providers:
                counts = Counter(result if isinstance(result,str) else 'admitted'
                                 for candidate,result in zip(receipt.candidates,checked)
                                 if candidate.provider_id == attempt.provider_id)
                update = {'date_filter_counts':dict(counts)} if counts else {}
                unresolved = [{'url':c.canonical_url, 'reason':out,
                    'writer_citable':False, 'content_withheld':True,
                    'publisher_search':{'tool':'read_public_source','arguments':{
                        'operation':'search','query':request.query
                            if not direct else 'site:'+(urlsplit(c.canonical_url).hostname or '')+' '+urlsplit(c.canonical_url).path.split('/')[-1]}}}
                    for c,out in zip(receipt.candidates,checked)
                    if c.provider_id == attempt.provider_id and out in (
                        'date_unverified','date_lookup_unavailable','origin_403','origin_404','origin_unavailable',
                        'redirect_outside_requested_domains','publisher_navigation_cycle','publisher_directory_not_dated_document')]
                if unresolved:
                    update['unresolved_originals'] = unresolved
                if verification_failures.get(attempt.provider_id):
                    update['verification_failures'] = dict(verification_failures[attempt.provider_id])
                navigation = [legislation_navigation[c.canonical_url] for c in receipt.candidates
                              if c.provider_id == attempt.provider_id and c.canonical_url in legislation_navigation]
                if navigation:
                    update['legislation_navigation'] = navigation
                if issuer:
                    update['issuer_navigation'] = {
                        'ticker':issuer.ticker, 'websites':list(issuer.roots),
                        'website_role':'navigation_only', 'website_provenance':dict(issuer.evidence), 'official_website_query':(request.query if _WEB.search(request.query) else request.query+' official website'),
                        'filing_attempts':(filing_source.failures if attempt.provider_id == 'sec_edgar_filings' else []),
                    }
                    # A strict issuer-site query stays strict. Expose a usable
                    # alternative query rather than silently ignoring its domain.
                    if request.include_domains and not _host_in_domains('www.sec.gov', request.include_domains):
                        update['issuer_navigation']['regulatory_readback'] = {
                            'tool':'read_public_source',
                            'arguments':{'operation':'search', 'query':issuer.ticker + ' ' + re.sub(r'(?i)(?:^|\s)site:[a-z0-9.-]+', '', request.query).strip()},
                            'meaning':'Separate company-disclosure search including SEC forms and exhibits; original website failure remains recorded.'}
                    if attempt.provider_id == 'sec_edgar_filings':
                        update['issuer_navigation']['filing_documents'] = filing_source.documents
                        update['issuer_navigation']['filing_indexes'] = filing_source.indexes
                        update['issuer_navigation']['filing_attempts'] = [
                            *filing_source.failures, *({'url':c.canonical_url,'stage':'filing_body','reason':out}
                            for c,out in zip(receipt.candidates,checked) if isinstance(out,str) and out != 'after_cutoff')]
                attempts.append(attempt.model_copy(update=update) if update else attempt)
            if admitted and sites and provider.primary is filing_source and not _WEB.search(request.query):
                # Keep filings even if the IR site rejects the read. Try one active
                # domain search so a readable company release can sit alongside EDGAR.
                saved_filings = admitted
                continue
            if saved_filings and receipt.attempted_providers:
                combined = [saved_filings[0], *admitted[:1], *saved_filings[1:], *admitted[1:]]
                admitted = list({c.canonical_url:c for c in combined}.values())[:request.max_results]
                break
            if admitted or legislation_navigation:
                break
        body = receipt.model_dump(mode='json',exclude={'receipt_digest'})
        body['attempted_providers'] = [row.model_dump(mode='json') for row in attempts]
        body['candidates'] = [row.model_dump(mode='json') for row in admitted]
        if admitted:
            body['status'] = 'ok'
        elif body['status'] == 'ok':
            body['status'] = 'zero_results'
        return DiscoveryReceipt(**body,receipt_digest=canonical_digest(body))
