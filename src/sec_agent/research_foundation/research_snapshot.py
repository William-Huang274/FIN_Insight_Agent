"""Read-only research qualification snapshots using SQLite/FTS5.

Not a production catalog migration. Source bodies retain their original IDs and
digests; graph traversal produces candidates, never an inferred financial fact.
"""
import json
import sqlite3
from contextlib import closing
from datetime import date
from hashlib import sha256
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE sources(id TEXT PRIMARY KEY, title TEXT NOT NULL, url TEXT NOT NULL,
 published_at TEXT, vintage TEXT NOT NULL, access_state TEXT NOT NULL,
 digest TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE passages(id TEXT PRIMARY KEY, source_id TEXT REFERENCES sources(id),
 locator TEXT NOT NULL, body TEXT NOT NULL, digest TEXT NOT NULL);
CREATE VIRTUAL TABLE passage_search USING fts5(id UNINDEXED, source_id UNINDEXED, body);
CREATE TABLE entities(id TEXT PRIMARY KEY, kind TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE aliases(alias TEXT, entity_id TEXT REFERENCES entities(id), PRIMARY KEY(alias,entity_id));
CREATE TABLE edges(id TEXT PRIMARY KEY, subject TEXT REFERENCES entities(id),
 predicate TEXT NOT NULL, object TEXT REFERENCES entities(id),
 source_id TEXT REFERENCES sources(id), locator TEXT NOT NULL, published_at TEXT NOT NULL,
 valid_from TEXT, valid_to TEXT, status TEXT NOT NULL, qualifiers TEXT NOT NULL);
CREATE TABLE observations(id TEXT PRIMARY KEY, kind TEXT NOT NULL, source_id TEXT REFERENCES sources(id),
 entity TEXT NOT NULL, period TEXT NOT NULL, unit TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE access_receipts(id INTEGER PRIMARY KEY, payload TEXT NOT NULL);
CREATE TABLE snapshot_metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def build_snapshot(path: Path, sources, passages, *, entities=(), edges=(), observations=(), receipts=()):
    """Fail on duplicate identities or foreign-key errors; never replace a snapshot."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create avoids racing another builder and preserves existing data.
    with path.open("xb"):
        pass
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript(SCHEMA)
        for s in sources:
            db.execute("INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)", (
                s['id'], s['title'], s['url'], s.get('published_at'), s['vintage'],
                s['access_state'], s['digest'], json.dumps(s.get('metadata', {}), ensure_ascii=False)))
        for p in passages:
            digest = sha256(p['body'].encode()).hexdigest()
            db.execute("INSERT INTO passages VALUES(?,?,?,?,?)", (p['id'], p['source_id'], p['locator'], p['body'], digest))
            db.execute("INSERT INTO passage_search VALUES(?,?,?)", (p['id'], p['source_id'], p['body']))
        for e in entities:
            db.execute("INSERT INTO entities VALUES(?,?,?)", (e['id'], e['kind'], e['name']))
            for alias in set([e['name'], *e.get('aliases', [])]):
                db.execute("INSERT INTO aliases VALUES(?,?)", (alias, e['id']))
        for e in edges:
            db.execute("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?,?,?,?)", (
                e['id'], e['subject'], e['predicate'], e['object'], e['source_id'],
                e['locator'], e['published_at'], e.get('valid_from'), e.get('valid_to'),
                e['status'], json.dumps(e.get('qualifiers', {}), ensure_ascii=False)))
        for o in observations:
            db.execute("INSERT INTO observations VALUES(?,?,?,?,?,?,?)", (
                o['id'], o['kind'], o['source_id'], o['entity'], o['period'], o['unit'],
                json.dumps(o['payload'], ensure_ascii=False)))
        db.executemany("INSERT INTO access_receipts(payload) VALUES(?)", [(json.dumps(r, ensure_ascii=False),) for r in receipts])
        db.execute("INSERT INTO snapshot_metadata VALUES('state','diagnostic_not_production')")
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'


class ResearchSnapshot:
    def __init__(self, path, *, time_mode='strict_as_of', knowledge_as_of=None):
        self.path = Path(path).resolve()
        if time_mode not in {'strict_as_of', 'retrospective'} or (time_mode=='retrospective' and knowledge_as_of is None):
            raise ValueError('invalid_snapshot_time_policy')
        if knowledge_as_of:
            date.fromisoformat(knowledge_as_of)
        self.time_mode, self.knowledge_as_of = time_mode, knowledge_as_of
        rows=self._query("SELECT value FROM snapshot_metadata WHERE key='state'")
        if rows != [{'value':'diagnostic_not_production'}]:
            raise ValueError('snapshot_not_complete')

    def _cutoff(self, as_of):
        date.fromisoformat(as_of)
        if self.time_mode=='retrospective':
            if self.knowledge_as_of < as_of:
                raise ValueError('knowledge_date_precedes_research_date')
            return self.knowledge_as_of
        return as_of

    def _vintages(self):
        return ('dated_original','known_as_of','current_revised') if self.time_mode=='retrospective' else ('dated_original','known_as_of')

    def _source(self, row, as_of):
        metadata=json.loads(row.get('metadata') or '{}')
        known=metadata.get('known_at')
        row['known_at']=known
        available=known if row['vintage'] in {'known_as_of','current_revised'} and known else row['published_at']
        row['eligible']=(row['access_state']=='readable' and available is not None
            and available <= self._cutoff(as_of) and row['vintage'] in self._vintages())
        return row

    def _query(self, sql, parameters=()):
        with closing(sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute(sql, parameters)]

    def catalog(self, as_of):
        # Unavailable and future items remain visible as gaps, not eligible evidence.
        rows = self._query('SELECT id,title,url,published_at,vintage,access_state,metadata FROM sources ORDER BY id')
        for r in rows:
            self._source(r,as_of)
        return rows

    def read(self, source_id, as_of, *, start=0, limit=8):
        if not 0 <= start or not 1 <= limit <= 40:
            raise ValueError('invalid_page_window')
        sources = self._query('SELECT * FROM sources WHERE id=?', (source_id,))
        if not sources:
            return {'status': 'unknown_source', 'source_id': source_id, 'items': []}
        s = self._source(sources[0],as_of)
        if s['access_state'] != 'readable':
            return {'status': s['access_state'], 'source': s, 'items': []}
        if not s['eligible']:
            return {'status': 'ineligible_vintage_or_date', 'source': s, 'items': []}
        items = self._query('SELECT * FROM passages WHERE source_id=? ORDER BY rowid LIMIT ? OFFSET ?', (source_id, limit+1, start))
        return {'status': 'readable', 'source': s, 'items': items[:limit],
                'next_start': start+limit if len(items) > limit else None}

    def search(self, terms, as_of, *, source_ids=(), limit=12):
        if not terms or not 1 <= limit <= 40:
            raise ValueError('empty_terms_or_invalid_limit')
        # Literal terms, no caller-authored SQL or FTS operators.
        expression = ' OR '.join('"' + str(t).replace('"', '""') + '"' for t in terms)
        eligible=[s['id'] for s in self.catalog(as_of) if s['eligible'] and (not source_ids or s['id'] in source_ids)]
        if not eligible:
            return []
        scope = ' AND s.id IN (' + ','.join('?' for _ in eligible) + ')'
        return self._query('SELECT p.id,p.source_id,p.locator,p.body,p.digest FROM passage_search f '
            'JOIN passages p ON p.id=f.id JOIN sources s ON s.id=p.source_id '
            "WHERE passage_search MATCH ?" + scope + ' ORDER BY bm25(passage_search) LIMIT ?',
            (expression, *eligible, limit))

    def related(self, entity_id, as_of):
        eligible={s['id'] for s in self.catalog(as_of) if s['eligible']}
        return [r for r in self._query("SELECT e.* FROM edges e "
            "WHERE (e.subject=? OR e.object=?) AND e.published_at<=? "
            "AND (e.valid_from IS NULL OR e.valid_from<=?) AND (e.valid_to IS NULL OR e.valid_to>=?)",
            (entity_id, entity_id, self._cutoff(as_of), as_of, as_of)) if r['source_id'] in eligible]

    def entities(self):
        return self._query('SELECT * FROM entities ORDER BY id')

    def observations(self, entity, as_of):
        eligible={s['id'] for s in self.catalog(as_of) if s['eligible']}
        rows = [r for r in self._query("SELECT * FROM observations WHERE entity=? ORDER BY period", (entity,)) if r['source_id'] in eligible]
        for r in rows:
            r['payload'] = json.loads(r['payload'])
        return rows
