"""Unambiguous original-text locators for source-first label authoring.

Repeated financial table headers need an explicit, unique section anchor.
The helper never reads ranked candidates or silently chooses the first match.
"""


def _unique(text, anchor, start, end):
    if not isinstance(anchor, str) or not anchor:
        raise ValueError('review_anchor_required')
    found = text.find(anchor, start, end)
    if found < 0:
        raise ValueError('review_anchor_missing')
    if text.find(anchor, found + 1, end) >= 0:
        raise ValueError('review_anchor_ambiguous')
    return found


def locate_reviewed_span(text, start_anchor, end_anchor, *, section_start=None,
                         section_end=None, closing_table=False):
    """Resolve exact coordinates in a uniquely identified optional section.

    closing_table requires an explicit table-opening start anchor and uses its
    first non-nested closing marker. Other end anchors must be unique inside
    the section. No normalization changes original character positions.
    """
    lo, hi = 0, len(text)
    if section_start is not None:
        lo = _unique(text, section_start, lo, hi)
    if section_end is not None:
        hi = _unique(text, section_end, lo, hi)
    start = _unique(text, start_anchor, lo, hi)
    if closing_table:
        if not start_anchor.startswith('[TABLE:') or end_anchor != '[/TABLE]':
            raise ValueError('review_explicit_table_anchor_required')
        end = text.find(end_anchor, start + len(start_anchor), hi)
        if end < 0 or '[TABLE:' in text[start + len(start_anchor):end]:
            raise ValueError('review_table_boundary_invalid')
    else:
        end = _unique(text, end_anchor, start, hi)
    return start, end + len(end_anchor)
