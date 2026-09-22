"""Offline relation candidates, independent review receipts and source-bound import.

Workers propose facts. This module checks provenance and binds the review to the
exact candidate file. It does not treat schema validity as semantic verification.
"""
from contextlib import closing
from datetime import date
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .counterparty_facts import Fact, import_reviewed, validate_evidence_values


PREDICATES = {
    'supplies': 'supply', 'provides_cloud_services_to': 'supply',
    'supplies_power_to': 'supply', 'hosts_model_for': 'cooperation',
    'commercial_partnership': 'cooperation', 'technology_licensing': 'cooperation',
    'invests_in': 'investment', 'owns_equity_in': 'investment',
    'parent_of': 'control', 'controls': 'control', 'acquired': 'control', 'operates': 'control',
    'leases_to': 'supply', 'builds_for': 'supply', 'finances': 'investment', 'guarantees': 'investment',
    'distributes': 'cooperation', 'competes_with': 'competition',
    'acts_as_trustee': 'cooperation',
    'provides_capital_markets_services': 'cooperation',
}

# Report categories identify the reporting issuer independently of the named
# parties in a transaction. A linked counterparty article is not issuer-owned.
ISSUER_REPORT_CATEGORIES = {'filing', 'filing_exhibit', 'official_report', 'annual_report'}

SCHEMA = '''
CREATE TABLE IF NOT EXISTS relationship_extraction_jobs(
 job_id TEXT PRIMARY KEY, job_digest TEXT NOT NULL, reviewer TEXT NOT NULL,
 reviewed_at TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relationship_assertions(
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES relationship_extraction_jobs(job_id),
 source_id TEXT NOT NULL REFERENCES sources(id), subject TEXT REFERENCES entities(id),
 object TEXT REFERENCES entities(id), predicate TEXT NOT NULL,
 status TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS relationship_coverage(
 entity_id TEXT NOT NULL REFERENCES entities(id), job_id TEXT NOT NULL,
 category TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(entity_id,job_id,category));
CREATE INDEX IF NOT EXISTS relationship_assertions_subject ON relationship_assertions(subject);
CREATE INDEX IF NOT EXISTS relationship_assertions_object ON relationship_assertions(object);
'''


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Evidence(Strict):
    passage_id: str
    quote: str = Field(min_length=1, max_length=12000)


class Term(Strict):
    metric: str
    value: Decimal
    unit: str
    operator: Literal['=', '<', '<=', '>', '>=', 'approximately']
    basis: str
    evidence_quote: str


class Relation(Strict):
    subject_name: str = Field(min_length=1)
    subject_id: str | None = None
    predicate: str
    object_name: str = Field(min_length=1)
    object_id: str | None = None
    status: Literal['current_as_reported', 'announced', 'agreement', 'planned',
                    'completed', 'historical', 'terminated']
    role: str = Field(min_length=1)
    scope_note: str = Field(min_length=1)
    products: list[str] = Field(default_factory=list)
    source_id: str
    valid_from: date | None = None
    valid_to: date | None = None
    observation_date: date | None = None
    terms: list[Term] = Field(default_factory=list)
    evidence: list[Evidence] = Field(min_length=1)


class CategoryCoverage(Strict):
    status: Literal['extracted', 'checked_no_explicit_fact', 'processing_pending',
                    'source_unavailable', 'parse_failed', 'not_applicable']
    detail: str = Field(min_length=1)


def coverage_sections(value):
    # Legacy extraction workers sometimes emit a single label. Normalize the
    # envelope here; do not ask the research model to redo semantic work.
    labels = [value] if isinstance(value, str) else value
    if not isinstance(labels, list) or not labels or any(not isinstance(x, str) or not x.strip() for x in labels):
        raise ValueError('source_review_sections_invalid')
    return labels


def validate_coverage(db, job):
    scope = set(job['company_ids'])
    for entity_id in scope:
        if not db.execute('SELECT 1 FROM entities WHERE id=?', (entity_id,)).fetchone():
            raise ValueError('coverage_unknown_entity:' + entity_id)
    covered = set()
    for item in job.get('coverage', []):
        if item['entity_id'] not in scope or item['entity_id'] in covered:
            raise ValueError('coverage_entity_scope')
        covered.add(item['entity_id'])
        if set(item['categories']) != {'customers', 'suppliers', 'investment_control', 'cooperation'}:
            raise ValueError('coverage_categories_incomplete')
        for state in item['categories'].values(): CategoryCoverage.model_validate(state)
        checked = set()
        for source in item['sources_reviewed']:
            sid = source['source_id']
            if not source.get('sections_checked') or not source.get('method'):
                raise ValueError('source_review_scope_missing')
            coverage_sections(source['sections_checked'])
            if not db.execute('SELECT 1 FROM sources WHERE id=?', (sid,)).fetchone():
                raise ValueError('coverage_unknown_source:' + sid)
            for pid in source['passage_ids']:
                if not db.execute('SELECT 1 FROM passages WHERE id=? AND source_id=?', (pid, sid)).fetchone():
                    raise ValueError('coverage_passage_mismatch:' + pid)
            checked.add(sid)
        if checked.intersection(item['remaining_source_ids']):
            raise ValueError('source_marked_both_reviewed_and_remaining')
        for sid in item['remaining_source_ids']:
            if not db.execute('SELECT 1 FROM sources WHERE id=?', (sid,)).fetchone():
                raise ValueError('coverage_unknown_remaining_source:' + sid)
    if scope != covered:
        raise ValueError('coverage_missing_company')


def digest_json(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode()).hexdigest()


def _normalize_name(value):
    return re.sub(r'[^\w]', '', value.casefold())


def bind_evidence(db, source_id, evidence):
    source = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
    if not source or source['access_state'] != 'readable':
        raise ValueError('source_not_readable:' + source_id)
    bound = []
    for item in evidence:
        item = Evidence.model_validate(item)
        passage = db.execute('SELECT source_id,body,locator FROM passages WHERE id=?',
                             (item.passage_id,)).fetchone()
        if not passage or passage['source_id'] != source_id:
            raise ValueError('evidence_source_mismatch:' + item.passage_id)
        start = passage['body'].find(item.quote)
        if start < 0:
            raise ValueError('evidence_quote_not_exact:' + item.passage_id)
        bound.append({'passage_id': item.passage_id, 'start': start,
                      'end': start + len(item.quote), 'quote': item.quote,
                      'locator': passage['locator']})
    return dict(source), bound


def prepare_job(db, job):
    """Read-only mechanical checks; return candidates and typed failures."""
    if job.get('version') != 'relation_extraction.v1':
        raise ValueError('unsupported_extraction_version')
    known = {r['id']: dict(r) for r in db.execute('SELECT * FROM entities')}
    provisional = {}
    errors = []
    try:
        validate_coverage(db, job)
    except (KeyError, ValueError) as exc:
        errors.append({'kind': 'coverage', 'index': 0, 'error': str(exc)})
    for index, entity in enumerate(job.get('new_entities', [])):
        try:
            pid = entity['provisional_id']
            if not pid.startswith('LOCAL::') or pid in provisional:
                raise ValueError('invalid_provisional_identity')
            if entity['kind'] not in {'company', 'investment_institution', 'fund', 'project', 'product', 'agency', 'person', 'government'}:
                raise ValueError('invalid_entity_kind')
            anchors = []
            for ev in entity['identity_evidence']:
                _, a = bind_evidence(db, ev['source_id'],
                    [{'passage_id': ev['passage_id'], 'quote': ev['quote']}])
                anchors.extend(a)
            if not anchors or not any(_normalize_name(entity['name']) in _normalize_name(a['quote']) for a in anchors):
                raise ValueError('identity_name_not_in_evidence')
            eid = 'DISCOVERED::' + digest_json([entity['kind'], _normalize_name(entity['name'])])[:24]
            collisions = [r['id'] for r in known.values()
                          if r['id'] != eid and _normalize_name(r['name']) == _normalize_name(entity['name'])]
            if collisions:
                raise ValueError('existing_identity_requires_resolution:' + ','.join(collisions))
            provisional[pid] = dict(entity, id=eid, bound_evidence=anchors)
        except (KeyError, ValueError) as exc:
            errors.append({'kind': 'entity', 'index': index, 'error': str(exc)})

    def resolve(identifier):
        if identifier is None:
            return None
        if identifier in known:
            return identifier
        if identifier in provisional:
            return provisional[identifier]['id']
        raise ValueError('unknown_entity:' + identifier)

    relations = []
    for index, raw in enumerate(job.get('relations', [])):
        try:
            relation = Relation.model_validate(raw)
            if relation.predicate not in PREDICATES:
                raise ValueError('unknown_predicate')
            source, evidence = bind_evidence(db, relation.source_id,
                                            [a.model_dump() for a in relation.evidence])
            text = ' '.join(e['quote'] for e in evidence)
            metadata = json.loads(source['metadata'])
            for name, identifier in ((relation.subject_name, relation.subject_id), (relation.object_name, relation.object_id)):
                # Issuer-owned original disclosures use "we" and need not repeat
                # the issuer's name in every table row. Related-material links
                # alone do not establish reporting identity.
                reporter = (identifier is not None and metadata.get('entity_id') == identifier
                            and metadata.get('category') in ISSUER_REPORT_CATEGORIES)
                if not reporter and _normalize_name(name) not in _normalize_name(text):
                    raise ValueError('counterparty_name_not_in_evidence:' + name)
            for term in relation.terms:
                if term.evidence_quote not in text:
                    raise ValueError('term_evidence_not_bound')
                # Scaling/units are reviewed semantically. Never silently rewrite.
            subject, target = resolve(relation.subject_id), resolve(relation.object_id)
            if subject and subject == target:
                raise ValueError('self_relation_requires_identity_review')
            payload = relation.model_dump(mode='json')
            payload.update(subject=subject, object=target, evidence=evidence,
                           family=PREDICATES[relation.predicate], published_at=source['published_at'],
                           source_title=source['title'], source_url=source['url'])
            identity = {k: v for k, v in payload.items() if k not in {'evidence', 'source_title', 'source_url'}}
            payload['id'] = 'RELATION::' + digest_json(identity)[:32]
            # Retrieval provenance is not a new relationship identity. An
            # undated original is usable from its verified capture date onward;
            # that date must never masquerade as publication or event time.
            known_at = metadata.get('known_at') or metadata.get('captured_at')
            captured = str(known_at)[:10] if known_at else None
            revision = source['vintage'] in {'known_as_of', 'current_revision'}
            payload['known_as_of'] = (captured or source['published_at']) if revision else (source['published_at'] or captured)
            payload['date_basis'] = 'published' if payload['known_as_of'] == source['published_at'] else 'captured'
            payload['reporting_entity_id'] = metadata.get('entity_id') if metadata.get('category') in ISSUER_REPORT_CATEGORIES else None
            relations.append({'index': index, 'payload': payload})
        except (KeyError, ValueError) as exc:
            errors.append({'kind': 'relation', 'index': index, 'error': str(exc)})

    disclosures = []
    for index, raw in enumerate(job.get('disclosures', [])):
        try:
            _, evidence = bind_evidence(db, raw['source_id'], raw['evidence'])
            fact = dict(raw, evidence=[{k: v for k, v in a.items() if k != 'locator'} for a in evidence])
            fact['counterparty_entity_id'] = resolve(fact.get('counterparty_entity_id'))
            typed_fact = Fact.model_validate(fact)
            validate_evidence_values(typed_fact)
            fact = typed_fact.model_dump(mode='json')
            if fact['entity_id'] not in known:
                raise ValueError('unknown_disclosure_subject')
            disclosures.append({'index': index, 'payload': fact})
        except (KeyError, ValueError) as exc:
            errors.append({'kind': 'disclosure', 'index': index, 'error': str(exc)})
    return {'job_digest': digest_json(job), 'relations': relations,
            'disclosures': disclosures, 'new_entities': list(provisional.values()), 'errors': errors}


def import_job(db, job, review):
    """Import accepted candidates only; no claims of completeness are inferred."""
    prepared = prepare_job(db, job)
    if review.get('job_digest') != prepared['job_digest'] or not review.get('reviewer'):
        raise ValueError('review_not_bound_to_job')
    if review.get('reviewer') == job.get('job_id'):
        raise ValueError('independent_reviewer_required')
    date.fromisoformat(review['reviewed_at'])
    approved = {}
    for kind, field in [('relation', 'relations'), ('disclosure', 'disclosures')]:
        verdicts = review.get(kind + '_verdicts', {})
        if set(verdicts) != {str(i) for i in range(len(job.get(field, [])))}:
            raise ValueError('review_coverage_incomplete:' + kind)
        if any(v.get('status') not in {'approved', 'rejected', 'needs_revision'}
               or not str(v.get('reason', '')).strip() for v in verdicts.values()):
            raise ValueError('invalid_candidate_verdict:' + kind)
        approved[field] = [r['payload'] for r in prepared[field]
                          if verdicts[str(r['index'])]['status'] == 'approved']
        for error in prepared['errors']:
            if error['kind'] == kind and verdicts[str(error['index'])]['status'] == 'approved':
                raise ValueError('approved_candidate_failed_validation:' + str(error))
    if any(e['kind'] in {'entity', 'coverage'} for e in prepared['errors']):
        raise ValueError('entity_or_coverage_validation_failed')
    coverage_verdicts = review.get('coverage_verdicts', {})
    scope = {c['entity_id']: c for c in job.get('coverage', [])}
    for eid, verdict in coverage_verdicts.items():
        if eid not in scope or verdict.get('status') not in {'complete', 'partial', 'not_reviewed'} or not str(verdict.get('reason', '')).strip():
            raise ValueError('invalid_scope_verdict')
        if verdict['status'] == 'complete' and (scope[eid]['remaining_source_ids'] or any(
                c['status'] in {'processing_pending', 'parse_failed'} for c in scope[eid]['categories'].values()) or any(
                gap.get('kind') in {'processing_pending', 'parse_failed'} for gap in scope[eid].get('gaps', []))):
            raise ValueError('complete_scope_has_unfinished_work')
    for statement in SCHEMA.split(';'):
        if statement.strip(): db.execute(statement)
    with db:
        old = db.execute('SELECT job_digest FROM relationship_extraction_jobs WHERE job_id=?', (job['job_id'],)).fetchone()
        if old and old[0] != prepared['job_digest']:
            raise ValueError('job_identity_conflict_use_new_revision')
        db.execute('INSERT OR REPLACE INTO relationship_extraction_jobs VALUES(?,?,?,?,?)',
                   (job['job_id'], prepared['job_digest'], review['reviewer'], review['reviewed_at'],
                    json.dumps({'job': job, 'review': review, 'mechanical_errors': prepared['errors']}, ensure_ascii=False)))
        used = {r[k] for r in approved['relations'] for k in ('subject', 'object')}
        used.update(f.get('counterparty_entity_id') for f in approved['disclosures'])
        for entity in prepared['new_entities']:
            if entity['id'] not in used:
                continue
            db.execute('INSERT OR IGNORE INTO entities VALUES(?,?,?)', (entity['id'], entity['kind'], entity['name']))
            for alias in {entity['name'], *entity.get('aliases', [])}:
                db.execute('INSERT OR IGNORE INTO aliases VALUES(?,?)', (alias, entity['id']))
            card = {'entity_id': entity['id'], 'name': entity['name'], 'profile_type': entity['kind'],
                    'roles': [entity['kind']], 'products': [], 'source_links': {},
                    'selection_reason': '从已核实关系发现的交易对手，尚未开展完整公司覆盖',
                    'business': entity.get('business'), 'sic_description': entity.get('business'),
                    'identity_basis': entity['identity_evidence'],
                    'coverage_scope': 'counterparty_identity_only', 'listing_status': 'to_verify'}
            db.execute('INSERT OR IGNORE INTO company_cards VALUES(?,?,?,?,?,?)',
                       (entity['id'], entity.get('industry') or '关系发现主体', '', 'to_verify', 3, json.dumps(card, ensure_ascii=False)))
        for payload in approved['relations']:
            state = 'reviewed' if payload['subject'] and payload['object'] else 'identity_unresolved'
            payload.update(review_status=state, reviewer=review['reviewer'], reviewed_at=review['reviewed_at'])
            db.execute('INSERT OR REPLACE INTO relationship_assertions VALUES(?,?,?,?,?,?,?,?)',
                       (payload['id'], job['job_id'], payload['source_id'], payload['subject'], payload['object'],
                        payload['predicate'], state, json.dumps(payload, ensure_ascii=False)))
            if state != 'reviewed' or not payload['known_as_of']:
                continue
            # Assertion ID preserves role/event/source. UI may group without deleting evidence.
            qualifiers = {k: v for k, v in payload.items() if k not in {'id', 'subject', 'object', 'predicate'}}
            db.execute('INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (payload['id'], payload['subject'], payload['predicate'], payload['object'], payload['source_id'],
                        payload['evidence'][0]['locator'], payload['known_as_of'], payload['valid_from'], payload['valid_to'],
                        payload['status'], json.dumps(qualifiers, ensure_ascii=False)))
            for eid in (payload['subject'], payload['object']):
                db.execute('INSERT OR IGNORE INTO entity_sources VALUES(?,?,?)', (eid, payload['source_id'], 'relationship_announcement'))
        for coverage in job.get('coverage', []):
            scope_review=review.get('coverage_verdicts',{}).get(coverage['entity_id'],
                {'status':'not_reviewed','reason':'Only emitted assertions have been reviewed; source coverage and extraction recall remain unaccepted.'})
            coverage=dict(coverage,coverage_review=scope_review)
            for category, state in coverage['categories'].items():
                db.execute('INSERT OR REPLACE INTO relationship_coverage VALUES(?,?,?,?,?)',
                           (coverage['entity_id'], job['job_id'], category, state['status'], json.dumps(coverage, ensure_ascii=False)))
                db.execute('INSERT OR REPLACE INTO data_gaps VALUES(?,?,?,?,?)',
                           (coverage['entity_id'], 'relationship_processing:' + category,
                            'available' if scope_review['status']=='complete' and state['status'] in {'extracted','checked_no_explicit_fact'} and not coverage['remaining_source_ids']
                            else 'review_pending', json.dumps({'detail':state['detail'],'job_id':job['job_id'],'coverage_review':scope_review,
                            'remaining_source_ids':coverage['remaining_source_ids'],'gaps':coverage.get('gaps',[])},ensure_ascii=False), review['reviewed_at']))
        # The disclosure importer shares this transaction: invalid numeric
        # evidence rolls back relations, entities and coverage as well.
        if approved['disclosures']:
            import_reviewed(db, {'version': 'counterparty_facts.v1', 'reviewed_by': review['reviewer'],
                                'review_note': 'Independent candidate review ' + job['job_id'], 'facts': approved['disclosures']},
                            manage_transaction=False)
    return {k: len(v) for k, v in approved.items()} | {'mechanical_errors': prepared['errors']}


def coverage_page(db, entity_id):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='relationship_coverage'").fetchone():
        return {'status': 'not_processed', 'jobs': []}
    rows = db.execute('SELECT DISTINCT job_id,payload FROM relationship_coverage WHERE entity_id=? ORDER BY job_id', (entity_id,))
    jobs = [dict(json.loads(r['payload']), job_id=r['job_id']) for r in rows]
    for job in jobs:
        job['sources_reviewed'] = [dict(s, sections_checked=coverage_sections(s['sections_checked']))
                                   for s in job.get('sources_reviewed', [])]
    return {'status': 'processing_recorded' if jobs else 'not_processed', 'jobs': jobs,
            'scope_notice': 'Each job names its inspected documents and remaining work. Processing is not proof that all real-world counterparties are known.'}


def assertion_page(db, entity_id, *, offset=0, limit=30, query='', as_of='9999-12-31'):
    if offset < 0 or not 1 <= limit <= 100: raise ValueError('invalid_relationship_window')
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='relationship_assertions'").fetchone():
        return {'items': [], 'total': 0, 'next_offset': None, 'status': 'not_processed'}
    where = """(a.subject=? OR a.object=? OR
      (json_extract(s.metadata,'$.entity_id')=? AND
       json_extract(s.metadata,'$.category') IN ('filing','filing_exhibit','official_report','annual_report')))
      AND s.access_state='readable'
      AND CASE WHEN s.vintage IN ('known_as_of','current_revision')
        THEN COALESCE(substr(json_extract(s.metadata,'$.known_at'),1,10),
                      substr(json_extract(s.metadata,'$.captured_at'),1,10),s.published_at,'9999-12-31')
        ELSE COALESCE(s.published_at,substr(json_extract(s.metadata,'$.known_at'),1,10),
                      substr(json_extract(s.metadata,'$.captured_at'),1,10),'9999-12-31') END<=?
      AND (?='' OR instr(lower(a.payload),lower(?))>0)"""
    args=(entity_id,entity_id,entity_id,as_of,query,query)
    total=db.execute('SELECT count(*) FROM relationship_assertions a JOIN sources s ON s.id=a.source_id WHERE '+where,args).fetchone()[0]
    rows=db.execute('SELECT a.payload FROM relationship_assertions a JOIN sources s ON s.id=a.source_id WHERE '+where+' ORDER BY s.published_at DESC,a.id LIMIT ? OFFSET ?',(*args,limit,offset))
    items=[]
    for row in rows:
        p=json.loads(row['payload'])
        # Extraction-local identifiers remain in the immutable job receipt, but
        # consumers must receive the same resolvable identities as the graph.
        p['subject_id']=p['subject']
        p['object_id']=p['object']
        # Full exact quotes stay in storage; context reads use bounded locators.
        p['evidence']=[{'passage_id':e['passage_id'],'locator':e['locator'],
                       'readback':{'source_space':'library','operation':'read','document_id':p['source_id'],
                                   'node_id':e['passage_id']}} for e in p['evidence']]
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='edge_chunk_links'").fetchone():
            chunks=[dict(r) for r in db.execute('SELECT DISTINCT c.id,c.source_id,c.parent_id,c.locator,l.binding FROM edge_chunk_links l JOIN retrieval_chunks c ON c.id=l.chunk_id WHERE l.edge_id=? ORDER BY c.parent_id,c.char_start LIMIT 20',(p['id'],))]
            p['parent_evidence']=p['evidence']
            p['chunk_evidence']=[dict(c,readback={'source_space':'library','operation':'read','document_id':c['source_id'],'node_id':c['id']}) for c in chunks]
            binding=db.execute('SELECT status,payload FROM edge_chunk_coverage WHERE edge_id=?',(p['id'],)).fetchone()
            p['chunk_binding']={'status':binding['status'],**json.loads(binding['payload'])} if binding else {'status':'not_published_identity_unresolved'}
        p['terms']=[{k:v for k,v in t.items() if k!='evidence_quote'} for t in p.get('terms',[])]
        items.append(p)
    return {'items':items,'total':total,'next_offset':offset+len(items) if offset+len(items)<total else None,'status':'ok'}


def check_file(library, job_file):
    with closing(sqlite3.connect(Path(library).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        db.row_factory = sqlite3.Row
        return prepare_job(db, json.loads(Path(job_file).read_text(encoding='utf8')))
