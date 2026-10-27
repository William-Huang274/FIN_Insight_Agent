"""Build necessary citation coverage from reviewed source coordinates.

Overlapping chunks are storage windows, not separate financial requirements.
No ranks, amounts, query text or provider results enter the covering algorithm.
"""
from hashlib import sha256


def cover_reviewed_span(bundle, start, end):
    text = bundle['text']
    if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
        raise ValueError('reviewed_span_coordinates_invalid')
    windows = []
    for chunk in bundle['chunks']:
        lo, hi = chunk['source_char_start'], chunk['source_char_end']
        if lo >= end or hi <= start:
            continue
        if text[lo:hi] != chunk['body'] or sha256(chunk['body'].encode()).hexdigest() != chunk['digest']:
            raise ValueError('reviewed_span_chunk_identity_mismatch')
        windows.append((max(start, lo), min(end, hi), chunk))
    selected, cursor = [], start
    while cursor < end:
        eligible = [w for w in windows if w[0] <= cursor < w[1]]
        if not eligible:
            raise ValueError('reviewed_span_has_uncovered_gap')
        # Minimum interval cover: take the farthest end at each frontier.
        # Identity tie-breaks remain independent of any retrieval ranking.
        lo, hi, chunk = min(eligible, key=lambda w: (-w[1], w[2]['id']))
        selected.append({'source_id': bundle['source']['id'], 'chunk_id': chunk['id'],
                         'body_sha256': chunk['digest'], 'quote': text[lo:hi],
                         'source_char_start': lo, 'source_char_end': hi})
        cursor = hi
    return selected


def retrieved_span_covered(bundle, start, end, chunk_ids):
    """Any verified original windows may cover the unchanged reviewed span.

    Do not require the particular minimum cover chosen for a label example.
    The caller binds returned IDs to this exact source version first.
    """
    by_id = {c['id']: c for c in bundle['chunks']}
    if not set(chunk_ids) <= by_id.keys():
        raise ValueError('reviewed_span_unknown_chunk_identity')
    selected = {**bundle, 'chunks': [by_id[k] for k in set(chunk_ids)]}
    try:
        cover_reviewed_span(selected, start, end)
    except ValueError as error:
        if str(error) == 'reviewed_span_has_uncovered_gap':
            return False
        raise
    return True
