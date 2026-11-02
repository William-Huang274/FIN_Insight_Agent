"""Consume source-proven Part labels as structure, retaining physical source text."""
from source_part_hierarchy import part_label


def repair(document):
    result=document;sources={s['id']:s for s in result.get('source_containers',[])}
    nodes=result.get('chapter_tree',[]);changes=[]
    for proof in result.get('source_part_proofs',[]):
        if not proof.get('selected_part') or proof.get('status')!='verified_original_part_and_item_order':continue
        i=proof['block'];block=result['blocks'][i];source=sources.get(proof.get('source_id'))
        parents=[n for n in nodes if n['block']==i and n.get('source_container_id')==proof['source_id']
                 and n.get('basis')=='original_part_container_and_item_order']
        if not source or len(parents)!=1:continue
        if part_label(block['text'])!=proof['selected_part'] or part_label(source['text'])!=proof['selected_part']:continue
        if block['kind'] not in ('text','heading') or block.get('effective_scope',{}).get('kind')=='source_signature_scope':continue
        if block.get('structural_only'):continue
        changes.append(dict(block=i,source_id=proof['source_id'],chapter_id=parents[0]['id'],part=proof['selected_part']))
    if not changes:return document,changes
    changed={c['block'] for c in changes}
    result=dict(document,blocks=[dict(b,structural_only=True,
        structural_marker_basis='verified_part_container_and_existing_parent') if i in changed else b
        for i,b in enumerate(document['blocks'])])
    result['source_marker_consumption_repairs']=changes
    assert [b['text'] for b in result.get('blocks',[])]==[b['text'] for b in document.get('blocks',[])]
    assert result.get('chapter_tree')==document.get('chapter_tree')
    return result,changes
