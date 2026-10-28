"""Validate structural companions without changing independent relevance ranks.

The separately authorized table completion reader owns supplemental text.
Original adjacency and a table-note relationship are never ranking evidence.
"""
from .source_window_selection import select_context_companions


def _table_identity(table):
    start, end = table.get('source_char_start'), table.get('source_char_end')
    digest = table.get('content_sha256')
    if (type(start) is not int or type(end) is not int or not 0 <= start < end
            or not isinstance(digest, str) or len(digest) != 64
            or any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('source_structure_selection_invalid_table')
    return start, end, digest


def _covered(lo, hi, identifiers, by_id):
    intervals = sorted((max(lo, by_id[n]['original_source']['source_char_start']),
                        min(hi, by_id[n]['original_source']['source_char_end'])) for n in identifiers)
    end, covered = lo, 0
    for start, stop in intervals:
        if stop > max(start, end):
            covered += stop - max(start, end)
            end = stop
    return covered


def select_structure_companions(rows, expansion):
    _, fallback = select_context_companions(rows, expansion)
    by_id = {r['node_id']: r for r in rows}
    core = {r['node_id'] for r in rows[:8]}
    notes = {}
    for row in rows:
        structure = row.get('source_structure', {})
        if structure.get('status') != 'verified_original_coordinates':
            continue
        for note in structure.get('footnotes', []):
            if note.get('binding') != 'explicit_post_table_marker':
                continue
            table = _table_identity(note['table'])
            origin = row['original_source']
            start, end = origin.get('source_char_start'), origin.get('source_char_end')
            lo, hi = note.get('source_char_start'), note.get('source_char_end')
            if (any(type(v) is not int for v in (start, end, lo, hi))
                    or not 0 <= start < end or not table[1] <= lo < hi
                    or not start < hi or not lo < end):
                raise ValueError('source_structure_selection_invalid_note')
            key = (row['parent_document_id'], table)
            groups = notes.setdefault(key, {})
            group = groups.setdefault((lo, hi, note['marker']), [])
            if row['node_id'] not in group:
                group.append(row['node_id'])
    promotions, used = {}, set()
    position = {r['node_id']: i for i, r in enumerate(rows)}
    for row in rows[:8]:
        structure = row.get('source_structure', {})
        if structure.get('status') != 'verified_original_coordinates':
            continue
        options = []
        for table in structure.get('tables', []):
            identity = _table_identity(table)
            origin = row['original_source']
            start, end = origin.get('source_char_start'), origin.get('source_char_end')
            if (type(start) is not int or type(end) is not int or not 0 <= start < end
                    or not start < identity[1] or not identity[0] < end):
                raise ValueError('source_structure_selection_invalid_table_owner')
            groups = notes.get((row['parent_document_id'], identity), {})
            # A chunk may contain only the first words of the linked note.
            # Require actual original interval coverage, not metadata presence.
            for (lo, hi, _), linked in groups.items():
                present = set(linked) & (core | used)
                covered = _covered(lo, hi, present, by_id)
                if covered == hi - lo:
                    continue
                options.extend(n for n in linked if n not in core | used
                               and _covered(lo, hi, present | {n}, by_id) > covered)
        if not options:
            continue
        if len(used) == 2:
            break
        other = min(options, key=position.__getitem__)
        promotions[row['node_id']] = (other, 'explicit_post_table_marker')
        used.add(other)
    for pair in fallback['companions']:
        if len(used) == 2:
            break
        anchor, other = pair['anchor'], pair['companion']
        if anchor not in promotions and other not in used:
            promotions[anchor] = (other, 'verified_adjacent_original')
            used.add(other)
    return rows, {'policy': 'supplemental-structure.v2', 'top_k_unchanged': True,
        'promotion_limit': 0, 'promotions': [], 'companions': [
            {'anchor': anchor, 'companion': other, 'basis': basis}
            for anchor, (other, basis) in promotions.items()]}
