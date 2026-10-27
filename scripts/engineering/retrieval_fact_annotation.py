"""One source-bound annotation envelope for legacy and typed fact reviews.

Normalization never upgrades a legacy citation review into a typed fact review.
Counterclaims ask for corrective evidence; this is not an answer/refusal scorer.
"""
from datetime import date, datetime
from hashlib import sha256
import json
import re


def normalize_question(question):
    review=question['label_review']
    facts=question.get('fact_review')
    return {'schema':'retrieval-fact-annotation.v1','question_id':question['id'],
        'query_sha256':sha256(question['query'].encode()).hexdigest(),
        'family':question['family'],'evidence':question['evidence'],
        'requirements':review['requirements'],'reviewer':review.get('reviewer'),
        'review_level':'typed_fact_reviewed' if facts and facts.get('status')=='reviewed' else 'clause_reviewed',
        'facts':facts,'legacy_review':review}


def validate_annotation(annotation, *, require_typed=False):
    if annotation.get('schema')!='retrieval-fact-annotation.v1' or not annotation.get('reviewer'):
        raise ValueError('fact_annotation_schema_or_reviewer')
    anchors={(e['source_id'],e['chunk_id']):e for e in annotation['evidence']}
    requirements=annotation['requirements']
    if not requirements or len({r['id'] for r in requirements})!=len(requirements):
        raise ValueError('fact_annotation_requirements')
    for r in requirements:
        if not r.get('citations'):raise ValueError('fact_annotation_citations_required')
        for c in r['citations']:
            a=anchors.get((c['source_id'],c['chunk_id']))
            if not a or c['body_sha256']!=a['body_sha256'] or not c['quote'].strip() or c['quote'] not in a['quote']:
                raise ValueError('fact_annotation_citation_binding')
    if annotation['review_level']!='typed_fact_reviewed':
        if require_typed:raise ValueError('typed_fact_review_required_no_automatic_upgrade')
        return
    f=annotation['facts']
    if not all(f.get(k) for k in ('entity','source_id','source_digest','unit','counterclaim','why_invalid','bindings')):
        raise ValueError('typed_fact_context_incomplete')
    if {c['source_id'] for r in requirements for c in r['citations']}!={f['source_id']}:
        raise ValueError('typed_fact_source_scope')
    text=' '.join(' '.join(c['quote'].split()) for r in requirements for c in r['citations'])
    for b in f['bindings']:
        if not all(b.get(k) for k in ('measure','entity_scope','period','display_value','unit','evidence_quote')):
            raise ValueError('typed_fact_binding_incomplete')
        if ' '.join(b['evidence_quote'].split()) not in text:
            raise ValueError('typed_fact_binding_quote_missing')
        # Exact display values, no scalar normalization that might hide units.
        if b['display_value'] not in ' '.join(b['evidence_quote'].split()):
            raise ValueError('typed_fact_display_value_missing')
        p=b['period']
        if p['kind'] in {'instant','event','reported_quarter_end'}:
            if date.fromisoformat(p['value']).isoformat()!=p['value']:raise ValueError('typed_fact_date')
        elif p['kind'] not in {'event','fiscal_quarter','fiscal_year','year_to_date','undated_statement','reported_quarter_end'}:
            raise ValueError('typed_fact_period_kind')
        if not p.get('value') or not p.get('meaning'):raise ValueError('typed_fact_period_meaning')
        pieces=b.get('period_quotes') or [b.get('period_quote','')]
        if not pieces or any(not v or ' '.join(v.split()) not in text for v in pieces):
            raise ValueError('typed_fact_period_quote_missing')
        period_quote=' '.join(' '.join(v.split()) for v in pieces)
        if p['kind'] in {'instant','event','reported_quarter_end'}:
            possible=[]
            for pattern in ('%B %d, %Y','%b %d, %Y','%Y-%m-%d'):
                try:possible.append(datetime.strptime(period_quote,pattern).date().isoformat())
                except ValueError:pass
            if p['value'] not in possible:raise ValueError('typed_fact_date_quote_mismatch')
        if not b.get('unit_quote') or b['unit_quote'] not in text:
            raise ValueError('typed_fact_unit_quote_missing')
        if b['unit'].startswith('USD '):
            scale=b['unit'][4:].rstrip('s')
            if scale not in {'million','billion','thousand'} or not re.search(r'\b'+scale+r's?\b',b['unit_quote'],re.I):
                raise ValueError('typed_fact_unit_scale_mismatch')


def annotation_digest(annotations):
    return sha256(json.dumps(annotations,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
