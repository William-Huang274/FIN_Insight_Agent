"""Thin routes to public institutions; no policy conclusions or case-specific URLs."""
import re
from datetime import datetime
from urllib.parse import urlsplit

from .external_sources import ExternalSourceError, FetchedPage


def official_search_entries(query):
    """Offer scoped discovery, without silently replacing the author's question."""
    routes = (
        (r'\btceq\b|得州环境质量|德州环境质量', 'tceq.texas.gov'),
        (r'\bercot\b|得州电网|德州电网', 'ercot.com'),
        (r'white house|白宫', 'whitehouse.gov'),
        (r'\babbott\b|texas governor|得州州长|德州州长', 'gov.texas.gov'),
    )
    if re.search(r'(?i)(?:^|\s)site:|^https?://', query):
        return []
    return [{'domain': domain, 'tool': 'read_public_source',
             'arguments': {'operation': 'search', 'query': query + ' site:' + domain},
             'role': 'official_site_discovery_not_evidence'}
            for pattern, domain in routes if re.search(pattern, query, re.I)]


def ercot_notice_id(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname != 'www.ercot.com' or parsed.query or parsed.fragment:
        return None
    match = re.fullmatch(r'/services/comm/mkt_notices/(M-[A-Z]\d{6}-\d{2})', parsed.path)
    return match[1] if match else None


def dated_bill_catalog(url, text, cutoff):
    """Expose dated version rows, not an undated current bill summary."""
    parsed = urlsplit(url)
    bill = re.fullmatch(r'/bills/([a-z]{1,3}\d{2,4}-\d+)',parsed.path,re.I)
    if not bill or not (parsed.hostname or '').endswith('.gov'):
        return None
    ident = bill[1].upper()
    if not re.match(re.escape(ident)+r'\s*\n',text,re.I):
        return None
    table = re.search(r'(?m)^### Bill Text\s*\n\s*Date\s*\|\s*Version\s*\|\s*Documents\s*\n[-| ]+\n((?:[^\n]+\n?)+)',text)
    if not table:
        return None
    rows=[]
    for line in table[1].splitlines():
        cells=[v.strip() for v in line.split('|')]
        if len(cells)<2:
            continue
        try:day=datetime.strptime(cells[0],'%m/%d/%Y').date()
        except ValueError:continue
        if day>cutoff:continue
        rows.append({'version_date':day.isoformat(),'version_label':cells[1],
            'read_entry':{'tool':'read_public_source','arguments':{'operation':'search',
                'query':f'site:{parsed.hostname} "{ident}" "{cells[1]}"'}}})
    if not rows:
        return None
    return {'kind':'official_bill_version_catalog','catalog_url':url,'bill_id':ident,
        'versions':rows,'writer_citable':False,'current_summary_withheld':True,
        'meaning':'Observed dated document-version rows only. Locate and read the selected text; current summary has no verified publication date.'}


class GovernmentSourceFetcher:
    """Government publication fallback through the existing metered Fetch provider.

    ERCOT notices must carry the exact notice ID and explicit notice dateline.
    A hosted transcription is labelled as such, never as a direct origin GET.
    Government URL transcriptions retain their weaker transport provenance;
    publication-date admission is still separate. No alternate URL is guessed.
    """
    def __init__(self, origin, hosted=None):
        self.origin, self.hosted = origin, hosted

    async def fetch(self, url, *, timeout_seconds):
        try:
            page = await self.origin.fetch(url, timeout_seconds=timeout_seconds)
            if not (page.html or page.extracted_text or '').strip():
                raise ExternalSourceError('capture_empty_response')
            return page
        except ExternalSourceError as exc:
            host = urlsplit(url).hostname or ''
            government = host.endswith('.gov')
            if not self.hosted or not (ercot_notice_id(url) or government) or exc.code not in {
                'capture_http_status_403', 'capture_http_status_406', 'capture_http_status_429',
                'capture_static_timeout', 'capture_static_connection_failed', 'capture_empty_response',
            }:
                raise
            failure = exc.code
        text = await self.hosted.fetch_markdown(url)
        ident = ercot_notice_id(url)
        if not ident:
            # The provider is an exact-URL transcription transport, not a direct
            # origin response. Never claim original bytes or archive provenance.
            if not text.strip():
                raise ExternalSourceError('government_hosted_empty_response')
            return FetchedPage(final_url=url, extracted_text=text,
                extraction_method='deepseek_hosted_publication', content_type='text/markdown',
                origin_failure_code=failure)
        # Notice type is publisher metadata, not a passing mention in the body.
        if not re.search(r'(?m)^NOTICE TYPE:\s*' + re.escape(ident) + r'\b', text):
            raise ExternalSourceError('ercot_hosted_notice_identity_mismatch')
        from .dated_web_discovery import publisher_day
        if publisher_day(text) is None:
            raise ExternalSourceError('ercot_hosted_notice_date_unverified')
        return FetchedPage(final_url=url, extracted_text=text,
            extraction_method='deepseek_hosted_notice', content_type='text/markdown',
            origin_failure_code=failure)
