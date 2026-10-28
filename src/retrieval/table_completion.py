"""Post-selection exact context; never changes top-K ranks or source bodies."""
from hashlib import sha256
from .source_coordinates import VERIFIED, origin_bounds

POLICY = 'table-completion.v1'


def read_span(anchor, span, locations, load_node):
    """Assemble a bounded exact interval from eligible, verified chunk bodies."""
    lo, hi = span['source_char_start'], span['source_char_end']
    position, pieces, readbacks = lo, [], []
    for start, end, node in sorted(locations):
        if end <= position or start >= hi:continue
        if start > position:return None
        row = load_node(node)
        original = row['original_source']
        if (row['parent_document_id'] != anchor['parent_document_id']
                or original['source_digest'] != anchor['original_source']['source_digest']
                or origin_bounds(original) != (origin_bounds(anchor['original_source'])[0],start,end)
                or len(row['content']) != end-start):
            raise ValueError('table_completion_chunk_identity_mismatch')
        stop = min(end,hi)
        pieces.append(row['content'][position-start:stop-start])
        readbacks.append({'source_space':'organization','operation':'read',
            'document_id':row['parent_document_id'],'node_id':node,
            'character_offset':position-start,'max_characters':max(2000,stop-position)})
        position = stop
        if position == hi:break
    if position < hi:return None
    return {'text':''.join(pieces),'document_id':anchor['parent_document_id'],
        'source_id':anchor['original_source']['source_id'],
        'source_digest':anchor['original_source']['source_digest'],
        'original_node_id':origin_bounds(anchor['original_source'])[0],
        'source_char_start':lo,'source_char_end':hi,'readbacks':readbacks}


def complete_tables(rows, load_context, *, top_k=10, maximum_spans=24, maximum_characters=12000,
                    independent_candidates=False):
    """Loader must enforce current eligible source scope and exact coordinates.

    Existing returned rows count as coverage only within the same document and
    original source digest. Missing/ambiguous/budget-limited dependencies remain
    explicit. Supplemental context is NOT a scored or reranked candidate.
    """
    result = [dict(row) for row in rows]
    used, characters = {}, 0
    all_used={}
    for row in result[:top_k]:
        # Every reranker document gets the same bounded context opportunity.
        # Earlier candidates must not spend later candidates' context budget.
        # The caller separately limits the aggregate provider input bytes.
        if independent_candidates:used,characters={},0
        origin = row.get('original_source', {})
        structure = row.get('source_structure', {})
        if structure.get('status') not in VERIFIED:
            row['table_completion'] = {'policy':POLICY,'status':'unverified_structure','contexts':[]}
            continue
        contexts, missing, required_count = [], [], 0
        for dependency in structure.get('table_dependencies', []):
            if row.get('scoring_view'):
                table=dependency['table']
                if not any(s['source_char_start']<table['source_char_end'] and s['source_char_end']>table['source_char_start']
                           for s in row['scoring_view']['spans']):
                    continue
            missing.extend(dependency['unresolved'])
            for span in dependency['required']:
                required_count += 1
                lo, hi = span['source_char_start'], span['source_char_end']
                key = (row['parent_document_id'], origin.get('source_digest'),
                       origin_bounds(origin)[0], lo, hi, span['content_sha256'])
                if type(lo) is not int or type(hi) is not int or not 0 <= lo < hi:
                    raise ValueError('table_completion_invalid_interval')
                covered = lo
                intervals = sorted(origin_bounds(r['original_source'])[1:]
                    for r in ([row] if independent_candidates else result[:top_k]) if r['parent_document_id']==key[0]
                    and r.get('original_source',{}).get('source_digest')==key[1]
                    and origin_bounds(r['original_source'])[0]==origin_bounds(origin)[0])
                for start, end in intervals:
                    if start <= covered: covered = max(covered,end)
                if covered >= hi:
                    continue
                if key not in used:
                    if len(used)>=maximum_spans or characters+hi-lo>maximum_characters:
                        missing.append('context_budget_exceeded:'+span['role']);continue
                    loaded = load_context(row, span)
                    if loaded is None:
                        missing.append('context_unavailable:'+span['role']);continue
                    text = loaded['text']
                    if len(text)!=hi-lo or sha256(text.encode()).hexdigest()!=span['content_sha256']:
                        raise ValueError('table_completion_original_mismatch')
                    if (loaded['source_digest']!=key[1] or loaded['document_id']!=key[0]
                            or loaded.get('original_node_id')!=origin_bounds(origin)[0]
                            or loaded['source_char_start']!=lo or loaded['source_char_end']!=hi):
                        raise ValueError('table_completion_source_mismatch')
                    used[key] = loaded;characters += len(text);all_used[key]=loaded
                contexts.append({**used[key], 'role':span['role'], 'content_sha256':span['content_sha256']})
        row['table_completion'] = {'policy':POLICY,
            'status':'incomplete' if missing else 'context_complete' if required_count else 'not_assessed',
            'contexts':contexts,'unresolved':sorted(set(missing)),
            'semantics':'structural_context_only_not_answer_validation'}
    return result, {'policy':POLICY,'top_k_unchanged':True,'unique_supplemental_spans':len(all_used),
                    'supplemental_characters':sum(len(v['text']) for v in all_used.values()),'maximum_spans':maximum_spans,
                    'maximum_characters':maximum_characters,
                    'budget_scope':'per_candidate' if independent_candidates else 'result_page',
                    'coverage_mode':'individual_candidate' if independent_candidates else 'result_page'}
