"""Locate wording shared by an opinion and a manuscript. Matches are navigation only."""
import re
import json
from math import sqrt

from .source_references import REFERENCE_TOKEN


def consultation_revision_context(messages, original, candidate):
    """Actual imported review of a report or hypotheses; never an investigation verdict."""
    for message in reversed(messages):
        if getattr(message, 'name', '') != 'read_research_agent_result' or getattr(message, 'status', '') != 'success':
            continue
        try:
            result = json.loads(message.content)
        except (ValueError, TypeError):
            continue
        if (not isinstance(result, dict) or result.get('status') != 'completed'
                or result.get('purpose') != 'review' or not isinstance(result.get('opinion'), str)):
            continue
        return {'review_receipt': message.tool_call_id, 'reviewed_report_digest': result.get('reviewed_report_digest'),
                'review_scope': 'report_version' if result.get('reviewed_report_digest') else 'delegated_research_question',
                'status': 'navigation_only_not_a_verdict',
                'related_wording': related_wording(original, candidate, result['opinion']),
                'review_readback': {'tool': 'read_research_agent_result', 'arguments': {'task_id': result['task_id']}},
                'meaning': 'Exact current wording beside the actual review; matches may be unrelated. A review of hypotheses is not review of this manuscript. Author decides whether the reasoning is consistent. Saved is not reviewed.'}
    return None


def _terms(text):
    words = re.findall(r'[a-z][a-z0-9-]+|[\u3400-\u9fff]+', re.sub(REFERENCE_TOKEN, '', text).lower())
    return {term for word in words for term in
            ([word] if word.isascii() else [word[i:i+2] for i in range(len(word)-1)])}


def related_wording(original, candidate, opinion):
    """Select bounded exact excerpts; keep closing restatements eligible even when untouched."""
    lines = [(s.strip(), _terms(s)) for s in opinion.splitlines()
             if len(s.strip()) >= 16 and not s.lstrip().startswith(('#', 'PASSAGE', '`PASSAGE'))]
    matches = []
    headings = [(m.start(), m[0]) for m in re.finditer(r'(?m)^#{1,6} .+$', candidate)]
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
                'section': next((title for offset, title in reversed(headings) if offset <= start), ''),
                'verbatim_in_base':sentence in original, 'opinion_excerpt':best[1][:500]}))
    # Cover distinct argument sections before filling by similarity. Otherwise
    # repeated legal terms can crowd out a later investment restatement.
    ranked = sorted(matches, key=lambda pair:-pair[0])
    sections = {}
    for pair in ranked:
        sections.setdefault(pair[1]['section'], pair)
    selected = list(sections.values())[:9]
    offsets = {p[1]['offset'] for p in selected}
    selected += [p for p in ranked if p[1]['offset'] not in offsets][:max(0, 11-len(selected))]
    selected += matches[-1:]
    if matches:
        last = matches[-1][1]
        offset = last['offset']
        start = max(candidate.rfind('\n', 0, offset) + 1, offset - 450)
        stop = candidate.find('\n', offset)
        last['paragraph_window'] = candidate[start:min(len(candidate) if stop == -1 else stop, offset + 500)]
    return [v for _,v in sorted({row['offset']:row for _,row in selected}.items())]
