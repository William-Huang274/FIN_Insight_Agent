"""A literal date adjacent to a filing label is a document selector.

It is not an assertion that publication date equals a financial fact's period.
Both common document-label conventions are checked against catalog fields.
"""
from datetime import date
import re


def document_date(query, form):
    if not form:
        return None
    pattern=re.escape(form).replace(r'\-',r'\s*-?\s*')
    matches=list(re.finditer(r'(?<![A-Za-z0-9])'+pattern+r'\s*[·:：]?\s*'
        r'(?P<date>(?:19|20)\d{2}-\d{2}-\d{2})(?!\d)',query,re.I))
    values={m['date'] for m in matches}
    if len(values)!=1:
        return None
    value=next(iter(values))
    try:
        if date.fromisoformat(value).isoformat()!=value:return None
    except ValueError:return None
    return {'value':value,'matched_query_text':[m[0] for m in matches],
        'basis':'literal_dated_filing_label_catalog_period_or_publication_not_fact_date'}


def matches_document_date(row, value):
    actual=[row.get('period_end'),row.get('publication_date')]
    if value in actual:
        return True
    return False if all(actual) else None


def mask_label_dates(query):
    """Keep offsets while removing only literal filing-label dates from facts."""
    pattern=r'(?<![A-Za-z0-9])(?:10\s*-?\s*[KQ]|8\s*-?\s*K)(?:/A)?\s*[·:：]?\s*(?P<date>(?:19|20)\d{2}-\d{2}-\d{2})(?!\d)'
    chars=list(query)
    for match in re.finditer(pattern,query,re.I):
        try:date.fromisoformat(match['date'])
        except ValueError:continue
        lo,hi=match.span('date');chars[lo:hi]=' '*(hi-lo)
    return ''.join(chars)
