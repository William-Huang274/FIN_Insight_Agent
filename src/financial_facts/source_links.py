"""Match reviewed original facts to SQL observations without amount-only joins.

Callers supply verified source identities and explicitly known dimensions.
Unknown fields are not wildcards. This creates provenance, not authorization.
"""
from decimal import Decimal, InvalidOperation
import re

IDENTITY_FIELDS=('cik','accession','taxonomy','concept','unit','period_start','period_end','dimensions')


def match_original_fact(observation, original):
    missing=[f for f in (*IDENTITY_FIELDS,'value_decimal')
             if f not in observation or f not in original]
    if missing:return {'status':'unresolved','reason':'missing_identity_fields','fields':missing}
    for row in (observation,original):
        if any(not row[f] for f in IDENTITY_FIELDS if f not in {'period_start','dimensions'}):
            return {'status':'unresolved','reason':'empty_identity'}
        if not isinstance(row['dimensions'],dict):
            return {'status':'unresolved','reason':'unknown_dimensions'}
    mismatches=[f for f in IDENTITY_FIELDS if observation[f]!=original[f]]
    if mismatches:return {'status':'different_fact','fields':mismatches}
    try:
        if any(isinstance(r['value_decimal'],(float,bool)) for r in (observation,original)):
            raise ValueError('binary_float_is_not_exact_fact')
        left,right=(Decimal(r['value_decimal']) for r in (observation,original))
        if not left.is_finite() or not right.is_finite():raise ValueError('nonfinite')
    except (InvalidOperation,ValueError,TypeError):
        return {'status':'unresolved','reason':'invalid_exact_decimal'}
    if left!=right:return {'status':'conflict','reason':'same_identity_different_value'}
    if (not re.fullmatch(r'[0-9a-f]{64}',str(original.get('source_sha256','')))
            or not isinstance(original.get('locator'),dict) or not original['locator']
            or not observation.get('id')):
        return {'status':'unresolved','reason':'missing_original_locator_or_record_id'}
    return {'status':'matched','observation_id':observation['id'],
            'source_sha256':original['source_sha256'],'locator':original['locator'],
            'value_decimal':str(right),'identity':{k:original[k] for k in IDENTITY_FIELDS},
            'scope':'fact_provenance_not_footnote_applicability_or_access_grant'}
