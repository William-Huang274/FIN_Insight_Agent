"""Congress.gov metadata and version navigation; no HTML challenge handling."""
import asyncio
from datetime import datetime, timezone
import os
import re
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from .external_sources import ExternalSourceError


API = 'https://api.congress.gov/v3/bill/'
TYPES = {'house-bill': 'hr', 'senate-bill': 's', 'house-joint-resolution': 'hjres',
         'senate-joint-resolution': 'sjres', 'house-concurrent-resolution': 'hconres',
         'senate-concurrent-resolution': 'sconres', 'house-resolution': 'hres',
         'senate-resolution': 'sres'}


def public_payload(value, secret):
    if isinstance(value, dict):
        return {k:public_payload(v, secret) for k,v in value.items() if k.lower() not in {'request','api_key','x-api-key'}}
    if isinstance(value, list):
        return [public_payload(v, secret) for v in value]
    if isinstance(value, str):
        if value.startswith(('https://','http://')):
            p = urlsplit(value)
            value = urlunsplit((p.scheme,p.netloc,p.path,urlencode([(k,v) for k,v in parse_qsl(p.query) if k.lower() != 'api_key']),p.fragment))
        return value.replace(secret, '[redacted]') if secret else value
    return value


def bill_identity(query):
    """Require an explicit Congress; never guess a session from a bare bill number."""
    query = query.strip()
    if query.startswith('https://'):
        p = urlsplit(query)
        if p.username or p.password or p.port or p.query:
            raise ValueError('congress_locator_invalid; use a public bill URL without query parameters')
        if p.hostname in {'www.congress.gov', 'congress.gov'}:
            m = re.fullmatch(r'/bill/(\d+)(?:st|nd|rd|th)-congress/([a-z-]+)/(\d+)(?:/(?:text|actions|all-actions|all-info))?/?', p.path)
            if m and m[2] in TYPES:
                return int(m[1]), TYPES[m[2]], int(m[3])
        if p.hostname == 'api.congress.gov':
            query = p.path.removeprefix('/v3/bill/').rstrip('/')
    m = re.fullmatch(r'(\d{1,3})/(hr|s|hjres|sjres|hconres|sconres|hres|sres)/(\d{1,7})', query.lower())
    if not m or not (int(m[1]) > 0 and int(m[3]) > 0):
        raise ValueError('congress_bill_identity_required; pass a Congress.gov bill URL or congress/type/number, e.g. 119/hr/1. For topics first use read_public_source search; this API is not full-text keyword search.')
    return int(m[1]), m[2], int(m[3])


def api_json(url, params, key):
    import requests
    if not key:
        raise ExternalSourceError('congress_api_key_missing: configure CONGRESS_API_KEY on the research service')
    try:
        with requests.get(url, params=params, headers={'X-Api-Key': key, 'Accept': 'application/json'},
                          timeout=(5, 20), allow_redirects=False, stream=True) as r:
            if r.status_code == 429:
                raise ExternalSourceError('congress_api_rate_limited; do not immediately retry')
            if r.status_code in (401, 403):
                raise ExternalSourceError('congress_api_credential_rejected; not a missing bill or browser challenge')
            if r.status_code != 200:
                raise ExternalSourceError(f'congress_api_http_{r.status_code}')
            data = bytearray()
            for chunk in r.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ExternalSourceError('congress_api_response_too_large')
            import json
            body = json.loads(data)
            if not isinstance(body, dict) or 'error' in body:
                raise ExternalSourceError('congress_api_invalid_response')
            # The provider's request echo can contain credentials. Never persist it.
            return public_payload(body, key)
    except requests.exceptions.SSLError:
        raise ExternalSourceError('congress_api_tls_failed') from None
    except requests.exceptions.ProxyError:
        raise ExternalSourceError('congress_api_proxy_failed') from None
    except requests.RequestException:
        raise ExternalSourceError('congress_api_connection_failed') from None
    except (ValueError, UnicodeError):
        raise ExternalSourceError('congress_api_invalid_json') from None


class CongressAPI:
    def __init__(self, *, key=None, transport=api_json):
        self.key = key if key is not None else os.environ.get('CONGRESS_API_KEY', '')
        self.transport = transport
        self.blocked_until = 0.0

    async def read(self, identity, section, offset=0, limit=20):
        congress, kind, number = identity
        suffix = {'record': '', 'texts': '/text', 'actions': '/actions'}[section]
        url = f'{API}{congress}/{kind}/{number}{suffix}'
        if time.monotonic() < self.blocked_until:
            raise ExternalSourceError('congress_api_rate_limited; cooling down, no new request sent')
        try:
            body = await asyncio.to_thread(self.transport, url, {'format':'json', 'offset':offset, 'limit':limit}, self.key)
        except ExternalSourceError as exc:
            if exc.code.startswith('congress_api_rate_limited'):
                self.blocked_until = time.monotonic() + 60
            raise
        field = {'record':'bill', 'texts':'textVersions', 'actions':'actions'}[section]
        value = body.get(field)
        if (section == 'record' and not isinstance(value, dict)) or (section != 'record' and not isinstance(value, list)):
            raise ExternalSourceError('congress_api_response_shape_invalid')
        if section == 'record' and (str(value.get('congress')), str(value.get('type', '')).lower(), str(value.get('number'))) != (str(congress), kind, str(number)):
            raise ExternalSourceError('congress_api_bill_identity_mismatch')
        # Only bounded numeric pagination is used; never follow provider URLs with a key.
        pagination = body.get('pagination') or {}
        return {'source_url':url, field:value,
                'next_offset':offset+limit if pagination.get('next') else None,
                'captured_at':datetime.now(timezone.utc).isoformat()}


def congress_rendition_package(url, identity):
    """Bind an API-listed file to exactly the same official GovInfo package."""
    p = urlsplit(url)
    if p.scheme != 'https' or p.hostname != 'www.congress.gov' or p.query or p.fragment or p.port:
        return None
    congress, kind, number = identity
    m = re.fullmatch(rf'/{congress}/bills/{kind}{number}/(BILLS-{congress}{kind}{number}[a-z]+)\.(htm|xml|pdf)', p.path)
    return m[1] if m else None
