"""Small, deterministic reading aids; never a financial semantic adjudicator.

Original text and citation identities stay unchanged. Only explicit USD scales
and explicit fiscal labels are recognized. Ambiguous tables/periods are left to
the researcher, not inferred from a calendar date.
"""
import re
from decimal import Decimal

_NUMBER = r"[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?"
_USD = re.compile(rf"(?<![\w.-])(?:US\$|USD\s*)\s*({_NUMBER})\s*(billion|million|trillion)\b", re.I)
_TABLE = re.compile(rf"(?P<label>[^\n]{{0,70}})\(US\$\s*(billions|millions)\)\s*({_NUMBER})", re.I)
_ZH = re.compile(rf"(?<![\d.])({_NUMBER})\s*(万亿|亿|百万|万)\s*美元")
_FY = re.compile(r"\b(?:FY\s*|fiscal\s+(?:year\s+)?)(20\d{2})\b|\b(20\d{2})\s*财年", re.I)
_SCALE = {'million': Decimal('1000000'), 'billion': Decimal('1000000000'),
          'trillion': Decimal('1000000000000'), '万': Decimal('10000'),
          '百万': Decimal('1000000'), '亿': Decimal('100000000'), '万亿': Decimal('1000000000000')}


def _decimal(value):
    return Decimal(value.replace(',', ''))


def source_fact_hints(text):
    amounts = []
    for match in _USD.finditer(text):
        amounts.append((match.group(0), match.group(1), match.group(2).lower()))
    for match in _TABLE.finditer(text):
        amounts.append((match.group(0).strip(), match.group(3), match.group(2).lower().rstrip('s')))
    unique = {}
    for original, value, scale in amounts:
        base = _decimal(value) * _SCALE[scale]
        unique[(original, value, scale)] = {'source_text': original, 'source_value': value,
            'source_scale': scale, 'currency': 'USD', 'base_value': format(base, 'f'),
            'display_zh': format(base / _SCALE['亿'], 'f') + ' 亿美元'}
    years = sorted({a or b for a, b in _FY.findall(text)})
    return {'amounts': list(unique.values())[:24], 'explicit_fiscal_years': years,
            'scope': 'Mechanical display aids only; no subject/period association or numeric-fact authority. Preserve original units when uncertain. Fiscal year is not calendar year.'}


def with_source_fact_hints(value):
    """Add host-owned aids only to original passages, without changing originals."""
    if isinstance(value, list):
        return [with_source_fact_hints(row) for row in value]
    if not isinstance(value, dict):
        return value
    result = {k: with_source_fact_hints(v) for k, v in value.items()}
    if result.get('result_state') == 'source_bound_passage' and result.get('passage'):
        hints = source_fact_hints(result['passage'])
        if hints['amounts'] or hints['explicit_fiscal_years']:
            result['host_fact_reading_aids'] = hints
    return result


def fact_consistency_issues(statement, cited_texts):
    """Flag narrow contradictions for correction, not missing/unsupported facts.

    Currency checks require a copied mantissa with a changed scale and no equal
    supported amount. Fiscal checks require a single explicit source fiscal
    year and a single conflicting claim year. Mixed-period sources are not
    automatically adjudicated. No calendar-to-fiscal inference is performed.
    """
    source = '\n'.join(cited_texts)
    hints = source_fact_hints(source)
    issues = []
    supported = {_decimal(r['base_value']) for r in hints['amounts']}
    supported.update(_decimal(m.group(1)) * _SCALE[m.group(2)] for m in _ZH.finditer(source))
    for match in _ZH.finditer(statement):
        value = _decimal(match.group(1))
        if value * _SCALE[match.group(2)] in supported:
            continue
        same = [r for r in hints['amounts'] if _decimal(r['source_value']) == value]
        if same:
            issues.append({'code': 'copied_currency_mantissa_changed_scale', 'claim_text': match.group(0),
                'source_text': same[0]['source_text'], 'mechanical_display': same[0]['display_zh']})
    claim_years = {a or b for a, b in _FY.findall(statement)}
    years = set(hints['explicit_fiscal_years'])
    if len(years) == len(claim_years) == 1 and years != claim_years:
        issues.append({'code': 'explicit_fiscal_year_conflict', 'claim_year': next(iter(claim_years)),
            'source_year': next(iter(years))})
    return issues
