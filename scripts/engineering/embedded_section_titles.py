"""Bind SEC titles inside mixed layout tables without suppressing their bodies.

Only the first nonempty physical row, full bold text, exact native cell matches,
unique section membership and an original DOM locator together establish proof.
No issuer names, preferred section labels or financial inference are used.
"""
from copy import deepcopy
from hashlib import sha256
import re

from lxml import html
from source_structure_contract import normalized, _all_bold

ITEM = re.compile(r'^item\s*(\d+(?:\.\d+)?[a-z]?)\s*[.:]?$', re.I)


def proposals(document, raw):
    if sha256(raw).hexdigest() != document['source_sha256']:
        raise ValueError('original_digest_changed')
    try:
        raw.decode('utf-8-sig')
        dom = html.fromstring(raw, parser=html.HTMLParser(encoding='utf-8'))
    except UnicodeDecodeError:
        dom = html.fromstring(raw)
    tree = dom.getroottree()
    paths = {tree.getpath(e): e for e in dom.iter()}
    sources = {s['id']: s for s in document.get('source_containers', [])}
    result = []; findings = []
    for chapter in document['chapter_tree']:
        if chapter.get('title_binding', {}).get('status') not in {'heading_not_bound', 'ambiguous_heading'}:
            continue
        key = chapter.get('native_section_key')
        expected = str(chapter.get('native_section', {}).get('item') or '').replace('.', '').casefold()
        candidates = []
        for i, block in enumerate(document['blocks']):
            if block['kind'] != 'table' or block.get('native_section_binding', {}).get('candidates') != [key]:
                continue
            sid = block.get('source_container_id'); source = sources.get(sid, {})
            if block.get('source_location_status') != 'unique_complete_container' or not sid:
                continue
            if source.get('excluded_navigation') or source.get('internal_link_only'):
                continue
            table = paths.get(sid.split(':', 1)[-1])
            if table is None or table.tag != 'table' or table.xpath('.//table'):
                continue
            rows = table.xpath('./tr | ./thead/tr | ./tbody/tr | ./tfoot/tr')
            first = next(((j, r) for j, r in enumerate(rows) if normalized(''.join(r.itertext()))), None)
            if first is None:
                continue
            j, row = first; cells = row.xpath('./td | ./th')
            visible = [(k, normalized(''.join(c.itertext()))) for k, c in enumerate(cells)
                       if normalized(''.join(c.itertext()))]
            # Item and label must occupy separate cells; prose citations and
            # compact tables of contents are not sufficient title evidence.
            if len(visible) != 2:
                continue
            match = ITEM.fullmatch(visible[0][1])
            if not match or match[1].replace('.', '').casefold() != expected:
                continue
            if not expected or not all(_all_bold(cells[k]) for k, _ in visible):
                continue
            if row.xpath('.//a[starts-with(@href,"#")]') or any(c.get('rowspan', '1') != '1' for c in cells):
                continue
            label = visible[1][1]
            if len(label) > 240 or not re.search(r'[A-Za-z]', label) or ITEM.match(label):
                continue
            parsed_rows = block.get('headers', []) + block.get('rows', []) + block.get('footer', [])
            matches = [k for k, r in enumerate(parsed_rows)
                       if [normalized(c['text']) for c in r] == [normalized(''.join(c.itertext())) for c in cells]]
            if len(matches) != 1:
                continue
            candidates.append(dict(chapter_id=chapter['id'], section=key, block=i,
                title=' '.join(text for _, text in visible), source_container_id=sid,
                original_row_xpath=tree.getpath(row), parsed_row=matches[0],
                cell_indices=[k for k, _ in visible], source_sha256=document['source_sha256'],
                basis='original_bold_first_row_exact_cells_unique_native_section'))
        if len(candidates) == 1:
            result.append(candidates[0])
        findings.append(dict(chapter_id=chapter['id'], candidates=len(candidates),
                             status='proved' if len(candidates)==1 else 'ambiguous' if candidates else 'not_proved'))
    # A physical title must not be assigned to multiple chapter identities.
    counts = {}
    for p in result:
        loc=(p['block'],p['parsed_row']); counts[loc]=counts.get(loc,0)+1
    return [p for p in result if counts[p['block'],p['parsed_row']]==1], findings


def repair(document, raw):
    proved, findings = proposals(document, raw)
    if not proved:
        return document, [], findings
    updated = deepcopy(document)
    chapters = {c['id']: c for c in updated['chapter_tree']}
    for proof in proved:
        node = chapters[proof['chapter_id']]
        node['prior_embedded_title_binding'] = dict(title=node['title'], block=node['block'],
                                                   title_binding=node.get('title_binding'))
        node.update(title=proof['title'], title_binding=dict(status='bound_embedded_heading', **proof))
        # Do not move the section anchor or alter any block's ownership. The
        # embedded title has its own row locator; the native range is unchanged.
        for outline in updated['outline']:
            if outline['block']==node['block'] and outline['title']==node['prior_embedded_title_binding']['title']:
                outline['title']=proof['title']
        updated['blocks'][proof['block']].setdefault('embedded_section_titles', []).append(proof)
    updated.setdefault('embedded_section_title_repairs', []).extend(proved)
    return updated, proved, findings


def verify(document, raw):
    """Rebuild every proof from original bytes, never trust saved status alone."""
    proofs = document.get('embedded_section_title_repairs', [])
    if not proofs:
        return
    prior = deepcopy(document)
    nodes = {n['id']: n for n in prior['chapter_tree']}
    for p in proofs:
        node = nodes[p['chapter_id']]
        if node.get('title') != p['title'] or node.get('title_binding') != dict(status='bound_embedded_heading', **p):
            raise ValueError('embedded_heading_not_consumed')
        if p not in prior['blocks'][p['block']].get('embedded_section_titles', []):
            raise ValueError('embedded_heading_block_reference_missing')
        node.update(node['prior_embedded_title_binding'])
    rebuilt, _ = proposals(prior, raw)
    if rebuilt != proofs:
        raise ValueError('embedded_title_proof_not_reproducible')
