"""Reviewed issuer facts, materialized before research, with exact passage anchors.

Schema/anchor validation is mechanical protection, not semantic approval. A
reviewer must check identity, table headers, qualifiers and reporting periods.
Unreviewed extraction candidates must never be imported by this entry point.
"""
from datetime import date
from contextlib import nullcontext
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
    metric: Literal['revenue_share', 'receivables_share', 'procurement_share', 'cost_of_sales_share', 'beneficial_shares', 'ownership_share',
                    'annualized_recurring_revenue', 'annualized_recurring_revenue_share', 'revenue_amount',
                    'procurement_amount', 'voting_power_share']
    value: Decimal = Field(ge=0)
    unit: Literal['percent', 'shares', 'USD', 'CNY', 'HKD', 'TWD', 'KRW',
                  'JPY', 'EUR', 'GBP', 'SGD', 'MYR', 'INR', 'AUD', 'CAD',
                  'CHF', 'AED', 'SAR']
    scale: Decimal = Field(default=Decimal('1'), gt=0)
    operator: Literal['=', '<', '<=', '>=', '>', 'approximately']
    denominator: str = Field(min_length=1)
    measurement_as_of: date | None = None
    denominator_as_of: date | None = None

    @model_validator(mode='after')
    def units(self):
        if (self.metric == 'beneficial_shares') != (self.unit == 'shares'):
            raise ValueError('metric_unit_mismatch')
        monetary = self.unit not in {'percent', 'shares'}
        if (self.metric in {'annualized_recurring_revenue', 'revenue_amount', 'procurement_amount'}) != monetary:
            raise ValueError('amount_unit_mismatch')
        if not monetary and self.scale != 1:
            raise ValueError('non_monetary_scale')
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
        metrics={'customers':{'revenue_share','receivables_share','annualized_recurring_revenue','annualized_recurring_revenue_share','revenue_amount'},'suppliers':{'procurement_share','cost_of_sales_share','procurement_amount'},
                 'shareholders':{'beneficial_shares','ownership_share','voting_power_share'}}
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


def import_reviewed(db, pack, *, manage_transaction=True):
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
        text = ' '.join(a.quote for a in fact.evidence)
        normalize=lambda s:re.sub(r'\s+', ' ', s).casefold().replace(',', '')
        if fact.identity_kind=='named' and normalize(fact.counterparty_name) not in normalize(text):
            raise ValueError('named_counterparty_not_in_evidence')
        # Compare decimal tokens, so source 10.0 and extracted Decimal('10')
        # agree without accepting a substring of 110.0 or joining table cells.
        numbers = {Decimal(token.replace(',', '')) for token in re.findall(
            r'(?<![\w.])-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\d.])', text)}
        for m in fact.measures:
            if m.value not in numbers:
                raise ValueError('value_not_in_evidence')
        payload = fact.model_dump(mode='json')
        # Adding a default unit multiplier must not change existing fact IDs.
        for measure in payload['measures']:
            if Decimal(measure.get('scale', '1')) == 1: measure.pop('scale', None)
        identity = {k: v for k, v in payload.items() if k != 'evidence'}
        fid = 'COUNTERPARTY::' + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:32]
        payload.update(id=fid, published_at=source['published_at'], review_status='reviewed',
                       reviewed_by=pack.reviewed_by, review_note=pack.review_note,
                       schema_version=pack.version, numeric_fact_authority=False,
                       value_basis='reviewed_issuer_disclosure_not_independent_audit')
        prepared.append((fid, fact, payload))
    # execute (unlike executescript) does not commit a caller's transaction.
    for statement in SCHEMA.split(';'):
        if statement.strip(): db.execute(statement)
    with db if manage_transaction else nullcontext():
        changed_ids=[]
        for fid, fact, payload in prepared:
            db.execute('INSERT OR REPLACE INTO counterparty_facts VALUES(?,?,?,?,?,?)',
                       (fid, fact.entity_id, fact.category, fact.source_id, fact.counterparty_entity_id,
                        json.dumps(payload, ensure_ascii=False)))
            changed_ids.append(fid)
        project_relationships(db, fact_ids=changed_ids)
    return {'facts': len(prepared), 'sources': len({f.source_id for _, f, _ in prepared})}


def project_relationships(db, *, fact_ids=None):
    """Project reviewed named facts; anonymous concentrations remain facts only.

    This is a deterministic view of already-reviewed identities, not another
    extraction or an inference that an indirect customer purchases directly.
    The caller owns the transaction, including when refreshing an older corpus.
    """
    predicates={'supplier':'supplies', 'direct_customer':'direct_customer_of',
                'indirect_customer':'indirect_customer_of', 'customer':'customer_of',
                'beneficial_owner':'disclosed_shareholder_of'}
    rows=db.execute('SELECT payload FROM counterparty_facts').fetchall()
    selected=None if fact_ids is None else set(fact_ids)
    groups={}; touched=set()
    for row in rows:
        p=json.loads(row[0])
        if p.get('review_status')!='reviewed' or p.get('identity_kind')!='named' or not p.get('counterparty_entity_id'):
            continue
        key=(p['counterparty_entity_id'],p['entity_id'],p['source_id'],p['relationship'])
        groups.setdefault(key,[]).append(p)
        if selected is None or p['id'] in selected: touched.add(key)
    count=0
    for supplier,buyer,sid,relationship in sorted(touched):
            records=groups[(supplier,buyer,sid,relationship)]
            source=db.execute('SELECT published_at,vintage,metadata,access_state FROM sources WHERE id=?',(sid,)).fetchone()
            if not source or source['access_state']!='readable': continue
            metadata=json.loads(source['metadata'] or '{}')
            captured=metadata.get('known_at') or metadata.get('captured_at')
            known=(captured or source['published_at']) if source['vintage'] in {'known_as_of','current_revision'} else (source['published_at'] or captured)
            if not known: continue
            known=str(known)[:10]
            evidence=[a for r in records for a in r['evidence']]
            locator=db.execute('SELECT locator FROM passages WHERE id=?',(evidence[0]['passage_id'],)).fetchone()[0]
            # Preserve existing supplier projection identities.
            identity=[supplier,buyer,sid] if relationship=='supplier' else [supplier,buyer,sid,relationship]
            eid=('EDGE::SUPPLY::' if relationship=='supplier' else 'EDGE::DISCLOSURE::')+hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:32]
            roles=sorted({r['role'] for r in records})
            db.execute('INSERT OR REPLACE INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                       (eid,supplier,predicates[relationship],buyer,sid,locator,known,None,None,
                        'issuer_disclosed',json.dumps({'counterparty_fact_ids':[r['id'] for r in records],
                        'roles':roles,'role':'；'.join(roles),'ranking':'not_disclosed',
                        'relationship':relationship,'published_at':source['published_at'],
                        'known_as_of':known,'date_basis':'published' if known==source['published_at'] else 'known_as_of',
                        'periods':[{'fiscal_year':r.get('fiscal_year'),'period_end':r.get('period_end'),'observation_date':r.get('observation_date')} for r in records],
                        'as_of_report':records[0]['period_end'],'evidence':evidence},ensure_ascii=False)))
            count+=1
    return count
