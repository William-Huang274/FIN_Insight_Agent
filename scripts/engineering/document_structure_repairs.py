"""Source-evidenced repairs over frozen documents, without parser/model calls."""
from copy import deepcopy
import re

from native_document_adaptation import finish
from source_structure_contract import normalized


def repair_markdown_html(previous):
    """Parse embedded HTML locally; keep source lines and raw blocks unchanged."""
    from lxml import html, etree
    d = deepcopy(previous); repairs = []
    for i,b in enumerate(d['blocks']):
        if b.get('candidate_role') != 'html_structure_pending':continue
        raw = b.get('raw_text',b['text'])
        try:
            root = html.fragment_fromstring(raw,create_parent='fin-fragment',parser=html.HTMLParser(no_network=True))
            tree = root.getroottree(); nodes=[]; headings=[]; tables=[]; images=[];stack=[]
            for e in root.iter():
                if not isinstance(e.tag,str):continue
                path=tree.getpath(e)
                nodes.append(dict(path=path,parent_path=tree.getpath(e.getparent()) if e.getparent() is not None else None,
                                  tag=e.tag,attributes=dict(e.attrib),text=e.text,tail=e.tail))
                if re.fullmatch(r'h[1-6]',e.tag) and not e.xpath('ancestor::table|ancestor::nav|ancestor::script'):
                    level=int(e.tag[1]);
                    while stack and stack[-1]['level']>=level:stack.pop()
                    row=dict(path=path,title=normalized(''.join(e.itertext())),level=level,parent_path=stack[-1]['path'] if stack else None)
                    headings.append(row);stack.append(row)
                if e.tag=='table':
                    rows=[]
                    for tr in e.xpath('.//tr'):
                        if next(iter(tr.iterancestors('table')),None) is not e:continue
                        rows.append([dict(text=''.join(c.itertext()),tag=c.tag,rowspan=c.get('rowspan','1'),colspan=c.get('colspan','1'),path=tree.getpath(c)) for c in tr if c.tag in {'td','th'}])
                    tables.append(dict(path=path,rows=rows,nested_table=bool(e.xpath('.//table')),role='physical_table_candidate',financial_semantics_inferred=False))
                if e.tag=='img':images.append(dict(path=path,src=e.get('src'),alt=e.get('alt'),role='image_purpose_unreviewed'))
            b['embedded_html_structure']=dict(nodes=nodes,headings=headings,tables=tables,images=images,
                source_lines=b['source_lines'],coordinate_namespace='html_fragment_within_markdown_source_lines',
                normalized_html=etree.tostring(root,encoding='unicode'),source_raw_preserved=True,
                quality_status='native_fragment_structure_requires_original_review')
            b['candidate_role']='html_structure_candidate'
            repairs.append(dict(block=i,headings=len(headings),tables=len(tables),images=len(images)))
        except (etree.ParserError,ValueError) as exc:
            b['embedded_html_failure']=dict(error=type(exc).__name__,detail=str(exc))
    d['embedded_html_repairs']=repairs
    return d


def attestation(text):
    text = normalized(text)
    return bool(re.match(r'^Pursuant to the requirements of\b', text, re.I)
                and re.search(r'\bSecurities Exchange Act of 1934\b', text, re.I)
                and re.search(r'\bregistrants?\b', text, re.I)
                and re.search(r'\bcaused this report to be signed\b', text, re.I)
                and re.search(r'\bduly authorized\b', text, re.I))


def repair_sec_signatures(previous):
    """A source heading plus adjacent attestation establishes a local boundary.

    Does not mutate native capture membership or claim the rest of the document
    has been source-reviewed. Stops at the next non-date heading/formal section.
    """
    d = deepcopy(previous)
    blocks = d['blocks']; sources = {r['id']: r for r in d.get('source_containers', [])}
    changes = []
    def proved(b):
        r = sources.get(b.get('source_container_id'))
        return r if (r and b.get('source_location_status') == 'unique_complete_container'
                     and not r.get('table_id') and not r.get('excluded_navigation')
                     and not r.get('internal_link_only') and normalized(b['text']) == normalized(r['text'])) else None
    for i, b in enumerate(blocks):
        if b['kind'] != 'heading' or not re.fullmatch(r'SIGNATURES?', normalized(b['text']), re.I) or not proved(b):
            continue
        following = next((j for j in range(i+1,len(blocks)) if normalized(blocks[j]['text'])), None)
        if following is None or not proved(blocks[following]) or not attestation(blocks[following]['text']):
            continue
        candidates = [n for n in d['chapter_tree'] if n['block'] == i and not n.get('embedded_in_table')]
        if len(candidates) != 1: continue
        node = candidates[0]
        end = next((j for j in range(following+1,len(blocks))
                    if blocks[j]['kind']=='heading' and not re.match(r'^Date\s*:', normalized(blocks[j]['text']),re.I)),len(blocks))
        if node.get('parent_id') is None and node.get('basis')=='source_signature_and_adjacent_attestation':
            continue
        changes.append(dict(kind='source_signature_scope',start_block=i,end_block_exclusive=end,
                            heading_source_id=b['source_container_id'],attestation_source_id=blocks[following]['source_container_id'],
                            previous_parent_id=node.get('parent_id'),chapter_id=node['id']))
        node.update(parent_id=None, level=1, basis='source_signature_and_adjacent_attestation',
                    navigation_status='source_boundary_candidate',chapter_binding_status='source_evidenced_local_scope')
        by_id = {n['id']:n for n in d['chapter_tree']}
        # Local descendants are reattached; unrelated later sections are untouched.
        for child in d['chapter_tree']:
            if not (i < child['block'] < end):continue
            parent = by_id.get(child.get('parent_id'))
            if parent is None or not (i <= parent['block'] < child['block']):
                child['parent_id'] = node['id']; parent = node
            if child.get('level') is not None and parent.get('level') is not None:
                child['level'] = parent['level']+1
        for j in range(i,end):
            old = list(blocks[j].get('chapter_ids',[]))
            ids = [node['id']] + [cid for cid in old if cid != node['id'] and cid in by_id and i < by_id[cid]['block'] <= j and by_id[cid]['block'] < end]
            blocks[j]['prior_to_scope_repair_chapter_ids'] = old
            blocks[j]['chapter_ids'] = ids
            blocks[j]['chapter_blocks'] = [by_id[cid]['block'] for cid in ids]
            blocks[j]['effective_scope'] = dict(kind='source_signature_scope',chapter_id=node['id'],
                                               basis='complete_heading_and_adjacent_original_attestation')
    d['source_scope_repairs'] = changes
    if changes:finish(d)
    return d
