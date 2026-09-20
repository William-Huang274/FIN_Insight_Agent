"""Reviewed issuer facts, materialized before research, with exact passage anchors.

Schema/anchor validation is mechanical protection, not semantic approval. A
reviewer must check identity, table headers, qualifiers and reporting periods.
Unreviewed extraction candidates must never be imported by this entry point.
"""
from datetime import date
from decimal import Decimal
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SCHEMA = '''CREATE TABLE IF NOT EXISTS counterparty_facts(
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 category TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id),
 counterparty_entity_id TEXT REFERENCES entities(id), payload TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS counterparty_fact_lookup
 ON counterparty_facts(entity_id,category,source_id);'''


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Anchor(Strict):
    passage_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, max_length=6500)


class Measure(Strict):
    metric: Literal['revenue_share', 'procurement_share', 'beneficial_shares', 'ownership_share']
    value: Decimal = Field(ge=0)
    unit: Literal['percent', 'shares']
    operator: Literal['=', '<', '<=', '>=', '>']
    denominator: str = Field(min_length=1)
    measurement_as_of: date | None = None
    denominator_as_of: date | None = None

    @model_validator(mode='after')
    def units(self):
        if (self.metric == 'beneficial_shares') != (self.unit == 'shares'):
            raise ValueError('metric_unit_mismatch')
        if self.unit == 'percent' and self.value > 100:
            raise ValueError('percent_out_of_range')
        return self


class Fact(Strict):
    entity_id: str
    category: Literal['customers', 'suppliers', 'shareholders']
    source_id: str
    counterparty_name: str = Field(min_length=1)
    counterparty_entity_id: str | None = None
    identity_kind: Literal['named', 'anonymous', 'aggregate', 'population']
    relationship: Literal['direct_customer', 'indirect_customer', 'customer', 'supplier', 'beneficial_owner']
    role: str = Field(min_length=1)
    fiscal_year: int | None = None
    period_end: date | None = None
    observation_date: date | None = None
    count: int | None = Field(default=None, ge=1)
    measurement_basis: Literal['single', 'each', 'aggregate', 'population_bound', 'qualitative']
    segment: str | None = None
    estimated: bool = False
    measures: list[Measure] = Field(default_factory=list)
    scope_note: str = Field(min_length=1)
    evidence: list[Anchor] = Field(min_length=1)

    @model_validator(mode='after')
    def semantics(self):
        if self.identity_kind != 'named' and self.counterparty_entity_id:
            raise ValueError('anonymous_or_aggregate_cannot_link_company')
        allowed = {'customers': {'customer', 'direct_customer', 'indirect_customer'},
                   'suppliers': {'supplier'}, 'shareholders': {'beneficial_owner'}}
        if self.relationship not in allowed[self.category]:
            raise ValueError('relationship_category_mismatch')
        metrics={'customers':{'revenue_share'},'suppliers':{'procurement_share'},
                 'shareholders':{'beneficial_shares','ownership_share'}}
        if any(m.metric not in metrics[self.category] for m in self.measures):
            raise ValueError('metric_category_mismatch')
        if self.measures and not (self.fiscal_year or self.period_end or self.observation_date):
            raise ValueError('measured_fact_requires_period')
        if self.measurement_basis == 'each' and (self.count or 0) < 2:
            raise ValueError('each_requires_population_count')
        return self


class ReviewedPack(Strict):
    version: Literal['counterparty_facts.v1']
    reviewed_by: str = Field(min_length=1)
    review_note: str = Field(min_length=1)
    facts: list[Fact]


def import_reviewed(db, pack):
    """Validate the entire pack before atomic import; all source IDs stay intact."""
    pack = ReviewedPack.model_validate(pack)
    prepared = []
    for fact in pack.facts:
        source = db.execute('SELECT published_at,access_state FROM sources WHERE id=?', (fact.source_id,)).fetchone()
        if not source or source['access_state'] != 'readable':
            raise ValueError('source_not_readable')
        if not db.execute('SELECT 1 FROM entities WHERE id=?', (fact.entity_id,)).fetchone():
            raise ValueError('unknown_subject')
        if fact.counterparty_entity_id and not db.execute('SELECT 1 FROM entities WHERE id=?', (fact.counterparty_entity_id,)).fetchone():
            raise ValueError('unknown_counterparty')
        for anchor in fact.evidence:
            p = db.execute('SELECT source_id,body FROM passages WHERE id=?', (anchor.passage_id,)).fetchone()
            if not p or p['source_id'] != fact.source_id or p['body'][anchor.start:anchor.end] != anchor.quote:
                raise ValueError('evidence_anchor_mismatch')
        # Values must appear in evidence; this does not prove table alignment.
        # Keep cell/word separators: removing them fuses neighboring values.
        text = ' '.join(a.quote for a in fact.evidence).replace(',', '')
        normalize=lambda s:re.sub(r'\s+', ' ', s).casefold().replace(',', '')
        if fact.identity_kind=='named' and normalize(fact.counterparty_name) not in normalize(text):
            raise ValueError('named_counterparty_not_in_evidence')
        for m in fact.measures:
            number = format(m.value.normalize(), 'f')
            if not re.search(r'(?<![\d.])' + re.escape(number) + r'(?![\d.])', text):
                raise ValueError('value_not_in_evidence')
        payload = fact.model_dump(mode='json')
        identity = {k: v for k, v in payload.items() if k != 'evidence'}
        fid = 'COUNTERPARTY::' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:32]
        payload.update(id=fid, published_at=source['published_at'], review_status='reviewed',
                       reviewed_by=pack.reviewed_by, review_note=pack.review_note,
                       schema_version=pack.version, numeric_fact_authority=False,
                       value_basis='reviewed_issuer_disclosure_not_independent_audit')
        prepared.append((fid, fact, payload))
    db.executescript(SCHEMA)
    with db:
        supply_groups=set()
        for fid, fact, payload in prepared:
            db.execute('INSERT OR REPLACE INTO counterparty_facts VALUES(?,?,?,?,?,?)',
                       (fid, fact.entity_id, fact.category, fact.source_id, fact.counterparty_entity_id,
                        json.dumps(payload, ensure_ascii=False)))
            # Supply direction is supplier -> reporting buyer. No anonymous edge.
            if fact.relationship == 'supplier' and fact.counterparty_entity_id and payload['published_at']:
                supply_groups.add((fact.counterparty_entity_id,fact.entity_id,fact.source_id))
        for supplier,buyer,sid in sorted(supply_groups):
            records=[json.loads(r[0]) for r in db.execute('''SELECT payload FROM counterparty_facts
                WHERE counterparty_entity_id=? AND entity_id=? AND source_id=? AND category='suppliers' ''',(supplier,buyer,sid))]
            evidence=[a for r in records for a in r['evidence']]
            locator=db.execute('SELECT locator FROM passages WHERE id=?',(evidence[0]['passage_id'],)).fetchone()[0]
            eid='EDGE::SUPPLY::'+hashlib.sha256(json.dumps([supplier,buyer,sid]).encode()).hexdigest()[:32]
            roles=sorted({r['role'] for r in records})
            db.execute('INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (eid,supplier,'supplies',buyer,sid,locator,records[0]['published_at'],None,None,
                        'issuer_disclosed',json.dumps({'counterparty_fact_ids':[r['id'] for r in records],
                        'roles':roles,'role':'；'.join(roles),'ranking':'not_disclosed',
                        'as_of_report':records[0]['period_end'],'evidence':evidence},ensure_ascii=False)))
    return {'facts': len(prepared), 'sources': len({f.source_id for _, f, _ in prepared})}
