"""Resolve the publication day before handing any ranked hit to a dated task."""
import asyncio
from collections import Counter
from datetime import date, datetime
import re
from urllib.parse import urlsplit

from sec_agent.research.reviewed_evidence_pack import canonical_digest
from .external_sources import DiscoveryReceipt, ExternalSourceError


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
    for value in re.findall(release_label, body):
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


class DatedWebDiscovery:
    """Only admitted locators enter navigation, receipts and model input."""
    def __init__(self, discovery, fetcher, *, fallback_discovery=None, origin_fetcher=None):
        self.discovery = discovery
        self.fetcher = fetcher
        self.fallback_discovery = fallback_discovery
        self.origin_fetcher = origin_fetcher
        self.verified = {}

    async def search(self, request):
        cutoff = request.run_scope.research_as_of.date()

        async def verify(candidate):
            url = candidate.canonical_url
            index = filing_index(url)
            locator = index or url
            origin_failure = None
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
                                day = publisher_html_day(page.html,bool(index))
                        except (ExternalSourceError, TimeoutError) as exc:
                            origin_failure = 'origin_403' if getattr(exc,'code','') == 'capture_http_status_403' else 'origin_unavailable'
                    if day is None:
                        page = await self.fetcher.fetch(locator, timeout_seconds=15)
                        if page.final_url != locator:
                            return 'redirect'
                        day = publisher_day(page.extracted_text or '',bool(index))
                    if day:
                        self.verified[locator] = day
                day = self.verified.get(locator)
            except (ExternalSourceError, ValueError, TimeoutError):
                return origin_failure or 'date_lookup_unavailable'
            if not day:
                return origin_failure or 'date_unverified'
            if day > cutoff:
                return 'after_cutoff'
            # The provider's search snippet may draw on other, newer content.
            return candidate.model_copy(update={'published_at':day.isoformat(),'snippet':''})

        attempts = []
        for provider in (self.discovery, self.fallback_discovery):
            if provider is None:
                break
            receipt = await provider.search(request)
            checked = await asyncio.gather(*(verify(c) for c in receipt.candidates))
            admitted = [row for row in checked if not isinstance(row, str)]
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
