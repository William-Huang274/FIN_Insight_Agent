"""Explicit report-period syntax, separate from dates of financial facts.

No filing-date, fiscal-calendar or bare-year inference. The caller retains
unknown document metadata and must still enforce current source permissions.
"""
import re
from .fact_period_matching import dates


def explicit_report_period(query):
    found = []
    for lo, hi, value in dates(query):
        before, after = query[:lo], query[hi:]
        english = re.search(
            r'\b(?:10-?Q|quarterly report)\s+for\s+(?:(?:the\s+)?(?:quarter|period)\s+ended\s+)?$',
            before, re.I)
        chinese = re.search(r'截至\s*$', before) and re.match(
            r'\s*(?:的)?\s*(?:10-?Q|季度报告|季度披露|季报)(?![A-Za-z])', after, re.I)
        if english or chinese:
            found.append({'value': value, 'quote': query[(english.start() if english else lo-2):hi],
                          'basis': 'explicit_report_period_not_filing_or_fact_date'})
    unique = {r['value'] for r in found}
    return found[0] if len(unique) == 1 else None


def comparison_starts_with_date(query, comparison_end):
    """Only an explicit date immediately after compare is a temporal object."""
    suffix = query[comparison_end:]
    found = dates(suffix)
    return bool(found and not suffix[:found[0][0]].strip())
