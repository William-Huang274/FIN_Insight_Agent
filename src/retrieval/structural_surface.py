"""Recognize parser-only surfaces without guessing financial relevance.

These bytes remain in the original and its partition, but need no embedding
and cannot compete as an answer. Short facts, headings, units and footnotes
are deliberately not classified by their length.
"""
import re

_TABLE_MARKER = re.compile(r'\[(?:TABLE:[^\]\r\n]*|/TABLE)\]')


def structural_only(text):
    remainder = _TABLE_MARKER.sub('', text)
    # SEC text conversion can leave rows containing only empty cell separators.
    # Preserve '-' (a reported nil value), numbers, currencies and all wording.
    # HTML filings also use zero-width spaces/BOMs as empty-cell furniture.
    # Do not normalize the stored text or strip symbols carrying nil/unit data.
    return not remainder.replace('|', '').replace('\u200b', '').replace('\ufeff', '').strip()
