"""A literal date adjacent to a filing label is a document selector.

It is not an assertion that publication date equals a financial fact's period.
Both common document-label conventions are checked against catalog fields.
"""
from datetime import date
import re


MONTHS=('January','February','March','April','May','June','July','August','September','October','November','December')
LITERAL_DATE=re.compile(r'(?<!\d)(?:(?P<iso>(?:19|20)\d{2}-\d{2}-\d{2})(?!\d)|'
    r'(?P<cy>(?:19|20)\d{2})\s*年\s*(?P<cm>\d{1,2})\s*月\s*(?P<cd>\d{1,2})\s*日|'
    r'\b(?P<month>'+ '|'.join(MONTHS)+r')\s+(?P<day>\d{1,2}),?\s+(?P<year>(?:19|20)\d{2})(?!\d))',re.I)


def label_dates(query, form=None):
    """Literal dates on either side of a filing label, with exact offsets."""
    pattern=re.escape(form).replace(r'\-',r'\s*-?\s*') if form else r'(?:10\s*-?\s*[KQ]|8\s*-?\s*K)(?:/A)?'
    forms=list(re.finditer(r'(?<![A-Za-z0-9])'+pattern+r'(?![A-Za-z0-9]|\s*/A)',query,re.I))
    found=[]
    for match in LITERAL_DATE.finditer(query):
        try:
            value=(date.fromisoformat(match['iso']) if match['iso'] else
                date(int(match['cy']),int(match['cm']),int(match['cd'])) if match['cy'] else
                date(int(match['year']),MONTHS.index(match['month'].title())+1,int(match['day']))).isoformat()
        except ValueError:continue
        for filing in forms:
            if filing.end()<=match.start() and re.fullmatch(r'\s*[·:：]?\s*',query[filing.end():match.start()]):
                lo,hi=filing.start(),match.end()
            elif match.end()<=filing.start() and re.fullmatch(r'\s*(?:的\s*)?',query[match.end():filing.start()]):
                lo,hi=match.start(),filing.end()
            else:continue
            found.append({'value':value,'start':match.start(),'end':match.end(),
                          'matched_query_text':query[lo:hi]})
    return found


def document_date(query, form):
    if not form:
        return None
    matches=label_dates(query,form)
    values={m['value'] for m in matches}
    if len(values)!=1:
        return None
    value=next(iter(values))
    return {'value':value,'matched_query_text':[m['matched_query_text'] for m in matches],
        'basis':'literal_dated_filing_label_catalog_period_or_publication_not_fact_date'}


def matches_document_date(row, value):
    actual=[row.get('period_end'),row.get('publication_date')]
    if value in actual:
        return True
    return False if all(actual) else None


def mask_label_dates(query):
    """Keep offsets while removing only literal filing-label dates from facts."""
    chars=list(query)
    for match in label_dates(query):
        lo,hi=match['start'],match['end'];chars[lo:hi]=' '*(hi-lo)
    return ''.join(chars)
