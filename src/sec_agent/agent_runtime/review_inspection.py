"""Current-paper review navigation; no financial verdicts or extra runtime."""
from difflib import SequenceMatcher
import re
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


def resolve_location(paper, path, quote=None):
    """Resolve exact field/claim identifiers, never fuzzy-match financial text."""
    fields = dict(text_locations(paper))
    path = '/' + path.lstrip('/')
    parts = path.split('/')
    if len(parts) >= 3 and parts[1] == 'claims':
        matches = [i for i, claim in enumerate(paper['claims']) if claim['claim_id'] == parts[2]]
        if len(matches) == 1:
            parts[2] = str(matches[0])
            path = '/'.join(parts)
    if path in fields:
        return path
    if quote:
        matches = [key for key, text in fields.items() if key.startswith(path + '/') and quote in text]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise ValueError('ambiguous_review_field_select_one:' + ','.join(matches[:12]))
    raise ValueError('unknown_review_field:' + path)


def read_location(artifacts, paper_id, path, offset=0, max_characters=2000):
    paper = artifacts.read_paper(paper_id)
    fields = dict(text_locations(paper))
    try:
        path = resolve_location(paper, path)
    except ValueError:
        # A container such as claims/counterevidence is a navigation request,
        # not missing source evidence. Return exact leaf selectors, not a crash.
        prefix = '/' + path.lstrip('/') + '/'
        children = [{'field_path': key, 'preview': text[:160], 'total_characters':len(text)}
                    for key, text in fields.items() if key.startswith(prefix)]
        if not children:
            raise
        if offset < 0 or not 1 <= max_characters <= 6000:
            raise ValueError('review_window_requires_nonnegative_offset_and_1_to_6000_characters')
        return {'paper_id':paper_id, 'paper_digest':canonical_sha256(paper), 'kind':'field_directory',
                'locations':children[offset:offset+12], 'next_offset':offset+12 if offset+12<len(children) else None,
                'notice':'Select an exact field_path. Directory previews are not a complete field read.'}
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
        'text_targets': [{'field_path':path, 'preview':text[:120]} for path,text in text_locations(artifacts.read_paper(row['paper_id']))
            if path.split('/')[1] in PROSE_FIELDS or (path.startswith('/claims/') and path.endswith('/statement'))],
        'required_dimensions': ['claim_support', 'citation_trace', 'prose_consistency', 'scope_and_counterevidence'],
        'semantic_targets': semantic_targets(artifacts.read_paper(row['paper_id'])),
    } for row in artifacts.catalog()['papers']}


def semantic_targets(paper):
    """Version-bound paragraph navigation, not a classifier of economic truth."""
    targets = []
    relation = re.compile(r'增长|增加|减少|下降|上升|贡献|驱动|抵减|叠加|转化|归因|导致|受益|压力|质量|假设|'
                          r'growth|increase|decrease|contribut|offset|driv|caus|because|quality', re.I)
    for path, text in text_locations(paper):
        field = path.split('/')[1]
        if field not in {'thesis','mechanism','narrative_markdown','counterevidence','what_would_change'}:
            continue
        for part in re.finditer(r'[^\n]+(?:\n(?!\n)[^\n]+)*', text):
            quote = part.group()
            if quote.lstrip().startswith(('#','|')) or not quote.strip():
                continue
            if field=='narrative_markdown' and not relation.search(quote):
                continue
            targets.append({'target_id':canonical_sha256([canonical_sha256(paper),path,part.start(),quote])[:20],
                'field_path':path,'start':part.start(),'end':part.end(),'preview':quote[:160],
                'selection_basis':'runtime paragraph navigation; main judgment/condition or relation wording, not a financial verdict'})
    return targets


SEMANTIC_SELF_CHECK = """
For each important judgment and numeric attribution paragraph, check arithmetic separately from meaning.
State what relationship the actual sentence expresses, what relationship the cited evidence supports, and whether
they agree, contradict, are ambiguous, or remain unsupported. Preserve positive/negative contribution, period,
denominator, actual/forecast and conditional language. A correct bridge or plausible overall thesis does not certify
each related sentence. Ambiguous wording may need clarification without being a material factual reversal.
Use complete source identifiers in prose. A guessed abbreviation-to-source mapping is a candidate, not a confirmed
citation. Reuse an actual source observation to confirm it; unresolved identity remains explicit. A confirmed intended
source still requires repair of an unresolvable identifier in the delivered draft.
"""


INSPECTION_GUIDANCE = """
Before reading, organize review around the supplied inspection_manifest, not a fresh full research assignment.
Copy field_path from text_targets, for example /claims/0/statement, /narrative_markdown or /counterevidence/0. Exact claim-ID selectors such as claims/C1/statement also resolve when C1 is an actual claim ID. A container such as claims returns a field directory. Do not invent a missing source from a locator error.
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
For prose_consistency, cover each semantic_targets entry separately with semantic_target_id, expressed_relationship,
supported_relationship and semantic_verdict (consistent/contradictory/ambiguous/unsupported). Copy an exact quote
inside that paragraph; do not use one correct equation to mark unrelated paragraphs checked. Reuse existing evidence.
Use read_review_references for runtime citation parsing. Exact means identifier identity only, not semantic support.
For a nonexact candidate, confirm_review_reference requires a prior actual source read and your concise mapping reason.
Suffix/content resemblance is never confirmation. Runtime automatically attaches delivery-reference repair findings;
do not rewrite them as model findings. Unconfirmed nonexact references require incomplete and unresolved work.
read_review_source_span returns a digest-bound quote_span that can replace copied quote text in source_checks.
Runtime table-layout compatibility may restore a unique literal span with identical nonempty cells; its
runtime_compatibility_parse record is not model output or proof of column/period meaning.
""" + SEMANTIC_SELF_CHECK
