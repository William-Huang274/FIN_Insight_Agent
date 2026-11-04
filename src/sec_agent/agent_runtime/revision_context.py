"""Locate wording shared by an opinion and a manuscript. Matches are navigation only."""
import re
from math import sqrt

from .source_references import REFERENCE_TOKEN


def _terms(text):
    words = re.findall(r'[a-z][a-z0-9-]+|[\u3400-\u9fff]+', re.sub(REFERENCE_TOKEN, '', text).lower())
    return {term for word in words for term in
            ([word] if word.isascii() else [word[i:i+2] for i in range(len(word)-1)])}


def related_wording(original, candidate, opinion):
    """Select bounded exact excerpts; keep closing restatements eligible even when untouched."""
    lines = [(s.strip(), _terms(s)) for s in opinion.splitlines()
             if len(s.strip()) >= 16 and not s.lstrip().startswith(('#', 'PASSAGE', '`PASSAGE'))]
    matches = []
    for match in re.finditer(r'[^。！？!?\n]+[。！？!?]?', candidate):
        sentence = match[0].strip()
        if not lines or len(sentence) < 12 or sentence.startswith('#'):
            continue
        terms = _terms(sentence)
        best = max(((len(terms & other) / sqrt(max(1,len(terms)*len(other))), line)
                    for line, other in lines if len(terms & other) >= 4), default=(0, ''))
        if best[0] >= 0.15:
            start = match.start() + match[0].index(sentence)
            matches.append((best[0], {'offset':start, 'excerpt':sentence[:500],
                'verbatim_in_base':sentence in original, 'opinion_excerpt':best[1][:500]}))
    # Show the strongest links plus the last related restatement, in manuscript order.
    selected = sorted(matches, key=lambda pair:-pair[0])[:5] + matches[-1:]
    if matches:
        last = matches[-1][1]
        offset = last['offset']
        start = max(candidate.rfind('\n', 0, offset) + 1, offset - 450)
        stop = candidate.find('\n', offset)
        last['paragraph_window'] = candidate[start:min(len(candidate) if stop == -1 else stop, offset + 500)]
    return [v for _,v in sorted({row['offset']:row for _,row in selected}.items())]
