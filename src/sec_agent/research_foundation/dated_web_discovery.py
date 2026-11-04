"""Resolve the publication day before handing any ranked hit to a dated task."""
import asyncio
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


class DatedWebDiscovery:
    """Only admitted locators enter navigation, receipts and model input."""
    def __init__(self, discovery, fetcher):
        self.discovery = discovery
        self.fetcher = fetcher
        self.verified = {}

    async def search(self, request):
        receipt = await self.discovery.search(request)
        cutoff = request.run_scope.research_as_of.date()

        async def verify(candidate):
            url = candidate.canonical_url
            index = filing_index(url)
            locator = index or url
            try:
                if candidate.published_at:
                    try:
                        if date.fromisoformat(candidate.published_at[:10]) > cutoff:
                            return None
                    except ValueError:
                        pass  # Use the publisher lookup for an unusable provider date.
                if locator not in self.verified:
                    page = await self.fetcher.fetch(locator, timeout_seconds=15)
                    if page.final_url != locator:
                        return None
                    day = publisher_day(page.extracted_text or '',bool(index))
                    if day:
                        self.verified[locator] = day
                day = self.verified.get(locator)
            except (ExternalSourceError, ValueError, TimeoutError):
                return None
            if not day or day > cutoff:
                return None
            # The provider's search snippet may draw on other, newer content.
            return candidate.model_copy(update={'published_at':day.isoformat(),'snippet':''})

        admitted = [row for row in await asyncio.gather(*(verify(c) for c in receipt.candidates)) if row]
        body = receipt.model_dump(mode='json',exclude={'receipt_digest'})
        body['candidates'] = [row.model_dump(mode='json') for row in admitted]
        if not admitted and body['status'] == 'ok':
            body['status'] = 'zero_results'
        return DiscoveryReceipt(**body,receipt_digest=canonical_digest(body))
