"""Original Item titles are authoritative display text, native keys stay stable.

Some native 8-K section fields reduce 5.02 to 5. An original TOC target and
adjacent section body can prove the complete title without migrating that key.
Table title evidence covers one exact row, never the rest of a mixed table.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import re

from source_heading_units import tokens
from source_section_title_links import original_geometry
from source_structure_contract import normalized, _all_bold


ITEM = re.compile(r'^item\s*(\d+(?:\.\d+)?[a-z]?)(?=[\s.:;\[(—–-]|$)', re.I)


def item_identity(text):
    match = ITEM.match(normalized(text))
    return match[1].replace('.', '').casefold() if match else None


def proposals(document, raw):
    if sha256(raw).hexdigest() != document['source_sha256']:
        raise ValueError('original_item_source_changed')
    tree, paths, spans, body, anchors, links = original_geometry(raw)
    sources = {s['id']: s for s in document.get('source_containers', [])}
    blocks = document['blocks']
    empty_targets = [(key, values[0]) for key, values in anchors.items()
                     if len(values) == 1 and not normalized(body[spans[values[0]][0]:spans[values[0]][1]])]
    navigation = []
    for source in sources.values():
        if not source.get('internal_link_only') or source.get('table_id'):
            continue
        element = paths.get(source['id'].split(':', 1)[-1])
        if element is None or normalized(''.join(element.itertext())) != source.get('text'):
            continue
        refs = element.xpath('.//a[starts-with(@href,"#")]')
        if refs and all(len(anchors[a.get('href')[1:]]) == 1 for a in refs):
            navigation.append((source['id'], *spans[element]))

    def navigation_gap(start, end):
        if not normalized(body[start:end]):
            return []
        covered = [(sid, lo, hi) for sid, lo, hi in navigation if start <= lo < hi <= end]
        cursor = start
        for sid, lo, hi in sorted(covered, key=lambda value: value[1:]):
            if lo > cursor and normalized(body[cursor:lo]):
                return None
            cursor = max(cursor, hi)
        if normalized(body[cursor:end]):
            return None
        return [sid for sid, _, _ in covered] if covered else None

    def toc_targets(element, title):
        result = []
        candidates = [element, *element.iterancestors(), *element.iterdescendants()]
        for candidate in candidates:
            if candidate not in spans:
                continue
            if spans[candidate][0] <= spans[element][0]:
                prefix = body[spans[candidate][0]:spans[element][0]]
            else:
                prefix = body[spans[element][0]:spans[candidate][0]]
            if normalized(prefix):
                continue
            for anchor in sorted(set(filter(None, (candidate.get('id'), candidate.get('name'))))):
                if len(anchors[anchor]) != 1:
                    continue
                for label in sorted(set(links.get(anchor, []))):
                    if tokens(label.casefold()) == tokens(title.casefold()):
                        result.append(dict(anchor=anchor, label=label))
        # SEC exporters also emit an empty sibling anchor directly before a
        # heading. Accept only the exact TOC label and an empty original gap.
        for anchor, candidate in empty_targets:
            if spans[candidate][1] > spans[element][0]:
                continue
            gap = navigation_gap(spans[candidate][1], spans[element][0])
            if gap is None:
                continue
            for label in sorted(set(links.get(anchor, []))):
                if tokens(label.casefold()) == tokens(title.casefold()):
                    result.append(dict(anchor=anchor, label=label, navigation_gap_source_ids=gap))
        return sorted(result, key=lambda value: (value['anchor'], value['label']))

    def locations(index):
        block = blocks[index]
        ids = ([block['source_container_id']] if block.get('source_container_id')
               else block.get('source_container_candidates', []))
        result = []
        for sid in ids:
            source = sources.get(sid, {})
            element = paths.get(sid.split(':', 1)[-1])
            if (element is None or source.get('excluded_navigation') or source.get('internal_link_only')
                or element.xpath('ancestor-or-self::nav|ancestor-or-self::script')):
                continue
            result.append((sid, element))
        return result

    findings = []; proposed = []
    for node in document.get('chapter_tree', []):
        if node.get('title_binding', {}).get('status') not in {'heading_not_bound', 'ambiguous_heading'}:
            continue
        native_number = str(node.get('native_section', {}).get('item') or '').replace('.', '').casefold()
        if not native_number:
            continue
        key = node.get('native_section_key')
        members = [i for i, b in enumerate(blocks)
                   if b.get('native_section_binding', {}).get('candidates') == [key]
                   and normalized(b.get('text', ''))]
        if not members:
            continue
        first = members[0]
        previous = next((j for j in range(first - 1, -1, -1) if normalized(blocks[j]['text'])), None)
        matches = []
        for index in [first] + ([previous] if previous is not None else []):
            block = blocks[index]
            for sid, element in locations(index):
                cell_evidence = None
                if block['kind'] == 'table':
                    if element.tag != 'table' or element.xpath('.//table'):
                        continue
                    rows = element.xpath('./tr|./thead/tr|./tbody/tr|./tfoot/tr')
                    row = next((r for r in rows if normalized(''.join(r.itertext()))), None)
                    if row is None:
                        continue
                    if row.xpath('.//a[starts-with(@href,"#")]'):
                        continue
                    cells = row.xpath('./td|./th')
                    texts = [normalized(''.join(c.itertext())) for c in cells]
                    visible = [j for j, text in enumerate(texts) if text]
                    parsed = block.get('headers', []) + block.get('rows', []) + block.get('footer', [])
                    same = [j for j, r in enumerate(parsed)
                            if [tokens(c['text']) for c in r] == [tokens(t) for t in texts]]
                    if len(same) != 1 or not visible:
                        continue
                    title = ' '.join(texts[j] for j in visible)
                    styled = all(_all_bold(cells[j]) for j in visible)
                    title_element = row
                    cell_evidence = dict(original_row_xpath=tree.getpath(row), parsed_row=same[0],
                                         cell_indices=visible, table_block=index)
                else:
                    if source := sources.get(sid):
                        if source.get('table_id'):
                            continue
                    if tokens(''.join(element.itertext())) != tokens(block['text']):
                        continue
                    title = normalized(block['text'])
                    styled = element.tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'} or _all_bold(element)
                    title_element = element
                actual = item_identity(title)
                if not actual or len(title) > 1000:
                    continue
                toc = toc_targets(title_element, title)
                if not styled and not toc:
                    continue
                if actual != native_number and not toc:
                    continue
                # The original heading must be the first member or immediately
                # precede its complete source container, with no visible gap.
                if index != first:
                    adjacent = [(bs, be) for bs, be in locations(first)
                                if spans[element][1] <= spans[be][0]
                                and not normalized(body[spans[element][1]:spans[be][0]])
                                and tokens(''.join(be.itertext())) == tokens(blocks[first]['text'])]
                    if len(adjacent) != 1:
                        continue
                matches.append(dict(chapter_id=node['id'], section=key, block=index,
                    source_container_id=sid, title=title, original_item=actual,
                    native_item=native_number, native_identity_preserved=True,
                    original_toc=toc[0] if toc else None, first_native_block=first,
                    original_span=spans[title_element], original_span_namespace='original_dom_itertext_character_offsets', table_row=cell_evidence,
                    basis='original_item_title_at_unique_native_start',
                    native_item_disagrees=actual != native_number))
        unique = {repr((p['block'], p['source_container_id'], p['title'])): p for p in matches}
        findings.append(dict(chapter_id=node['id'], candidates=len(unique),
                             status='proved' if len(unique) == 1 else 'ambiguous' if unique else 'not_proved'))
        if len(unique) == 1:
            proposed.extend(unique.values())
    owners = defaultdict(set)
    for proof in proposed:
        owners[proof['source_container_id'], repr(proof['table_row'])].add(proof['chapter_id'])
    return [p for p in proposed if len(owners[p['source_container_id'], repr(p['table_row'])]) == 1], findings


def repair(document, raw):
    proofs, findings = proposals(document, raw)
    if not proofs:
        return document, [], findings
    updated = deepcopy(document); nodes = {n['id']: n for n in updated['chapter_tree']}
    for proof in proofs:
        node = nodes[proof['chapter_id']]
        node['prior_original_item_title'] = dict(title=node['title'], title_binding=node['title_binding'])
        old_title = node['title']
        node.update(title=proof['title'], title_binding=dict(status='bound_original_item_title', **proof))
        for outline in updated['outline']:
            if outline['block'] == node['block'] and outline['title'] == old_title:
                outline['title'] = proof['title']
    updated.setdefault('source_item_title_repairs', []).extend(proofs)
    return updated, proofs, findings


def verify(document, raw):
    proofs = document.get('source_item_title_repairs', [])
    if not proofs:
        return
    previous = deepcopy(document); nodes = {n['id']: n for n in previous['chapter_tree']}
    for proof in proofs:
        node = nodes[proof['chapter_id']]
        if node['title_binding'] != dict(status='bound_original_item_title', **proof) or node['title'] != proof['title']:
            raise ValueError('original_item_title_not_consumed')
        node.update(node['prior_original_item_title'])
    if proposals(previous, raw)[0] != proofs:
        raise ValueError('original_item_title_not_reproducible')
