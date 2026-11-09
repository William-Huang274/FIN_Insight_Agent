"""arXiv's versioned Atom records over the existing guarded HTTP transport.

lxml parses Atom; this adapter binds the requested paper/version and dates. An
API abstract is labelled as metadata, never as the paper's full text.
"""
import asyncio
from collections import OrderedDict
from datetime import datetime
from html import escape
import re
import time
from urllib.parse import parse_qs, urlencode, urlsplit

from lxml import etree

from .external_sources import ExternalSourceError, FetchedPage
from sec_agent.research.reviewed_evidence_pack import canonical_digest

_ID = re.compile(r'(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v[1-9]\d*)?')
_ATOM = '{http://www.w3.org/2005/Atom}'


def arxiv_locator(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('https', 'http') or parsed.username or parsed.password or parsed.port:
        return None
    if parsed.hostname in ('arxiv.org', 'www.arxiv.org', 'export.arxiv.org'):
        match = re.fullmatch(r'/(abs|pdf|html)/(.+?)(?:\.pdf)?', parsed.path)
        if match and _ID.fullmatch(match[2]) and not parsed.query:
            return match[1], match[2]
        params = parse_qs(parsed.query)
        if parsed.path == '/api/query' and set(params) == {'id_list'} and len(params['id_list']) == 1 and _ID.fullmatch(params['id_list'][0]):
            return 'api', params['id_list'][0]
    return None


def api_url(paper_id):
    return 'https://export.arxiv.org/api/query?' + urlencode({'id_list': paper_id})


def parse_record(raw, requested):
    try:
        root = etree.fromstring(raw.encode(), etree.XMLParser(resolve_entities=False, no_network=True))
        rows = root.findall(_ATOM + 'entry')
        if len(rows) != 1:
            raise ValueError('one exact record required')
        row = rows[0]
        identity = arxiv_locator(row.findtext(_ATOM + 'id', ''))
        if not identity or identity[0] != 'abs' or not re.search(r'v[1-9]\d*$', identity[1]):
            raise ValueError('version identity missing')
        version = identity[1]
        if (version != requested if re.search(r'v[1-9]\d*$', requested) else re.sub(r'v\d+$', '', version) != requested):
            raise ValueError('record identity mismatch')
        published = row.findtext(_ATOM + 'published', '')
        updated = row.findtext(_ATOM + 'updated', '')
        stamps = [datetime.fromisoformat(v.replace('Z', '+00:00')) for v in (published, updated)]
        if any(t.tzinfo is None for t in stamps) or stamps[1] < stamps[0]:
            raise ValueError('invalid publication timestamps')
        links = []
        for link in row.findall(_ATOM + 'link'):
            href = link.get('href', '')
            target = arxiv_locator(href)
            if target and target[0] in ('pdf','html') and target[1] == version:
                links.append((target[0], urlsplit(href)._replace(scheme='https').geturl()))
        return {'version': version, 'published': published, 'updated': updated,
                'day': max(stamps).date().isoformat(),
                'title': ' '.join(row.findtext(_ATOM + 'title', '').split()),
                'links': links,
                'authors': [a.findtext(_ATOM + 'name','') for a in row.findall(_ATOM + 'author')],
                'summary': row.findtext(_ATOM + 'summary', '').strip()}
    except (etree.XMLSyntaxError, ValueError, TypeError) as exc:
        raise ExternalSourceError('arxiv_record_identity_or_version_invalid') from exc


class ArxivSources:
    def __init__(self, origin, *, request_interval=3.0):
        self.origin, self.interval = origin, request_interval
        self.records = OrderedDict()
        self.lock, self.last_request = asyncio.Lock(), 0.0

    async def record(self, paper_id, timeout_seconds=30):
        async with self.lock:
            if paper_id in self.records:
                self.records.move_to_end(paper_id)
                return self.records[paper_id]
            await asyncio.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            page = await self.origin.fetch(api_url(paper_id), timeout_seconds=timeout_seconds)
            if page.final_url != api_url(paper_id):
                raise ExternalSourceError('arxiv_api_redirect_identity_changed')
            record = parse_record(page.html or page.extracted_text or '', paper_id)
            self.records[paper_id] = record
            if len(self.records) > 64:
                self.records.popitem(last=False)
            return record

    async def resolve(self, candidate, cutoff):
        locator = arxiv_locator(candidate.canonical_url)
        if not locator:
            return None
        kind, paper_id = locator
        record = await self.record(paper_id)
        if record['day'] > cutoff.isoformat():
            return 'after_cutoff'
        # Keep a full-text request as full text. An abstract request exposes the
        # actual official API record and links to separately readable renditions.
        url = (f'https://arxiv.org/{kind}/{record["version"]}' if kind in ('pdf', 'html')
               else api_url(record['version']))
        return candidate.model_copy(update={'canonical_url': url, 'source_domain': urlsplit(url).hostname,
            'candidate_id': canonical_digest({'candidate': candidate.candidate_id, 'version_url': url}),
            'title': record['title'], 'published_at': record['day'], 'snippet': ''})

    async def fetch(self, url, *, timeout_seconds):
        locator = arxiv_locator(url)
        if not locator or locator[0] != 'api':
            return await self.origin.fetch(url, timeout_seconds=timeout_seconds)
        record = await self.record(locator[1], timeout_seconds)
        version = record['version']
        text = (f'arXiv official bibliographic record and abstract; NOT full paper.\n'
                f'Version: {version}\nFirst submitted: {record["published"]}\n'
                f'Version updated: {record["updated"]}\nAuthors: {", ".join(record["authors"])}\n'
                f'{record["title"]}\n{record["summary"]}\n')
        text += '\n'.join(f'[Full paper {kind.upper()} — not yet read]({href})' for kind,href in record['links'])
        html = (f'<html><head><meta name="dcterms.issued" content="{escape(record["published"])}">'
                f'<meta name="dcterms.modified" content="{escape(record["updated"])}"></head>'
                f'<body><h1>{escape(record["title"])}</h1><pre>{escape(text)}</pre></body></html>')
        return FetchedPage(final_url=url, html=html, extracted_text=text,
            extraction_method='arxiv_api_metadata', status_code=200, content_type='application/atom+xml')
