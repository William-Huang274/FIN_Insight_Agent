"""Durable chapter drafts and reversible native receipt retirement.

No model summary is generated here. The author selects the chapter, writes its
prose and takeaway, and names the successful receipts used. SQLite retains the
exact versions; native surface replacement does not modify canonical history.
"""
import json
from langchain_core.messages import ToolMessage, messages_to_dict
from .research_graph_contracts import canonical_sha256
from .research_workpapers import WorkpaperConflict
from .assessment_evidence import section_counterexamples
from .authoring_editorial import EDITORIAL_BRIEF, writing_judgments
from pydantic import BaseModel, ConfigDict, Field


class MaterialUse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    receipt_id: str
    purpose: str = Field(min_length=1, max_length=2000,
        description='What the exact observed window contributes: mechanism, comparison, counterevidence or another author-selected use.')

MATERIAL_TOOLS = frozenset({'reuse_adopted_judgment', 'read_synthesis_material', 'read_research_workpaper',
    'read_workpaper_evidence', 'read_saved_result', 'calculate_research_metric'})


class AuthoringSections:
    def __init__(self, workspace):
        self.w = workspace
        with workspace.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS authoring_sections (
                    section TEXT, revision INTEGER, payload TEXT,
                    PRIMARY KEY(section,revision));
                CREATE TABLE IF NOT EXISTS authoring_focus (
                    id INTEGER PRIMARY KEY CHECK(id=1), section TEXT);
                CREATE TABLE IF NOT EXISTS authoring_editing (
                    id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT);
                CREATE TABLE IF NOT EXISTS authoring_workset (
                    id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT);
                CREATE TABLE IF NOT EXISTS authoring_released_materials (
                    receipt TEXT PRIMARY KEY, payload TEXT);
            ''')

    def _latest(self, db):
        return {s:json.loads(p) for s,p in db.execute('''SELECT section,payload FROM authoring_sections a
            WHERE revision=(SELECT MAX(revision) FROM authoring_sections b WHERE b.section=a.section)''')}

    def _status(self, db, value, state):
        key = value['section_id']
        if key not in state['sections']:
            return 'removed'
        basis = self.w.authoring._section_basis(state,[key])
        observations = section_counterexamples(self.w,db,state,[key],draft=value)
        if value.get('counterexample_digest') != (canonical_sha256(observations) if observations else None):
            return 'needs_update'
        if value['basis'] != basis or set(basis['judgments']) & set(self.w.authoring._impacts(db,state)):
            return 'needs_update'
        return 'current'

    def overview(self, *, db=None):
        if db is None:
            with self.w.connection() as conn:
                return self.overview(db=conn)
        state = self.w.authoring._state(db)
        result=[]
        for k,v in self._latest(db).items():
            reasons=self.update_reasons(db,v,state)
            status='removed' if k not in state['sections'] else 'needs_update' if reasons else 'current'
            result.append({'section_id':k,'revision':v['revision'],'status':status,
                'update_reasons':reasons,'takeaway':v['takeaway'],
                'readback':{'tool':'authoring_section','arguments':{'section_id':k,'action':'read','revision':v['revision']}}})
        return result

    def update_reasons(self, db, chapter, state):
        if chapter['section_id'] not in state['sections']:
            return ['section_removed']
        current=self.w.authoring._section_basis(state,[chapter['section_id']])
        prior=chapter['basis']; reasons=[]
        if prior.get('sections') != current['sections']:
            reasons.append('section_responsibility_changed')
        if prior.get('editorial_dependencies') != current.get('editorial_dependencies'):
            reasons.append('related_section_responsibility_changed')
        if prior['judgments'] != current['judgments'] or set(current['judgments']) & set(self.w.authoring._impacts(db,state)):
            reasons.append('judgment_or_evidence_changed')
        return reasons

    def working_set(self, db):
        row = db.execute('SELECT payload FROM authoring_workset WHERE id=1').fetchone()
        return json.loads(row[0]) if row else None

    def select(self, db, state, section_ids):
        return self.w.authoring.select_workset(db,state,section_ids)

    def release(self, receipt_ids, reason, messages):
        """Explicitly shelve inspected, unused receipts; preserve exact bytes and why."""
        if not receipt_ids or not reason.strip():
            raise WorkpaperConflict('release_requires_receipts_and_reason')
        observed = {m.tool_call_id:m for m in messages if isinstance(m,ToolMessage)
                    and m.status=='success' and m.name in MATERIAL_TOOLS}
        with self.w.connection() as db:
            adopted = {r for v in self._latest(db).values() for r in v['receipts']}
            for key in receipt_ids:
                if key not in observed or key in adopted:
                    raise WorkpaperConflict('release_only_successful_unused_material')
                m=observed[key]
                try: result=json.loads(m.content)
                except (ValueError,TypeError): result=None
                if not isinstance(result,dict) or result.get('error') or not result.get('result_digest'):
                    raise WorkpaperConflict('release_requires_exact_successful_material')
                wire=json.dumps(messages_to_dict([m])[0],ensure_ascii=False,sort_keys=True)
                old=db.execute('SELECT payload FROM evidence WHERE id=?',(key,)).fetchone()
                if old and json.loads(old[0])!=json.loads(wire):
                    raise WorkpaperConflict('chapter_receipt_identity_changed')
                db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?)',(key,wire))
                value={'content_digest':canonical_sha256(m.content),'reason':reason,
                       'understanding_digest':self.w.authoring._state(db)['digest']}
                db.execute('INSERT OR REPLACE INTO authoring_released_materials VALUES (?,?)',(key,json.dumps(value)))
            if not self.working_set(db) and self.w.authoring._state(db)['sections']:
                self.select(db,self.w.authoring._state(db),None)
        return {'released':list(dict.fromkeys(receipt_ids)), 'reason':reason,
                'readbacks':[{'tool':'read_workpaper_evidence','arguments':{'receipt_id':r}} for r in dict.fromkeys(receipt_ids)],
                'meaning':'Unused in the current argument, not disproven or unavailable. Exact originals remain readable.'}

    def act(self, section_id, action, *, prose='', takeaway='', receipt_ids=None,
            messages=(), revision=None, base_revision=None, section_ids=None, material_uses=None, reason=''):
        if action == 'assemble':
            return self.assemble(section_ids)
        if action == 'release':
            return self.release(receipt_ids,reason,messages)
        if action == 'select':
            with self.w.connection() as db:
                selected=self.select(db,self.w.authoring._state(db),section_ids)
                db.execute('DELETE FROM authoring_focus')
            return {'working_set':selected,'context':self.w.authoring.context(selected['section_ids'])}
        if action not in {'open','save','read'}:
            raise WorkpaperConflict('unknown_authoring_section_action')
        with self.w.connection() as db:
            state = self.w.authoring._state(db)
            if section_id not in state['sections'] and action != 'read':
                raise WorkpaperConflict('unknown_authoring_section')
            latest = self._latest(db)
            if action == 'save':
                current_revision = latest.get(section_id,{}).get('revision',0)
                if base_revision != current_revision:
                    raise WorkpaperConflict('chapter_version_changed_read_current')
                if not prose.strip() or not takeaway.strip() or not receipt_ids:
                    raise WorkpaperConflict('chapter_requires_prose_takeaway_and_read_receipts')
                basis = self.w.authoring._section_basis(state,[section_id])
                if set(basis['judgments']) & set(self.w.authoring._impacts(db,state)):
                    raise WorkpaperConflict('reassess_judgments_before_saving_chapter')
                observed={m.tool_call_id:m for m in messages if isinstance(m,ToolMessage)
                    and m.status=='success' and m.name in MATERIAL_TOOLS}
                refs={}
                uses=[MaterialUse.model_validate(u).model_dump() for u in (material_uses or [])]
                if len({u['receipt_id'] for u in uses})!=len(uses) or any(u['receipt_id'] not in receipt_ids for u in uses):
                    raise WorkpaperConflict('material_purpose_requires_selected_receipt')
                for key in dict.fromkeys(receipt_ids):
                    if key not in observed:
                        raise WorkpaperConflict('chapter_material_requires_successfully_read_receipt')
                    message=observed[key]
                    try: body=json.loads(message.content)
                    except (ValueError,TypeError): body=None
                    if not isinstance(body,dict) or body.get('error') or body.get('saved') is False:
                        raise WorkpaperConflict('chapter_material_requires_successfully_read_receipt')
                    if message.name == 'reuse_adopted_judgment' and (
                            body.get('section_id') != section_id or not body.get('judgment_digest') or
                            basis['judgments'].get(body.get('judgment_id')) != body['judgment_digest']):
                        raise WorkpaperConflict('chapter_requires_current_adopted_judgment')
                    refs[key]={'content_digest':canonical_sha256(message.content),
                               'result_digest':body.get('result_digest'), 'tool':message.name}
                    wire=json.dumps(messages_to_dict([message])[0],ensure_ascii=False,sort_keys=True)
                    old=db.execute('SELECT payload FROM evidence WHERE id=?',(key,)).fetchone()
                    if old and json.loads(old[0])!=json.loads(wire):
                        raise WorkpaperConflict('chapter_receipt_identity_changed')
                    db.execute('INSERT OR IGNORE INTO evidence VALUES (?,?)',(key,wire))
                    db.execute('DELETE FROM authoring_released_materials WHERE receipt=?',(key,))
                value={'section_id':section_id,'revision':current_revision+1,'prose':prose,
                       'takeaway':takeaway,'basis':basis,'receipts':refs,
                       'understanding_revision':state['revision'], 'material_uses':uses}
                from .chapter_citations import archive_chapter_citations
                prior = latest.get(section_id, {})
                observations = section_counterexamples(self.w,db,state,[section_id],draft=value)
                if observations:
                    value['counterexample_digest'] = canonical_sha256(observations)
                value['citation_receipts'] = archive_chapter_citations(db, prose, messages, prior.get('citation_receipts'))
                db.execute('INSERT INTO authoring_sections VALUES (?,?,?)',
                    (section_id,value['revision'],json.dumps(value,ensure_ascii=False)))
                # Explicit successful save releases focus; open again to work on it.
                db.execute('DELETE FROM authoring_focus WHERE section=?',(section_id,))
                result={'saved':True,'section_id':section_id,'revision':value['revision'],
                        'takeaway':takeaway,'readback':{'tool':'authoring_section',
                            'arguments':{'section_id':section_id,'action':'read','revision':value['revision']}}}
            elif action == 'open':
                self.select(db,state,[section_id])
                db.execute('INSERT OR REPLACE INTO authoring_focus VALUES (1,?)',(section_id,))
                draft = latest.get(section_id)
                if draft and self.w.authoring_active(db):
                    draft = {'section_id':section_id, 'revision':draft['revision'],
                             'takeaway':draft['takeaway'], 'status':self._status(db,draft,state),
                             'readback':{'tool':'authoring_section','arguments':{
                                 'section_id':section_id,'action':'read','revision':draft['revision']}}}
                result={'section_id':section_id,'current_context':self.w.authoring.context([section_id],_db=db),
                        'draft':draft, 'next_step':'Explain this section\'s finding, mechanism and decision implications. Read the relevant arguments and evidence as needed. Save the chapter; whole-report editing may later merge, shorten or omit it.'}
            else:
                value=latest.get(section_id)
                if revision is not None:
                    row=db.execute('SELECT payload FROM authoring_sections WHERE section=? AND revision=?',
                                   (section_id,revision)).fetchone()
                    value=json.loads(row[0]) if row else None
                if value is None:
                    raise WorkpaperConflict('unknown_saved_chapter_revision')
                result={**value,'status':self._status(db,value,state),
                        'current_revision':latest[section_id]['revision'],
                        'source_readbacks':[{'tool':'read_saved_result','arguments':{'tool_call_id':k},
                                            'content_digest':r['content_digest']} for k,r in value['receipts'].items()]}
            result['chapters']=self.overview(db=db)
            result['result_digest']=canonical_sha256(result)
            return result

    def editing_status(self, db):
        row=db.execute('SELECT payload FROM authoring_editing WHERE id=1').fetchone()
        if not row:
            return {'status':'not_opened','readback':{'tool':'authoring_section','arguments':{'section_id':'','action':'assemble'}}}
        saved=json.loads(row[0]); state=self.w.authoring._state(db)
        scope=saved.get('section_ids')
        current={k:v['revision'] for k,v in self._latest(db).items() if k in state['sections'] and (scope is None or k in scope)}
        missing=scope is not None and any(k not in state['sections'] for k in scope)
        changed=saved['chapters']!=current or missing or (
            saved['editorial_basis']!=self.w.authoring.synthesis_basis(state,scope)
            if 'editorial_basis' in saved and not missing else saved['understanding_digest']!=state['digest'])
        if not changed:
            observations = section_counterexamples(self.w,db,state,list(current),whole=scope is None)
            changed = saved.get('counterexample_digest') != (canonical_sha256(observations) if observations else None)
        versions = [{'section_id':key, 'title':state['sections'].get(key, {}).get('title', key),
                     'assembled_revision':saved['chapters'].get(key), 'current_revision':current.get(key)}
                    for key in sorted(saved['chapters'].keys() | current.keys())
                    if saved['chapters'].get(key) != current.get(key)]
        refresh_scope = [key for key in scope if key in state['sections']] if missing else scope
        readback = {'tool':'authoring_section','arguments':{'section_id':'','action':'assemble', 'section_ids':refresh_scope}}
        if changed and not current:
            readback = {'tool':'read_authoring_context','arguments':{}}
        return {'status':'inputs_changed' if changed else 'editing', **saved,
                **({'changed_chapters':versions} if versions else {}), 'readback':readback,
                'semantic_approval':False}

    def assemble(self, section_ids=None):
        """One current editing workset, with exact versioned chapters and deduplicated source navigation."""
        with self.w.connection() as db:
            state=self.w.authoring._state(db); latest=self._latest(db)
            workset=self.select(db,state,section_ids)
            selected=[latest[s['id']] for s in sorted(state['sections'].values(),key=lambda s:(s['order'],s['id']))
                      if s['id'] in latest and s['id'] in workset['section_ids']]
            if not selected:
                raise WorkpaperConflict('no_saved_chapters_for_editing')
            db.execute('DELETE FROM authoring_focus')
            sources={}
            for value in selected:
                for key,ref in value['receipts'].items():
                    if key in sources and sources[key]['content_digest']!=ref['content_digest']:
                        raise WorkpaperConflict('chapter_receipt_identity_changed')
                    sources[key]={'content_digest':ref['content_digest'],
                        'readback':{'tool':'read_workpaper_evidence','arguments':{'receipt_id':key}}}
            saved={'understanding_revision':state['revision'],'understanding_digest':state['digest'],
                   'section_ids':section_ids,
                   'editorial_basis':self.w.authoring.synthesis_basis(state,section_ids),
                   'chapters':{v['section_id']:v['revision'] for v in selected}}
            observations = section_counterexamples(self.w,db,state,list(saved['chapters']),whole=section_ids is None)
            if observations:
                saved['counterexample_digest'] = canonical_sha256(observations)
            db.execute('INSERT OR REPLACE INTO authoring_editing VALUES (1,?)',(json.dumps(saved),))
            result={'editorial_brief':EDITORIAL_BRIEF, 'basis':saved,
                'working_set':workset,'report_orientation':self.w.authoring.orientation(state),
                'chapters':[{k:v[k] for k in ('section_id','revision','prose','takeaway')} |
                            {'status':self._status(db,v,state)} for v in selected],
                'missing_drafts':[k for k in workset['section_ids'] if k not in latest],
                'source_readbacks':sources,
                'understanding_readback':{'tool':'read_authoring_context','arguments':{}},
                'selection':'合并章节时，按读者实际做决定的先后组织比较。删去案例或数字后，检查保留下来的对照还能支撑哪一句判断；'
                            '若删掉的是足以改变选择的反例，保留它或相应调整结论。涉及另一种分组或成本时，给出它自己的依据。'
                            '可调整提纲；移出的章节和原件仍可回读。'}
            if observations:
                result['reviewed_counterexamples'] = observations
            return {**result,'result_digest':canonical_sha256(result)}

    def replacements(self, messages, candidates):
        from .harness_business_tools import model_receipt
        by_id={m.tool_call_id:m for m in messages if isinstance(m,ToolMessage) and m.status=='success'}
        with self.w.connection() as db:
            state=self.w.authoring._state(db)
            drafts=self._latest(db)
            released={k:json.loads(v) for k,v in db.execute('SELECT receipt,payload FROM authoring_released_materials')}
            focus=db.execute('SELECT section FROM authoring_focus WHERE id=1').fetchone()
            focus=focus[0] if focus else None
            owners={}
            for key,value in drafts.items():
                for receipt_id in value['receipts']:
                    owners.setdefault(receipt_id,[]).append(value)
            out=[]
            for candidate in candidates:
                key=candidate['receipt_id'];message=by_id.get(key)
                if not message: continue
                uses=owners.get(key,[])
                if any(v['receipts'][key]['content_digest']!=canonical_sha256(message.content) for v in uses):
                    raise RuntimeError('chapter_receipt_identity_changed')
                # A changed/shared active chapter keeps its complete evidence live.
                eligible=bool(uses) and all(v['section_id']!=focus and self._status(db,v,state)=='current'
                    and v['receipts'][key]['content_digest']==canonical_sha256(message.content)
                    for v in uses)
                try: body=json.loads(message.content)
                except (ValueError,TypeError): continue
                if not isinstance(body,dict): continue
                digest=body.get('result_digest')
                if not digest: continue
                unused=released.get(key)
                if unused and unused['content_digest']!=canonical_sha256(message.content):
                    raise RuntimeError('released_receipt_identity_changed')
                if unused and not uses and unused['understanding_digest']==state['digest']:
                    receipt={'receipt_id':key,'status':'success','result':{
                        'result_digest':digest,'context_state':'unused_authoring_material',
                        'reason':unused['reason'],'content_digest':unused['content_digest'],
                        'original_readback':{'tool':'read_workpaper_evidence','arguments':{'receipt_id':key}}}}
                elif eligible:
                    receipt={'receipt_id':key,'status':'success','result':{
                        'result_digest':digest,'context_state':'saved_chapter_material',
                        'chapters':[{'section_id':v['section_id'],'revision':v['revision'],'takeaway':v['takeaway'],
                            'readback':{'tool':'authoring_section','arguments':{'section_id':v['section_id'],
                                'action':'read','revision':v['revision']}}} for v in uses],
                        'original_readback':{'tool':'read_saved_result','arguments':{'tool_call_id':key}},
                        'content_digest':canonical_sha256(message.content)}}
                elif candidate.get('retired') and candidate.get('context_state') in {'saved_chapter_material','unused_authoring_material'}:
                    receipt=model_receipt(message)
                    receipt['context_notice']='Chapter reopened or its basis changed; exact saved material restored. Read authoring context for affected chapters.'
                elif (focus and message.name == 'read_synthesis_material' and body.get('offset') == 0
                      and body.get('presentation') == 'authoring_material_v1' and not body.get('snapshot_read_view')
                      and (body.get('adoption_context') or {}).get('snapshot_id')):
                    # Earlier sessions received the complete snapshot history with every first window.
                    # Keep that original receipt immutable and project the version-pinned chapter argument.
                    from .authoring_materials import chapter_argument
                    snap_id = body['adoption_context']['snapshot_id']
                    snap = self.w.snapshot(snap_id, _db=db)
                    topic = body['topic_id']
                    if (focus not in snap.get('section_ids', []) or snap['changed_topics'] or snap['understanding_changed']
                            or snap['selected'].get(topic) != {k:body[k] for k in ('revision','digest')}):
                        if candidate.get('context_state') != 'chapter_argument_view':
                            continue
                        receipt = model_receipt(message)
                    else:
                        argument = chapter_argument(self.w,snap_id,snap,topic,_db=db)
                        receipt = {'receipt_id':key,'status':'success','result':{**argument,'result_digest':digest,
                            'context_state':'chapter_argument_view','original_readback':{
                                'tool':'read_saved_result','arguments':{'tool_call_id':key}}}}
                elif candidate.get('context_state') == 'chapter_argument_view':
                    receipt = model_receipt(message)
                else: continue
                out.append({'receipt_id':key,'result_digest':digest,'receipt':receipt})
            return out


async def project_authoring_context(workspace, bridge, candidates, check):
    import asyncio
    from .research_authoring import authoring_context_replacements, material_context_replacements
    await asyncio.to_thread(check)
    messages=(await bridge.state()).get('messages',[])
    def project():
        check()
        replacements=AuthoringSections(workspace).replacements(messages,candidates)
        used={x['receipt_id'] for x in replacements}
        rest=[c for c in candidates if c['receipt_id'] not in used]
        replacements+=authoring_context_replacements(messages,rest,
            lambda sections,history,**kwargs:workspace.authoring.context(sections,include_history=history,**kwargs))
        used={x['receipt_id'] for x in replacements}
        replacements+=material_context_replacements(messages,[c for c in rest if c['receipt_id'] not in used])
        chapters=AuthoringSections(workspace)
        with workspace.connection() as db:
            current=workspace.authoring._state(db)
            focus=db.execute('SELECT section FROM authoring_focus WHERE id=1').fetchone()
            # Preserve the supporting premises too, once detailed receipts leave the surface.
            # Keep each judgment once in control state, not in every retired receipt.
            roots = list(current['lead_judgment_ids'])
            workset=chapters.working_set(db)
            working_ids=workset['section_ids'] if workset else [c['section_id'] for c in chapters.overview(db=db)]
            for key in working_ids:
                if key in current['sections']:
                    roots.extend(current['sections'][key]['judgment_ids'])
            if focus and focus[0] in current['sections']:
                roots.extend(current['sections'][focus[0]]['judgment_ids'])
            retained = workspace.authoring._closure(current, roots)
            orientation = workspace.authoring.orientation(current)
            active = current['sections'].get(focus[0]) if focus else None
            chapter_focus = None
            if active:
                chapter_focus = {key: active[key] for key in ('id', 'question', 'role')}
                orientation['outline'] = [
                    {k: v for k, v in row.items() if k not in ('question', 'role')}
                    if row['id'] == active['id'] else row for row in orientation['outline']]
            state={'phase':'chapter_authoring','understanding_revision':current['revision'],
                'chapter_focus':chapter_focus,'report_orientation':orientation,
                'working_set':workset,
                'requires_reassessment':workspace.authoring._impacts(db,current),
                'current_findings':writing_judgments({k:current['judgments'][k] for k in sorted(retained)}),
                'chapters':chapters.overview(db=db), 'active_section':active['id'] if active else None,
                'whole_report_editing':chapters.editing_status(db),
                'readback':{'tool':'read_authoring_context','arguments':{}},
                'instruction':'Choose the main explanation and evidence for the reader. Saved chapters remain editable inputs; use assemble for whole-report editing. Reopen needs_update chapters; exact sources remain readable. Bind the outline actually used; omitted research stays archived.'}
            observations = section_counterexamples(workspace,db,current,[active['id']] if active else working_ids,
                whole=not active and state['whole_report_editing']['status']=='editing'
                and state['whole_report_editing'].get('section_ids') is None)
            if observations:
                state['reviewed_counterexamples'] = observations
        return {'replacements':replacements,'control_state':{'generation':canonical_sha256(state),'state':state}}
    return await asyncio.to_thread(project)


async def project_research_and_authoring(workspace, bridge, candidates, check, consultations=None):
    """Normal research, local revision and isolated writing share the same projection.

    Chapter receipts belong exclusively to the writing lifecycle once it is active;
    consultation retirement must not evict a reopened chapter's source material.
    """
    import asyncio
    if not await asyncio.to_thread(workspace.authoring_active):
        return await consultations.context_projection(candidates) if consultations else {'replacements':[]}
    writing = await project_authoring_context(workspace,bridge,candidates,check)
    if not consultations:
        return writing
    messages=(await bridge.state()).get('messages',[])
    protected={m.tool_call_id for m in messages if isinstance(m,ToolMessage)
               and m.name in MATERIAL_TOOLS | {'read_authoring_context'}}
    other=await consultations.context_projection([c for c in candidates if c['receipt_id'] not in protected])
    state=dict(writing['control_state']['state'])
    research=other.get('control_state',{}).get('state')
    if research:
        research=dict(research)
        if 'current_understanding' in research:
            research['current_understanding']={'readback':{'tool':'read_authoring_context','arguments':{}},
                'location':'Current authoring findings and report orientation in this runtime state.'}
        state['research_tasks']=research
    return {'replacements':writing['replacements']+other.get('replacements',[]),
            'control_state':{'generation':canonical_sha256(state),'state':state}}
