"""Exact SEC original-document identity across local parse revisions.

This is a navigation alias for the SAME filing document, never a global issuer
merge, a grant, or a claim that two parsed bodies have identical financial facts.
"""
import re
from urllib.parse import urlsplit


def original_filing_key(url):
    if not isinstance(url, str):
        return None
    try:
        parsed = urlsplit(url)
    except ValueError:
        return None
    if (parsed.scheme != 'https' or parsed.hostname not in {'sec.gov', 'www.sec.gov'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.netloc not in {'sec.gov', 'www.sec.gov'}):
        return None
    if not re.fullmatch(r'/Archives/edgar/data/[0-9]+/[0-9]{18}/[A-Za-z0-9_.-]+\.html?', parsed.path):
        return None
    return 'https://www.sec.gov' + parsed.path


def with_document_issuer_aliases(metadata):
    """Only join identities present in this caller's already authorized catalog."""
    owners = {}
    for row in metadata.values():
        key = original_filing_key(row.get('original_filing_key'))
        if key and row.get('issuer_id'):
            owners.setdefault(key, set()).add(row['issuer_id'])
    result = {}
    for document, row in metadata.items():
        # Discard caller-supplied derived aliases and recompute from originals.
        clean = {k:v for k,v in row.items() if k != 'same_document_issuer_ids'}
        key = original_filing_key(row.get('original_filing_key'))
        # Compatibility between explicit parse identities is not enrichment of
        # incomplete catalog rows. Filling only their owner would admit them to
        # owner-specific lanes while their missing form/period stayed unknown.
        if key and key in owners and row.get('issuer_id'):
            clean['same_document_issuer_ids'] = sorted(owners[key])
        result[document] = clean
    return result
