"""Versioned source-scope reviews shared by metric readers and research tools.

Reviews qualify observations without rewriting previously published facts. A
bounded negative finding never asserts that an issuer has never disclosed it.
"""
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import sqlite3

from .industry_metrics import dumps, identity

OUTCOMES = {'resolved', 'bounded_not_found', 'source_access_blocked',
            'definition_boundary', 'precision_limit'}
SCHEMA = '''CREATE TABLE IF NOT EXISTS industry_metric_reviews(
 id TEXT PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id),
 field TEXT NOT NULL, reviewed_at TEXT NOT NULL, outcome TEXT NOT NULL,
 payload TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS metric_review_entity_date
 ON industry_metric_reviews(entity_id,reviewed_at);'''


def import_reviews(path, reviews, *, reviewed_at):
    """Append validated reviews, retaining prior versions and source identities."""
    date.fromisoformat(reviewed_at)
    if 'published' in Path(path).parts:
        raise ValueError('immutable_published_library')
    with closing(sqlite3.connect(path)) as db:
        state = db.execute("SELECT value FROM snapshot_metadata WHERE key='state'").fetchone()
        if state and state[0] == 'published_public_library.v1':
            raise ValueError('immutable_published_library')
        prepared = []
        for review in reviews:
            r = dict(review)
            if r['outcome'] not in OUTCOMES:
                raise ValueError('invalid_review_outcome')
            if not all(r.get(k) for k in ('entity_id', 'field', 'reason', 'next_action', 'comparison_rule', 'reviewed_materials')):
                raise ValueError('incomplete_metric_review')
            if not db.execute('SELECT 1 FROM company_cards WHERE entity_id=?', (r['entity_id'],)).fetchone():
                raise ValueError('unknown_review_entity')
            affected = r.get('affected_metrics', [])
            if not isinstance(affected, list) or any(not isinstance(m, str) for m in affected):
                raise ValueError('invalid_affected_metric_ids')
            for metric in affected:
                if not db.execute('SELECT 1 FROM industry_metric_observations WHERE metric=?', (metric,)).fetchone():
                    raise ValueError('unknown_review_metric_id')
            for material in r['reviewed_materials']:
                sid = material.get('source_id')
                if sid and not db.execute('SELECT 1 FROM sources WHERE id=?', (sid,)).fetchone():
                    raise ValueError('review_source_not_found')
                if not material.get('url', '').startswith(('https://', 'http://')) or not material.get('sections'):
                    raise ValueError('review_requires_source_and_scope')
            if r['outcome'] == 'resolved' and not r.get('completed_observation_ids'):
                raise ValueError('resolved_review_requires_observations')
            for rid in r.get('completed_observation_ids', []):
                if not db.execute('SELECT 1 FROM industry_metric_observations WHERE id=? AND entity_id=?', (rid, r['entity_id'])).fetchone():
                    raise ValueError('review_observation_not_found')
            for rule in r.get('series_rules', []):
                if not rule.get('metrics') or rule.get('action') not in {'separate_series', 'points_only'} or not rule.get('reason'):
                    raise ValueError('invalid_metric_series_rule')
                if not set(rule['metrics']).issubset(affected):
                    raise ValueError('series_rule_outside_affected_metrics')
                if set(rule) - {'metrics', 'action', 'reason', 'date_start', 'date_end', 'scope_contains', 'series_key'}:
                    raise ValueError('unknown_metric_rule_selector')
                for key in ('date_start', 'date_end'):
                    if rule.get(key): date.fromisoformat(rule[key])
                if rule['action'] == 'separate_series' and not rule.get('series_key'):
                    raise ValueError('series_rule_requires_key')
            r['reviewed_at'] = reviewed_at
            r['id'] = 'METRIC_REVIEW::' + identity(r)[:40]
            prepared.append(r)
        db.executescript(SCHEMA)
        with db:
            for r in prepared:
                db.execute('INSERT OR IGNORE INTO industry_metric_reviews VALUES(?,?,?,?,?,?)',
                           (r['id'], r['entity_id'], r['field'], reviewed_at, r['outcome'], dumps(r)))
        return len(prepared)


def read_reviews(db, entity_ids, as_of, metric=''):
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='industry_metric_reviews'").fetchone():
        return []
    latest = {}
    for eid in entity_ids:
        for row in db.execute('SELECT payload FROM industry_metric_reviews WHERE entity_id=? AND reviewed_at<=? ORDER BY reviewed_at,rowid', (eid, as_of)):
            r = json.loads(row[0])
            latest[(eid, r['field'])] = r
    return [r for r in latest.values() if not metric or metric in r.get('affected_metrics', [])]


def qualify_rows(rows, reviews):
    for row in rows:
        applicable = [r for r in reviews if r['entity_id'] == row['entity_id'] and row['metric'] in r.get('affected_metrics', [])]
        row['review_ids'] = [r['id'] for r in applicable]
        rules = []
        for r in applicable:
            for rule in r.get('series_rules', []):
                if row['metric'] not in rule['metrics']: continue
                day = row.get('observation_date') or ''
                if rule.get('date_start') and day < rule['date_start']: continue
                if rule.get('date_end') and day > rule['date_end']: continue
                if rule.get('scope_contains') and rule['scope_contains'] not in row.get('business_scope', ''): continue
                rules.append(rule)
        if rules:
            # Keep the original scope as part of the partition: a review cannot
            # accidentally join products that already had separate series.
            partitions = sorted({r['series_key'] for r in rules if r['action'] == 'separate_series'})
            if partitions:
                row['series_scope'] = (row.get('series_scope') or row.get('business_scope', '')) + ' | ' + ' | '.join(partitions)
            if any(r['action'] == 'points_only' for r in rules): row['chart_policy'] = 'points_only'
            row['comparison_rules'] = rules
        if applicable:
            row['comparison_note'] += ' 核查结论：' + '；'.join(dict.fromkeys(r['comparison_rule'] for r in applicable))
