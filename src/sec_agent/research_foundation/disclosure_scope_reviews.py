"""Source/category review receipts; absence within a scope is not nondisclosure.

The reviewer owns completeness and meaning. Exact anchors and source digests
prevent a receipt for one document from silently closing another document.
"""
from datetime import date
import json

from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .counterparty_facts import Anchor


SCHEMA = '''CREATE TABLE IF NOT EXISTS disclosure_scope_reviews(
 entity_id TEXT NOT NULL REFERENCES entities(id),
 source_id TEXT NOT NULL REFERENCES sources(id),
 category TEXT NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY(entity_id,source_id,category));'''


class ScopeReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    entity_id: str
    source_id: str
    source_digest: str
    category: Literal['customers', 'suppliers', 'shareholders']
    result: Literal['reviewed_facts', 'checked_no_explicit_fact']
    reviewed_sections: list[str] = Field(min_length=1)
    scope_note: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    reviewed_at: date
    evidence: list[Anchor] = Field(min_length=1)


def import_reviews(db, reviews):
    """Validate a whole batch, then persist in the caller's transaction."""
    prepared = []
    facts_installed = db.execute("SELECT 1 FROM sqlite_master WHERE name='counterparty_facts'").fetchone()
    for raw in reviews:
        r = ScopeReview.model_validate(raw)
        source = db.execute('SELECT digest,access_state FROM sources WHERE id=?', (r.source_id,)).fetchone()
        if not source or source['access_state'] != 'readable' or source['digest'] != r.source_digest:
            raise ValueError('scope_source_digest_or_availability')
        if not db.execute('SELECT 1 FROM entities WHERE id=?', (r.entity_id,)).fetchone():
            raise ValueError('scope_unknown_entity')
        if any(not s.strip() for s in r.reviewed_sections):
            raise ValueError('scope_empty_section')
        for a in r.evidence:
            p = db.execute('SELECT source_id,body FROM passages WHERE id=?', (a.passage_id,)).fetchone()
            if not p or p['source_id'] != r.source_id or p['body'][a.start:a.end] != a.quote:
                raise ValueError('scope_evidence_mismatch')
        exists = facts_installed and db.execute(
            'SELECT 1 FROM counterparty_facts WHERE entity_id=? AND source_id=? AND category=? LIMIT 1',
            (r.entity_id, r.source_id, r.category)).fetchone()
        if bool(exists) != (r.result == 'reviewed_facts'):
            raise ValueError('scope_result_contradicts_materialized_facts')
        prepared.append((r.entity_id, r.source_id, r.category, json.dumps(r.model_dump(mode='json'), ensure_ascii=False)))
    db.execute(SCHEMA)
    db.executemany('INSERT OR REPLACE INTO disclosure_scope_reviews VALUES(?,?,?,?)', prepared)
    return {'scope_reviews': len(prepared)}


def for_entity(db, entity_id, as_of):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='disclosure_scope_reviews'").fetchone():
        return {}
    rows = db.execute('''SELECT r.source_id,r.category,r.payload,s.title,s.published_at,
      CASE WHEN s.vintage IN ('known_as_of','current_revised')
        THEN coalesce(substr(json_extract(s.metadata,'$.known_at'),1,10),
                      substr(json_extract(s.metadata,'$.captured_at'),1,10),s.published_at)
        ELSE coalesce(s.published_at,substr(json_extract(s.metadata,'$.known_at'),1,10),
                      substr(json_extract(s.metadata,'$.captured_at'),1,10)) END known_as_of
      FROM disclosure_scope_reviews r JOIN sources s ON s.id=r.source_id
      WHERE r.entity_id=? AND s.access_state='readable' AND known_as_of<=?
        AND json_extract(r.payload,'$.source_digest')=s.digest''', (entity_id, as_of))
    return {(r['source_id'], r['category']): {**dict(r), 'review': json.loads(r['payload'])} for r in rows}
