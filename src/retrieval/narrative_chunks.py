"""Lossless sentence groups inside one original paragraph.

Reuse the existing abbreviation-aware detector. Oversize single sentences are
preserved, not silently cut; the caller must qualify them against its hard
model-input budget. Coordinates refer to the unchanged input paragraph.
"""
import re

from .object_view_compiler_v2 import _abbreviation_aware_sentence_spans


def sentence_groups(text: str, max_bytes: int = 6000):
    if max_bytes <= 0:
        raise ValueError('positive_sentence_group_budget_required')
    # Chinese terminal punctuation needs no following whitespace. Retain
    # punctuation/closing quotes and all whitespace in the original slices.
    spans = []
    for start, end in _abbreviation_aware_sentence_spans(text):
        cursor = start
        for match in re.finditer(r'[。！？]+[”’」』）]*', text[start:end]):
            boundary = start + match.end()
            spans.append((cursor, boundary)); cursor = boundary
        if cursor < end:
            spans.append((cursor, end))
    pending = None
    for start, end in spans:
        if pending is not None and len(text[pending:end].encode('utf8')) > max_bytes:
            yield pending, start, text[pending:start]
            pending = None
        if pending is None:
            pending = start
    if pending is not None:
        yield pending, len(text), text[pending:]
