"""Versioned research artifacts and adoption links, not a workflow engine.

SQLite owns atomic publication and optimistic concurrency. Existing native
sessions own execution; the model owns interpretation and semantic acceptance.
One database is scoped to one authorized root research thread.
"""
from contextlib import closing, contextmanager, nullcontext
import json
import sqlite3
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .research_graph_contracts import canonical_sha256
from .research_decision_context import Counterexample, quote_location


class Adoption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    topic_id: str
    revision: int = Field(ge=1)
    digest: str
    use: Literal['adopted', 'qualified', 'challenged', 'background'] = Field(
        description='Background is historical orientation, not a premise of the current conclusion. '
        'Use adopted, qualified or challenged for material the argument relies on; its changes require reassessment.')
    rationale: str = Field(min_length=1, max_length=3000)


class ResearchWorkpaper(BaseModel):
    model_config = ConfigDict(extra='forbid')
    finding: str = Field(min_length=1, max_length=1800)
    body: str = Field(min_length=1, max_length=200000,
        description='Complete readable research deliverable: question, evidence, comparison, public reasoning and judgment. Not private chain of thought.')
    conditions: str = Field(min_length=1, max_length=4000)
    counterevidence: str = Field(min_length=1, max_length=4000)
    remaining: str = Field(min_length=1, max_length=4000)
    decision_uncertainty: str | None = Field(default=None, min_length=1, max_length=3000,
        description='Which remaining observation could change direction, timing, scale or the next investigation?')
    competing_explanation: str | None = Field(default=None, min_length=1, max_length=3000,
        description='A live alternative explanation and the observation that distinguishes it.')
    decisive_passages: list[Counterexample] | None = Field(default=None,
        description='Original observations that materially challenge the finding. Pair exact quotes with your counterevidence.')
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
                CREATE TABLE IF NOT EXISTS assessment_evidence (topic TEXT, revision INTEGER, reviewer TEXT, payload TEXT,
                    PRIMARY KEY(topic,revision,reviewer));
                CREATE TABLE IF NOT EXISTS execution_observations (id TEXT PRIMARY KEY, actor TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS reads (actor TEXT, topic TEXT, revision INTEGER,
                    PRIMARY KEY(actor,topic,revision));
                CREATE TABLE IF NOT EXISTS snapshots (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS bindings (report_digest TEXT PRIMARY KEY, snapshot TEXT);
                CREATE TABLE IF NOT EXISTS organization_policy (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT);
            ''')
            identity = db.execute('SELECT * FROM identity').fetchall()
            if identity and identity != [(root_id, question, as_of)]:
                raise RuntimeError('research_workspace_identity_mismatch')
            db.execute('INSERT OR IGNORE INTO identity VALUES (?,?,?)', (root_id, question, as_of))
            db.execute('INSERT OR IGNORE INTO topics VALUES (?,?,?)', ('root', None, question))
        from .research_authoring import ResearchAuthoring
        self.authoring = ResearchAuthoring(self)

    def configure_topic_leads(self, required=True):
        """Host-only task arrangement; not a model tool or a research judgment."""
        with self.connection() as db:
            db.execute('INSERT OR REPLACE INTO organization_policy VALUES (1,?)',
                (json.dumps({'root_investigations_require_topic_lead': bool(required)}),))

    def authoring_active(self, db=None):
        if getattr(self, 'authoring_editorial', False):
            return True
        with (self.connection() if db is None else nullcontext(db)) as conn:
            return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='authoring_workset'").fetchone()
                        and conn.execute('SELECT 1 FROM authoring_workset').fetchone())

    def organization_policy(self, db=None):
        with (self.connection() if db is None else nullcontext(db)) as conn:
            row = conn.execute('SELECT payload FROM organization_policy WHERE id=1').fetchone()
            return json.loads(row[0]) if row else {}

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

    def dependency_walk(self, db, paper, seen=None, historical=None, *, active_only=False, background=None):
        """Walk active versioned premises; an earlier ancestor is revision history.

        B2 -> worker1 -> B1 records investigation of B1, not a dependency on B2.
        Exact identities remain stored and readable. Other outdated premises
        still require reassessment; a same/newer ancestor is never accepted.
        """
        seen = set() if seen is None else seen
        identity = (paper['topic_id'], paper['revision'])
        if identity in seen:
            raise RuntimeError('research_dependency_cycle')
        seen = seen | {identity}
        yield paper
        for dep in paper['dependencies']:
            upstream = self._get(db, dep['topic_id'], dep['revision'])
            if upstream['digest'] != dep['digest']:
                raise RuntimeError('research_dependency_digest_mismatch')
            if active_only and dep['use'] == 'background':
                if background is not None:
                    background.append({'from': {k:paper[k] for k in ('topic_id','revision','digest')},
                                       'historical_input': dep})
                continue
            ancestors = [r for t, r in seen if t == dep['topic_id']]
            if ancestors:
                if dep['revision'] >= min(ancestors):
                    raise RuntimeError('research_dependency_cycle')
                if historical is not None:
                    historical.append({'from': {k:paper[k] for k in ('topic_id','revision','digest')},
                        'historical_input': dep,
                        'reassessed_by': {'topic_id':dep['topic_id'],'revision':min(ancestors)}})
                continue
            yield from self.dependency_walk(db, upstream, seen, historical,
                                            active_only=active_only, background=background)

    def _stale(self, db, paper, latest, seen=None):
        return [{'adopted': {k:p[k] for k in ('topic_id','revision','digest')},
                 'current_revision':latest.get(p['topic_id'])}
                for p in list(self.dependency_walk(db, paper, seen, active_only=True))[1:]
                if latest.get(p['topic_id']) != p['revision']]

    def publish(self, actor, base_revision, paper, evidence, command_id, *, assignment=None):
        paper = ResearchWorkpaper.model_validate(paper).model_dump(mode='json', exclude_none=True)
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
                if dep['use'] != 'background' and (latest.get(dep['topic_id']) != dep['revision'] or self._stale(
                        db, upstream, latest, {(actor, base_revision + 1)})):
                    raise WorkpaperConflict('dependency_changed_reassess_current')
                if upstream['digest'] != dep['digest']:
                    raise WorkpaperConflict('dependency_digest_changed')
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                                  (actor, dep['topic_id'], dep['revision'])).fetchone():
                    raise WorkpaperConflict('read_dependency_before_adoption')
            if len(paper['evidence_receipt_ids']) != len(set(paper['evidence_receipt_ids'])):
                raise WorkpaperConflict('unique_evidence_receipts_required')
            if set(paper['evidence_receipt_ids']) != set(evidence):
                raise WorkpaperConflict('evidence_must_be_successfully_observed')
            for item in paper.get('decisive_passages', []):
                original = evidence.get(item['receipt_id'], {}).get('data', {})
                if original.get('status') != 'success':
                    raise WorkpaperConflict('counterexample_requires_observed_workpaper_source')
                quote_location(Counterexample.model_validate(item), original, paper['counterevidence'])
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
        if field not in {'body', 'metadata', 'outline'} or offset < 0 or not 1 <= max_characters <= 24000:
            raise WorkpaperConflict('invalid_workpaper_window')
        with self.connection() as db:
            latest = self._latest(db)
            paper = self._get(db, topic_id, revision or latest.get(topic_id, 0))
            stale = self._stale(db, paper, latest)
            metadata = {k: v for k, v in paper.items() if k != 'body'}
            if field == 'outline':
                from .authoring_materials import argument_outline
                return {**argument_outline(paper, compact_dependencies=self.authoring_active(db)),
                        'requires_reassessment': stale,
                        'current_revision': latest.get(topic_id)}
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
            writing = self.authoring_active(db)
            if writing:
                from .authoring_materials import material_view
                metadata = material_view(metadata)
            elif self.organization_policy(db).get('root_investigations_require_topic_lead'):
                from .research_decision_context import paper_decision
                metadata = paper_decision(paper)
            if writing or self.organization_policy(db).get('root_investigations_require_topic_lead'):
                from .assessment_evidence import current_counterexamples
                observations = current_counterexamples(self,db,[(topic_id,paper['revision'],paper['digest'])],descend=False)
                if observations:
                    metadata['reviewed_counterexamples'] = observations
            return {**metadata, 'body': paper['body'][offset:end], 'offset': offset,
                'next_offset': end if end < len(paper['body']) else None, 'total_characters': len(paper['body']),
                'requires_reassessment': stale, 'current_revision': latest.get(topic_id),
                'read_scope': 'Observed window, not proof of full reading or semantic acceptance.'}

    def catalog(self, *, after=0, limit=8, include_catalog=None):
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
                    for key,parent,question in db.execute('SELECT id,parent,question FROM topics ORDER BY id')
                    if (include_catalog if include_catalog is not None else after==0) or key in {r[1] for r in rows}],
                'catalog_scope':'all' if (include_catalog if include_catalog is not None else after==0) else 'updated_topics',
                'notice': 'Updates are asynchronous proposals. Read important changes; no count certifies coverage.'}

    def evidence(self, receipt_id):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM evidence WHERE id=?', (receipt_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_workpaper_evidence')
            return json.loads(row[0])

    def calculation_source(self, source_id):
        """Resolve an exact calculation dependency in the authorized archive.

        This restores provenance, not a claim that the author read the full
        original. Only successful source artifacts count; prose mentions do not.
        The organization reader still revalidates the returned observation.
        """
        from sec_agent.research_foundation.source_bound_calculator import sources_from_receipts, source_observation_identity
        from sec_agent.research_foundation.calculation_receipt_restore import public_capture_identity
        self.check()
        found = None
        with self.connection() as db:
            for (payload,) in db.execute('SELECT payload FROM evidence WHERE instr(payload,?)>0 ORDER BY length(payload)', (source_id,)):
                message = json.loads(payload)['data']
                candidate = sources_from_receipts([message]).get(source_id)
                if candidate is None:
                    continue
                if found is not None and public_capture_identity(source_observation_identity(found)) != public_capture_identity(source_observation_identity(candidate)):
                    raise RuntimeError('archived_calculation_dependency_identity_conflict')
                found = candidate
        self.check()
        return found

    def archive_execution_observations(self, actor, messages):
        """Retain failed acquisition with its real call; never promote it to source evidence."""
        from langchain_core.messages import ToolMessage, messages_to_dict
        from .source_acquisition_view import acquisition_history, SOURCE_TOOLS
        calls = {c['id']: c for m in messages for c in getattr(m, 'tool_calls', [])}
        blocked = {e['receipt_id'] for row in acquisition_history(messages) for e in row['events']
                   if e['stage'] in {'tool_failed', 'access_or_verification_unresolved',
                                     'search_execution_failed', 'search_no_usable_result'}}
        saved = []
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM topics WHERE id=?', (actor,)).fetchone():
                raise WorkpaperConflict('unknown_topic')
            for m in messages:
                if not isinstance(m, ToolMessage) or m.name not in SOURCE_TOOLS:
                    continue
                try:
                    body = json.loads(m.content)
                except (ValueError, TypeError):
                    body = {}
                execution = body.get('execution_receipt', {}) if isinstance(body, dict) else {}
                public_navigation = isinstance(body,dict) and (body.get('operation') in {'search','read'}
                    or (isinstance(body.get('items'),list) and bool(body['items'])))
                if (not public_navigation and m.status != 'error' and m.tool_call_id not in blocked
                        and execution.get('status') not in {'tool_failure', 'failed', 'blocked', 'error'}):
                    continue
                call = calls.get(m.tool_call_id)
                if not call:
                    continue  # An imported receipt alone cannot invent its original request.
                value = {'receipt': messages_to_dict([m])[0], 'call': call}
                wire = json.dumps(value, ensure_ascii=False, sort_keys=True)
                old = db.execute('SELECT payload FROM execution_observations WHERE id=?', (m.tool_call_id,)).fetchone()
                if old and old[0] != wire:
                    raise RuntimeError('execution_observation_identity_collision')
                db.execute('INSERT OR IGNORE INTO execution_observations VALUES (?,?,?)', (m.tool_call_id, actor, wire))
                saved.append(m.tool_call_id)
        return saved

    def execution_observation(self, receipt_id):
        with self.connection() as db:
            row = db.execute('SELECT actor,payload FROM execution_observations WHERE id=?', (receipt_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_workpaper_evidence')
            return {'topic_id': row[0], **json.loads(row[1])}

    def execution_readbacks(self, actor):
        with self.connection() as db:
            return [{'receipt_id': row[0], 'record_kind': 'execution_observation',
                     'readback': {'tool': 'read_workpaper_evidence', 'arguments': {'receipt_id': row[0]}}}
                    for row in db.execute('SELECT id FROM execution_observations WHERE actor=? ORDER BY id', (actor,))]

    def execution_catalog(self, topic=None, offset=0, limit=8, query=''):
        if offset < 0 or not 1 <= limit <= 20:
            raise WorkpaperConflict('invalid_execution_catalog_window')
        with self.connection() as db:
            if topic and not db.execute('SELECT 1 FROM topics WHERE id=?', (topic,)).fetchone():
                raise WorkpaperConflict('unknown_topic')
            where, params = (' WHERE actor=?', (topic,)) if topic else ('', ())
            if query:
                where += (' AND ' if where else ' WHERE ') + 'instr(lower(payload), lower(?))>0'
                params += (query,)
            total = db.execute('SELECT COUNT(*) FROM execution_observations'+where, params).fetchone()[0]
            rows = db.execute('SELECT id,actor,payload FROM execution_observations'+where+
                ' ORDER BY id LIMIT ? OFFSET ?', (*params, limit, offset)).fetchall()
        entries=[]
        for receipt_id, actor, wire in rows:
            value=json.loads(wire)
            call=value['call']
            args=call.get('args',{})
            # Small exact navigation fields; full parameters and result stay paginated in readback.
            query={k:v for k,v in args.items() if k in ('query','url','document_id','source_id','operation')}
            entries.append({'receipt_id':receipt_id,'topic_id':actor,'tool':call['name'],
                'request_preview':{k:str(v)[:500] for k,v in query.items()},
                'readback':{'tool':'read_workpaper_evidence','arguments':{'receipt_id':receipt_id}}})
        return {'record_kind':'execution_catalog','source_evidence':False,'entries':entries,
            'total':total,'offset':offset,'next_offset':offset+len(rows) if offset+len(rows)<total else None}

    def observed(self, actor, topic, revision):
        with self.connection() as db:
            return bool(db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                                   (actor,topic,revision)).fetchone())

    def prepare(self, actor, topics, rationale, section_ids=None):
        """Freeze exact versions, including transitive dependencies; no full paper concatenation."""
        if actor != 'root' or not topics or not rationale.strip():
            raise WorkpaperConflict('root_synthesis_requires_selected_topics_and_scope_rationale')
        with self.connection() as db:
            latest = self._latest(db)
            selected, historical, background = {}, [], []
            for key in dict.fromkeys(topics):
                paper = self._get(db, key, latest.get(key, 0))
                for item in self.dependency_walk(db, paper, historical=historical,
                                                active_only=True, background=background):
                    if latest.get(item['topic_id']) != item['revision']:
                        raise WorkpaperConflict('synthesis_dependency_stale')
                    selected[item['topic_id']] = {'revision':item['revision'],'digest':item['digest']}
            payload = {'root_id': self.root_id, 'selected': selected, 'direct_topics': list(dict.fromkeys(topics)), 'scope_rationale': rationale,
                'catalog_versions': latest, 'as_of': db.execute('SELECT as_of FROM identity').fetchone()[0]}
            if historical:
                payload['historical_inputs'] = historical
            if background:
                payload['background_inputs'] = background
            understanding = self.authoring._state(db)
            if section_ids is not None:
                if not section_ids or len(set(section_ids)) != len(section_ids) or any(s not in understanding['sections'] for s in section_ids):
                    raise WorkpaperConflict('unknown_or_empty_authoring_workset')
                payload['section_ids'] = list(section_ids)
                payload['scope'] = 'chapters'
            if understanding['revision']:
                sections = understanding['sections'].values() if section_ids is None else [understanding['sections'][s] for s in section_ids]
                needed = self.authoring._closure(understanding, (understanding['lead_judgment_ids'] if section_ids is None else []) +
                    [j for s in sections for j in s['judgment_ids']])
                if set(self.authoring._impacts(db,understanding)) & needed:
                    raise WorkpaperConflict('reassess_judgments_before_synthesis')
                for key in needed:
                    for ref in understanding['judgments'][key]['workpapers']:
                        if selected.get(ref['topic_id']) != {k:ref[k] for k in ('revision','digest')}:
                            raise WorkpaperConflict('select_outline_argument_materials')
                payload.update(understanding_revision=understanding['revision'], understanding_digest=understanding['digest'])
                payload['understanding_basis']=self.authoring.synthesis_basis(understanding, section_ids)
                if understanding['sections']:
                    self.authoring.select_workset(db,understanding,section_ids)
            payload['invalidation_scope']='selected_dependencies'
            key = canonical_sha256(payload)
            db.execute('INSERT OR IGNORE INTO snapshots VALUES (?,?)', (key, json.dumps(payload, ensure_ascii=False)))
            inherited = self._chapter_adoptions(db, section_ids)
            observed={t:bool(db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                (actor,t,ref['revision'])).fetchone()) for t,ref in selected.items()}
            return {'snapshot_id': key, **payload, 'observed_versions':observed,
                'inherited_direct_topics':[t for t in payload['direct_topics'] if (t,selected[t]['revision'],selected[t]['digest']) in inherited],
                'unread_direct_topics':[t for t in payload['direct_topics'] if not observed[t]
                    and (t,selected[t]['revision'],selected[t]['digest']) not in inherited],
                'next_step': 'Reuse observed same-version material. Read unread relevant arguments or needed windows; author chapters and assemble the report.'}

    def snapshot(self, snapshot_id, *, _db=None):
        with (self.connection() if _db is None else nullcontext(_db)) as db:
            row = db.execute('SELECT payload FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_synthesis_snapshot')
            value = json.loads(row[0])
            if canonical_sha256(value) != snapshot_id:
                raise RuntimeError('synthesis_snapshot_integrity_failure')
            latest = self._latest(db)
            scope=value['selected'] if value.get('invalidation_scope')=='selected_dependencies' else set(latest)|set(value['catalog_versions'])
            state=self.authoring._state(db)
            missing_sections = any(s not in state['sections'] for s in value.get('section_ids', []))
            return {**value, 'changed_topics': [key for key in scope
                if latest.get(key) != value['catalog_versions'].get(key)],
                'unselected_updates':[key for key in set(latest)|set(value['catalog_versions']) if key not in scope and latest.get(key)!=value['catalog_versions'].get(key)],
                'understanding_changed': missing_sections or (value['understanding_basis'] != self.authoring.synthesis_basis(state, value.get('section_ids'))
                    if 'understanding_basis' in value else value.get('understanding_digest') != state['digest'])}

    def _chapter_adoptions(self, db, section_ids=None):
        """Versions explicitly reused by saved current chapters. Never mark full papers read."""
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='authoring_sections'").fetchone():
            return set()
        from .authoring_sections import AuthoringSections
        chapters = object.__new__(AuthoringSections)
        chapters.w = self
        state = self.authoring._state(db)
        adopted = set()
        for key, chapter in chapters._latest(db).items():
            if section_ids is not None and key not in section_ids:
                continue
            for receipt, ref in chapter['receipts'].items():
                if ref['tool'] != 'reuse_adopted_judgment':
                    continue
                if chapters._status(db,chapter,state) != 'current':
                    break
                row = db.execute('SELECT payload FROM evidence WHERE id=?',(receipt,)).fetchone()
                if not row:
                    raise WorkpaperConflict('missing_adopted_judgment_receipt')
                content = json.loads(row[0])['data']['content']
                if canonical_sha256(content) != ref['content_digest']:
                    raise WorkpaperConflict('chapter_receipt_identity_changed')
                claim = json.loads(content)
                node = state['judgments'][claim['judgment_id']]
                if canonical_sha256(node) != claim['judgment_digest']:
                    raise WorkpaperConflict('read_current_adopted_judgment')
                for source in claim['sources']:
                    original = db.execute('SELECT payload FROM evidence WHERE id=?',(source['receipt_id'],)).fetchone()
                    if not original or canonical_sha256(json.loads(original[0])) != source['original_digest']:
                        raise WorkpaperConflict('adopted_citation_identity_changed')
                adopted.update((r['topic_id'],r['revision'],r['digest']) for r in node['workpapers']
                               if r['use'] in ('adopted','qualified'))
        return adopted

    def bind(self, snapshot_id, report_digest, *, report=None, section_uses=None):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM snapshots WHERE id=?', (snapshot_id,)).fetchone()
            if not row:
                raise WorkpaperConflict('unknown_synthesis_snapshot')
            snap = json.loads(row[0])
            latest=self._latest(db)
            scope=snap['selected'] if snap.get('invalidation_scope')=='selected_dependencies' else set(latest)|set(snap['catalog_versions'])
            if any(snap['catalog_versions'].get(k)!=latest.get(k) for k in scope):
                raise WorkpaperConflict('research_changed_refresh_synthesis')
            inherited = self._chapter_adoptions(db, snap.get('section_ids'))
            for key in snap.get('direct_topics', snap['selected']):
                ref = snap['selected'][key]
                if (key,ref['revision'],ref['digest']) in inherited:
                    continue
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?', ('root',key,ref['revision'])).fetchone():
                    raise WorkpaperConflict('read_selected_argument_before_delivery:'+key+':'+str(ref['revision']))
            authoring = self.authoring.binding(db, snap, report_digest, report, section_uses)
            db.execute('INSERT OR REPLACE INTO bindings VALUES (?,?)', (report_digest,snapshot_id))
        return {'bound': True, 'snapshot_id': snapshot_id, 'report_digest': report_digest,
                'authoring': {'understanding_revision':authoring['understanding_revision'],
                    'mapped_sections':len(authoring['sections']), 'readback':{'tool':'read_current_report','arguments':{'field':'argument_map'}}} if authoring else None,
                'coverage':'mapped_passages_not_semantic_approval','semantic_approval': False}

    def require_current_binding(self, report_digest, report=None):
        with self.connection() as db:
            if not db.execute('SELECT 1 FROM papers').fetchone() and not self.authoring._state(db)['revision']:
                return  # Unmigrated legacy task: preserve existing delivery contract.
            row = db.execute('SELECT snapshot FROM bindings WHERE report_digest=?', (report_digest,)).fetchone()
            if not row:
                raise WorkpaperConflict('bind_current_report_to_research_snapshot')
        snapshot = self.snapshot(row[0])
        if snapshot['changed_topics']:
            raise WorkpaperConflict('research_changed_refresh_synthesis')
        if snapshot['understanding_changed']:
            raise WorkpaperConflict('understanding_changed_refresh_synthesis')
        with self.connection() as db:
            state = self.authoring._state(db)
            self._chapter_adoptions(db, snapshot.get('section_ids'))  # Recheck archived citations at the delivery boundary.
            bound = db.execute('SELECT payload FROM section_bindings WHERE report_digest=?',(report_digest,)).fetchone()
            if bound:
                from .assessment_evidence import section_counterexamples
                observations = section_counterexamples(self,db,state,list(state['sections']),whole=True)
                if observations != json.loads(bound[0]).get('reviewed_counterexamples',[]):
                    raise WorkpaperConflict('review_evidence_changed_rebind_report')
            if any(i['status'] == 'open' for i in self.authoring._issues(db,state,report)):
                raise WorkpaperConflict('resolve_authoring_issues_before_delivery')
