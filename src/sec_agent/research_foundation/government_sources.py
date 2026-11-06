"""Thin routes to public institutions; no policy conclusions or case-specific URLs."""
import re
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


class GovernmentSourceFetcher:
    """ERCOT notice fallback through an existing metered fetch provider.

    The returned body must carry the exact notice ID and explicit notice dateline.
    A hosted transcription is labelled as such, never as a direct origin GET.
    Other documents/blocked APIs are not guessed or substituted.
    """
    def __init__(self, origin, hosted=None):
        self.origin, self.hosted = origin, hosted

    async def fetch(self, url, *, timeout_seconds):
        try:
            return await self.origin.fetch(url, timeout_seconds=timeout_seconds)
        except ExternalSourceError as exc:
            if not self.hosted or not ercot_notice_id(url) or exc.code not in {
                'capture_http_status_403', 'capture_http_status_429',
                'capture_static_timeout', 'capture_static_connection_failed',
            }:
                raise
            failure = exc.code
        text = await self.hosted.fetch_markdown(url)
        ident = ercot_notice_id(url)
        # Notice type is publisher metadata, not a passing mention in the body.
        if not re.search(r'(?m)^NOTICE TYPE:\s*' + re.escape(ident) + r'\b', text):
            raise ExternalSourceError('ercot_hosted_notice_identity_mismatch')
        from .dated_web_discovery import publisher_day
        if publisher_day(text) is None:
            raise ExternalSourceError('ercot_hosted_notice_date_unverified')
        return FetchedPage(final_url=url, extracted_text=text,
            extraction_method='deepseek_hosted_notice', content_type='text/markdown',
            origin_failure_code=failure)
