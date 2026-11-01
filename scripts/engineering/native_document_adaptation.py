"""Consume frozen native structures; never invoke a parser or a provider.

SEC preserves repaired FIN text/positions and binds native section membership.
Markdown consumes native tokens, keeping a complete source-line partition.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from native_document_capture import read_capture, validate_capture
from source_structure_contract import reconcile_chapters, normalized
from retrieval.narrative_chunks import sentence_groups


def finish(document):
    chunks = []
    for i, block in enumerate(document['blocks']):
        if block['kind'] == 'heading':
            continue
        common = dict(block=i, heading_path=block.get('chapter_blocks', []),
                      chapter_ids=block.get('chapter_ids', []),
                      source_container_id=block.get('source_container_id'))
        if block['kind'] == 'table':
            chunks.append(dict(common, kind='table', representation='native_table_not_numeric_SQL_replacement'))
        else:
            for start, end, _ in sentence_groups(block['text']):
                chunks.append(dict(common, kind='prose', start=start, end=end))
    document['pre_chunks'] = chunks
    visible = [n for n in document['chapter_tree'] if n.get('navigation_status') != 'compatibility_only']
    document['outline'] = [dict(block=n['block'], title=n['title'], level=n['level'],
                               parent_block=None, basis=n['basis']) for n in visible]
    by_id = {n['id']: n for n in document['chapter_tree']}
    for row, node in zip(document['outline'], visible):
        parent = by_id.get(node.get('parent_id'))
        cursor = parent; hidden_ancestors = 0
        while cursor:
            hidden_ancestors += cursor.get('navigation_status') == 'compatibility_only'
            cursor = by_id.get(cursor.get('parent_id'))
        while parent and parent.get('navigation_status') == 'compatibility_only':
            parent = by_id.get(parent.get('parent_id'))
        row['parent_block'] = parent['block'] if parent else None
        if row['level'] is not None:
            row['level'] = max(1, row['level'] - hidden_ancestors)
    document['native_adaptation_version'] = 'native_structure_v2'
    document['quality_status'] = 'requires_original_based_quality_review'
    from validate_source_structure_audit import validate
    errors = validate(document)
    if errors:
        raise ValueError(f'native_projection_invalid:{errors}')
    return document


def markdown_document(capture):
    native = capture['native']; tokens = native['tokens']
    lines = native['source_text'].splitlines(keepends=True)
    blocks = []; cursor = 0; i = 0
    def append(start, end, role, token_indices, **extra):
        blocks.append(dict(kind='text', text=''.join(lines[start:end]),
                           source_lines=[start, end], native_token_indices=token_indices,
                           native_role=role, **extra))
    while i < len(tokens):
        token = tokens[i]
        if token['level'] != 0 or token.get('map') is None:
            i += 1; continue
        start, end = token['map']; stop = i + 1
        if token['nesting'] == 1:
            depth = 1
            while stop < len(tokens) and depth:
                depth += tokens[stop]['nesting']; stop += 1
            if depth:
                raise ValueError('unclosed_native_markdown_token')
        if start < cursor:
            raise ValueError('overlapping_native_markdown_ranges')
        if start > cursor:
            append(cursor, start, 'unclaimed_source', [], structural_only=not ''.join(lines[cursor:start]).strip())
        group = tokens[i:stop]
        append(start, end, token['type'], list(range(i, stop)))
        block = blocks[-1]
        if token['type'] == 'heading_open':
            block.update(kind='heading', level=int(token['tag'][1:]),
                         heading_basis='native_markdown_heading_token',
                         raw_text=block['text'], text=next(t['content'] for t in group if t['type'] == 'inline'))
        elif token['type'] == 'table_open':
            rows = []; row = None; header = False
            for t in group:
                if t['type'] == 'thead_open': header = True
                elif t['type'] == 'thead_close': header = False
                elif t['type'] == 'tr_open': row = []; rows.append((header, row))
                elif t['type'] == 'inline' and row is not None:
                    row.append(dict(text=t['content'], is_header=header, rowspan=1, colspan=1))
            block.update(kind='table', headers=[r for h, r in rows if h],
                         rows=[r for h, r in rows if not h], footer=[],
                         raw_text=block['text'], structure_gap='native_table_display_grammar_requires_source_cell_audit')
        elif token['type'] == 'front_matter':
            block['structural_only'] = True
        elif token['type'] in {'fence', 'code_block'}:
            block['candidate_role'] = 'code_candidate'
        elif token['type'] == 'html_block':
            block['candidate_role'] = 'html_structure_pending'
        cursor = end; i = stop
    if cursor < len(lines):
        append(cursor, len(lines), 'unclaimed_source', [], structural_only=not ''.join(lines[cursor:]).strip())
    # Prove lossless source retention including separators and front matter.
    if ''.join(b.get('raw_text', b['text']) for b in blocks) != native['source_text']:
        raise ValueError('markdown_source_not_conserved')
    tree = reconcile_chapters(blocks)
    return finish(dict(route='markdown_native', blocks=blocks, chapter_tree=tree,
                       issues=[{'kind': 'native_table_cell_coverage_requires_review', 'block': i}
                               for i, b in enumerate(blocks) if b['kind'] == 'table'],
                       source_sha256=capture['source_sha256'], source_containers=[],
                       source_line_partition_complete=True))


def section_display_title(key, fields, indices, blocks):
    """Resolve a display label from a bound heading, never from body prose.

    The upstream title can be an internal key. Keep that key separately and
    leave a missing/ambiguous label explicit instead of inventing a heading.
    """
    item = fields.get('item')
    if item:
        pattern = re.compile(r'^item\s+(\d+(?:\.\d+)?[a-z]?)(?=[.\s:—–-]|$)', re.I)
    elif 'signature' in key.lower():
        pattern = re.compile(r'^signatures?\s*$', re.I)
    else:
        pattern = None
    candidates = []
    for i in indices:
        b = blocks[i]
        if b['kind'] != 'heading' and not b.get('structural_heading'):
            continue
        label = ' '.join(str(b.get('structural_heading') or b['text']).split())
        if not label or len(label) > 500:
            continue
        if pattern and not pattern.match(label):
            continue
        if item and pattern.match(label).group(1).replace('.', '').lower() != str(item).replace('.', '').lower():
            continue
        if not pattern and normalized(label) != normalized(str(fields.get('title', ''))):
            continue
        candidates.append((i, label))
    labels = {normalized(label) for _, label in candidates}
    if len(labels) == 1:
        i, label = candidates[0]
        return label, i, dict(status='bound_heading', block=i,
                              source_container_id=blocks[i].get('source_container_id'),
                              membership_basis=blocks[i]['native_section_binding']['basis'])
    fallback = str(fields.get('title') or '')
    if fallback == key or fallback == fields.get('name'):
        fallback = 'Item ' + str(item) if item else 'Signatures' if 'signature' in key.lower() else 'Section'
    return fallback, min(indices), dict(status='ambiguous_heading' if candidates else 'heading_not_bound',
                                        candidates=[i for i, _ in candidates])


def edgar_document(capture, previous, *, native_paths_verified=True):
    native = capture['native']; nodes = {n['ref']: n for n in native['nodes']}
    paths = {}
    def walk(ref, path=None, visiting=frozenset()):
        if ref in visiting:
            raise ValueError('native_children_cycle')
        if path is not None: paths[path] = ref
        members = {ref}
        for index, child in enumerate(nodes[ref]['fields'].get('children', [])):
            members.update(walk(child['$node'], f'{path}/{index}' if path is not None else None,
                                visiting | {ref}))
        return members
    walk(native['root']['$node'], '0')
    membership = defaultdict(set)
    for key, section in native['sections'].items():
        ref = section['fields'].get('node', {}).get('$node')
        if not ref: continue
        for member in walk(ref): membership[member].add(key)
    document = deepcopy(previous); blocks = document['blocks']; assigned = defaultdict(list)
    issues = []
    # Native TOC boundaries address the original DOM, not offsets in a flat
    # string. Only complete source containers inside unique bounds are bound.
    dom_membership = defaultdict(set)
    if native.get('toc_boundaries'):
        from lxml import html
        original = native['metadata']['fields']['original_html']
        dom = html.fromstring(original.encode('utf-8'))
        elements = list(dom.iter()); positions = {e: i for i, e in enumerate(elements)}
        ends = {}
        for e in reversed(elements):
            ends[e] = max([positions[e]] + [ends[c] for c in e])
        path_index = {dom.getroottree().getpath(e): e for e in elements}
        def endpoint(fields, paths, role):
            explicit = paths.get(role + '_element')
            if explicit:
                found = [path_index[explicit]] if explicit in path_index else []
            else:
                anchor = fields.get('anchor_id' if role == 'start' else 'end_element_id')
                if not anchor: return None if role == 'start' else len(elements)
                found = dom.xpath('//*[@id=$anchor or @name=$anchor]', anchor=anchor)
            return positions[found[0]] if len(found) == 1 else None
        source_rows = {r['id']: r for r in document.get('source_containers', [])}
        heading_tables = {}
        for block in blocks:
            sid = block.get('source_container_id')
            if (block['kind'] == 'table' and block.get('structural_heading')
                    and block.get('source_table_role') == 'section_heading_container'
                    and block.get('source_location_status') == 'unique_complete_container'
                    and sid in source_rows and sid.startswith(capture['source_sha256'] + ':')):
                element = path_index.get(sid.split(':', 1)[1])
                if element is not None and element.tag == 'table':
                    heading_tables[sid] = element
        starts = {key: endpoint(b['fields'], b['element_paths'], 'start')
                  for key, b in native['toc_boundaries'].items()}
        adjustments = []
        for key, boundary in native['toc_boundaries'].items():
            if key not in native['sections']: continue
            start = endpoint(boundary['fields'], boundary['element_paths'], 'start')
            end = endpoint(boundary['fields'], boundary['element_paths'], 'end')
            if start is None or end is None or end <= start:
                issues.append(dict(kind='native_toc_boundary_unresolved', section=key)); continue
            # A SEC heading can be a complete one-row layout table, with the
            # anchor on its first cell. Preserve that physical heading container,
            # but never lift an ordinary data table or a multi-section table.
            candidates = [(sid, element) for sid, element in heading_tables.items()
                          if positions[element] < start <= ends[element] < end
                          and not any(other != key and pos is not None
                                      and positions[element] <= pos <= ends[element]
                                      for other, pos in starts.items())]
            if len(candidates) == 1:
                sid, element = candidates[0]
                adjustments.append(dict(section=key, source_container_id=sid,
                                        native_start=start, adapted_start=positions[element],
                                        basis='verified_section_heading_table_contains_unique_anchor'))
                start = positions[element]
            for sid, row in source_rows.items():
                if not sid.startswith(capture['source_sha256'] + ':'): continue
                found = path_index.get(sid.split(':', 1)[1])
                if found is not None and start <= positions[found] and ends[found] < end:
                    dom_membership[sid].add(key)
        document['native_boundary_adjustments'] = adjustments
    for i, block in enumerate(blocks):
        ref = paths.get(block.get('native_container_id')) if native_paths_verified else None
        fields = nodes[ref]['fields'] if ref else {}
        text = nodes[ref].get('rendered_text', fields.get('content')) if ref else None
        kind = fields.get('type', {}).get('name', '').lower()
        # Preserved DOM repairs may combine fragments. Do not assume the first
        # fragment's section proves ownership of an expanded block.
        compatible = (isinstance(text, str) and normalized(text) == normalized(block['text']))
        if block['kind'] == 'table' and kind == 'table':
            compatible = False  # Bound below using each complete cell, not a path alone.
            def cells(rows):
                return [[c['fields']['content'] for c in r] for r in rows]
            native_rows = fields.get('headers', []) + [r['fields']['cells'] for r in fields.get('rows', [])] + [r['fields']['cells'] for r in fields.get('footer', [])]
            fin_rows = block.get('headers', []) + block.get('rows', []) + block.get('footer', [])
            try:
                raw_cells = cells(native_rows)
                compatible = all(isinstance(c, str) for r in raw_cells for c in r) and [[normalized(c) for c in r] for r in raw_cells] == [[normalized(c['text']) for c in r] for r in fin_rows]
            except (KeyError, TypeError):
                pass
        choices = sorted(membership.get(ref, set())) if compatible else []
        basis = 'native_node_membership'
        if not choices and block.get('source_location_status') == 'unique_complete_container':
            choices = sorted(dom_membership.get(block.get('source_container_id'), set()))
            if choices: basis = 'native_toc_boundary_complete_original_container'
        status = 'unique_native_membership' if len(choices) == 1 else 'ambiguous_native_membership' if choices else 'unresolved_native_membership' if not compatible else 'outside_native_sections'
        block['native_section_binding'] = dict(node=ref, candidates=choices, status=status, basis=basis)
        if len(choices) == 1: assigned[choices[0]].append(i)
        else: issues.append(dict(kind=status, block=i))
    old_tree = document['chapter_tree']; tree = []; section_nodes = {}; parts = {}
    if not assigned:
        document.update(native_section_coverage=dict(total_sections=len(native['sections']),
                        sections_with_bound_blocks=0, bound_blocks=0, total_blocks=len(blocks)),
                        native_section_issues=issues, native_tree_status='existing_tree_retained_no_native_scope',
                        source_sha256=capture['source_sha256'])
        return finish(document)
    old_by_id = {n['id']: n for n in old_tree}
    scope = {i: key for key, indices in assigned.items() for i in indices}
    for key, indices in sorted(assigned.items(), key=lambda item: min(item[1])):
        section = native['sections'][key]; fields = section['fields']
        title, anchor, title_binding = section_display_title(key, fields, indices, blocks)
        part = fields.get('part'); parent = None
        if part:
            parent = 'native-part:' + str(part)
            if part not in parts:
                parts[part] = dict(id=parent, block=anchor, title='Part '+str(part), level=1,
                                   parent_id=None, basis='native_section_part', source_container_id=None)
                tree.append(parts[part])
        node = dict(id='native-section:'+key, block=anchor, title=title, level=2 if part else 1,
                    parent_id=parent, basis='native_section_node_membership', source_container_id=None,
                    native_section=deepcopy(fields), native_section_key=key, title_binding=title_binding,
                    native_quality_status='upstream_hypothesis')
        tree.append(node); section_nodes[key] = node
    # Replace only proved section headings, not the first arbitrary body block.
    replacements = {}
    for old in old_tree:
        key = scope.get(old['block'])
        if key and section_nodes[key]['title_binding']['status'] == 'bound_heading' and old['block'] == section_nodes[key]['block']:
            replacements[old['id']] = section_nodes[key]['id']
            parent = old_by_id.get(old.get('parent_id'))
            part = native['sections'][key]['fields'].get('part')
            if parent and part and re.match(r'^part\s+' + re.escape(str(part)) + r'(?:\s|[.:—–-]|$)', parent['title'], re.I):
                replacements[parent['id']] = parts[part]['id']
    retained = {}; by_id = {n['id']: n for n in tree}
    def retain(cid, visiting=frozenset()):
        if cid in replacements: return by_id[replacements[cid]]
        if cid in retained: return retained[cid]
        if cid in visiting: raise ValueError('previous_chapter_cycle')
        old = old_by_id[cid]; node = deepcopy(old); key = scope.get(old['block'])
        parent = retain(old['parent_id'], visiting | {cid}) if old.get('parent_id') in old_by_id else None
        if key:
            root = section_nodes[key]
            # Native membership wins over an incompatible old ancestor.
            cursor = parent
            while cursor and cursor['id'] != root['id']:
                cursor = by_id.get(cursor.get('parent_id'))
            if cursor is None: parent = root
            node['chapter_binding_status'] = 'native_scope_existing_heading'
        else:
            node['chapter_binding_status'] = 'prior_scope_unverified'
            node['navigation_status'] = 'compatibility_only'
        node['parent_id'] = parent['id'] if parent else None
        node['level'] = parent['level'] + 1 if parent else old['level']
        retained[cid] = node; by_id[cid] = node; tree.append(node)
        return node
    for old in old_tree: retain(old['id'])
    document['unscoped_chapter_tree'] = [n for n in old_tree if n['block'] not in scope]
    document['chapter_replacements'] = replacements
    def ancestors(cid):
        chain = []; node = by_id.get(cid)
        while node:
            chain.append(node['id']); node = by_id.get(node.get('parent_id'))
        return list(reversed(chain))
    for i, block in enumerate(blocks):
        block['previous_chapter_ids'] = list(block.get('chapter_ids', []))
        key = scope.get(i); ids = []
        if key:
            root = section_nodes[key]
            ids = ancestors(root['id'])
            for cid in block['previous_chapter_ids']:
                mapped = replacements.get(cid, cid)
                chain = ancestors(mapped)
                if root['id'] in chain:
                    ids = list(dict.fromkeys(ids + chain))
            block['chapter_binding_status'] = 'native_scope_with_prior_subheadings' if any(by_id[c].get('chapter_binding_status') == 'prior_scope_unverified' for c in ids) else 'native_scope'
        else:
            for cid in block['previous_chapter_ids']:
                ids = list(dict.fromkeys(ids + ancestors(replacements.get(cid, cid))))
            block['chapter_binding_status'] = 'prior_scope_unverified' if ids else 'no_prior_scope'
        block['chapter_ids'] = ids
        block['chapter_blocks'] = [by_id[cid]['block'] for cid in ids]
        block['embedded_chapter_ids'] = list(dict.fromkeys(replacements.get(cid, cid) for cid in block.get('embedded_chapter_ids', []) if cid in old_by_id))
    document.update(chapter_tree=tree, native_section_coverage=dict(total_sections=len(native['sections']),
                    sections_with_bound_blocks=len(assigned), bound_blocks=len(scope), total_blocks=len(blocks)),
                    native_section_issues=issues, source_sha256=capture['source_sha256'])
    assert [b['text'] for b in blocks] == [b['text'] for b in previous['blocks']]
    return finish(document)


def adapt(capture, previous=None, *, native_paths_verified=True):
    validate_capture(capture)
    if capture['route'] == 'markdown': return markdown_document(capture)
    if capture['route'] == 'edgartools' and previous is not None:
        return edgar_document(capture, previous, native_paths_verified=native_paths_verified)
    raise ValueError('native_adaptation_route_not_supported')


def main():
    import argparse, gzip
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--baseline-artifact', type=Path)
    p.add_argument('--baseline-sha256')
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=False)
    receipt = json.loads((a.capture/'receipt.json').read_bytes())
    native = read_capture(a.capture/'native.json.gz', expected_sha256=receipt['native_sha256'],
                          expected_source_sha256=receipt['source_sha256'])
    previous = None
    baseline_hash = receipt.get('fin_comparison_sha256'); baseline_path = a.capture/'fin-comparison.json.gz'
    paths_verified = True
    if native['route'] == 'edgartools':
        raw = (a.capture/'fin-comparison.json.gz').read_bytes()
        if sha256(raw).hexdigest() != receipt['fin_comparison_sha256']:
            raise ValueError('previous_projection_digest_mismatch')
        previous = json.loads(gzip.decompress(raw))
        if a.baseline_artifact:
            frozen_raw = a.baseline_artifact.read_bytes()
            if not a.baseline_sha256 or sha256(frozen_raw).hexdigest() != a.baseline_sha256:
                raise ValueError('frozen_baseline_digest_mismatch')
            frozen = json.loads(gzip.decompress(frozen_raw))
            fields = ('native_container_id','native_parent_id','kind','text','headers','rows','footer')
            paths_verified = [{k:b.get(k) for k in fields} for b in previous['blocks']] == [{k:b.get(k) for k in fields} for b in frozen['blocks']]
            previous = frozen; baseline_hash = a.baseline_sha256; baseline_path = a.baseline_artifact
    document = adapt(native, previous, native_paths_verified=paths_verified)
    from finalize_structure_prechunks import classify
    final = classify(document)
    packed = gzip.compress(json.dumps(document, ensure_ascii=False).encode(), mtime=0)
    (a.output/'document.json.gz').write_bytes(packed)
    (a.output/'prechunks.json.gz').write_bytes(gzip.compress(json.dumps(final, ensure_ascii=False).encode(), mtime=0))
    result = dict(source_sha256=receipt['source_sha256'], native_sha256=receipt['native_sha256'],
                  parent_fin_sha256=baseline_hash, parent_fin_path=str(baseline_path),
                  native_paths_verified=paths_verified, artifact_sha256=sha256(packed).hexdigest(),
                  implementation_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  route=document['route'], blocks=len(document['blocks']), chapters=len(document['chapter_tree']),
                  native_section_coverage=document.get('native_section_coverage'),
                  unscoped_chapters=len(document.get('unscoped_chapter_tree', [])),
                  source_line_partition_complete=document.get('source_line_partition_complete'),
                  prechunk_roles=final['counts'], provider_calls=0, quality_pass=False, published=False)
    (a.output/'receipt.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__': main()
