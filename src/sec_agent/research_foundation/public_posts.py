"""Read public X embed objects without account cookies or paid API dispatch.

The fixed syndication endpoint is also used by vercel/react-tweet. Search stays
with the existing web providers; this adapter never claims timeline coverage.
"""
import asyncio
from datetime import datetime, timezone
from html import escape
import json
import re
from urllib.parse import urlsplit

from .external_sources import ExternalSourceError, FetchedPage


def post_locator(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com'}:
        return None
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,30}|i/web)/status/(\d{1,30})/?', parsed.path)
    return match.groups() if match else None


def public_json(url, params, timeout):
    """Fixed-provider callers only; finite response, no redirects or retries."""
    import requests
    try:
        with requests.get(url, params=params, timeout=(5, timeout), stream=True,
                          allow_redirects=False, headers={'User-Agent': 'Mozilla/5.0 FinSight public research reader'}) as response:
            if response.status_code != 200:
                raise ExternalSourceError(f'public_data_http_{response.status_code}')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > 3_000_000:
                    raise ExternalSourceError('public_data_response_too_large')
                chunks.append(chunk)
            return json.loads(b''.join(chunks))
    except requests.RequestException as exc:
        raise ExternalSourceError('public_data_transport_failed') from exc
    except (ValueError, UnicodeError) as exc:
        raise ExternalSourceError('public_data_invalid_json') from exc


def post_page(url, payload, cutoff=None):
    handle, post_id = post_locator(url)
    if not isinstance(payload, dict) or payload.get('id_str') != post_id or not payload.get('text'):
        raise ExternalSourceError('x_public_post_unavailable')
    user = payload.get('user') or {}
    username = user.get('screen_name', '')
    if not username or (handle != 'i/web' and handle.casefold() != username.casefold()):
        raise ExternalSourceError('x_post_author_mismatch')
    try:
        published = datetime.fromisoformat(payload['created_at'].replace('Z', '+00:00'))
        if published.tzinfo is None:
            raise ValueError('timezone missing')
        edit_ids = (payload.get('edit_control') or {}).get('edit_tweet_ids', [])
        if payload.get('isEdited') and not edit_ids:
            raise ValueError('edited version missing')
        version_time = max([published] + [datetime.fromtimestamp(((int(i) >> 22) + 1288834974657) / 1000, timezone.utc)
                                         for i in edit_ids])
    except (KeyError, ValueError, OverflowError, OSError, TypeError) as exc:
        raise ExternalSourceError('x_post_version_time_unverified') from exc
    if cutoff and version_time > cutoff:
        raise ExternalSourceError('x_post_after_cutoff_or_later_edit')
    text = payload['text']
    if not isinstance(text, str):
        raise ExternalSourceError('x_public_post_invalid_text')
    links = [u.get('expanded_url') for u in (payload.get('entities') or {}).get('urls', []) if u.get('expanded_url')]
    metadata = {
        'source_url': url, 'post_id': post_id, 'author_handle': username,
        'author_name': user.get('name'), 'author_id': user.get('id_str'),
        'published_at': published.isoformat(), 'latest_version_at': version_time.isoformat(),
        'account_badges': {key: user.get(key) for key in ('verified', 'is_blue_verified', 'verified_type')},
        'identity_verification': 'not_established_by_badge; corroborate account via institution or issuer website',
        'edit_ids': edit_ids, 'is_stale_edit': payload.get('isStaleEdit'),
        'reply_to_post_id': payload.get('in_reply_to_status_id_str'),
        'quoted_post_id': (payload.get('quoted_tweet') or {}).get('id_str'),
        'linked_urls_not_read': links, 'text_completeness': 'public_embed_text_only; linked articles, media and thread not read',
        'source_channel': 'x_public_syndication', 'claim_status': 'speaker_statement_not_independent_confirmation',
    }
    # Publication metadata is provider-derived, not arbitrary dates inside the post.
    body = json.dumps(metadata, ensure_ascii=False, sort_keys=True) + '\n\nPost text:\n' + text
    html = ('<html><head><meta property="article:published_time" content="' + version_time.isoformat()
            + '"></head><body><article><h1>Public post by @' + escape(username)
            + '</h1><pre>' + escape(body) + '</pre></article></body></html>')
    return FetchedPage(final_url=url, html=html, extracted_text=body,
                       extraction_method='x_public_embed', status_code=200, content_type='text/html')


class PublicPostFetcher:
    def __init__(self, fallback, *, cutoff=None, transport=public_json):
        self.fallback, self.cutoff, self.transport = fallback, cutoff, transport

    async def fetch(self, url, *, timeout_seconds):
        locator = post_locator(url)
        if locator is None:
            return await self.fallback.fetch(url, timeout_seconds=timeout_seconds)
        payload = await asyncio.to_thread(self.transport, 'https://cdn.syndication.twimg.com/tweet-result',
                                         {'id': locator[1], 'lang': 'en', 'token': '0'}, timeout_seconds)
        return post_page(url, payload, self.cutoff)
