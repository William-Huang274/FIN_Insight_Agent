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


def _alias_pattern(alias, compatible=False):
    # Whitespace/punctuation compatibility for catalog-derived aliases only;
    # no fuzzy spelling, inferred ticker, or merging issuer identities.
    if compatible and alias.isascii():
        return r'[\W_]*'.join(re.escape(c) for c in alias if c.isalnum())
    return re.escape(alias)


def _compatible_mentions(query, aliases, *, bilingual_boundaries=False):
    hits = []
    for alias, owners in aliases.items():
        boundary = '' if re.search(r'[\u3400-\u9fff]', alias) else (r'(?<![A-Za-z0-9_])' if bilingual_boundaries else r'(?<!\w)')
        end = '' if not boundary else (r'(?![A-Za-z0-9_])' if bilingual_boundaries else r'(?!\w)')
        for match in re.finditer(boundary+_alias_pattern(alias, True)+end, query, re.I):
            hits.append((alias, owners, match.start(), match.end()))
    # A separate short-name mention is still retained. Only a short match
    # wholly inside a longer declared name at the SAME query location loses.
    hits = [h for h in hits if not any(
        other[2] <= h[2] and other[3] >= h[3] and other[3]-other[2] > h[3]-h[2]
        for other in hits)]
    active = {h[0] for h in hits}
    return [(a, ids) for a, ids in aliases.items() if a in active], [
        {'alias': a, 'query_text': query[lo:hi], 'start': lo, 'end': hi,
         'issuer_ids': sorted(owners)} for a, owners, lo, hi in hits]


def _report_owners(query, aliases, *, allow_comparison=False, compatible=False, dated_reports=False):
    # A named report owner is different from counterparties mentioned in the
    # question. Only explicit report phrases narrow scope; comparison abstains.
    if not allow_comparison and re.search(r'\b(?:compare|comparison|versus|vs\.?)\b|对比|比较|相比', query, re.IGNORECASE):
        return set(), []
    found=[]; owners=set()
    for alias, ids in aliases.items():
        boundary='' if re.search(r'[\u3400-\u9fff]',alias) else r'(?<!\w)'
        pattern=(boundary+_alias_pattern(alias, compatible)+r"(?:['’]s)?\s*(?:fiscal\s*|FY\s*)?"
                 r'(?:20\d{2}\s*年?\s*)?(?:Form\s+)?(?:annual\s+report|10-?[KQ]|年报|季度报告)(?![A-Za-z])')
        for match in re.finditer(pattern,query,re.IGNORECASE):
            owners.update(ids);found.append(match.group())
        if dated_reports:
            dated = (boundary+_alias_pattern(alias, compatible)+r'\s*截至\s*(?:20\d{2}年\s*\d{1,2}月\s*\d{1,2}日|20\d{2}-\d{2}-\d{2})'
                     r'\s*的?\s*(?:10-?Q|季度报告|季度披露|季报)(?![A-Za-z])')
            for match in re.finditer(dated, query, re.I):
                from retrieval.query_report_period import explicit_report_period
                if explicit_report_period(match.group()):
                    owners.update(ids);found.append(match.group())
            english_dated = (boundary+_alias_pattern(alias, compatible)+r"(?:['’]s|['’])?\s+[A-Za-z]+\s+\d{1,2},?\s+20\d{2}\s+(?:Form\s+)?10-?[KQ](?![A-Za-z])")
            for match in re.finditer(english_dated, query, re.I):
                from retrieval.fact_period_matching import dates
                if dates(match.group()):
                    owners.update(ids);found.append(match.group())
    return owners,found


def plan_query(query, metadata, *, policy='conservative.v1'):
    if policy not in {'conservative.v1', 'conservative.v2', 'conservative.v3', 'conservative.v4', 'conservative.v5'}:
        raise ValueError('unsupported_organization_query_plan')
    original_query = query
    exclusions = []
    if policy == 'conservative.v5':
        from retrieval.query_requirements import positive_view
        query, exclusions = positive_view(query)
        from retrieval.catalog_company_identity import with_original_registrant_identity
        metadata={d:with_original_registrant_identity(row) for d,row in metadata.items()}
    aliases, names = {}, {}
    named_issuers = {}
    from retrieval.catalog_company_identity import aliases_for, name_key, owners_for_row
    for row in metadata.values():
        if row.get('issuer_id'):
            for alias in aliases_for(row):
                named_issuers.setdefault(name_key(alias), set()).add(row['issuer_id'])
    for row in metadata.values():
        issuer, name = row.get('issuer_id'), row.get('company_name')
        if issuer and policy in {'conservative.v1','conservative.v2'}:
            # Only literal catalog identifiers; never infer a ticker/company
            # association from body text, graph counterparties or a URL.
            tail = issuer.split('::')[-1].replace('_', ' ').strip()
            if len(tail) >= 3:
                aliases.setdefault(tail.casefold(), set()).add(issuer)
        if name:
            owners = owners_for_row(row, named_issuers)
            for owner in owners:
                names.setdefault(owner, set()).add(name)
                aliases.setdefault(name.casefold(), set()).add(owner)
        if policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'}:
            for alias in aliases_for(row):
                owners = owners_for_row(row, named_issuers)
                aliases.setdefault(alias.casefold(), set()).update(owners)
            if issuer:
                names.setdefault(issuer,set()).update(row.get('verified_company_names') or [])
                names[issuer].update(row.get('joint_registrant_names') or [])
    matches = [(a, owners) for a, owners in aliases.items() if _mentions(query, a)]
    mentions = []
    if policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'}:
        matches, mentions = _compatible_mentions(query, aliases, bilingual_boundaries=policy=='conservative.v5')
    owners = set().union(*(v for _, v in matches)) if matches else set()
    from retrieval.catalog_company_identity import verified_issuer_groups, joint_reporting_targets
    joint_targets=joint_reporting_targets(query,metadata) if policy=='conservative.v5' else {}
    identity_group=next((g for g in verified_issuer_groups(metadata)
                         if owners and owners<=set(g['issuer_ids'])),None) if policy=='conservative.v5' else None
    unresolved, evidence, constraint = [], [], {}
    report_owners, report_phrases = _report_owners(query,
        dict(matches) if policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'} else aliases,
        allow_comparison=policy!='conservative.v1', compatible=policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'},
        dated_reports=policy=='conservative.v5')
    comparison = re.search(r'\b(?:compare|comparison|versus|vs\.?)\b|对比|比较|两家公司|各自', query, re.I)
    if (policy != 'conservative.v1' and len(owners)>1 and comparison and report_phrases
            and comparison.start() < min(query.casefold().find(p.casefold()) for p in report_phrases)):
        # "Compare Alpha and Beta annual report" modifies both owners, not
        # just the last name adjacent to the report noun.
        report_owners = set()
    from retrieval.query_report_period import comparison_starts_with_date, explicit_report_period
    temporal_comparison = bool(policy == 'conservative.v5' and comparison and comparison_starts_with_date(query, comparison.end()))
    if temporal_comparison:
        evidence.append({'field':'issuer', 'basis':'comparison_object_is_explicit_date_not_another_issuer'})
    explicit_joint_comparison=len(owners)==1 and len(joint_targets.get(next(iter(owners)),[]))>1
    if (policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'} and comparison
            and len(owners) == 1 and not temporal_comparison and not explicit_joint_comparison):
        # "In Alpha's report, compare ..." has an explicit owner before the
        # comparison. "Compare Unknown and Alpha ..." does not justify a
        # one-company scope, even if only Alpha is present in the catalog.
        explicit_before = bool(report_phrases) and min(
            query.casefold().find(p.casefold()) for p in report_phrases) < comparison.start()
        if not explicit_before:
            owners, report_owners = set(), set()
            unresolved.append('comparison_only_one_catalog_owner_no_issuer_filter')
    if len(report_owners)==1:
        owners=report_owners
        evidence.append({'field':'issuer','matched_query_text':report_phrases,
                         'basis':'explicit_report_owner_not_counterparty'})
    if len(owners) == 1 and identity_group is None:
        owner = next(iter(owners))
        constraint['company_names'] = sorted(names.get(owner, set()))
        if not owner.startswith('name:'):
            constraint['issuer_id'] = owner
        evidence.append({'field': 'issuer', 'matched_query_text': sorted(a for a, ids in matches if owner in ids),
                         'basis': 'literal_authorized_catalog_identity'})
    elif (policy != 'conservative.v1' and owners and all(len(ids) == 1 for _, ids in matches)
          and (comparison or len(report_owners)>1)):
        constraint['issuer_union'] = [dict(issuer_id=None if owner.startswith('name:') else owner,
            company_names=sorted(names.get(owner, set()))) for owner in sorted(owners)]
        evidence.append({'field':'issuer_union', 'matched_query_text':sorted(a for a,_ in matches),
                         'basis':'explicit_comparison_of_unambiguous_catalog_owners'})
    elif owners and identity_group:
        constraint['issuer_union']=[{'issuer_id':owner,'company_names':sorted(names.get(owner,set()))}
                                    for owner in identity_group['issuer_ids']]
        evidence.append({'field':'issuer_union','basis':'verified_original_identity_compatibility',
            'proof':identity_group,'wire_ids_unchanged':True})
    elif owners:
        unresolved.append('multiple_or_ambiguous_issuers_no_issuer_filter')
        if policy == 'conservative.v5' and not comparison:
            # Duplicate parse IDs for one exact original can use an explicit
            # common name scope. Never merge those IDs across other filings.
            from retrieval.filing_document_identity import original_filing_key
            filing_owners = {}
            for row in metadata.values():
                key = original_filing_key(row.get('original_filing_key'))
                if key and row.get('issuer_id'):
                    filing_owners.setdefault(key,set()).add(row['issuer_id'])
            common = set.intersection(*(set(names.get(o,())) for o in owners)) if owners else set()
            if common and any(owners <= ids for ids in filing_owners.values()):
                constraint['company_names'] = sorted(common)
                unresolved.remove('multiple_or_ambiguous_issuers_no_issuer_filter')
                evidence.append({'field':'company_names','basis':'same_original_multiple_parse_ids_common_name',
                                 'issuer_ids_not_merged':True})
    else:
        unresolved.append('no_unambiguous_literal_catalog_issuer')
    form_pattern = (r'(?<![A-Za-z0-9_-])(?:10-?[KQ]|8-?K)(?:\s*/A)?(?![A-Za-z0-9_/-])'
                    if policy == 'conservative.v5' else r'(?<![\w-])(?:10-?[KQ]|8-?K)(?:\s*/A)?(?![\w/-])')
    forms = sorted(set(m.group().upper().replace(' ', '') for m in re.finditer(
        form_pattern, query, re.IGNORECASE)))
    forms = [re.sub(r'^(10|8)([KQ])', r'\1-\2', f) for f in forms]
    forms = sorted(set(forms))
    excluded_forms = sorted({re.sub(r'^(10|8)([KQ])', r'\1-\2', m.group().upper().replace(' ', ''))
        for span in exclusions for m in re.finditer(form_pattern, span['text'], re.I)})
    if excluded_forms:
        constraint['excluded_forms'] = excluded_forms
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
    if policy == 'conservative.v5':
        report_years.update(re.findall(
            r'(?:\bannual\s+report|年报|年度报告|\b10-?K(?:\s*/A)?)\s*(?:for\s+)?(?:FY\s*|fiscal\s+(?:year\s+)?)?'
            r'((?:19|20)\d{2})(?![\d-])', query, re.I))
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
    if policy == 'conservative.v5' and 'period_end' not in constraint and (report_period := explicit_report_period(query)):
        constraint['period_end'] = report_period['value']
        evidence.append({'field':'period_end', **report_period})
        unresolved = [v for v in unresolved if v != 'year_or_publication_date_not_mapped_to_period_end']
    if policy == 'conservative.v5':
        from retrieval.query_document_date import document_date
        labelled_date=document_date(query,constraint.get('form'))
        if labelled_date:
            constraint['document_date']=labelled_date['value']
            evidence.append({'field':'document_date',**labelled_date})
    result = {'policy': policy, 'constraint': constraint, 'evidence': evidence,
              'unresolved': unresolved, 'unknown_metadata_retained': True}
    if policy == 'conservative.v5':
        result['joint_reporting_entity_targets']=joint_targets
        if any(owner in joint_targets and not joint_targets[owner] for owner in owners):
            unresolved.append('joint_filing_reporting_entity_not_explicit')
        entity_ids={}
        for row in metadata.values():
            if row.get('issuer_id'):
                entity_ids.setdefault(row['issuer_id'],set()).update(
                    (v['scheme'],v['identifier']) for v in row.get('fact_entity_identifiers',[]))
        # Conflicting IDs under one catalog issuer remain unresolved. No
        # borrowing the largest/most frequent context from a joint filing.
        result['fact_entity_by_issuer']={issuer:[{'scheme':scheme,'identifier':identifier}]
            for issuer,values in entity_ids.items() if len(values)==1 and issuer not in joint_targets
            for scheme,identifier in values}
    if exclusions:
        result['query_requirements'] = {'original_query':original_query,
            'positive_constraint_view':query, 'exclusions':exclusions,
            'semantics':'excluded_terms_do_not_create_positive_constraints_original_query_retained'}
    if policy in {'conservative.v3', 'conservative.v4', 'conservative.v5'}:
        result['issuer_mentions'] = mentions
        result['issuer_matching'] = 'catalog_name_compatibility_longest_mention.v2'
    if policy != 'conservative.v1':
        # A bare "2025 report" does not establish a filing form or fiscal
        # endpoint. It can prefer an independently cover-verified report year
        # when selecting evidence, without excluding uncertain sources.
        years = set(re.findall(r'(?<!\d)((?:19|20)\d{2})\s*(?:年)?\s*(?:reports?|报告)(?![A-Za-z])', query, re.I))
        if len(years) == 1 and len(set(re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', query))) == 1:
            result['preferences'] = {'verified_report_year':next(iter(years)),
                'basis':'explicit_report_year_soft_preference_no_fiscal_or_form_inference'}
    return result


def document_constraint_states(metadata, plan):
    """Proven document matches and unknowns remain distinct after recall.

    Unknown catalog rows may be retrieved, but cannot prove that a requested
    filing identity was satisfied merely by containing a matching fact date.
    """
    if plan['policy'] == 'conservative.v5':
        from retrieval.filing_document_identity import with_document_issuer_aliases
        from retrieval.same_original_metadata import resolve
        metadata = with_document_issuer_aliases(resolve(metadata))
    else:
        metadata = {k:{field:value for field,value in row.items() if field != 'same_document_issuer_ids'}
                    for k,row in metadata.items()}
    from retrieval.catalog_company_identity import document_names
    wanted = plan['constraint']
    states = {}
    for document, row in metadata.items():
        checks = []
        if 'issuer_union' in wanted:
            actual_id, actual_name = row.get('issuer_id'), row.get('company_name')
            owners = wanted['issuer_union']
            ids = {o['issuer_id'] for o in owners if o['issuer_id']}
            names = {name.casefold() for o in owners for name in o['company_names']}
            if actual_id and all(o['issuer_id'] for o in owners):
                checks.append(actual_id in ids or bool(ids & set(row.get('same_document_issuer_ids', []))))
            elif names and document_names(row):
                actual_names = {n.casefold() for n in document_names(row)}
                checks.append(bool(actual_names & names))
            else:
                checks.append(None)
        if ('form' in wanted or 'report_kind' in wanted) and row.get('evidence_role') == 'discovery_metadata_only':
            # Discovery remains available for general/news navigation. It
            # cannot satisfy an explicit request for an original filing/report,
            # even if a parent filing form was copied into its metadata.
            checks.append(False)
        if 'issuer_id' in wanted or wanted.get('company_names'):
            names = {n.casefold() for n in wanted.get('company_names', [])}
            actual_id, actual_name = row.get('issuer_id'), row.get('company_name')
            if actual_id and wanted.get('issuer_id'):
                checks.append(actual_id == wanted['issuer_id'] or wanted['issuer_id'] in row.get('same_document_issuer_ids', []))
            elif names and document_names(row):
                actual_names = {n.casefold() for n in document_names(row)}
                checks.append(bool(actual_names & names))
            else:
                checks.append(None)
        for field in ('form', 'period_end'):
            if field in wanted:
                checks.append(row.get(field) == wanted[field] if row.get(field) else None)
        if wanted.get('document_date'):
            from retrieval.query_document_date import matches_document_date
            checks.append(matches_document_date(row,wanted['document_date']))
        if wanted.get('excluded_forms'):
            checks.append(row['form'] not in wanted['excluded_forms'] if row.get('form') else None)
        if 'report_kind' in wanted:
            kind = REPORT_KINDS.get(row.get('form'))
            checks.append(kind == wanted['report_kind'] if kind else None)
        if 'annual_report_year' in wanted:
            year = row.get('calendar_annual_year')
            checks.append(year == wanted['annual_report_year'] if year else None)
        states[document] = 'mismatch' if False in checks else 'unknown' if None in checks else 'match'
    return states


def select_planned(metadata, plan):
    states = document_constraint_states(metadata, plan)
    accepted = {document for document, state in states.items() if state != 'mismatch'}
    unknown = sum(state == 'unknown' for state in states.values())
    return accepted, {**plan, 'scope_sources': len(metadata), 'selected_sources': len(accepted),
                      'unknown_sources_retained': unknown, 'excluded_sources': len(metadata)-len(accepted)}
