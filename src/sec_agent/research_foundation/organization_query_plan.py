"""Conservative query constraints from the currently authorized catalog only.

No model calls, answer labels, title-based fiscal-year guesses or new grants.
Ambiguous/multi-issuer questions remain broad. Unknown metadata remains eligible
for an automatically planned search; an explicit user filter is a different API.
"""
from datetime import date
import re


REPORT_KINDS = {'10-K': 'annual', '10-K/A': 'annual', '20-F': 'annual', '20-F/A': 'annual',
                '40-F': 'annual', '40-F/A': 'annual', '10-Q': 'quarterly', '10-Q/A': 'quarterly',
                '8-K': 'event', '8-K/A': 'event', 'DEF 14A': 'proxy',
                'DEFA14A': 'proxy', 'DEFR14A': 'proxy', 'PRE 14A': 'proxy'}


def _mentions(query, alias):
    if re.search(r'[\u3400-\u9fff]', alias):
        return alias.casefold() in query.casefold()
    return bool(re.search(r'(?<!\w)' + re.escape(alias) + r'(?!\w)', query, re.IGNORECASE))


def _report_owners(query, aliases):
    # A named report owner is different from counterparties mentioned in the
    # question. Only explicit report phrases narrow scope; comparison abstains.
    if re.search(r'\b(?:compare|comparison|versus|vs\.?)\b|对比|比较|相比', query, re.IGNORECASE):
        return set(), []
    found=[]; owners=set()
    for alias, ids in aliases.items():
        boundary='' if re.search(r'[\u3400-\u9fff]',alias) else r'(?<!\w)'
        pattern=(boundary+re.escape(alias)+r"(?:['’]s)?\s*(?:fiscal\s*|FY\s*)?"
                 r'(?:20\d{2}\s*年?\s*)?(?:Form\s+)?(?:annual\s+report|10-?[KQ]|年报|季度报告)(?![A-Za-z])')
        for match in re.finditer(pattern,query,re.IGNORECASE):
            owners.update(ids);found.append(match.group())
    return owners,found


def plan_query(query, metadata):
    aliases, names = {}, {}
    named_issuers = {}
    for row in metadata.values():
        if row.get('issuer_id') and row.get('company_name'):
            named_issuers.setdefault(row['company_name'].casefold(), set()).add(row['issuer_id'])
    for row in metadata.values():
        issuer, name = row.get('issuer_id'), row.get('company_name')
        if issuer:
            # Only literal catalog identifiers; never infer a ticker/company
            # association from body text, graph counterparties or a URL.
            tail = issuer.split('::')[-1].replace('_', ' ').strip()
            if len(tail) >= 3:
                aliases.setdefault(tail.casefold(), set()).add(issuer)
        if name:
            owners = {issuer} if issuer else named_issuers.get(name.casefold(), {'name:'+name.casefold()})
            for owner in owners:
                names.setdefault(owner, set()).add(name)
                aliases.setdefault(name.casefold(), set()).add(owner)
    matches = [(a, owners) for a, owners in aliases.items() if _mentions(query, a)]
    owners = set().union(*(v for _, v in matches)) if matches else set()
    unresolved, evidence, constraint = [], [], {}
    report_owners, report_phrases = _report_owners(query, aliases)
    if len(report_owners)==1:
        owners=report_owners
        evidence.append({'field':'issuer','matched_query_text':report_phrases,
                         'basis':'explicit_report_owner_not_counterparty'})
    if len(owners) == 1:
        owner = next(iter(owners))
        constraint['company_names'] = sorted(names.get(owner, set()))
        if not owner.startswith('name:'):
            constraint['issuer_id'] = owner
        evidence.append({'field': 'issuer', 'matched_query_text': sorted(a for a, ids in matches if owner in ids),
                         'basis': 'literal_authorized_catalog_identity'})
    elif owners:
        unresolved.append('multiple_or_ambiguous_issuers_no_issuer_filter')
    else:
        unresolved.append('no_unambiguous_literal_catalog_issuer')
    forms = sorted(set(m.group().upper().replace(' ', '') for m in re.finditer(
        r'(?<![\w-])(?:10-?[KQ]|8-?K)(?:\s*/A)?(?![\w/-])', query, re.IGNORECASE)))
    forms = [re.sub(r'^(10|8)([KQ])', r'\1-\2', f) for f in forms]
    forms = sorted(set(forms))
    if len(forms) == 1:
        constraint['form'] = forms[0]
        evidence.append({'field': 'form', 'matched_query_text': forms, 'basis': 'explicit_filing_form'})
    elif forms:
        unresolved.append('multiple_forms_no_form_filter')
    kinds = set()
    if re.search(r'\bannual\s+reports?\b|年报|年度报告', query, re.IGNORECASE):
        kinds.add('annual')
    if re.search(r'\bquarterly\s+reports?\b|季报|季度报告', query, re.IGNORECASE):
        kinds.add('quarterly')
    if len(kinds) == 1 and not forms:
        constraint['report_kind'] = next(iter(kinds))
        evidence.append({'field': 'report_kind', 'basis': 'explicit_report_kind_not_fiscal_calendar'})
    elif len(kinds) > 1:
        unresolved.append('multiple_report_kinds_no_kind_filter')
    report_years = set(re.findall(r'(?<!\d)((?:19|20)\d{2})\s*(?:财年|年)?\s*'
        r'(?:annual\s+reports?|年报|年度报告|(?:Form\s+)?10-?K(?:\s*/A)?)(?![A-Za-z0-9/-])', query, re.I))
    for years in re.findall(r'((?:19|20)\d{2})\s*(?:and|versus|vs|to|[、/–—-]|与|和|及|至)\s*'
        r'((?:19|20)\d{2})\s*(?:财年|年)?\s*(?:annual\s+reports?|年报|年度报告|(?:Form\s+)?10-?K)', query, re.I):
        report_years.update(years)
    if len(report_years) == 1:
        constraint['annual_report_year'] = next(iter(report_years))
        evidence.append({'field':'annual_report_year', 'basis':'explicit_report_year_with_calendar_cover_validation',
                         'unknown_noncalendar_reports_retained':True})
    elif report_years:
        unresolved.append('multiple_annual_report_years_no_year_filter')
    periods = re.findall(r'(?:period\s+end(?:ing)?|报告期末|期末)\s*[:：]?\s*(\d{4}-\d{2}-\d{2})(?!\d)', query, re.IGNORECASE)
    if len(set(periods)) == 1:
        try:
            constraint['period_end'] = date.fromisoformat(periods[0]).isoformat()
            evidence.append({'field': 'period_end', 'matched_query_text': periods,
                             'basis': 'explicit_reporting_period_end'})
        except ValueError:
            unresolved.append('invalid_period_end_no_date_filter')
    elif periods:
        unresolved.append('multiple_periods_no_date_filter')
    if re.search(r'(?<!\d)(?:19|20)\d{2}(?!\d)', query) and 'period_end' not in constraint:
        unresolved.append('year_or_publication_date_not_mapped_to_period_end')
    return {'policy': 'conservative.v1', 'constraint': constraint, 'evidence': evidence,
            'unresolved': unresolved, 'unknown_metadata_retained': True}


def select_planned(metadata, plan):
    wanted = plan['constraint']
    accepted, unknown = set(), 0
    for document, row in metadata.items():
        checks = []
        if ('form' in wanted or 'report_kind' in wanted) and row.get('evidence_role') == 'discovery_metadata_only':
            # Discovery remains available for general/news navigation. It
            # cannot satisfy an explicit request for an original filing/report,
            # even if a parent filing form was copied into its metadata.
            checks.append(False)
        if 'issuer_id' in wanted or wanted.get('company_names'):
            names = {n.casefold() for n in wanted.get('company_names', [])}
            actual_id, actual_name = row.get('issuer_id'), row.get('company_name')
            if actual_id and wanted.get('issuer_id'):
                checks.append(actual_id == wanted['issuer_id'])
            elif actual_name and names:
                checks.append(actual_name.casefold() in names)
            else:
                checks.append(None)
        for field in ('form', 'period_end'):
            if field in wanted:
                checks.append(row.get(field) == wanted[field] if row.get(field) else None)
        if 'report_kind' in wanted:
            kind = REPORT_KINDS.get(row.get('form'))
            checks.append(kind == wanted['report_kind'] if kind else None)
        if 'annual_report_year' in wanted:
            year = row.get('calendar_annual_year')
            checks.append(year == wanted['annual_report_year'] if year else None)
        if False in checks:
            continue
        accepted.add(document)
        unknown += int(None in checks)
    return accepted, {**plan, 'scope_sources': len(metadata), 'selected_sources': len(accepted),
                      'unknown_sources_retained': unknown, 'excluded_sources': len(metadata)-len(accepted)}
