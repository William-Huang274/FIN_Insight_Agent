"""Verify SEC Part parents from complete original containers and source order.

The stored source-container list is DOM preorder, as emitted by
source_structure_contract. A style label alone is not a boundary proof.
"""
from copy import deepcopy
import re

from source_structure_contract import normalized

PART_LABEL = re.compile(r'part\s+(I|II|III|IV|V|VI|VII|VIII|IX|X)\s*[.:]?$', re.I)


def part_label(text):
    m = PART_LABEL.fullmatch(normalized(text))
    return m[1].upper() if m else None


def body_source(row):
    return not (row.get('table_id') or row.get('role') in {'table', 'container'}
                or row.get('excluded_navigation') or row.get('internal_link_only'))


def proposals(document):
    sources = document['source_containers']; blocks = document['blocks']
    order = {s['id']: i for i, s in enumerate(sources)}
    by_id = {s['id']: s for s in sources}
    markers = [(i, s, part_label(s['text'])) for i, s in enumerate(sources)
               if body_source(s) and part_label(s['text'])]
    located = {}
    for i, b in enumerate(blocks):
        s = by_id.get(b.get('source_container_id'))
        if (s and body_source(s) and b.get('source_location_status') == 'unique_complete_container'
                and normalized(b['text']) == normalized(s['text'])):
            located[i] = order[s['id']]
    for u in document.get('source_heading_units', []):
        for i in u['blocks']:
            located[i] = order[u['source_id']]
    result = []
    for u in document.get('source_heading_units', []):
        expected = document.get('parser_sections', {}).get(u['section'], {}).get('part')
        if not expected:
            continue
        item_position = order[u['source_id']]
        prior = [m for m in markers if m[0] < item_position]
        proof = dict(unit=u['id'], section=u['section'], chapter=u['chapter_id'],
                     native_part_proposal=expected, selected_part=None)
        if not prior:
            result.append(dict(proof, status='no_complete_original_part')); continue
        position, source, part = prior[-1]
        proof.update(source_id=source['id'], original_part=part,
                     source_role=source['role'], source_order=position, item_source_order=item_position)
        if part != str(expected).upper():
            result.append(dict(proof, status='nearest_original_part_disagrees')); continue
        # Repeated page headers may have the same complete label as a Part.
        # They are boundaries to inspect, not new roots to prefer over a valid
        # existing parent. Require one occurrence in the current Part sequence.
        sequence=[]
        for marker in reversed(prior):
            if marker[2] != part: break
            sequence.append(marker[1]['id'])
        if len(sequence)>1:
            result.append(dict(proof, status='repeated_part_containers_require_role_review',
                               repeated_source_ids=list(reversed(sequence)))); continue
        candidates = []
        for i, b in enumerate(blocks[:u['blocks'][0]]):
            if b['kind'] not in {'heading', 'text'} or part_label(b['text']) != part:
                continue
            current = b.get('source_container_id')
            if current and current != source['id'] and body_source(by_id.get(current, {})):
                continue
            left = next((j for j in range(i-1, -1, -1) if j in located), None)
            right = next((j for j in range(i+1, len(blocks)) if j in located), None)
            exact = current == source['id'] and located.get(i) == position
            bracket = (left is not None and right is not None
                       and located[left] < position < located[right])
            if exact or bracket:
                candidates.append(dict(block=i, bracket_blocks=[left, right], exact=exact))
        if len(candidates) != 1:
            result.append(dict(proof, status='part_parser_position_not_unique', matches=len(candidates))); continue
        result.append(dict(proof, status='verified_original_part_and_item_order',
                           selected_part=part, **candidates[0]))
    return result


def repair(document):
    proofs = proposals(document)
    d = deepcopy(document); nodes = {n['id']: n for n in d['chapter_tree']}
    changed = set(); adopted = []
    for p in proofs:
        if not p['selected_part']:
            continue
        unit = next(u for u in d['source_heading_units'] if u['id'] == p['unit'])
        node = nodes[p['chapter']]
        if (unit.get('part') == p['selected_part'] and unit.get('part_source_id') == p['source_id']
                and node.get('parent_id')):
            p['changed'] = False
            continue
        p['changed'] = True
        parent_id = 'verified-part:' + p['source_id']
        existing = [n for n in nodes.values() if n['block'] == p['block']
                    and part_label(n['title']) == p['selected_part']
                    and n.get('navigation_status') != 'compatibility_only']
        if len(existing) == 1:
            parent_id = existing[0]['id']
        if parent_id not in nodes:
            source = next(s for s in d['source_containers'] if s['id'] == p['source_id'])
            parent = dict(id=parent_id, block=p['block'], title=source['text'], level=1,
                          parent_id=None, source_container_id=p['source_id'],
                          basis='original_part_container_and_item_order')
            d['chapter_tree'].append(parent); nodes[parent_id] = parent
        else:
            nodes[parent_id].update(parent_id=None, level=1, source_container_id=p['source_id'],
                                    basis='original_part_container_and_item_order')
        node['parent_before_source_part'] = node.get('parent_id')
        node.update(parent_id=parent_id, level=2, parent_resolution=p['status'])
        unit['part_before_source_part'] = unit.get('part')
        unit.update(part=p['selected_part'], part_source_id=p['source_id'], parent_resolution=p['status'])
        changed.add(node['id']); adopted.append(p)
    def ancestry(cid):
        path=[]; seen=set()
        while cid:
            if cid in seen: raise ValueError('part_hierarchy_cycle')
            seen.add(cid); path.append(cid); cid=nodes[cid].get('parent_id')
        return list(reversed(path))
    for b in d['blocks']:
        old=b.get('chapter_ids', [])
        if not changed.intersection(old): continue
        if b.get('effective_scope', {}).get('kind') == 'source_signature_scope':
            raise ValueError('part_repair_would_change_signature_scope')
        b['chapter_ids_before_source_part']=list(old)
        b['chapter_ids']=ancestry(old[-1]); b['chapter_blocks']=[nodes[c]['block'] for c in b['chapter_ids']]
    resolved={p['unit'] for p in adopted}
    conflicts=d.get('heading_parent_conflicts', [])
    d['heading_parent_conflict_history']=deepcopy(conflicts)
    d['heading_parent_conflicts']=[c for c in conflicts if c['unit'] not in resolved]
    d['source_part_proofs']=proofs
    # Shared physical ranges retain every identity; no guessed unique ownership.
    units={u['section']:u for u in d.get('source_heading_units', [])}
    d['shared_range_reviews']=[dict(g, heading_evidence_sections=[s for s in g['sections'] if s in units],
        status='shared_extent_requires_reference_or_boundary_proof', canonical_section=None)
        for g in d.get('shared_native_range_groups', [])]
    from native_document_adaptation import finish
    return finish(d), proofs
