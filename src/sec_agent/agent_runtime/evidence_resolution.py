"""Deterministic citation navigation and literal selection, never financial inference."""
import re

from .research_graph_contracts import canonical_sha256


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


def resolve_quote(body, quote):
    """Only restore a unique contiguous table block with identical nonempty cells.

    No number/sign/unit/word changes, fuzzy matching or skipped rows. Empty cell
    layout may change; this does NOT establish column/period comparability.
    """
    if quote and quote in body:
        return quote, None
    tokens = list(re.finditer(r'\w+|[^\w\s]',body))
    requested_tokens = re.findall(r'\w+|[^\w\s]',quote)
    matches = [i for i in range(len(tokens)-len(requested_tokens)+1) if requested_tokens and
               [t.group() for t in tokens[i:i+len(requested_tokens)]]==requested_tokens]
    if len(matches)==1:
        start = tokens[matches[0]].start()
        end = tokens[matches[0]+len(requested_tokens)-1].end()
        return body[start:end], parsing_record('unique_layout_whitespace_v1',quote,body[start:end],
                                               source_digest=canonical_sha256(body),start=start,end=end)
    requested = quote.strip().splitlines()
    lines = body.splitlines(keepends=True)
    if not requested or not all('|' in line for line in requested):
        return quote, None
    def cells(line):
        return tuple(cell.strip() for cell in line.strip().split('|') if cell.strip())
    target = [cells(line) for line in requested]
    # Require text row labels and numeric content; never repair bare values.
    if (any(not row or not re.search(r'[^\W\d_]',row[0]) for row in target)
            or not any(re.search(r'\d',cell) for row in target for cell in row[1:])):
        return quote, None
    matches = [i for i in range(len(lines) - len(target) + 1)
               if all('|' in lines[i+j] and cells(lines[i+j]) == row for j, row in enumerate(target))]
    if len(matches) != 1:
        return quote, None
    start = sum(len(line) for line in lines[:matches[0]])
    exact = ''.join(lines[matches[0]:matches[0]+len(target)]).rstrip('\r\n')
    return exact, parsing_record('unique_table_nonempty_cells_v1', quote, exact,
        source_digest=canonical_sha256(body), start=start, end=start+len(exact),
        notice='Original table layout restored; column meaning must still be checked against original headings.')


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
            for item in catalog:
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


def read_source_span(artifacts, source_id, start=0, end=None, anchor=None, max_characters=1000):
    body = source_body(artifacts, source_id)
    if not 1 <= max_characters <= 6000:
        raise ValueError('source_span_max_characters_must_be_1_to_6000')
    original = {'source_id':source_id,'start':start,'end':end,'anchor':anchor,'max_characters':max_characters}
    if anchor is not None:
        if not anchor or start != 0 or end is not None:
            raise ValueError('use_one_nonempty_anchor_or_explicit_offsets')
        positions = [m.start() for m in re.finditer(re.escape(anchor),body)]
        if len(positions)!=1:
            raise ValueError('source_anchor_not_unique:positions=' + str(positions[:12]))
        start = positions[0]
    if end is None:
        end = min(len(body),start+max_characters)
    digest = canonical_sha256(body)
    text = select_source_span(body, digest, start, end)
    return {'source_id':source_id, 'source_digest':digest, 'text':text,
            'quote_span':{'source_digest':digest,'start':start,'end':end},
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
        offset = value.get('offset',value.get('quote_span',{}).get('start',0))
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
                'severity':'material', 'problematic_quote':row['original_reference'],
                'diagnosis':'Runtime delivery-reference check: this original identifier is not directly resolvable. '
                    'This is a traceability defect, not a financial semantic verdict.',
                'requested_change':('Replace this literal reference with confirmed complete source identity '+target
                    if target else 'Resolve the original reference against current authorized sources before delivery; do not guess.'),
                'source_checks':[]})
            records.append({**row['runtime_parsing'],'reference_id':ref,'paper_id':row['paper_id'],
                'confirmation':confirmed,'generated_finding_id':'runtime_reference_'+ref,'draft_changed':False})
    if complete and missing:
        import json
        raise ValueError(json.dumps({'unconfirmed_references':missing,
            'remedy':'Read current candidate sources and confirm_review_reference, or submit incomplete with unresolved_data_requests. Runtime records delivery-reference repair findings; do not copy them manually.'}))
    return findings, records
