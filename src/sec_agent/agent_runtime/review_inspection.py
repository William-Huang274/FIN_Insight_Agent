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
            'location_id': 'RL:' + canonical_sha256([canonical_sha256(paper), path, offset, end]),
            'offset': offset, 'text': text[offset:end], 'next_offset': end if end < len(text) else None,
            'total_characters': len(text), 'notice': 'Exact current text; not a verified financial statement.'}


def read_structured_location(artifacts, paper_id, path, offset=0, max_characters=2000):
    """Read a structured field together, without turning directory previews into evidence."""
    import json
    paper = artifacts.read_paper(paper_id)
    value = paper
    try:
        for part in path.lstrip('/').split('/'):
            part = part.replace('~1', '/').replace('~0', '~')
            value = value[int(part)] if isinstance(value, list) else value[part]
    except (KeyError, ValueError, TypeError, IndexError) as exc:
        raise ValueError('unknown_structured_review_field') from exc
    if not isinstance(value, (dict, list)):
        raise ValueError('use_text_view_for_string_field')
    if offset < 0 or not 1 <= max_characters <= 6000:
        raise ValueError('review_window_requires_nonnegative_offset_and_1_to_6000_characters')
    text = json.dumps(value, ensure_ascii=False)
    end = min(len(text), offset + max_characters)
    return {'paper_id': paper_id, 'paper_digest': canonical_sha256(paper),
        'field_path': path, 'view': 'json', 'offset': offset, 'text': text[offset:end],
        'total_characters': len(text), 'next_offset': end if end < len(text) else None,
        'notice': 'Current structured field; not financial confirmation or a quote location. Use a text leaf for exact finding quotes.'}


def read_quoted_location(artifacts, paper_id, path, quote, *, match_index=None,
                         paper_digest=None, match_offset=0, max_characters=2000):
    """Locate the author's literal selection in one current field, never infer intent."""
    paper = artifacts.read_paper(paper_id)
    digest = canonical_sha256(paper)
    if paper_digest is not None and paper_digest != digest:
        raise ValueError('review_location_is_stale_or_wrong_paper')
    if not quote or not quote.strip() or len(quote) > 6000:
        raise ValueError('review_quote_requires_1_to_6000_nonblank_characters')
    if not 1 <= max_characters <= 6000 or match_offset < 0:
        raise ValueError('review_quote_invalid_window_or_match_offset')
    path = resolve_location(paper, path)
    body = dict(text_locations(paper))[path]
    # Include overlapping exact occurrences; never normalize financial wording.
    positions = [m.start() for m in re.finditer('(?=' + re.escape(quote) + ')', body)]
    base = {'paper_id': paper_id, 'paper_digest': digest, 'field_path': path,
            'quote': quote, 'total_matches': len(positions), 'financial_semantics_verified': False}
    args = {'paper_id': paper_id, 'field_path': path, 'quote': quote,
            'paper_digest': digest, 'max_characters': max_characters}
    if match_index is not None:
        if paper_digest is None:
            raise ValueError('review_quote_selection_requires_candidate_paper_digest')
        if match_offset or not 0 <= match_index < len(positions):
            raise ValueError('review_quote_match_index_out_of_range_or_conflicting_page')
    elif len(positions) == 1:
        if match_offset:
            raise ValueError('review_quote_match_offset_out_of_range')
        match_index = 0
    if match_index is not None:
        start = positions[match_index]
        value = read_location(artifacts, paper_id, path, start, len(quote))
        return {**base, **value, 'status': 'exact_quote_match', 'selected_match': match_index,
                'match_start': start, 'match_end': start + len(quote),
                'runtime_parsing': {'method': 'exact_review_quote_v1',
                    'origin': 'runtime_literal_location', 'model_quote_unchanged': True}}
    if match_offset and match_offset >= len(positions):
        raise ValueError('review_quote_match_offset_out_of_range')
    candidates = []
    width = min(max_characters, 1000)
    for index, start in enumerate(positions[match_offset:match_offset + 6], match_offset):
        lo = max(0, start - min(120, width // 3))
        hi = min(len(body), lo + width)
        candidates.append({'match_index': index, 'match_start': start, 'match_end': start + len(quote),
            'context': body[lo:hi], 'context_start': lo, 'context_end': hi,
            'readback': {'tool': 'read_review_location', 'arguments': {**args, 'match_index': index}}})
    next_offset = match_offset + len(candidates)
    return {**base, 'status': 'multiple_quote_matches' if positions else 'quote_not_found',
            'selected_match': None, 'candidates': candidates,
            'next_page': {'tool': 'read_review_location', 'arguments': {**args, 'match_offset': next_offset}}
                if next_offset < len(positions) else None,
            'readback': {'tool': 'read_review_location', 'arguments': {
                'paper_id': paper_id, 'field_path': path, 'offset': 0, 'max_characters': max_characters}},
            'notice': 'Select a candidate using its readback, or revise your literal quote. No location or finding is accepted by this navigation response.'}


def bind_location(artifacts, messages, paper_id, location_id):
    """Only a successful, current-version tool read can supply a finding quote."""
    from langchain_core.messages import ToolMessage
    for message in reversed(messages):
        value = message.artifact if isinstance(message, ToolMessage) and message.status == 'success' else None
        if not isinstance(value, dict) or value.get('location_id') != location_id:
            continue
        if value.get('paper_id') != paper_id or value.get('paper_digest') != canonical_sha256(artifacts.read_paper(paper_id)):
            raise ValueError('review_location_is_stale_or_wrong_paper')
        current = read_location(artifacts, paper_id, value['field_path'], value['offset'], len(value['text']))
        if current['location_id'] != location_id or current['text'] != value['text']:
            raise ValueError('review_location_content_changed')
        return value['text']
    raise ValueError('review_location_not_observed_read_current_location')


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
                  'Do not join a heading and paragraph or normalize whitespace. Reuse this finding ID; other saved findings remain.',
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
Assess financial support and delivery clarity separately. A charitable interpretation that makes the thesis true
does not make wording clear: readers should not have to supply a missing sign, period, denominator or condition.
Preserve supported conclusions while requesting a precise local clarification. Do not call this a financial error.
For new calculations, use the existing source-bound calculator and retain its ID; identity-valid citations alone
do not bind every operand. Keep source-reported signs distinct from signed contributions in the formula rationale.
Use complete source identifiers in prose. A guessed abbreviation-to-source mapping is a candidate, not a confirmed
citation. Reuse an actual source observation to confirm it; unresolved identity remains explicit. A confirmed intended
source still requires repair of an unresolvable identifier in the delivered draft.
"""


REVIEW_GUIDANCE = """
Review completion is a reasoned handoff, not exhaustive paragraph certification.
Read the current workpapers, reuse prior source reads and valid findings, and focus source checks on
claims that could change the answer, magnitude, timing or confidence. Counter challenges mechanisms and
alternative explanations; Verifier checks material facts, units, periods, calculations and source support.
Neither duplicates the other's entire assignment. State what you checked and any necessary unfinished work.

The runtime preserves read receipts, versions and legacy checks. Do NOT recreate inspection tables,
paragraph coverage, hashes or previously saved checks. Automatic paragraph/keyword candidates are navigation
only and do not create mandatory work. Assess each assigned paper concisely; no per-paragraph pass records.
For a paper finding, an already-read exact problematic_quote remains valid without a location_id.
When you need a version-bound location_id, pass your chosen exact quote and field_path to
read_review_location; runtime locates it. Do not estimate character offsets for text already read.
Multiple literal matches return contexts and exact selection calls; choose the intended occurrence.
For evidence supply source_id and your chosen exact quote; runtime locates it. Returned window_span is
reading context, not citation offsets. Repeated quotes or conflicting selections return candidates for
your decision; nothing is saved as accepted until selection is resolved. Do not invent mappings.
Record specific source-grounded findings as they emerge.

Ordinary editorial suggestions are advisory. A material issue changes the answer or leaves a significant
statement misleading; identify the affected claim and explain its impact. Necessary checks you could not
complete belong in unresolved_data_requests. Known limits of the answer belong in research_limitations.
Do not label a review incomplete merely because legacy inspection slots are empty; do not label genuinely
unfinished critical verification complete. No quota of findings, calculations or positive conclusions.
Submit findings and your assessment once the question is adequately reviewed. Other reviewers and Lead
evaluate these judgments; runtime identifier validation never certifies financial truth.
"""
