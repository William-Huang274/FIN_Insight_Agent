"""Current-paper review navigation; no financial verdicts or extra runtime."""
from difflib import SequenceMatcher
from .research_graph_contracts import canonical_sha256


PROSE_FIELDS = ('thesis', 'mechanism', 'narrative_markdown', 'counterevidence', 'what_would_change', 'open_gaps')


def text_locations(value, path=''):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from text_locations(child, path + '/' + str(key).replace('~', '~0').replace('/', '~1'))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from text_locations(child, path + '/' + str(index))


def read_location(artifacts, paper_id, path, offset=0, max_characters=2000):
    paper = artifacts.read_paper(paper_id)
    fields = dict(text_locations(paper))
    if path not in fields:
        raise ValueError('unknown_review_field:' + path)
    if offset < 0 or not 1 <= max_characters <= 6000:
        raise ValueError('review_window_requires_nonnegative_offset_and_1_to_6000_characters')
    text = fields[path]
    end = min(len(text), offset + max_characters)
    return {'paper_id': paper_id, 'paper_digest': canonical_sha256(paper), 'field_path': path,
            'offset': offset, 'text': text[offset:end], 'next_offset': end if end < len(text) else None,
            'total_characters': len(text), 'notice': 'Exact current text; not a verified financial statement.'}


def quote_recovery(artifacts, finding):
    """Suggest literal windows without accepting or rewriting a faulty quote."""
    paper = artifacts.read_paper(finding.paper_id)
    candidates = []
    for path, text in text_locations(paper):
        if not path.startswith(tuple('/' + key for key in (*PROSE_FIELDS, 'claims'))):
            continue
        match = SequenceMatcher(None, finding.problematic_quote, text, autojunk=False).find_longest_match()
        if match.size >= 4:
            candidates.append((match.size, path, max(0, match.b - 100)))
    return {'finding_id': finding.finding_id, 'accepted': False,
        'remedy': 'Read a current field window and copy ONE exact contiguous substring, including literal markdown. '
                  'Do not join a heading and paragraph or normalize whitespace. Reuse this finding ID; other saved findings remain. '
                  'If this is the final call, put the corrected finding directly in submit_case_review with incomplete/unresolved work explicitly listed.',
        'locations': [read_location(artifacts, finding.paper_id, path, offset, 800)
                      for _, path, offset in sorted(candidates, reverse=True)[:3]],
        'read_tool': 'read_review_location'}


def inspection_manifest(artifacts):
    return {row['paper_id']: {
        'paper_digest': canonical_sha256(artifacts.read_paper(row['paper_id'])),
        'material_claim_ids': [c['claim_id'] for c in artifacts.read_paper(row['paper_id'])['claims']
                               if c.get('materiality') == 'high'],
        'prose_fields': [key for key in PROSE_FIELDS if artifacts.read_paper(row['paper_id']).get(key)],
        'required_dimensions': ['claim_support', 'citation_trace', 'prose_consistency', 'scope_and_counterevidence'],
    } for row in artifacts.catalog()['papers']}


INSPECTION_GUIDANCE = """
Before reading, organize review around the supplied inspection_manifest, not a fresh full research assignment.
Use compact inspection_checks in the final submission. Cover each material claim and four dimensions for every paper:
claim_support (source, period, unit and actual/forecast); citation_trace (literal references in prose AND structured claim/source bindings);
prose_consistency (numeric bridges, signed contributions versus levels, headings and conclusions read together);
scope_and_counterevidence (original user question versus author wording, strongest competing explanation and limits).
For each check cite an exact current field_path and target_quote, current paper_digest, and concise public result grounded in original source_checks.
Several claim IDs may share one genuinely common check. Arithmetic/literal presence alone cannot certify causal or prose correctness.
For a bridge explain positive and negative contributions to the CHANGE, not merely two correct totals. For cash/segment comparisons keep periods and denominators explicit.
For citation_trace, resolve prose identifiers and ensure new material explanations have matching claim/source bindings; archived sources existing somewhere is insufficient.
Do not accept model prior knowledge or an author's hypothetical caveat as source evidence. Counter must distinguish a qualification of broad author wording from refutation of the actual user question.
Each dimension must say checked, issue (link recorded/current finding IDs), unresolved (also list unfinished work), or not_applicable with a concrete scope reason.
Not-applicable is only allowed for prose_consistency; it cannot replace checking claims, citation trace or scope. A check is a reviewer assertion, not runtime semantic proof.
Read every full workpaper once and relevant original source windows. Avoid repeating reads already available. Never fill inspection checks from an author note alone.
"""
