"""Recover logical SEC headings without changing physical block identities.

Original containers, TOC bounds, styles and bracketing source locations provide
the proof. Parser sibling identity and company-specific words are not evidence.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import re

from source_structure_contract import normalized

ITEM = re.compile(r'^item\s*(\d+(?:\.\d+)?[a-z]?)(?=[\s.:\[]|$)', re.I)
PART = re.compile(r'^part\s+([ivx]+)(?=[\s.:—–-]|$)', re.I)


def tokens(text):
    return tuple(re.findall(r'\w+|[^\w\s]', normalized(text)))


def number(text):
    match = ITEM.match(normalized(text))
    return match[1].replace('.', '').casefold() if match else None


def geometry(native, sources):
    from lxml import html
    dom = html.fromstring(native['metadata']['fields']['original_html'].encode('utf8'))
    elements = list(dom.iter()); positions = {e:i for i,e in enumerate(elements)}
    tree = dom.getroottree(); paths = {}; anchors = defaultdict(list); ends = {}
    for e in elements:
        paths[tree.getpath(e)] = e
        for a in set(filter(None, (e.get('id'), e.get('name')))):
            anchors[a].append(e)
    for e in reversed(elements):
        ends[e] = max([positions[e]] + [ends[c] for c in e])
    def endpoint(b, role):
        path = b.get('element_paths', {}).get(role+'_element')
        if path:
            return positions.get(paths.get(path))
        a = b['fields'].get('anchor_id' if role=='start' else 'end_element_id')
        if not a:
            return None if role=='start' else len(elements)
        matches = anchors.get(a, [])
        return positions[matches[0]] if len(matches)==1 else None
    ranges = {}
    for key,b in native.get('toc_boundaries', {}).items():
        start,end = endpoint(b,'start'),endpoint(b,'end')
        if start is not None and end is not None and start<end:
            ranges[key] = (start,end)
    spans = {}
    for row in sources:
        e = paths.get(row['id'].split(':',1)[-1])
        if e is not None:
            spans[row['id']] = (positions[e], ends[e])
    return ranges,spans


def matching_sequences(blocks, starts, target):
    """Allow only exact prefix restoration or whole-heading token spacing."""
    result = []
    for start in starts:
        first = normalized(blocks[start]['text'])
        if tokens(first)==tokens(target):
            result.append([start]); continue
        if not target.startswith(first):
            continue
        current = first; used = [start]
        for i in range(start+1, min(start+16,len(blocks))):
            b = blocks[i]
            if b['kind'] not in {'text','heading'}:
                break
            tail = normalized(b['text'])
            if not tail:
                continue
            options = {normalized(current+tail), normalized(current+' '+tail)}
            options = {v for v in options if target.startswith(v)}
            if len(options)!=1:
                break
            current = options.pop(); used.append(i)
            if current==target:
                result.append(used); break
    return result


def propose(document, native, ranges, spans):
    blocks = document['blocks']; sources = {r['id']:r for r in document.get('source_containers',[])}
    starts = defaultdict(list)
    for i,b in enumerate(blocks):
        if b['kind'] in {'text','heading'} and number(b['text']):
            starts[number(b['text'])].append(i)
    eligible = [r for r in sources.values() if r['id'] in spans and not r.get('table_id')
                and not r.get('excluded_navigation') and not r.get('internal_link_only')
                and (r.get('role') in {'heading','styled_heading_candidate'}
                     or (r.get('referenced_anchor') and len(r['text'])<=200
                         and (number(r['text']) or PART.match(normalized(r['text'])))))]
    mapped = {}
    for i,b in enumerate(blocks):
        sid = b.get('source_container_id'); row = sources.get(sid)
        if (row and sid in spans and b.get('source_location_status')=='unique_complete_container'
                and not row.get('table_id') and row.get('role')!='table'
                and not row.get('excluded_navigation') and not row.get('internal_link_only')
                and normalized(row['text'])==normalized(b['text'])):
            mapped[i] = spans[sid]
    proposals = []; findings = []
    for key,section in native.get('sections',{}).items():
        item = section['fields'].get('item'); bounds = ranges.get(key)
        if item is None or bounds is None:
            continue
        within = sorted((r for r in eligible if bounds[0]<=spans[r['id']][0] and spans[r['id']][1]<bounds[1]
                         and number(r['text'])), key=lambda r:spans[r['id']])
        if not within or number(within[0]['text'])!=str(item).replace('.','').casefold():
            findings.append(dict(section=key,kind='first_original_item_disagrees_or_missing')); continue
        headings = [r for r in within if number(r['text'])==number(within[0]['text'])]
        if len(headings)!=1:
            findings.append(dict(section=key,kind='repeated_original_item_container')); continue
        row = headings[0]; target = normalized(row['text']); span = spans[row['id']]
        sequences = matching_sequences(blocks, starts[number(target)], target)
        proved = []
        for indices in sequences:
            # Existing exact target is sufficient; otherwise require complete
            # source locations on both sides to constrain the parser occurrence.
            exact = len(indices)==1 and blocks[indices[0]].get('source_container_id')==row['id'] and mapped.get(indices[0])==span
            left = next((j for j in range(indices[0]-1,-1,-1) if j in mapped),None)
            right = next((j for j in range(indices[-1]+1,len(blocks)) if j in mapped),None)
            bracket = left is not None and right is not None and mapped[left][1]<span[0]<=span[1]<mapped[right][0]
            if exact or bracket:
                # A conflicting body location must not be replaced by matching
                # words. Only navigation/table-cell selections can be corrected.
                conflict = any(blocks[i].get('source_container_id') not in {None,row['id']}
                    and not (sources.get(blocks[i]['source_container_id'],{}).get('table_id')
                             or sources.get(blocks[i]['source_container_id'],{}).get('internal_link_only')
                             or sources.get(blocks[i]['source_container_id'],{}).get('excluded_navigation')) for i in indices)
                if not conflict:
                    proved.append(dict(section=key,blocks=indices,source_id=row['id'],title=target,
                                       bounds=list(bounds),bracket_blocks=[left,right],basis='original_item_container_and_toc_scope'))
        if len(proved)!=1:
            findings.append(dict(section=key,kind='parser_sequence_not_uniquely_located',matches=len(proved))); continue
        proof = proved[0]
        prior_parts = [(spans[r['id']][0],PART.match(normalized(r['text'])),r['id']) for r in eligible
                       if spans[r['id']][1]<span[0] and PART.match(normalized(r['text']))]
        proof['part'] = max(prior_parts,key=lambda x:x[0])[1][1].upper() if prior_parts else None
        proof['part_source_id'] = max(prior_parts,key=lambda x:x[0])[2] if prior_parts else None
        proposals.append(proof)
    owners = defaultdict(set)
    section_owners = defaultdict(set)
    for p in proposals:
        section_owners[p['source_id']].add(p['section'])
        for i in p['blocks']:
            owners[i].add(p['source_id'])
    retained=[]
    for p in proposals:
        if len(section_owners[p['source_id']])>1:
            findings.append(dict(section=p['section'],kind='same_heading_multiple_section_identities'))
        elif any(len(owners[i])>1 for i in p['blocks']):
            findings.append(dict(section=p['section'],kind='overlapping_heading_proofs'))
        else:retained.append(p)
    return retained,findings


def repair(previous, capture):
    native = capture['native']; d = deepcopy(previous)
    if capture['source_sha256']!=d['source_sha256']:
        raise ValueError('heading_source_identity_mismatch')
    ranges,spans = geometry(native,d.get('source_containers',[]))
    proposals,findings = propose(d,native,ranges,spans)
    groups = defaultdict(list)
    for key,bounds in ranges.items():
        groups[bounds].append(key)
    d['shared_native_range_groups'] = [dict(original_range=list(k),sections=sorted(v),
        status='shared_range_requires_reference_review',canonical_section=None) for k,v in groups.items() if len(v)>1]
    d['source_heading_findings'] = findings
    sources = {r['id']:r for r in d.get('source_containers',[])}
    tree = d['chapter_tree']; by_id = {n['id']:n for n in tree}; blocks = d['blocks']; repairs = []
    section_units = {}; fragment_nodes = {}
    for p in proposals:
        sid = p['source_id']; indices = p['blocks']; start = indices[0]
        # Unchanged, already-consumed complete headings need no mutation.
        existing = [n for n in tree if n['block'] in indices and not n.get('embedded_in_table')
                    and not n['id'].startswith(('native-part:','source-part:'))]
        native_node = by_id.get('native-section:'+p['section'])
        node = native_node or next((n for n in existing if n.get('navigation_status')!='compatibility_only'),None)
        if (len(indices)==1 and blocks[start]['kind']=='heading' and blocks[start].get('source_container_id')==sid
                and node and normalized(node['title'])==p['title']
                and node.get('navigation_status')!='compatibility_only'):
            continue
        uid = 'source-heading:'+sha256(sid.encode()).hexdigest()[:24]
        if node is None:
            node = dict(id=uid,block=start,title=p['title'],level=None,parent_id=None)
            tree.append(node);by_id[node['id']]=node
        parent = by_id.get('native-part:'+p['part']) if p['part'] else None
        part_blocks = [i for i,b in enumerate(blocks) if b.get('source_container_id')==p['part_source_id']
                       and p['part_source_id'] and b.get('source_location_status')=='unique_complete_container']
        if parent is None and p['part'] and len(part_blocks)==1:
            parent = dict(id='source-part:'+p['part_source_id'],block=part_blocks[0],title=sources[p['part_source_id']]['text'],level=1,
                          parent_id=None,source_container_id=p['part_source_id'],basis='original_part_heading')
            if parent['id'] not in by_id:
                tree.append(parent);by_id[parent['id']]=parent
            else:parent=by_id[parent['id']]
        node.update(block=start,title=p['title'],parent_id=parent['id'] if parent else None,
                    level=2 if parent else 1 if not native['sections'][p['section']]['fields'].get('part') else None,
                    source_container_id=sid,basis=p['basis'],source_heading_unit_id=uid,
                    navigation_status='source_heading_candidate',chapter_binding_status='source_evidenced_heading_unit')
        node['previous_title_binding']=deepcopy(node.get('title_binding'))
        node['title_binding']=dict(status='source_heading_unit',source_id=sid,blocks=indices)
        for other in existing:
            if other['id']!=node['id'] and not other['id'].startswith(('native-part:','source-part:')):
                other.update(navigation_status='compatibility_only',structural_role='heading_unit_fragment')
                fragment_nodes[other['id']]=node['id']
        before = []
        for i in indices:
            b = blocks[i]
            before.append(dict(block=i,kind=b['kind'],source_id=b.get('source_container_id'),source_status=b.get('source_location_status')))
            b['source_heading_unit_id']=uid;b['structural_only']=True
            b['structural_role']='complete_heading' if len(indices)==1 else 'heading_fragment'
            b['candidate_role']='retained_structure'
            if len(indices)==1 and normalized(b['text'])==normalized(sources[sid]['text']):
                b.update(source_container_id=sid,source_location_status='unique_complete_container')
            else:
                b.update(source_container_id=None,source_location_status='verified_heading_unit_component')
            if i==start:b['kind']='heading'
        p.update(id=uid,chapter_id=node['id'],previous_blocks=before,physical_blocks_preserved=True)
        repairs.append(p);section_units[p['section']]=node['id']
    # Original complete-container scopes drive body assignment. Shared ranges
    # remain explicit alternatives; they never silently become one owner.
    membership = {}
    for sid,(left,right) in spans.items():
        keys = [k for k,(a,z) in ranges.items() if a<=left and right<z]
        if len(keys)==1 and keys[0] in section_units:membership[sid]=section_units[keys[0]]
    scope = {i:membership[b['source_container_id']] for i,b in enumerate(blocks)
             if b.get('source_container_id') in membership and b.get('source_location_status')=='unique_complete_container'
             and b.get('effective_scope',{}).get('kind')!='source_signature_scope'}
    for p in repairs:
        for i in p['blocks']:scope[i]=p['chapter_id']
    roots = set(section_units.values())
    section_for_root={root:key for key,root in section_units.items()}
    heading_blocks={i for p in repairs for i in p['blocks']}
    deferrals=[]
    for i,root in list(scope.items()):
        if i in heading_blocks:continue
        b=blocks[i];key=section_for_root[root]
        native_candidates=b.get('native_section_binding',{}).get('candidates',[])
        # An EOF-based TOC extent is not evidence to swallow a later signature,
        # attachment or another known section. Keep both claims for review.
        conflicts=[c for c in native_candidates if c!=key]
        unlocated=[cid for cid in b.get('chapter_ids',[]) if cid in by_id
                   and cid not in roots and cid not in fragment_nodes
                   and not cid.startswith(('native-part:','source-part:','native-section:'))
                   and by_id[cid]['block']>=by_id[root]['block']
                   and scope.get(by_id[cid]['block'])!=root]
        if conflicts or unlocated:
            deferrals.append(dict(block=i,candidate_chapter=root,
                                  conflicting_native_sections=conflicts,unlocated_prior_headings=unlocated,
                                  status='retain_prior_scope_pending_boundary_proof'))
            del scope[i]
    d['source_heading_scope_deferrals']=deferrals
    for n in tree:
        root = scope.get(n['block'])
        if root and n['id'] not in roots and n['id'] not in fragment_nodes and not n['id'].startswith(('native-part:','source-part:','native-section:')):
            parent = by_id.get(n.get('parent_id'))
            if not parent or scope.get(parent['block'])!=root or parent['id']==n['id']:
                n['parent_id']=root
    def ancestors(cid):
        result=[];seen=set()
        while cid:
            if cid in seen:raise ValueError('heading_unit_cycle')
            seen.add(cid);result.append(cid);cid=by_id[cid].get('parent_id')
        return list(reversed(result))
    for i,b in enumerate(blocks):
        if i not in scope:continue
        old=list(b.get('chapter_ids',[]));root=scope[i]
        leaves=[by_id[c] for c in old if c in by_id and c not in fragment_nodes and c not in roots
                and scope.get(by_id[c]['block'])==root and by_id[c]['block']<=i
                and not c.startswith(('native-part:','source-part:'))]
        leaf=max(leaves,key=lambda n:n['block'])['id'] if leaves else root
        b['prior_chapter_ids_before_heading_units']=old;b['chapter_ids']=ancestors(leaf)
        b['chapter_blocks']=[by_id[c]['block'] for c in b['chapter_ids']]
    d['source_heading_units']=repairs
    from native_document_adaptation import finish
    return finish(d)
