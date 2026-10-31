"""Consume frozen native structures; never invoke a parser or a provider.

SEC preserves repaired FIN text/positions and binds native section membership.
Markdown consumes native tokens, keeping a complete source-line partition.
"""
from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
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
    document['outline'] = [dict(block=n['block'], title=n['title'], level=n['level'],
                               parent_block=None, basis=n['basis']) for n in document['chapter_tree']]
    by_id = {n['id']: n for n in document['chapter_tree']}
    for row, node in zip(document['outline'], document['chapter_tree']):
        parent = by_id.get(node.get('parent_id'))
        row['parent_block'] = parent['block'] if parent else None
    document['native_adaptation_version'] = 'native_structure_v1'
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
        for key, boundary in native['toc_boundaries'].items():
            if key not in native['sections']: continue
            start = endpoint(boundary['fields'], boundary['element_paths'], 'start')
            end = endpoint(boundary['fields'], boundary['element_paths'], 'end')
            if start is None or end is None or end <= start:
                issues.append(dict(kind='native_toc_boundary_unresolved', section=key)); continue
            for sid, row in source_rows.items():
                if not sid.startswith(capture['source_sha256'] + ':'): continue
                found = path_index.get(sid.split(':', 1)[1])
                if found is not None and start <= positions[found] and ends[found] < end:
                    dom_membership[sid].add(key)
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
        section = native['sections'][key]; fields = section['fields']; anchor = min(indices)
        part = fields.get('part'); parent = None
        if part:
            parent = 'native-part:' + str(part)
            if part not in parts:
                parts[part] = dict(id=parent, block=anchor, title='Part '+str(part), level=1,
                                   parent_id=None, basis='native_section_part', source_container_id=None)
                tree.append(parts[part])
        node = dict(id='native-section:'+key, block=anchor, title=fields['title'], level=2 if part else 1,
                    parent_id=parent, basis='native_section_node_membership', source_container_id=None,
                    native_section=deepcopy(fields), native_quality_status='upstream_hypothesis')
        tree.append(node); section_nodes[key] = node
    # Existing subheading repairs survive inside their own native section. A
    # heading outside proved membership remains in a separate unresolved ledger.
    retained = {}
    for old in old_tree:
        key = scope.get(old['block'])
        if not key or old['block'] == section_nodes[key]['block']:
            continue
        node = deepcopy(old); root = section_nodes[key]
        parent = retained.get(old.get('parent_id'))
        node['parent_id'] = parent['id'] if parent and scope.get(parent['block']) == key else root['id']
        node['level'] = (parent['level'] if parent and node['parent_id'] == parent['id'] else root['level']) + 1
        tree.append(node); retained[node['id']] = node
    document['unscoped_chapter_tree'] = [n for n in old_tree if n['block'] not in scope]
    by_id = {n['id']: n for n in tree}
    for i, block in enumerate(blocks):
        block['previous_chapter_ids'] = block.get('chapter_ids', [])
        key = scope.get(i); ids = []
        if key:
            root = section_nodes[key]
            if root['parent_id']: ids.append(root['parent_id'])
            ids.append(root['id'])
            ids.extend(cid for cid in block['previous_chapter_ids'] if cid in retained and scope.get(old_by_id[cid]['block']) == key)
        block['chapter_ids'] = ids
        block['chapter_blocks'] = [by_id[cid]['block'] for cid in ids]
        block['embedded_chapter_ids'] = [cid for cid in block.get('embedded_chapter_ids', []) if cid in retained]
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
