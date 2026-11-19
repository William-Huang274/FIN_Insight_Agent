"""Explicit calculation lineage checks, not a natural-language research judge."""
import re


FACT_STATES = {
    'numeric_fact': {'numeric_fact'},
    'calculation': {'numeric_fact', 'non_authoritative_metric'},
    'inference': {'numeric_fact', 'non_authoritative_metric'},
    'hypothesis': {'numeric_fact', 'non_authoritative_metric', 'research_scenario'},
    'boundary': {'numeric_fact', 'non_authoritative_metric', 'research_scenario'},
    'reported_fact': set(),
}
KIND_DESCRIPTION = (
    'reported_fact restates issuer/source disclosure with PASSAGE evidence; it is not a derived result. '
    'numeric_fact requires an authoritative S2/NUMFACT. calculation uses an observed CALC and '
    'numeric_authority=non_authoritative. inference interprets evidence and may keep observed CALC '
    'in fact_ids with numeric_authority=not_applicable; hypothesis/boundary may also retain CALC. '
    'For mixed disclosure and analysis, choose the kind describing the actual assertion. '
    'Do not clear CALC bindings while retaining the dependent result or interpretation. '
    'A label change never verifies financial reasoning or arithmetic.'
)
CLASSIFICATION_OPTIONS = [
    {'kind': 'inference', 'numeric_authority': 'not_applicable',
     'when': 'The assertion interprets disclosure or an observed calculation; preserve supporting PASSAGE and CALC bindings.'},
    {'kind': 'calculation', 'numeric_authority': 'non_authoritative',
     'when': 'The assertion is the computed result; retain the observed verified CALC, source operands and assumptions.'},
]
CALC_ID = re.compile(r'CALC::[A-Za-z0-9][A-Za-z0-9_-]*(?:::[A-Za-z0-9][A-Za-z0-9_-]*)*')


def _claim_rows(submission):
    rows = submission.get('claims') or []
    return [(i, row) for i, row in enumerate(rows) if isinstance(row, dict)] if isinstance(rows, (list, tuple)) else []


def _fact_rows(claim):
    values = claim.get('fact_ids') or []
    return [(i, ref) for i, ref in enumerate(values) if isinstance(ref, str)] if isinstance(values, (list, tuple)) else []


def _uses(submission):
    uses = {}
    def add(value, location, claim_id=None):
        if isinstance(value, str):
            for source_id in dict.fromkeys(CALC_ID.findall(value)):
                uses.setdefault(source_id, []).append({'location': location, 'claim_id': claim_id})
        elif isinstance(value, (tuple, list)):
            for i, item in enumerate(value):
                add(item, [*location, i], claim_id)
    for field in ('thesis', 'mechanism', 'narrative_markdown', 'counterevidence', 'what_would_change'):
        add(submission.get(field), [field])
    for i, claim in _claim_rows(submission):
        for field in ('statement', 'authority_note', 'reasoning_summary'):
            add(claim.get(field), ['claims', i, field], claim.get('claim_id'))
    # Administrative task_note/reason_summary and verbatim source citation_quotes
    # are records, not assertions that their mentioned CALCs support this paper.
    return uses


def calculation_binding_issues(submission, notebook, prior=None):
    """Return current deterministic issues; saving treats these as advisories.

    No edits, category inference, alias guessing, formula detection or authority
    promotion. Immutable accepted history is not resubmitted by this function.
    """
    claims = _claim_rows(submission)
    refs = {r['ref_id']: r for obs in notebook.get('observations', []) for r in obs.get('references', [])}
    verified = {item.get('calculation_id') for obs in notebook.get('observations', [])
        if obs.get('status') == 'success' and not obs.get('failure') for item in obs.get('content', [])
        if item.get('result_state') == 'non_authoritative_metric'
        and item.get('arithmetic_verified') is True and item.get('numeric_fact_authority') is False}
    bound = {}
    for i, claim in claims:
        for j, ref in _fact_rows(claim):
            if ref.startswith('CALC::'):
                bound.setdefault(ref, []).append({'location': ['claims', i, 'fact_ids', j], 'claim_id': claim.get('claim_id')})
    uses = _uses(submission)
    current = {c['claim_id']: (i, c) for i, c in claims if c.get('claim_id')}
    removed = {}
    for _, claim in _claim_rows(prior or {}):
        if claim.get('claim_id') not in current:
            continue
        i, now = current[claim['claim_id']]
        for _, ref in _fact_rows(claim):
            if ref.startswith('CALC::') and ref not in (now.get('fact_ids') or []):
                removed.setdefault(ref, []).append({'location': ['claims', i, 'fact_ids'], 'claim_id': claim['claim_id']})
    issues = []
    def issue(code, ref, locations, instruction, *, blocking=True):
        locations = locations or [{'location': ['references'], 'claim_id': None}]
        issues.append({'code': code, 'type': 'calculation_binding', 'source_id': ref,
            'location': locations[0]['location'],
            'affected_locations': [r['location'] for r in locations],
            'claim_ids': sorted({r['claim_id'] for r in locations if r.get('claim_id')}),
            'removed_claim_ids': sorted({r['claim_id'] for r in removed.get(ref, [])}),
            'blocking': blocking, 'instruction': instruction,
            'classification_options': CLASSIFICATION_OPTIONS})
    for ref in sorted(bound.keys() | uses.keys()):
        locations = bound.get(ref) or uses[ref]
        observed = refs.get(ref)
        if observed is None:
            if ref not in bound:  # Existing unknown_fact_id check owns bound IDs.
                issue('calculation_reference_unobserved', ref, locations,
                    'This explicit CALC ID is not observed. Read/restore its actual receipt or calculate '
                    'from observed operands. Do not invent IDs or remove the ID while retaining its result.')
        elif (observed.get('authority_state') != 'non_authoritative_metric' or ref not in verified):
            issue('calculation_receipt_unverified', ref, locations,
                'A CALC used as support requires an observed, arithmetic-verified, non-authoritative '
                'receipt. Reclassifying as inference does not bypass this check. Restore or obtain the '
                'actual receipt; it does not certify financial meaning.')
        missing = [row for row in uses.get(ref, []) if row.get('claim_id') in current and
            ref not in (current[row['claim_id']][1].get('fact_ids') or [])]
        if missing or (ref in uses and ref not in bound):
            locations = missing or [*removed.get(ref, []), *uses[ref]]
            issue('calculation_binding_missing', ref, locations,
                'Current research text still explicitly uses this CALC, but its supporting claim '
                'binding is missing. Keep it in the appropriate claim fact_ids with its PASSAGE support '
                'and assumptions. Choose inference for interpretation or calculation for a computed '
                'result, according to meaning; do not change kind merely to pass. If genuinely retiring '
                'the calculation, revise the dependent assertion too, or rebind it to the appropriate '
                'claim. Deleting an ID alone does not resolve unsupported content.')
    for ref, locations in removed.items():
        if not any(r['source_id'] == ref and r['code'] == 'calculation_binding_missing' for r in issues):
            issue('calculation_binding_removed', ref, locations,
                'This save removes a prior CALC relationship. Check dependent assertions and retained '
                'assumptions; the original receipt remains archived. A deliberate retirement or move '
                'to another claim is allowed. No extra plan, note or explanation form is required.', blocking=False)
    return issues


def classification_issue(error, submission, notebook):
    """Locate an authority mismatch without deciding the author's semantic kind."""
    parts = error.split(':', 2)
    if len(parts) != 3:
        return None
    _, kind, ref = parts
    rows = [(i, claim, j) for i, claim in _claim_rows(submission)
            for j, value in _fact_rows(claim) if value == ref and claim.get('kind') == kind]
    locations = [['claims', i, 'fact_ids', j] for i, _, j in rows]
    observed = next((r for o in notebook.get('observations', []) for r in o.get('references', []) if r['ref_id'] == ref), None)
    return {'location': locations[0] if locations else ['references'], 'affected_locations': locations,
        'claim_ids': [c['claim_id'] for _, c, _ in rows], 'source_id': ref,
        'type': 'claim_reference_classification', 'message': error,
        'diagnosis': 'claim_kind_reference_authority_mismatch',
        'observed_authority': observed.get('authority_state') if observed else None,
        'classification_options': CLASSIFICATION_OPTIONS if ref.startswith('CALC::') else [],
        'instruction': 'The current kind does not admit this observed reference. Retain the actual '
            'source/calculation when it supports the assertion; select the semantically appropriate '
            'kind and numeric_authority using the supplied schema and options. Use update_claim with '
            'only changed fields. The runtime will not choose a kind for you, write conclusions, or '
            'promote a CALC to S2 authority.'}


def claim_shape_feedback(errors, submission):
    """Explain cross-field errors using the current claim, without editing it."""
    result = []
    claims = submission.get('claims') or []
    for error in errors:
        location = list(error['loc'])
        item = {'location': location, 'type': error['type'], 'message': error['msg']}
        if (len(location) >= 2 and location[0] == 'claims'
                and isinstance(location[1], int) and location[1] < len(claims)
                and any(code in error['msg'] for code in (
                    'non_numeric_claim_numeric_authority_invalid',
                    'calculation_requires_non_authoritative_disclosure',
                    'numeric_fact_requires_authoritative_fact'))):
            claim = claims[location[1]]
            calc_ids = [ref for _, ref in _fact_rows(claim) if ref.startswith('CALC::')]
            options = [dict(row) for row in CLASSIFICATION_OPTIONS]
            if not calc_ids:
                options.append({'kind': 'reported_fact', 'numeric_authority': 'not_applicable',
                    'when': 'The assertion only restates source disclosure; cite its PASSAGE. Non-S2 provenance belongs in authority_note.'})
            item.update(claim_id=claim.get('claim_id'),
                current_fields={k: claim.get(k) for k in ('kind', 'numeric_authority', 'fact_ids')},
                retained_calculation_ids=calc_ids, classification_options=options,
                edit={'op': 'update_claim', 'claim_id': claim.get('claim_id'),
                      'changed_fields': ['kind', 'numeric_authority']},
                instruction='Choose the pair matching the actual assertion, not merely to pass validation. '
                    'Use SaveWorkpaperEditsAction with the current draft digest and update_claim changes; '
                    'unchanged fact_ids and evidence_ids are retained. Keep CALC bindings while the '
                    'computed result or comparison remains. For separate disclosure and calculation '
                    'assertions, split them into source-bound reported_fact and calculation/inference '
                    'claims and move the CALC to its dependent claim, preserving related text and operands. '
                    'not_applicable describes the claim kind; it does not promote a source or CALC to S2. '
                    'The runtime does not select a classification or change conclusions.')
        result.append(item)
    return result
