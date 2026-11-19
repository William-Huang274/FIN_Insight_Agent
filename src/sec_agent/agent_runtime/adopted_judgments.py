"""Reuse a lead's versioned finding and its archived citation identities."""
import json

from langchain_core.messages import messages_from_dict
from .authoring_materials import workpaper_locator
from .research_graph_contracts import canonical_sha256
from .research_workpapers import WorkpaperConflict
from .source_references import reference_sources, reference_handle


def citation_view(source_id, item):
    view = {'source_id': source_id, 'handle': reference_handle(source_id)}
    for field in ('title','source_url','publication_date','as_of','period','unit'):
        if item.get(field):
            view[field] = item[field]
    passage = item.get('passage')
    if isinstance(passage,str):
        view['passage_preview'] = passage[:320]
        view['passage_characters'] = len(passage)
    return view


def evidence_for_judgment(workspace, db, judgment, receipt_ids):
    """Only the lead's affirmative/qualified source versions can supply references."""
    refs = [r for r in judgment['workpapers'] if r['use'] in ('qualified', 'adopted')]
    allowed, visited = set(), set()
    selected = set(receipt_ids)
    stack = [(ref, ()) for ref in refs]
    while stack:
        ref, ancestors = stack.pop()
        topic = ref['topic_id']
        if topic in ancestors:
            continue  # Version lineage can revisit an earlier revision of the same topic.
        key = (topic,ref['revision'],ancestors)
        if key in visited:
            continue
        visited.add(key)
        paper = workspace._get(db,topic,ref['revision'])
        if ref['digest'] != paper['digest']:
            raise WorkpaperConflict('judgment_source_digest_changed')
        allowed.update(selected.intersection(paper['evidence_receipt_ids']))
        for dep in paper['dependencies']:
            if dep['use'] in ('adopted','qualified') and dep['topic_id'] not in (*ancestors, topic):
                stack.append((dep,(*ancestors,topic)))
    sources, originals = [], []
    for key in dict.fromkeys(receipt_ids):
        if key not in allowed:
            raise WorkpaperConflict('receipt_outside_adopted_judgment')
        row = db.execute('SELECT payload FROM evidence WHERE id=?', (key,)).fetchone()
        if not row:
            raise WorkpaperConflict('missing_adopted_source_receipt')
        original = messages_from_dict([json.loads(row[0])])[0]
        if original.tool_call_id != key or original.status != 'success':
            raise WorkpaperConflict('invalid_adopted_source_receipt')
        items, _ = reference_sources({'messages': [original]})
        if not items:
            raise WorkpaperConflict('receipt_has_no_citable_original')
        originals.append(original)
        sources.append({'receipt_id':key, 'original_digest':canonical_sha256(json.loads(row[0])),
            'readback':{'tool':'read_workpaper_evidence','arguments':{'receipt_id':key}},
            'citations':[citation_view(sid,item) for sid,item in items.items()]})
    return sources, originals


def reuse_judgment(workspace, section_id, judgment_id, digest, source_receipts):
    with workspace.connection() as db:
        state = workspace.authoring._state(db)
        section = state['sections'].get(section_id)
        if not section or judgment_id not in workspace.authoring._closure(state,section['judgment_ids']):
            raise WorkpaperConflict('judgment_outside_section')
        judgment = state['judgments'][judgment_id]
        if (judgment['status'] != 'active' or canonical_sha256(judgment) != digest
                or judgment_id in workspace.authoring._impacts(db,state)):
            raise WorkpaperConflict('read_current_adopted_judgment')
        chosen = list(dict.fromkeys(judgment.get('representative_receipts', []) + source_receipts))
        if len(chosen)>12:
            raise WorkpaperConflict('select_specific_judgment_sources')
        sources, originals = evidence_for_judgment(workspace,db,judgment,chosen)
        for source in sources:
            source['selection'] = ('lead' if source['receipt_id'] in judgment.get('representative_receipts', [])
                                   else 'writer_from_versioned_workpaper')
        value = {k: judgment[k] for k in ('statement', 'rationale', 'conditions', 'counterevidence')}
        value['remaining'] = judgment.get('decision_uncertainty', judgment['remaining'])
        value['workpapers'] = [workpaper_locator(ref, 'metadata') for ref in judgment['workpapers']]
        value['judgment_readback'] = {'tool': 'read_authoring_context', 'arguments': {
            'section_ids': [section_id], 'revision': state['revision'], 'include_history': True}}
        value.update(section_id=section_id, judgment_id=judgment_id, judgment_digest=digest, sources=sources)
        value['result_digest'] = canonical_sha256(value)
        return value, originals
