"""Incremental public judgments and argument outlines on the existing SQLite workspace.

This is a provenance contract, not a semantic judge or another agent scheduler.
Historical states are immutable; unchanged judgments retain their exact basis.
"""
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from .research_graph_contracts import canonical_sha256
from .research_workpapers import Adoption, WorkpaperConflict


class Judgment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    statement: str = Field(min_length=1, max_length=3000)
    rationale: str = Field(min_length=1, max_length=6000, description='Public reasons and inferential bridge, not private thinking.')
    conditions: str = Field(min_length=1, max_length=3000)
    counterevidence: str = Field(min_length=1, max_length=3000)
    remaining: str = Field(min_length=1, max_length=3000)
    status: Literal['active', 'withdrawn'] = 'active'
    workpapers: list[Adoption] = Field(default_factory=list, max_length=32)
    depends_on: list[str] = Field(default_factory=list, max_length=32)


class ArgumentSection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    title: str = Field(min_length=1, max_length=500)
    question: str = Field(min_length=1, max_length=2000)
    role: str = Field(min_length=1, max_length=2000, description='How this section advances the original decision.')
    judgment_ids: list[str] = Field(min_length=1, max_length=32)
    order: int = Field(ge=0)


class UnderstandingPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reason: str = Field(min_length=1, max_length=3000)
    judgments: list[Judgment] = Field(default_factory=list, max_length=64)
    sections: list[ArgumentSection] = Field(default_factory=list, max_length=64)
    remove_sections: list[str] = Field(default_factory=list, max_length=64)
    lead_judgment_ids: list[str] | None = Field(default=None, max_length=32)


class AuthoringIssue(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=120)
    section_ids: list[str] = Field(min_length=1, max_length=32)
    kind: Literal['missing_link', 'stale_basis', 'expression', 'thesis_conflict', 'access_failure']
    question: str = Field(min_length=1, max_length=4000)
    quote: str = Field(min_length=1, max_length=6000)
    field: Literal['title','narrative_markdown'] = 'narrative_markdown'


class SectionUse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    section_id: str
    excerpt: str = Field(min_length=1, max_length=12000, description='Exact unique passage in the saved report.')
    field: Literal['title','narrative_markdown'] = 'narrative_markdown'


class ResearchAuthoring:
    def __init__(self, workspace):
        self.w = workspace
        with self.w.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS understanding (revision INTEGER PRIMARY KEY, digest TEXT, payload TEXT);
                CREATE TABLE IF NOT EXISTS authoring_issues (id TEXT PRIMARY KEY, payload TEXT);
                CREATE TABLE IF NOT EXISTS authoring_resolutions (id TEXT, revision INTEGER, payload TEXT,
                    PRIMARY KEY(id,revision));
                CREATE TABLE IF NOT EXISTS section_bindings (report_digest TEXT PRIMARY KEY, payload TEXT);
            ''')

    @staticmethod
    def _state(db, revision=None):
        row = (db.execute('SELECT revision,digest,payload FROM understanding WHERE revision=?', (revision,)).fetchone()
               if revision is not None else db.execute('SELECT revision,digest,payload FROM understanding ORDER BY revision DESC LIMIT 1').fetchone())
        if not row:
            if revision is not None:
                raise WorkpaperConflict('unknown_understanding_revision')
            return {'revision': 0, 'digest': None, 'judgments': {}, 'sections': {}, 'lead_judgment_ids': []}
        payload = json.loads(row[2])
        if canonical_sha256(payload) != row[1]:
            raise RuntimeError('understanding_integrity_failure')
        return {'revision': row[0], 'digest': row[1], **payload}

    def _impacts(self, db, state):
        latest = self.w._latest(db)
        affected = {}
        for key, node in state['judgments'].items():
            if node['status'] == 'withdrawn':
                continue
            reasons = []
            for ref in node['workpapers']:
                paper = self.w._get(db, ref['topic_id'], ref['revision'])
                if paper['digest'] != ref['digest']:
                    raise RuntimeError('judgment_evidence_digest_mismatch')
                if latest.get(ref['topic_id']) != ref['revision'] or self.w._stale(db, paper, latest):
                    reasons.append({'workpaper': ref, 'current_revision': latest.get(ref['topic_id'])})
            for upstream in node['depends_on']:
                if node['basis'][upstream] != canonical_sha256(state['judgments'][upstream]):
                    reasons.append({'judgment_changed': upstream})
            if reasons:
                affected[key] = reasons
        while True:
            before = len(affected)
            for key, node in state['judgments'].items():
                if node['status'] == 'active' and key not in affected:
                    deps = [d for d in node['depends_on'] if d in affected]
                    if deps:
                        affected[key] = [{'upstream_requires_reassessment': deps}]
            if len(affected) == before:
                break
        return affected

    def update(self, base_revision, patch, command_id):
        patch = UnderstandingPatch.model_validate(patch).model_dump(mode='json')
        fingerprint = canonical_sha256(['understanding', base_revision, patch])
        with self.w.connection() as db:
            old = db.execute('SELECT fingerprint,result FROM commands WHERE id=?', (command_id,)).fetchone()
            if old:
                if old[0] != fingerprint:
                    raise WorkpaperConflict('understanding_command_changed')
                return json.loads(old[1])
            state = self._state(db)
            if base_revision != state['revision']:
                raise WorkpaperConflict('understanding_version_changed_read_current')
            for field in ('judgments', 'sections'):
                ids = [n['id'] for n in patch[field]]
                if len(ids) != len(set(ids)):
                    raise WorkpaperConflict('duplicate_patch_identity')
            if set(patch['remove_sections']) & {n['id'] for n in patch['sections']}:
                raise WorkpaperConflict('cannot_remove_and_update_same_section')
            nodes = dict(state['judgments'])
            changed = {n['id'] for n in patch['judgments']}
            nodes.update({n['id']: n for n in patch['judgments']})
            visiting, done = set(), set()
            latest = self.w._latest(db)

            def validate(key):
                if key in visiting:
                    raise WorkpaperConflict('judgment_dependency_cycle')
                if key in done:
                    return
                if key not in nodes:
                    raise WorkpaperConflict('unknown_judgment_dependency')
                visiting.add(key)
                node = nodes[key]
                for dep in node['depends_on']:
                    validate(dep)
                    if nodes[dep]['status'] == 'withdrawn' and node['status'] == 'active':
                        raise WorkpaperConflict('active_judgment_depends_on_withdrawn')
                if key in changed:
                    if len({r['topic_id'] for r in node['workpapers']}) != len(node['workpapers']):
                        raise WorkpaperConflict('one_version_per_judgment_source')
                    for ref in node['workpapers']:
                        paper = self.w._get(db, ref['topic_id'], ref['revision'])
                        if paper['digest'] != ref['digest']:
                            raise WorkpaperConflict('judgment_source_digest_changed')
                        if node['status'] == 'active' and (latest.get(ref['topic_id']) != ref['revision'] or self.w._stale(db, paper, latest)):
                            raise WorkpaperConflict('read_current_basis_before_updating_judgment')
                        if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?',
                                          ('root', ref['topic_id'], ref['revision'])).fetchone():
                            raise WorkpaperConflict('read_argument_before_judgment')
                    node['basis'] = {d: canonical_sha256(nodes[d]) for d in node['depends_on']}
                visiting.remove(key)
                done.add(key)
            for key in nodes:
                validate(key)
            sections = dict(state['sections'])
            for key in patch['remove_sections']:
                if key not in sections:
                    raise WorkpaperConflict('unknown_section_to_remove')
                del sections[key]
            sections.update({s['id']: s for s in patch['sections']})
            leads = patch['lead_judgment_ids'] if patch['lead_judgment_ids'] is not None else state['lead_judgment_ids']
            for key in leads + [j for s in sections.values() for j in s['judgment_ids']]:
                if key not in nodes or nodes[key]['status'] != 'active':
                    raise WorkpaperConflict('outline_requires_active_judgment')
            payload = {'judgments': nodes, 'sections': sections, 'lead_judgment_ids': leads,
                       'change': patch, 'previous_revision': base_revision}
            revision = base_revision + 1
            digest = canonical_sha256(payload)
            db.execute('INSERT INTO understanding VALUES (?,?,?)', (revision, digest, json.dumps(payload, ensure_ascii=False)))
            affected = self._impacts(db, payload)
            result = {'saved': True, 'revision': revision, 'digest': digest, 'updated_judgments': sorted(changed),
                      'requires_reassessment': affected, 'readback': {'tool': 'read_authoring_context', 'arguments': {}},
                      'semantic_approval': False}
            db.execute('INSERT INTO commands VALUES (?,?,?)', (command_id, fingerprint, json.dumps(result)))
            return result

    @staticmethod
    def _closure(state, ids):
        selected = set()
        def visit(key):
            if key not in selected:
                selected.add(key)
                for dep in state['judgments'][key]['depends_on']:
                    visit(dep)
        for key in ids:
            visit(key)
        return selected

    def _issues(self, db, state):
        result = []
        for (payload,) in db.execute('SELECT payload FROM authoring_issues ORDER BY id'):
            issue = json.loads(payload)
            row = db.execute('SELECT payload FROM authoring_resolutions WHERE id=? ORDER BY revision DESC LIMIT 1', (issue['id'],)).fetchone()
            resolution = json.loads(row[0]) if row else None
            current = self._section_basis(state, issue['section_ids'])
            closed = resolution and current == resolution['basis']
            if closed:
                for ref in resolution['results']:
                    paper = self.w._get(db,ref['topic_id'],ref['revision'])
                    if self.w._latest(db).get(ref['topic_id']) != ref['revision'] or self.w._stale(db,paper,self.w._latest(db)):
                        closed = False
            result.append({**issue, 'status': 'resolved' if closed else 'open', 'resolution': resolution})
        return result

    @staticmethod
    def _section_basis(state, ids):
        sections = {key: state['sections'].get(key) for key in ids}
        nodes = ResearchAuthoring._closure(state, [j for s in sections.values() if s for j in s['judgment_ids']])
        return {'sections': sections, 'judgments': {key: canonical_sha256(state['judgments'][key]) for key in sorted(nodes)}}

    def context(self, section_ids=None, revision=None):
        with self.w.connection() as db:
            state = self._state(db, revision)
            ids = list(state['sections']) if section_ids is None else section_ids
            if any(key not in state['sections'] for key in ids):
                raise WorkpaperConflict('unknown_authoring_section')
            nodes = self._closure(state, state['lead_judgment_ids'] + [j for key in ids for j in state['sections'][key]['judgment_ids']])
            affected = self._impacts(db, state)
            papers = {}
            for key in nodes:
                for ref in state['judgments'][key]['workpapers']:
                    paper = self.w._get(db, ref['topic_id'], ref['revision'])
                    papers[(ref['topic_id'], ref['revision'])] = {**ref,
                        'readback': {'tool': 'read_research_workpaper', 'arguments': {'topic_id': ref['topic_id'], 'revision': ref['revision']}},
                        'evidence_receipt_ids': paper['evidence_receipt_ids']}
            identity = db.execute('SELECT question,as_of FROM identity').fetchone()
            issues = self._issues(db, state)
            generation = canonical_sha256([state['digest'], self.w._latest(db), issues])
            value = {'revision': state['revision'], 'digest': state['digest'], 'historical_read': revision is not None,
                'context_generation': generation,
                'question': identity[0], 'as_of': identity[1],
                'lead_judgment_ids': state['lead_judgment_ids'], 'judgments': {k: state['judgments'][k] for k in sorted(nodes)},
                'outline': sorted(state['sections'].values(), key=lambda s: (s['order'], s['id'])),
                'selected_sections': ids, 'materials': list(papers.values()), 'requires_reassessment': affected,
                'affected_sections': [k for k,s in state['sections'].items() if any(j in affected for j in s['judgment_ids'])],
                'issues': [{**{k:v for k,v in i.items() if k not in {'basis','resolution'}},
                    'resolution': {k:v for k,v in i['resolution'].items() if k != 'basis'} if i['resolution'] else None} for i in issues],
                'withdrawn': [{'id': k, 'statement': n['statement'], 'reason': n['rationale']} for k,n in state['judgments'].items() if n['status']=='withdrawn'],
                'notice': 'Current public understanding and navigation. Read complete relevant arguments; this is not evidence or semantic approval.'}
            return {**value, 'result_digest': canonical_sha256(value)}

    def open_issue(self, base_revision, issue, report):
        issue = AuthoringIssue.model_validate(issue).model_dump(mode='json')
        with self.w.connection() as db:
            state = self._state(db)
            if state['revision'] != base_revision:
                raise WorkpaperConflict('understanding_version_changed_read_current')
            if any(s not in state['sections'] for s in issue['section_ids']):
                raise WorkpaperConflict('unknown_authoring_section')
            body = report.get(issue['field'], '')
            if body.count(issue['quote']) != 1:
                raise WorkpaperConflict('issue_quote_must_identify_unique_saved_passage')
            value = {**issue, 'opened_revision': base_revision, 'report_digest': canonical_sha256(report),
                     'basis': self._section_basis(state, issue['section_ids'])}
            old = db.execute('SELECT payload FROM authoring_issues WHERE id=?', (issue['id'],)).fetchone()
            if old and json.loads(old[0]) != value:
                raise WorkpaperConflict('issue_identity_changed_use_new_id')
            db.execute('INSERT OR IGNORE INTO authoring_issues VALUES (?,?)', (issue['id'], json.dumps(value, ensure_ascii=False)))
            return {'saved': True, 'issue_id': issue['id'], 'status': 'open',
                    'next_step': 'For evidence gaps consult_research_agent(authoring_issue_id=...); for expression update the affected prose. Reassess affected judgments then resolve_authoring_issue.'}

    def handoff(self, issue_id):
        view = self.context()
        issue = next((i for i in view['issues'] if i['id'] == issue_id), None)
        if not issue or issue['status'] != 'open':
            raise WorkpaperConflict('authoring_issue_not_open')
        view = self.context(issue['section_ids'])
        return {'issue': issue, 'understanding_revision': view['revision'], 'original_question': view['question'],
                'as_of': view['as_of'], 'lead_judgments': view['lead_judgment_ids'], 'judgments': view['judgments'],
                'sections': [s for s in view['outline'] if s['id'] in issue['section_ids']], 'materials': view['materials'],
                'instruction': 'Investigate this relationship and its implications; the existing judgment is revisable. Return a complete workpaper, not just replacement wording.'}

    def resolve(self, issue_id, base_revision, disposition, explanation, results, report):
        if disposition not in {'revised', 'retained', 'bounded_answer'} or not explanation.strip():
            raise WorkpaperConflict('explicit_resolution_required')
        refs = [Adoption.model_validate(r).model_dump(mode='json') for r in results]
        with self.w.connection() as db:
            state = self._state(db)
            if state['revision'] != base_revision:
                raise WorkpaperConflict('understanding_version_changed_read_current')
            issue = next((i for i in self._issues(db, state) if i['id'] == issue_id), None)
            if not issue:
                raise WorkpaperConflict('unknown_authoring_issue')
            affected = self._impacts(db, state)
            basis = self._section_basis(state, issue['section_ids'])
            if any(k in affected for k in basis['judgments']):
                raise WorkpaperConflict('reassess_affected_judgments_before_resolution')
            if issue['kind'] in {'missing_link', 'access_failure'} and not refs:
                raise WorkpaperConflict('investigation_result_required_even_for_bounded_answer')
            for ref in refs:
                paper = self.w._get(db, ref['topic_id'], ref['revision'])
                assignment = paper['original_task'].get('assignment') or {}
                if (assignment.get('authoring_issue_id') != issue_id or paper['digest'] != ref['digest']
                    or self.w._latest(db).get(ref['topic_id']) != ref['revision'] or self.w._stale(db,paper,self.w._latest(db))):
                    raise WorkpaperConflict('resolution_requires_current_linked_result')
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?', ('root',ref['topic_id'],ref['revision'])).fetchone():
                    raise WorkpaperConflict('read_resolution_argument_first')
            value = {'disposition': disposition, 'explanation': explanation, 'results': refs, 'basis': basis,
                     'report_digest': canonical_sha256(report), 'understanding_revision': base_revision}
            previous = db.execute('SELECT revision,payload FROM authoring_resolutions WHERE id=? ORDER BY revision DESC LIMIT 1',(issue_id,)).fetchone()
            if not previous or json.loads(previous[1]) != value:
                db.execute('INSERT INTO authoring_resolutions VALUES (?,?,?)',(issue_id,previous[0]+1 if previous else 1,json.dumps(value,ensure_ascii=False)))
            return {'saved': True, 'issue_id': issue_id, 'resolution': value, 'semantic_approval': False}

    def binding(self, db, snapshot, report_digest, report, section_uses):
        state = self._state(db)
        if not state['revision']:
            return None  # Existing tasks keep their legacy whole-report contract.
        if report is not None and canonical_sha256(report) != report_digest:
            raise WorkpaperConflict('report_digest_does_not_match_saved_prose')
        if snapshot.get('understanding_digest') != state['digest']:
            raise WorkpaperConflict('understanding_changed_refresh_synthesis')
        if self._impacts(db, state):
            raise WorkpaperConflict('reassess_judgments_before_delivery')
        if not state['lead_judgment_ids'] or not state['sections']:
            raise WorkpaperConflict('authoring_requires_current_thesis_and_outline')
        if any(i['status'] == 'open' for i in self._issues(db,state)):
            raise WorkpaperConflict('resolve_authoring_issues_before_delivery')
        uses = [SectionUse.model_validate(u).model_dump(mode='json') for u in (section_uses or [])]
        if len({(u['section_id'],u['field'],u['excerpt']) for u in uses}) != len(uses) or {u['section_id'] for u in uses} != set(state['sections']):
            raise WorkpaperConflict('bind_each_outline_section_to_saved_prose')
        for use in uses:
            text = (report or {}).get(use['field'],'')
            if text.count(use['excerpt']) != 1:
                raise WorkpaperConflict('section_excerpt_must_match_unique_saved_prose')
            use['start'] = text.index(use['excerpt'])
            use['end'] = use['start'] + len(use['excerpt'])
            use['basis'] = self._section_basis(state,[use['section_id']])
        value = {'understanding_revision':state['revision'],'understanding_digest':state['digest'], 'sections':uses}
        db.execute('INSERT OR REPLACE INTO section_bindings VALUES (?,?)',(report_digest,json.dumps(value,ensure_ascii=False)))
        return value

    def report_map(self, report_digest):
        with self.w.connection() as db:
            row = db.execute('SELECT payload FROM section_bindings WHERE report_digest=?',(report_digest,)).fetchone()
            if not row:
                return {'found':False,'report_digest':report_digest,'next_step':'Bind current saved prose to the synthesis snapshot and outline.'}
            value = json.loads(row[0])
            archived = self._state(db,value['understanding_revision'])
            if archived['digest'] != value['understanding_digest']:
                raise RuntimeError('report_argument_map_integrity_failure')
            return {'found':True,'report_digest':report_digest,**value,
                'judgments':archived['judgments'],
                'understanding_readback':{'tool':'read_authoring_context','arguments':{'revision':value['understanding_revision']}},
                'current_understanding_changed':self._state(db)['digest'] != value['understanding_digest'],
                'basis_requires_reassessment':self._impacts(db,archived),
                'semantic_approval':False}


def authoring_context_replacements(messages, candidates, current):
    """Retire superseded same-scope views only after a current replacement was actually read.

    Reuse native logged surface replacement; never alter canonical history or tool pairing.
    Deliberate historical reads stay visible. Changed conditions remain in the newer view.
    """
    from langchain_core.messages import ToolMessage
    from .harness_business_tools import model_receipt
    originals, newest = {}, {}
    for message in messages:
        if not isinstance(message,ToolMessage) or message.name != 'read_authoring_context' or message.status != 'success':
            continue
        body = json.loads(message.content)
        if 'result_digest' not in body:
            continue
        originals[message.tool_call_id] = (message,body)
        if not body.get('historical_read') and body.get('context_generation') == current['context_generation']:
            newest[tuple(sorted(body['selected_sections']))] = message.tool_call_id
    replacements = []
    for candidate in candidates:
        pair = originals.get(candidate.get('receipt_id'))
        if not pair:
            continue
        message,body = pair
        newer = newest.get(tuple(sorted(body['selected_sections'])))
        if (newer and newer != message.tool_call_id and not body.get('historical_read')
                and body.get('context_generation') != current['context_generation']):
            receipt = {'receipt_id':message.tool_call_id,'status':'success','result':{
                'result_digest':body['result_digest'],'context_state':'superseded_authoring_view',
                'old_revision':body['revision'],'current_revision':current['revision'],
                'current_view_receipt_id':newer,
                'current_readback':{'tool':'read_authoring_context','arguments':{'section_ids':body['selected_sections']}},
                'original_readback':{'tool':'read_authoring_context','arguments':{'section_ids':body['selected_sections'],'revision':body['revision']}}}}
        elif candidate.get('retired'):
            receipt = model_receipt(message)
            receipt['context_notice'] = 'No current same-scope replacement has been read; recover current authoring context.'
        else:
            continue
        replacements.append({'receipt_id':message.tool_call_id,'result_digest':body['result_digest'],'receipt':receipt})
    return replacements
