"""Demote source-proved cover fields and unit labels without deleting content."""
from copy import deepcopy
import re
from native_document_adaptation import finish
from source_structure_contract import normalized

UNIT_LABEL=re.compile(r'^\(\s*(?:amounts?\s+)?in\s+(?:thousands|millions|billions)(?:\s+of\s+(?:U\.?S\.?\s+)?dollars)?(?:\s*,?\s*(?:except|unless)\s+[^()]{1,100})?\s*\)$',re.I)
MONTH_FIELD=re.compile(r'^For the month of\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}\.?$',re.I)


def repair_context_roles(previous):
    d=deepcopy(previous);sources={r['id']:r for r in d.get('source_containers',[])};blocks=d['blocks'];changes=[];demoted={}
    form_parents={r.get('parent_id') for r in sources.values() if re.fullmatch(r'Form\s+6-K',normalized(r['text']),re.I) and not r.get('table_id') and not r.get('excluded_navigation')}
    for i,b in enumerate(blocks):
        if b['kind']!='heading':continue
        candidates=[sources[s] for s in ([b['source_container_id']] if b.get('source_container_id') else b.get('source_container_candidates',[])) if s in sources]
        if not candidates or any(normalized(r['text'])!=normalized(b['text']) or r.get('excluded_navigation') or r.get('internal_link_only') for r in candidates):continue
        role=None;text=normalized(b['text'])
        if UNIT_LABEL.fullmatch(text):role='unit_context'
        elif MONTH_FIELD.fullmatch(text) and all(r.get('parent_id') is not None and r.get('parent_id') in form_parents for r in candidates):role='filing_cover_period'
        if not role:continue
        nodes=[n for n in d['chapter_tree'] if n['block']==i and not n.get('embedded_in_table')]
        if len(nodes)!=1:continue
        node=nodes[0];demoted[node['id']]=node.get('parent_id')
        node.update(navigation_status='compatibility_only',structural_role=role,chapter_binding_status='role_reference_not_section')
        b.update(kind='text',structural_role=role,candidate_role='attached_context_candidate' if role=='unit_context' else 'retained_structure',
                 role_basis='complete_original_unit_label' if role=='unit_context' else 'original_month_field_shares_form_6k_container')
        changes.append(dict(block=i,chapter_id=node['id'],role=role,source_candidates=[r['id'] for r in candidates]))
    by_id={n['id']:n for n in d['chapter_tree']}
    def active(cid):
        seen=set()
        while cid in demoted:
            if cid in seen:raise ValueError('role_parent_cycle')
            seen.add(cid);cid=demoted[cid]
        return cid
    for n in d['chapter_tree']:
        if n['id'] not in demoted:n['parent_id']=active(n.get('parent_id'))
    for b in blocks:
        ids=[cid for cid in b.get('chapter_ids',[]) if cid not in demoted]
        b['chapter_ids']=ids;b['chapter_blocks']=[by_id[cid]['block'] for cid in ids]
    d['source_role_repairs']=changes
    if changes:finish(d)
    return d
