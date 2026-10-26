"""Reviewed fact requirements: OR alternatives, AND citations and requirements.

This checks source binding and declared numeric precision, not automated table
understanding. A reviewer must attest column ownership and financial meaning.
Labels never enter query planning or ranking. Preserve the old strict ID score.
"""
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re

SCALES = {'ones': 1, 'thousands': 1000, 'millions': 1000000, 'billions': 1000000000}


def quantity(value):
    try:
        number = Decimal(value['value'].replace(',', ''))
        resolution = Decimal(value['resolution'])
        scale = SCALES[value['scale']]
    except (KeyError, AttributeError, InvalidOperation):
        raise ValueError('invalid_reviewed_quantity') from None
    if not number.is_finite() or not resolution.is_finite() or resolution <= 0:
        raise ValueError('invalid_reviewed_quantity')
    return number * scale, resolution * scale


def review_requirements(contract, originals):
    """originals maps stable node IDs to hash-verified published source bodies."""
    if contract.get('schema') != 'reviewed-fact-requirements.v1':
        raise ValueError('unsupported_fact_requirements')
    requirements = contract['requirements']
    ids = [r['id'] for r in requirements]
    if not ids or not all(ids) or len(set(ids)) != len(ids):
        raise ValueError('invalid_fact_requirement_ids')
    validated = []
    for requirement in requirements:
        context = requirement['context']
        if any(not context.get(k) for k in ('source_id', 'source_digest', 'entity', 'period', 'measure')):
            raise ValueError('incomplete_fact_context')
        alternatives = []
        for alternative in requirement['alternatives']:
            if not alternative.get('reviewer') or alternative.get('review') != 'original_scope_units_and_precision_checked':
                raise ValueError('fact_original_review_required')
            if alternative['context'] != context:
                raise ValueError('fact_period_entity_measure_or_revision_mismatch')
            citations = alternative['citations']
            if not citations:
                raise ValueError('fact_citations_required')
            for citation in citations:
                original = originals[citation['node_id']]
                if (original['source_id'] != context['source_id'] or
                        original['source_digest'] != context['source_digest'] or
                        sha256(original['body'].encode()).hexdigest() != citation['body_sha256']):
                    raise ValueError('fact_original_binding_mismatch')
                if not citation['quote'].strip() or citation['quote'] not in original['body']:
                    raise ValueError('fact_quote_missing')
            status = 'complete'
            if 'quantity' in requirement:
                expected, allowed_resolution = quantity(requirement['quantity'])
                actual, resolution = quantity(alternative['quantity'])
                if alternative['quantity']['currency'] != requirement['quantity']['currency']:
                    raise ValueError('fact_currency_mismatch')
                # Explicit original value and unit quote are mandatory. The
                # reviewer owns the relation to the particular column/date.
                quotes = ' '.join(' '.join(c['quote'].split()) for c in citations)
                observed = alternative['quantity']
                if (observed['value'] not in quotes or not observed.get('unit_quote')
                        or observed['unit_quote'] not in quotes):
                    raise ValueError('fact_quantity_not_quoted')
                declared_resolution = Decimal(observed['resolution'])
                displayed_resolution = Decimal(1).scaleb(Decimal(observed['value'].replace(',', '')).as_tuple().exponent)
                unit_patterns = {'ones': r'\b(?:USD|dollars?)\b', 'thousands': r'\bthousands?\b',
                                 'millions': r'\bmillions?\b', 'billions': r'\bbillions?\b'}
                if (declared_resolution < displayed_resolution or not re.search(
                        unit_patterns[observed['scale']], observed['unit_quote'], re.I)):
                    raise ValueError('fact_precision_or_scale_not_supported_by_quote')
                if abs(actual - expected) > max(resolution, allowed_resolution) / 2:
                    status = 'value_mismatch'
                elif resolution > allowed_resolution:
                    status = 'precision_insufficient'
            alternatives.append({'nodes': sorted({c['node_id'] for c in citations}), 'status': status})
        if not alternatives or not any(a['status'] == 'complete' for a in alternatives):
            raise ValueError('requirement_has_no_complete_reference')
        validated.append({'id': requirement['id'], 'alternatives': alternatives})
    return validated


def score_requirements(ranked, validated, k=10):
    selected = set(ranked[:k])
    outcomes = []
    for requirement in validated:
        hits = [a['status'] for a in requirement['alternatives'] if set(a['nodes']) <= selected]
        status = ('complete' if 'complete' in hits else 'precision_insufficient'
                  if 'precision_insufficient' in hits else 'value_mismatch' if hits else 'missing')
        outcomes.append({'id': requirement['id'], 'status': status})
    return {'requirements': outcomes,
            'complete_fraction': sum(r['status'] == 'complete' for r in outcomes) / len(outcomes),
            'all_complete': all(r['status'] == 'complete' for r in outcomes),
            'scope': 'reviewed_known_facts_not_exhaustive_relevance_or_answer_quality'}
