"""Versioned research artifacts and adoption links, not a workflow engine.

SQLite owns atomic publication and optimistic concurrency. Existing native
sessions own execution; the model owns interpretation and semantic acceptance.
One database is scoped to one authorized root research thread.
"""
from contextlib import closing, contextmanager
import json
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_graph_contracts import canonical_sha256


class Adoption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic_id: str
    revision: int = Field(ge=1)
    digest: str
    use: Literal['adopted', 'qualified', 'challenged', 'background']
    rationale: str = Field(min_length=1, max_length=3000)


class ResearchWorkpaper(BaseModel):
    model_config = ConfigDict(extra='forbid')
    finding: str = Field(min_length=1, max_length=1800)
    body: str = Field(min_length=1, max_length=200000,
        description='Complete readable research deliverable: question, evidence, comparison, public reasoning and judgment. Not private chain of thought.')
    conditions: str = Field(min_length=1, max_length=4000)
    counterevidence: str = Field(min_length=1, max_length=4000)
    remaining: str = Field(min_length=1, max_length=4000)
    next_decision: str = Field(min_length=1, max_length=3000)
    disposition: Literal['continue', 'bounded_answer', 'awaiting_observation', 'access_blocked']
    change: str = Field(min_length=1, max_length=3000)
    dependencies: list[Adoption] = Field(default_factory=list, max_length=32)
    evidence_receipt_ids: list[str] = Field(default_factory=list, max_length=64)


class WorkpaperConflict(ValueError):
    """Correctable identity/version selection; never a storage error."""


class ResearchWorkpapers:
    def __init__(self, path, *, root_id, question, as_of, check):
        self.path, self.root_id, self.check = Path(path), root_id, check
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS identity (root TEXT PRIMARY KEY, question TEXT, as_of TEXT);
                CREATE TABLE IF NOT EXISTS topics (id TEXT PRIMARY KEY, parent TEXT, question TEXT);
                CREATE TABLE IF NOT EXISTS papers (topic TEXT, revision INTEGER, digest TEXT, payload TEXT,
                    PRIMARY KEY(topic,revision));
                CREATE TABLE IF NOT EXISTS events (sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT, revision INTEGER, kind TEXT);
                CREATE TABLE IF NOT EXISTS commands (id TEXT PRIMARY KEY, fingerprint TEXT, result TEXT);
                CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS reads (actor TEXT, topic TEXT, revision INTEGER,
                    PRIMARY KEY(actor,topic,revision));
                CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS bindings (report_digest TEXT PRIMARY KEY, snapshot TEXT);
            ''')
            identity = db.execute('SELECT * FROM identity').fetchall()
            if identity and identity != [(root_id, question, as_of)]:
                raise RuntimeError('research_workspace_identity_mismatch')
            db.execute('INSERT OR IGNORE INTO identity VALUES (?,?,?)', (root_id, question, as_of))
            db.execute('INSERT OR IGNORE INTO topics VALUES (?,?,?)', ('root', None, question))

    @contextmanager
    def connection(self):
        self.check()
        with closing(sqlite3.connect(self.path, timeout=10)) as db, db:
            db.execute('PRAGMA foreign_keys=ON')
            db.execute('BEGIN IMMEDIATE')
            yield db
            self.check()

    def register(self, topic_id, parent, question, *, reuse=False):
        if not topic_id or not question.strip():
            raise WorkpaperConflict('topic_identity_required')
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM topics WHERE id=?', (parent,)).fetchone():
                raise WorkpaperConflict('unknown_parent_topic')
            row = db.execute('SELECT parent,question FROM topics WHERE id=?', (topic_id,)).fetchone()
            if row and (row[0] != parent or (not reuse and row[1] != question)):
                raise WorkpaperConflict('topic_identity_changed')
            if reuse and not row:
                raise WorkpaperConflict('unknown_topic_to_continue')
            db.execute('INSERT OR IGNORE INTO topics VALUES (?,?,?)', (topic_id, parent, question))

    @staticmethod
    def _latest(db):
        return dict(db.execute('SELECT topic,MAX(revision) FROM papers GROUP BY topic'))

    @staticmethod
    def _get(db, topic, revision):
        row = db.execute('SELECT digest,payload FROM papers WHERE topic=? AND revision=?', (topic, revision)).fetchone()
        if not row:
            raise WorkpaperConflict('unknown_workpaper_version')
        payload = json.loads(row[1])
        if canonical_sha256(payload) != row[0]:
            raise RuntimeError('research_workpaper_integrity_failure')
        return {'topic_id': topic, 'revision': revision, 'digest': row[0], **payload}

    def _stale(self, db, paper, latest, seen=None):
        seen = set() if seen is None else seen
        identity = (paper['topic_id'], paper['revision'])
        if identity in seen:
            raise RuntimeError('research_dependency_cycle')
        seen = seen | {identity}
        problems = []
        for dep in paper['dependencies']:
            upstream = self._get(db, dep['topic_id'], dep['revision'])
            if upstream['digest'] != dep['digest']:
                raise RuntimeError('research_dependency_digest_mismatch')
            if latest.get(dep['topic_id']) != dep['revision']:
                problems.append({'adopted': dep, 'current_revision': latest.get(dep['topic_id'])})
            problems.extend(self._stale(db, upstream, latest, seen))
        return problems

    def publish(self, actor, base_revision, paper, evidence, command_id, *, assignment=None):
        paper = ResearchWorkpaper.model_validate(paper).model_dump(mode='json')
        fingerprint = canonical_sha256([actor, base_revision, paper, evidence, assignment])
        with self.connection() as db:
            prior = db.execute('SELECT fingerprint,result FROM commands WHERE id=?', (command_id,)).fetchone()
            if prior:
                if prior[0] != fingerprint:
                    raise WorkpaperConflict('publication_command_changed')
                return json.loads(prior[1])
            topic = db.execute('SELECT parent,question FROM topics WHERE id=?', (actor,)).fetchone()
            if topic is None:
                raise WorkpaperConflict('unknown_topic')
            latest = self._latest(db)
            if latest.get(actor, 0) != base_revision:
                raise WorkpaperConflict('workpaper_version_changed_read_current')
            if len({d['topic_id'] for d in paper['dependencies']}) != len(paper['dependencies']):
                raise WorkpaperConflict('one_explicit_version_per_dependency')
            for dep in paper['dependencies']:
                if dep['topic_id'] == actor:
                    raise WorkpaperConflict('self_dependency_use_change_field')
                upstream = self._get(db, dep['topic_id'], dep['revision'])
                if latest.get(dep['topic_id']) != dep['revision'] or self._stale(db, upstream, latest):
                    raise WorkpaperConflict('dependency_changed_reassess_current')
                if upstream['digest'] != dep['digest']:
                    raise WorkpaperConflict('dependency_digest_changed')
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                                  (actor, dep['topic_id'], dep['revision'])).fetchone():
                    raise WorkpaperConflict('read_dependency_before_adoption')
                # Versioned research can evolve, but current artifact adoption must not form a cycle.
                stack = [upstream]
                while stack:
                    item = stack.pop()
                    for d in item['dependencies']:
                        if d['topic_id'] == actor:
                            raise WorkpaperConflict('cyclic_adoption_restructure_shared_premise')
                        stack.append(self._get(db, d['topic_id'], d['revision']))
            if len(paper['evidence_receipt_ids']) != len(set(paper['evidence_receipt_ids'])):
                raise WorkpaperConflict('unique_evidence_receipts_required')
            if set(paper['evidence_receipt_ids']) != set(evidence):
                raise WorkpaperConflict('evidence_must_be_successfully_observed')
            for key, value in evidence.items():
                wire = json.dumps(value, ensure_ascii=False, sort_keys=True)
                old = db.execute('SELECT payload FROM evidence WHERE id=?', (key,)).fetchone()
                if old and old[0] != wire:
                    raise RuntimeError('evidence_identity_collision')
                db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?)', (key, wire))
            payload = {**paper, 'original_task': {'root_id': self.root_id, 'topic_id': actor,
                'parent_topic': topic[0], 'question': topic[1],
                'root_question': db.execute('SELECT question FROM identity').fetchone()[0],
                'assignment': assignment},
                'as_of': db.execute('SELECT as_of FROM identity').fetchone()[0]}
            digest = canonical_sha256(payload)
            revision = base_revision + 1
            db.execute('INSERT INTO papers VALUES (?,?,?,?)',
                       (actor, revision, digest, json.dumps(payload, ensure_ascii=False)))
            db.execute('INSERT INTO events(topic,revision,kind) VALUES (?,?,?)', (actor, revision, 'workpaper_published'))
            result = {'saved': True, 'topic_id': actor, 'revision': revision, 'digest': digest,
                'readback': {'tool': 'read_research_workpaper', 'arguments': {'topic_id': actor, 'revision': revision}},
                'meaning': 'Durably saved research proposal; not independent semantic approval.'}
            db.execute('INSERT INTO commands VALUES (?,?,?)', (command_id, fingerprint, json.dumps(result)))
            return result

    def read(self, actor, topic_id, revision=None, *, field='body', offset=0, max_characters=12000):
        if field not in {'body', 'metadata'} or offset < 0 or not 1 <= max_characters <= 24000:
            raise WorkpaperConflict('invalid_workpaper_window')
        with self.connection() as db:
            latest = self._latest(db)
            paper = self._get(db, topic_id, revision or latest.get(topic_id, 0))
            stale = self._stale(db, paper, latest)
            metadata = {k: v for k, v in paper.items() if k != 'body'}
            if field == 'metadata':
                return {**metadata, 'requires_reassessment': stale, 'current_revision': latest.get(topic_id)}
            if offset >= len(paper['body']):
                raise WorkpaperConflict('offset_outside_workpaper')
            db.execute('INSERT OR IGNORE INTO reads VALUES (?,?,?)', (actor, topic_id, paper['revision']))
            end = min(len(paper['body']), offset + max_characters)
            if offset:
                # Repeated windows keep semantic boundaries, not another copy of the task/dependency catalog.
                metadata = {k:metadata[k] for k in ('topic_id','revision','digest','finding','as_of',
                    'conditions','counterevidence','remaining','disposition')}
                metadata['metadata_readback'] = {'tool':'read_research_workpaper',
                    'arguments':{'topic_id':topic_id,'revision':paper['revision'],'field':'metadata'}}
            return {**metadata, 'body': paper['body'][offset:end], 'offset': offset,
                'next_offset': end if end < len(paper['body']) else None, 'total_characters': len(paper['body']),
                'requires_reassessment': stale, 'current_revision': latest.get(topic_id),
                'read_scope': 'Observed window, not proof of full reading or semantic acceptance.'}

    def catalog(self, *, after=0, limit=8):
        if after < 0 or not 1 <= limit <= 20:
            raise WorkpaperConflict('invalid_update_window')
        with self.connection() as db:
            latest = self._latest(db)
            rows = db.execute('SELECT sequence,topic,revision,kind FROM events WHERE sequence>? ORDER BY sequence LIMIT ?',
                              (after, limit)).fetchall()
            return {'updates': [{'sequence': seq, 'topic_id': topic, 'revision': rev, 'kind': kind,
                'current_revision': latest[topic],
                'readback': {'tool': 'read_research_workpaper', 'arguments': {'topic_id': topic, 'revision': rev, 'field': 'metadata'}}}
                for seq, topic, rev, kind in rows], 'next_cursor': rows[-1][0] if rows else after,
                'has_more': bool(rows and db.execute('SELECT 1 FROM events WHERE sequence>?', (rows[-1][0],)).fetchone()),
                'topics': [{'topic_id': key, 'parent_topic': parent, 'question': question,
                    'current_revision': latest.get(key),
                    'status': 'needs_reassessment' if key in latest and self._stale(db, self._get(db,key,latest[key]),latest)
                        else 'saved_proposal' if key in latest else 'not_yet_delivered'}
                    for key,parent,question in db.execute('SELECT id,parent,question FROM topics ORDER BY id')],
                'notice': 'Updates are asynchronous proposals. Read important changes; no count certifies coverage.'}

    def evidence(self, receipt_id):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM evidence WHERE id=?', (receipt_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_workpaper_evidence')
            return json.loads(row[0])

    def observed(self, actor, topic, revision):
        with self.connection() as db:
            return bool(db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                                   (actor,topic,revision)).fetchone())

    def prepare(self, actor, topics, rationale):
        """Freeze exact versions, including transitive dependencies; no full paper concatenation."""
        if actor != 'root' or not topics or not rationale.strip():
            raise WorkpaperConflict('root_synthesis_requires_selected_topics_and_scope_rationale')
        with self.connection() as db:
            latest = self._latest(db)
            selected, stack = {}, list(dict.fromkeys(topics))
            while stack:
                key = stack.pop()
                if key in selected:
                    continue
                paper = self._get(db, key, latest.get(key, 0))
                if self._stale(db, paper, latest):
                    raise WorkpaperConflict('synthesis_dependency_stale')
                selected[key] = {'revision': paper['revision'], 'digest': paper['digest']}
                stack.extend(d['topic_id'] for d in paper['dependencies'])
            payload = {'root_id': self.root_id, 'selected': selected, 'scope_rationale': rationale,
                'catalog_versions': latest, 'as_of': db.execute('SELECT as_of FROM identity').fetchone()[0]}
            key = canonical_sha256(payload)
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)', (key, json.dumps(payload, ensure_ascii=False)))
            return {'snapshot_id': key, **payload, 'next_step': 'Read selected complete argument windows with read_synthesis_material; then compose and check the whole report.'}

    def snapshot(self, snapshot_id):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_synthesis_snapshot')
            value = json.loads(row[0])
            if canonical_sha256(value) != snapshot_id:
                raise RuntimeError('synthesis_snapshot_integrity_failure')
            latest = self._latest(db)
            return {**value, 'changed_topics': [key for key in set(latest) | set(value['catalog_versions'])
                if latest.get(key) != value['catalog_versions'].get(key)]}

    def bind(self, snapshot_id, report_digest):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_synthesis_snapshot')
            snap = json.loads(row[0])
            if snap['catalog_versions'] != self._latest(db):
                raise WorkpaperConflict('research_changed_refresh_synthesis')
            for key, ref in snap['selected'].items():
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?', ('root',key,ref['revision'])).fetchone():
                    raise WorkpaperConflict('read_selected_argument_before_delivery')
            db.execute('INSERT OR REPLACE INTO bindings VALUES (?,?)', (report_digest,snapshot_id))
        return {'bound': True, 'snapshot_id': snapshot_id, 'report_digest': report_digest,
                'semantic_approval': False}

    def require_current_binding(self, report_digest):
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM papers').fetchone():
                return  # Unmigrated legacy task: preserve existing delivery contract.
            row = db.execute('SELECT snapshot FROM bindings WHERE report_digest=?', (report_digest,)).fetchone()
            if not row:
                raise WorkpaperConflict('bind_current_report_to_research_snapshot')
        if self.snapshot(row[0])['changed_topics']:
            raise WorkpaperConflict('research_changed_refresh_synthesis')
