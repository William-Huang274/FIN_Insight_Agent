"""Incremental public judgments and argument outlines on the existing SQLite workspace.

This is a provenance contract, not a semantic judge or another agent scheduler.
Historical states are immutable; unchanged judgments retain their exact basis.
"""
import json
from contextlib import nullcontext
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
                CREATE TABLE IF NOT EXISTS authoring_report (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT);
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
                    previous = next((json.loads(row[0])['judgments'].get(upstream) for row in db.execute(
                        'SELECT payload FROM understanding ORDER BY revision DESC')
                        if canonical_sha256(json.loads(row[0])['judgments'].get(upstream)) == node['basis'][upstream]), None)
                    reasons.append({'judgment_changed': upstream, 'changed_fields': self._difference(previous or {}, state['judgments'][upstream])})
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
            if all(payload[k] == state[k] for k in ('judgments','sections','lead_judgment_ids')):
                result = {'saved': True, 'unchanged': True, 'revision': base_revision, 'digest': state['digest'],
                          'updated_judgments': [], 'requires_reassessment': self._impacts(db,state)}
                db.execute('INSERT INTO commands VALUES (?,?,?)', (command_id,fingerprint,json.dumps(result)))
                return result
            revision = base_revision + 1
            digest = canonical_sha256(payload)
            db.execute('INSERT INTO understanding VALUES (?,?,?)', (revision, digest, json.dumps(payload, ensure_ascii=False)))
            affected = self._impacts(db, payload)
            result = {'saved': True, 'revision': revision, 'digest': digest, 'updated_judgments': sorted(changed),
                      'requires_reassessment': affected, 'readback': {'tool': 'read_authoring_context', 'arguments': {}},
                      'semantic_approval': False}
            result['changes'] = {key:self._difference(state['judgments'].get(key,{}),nodes[key]) for key in sorted(changed)}
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

    @staticmethod
    def _difference(before, after):
        return {k:{'before':before.get(k),'after':after.get(k)} for k in sorted(set(before)|set(after))
                if k != 'basis' and before.get(k) != after.get(k)}

    def observe_report(self, report):
        with self.w.connection() as db:
            db.execute('INSERT OR REPLACE INTO authoring_report VALUES (1,?)',(json.dumps(report,ensure_ascii=False),))

    def _issues(self, db, state, report=None):
        if report is None:
            row = db.execute('SELECT payload FROM authoring_report WHERE id=1').fetchone()
            report = json.loads(row[0]) if row else None
        result = []
        for (payload,) in db.execute('SELECT payload FROM authoring_issues ORDER BY id'):
            issue = json.loads(payload)
            row = db.execute('SELECT payload FROM authoring_resolutions WHERE id=? ORDER BY revision DESC LIMIT 1', (issue['id'],)).fetchone()
            resolution = json.loads(row[0]) if row else None
            current = self._section_basis(state, issue['section_ids'])
            closed = resolution and current == resolution['basis']
            if closed and report is not None:
                tracking = resolution.get('prose')
                if tracking:
                    closed = all(report.get(a['field'],'').count(a['excerpt']) == 1 for a in tracking['anchors'])
                    closed = closed and all(canonical_sha256(report.get(k,'')) == v for k,v in tracking['fields'].items())
                    forbidden = tracking.get('removed_quote')
                    if forbidden and forbidden['quote'] in report.get(forbidden['field'],''):
                        closed = False
                else:
                    closed = canonical_sha256(report) == resolution['report_digest']
            if closed:
                for ref in resolution['results']:
                    paper = self.w._get(db,ref['topic_id'],ref['revision'])
                    if self.w._latest(db).get(ref['topic_id']) != ref['revision'] or self.w._stale(db,paper,self.w._latest(db)):
                        closed = False
            result.append({**issue, 'status': 'resolved' if closed else 'open', 'resolution': resolution})
        return result

    @staticmethod
    def _section_basis(state, ids):
        sections = {key: ({k:v for k,v in state['sections'][key].items() if k != 'order'}
                         if key in state['sections'] else None) for key in ids}
        nodes = ResearchAuthoring._closure(state, [j for s in sections.values() if s for j in s['judgment_ids']])
        return {'sections': sections, 'judgments': {key: canonical_sha256(state['judgments'][key]) for key in sorted(nodes)}}

    def context(self, section_ids=None, revision=None, include_history=False, *, _db=None):
        with (self.w.connection() if _db is None else nullcontext(_db)) as db:
            state = self._state(db, revision)
            ids = list(state['sections']) if section_ids is None else section_ids
            if any(key not in state['sections'] for key in ids):
                raise WorkpaperConflict('unknown_authoring_section')
            nodes = self._closure(state, (state['lead_judgment_ids'] if section_ids is None else [])+
                                  [j for key in ids for j in state['sections'][key]['judgment_ids']])
            affected = self._impacts(db, state)
            papers = {}
            for key in nodes:
                for ref in state['judgments'][key]['workpapers']:
                    paper = self.w._get(db, ref['topic_id'], ref['revision'])
                    papers[(ref['topic_id'], ref['revision'])] = {**ref,
                        'readback': {'tool': 'read_research_workpaper', 'arguments': {'topic_id': ref['topic_id'], 'revision': ref['revision']}},
                        'evidence_receipt_ids': paper['evidence_receipt_ids']}
            identity = db.execute('SELECT question,as_of FROM identity').fetchone()
            issues = [i for i in self._issues(db,state) if set(i['section_ids']) & set(ids)
                      and (include_history or i['status']=='open')]
            visible_nodes = {k:state['judgments'][k] for k in sorted(nodes)}
            leads = {k:{f:state['judgments'][k][f] for f in ('statement','conditions','counterevidence','remaining')}
                     for k in state['lead_judgment_ids'] if k not in nodes}
            scoped_impacts = {k:v for k,v in affected.items() if k in nodes or k in leads}
            generation = canonical_sha256([visible_nodes,leads,[state['sections'][k] for k in ids],scoped_impacts,issues])
            value = {'revision': state['revision'], 'digest': state['digest'], 'historical_read': revision is not None,
                'context_generation': generation,
                'question': identity[0], 'as_of': identity[1],
                'lead_judgment_ids': state['lead_judgment_ids'], 'lead_overview': leads, 'judgments': visible_nodes,
                'outline': sorted([state['sections'][k] for k in ids], key=lambda s: (s['order'], s['id'])),
                'selected_sections': ids, 'include_history':include_history, 'materials': list(papers.values()), 'requires_reassessment': scoped_impacts,
                'affected_sections': [k for k,s in state['sections'].items() if any(j in affected for j in s['judgment_ids'])],
                'issues': [{**{k:v for k,v in i.items() if k not in {'basis','resolution'}},
                    'resolution': {k:v for k,v in i['resolution'].items() if k != 'basis'} if i['resolution'] else None} for i in issues],
                'withdrawn': [{'id': k, 'statement': n['statement'], 'reason': n['rationale']} for k,n in state['judgments'].items() if include_history and n['status']=='withdrawn'],
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
        with self.w.connection() as db:
            state=self._state(db)
            issue=next((i for i in self._issues(db,state) if i['id']==issue_id),None)
            if not issue or issue['status']!='open':
                raise WorkpaperConflict('authoring_issue_not_open')
            issue={k:v for k,v in issue.items() if k not in {'basis','resolution'}}
            view=self.context(issue['section_ids'],_db=db)
        return {'issue': issue, 'understanding_revision': view['revision'], 'original_question': view['question'],
                'as_of': view['as_of'], 'lead_judgments': view['lead_overview'], 'judgments': view['judgments'],
                'sections': [s for s in view['outline'] if s['id'] in issue['section_ids']], 'materials': view['materials'],
                'instruction': 'Investigate this relationship and its implications; the existing judgment is revisable. Return a complete workpaper, not just replacement wording.'}

    def synthesis_basis(self, state):
        return canonical_sha256({'lead_judgment_ids':state['lead_judgment_ids'],
            'sections':self._section_basis(state,list(state['sections'])),
            'leads':{k:state['judgments'][k] for k in self._closure(state,state['lead_judgment_ids'])}})

    def review_handoff(self, since_revision=0):
        with self.w.connection() as db:
            state=self._state(db)
            if not state['revision']:
                return None
            previous=self._state(db,since_revision) if since_revision else {'judgments':{}}
            changed={k:list(self._difference(previous['judgments'].get(k,{}),v)) for k,v in state['judgments'].items()
                     if previous['judgments'].get(k)!=v}
            return {'understanding_revision':state['revision'], 'comparison_base_revision':since_revision,
                'lead_judgments':{k:state['judgments'][k] for k in state['lead_judgment_ids']},
                'changed_judgments':changed,'outline':list(state['sections'].values()),
                'readback':{'tool':'read_authoring_context','arguments':{'revision':state['revision']}},
                'instruction':'Review the actual report and updated explanation against the original question. Changed field names are navigation; read the exact current judgments and complete arguments. Current judgments are revisable, not an answer key.'}

    def resolve(self, issue_id, base_revision, disposition, explanation, results, report, *, prose_uses=None, direct_evidence=None):
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
            if issue['kind'] in {'missing_link', 'access_failure'} and not refs and not direct_evidence:
                raise WorkpaperConflict('investigation_result_required_even_for_bounded_answer')
            for ref in refs:
                paper = self.w._get(db, ref['topic_id'], ref['revision'])
                assignment = paper['original_task'].get('assignment') or {}
                if (assignment.get('authoring_issue_id') != issue_id or paper['digest'] != ref['digest']
                    or self.w._latest(db).get(ref['topic_id']) != ref['revision'] or self.w._stale(db,paper,self.w._latest(db))):
                    raise WorkpaperConflict('resolution_requires_current_linked_result')
                if not db.execute('SELECT 1 FROM reads WHERE actor=? AND topic=? AND revision=?', ('root',ref['topic_id'],ref['revision'])).fetchone():
                    raise WorkpaperConflict('read_resolution_argument_first')
            anchors = [SectionUse.model_validate(u).model_dump(mode='json') for u in (prose_uses or [])]
            if any(a['section_id'] not in issue['section_ids'] or report.get(a['field'],'').count(a['excerpt']) != 1 for a in anchors):
                raise WorkpaperConflict('resolution_prose_requires_unique_related_passage')
            # Track whole paragraphs around explicit anchors; a tiny unchanged phrase cannot hide a
            # changed assertion in the same paragraph. Legacy callers conservatively track the field.
            for a in anchors:
                text=report[a['field']];start=text.index(a['excerpt']);end=start+len(a['excerpt'])
                left=text.rfind('\n\n',0,start);right=text.find('\n\n',end)
                a['excerpt']=text[0 if left<0 else left+2:len(text) if right<0 else right]
            prose={'anchors':anchors,'fields':{} if anchors else {issue['field']:canonical_sha256(report.get(issue['field'],''))}}
            if disposition=='revised' and issue['quote'] not in report.get(issue['field'],''):
                prose['removed_quote']={'field':issue['field'],'quote':issue['quote']}
            value = {'disposition': disposition, 'explanation': explanation, 'results': refs, 'basis': basis, 'prose':prose,
                     'direct_evidence':list(direct_evidence or {}),
                     'report_digest': canonical_sha256(report), 'understanding_revision': base_revision}
            for key,evidence in (direct_evidence or {}).items():
                wire=json.dumps(evidence,ensure_ascii=False,sort_keys=True)
                old=db.execute('SELECT payload FROM evidence WHERE id=?',(key,)).fetchone()
                if old and old[0]!=wire:
                    raise RuntimeError('evidence_identity_collision')
                db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?)',(key,wire))
            previous = db.execute('SELECT revision,payload FROM authoring_resolutions WHERE id=? ORDER BY revision DESC LIMIT 1',(issue_id,)).fetchone()
            if not previous or json.loads(previous[1]) != value:
                db.execute('INSERT INTO authoring_resolutions VALUES (?,?,?)',(issue_id,previous[0]+1 if previous else 1,json.dumps(value,ensure_ascii=False)))
            db.execute('INSERT OR REPLACE INTO authoring_report VALUES (1,?)',(json.dumps(report,ensure_ascii=False),))
            return {'saved': True, 'issue_id': issue_id, 'disposition':disposition,
                    'readback':{'tool':'read_authoring_context','arguments':{'section_ids':issue['section_ids'],'include_history':True}},
                    'semantic_approval': False}

    def binding(self, db, snapshot, report_digest, report, section_uses):
        state = self._state(db)
        if not state['revision']:
            return None  # Existing tasks keep their legacy whole-report contract.
        if report is not None and canonical_sha256(report) != report_digest:
            raise WorkpaperConflict('report_digest_does_not_match_saved_prose')
        if (snapshot.get('understanding_basis') != self.synthesis_basis(state) if 'understanding_basis' in snapshot
                else snapshot.get('understanding_digest') != state['digest']):
            raise WorkpaperConflict('understanding_changed_refresh_synthesis')
        needed=self._closure(state,state['lead_judgment_ids']+[j for s in state['sections'].values() for j in s['judgment_ids']])
        if set(self._impacts(db, state)) & needed:
            raise WorkpaperConflict('reassess_judgments_before_delivery')
        if not state['lead_judgment_ids'] or not state['sections']:
            raise WorkpaperConflict('authoring_requires_current_thesis_and_outline')
        if any(i['status'] == 'open' for i in self._issues(db,state,report)):
            raise WorkpaperConflict('resolve_authoring_issues_before_delivery')
        uses = [SectionUse.model_validate(u).model_dump(mode='json') for u in (section_uses or [])]
        if (report or {}).get('title') and not any(u['field']=='title' for u in uses):
            raise WorkpaperConflict('bind_report_title_to_current_judgment')
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
    active={c['receipt_id'] for c in candidates if not c.get('retired')}
    def scope(body):
        return (tuple(sorted(body['selected_sections'])),body.get('include_history',False))
    def live(body):
        try:
            return current(body['selected_sections'],body.get('include_history',False)) if callable(current) else current
        except WorkpaperConflict as exc:
            if str(exc)!='unknown_authoring_section':
                raise
            # Removing a provisional section is legitimate. Its historical view has no same-scope
            # replacement; preserve/restore it instead of failing the native pre-step hook.
            return {'context_generation':None,'revision':None}
    for message in messages:
        if not isinstance(message,ToolMessage) or message.name != 'read_authoring_context' or message.status != 'success':
            continue
        body = json.loads(message.content)
        if 'result_digest' not in body:
            continue
        originals[message.tool_call_id] = (message,body)
        if (message.tool_call_id in active and not body.get('historical_read')
                and body.get('context_generation') == live(body)['context_generation']):
            newest[scope(body)] = message.tool_call_id
    replacements = []
    for candidate in candidates:
        pair = originals.get(candidate.get('receipt_id'))
        if not pair:
            continue
        message,body = pair
        newer = newest.get(scope(body))
        if newer and newer != message.tool_call_id and not body.get('historical_read'):
            receipt = {'receipt_id':message.tool_call_id,'status':'success','result':{
                'result_digest':body['result_digest'],'context_state':'superseded_authoring_view',
                'old_revision':body['revision'],'current_revision':live(body)['revision'],
                'current_view_receipt_id':newer,
                'current_readback':{'tool':'read_authoring_context','arguments':{'section_ids':body['selected_sections']}},
                'original_readback':{'tool':'read_saved_result','arguments':{'tool_call_id':message.tool_call_id}}}}
        elif candidate.get('retired'):
            receipt = model_receipt(message)
            receipt['context_notice'] = 'No current same-scope replacement has been read; recover current authoring context.'
        else:
            continue
        replacements.append({'receipt_id':message.tool_call_id,'result_digest':body['result_digest'],'receipt':receipt})
    return replacements


def material_context_replacements(messages, candidates):
    """Retire exact duplicate windows only while later covering reads remain active."""
    from langchain_core.messages import ToolMessage
    from .harness_business_tools import model_receipt
    from .research_result_acceptance import workpaper_conditions
    active={c['receipt_id'] for c in candidates if not c.get('retired')}
    rows={}
    for index,message in enumerate(messages):
        if isinstance(message,ToolMessage) and message.status=='success' and message.name in {'read_research_workpaper','read_synthesis_material'}:
            body=json.loads(message.content)
            if body.get('result_digest') and isinstance(body.get('body'),str):
                rows[message.tool_call_id]=(index,message,body)
    result=[];retiring=set()
    for item in sorted(candidates,key=lambda c:rows.get(c['receipt_id'],(-1,))[0],reverse=True):
        row=rows.get(item['receipt_id'])
        if not row:
            continue
        index,message,body=row
        start=body['offset'];end=start+len(body['body']);cursor=start;cover=[]
        windows=sorted((other['offset'],other['offset']+len(other['body']),key,other) for key,(i,m,other) in rows.items()
            if i>index and key in active and key not in retiring and all(other.get(k)==body.get(k) for k in ('topic_id','revision','digest')))
        for left,right,key,other in windows:
            if left>cursor or right<=cursor:
                continue
            lo=max(start,left);hi=min(end,right)
            if body['body'][lo-start:hi-start]!=other['body'][lo-left:hi-left]:
                continue
            cursor=min(end,right);cover.append(key)
            if cursor==end:
                break
        if cursor==end and cover:
            retiring.add(message.tool_call_id)
            receipt={'receipt_id':message.tool_call_id,'status':'success','result':{
                'result_digest':body['result_digest'],'context_state':'duplicate_material_window',
                'active_window_receipts':cover,'workpaper_conditions':workpaper_conditions(body),
                'original_readback':{'tool':'read_saved_result','arguments':{'tool_call_id':message.tool_call_id}}}}
        elif item.get('retired') and item.get('context_state')=='duplicate_material_window':
            receipt=model_receipt(message)
            receipt['context_notice']='Covering windows left the active surface; exact original restored.'
        else:
            continue
        result.append({'receipt_id':message.tool_call_id,'result_digest':body['result_digest'],'receipt':receipt})
    return result
