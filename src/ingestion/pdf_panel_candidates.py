"""Source-drawn panel containers for PDF structural comparison.

Uses PyMuPDF's native drawing/word extraction. Containers do not imply a table,
heading, financial meaning or global reading order. Ambiguous overlaps stay
unassigned; original word identities are never duplicated or discarded.
"""
from typing import Any


def _contains(outer, inner, tolerance=0.05):
    return all((outer[0]-tolerance <= inner[0], outer[1]-tolerance <= inner[1],
                inner[2] <= outer[2]+tolerance, inner[3] <= outer[3]+tolerance))


def _panel_shape(drawing):
    items = drawing.get('items') or []
    if drawing.get('fill') is None:
        return None
    if len(items) == 1 and items[0][0] == 're':
        return 'native_rectangle'
    # Rounded panels have four side segments and four corner curves. Validate
    # the actual side positions; a pie sector/chart is not a rounded panel.
    if len(items) != 8 or sum(i[0] == 'c' for i in items) != 4:
        return None
    x0, y0, x1, y1 = drawing['rect']
    sides = set()
    for item in items:
        if item[0] != 'l':
            continue
        a, b = item[1:]
        if abs(a[0]-b[0]) < 0.05:
            for name, x in [('left', x0), ('right', x1)]:
                if abs(a[0]-x) < 0.05:
                    sides.add(name)
        if abs(a[1]-b[1]) < 0.05:
            for name, y in [('top', y0), ('bottom', y1)]:
                if abs(a[1]-y) < 0.05:
                    sides.add(name)
    return 'native_rounded_panel_candidate' if len(sides) == 4 else None


def source_panel_candidates(page: Any) -> dict:
    words = page.get_text('words', sort=False)
    panels = []
    seen = set()
    for drawing in page.get_drawings():
        shape = _panel_shape(drawing)
        bbox = tuple(float(v) for v in drawing['rect'])
        key = tuple(round(v, 3) for v in bbox)
        if shape is None or key in seen:
            continue
        seen.add(key)
        contained = [i for i, w in enumerate(words) if _contains(bbox, w[:4])]
        if not contained:
            continue
        panels.append({'panel_index': len(panels), 'bbox': bbox,
                       'drawing_seqno': drawing.get('seqno'), 'shape': shape,
                       'contained_word_indices': contained, 'owned_word_indices': []})
    assignments = []
    for index, word in enumerate(words):
        candidates = [p for p in panels if index in p['contained_word_indices']]
        leaves = [p for p in candidates if not any(
            q is not p and _contains(p['bbox'], q['bbox']) and p['bbox'] != q['bbox']
            for q in candidates)]
        owner = leaves[0]['panel_index'] if len(leaves) == 1 else None
        if owner is not None:
            panels[owner]['owned_word_indices'].append(index)
        assignments.append({'word_index': index, 'text': word[4], 'bbox': list(word[:4]),
                            'native_block_line_word': list(word[5:8]), 'panel_index': owner,
                            'assignment': 'unique_leaf' if owner is not None else
                                          'ambiguous_overlap' if leaves else 'outside_panels'})
    return {'schema_version': 'fin_pdf_source_panel_candidates_v1', 'panels': panels,
            'words': assignments, 'global_reading_order_qualified': False,
            'financial_semantics_qualified': False}
