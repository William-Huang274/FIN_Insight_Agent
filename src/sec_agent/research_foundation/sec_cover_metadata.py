"""Conservative form recovery from a captured SEC filing's own cover.

This is navigation metadata, not financial fact authority. No title, URL suffix,
parent filing, fiscal-year inference, network lookup or source mutation.
"""
from hashlib import sha256
import re
from urllib.parse import urlsplit

POLICY = 'sec-original-cover-form.v1'
_HEADER = re.compile(r'SECURITIES\s+AND\s+EXCHANGE\s+COMMISSION', re.I)
_FORM = re.compile(r'^\s*FORM\s+(10\s*-\s*[KQ]|8\s*-\s*K)(\s*/\s*A)?\s*$', re.I | re.M)


def cover_form(bundle, metadata):
    source = bundle['source']
    url = urlsplit(source.get('url') or '')
    if (metadata.get('category') != 'filing' or url.scheme != 'https'
            or url.hostname not in {'www.sec.gov', 'sec.gov'} or url.username or url.password
            or not url.path.startswith('/Archives/edgar/data/')):
        return None
    text = bundle.get('text', '')
    if not isinstance(text, str):
        return None
    cover = text[:2048]
    header = _HEADER.search(cover)
    if header is None or header.start() > 1000:
        return None
    matches = list(_FORM.finditer(cover, header.end()))
    if len(matches) != 1 or matches[0].start() - header.end() > 300:
        return None
    match = matches[0]
    form = re.sub(r'\s+', '', match.group(1)).upper() + ('/A' if match.group(2) else '')
    # Preserve the exact offsets in the original text, not normalized display text.
    lo, hi = match.start(), match.end()
    return {'policy': POLICY, 'source_id': source['id'], 'form': form,
            'char_start': lo, 'char_end': hi, 'quote': text[lo:hi],
            'quote_sha256': sha256(text[lo:hi].encode()).hexdigest()}


def calendar_annual_year(bundle, descriptor, form_evidence):
    """Resolve a calendar annual report from its own explicit December 31 cover.

    No conversion of arbitrary fiscal years to dates. Non-calendar years,
    missing/conflicting period metadata, exhibits and transition reports stay
    unknown. Used only to distinguish explicitly requested annual-report years.
    """
    if not form_evidence or descriptor.get('form') not in {'10-K', '10-K/A'}:
        return None
    text = bundle.get('text', '')
    if not isinstance(text, str):
        return None
    cover = text[:2048]
    matches = list(re.finditer(r'for\s+the\s+fiscal\s+year\s+ended\s+'
        r'December\s+31\s*,?\s*((?:19|20)\d{2})(?!\d)', cover, re.I))
    if len(matches) != 1 or matches[0].start() < form_evidence['char_end']:
        return None
    match = matches[0]; year = match.group(1)
    if descriptor.get('period_end') != year+'-12-31':
        return None
    # The date clause, not the title or publication date, supplies the year.
    quote = text[match.start():match.end()]
    return {'policy':'sec-calendar-annual-year.v1', 'year':year,
            'char_start':match.start(), 'char_end':match.end(), 'quote':quote,
            'quote_sha256':sha256(quote.encode()).hexdigest()}
