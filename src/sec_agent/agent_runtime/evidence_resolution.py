"""Deterministic citation navigation and literal selection, never financial inference."""
import re

from .research_graph_contracts import canonical_sha256
from sec_agent.research_foundation.source_quotes import resolve_quote


REFERENCE = re.compile(r'(?:PASSAGE::|CALC::|P\d+:S)[A-Za-z0-9_:./…-]+')
IDENTITY_KEYS = ('passage_id', 'evidence_id', 'numeric_fact_id', 'fact_id', 'calculation_id')


def parsing_record(method, original, normalized, **basis):
    return {'origin': 'runtime_compatibility_parse', 'method': method,
            'original_input': original, 'normalized_result': normalized, 'basis': basis,
            'financial_semantics_verified': False}


def source_body(artifacts, source_id):
    item = artifacts.source_item(source_id)
    return str(item.get('passage') or item.get('bounded_excerpt') or item.get('value_decimal') or '')


def select_source_span(body, digest, start, end):
    if digest != canonical_sha256(body):
        raise ValueError('source_span_stale_digest')
    if not 0 <= start < end <= len(body) or end - start > 6000:
        raise ValueError('source_span_requires_valid_offsets_and_at_most_6000_characters')
    return body[start:end]


class SourceQuoteSelectionRequired(ValueError):
    """Navigation feedback: no quote or occurrence has been selected by the host."""

    def __init__(self, feedback):
        import json
        self.feedback = feedback
        super().__init__(json.dumps(feedback, ensure_ascii=False))


def quote_selection_feedback(error):
    """Only pure navigation requests are nonfatal; any other error still stops."""
    import json
    try:
        value = json.loads(str(error))
    except (ValueError, TypeError):
        return None
    errors = value.get('errors', []) if isinstance(value, dict) else []
    if errors and all(e.startswith('source_quote_selection_required:') for e in errors):
        return {**value, 'status': 'source_quote_selection_required', 'accepted': False,
                'notice': 'The affected selection is pending and was not accepted. Any independently saved findings are listed separately; the review is not complete.'}
    return None


def bind_source_quote(body, source_id, quote, span=None):
    """Locate model-selected text; never choose between conflicting selections."""
    digest = canonical_sha256(body)
    original = {'source_id': source_id, 'quote': quote, 'quote_span': span}
    selected = None
    if span:
        selected = select_source_span(body, span['source_digest'], span['start'], span['end'])
        if not quote or quote == selected:
            return selected, span, parsing_record('digest_bound_source_span_v1', original, selected,
                source_digest=digest, start=span['start'], end=span['end'])
    exact, layout = resolve_quote(body, quote)
    positions = [m.start() for m in re.finditer(re.escape(exact), body)] if exact else []
    if span or len(positions) != 1:
        candidates = []
        for pos in positions[:6]:
            lo, hi = max(0, pos-120), min(len(body), pos+len(exact)+120)
            candidates.append({'quote_span': {'source_digest': digest, 'start': pos, 'end': pos+len(exact)},
                'context_preview': body[lo:min(hi,lo+1000)],
                'readback': {'tool': 'read_review_source_span', 'arguments': {
                    'source_id': source_id, 'start': lo, 'max_characters': min(6000,hi-lo)}}})
        raise SourceQuoteSelectionRequired({'status': 'source_quote_selection_required',
            'reason': 'quote_span_conflict' if span else 'multiple_quote_matches' if positions else 'quote_not_found',
            'source_id': source_id, 'original_input': original, 'accepted': False, 'selected_match': None,
            'supplied_span_preview': selected[:1000] if selected is not None else None,
            'supplied_span_characters': len(selected) if selected is not None else None,
            'quote_candidates': candidates, 'total_matches': len(positions),
            'readback': {'tool': 'read_review_source_span', 'arguments': {
                'source_id': source_id, 'start': 0, 'max_characters': 1000}},
            'more_matches_readback': {'tool': 'read_review_source_span', 'arguments': {
                'source_id': source_id, 'anchor': exact, 'match_offset': 6}} if len(positions)>6 else None,
            'remedy': 'Decide which text you intend. For the literal quote, resubmit source_id + quote without quote_span; runtime locates it. For repeated text choose a returned exact quote_span. For the supplied span, explicitly use its full text or omit quote. A reading window is not a selected quotation. No finding or review has been accepted.'})
    pos = positions[0]
    resolved = {'source_digest': digest, 'start': pos, 'end': pos+len(exact)}
    return exact, resolved, parsing_record('unique_source_quote_location_v1', original, exact,
        source_digest=digest, start=pos, end=pos+len(exact), layout_recovery=layout)



def citation_inventory(artifacts, paper_id):
    from .review_inspection import PROSE_FIELDS, text_locations
    paper = artifacts.read_paper(paper_id)
    version = canonical_sha256(paper)
    catalog = artifacts.source_identity_catalog(paper_id)
    result = []
    for path, text in text_locations(paper):
        if path.split('/')[1] not in PROSE_FIELDS:
            continue
        for match in REFERENCE.finditer(text):
            raw = match.group().rstrip('.')
            end = match.start() + len(raw)
            short = '...' in raw or '…' in raw
            parts = re.split(r'\.{3}|…', raw)
            pattern = '^' + '.+'.join(re.escape(part) for part in parts) + '$'
            candidates = []
            # A complete case-local alias names its owning paper explicitly.
            # Reading and reviewing it must use the same authorized snapshot.
            # Never extend suffix/ellipsis search across papers.
            reference_catalog = catalog
            if re.fullmatch(r'P\d+:S\d+', raw):
                owner = raw.split(':', 1)[0]
                reference_catalog = []
                if owner in {p['paper_id'] for p in artifacts.catalog()['papers']}:
                    reference_catalog = [item for item in artifacts.source_identity_catalog(owner)
                                         if item['source_id'] == raw]
            for item in reference_catalog:
                ids = [item['source_id'], *item['canonical_ids']]
                matched = [ref for ref in ids if (re.fullmatch(pattern, ref) if short else ref == raw)]
                node = item['identity'].get('node_id','')
                node_hint = (short and len(parts)==2 and parts[0]=='PASSAGE::' and
                             bool(parts[1]) and node.endswith(':'+parts[1]))
                if not matched and node_hint:
                    matched = item['canonical_ids']
                if matched:
                    candidates.append({**item, 'matched_ids': matched,
                        'candidate_basis':'node_suffix_hint_missing_identity_digest' if node_hint else 'identifier_match'})
            status = ('candidate_requires_confirmation' if len(candidates) == 1 else
                      'ambiguous' if candidates else 'unresolved') if short else (
                      'exact' if len(candidates) == 1 else 'ambiguous' if candidates else 'unresolved')
            result.append({'reference_id': canonical_sha256([version,raw])[:20],
                'paper_id':paper_id, 'paper_digest':version, 'field_path':path, 'start':match.start(), 'end':end,
                'original_reference':raw, 'status':status, 'delivery_reference_needs_repair':status!='exact',
                'candidates':candidates,
                'runtime_parsing':parsing_record('case_scoped_identifier_v1',raw,
                    candidates[0]['source_id'] if status=='exact' else None,
                    rule='Exact identity or explicit ellipsis prefix/suffix candidates; never inferred confirmation.')})
    return result


def review_reference_state(artifacts, messages, *, limit=10):
    """Expose current mechanical blockers before submission, without confirming them."""
    _, records = delivery_reference_findings(artifacts, messages, complete=False)
    pending = [r for r in records if r['confirmation'] is None]
    rows = []
    for record in pending[:limit]:
        rows.append({'reference_id': record['reference_id'],
                     'original_reference': record['original_input'],
                     **record['navigation']})
    return {'origin': 'runtime_reference_state', 'pending_count': len(pending),
            'items': rows, 'remaining_count': max(0, len(pending)-len(rows)),
            'paper_ids': sorted({r['navigation']['paper_id'] for r in pending}),
            'readback': {'tool': 'read_review_references', 'arguments': {'paper_id': '<paper_id>'}},
            'financial_semantics_verified': False}


def read_source_span(artifacts, source_id, start=0, end=None, anchor=None, max_characters=1000, match_offset=0):
    body = source_body(artifacts, source_id)
    if not 1 <= max_characters <= 6000:
        raise ValueError('source_span_max_characters_must_be_1_to_6000')
    if match_offset < 0 or (match_offset and anchor is None):
        raise ValueError('match_offset_requires_anchor_and_nonnegative_index')
    original = {'source_id':source_id,'start':start,'end':end,'anchor':anchor,'max_characters':max_characters}
    if match_offset:
        original['match_offset'] = match_offset
    if anchor is not None:
        if not anchor or start != 0 or end is not None:
            raise ValueError('use_one_nonempty_anchor_or_explicit_offsets')
        positions = [m.start() for m in re.finditer(re.escape(anchor),body)]
        if match_offset and match_offset >= len(positions):
            raise ValueError('match_offset_out_of_range')
        if len(positions)!=1:
            # Ambiguity is navigation, not a tool failure or source selection.
            # Bound previews to six windows / 6000 source characters per page.
            digest = canonical_sha256(body)
            width = min(max_characters,1000)
            candidates = []
            for index,pos in enumerate(positions[match_offset:match_offset+6],match_offset):
                lo = max(0,pos-min(120,width//3))
                hi = min(len(body),lo+width)
                candidates.append({'match_index':index,'match_start':pos,'match_end':pos+len(anchor),
                    'text':body[lo:hi],'window_span':{'source_digest':digest,'start':lo,'end':hi},
                    'readback':{'tool':'read_review_source_span','arguments':{
                        'source_id':source_id,'start':lo,'max_characters':min(6000,max(1000,max_characters*2))}}})
            next_offset = match_offset+len(candidates)
            return {'status':'multiple_anchor_matches' if positions else 'anchor_not_found',
                'source_id':source_id,'source_digest':digest,'anchor':anchor,
                'total_matches':len(positions),'match_offset':match_offset,'candidates':candidates,
                'selected_match':None,'financial_semantics_verified':False,
                'next_page':{'tool':'read_review_source_span','arguments':{
                    'source_id':source_id,'anchor':anchor,'max_characters':max_characters,'match_offset':next_offset}}
                    if next_offset<len(positions) else None,
                'readback':{'tool':'read_review_source_span','arguments':{'source_id':source_id,'start':0,'max_characters':max_characters}},
                'notice':'window_span covers context only; match_start/end locate the search anchor, not your selected quotation. Submit source_id + your exact quote; runtime locates it. Do not copy window_span as quote_span. No match or financial conclusion has been selected.'}
        start = positions[0]
    if end is None:
        end = min(len(body),start+max_characters)
    digest = canonical_sha256(body)
    text = select_source_span(body, digest, start, end)
    return {'source_id':source_id, 'source_digest':digest, 'text':text,
            'window_span':{'source_digest':digest,'start':start,'end':end},
            'notice':'This is a reading window. Submit source_id + your chosen exact quote; runtime locates it. Only use these offsets as quote_span if selecting this entire text verbatim.',
            'runtime_parsing':parsing_record('exact_source_anchor_v1' if anchor else 'exact_source_span_v1', original,text,
                                            source_digest=digest)}


def confirmed_reference(artifacts, paper_id, reference_id, source_id, reason, messages):
    row = next((r for r in citation_inventory(artifacts,paper_id) if r['reference_id']==reference_id),None)
    if not row:
        raise ValueError('reference_missing_or_stale_read_current_inventory')
    selected = next((c for c in row['candidates'] if c['source_id']==source_id),None)
    if not selected:
        raise ValueError('source_not_a_current_reference_candidate')
    from langchain_core.messages import ToolMessage
    observed = []
    for message in messages:
        if not isinstance(message, ToolMessage) or message.status!='success' or not isinstance(message.artifact,dict):
            continue
        value = message.artifact
        if message.name not in {'read_research_source','read_review_source_span'}:
            continue
        if value.get('source_id') not in [source_id,*selected['canonical_ids']]:
            continue
        body = source_body(artifacts,source_id)
        text = value.get('text','')
        offset = value.get('offset',value.get('window_span',value.get('quote_span',{})).get('start',0))
        if text and body[offset:offset+len(text)]==text:
            observed.append(message.tool_call_id)
    if not observed:
        raise ValueError('candidate_confirmation_requires_actual_current_source_read')
    return {**{k:row[k] for k in ('reference_id','paper_id','paper_digest','field_path','original_reference')},
            'selected_source_id':source_id, 'status':'model_confirmed_from_observed_source',
            'model_reason':reason, 'read_tool_call_ids':observed,
            'delivery_reference_needs_repair':row['delivery_reference_needs_repair'],
            'runtime_parsing':row['runtime_parsing'],
            'notice':'Runtime verified candidate membership and actual read, not the model semantic choice. Original draft unchanged.'}


def delivery_reference_findings(artifacts, messages, *, complete):
    """Attach mechanical delivery defects, distinct from model-authored findings."""
    from langchain_core.messages import ToolMessage
    findings, records, missing = [], [], []
    for paper in artifacts.catalog()['papers']:
        rows = {r['reference_id']:r for r in citation_inventory(artifacts,paper['paper_id'])}
        for ref, row in rows.items():
            if row['status']=='exact':
                continue
            confirmations = [m.artifact for m in messages if isinstance(m,ToolMessage) and
                m.name=='confirm_review_reference' and m.status=='success' and isinstance(m.artifact,dict) and
                m.artifact.get('reference_id')==ref and m.artifact.get('paper_digest')==row['paper_digest']]
            confirmed = confirmations[-1] if confirmations else None
            if confirmed:
                confirmed = confirmed_reference(artifacts,row['paper_id'],ref,confirmed['selected_source_id'],
                                                 confirmed['model_reason'],messages)
            else:
                missing.append({'reference_id':ref,'paper_id':row['paper_id'],'original_reference':row['original_reference']})
            target = confirmed['selected_source_id'] if confirmed else None
            findings.append({'finding_id':'runtime_reference_'+ref, 'paper_id':row['paper_id'], 'claim_ids':[],
                'severity':'material', 'finding_type':'traceability', 'problematic_quote':row['original_reference'],
                'diagnosis':'Runtime delivery-reference check: this original identifier is not directly resolvable. '
                    'This is a traceability defect, not a financial semantic verdict.',
                'requested_change':('Replace this literal reference with confirmed complete source identity '+target
                    if target else 'Resolve the original reference against current authorized sources before delivery; do not guess.'),
                'source_checks':[]})
            records.append({**row['runtime_parsing'],'reference_id':ref,'paper_id':row['paper_id'],
                'navigation': {'paper_id':row['paper_id'], 'paper_digest':row['paper_digest'],
                    'field_path':row['field_path'], 'status':row['status'],
                    'candidate_source_ids':[c['source_id'] for c in row['candidates']]},
                'confirmation':confirmed,'generated_finding_id':'runtime_reference_'+ref,'draft_changed':False})
    if complete and missing:
        import json
        raise ValueError(json.dumps({'unconfirmed_references':missing,
            'remedy':'Read current candidate sources and confirm_review_reference, or submit incomplete with unresolved_data_requests. Runtime records delivery-reference repair findings; do not copy them manually.'}))
    return findings, records
