"""Locate named survey editions in their publisher's public catalog.
Catalog HTML may contain newer releases. Only original, date-checked documents
are exposed to the caller. No release dates, document IDs or conclusions are configured.
"""
import asyncio
import calendar
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from .external_sources import ExternalSourceError, ProviderHit, _host_in_domains


_MONTHS = {calendar.month_name[n].lower(): n for n in range(1, 13)}
_MONTH_PATTERN = '|'.join(_MONTHS)
_SCF = r'(?:survey of consumer finances|消费者财务调查|家庭财务调查|\bscf\b)'


@dataclass(frozen=True)
class PublisherCatalog:
    provider_id: str
    host: str
    year: int
    month: int = 0
    stage: str = ''

    @classmethod
    def match(cls, request):
        query = request.query.casefold()
        cutoff = request.run_scope.research_as_of.date()
        if ('michigan' in query or '密歇根' in query) and re.search(
                r'consumer sentiment|surveys? of consumers|消费者信心|消费者调查', query):
            en = re.findall(rf'\b({_MONTH_PATTERN})\s+(20\d{{2}})\b', query)
            zh = re.findall(r'(20\d{2})\s*年\s*(1[0-2]|0?[1-9])\s*月', query)
            periods = {(int(y), _MONTHS[m]) for m, y in en} | {(int(y), int(m)) for y, m in zh}
            if len(periods) != 1:
                return None
            year, month = periods.pop()
            prelim = bool(re.search(r'prelim|初值', query))
            final = bool(re.search(r'final|终值', query))
            # Don't silently select one version when a comparison is requested.
            if prelim and final:
                return None
            route = cls('michigan_survey_catalog', 'data.sca.isr.umich.edu', year, month, 'Preliminary' if prelim else 'Final' if final else '')
        elif ('federal reserve' in query or '美联储' in query) and re.search(_SCF, query):
            # Bind the requested survey edition, not the year it might be released.
            match = re.search(rf'{_SCF}\s*[(（]?\s*(20\d{{2}})\b', query) or re.search(
                rf'(20\d{{2}})\s*(?:年|edition of the)?\s*{_SCF}', query)
            if not match:
                return None
            route = cls('fed_scf_release_catalog', 'www.federalreserve.gov', int(match[1]))
        else:
            return None
        if route.year > cutoff.year or (request.include_domains and not _host_in_domains(route.host, request.include_domains)):
            return None
        return route


class CatalogSearch:
    def __init__(self, catalog, origin):
        self.catalog = catalog
        self.provider_id = catalog.provider_id
        self.origin = origin

    async def _index(self, url):
        page = await self.origin.fetch(url, timeout_seconds=15)
        if page.final_url != url or not page.html:
            raise ExternalSourceError('publisher_catalog_identity_unverified')
        return BeautifulSoup(page.html, 'html.parser')

    async def search(self, request):
        cat = self.catalog
        if cat.month:
            url = f'https://{cat.host}/reports.php?year={cat.year}'
            soup = await self._index(url)
            if not soup.find(string=re.compile(rf'^\s*{cat.year} Reports\s*$')):
                raise ExternalSourceError('publisher_catalog_edition_unverified')
            month = calendar.month_name[cat.month]
            labels = [f'{month} {stage} Results' for stage in ((cat.stage,) if cat.stage else ('Final','Preliminary'))]
            hits = []
            for link in soup.select('a[href]'):
                label = ' '.join(link.stripped_strings)
                if label not in labels:
                    continue
                target = urljoin(url, link['href'])
                parsed = urlsplit(target)
                if (parsed.hostname == cat.host and parsed.path == '/fetchdoc.php'
                        and re.fullmatch(r'docid=\d+', parsed.query)):
                    hits.append(ProviderHit(url=target, title=f'{label} ({cat.year})'))
            return sorted(hits,key=lambda hit: 'Final Results' not in hit.title)

        cutoff = request.run_scope.research_as_of.date()
        # The survey launch and results can be published in different years.
        # SCF is triennial; inspect the edition year and subsequent year.
        years = range(cat.year, min(cat.year + 1, cutoff.year) + 1)
        async def year_hits(year):
            url = f'https://{cat.host}/newsevents/pressreleases/{year}-press.htm'
            soup = await self._index(url)
            hits = []
            for link in soup.select('.eventlist__event a[href]'):
                title = ' '.join(link.stripped_strings)
                if not re.search(rf'\b{cat.year} Survey of Consumer Finances\b', title, re.I):
                    continue
                row = link.find_parent('div', class_='row')
                stamp = row.find('time') if row else None
                if not stamp:
                    continue
                try:
                    day = datetime.strptime(stamp.get_text(strip=True), '%m/%d/%Y').date()
                except ValueError:
                    continue
                target = urljoin(url, link['href'])
                if day <= cutoff and urlsplit(target).hostname == cat.host:
                    hits.append(ProviderHit(title=title,url=target,published_at=day.isoformat()))
            return hits
        pages = await asyncio.gather(*(year_hits(y) for y in years),return_exceptions=True)
        hits = [h for page in pages if isinstance(page,list) for h in page]
        if any(isinstance(page,Exception) for page in pages):
            raise ExternalSourceError('publisher_catalog_lookup_incomplete')
        return sorted(hits, key=lambda h:h.published_at, reverse=True)
