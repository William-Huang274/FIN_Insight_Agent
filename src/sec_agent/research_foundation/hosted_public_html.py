"""Optional maintained Reader transport for public HTML; no date admission."""
import asyncio
import os

import httpx

from .external_sources import ExternalSourceError, FetchedPage, PublicURLGuard
from .public_network import http_options


class HostedPublicHTML:
    def __init__(self, origin, *, guard=None):
        self.origin = origin
        self.guard = guard or PublicURLGuard()

    async def fetch(self, url, *, timeout_seconds):
        try:
            return await self.origin.fetch(url, timeout_seconds=timeout_seconds)
        except ExternalSourceError as exc:
            failure = exc.code
            if os.environ.get('FIN_PUBLIC_READER_FALLBACK') != 'jina' or not any(
                code in failure for code in ('capture_http_status_403',
                    'capture_http_status_406', 'capture_access_challenge',
                    'capture_browser_content_incomplete')
            ):
                raise
        # Only public destinations, no inherited cookies, authorization or paid
        # key. Both service HTTP and upstream HTTP status must succeed.
        target = await asyncio.to_thread(self.guard.validate, url)
        try:
            async with httpx.AsyncClient(**http_options(), timeout=timeout_seconds) as client:
                async with client.stream('GET', 'https://r.jina.ai/' + target,
                        headers={'Accept': 'application/json', 'X-Respond-With': 'html'}) as response:
                    if response.status_code != 200:
                        raise ExternalSourceError('reader_http_status_' + str(response.status_code))
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > 5_000_000:
                            raise ExternalSourceError('reader_response_too_large')
            import json
            data = json.loads(body)['data']
            if data.get('url') != target or data.get('httpStatus') != 200:
                raise ExternalSourceError('reader_origin_status_or_identity_invalid')
            final = await asyncio.to_thread(self.guard.validate, data.get('finalUrl') or target)
            html = data.get('html')
            if not isinstance(html, str) or not html.strip():
                raise ExternalSourceError('reader_html_missing')
            return FetchedPage(final_url=final, html=html, status_code=200,
                extraction_method='hosted_reader_html', origin_failure_code=failure)
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            raise ExternalSourceError('reader_transport_or_response_invalid') from exc
