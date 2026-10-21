"""Pinned offline parser receipts for legacy binary-digest sources.

Only the offline producer opens an explicitly supplied archive. Request-time
readers accept a server-pinned catalog, never an archive path from metadata.
"""
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re

from retrieval.library_source_bundle import text_digest

FORMAT = 'library-archive-recovery.v1'
CATALOG = 'library-archive-catalog.v1'
PROFILES = {'.html': 'legacy-html-table-text.v1', '.pdf': 'legacy-pypdf-pages.v1'}


def parse_archive(raw, suffix):
    if suffix == '.pdf':
        from pypdf import PdfReader
        return [page.extract_text() for page in PdfReader(BytesIO(raw)).pages]
    if suffix != '.html':
        raise ValueError('archive_parser_unsupported')
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(raw, 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'nav', 'footer', 'header']):
        tag.decompose()
    for row in soup.find_all('tr'):
        row.replace_with(soup.new_string('\n' + ' | '.join(
            cell.get_text(' ', strip=True) for cell in row.find_all(['th', 'td'])) + '\n'))
    return [re.sub(r'\n{3,}', '\n\n', soup.get_text('\n', strip=True))]


def create_receipt(source, parents, library_sha256, archive):
    archive = Path(archive)
    raw = archive.read_bytes()
    if sha256(raw).hexdigest() != source['digest']:
        raise ValueError('archive_raw_digest_mismatch')
    suffix = archive.suffix.lower()
    pages = parse_archive(raw, suffix)
    receipt = dict(format=FORMAT, source_id=source['id'], library_sha256=library_sha256,
                   raw_sha256=source['digest'], parser=PROFILES[suffix],
                   pages=[dict(number=i+1, text=text, sha256=text_digest(text)) for i, text in enumerate(pages)])
    recover_archive(source, parents, library_sha256, receipt)
    return receipt


def recover_archive(source, parents, library_sha256, receipt):
    if (source['access_state'] != 'readable' or receipt['format'] != FORMAT
            or receipt['source_id'] != source['id'] or receipt['raw_sha256'] != source['digest']
            or receipt['library_sha256'] != library_sha256 or receipt['parser'] not in PROFILES.values()):
        raise ValueError('archive_receipt_identity_mismatch')
    pages = receipt['pages']
    if not pages or (receipt['parser'] == PROFILES['.html'] and len(pages) != 1):
        raise ValueError('archive_page_sequence_invalid')
    expected, spans, texts, cursor = {}, [], [], 0
    for number, page in enumerate(pages, 1):
        text = page['text']
        if type(page['number']) is not int or page['number'] != number or text_digest(text) != page['sha256']:
            raise ValueError('archive_page_sequence_or_digest_mismatch')
        label = f'PDF page {number}' if receipt['parser'] == PROFILES['.pdf'] else 'HTML text'
        spans.append(dict(number=number, source_char_start=cursor, source_char_end=cursor+len(text), sha256=page['sha256']))
        for lo in range(0, len(text), 3500):
            hi = min(lo+3500, len(text))
            expected[f'{source["id"]}:P{number}:{lo}'] = dict(
                locator=f'{label} chars {lo}-{hi}', body=text[lo:hi],
                source_char_start=cursor+lo, source_char_end=cursor+hi, original_page=number)
        texts.append(text)
        cursor += len(text) + 1  # Explicit form-feed boundary, including blank PDF pages.
    if len(parents) != len(expected) or {p['id'] for p in parents} != set(expected):
        raise ValueError('archive_parent_coverage_mismatch')
    recovered = []
    for parent in parents:
        row = expected[parent['id']]
        if (parent['source_id'] != source['id'] or parent['body'] != row['body']
                or parent['locator'] != row['locator'] or parent['digest'] != text_digest(row['body'])):
            raise ValueError('archive_parent_replay_mismatch')
        recovered.append({**parent, **row})
    text = '\f'.join(texts)
    provenance = dict(format=FORMAT, parser=receipt['parser'], raw_sha256=source['digest'],
                      parsed_text_sha256=text_digest(text), separator='\f', pages=spans)
    return text, recovered, provenance


class ArchiveRecoveryCatalog:
    def __init__(self, path, expected_sha256):
        self.root = Path(path).resolve().parent
        raw = Path(path).read_bytes()
        if not re.fullmatch('[a-f0-9]{64}', expected_sha256 or '') or sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('archive_catalog_digest_mismatch')
        self.manifest = json.loads(raw)
        self.sha256 = expected_sha256
        if self.manifest['format'] != CATALOG or self.manifest['status'] != 'verified':
            raise ValueError('archive_catalog_not_verified')

    def recover(self, source, parents, library_sha256):
        if self.manifest['library_sha256'] != library_sha256:
            raise ValueError('archive_catalog_library_mismatch')
        record = self.manifest['sources'].get(source['id'])
        if record is None:
            raise ValueError('archive_receipt_not_found')
        digest = record['sha256']
        if not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('archive_receipt_digest_invalid')
        path = (self.root / (digest + '.json')).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError('archive_receipt_path_invalid')
        raw = path.read_bytes()
        if sha256(raw).hexdigest() != digest:
            raise ValueError('archive_receipt_digest_mismatch')
        text, recovered, provenance = recover_archive(source, parents, library_sha256, json.loads(raw))
        provenance.update(receipt_sha256=digest, catalog_sha256=self.sha256,
                          parser_versions=self.manifest['parser_versions'])
        return text, recovered, provenance


def configured_catalog():
    import os
    path = os.getenv('FINSIGHT_LIBRARY_RECOVERY_CATALOG')
    expected = os.getenv('FINSIGHT_LIBRARY_RECOVERY_SHA256')
    if not path and not expected:
        return None
    if not path or not expected:
        raise ValueError('archive_catalog_configuration_incomplete')
    return ArchiveRecoveryCatalog(path, expected)
