"""Thin discovery adapter to a maintained SearXNG service.

Engine parsing/ranking belongs to SearXNG. FIN still verifies publication dates,
reads originals and binds citations through the existing discovery/capture path.
"""
from __future__ import annotations

import os
import re
from typing import Literal
from urllib.parse import urlsplit

import httpx

from .external_sources import ExternalSourceError, ProviderHit, _engine_http

SearchBackend = Literal['auto', 'bing', 'bing_china', 'baidu', 'github', 'bilibili']
ENGINES = {'bing': 'bing', 'bing_china': 'bing china', 'baidu': 'baidu',
           'github': 'github', 'bilibili': 'bilibili'}


def search_availability():
    """Deployment health overrides, not a claim that configured engines work."""
    disabled = set(os.environ.get('FIN_SEARCH_DISABLED_BACKENDS', '').split(','))
    return {'disabled_backends': [name for name in ENGINES if name in disabled],
            'reason': os.environ.get('FIN_SEARCH_DISABLED_REASON', 'deployment_health_check_failed'),
            'alternative': {'tool': 'read_public_source',
                            'arguments': {'operation': 'search', 'search_backend': 'auto'},
                            'instruction': 'Keep your original query; auto skips disabled engines. '
                                           'This is a retrieval fault, not evidence that information is absent.'}}


class SearxNGProvider:
    provider_id = 'searxng'

    def __init__(self, endpoint: str | None = None, *, transport=None):
        self.endpoint = (endpoint or os.environ.get('FIN_SEARXNG_URL', '')).rstrip('/')
        self.transport = transport
        if self.endpoint:
            parsed = urlsplit(self.endpoint)
            if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.query or parsed.fragment or parsed.username:
                raise ValueError('searxng_endpoint_invalid')

    async def search(self, request):
        if not self.endpoint:
            raise ExternalSourceError('searxng_not_configured')
        backend = getattr(request, 'search_backend', 'auto')
        availability = search_availability()
        disabled = set(availability['disabled_backends'])
        selected = [backend] if backend != 'auto' else ['bing', 'bing_china']
        enabled = [name for name in selected if name not in disabled]
        if not enabled:
            observed = _engine_http.get()
            if observed is not None:
                for name in selected:
                    observed['searxng:' + ENGINES[name]] = 'disabled: ' + availability['reason'][:120]
            raise ExternalSourceError('searxng_selected_engines_disabled_use_auto_or_other_backend')
        # Baidu is explicitly selectable, never silently added to the default.
        engines = ','.join(ENGINES[name] for name in enabled)
        language = getattr(request, 'search_language', None) or ('zh-CN' if backend in {'bing_china', 'baidu', 'bilibili'} else 'all')
        try:
            async with httpx.AsyncClient(timeout=30, transport=self.transport, follow_redirects=False) as client:
                response = await client.get(self.endpoint + '/search', params={
                    'q': request.query, 'engines': engines, 'language': language,
                    'format': 'json', 'safesearch': 1})
            if response.status_code != 200:
                raise ExternalSourceError(f'searxng_http_{response.status_code}')
            data = response.json()
            if not isinstance(data, dict) or not isinstance(data.get('results'), list):
                raise ExternalSourceError('searxng_invalid_response')
        except httpx.TimeoutException as exc:
            raise ExternalSourceError('searxng_timeout') from exc
        except httpx.HTTPError as exc:
            raise ExternalSourceError('searxng_transport_error') from exc
        except ValueError as exc:
            raise ExternalSourceError('searxng_invalid_response') from exc
        observed = _engine_http.get()
        failures = data.get('unresponsive_engines') or []
        if observed is not None:
            for name, *details in failures:
                observed['searxng:' + str(name)] = str(details[0])[:160] if details else 'unavailable'
        hits = []
        # Enforce a single explicit site operator without altering the query.
        # Multiple/OR/negative operators need their original engine semantics.
        sites = re.findall(r'(?i)(?<!\S)site:([\w.-]+)(?=\s|$)', request.query)
        site = sites[0].lower().strip('.') if len(sites) == 1 and not re.search(r'(?i)\bOR\b', request.query) else None
        rejected_sites = 0
        for row in data['results']:
            if not isinstance(row, dict) or row.get('is_ad') or row.get('sponsored'):
                continue
            if not set(row.get('engines') or []) & set(engines.split(',')):
                continue  # Never present an unrequested engine as the selected one.
            url, title = str(row.get('url') or ''), str(row.get('title') or '')
            if not title or urlsplit(url).scheme not in {'http', 'https'}:
                continue
            host = (urlsplit(url).hostname or '').lower()
            if site and host != site and not host.endswith('.' + site):
                rejected_sites += 1
                continue
            # Metadata such as a repository's updated_at is NOT publication
            # of the underlying content. Verify dates at the original as usual.
            hits.append(ProviderHit(title=title, url=url, snippet=str(row.get('content') or ''), published_at=None))
            if len(hits) >= request.max_results:
                break
        if not hits and failures:
            raise ExternalSourceError('searxng_engines_unavailable')
        if not hits and rejected_sites:
            raise ExternalSourceError('searxng_site_constraint_ignored')
        return tuple(hits)


class SelectedSearchDiscovery:
    """Explicit engine selection must not silently run another paid provider."""
    def __init__(self, default, regional):
        self.default, self.regional = default, regional

    async def search(self, request):
        target = self.regional if request.search_backend != 'auto' else self.default
        return await target.search(request)
