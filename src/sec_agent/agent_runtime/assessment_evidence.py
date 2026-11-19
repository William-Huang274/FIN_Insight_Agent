"""Decision-changing observations selected by the reviewer of an exact workpaper."""
import json
from langchain_core.messages import ToolMessage, message_to_dict
from .research_decision_context import Counterexample, quote_location
from .research_workpapers import WorkpaperConflict


def record_counterexamples(workspace, actor, ref, digest, disposition, reason, selections, evidence, messages):
    """Persist an exact quote with its review; the reviewer owns its interpretation."""
    with workspace.connection() as db:
        paper = workspace._get(db, ref['topic_id'], ref['revision'])
        if paper['digest'] != ref['digest']:
            raise WorkpaperConflict('assessment_workpaper_identity_changed')
        key = (ref['topic_id'], ref['revision'], actor)
        observations = []
        for selection in selections:
            observed = next((m for m in messages if isinstance(m,ToolMessage) and m.status=='success'
                             and m.tool_call_id==selection.receipt_id), None)
            if selection.receipt_id not in evidence or observed is None:
                raise WorkpaperConflict('counterexample_requires_observed_workpaper_source')
            row = db.execute('SELECT payload FROM evidence WHERE id=?',(selection.receipt_id,)).fetchone()
            wire = message_to_dict(observed)
            if row and json.loads(row[0]) != wire:
                raise WorkpaperConflict('counterexample_original_receipt_changed')
            observation = quote_location(selection,wire['data'],reason)
            if not row:
                db.execute('INSERT INTO evidence VALUES (?,?)',(selection.receipt_id,json.dumps(wire,ensure_ascii=False)))
            observations.append(observation)
        if observations:
            value = dict(workpaper=ref, reviewer=actor, result_digest=digest, disposition=disposition,
                         observations=observations)
            db.execute('INSERT OR REPLACE INTO assessment_evidence VALUES (?,?,?,?)',
                       (*key,json.dumps(value,ensure_ascii=False)))
        else:
            db.execute('DELETE FROM assessment_evidence WHERE topic=? AND revision=? AND reviewer=?',key)
        return observations


def current_counterexamples(workspace, db, roots, *, descend):
    rows = db.execute('SELECT topic,revision,payload FROM assessment_evidence ORDER BY topic,revision,reviewer').fetchall()
    if not rows:
        return []
    latest = workspace._latest(db)
    active = set()
    for topic, revision, digest in set(roots):
        if latest.get(topic) != revision:
            continue
        paper = workspace._get(db,topic,revision)
        if paper['digest'] != digest or workspace._stale(db,paper,latest):
            continue
        lineage = workspace.dependency_walk(db,paper,active_only=True) if descend else [paper]
        active.update((p['topic_id'],p['revision'],p['digest']) for p in lineage)
    result = []
    for topic,revision,payload in rows:
        value = json.loads(payload)
        if (topic,revision,value['workpaper']['digest']) in active:
            result.append(value)
    return result


def section_counterexamples(workspace, db, state, section_ids, *, whole=False, draft=None):
    if not db.execute('SELECT 1 FROM assessment_evidence LIMIT 1').fetchone():
        return []
    section_ids = set(section_ids) & state['sections'].keys()
    ids = [j for s in section_ids for j in state['sections'][s]['judgment_ids']]
    affected = workspace.authoring._impacts(db,state)
    refs = [r for j in workspace.authoring._closure(state,ids) if j not in affected
            and state['judgments'][j]['status']=='active' for r in state['judgments'][j]['workpapers']
            if r['use'] != 'background']
    roots = {(r['topic_id'],r['revision'],r['digest']) for r in refs}
    if whole:
        return current_counterexamples(workspace,db,roots,descend=True)
    other = [j for k,s in state['sections'].items() if k not in section_ids for j in s['judgment_ids']]
    shared = {(r['topic_id'],r['revision'],r['digest']) for j in workspace.authoring._closure(state,other)
              for r in state['judgments'][j]['workpapers'] if r['use']!='background'} & roots
    if not shared:
        return current_counterexamples(workspace,db,roots,descend=True)
    # An omnibus parent can support every chapter. Route its children to the
    # source-reading surface, or to a chapter already using that exact source.
    own = current_counterexamples(workspace,db,roots-shared,descend=True)
    texts = []
    if draft is not None:
        texts = [draft['prose']]
    elif db.execute("SELECT 1 FROM sqlite_master WHERE name='authoring_sections'").fetchone():
        for key in sorted(section_ids):
            row = db.execute('SELECT payload FROM authoring_sections WHERE section=? ORDER BY revision DESC LIMIT 1',(key,)).fetchone()
            if row:
                texts.append(json.loads(row[0])['prose'])
    from .report_synthesis_agent import answer_reference_ids
    cited = set(answer_reference_ids('\n'.join(texts)))
    for item in current_counterexamples(workspace,db,shared,descend=True):
        p = item['workpaper']
        if ((p['topic_id'],p['revision'],p['digest']) in shared or
                any(o['source_id'] in cited for o in item['observations'])) and item not in own:
            own.append(item)
    return own
