"""Conservative textual scope binding; never certifies financial equivalence."""
import re
from .research_graph_contracts import canonical_sha256


def disposition_scope(report, quote):
    text = report.get('narrative_markdown', '')
    if not quote or quote not in text:
        return None  # Title/chart-only or legacy responses retain full-report binding.
    starts = [0] + [m.start() for m in re.finditer(r'(?m)^#{1,6} ', text) if m.start()]
    ends = starts[1:] + [len(text)]
    spans = list(zip(starts, ends))
    # Include every section intersecting every occurrence, not just an unchanged
    # sentence whose surrounding argument might have been rewritten.
    positions = [m.start() for m in re.finditer(re.escape(quote), text)]
    selected = [text[a:b] for a, b in spans if any(a < p + len(quote) and b > p for p in positions)]
    if not selected:
        return None
    shared = [text[spans[0][0]:spans[0][1]], text[spans[-1][0]:spans[-1][1]]]
    if len(spans) > 1:
        shared.append(text[spans[1][0]:spans[1][1]])
    # Repeated headings are ambiguous: bind the exact section text and its
    # occurrence count. A new/removed copy requires a new author decision.
    sections = [{'digest': canonical_sha256(s), 'count': text.count(s)} for s in dict.fromkeys(selected)]
    cited_text = '\n'.join(selected + shared)
    from .source_references import reference_handle
    citations = {key: value for key, value in report.get('citations', {}).items()
                 if key in cited_text or reference_handle(key) in cited_text}
    return {'version': 1, 'sections': sections,
        'shared_digest': canonical_sha256({'title': report.get('title'), 'edges': shared,
            'charts': report.get('charts', []), 'citations': citations})}


def scope_unchanged(report, response):
    prior = response.get('disposition_scope')
    if not prior:
        return False
    current = disposition_scope(report, response.get('current_quote'))
    return current == prior
