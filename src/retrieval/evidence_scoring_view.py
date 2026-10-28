"""Exact original intervals for scoring a mixed chunk under a business scope.

The original body, embedding and citation identity are unchanged. A matched
table does not make conflicting tables in the same chunk eligible evidence.
"""
from hashlib import sha256
from .evidence_scope import scope_intervals, scoring_scope_text

FORMAT = 'original-scope-scoring-view.v1'


def attach_scoring_view(row, wanted):
    structure=row.get('source_structure',{})
    regions=structure.get('evidence_scopes',[])
    from .source_coordinates import VERIFIED, verified_bounds
    if not wanted or structure.get('status') not in VERIFIED or not regions:
        return dict(row)
    scoring_scope_text(row)  # Validate coordinates, attributes and proof shapes.
    _,start,end=verified_bounds(row)
    if len(row['content'])!=end-start or sha256(row['content'].encode()).hexdigest()!=row['content_sha256']:
        raise ValueError('scope_view_original_mismatch')
    eligible=[];excluded=[]
    for interval in scope_intervals(start,end,regions,wanted):
        lo,hi,state=interval['source_char_start'],interval['source_char_end'],interval['state']
        keep=state=='match' or (state=='unknown' and wanted.get('unknown_policy')=='retain')
        target=eligible if keep else excluded
        if target and target[-1]['source_char_end']==lo and target[-1]['state']==state:
            target[-1]['source_char_end']=hi
        else:
            target.append({'source_char_start':lo,'source_char_end':hi,'state':state})
    if not eligible:
        raise ValueError('scope_view_has_no_eligible_original_interval')
    spans=[]
    for span in eligible:
        text=row['content'][span['source_char_start']-start:span['source_char_end']-start]
        spans.append({**span,'content_sha256':sha256(text.encode()).hexdigest()})
    return {**row,'scoring_view':{'format':FORMAT,'original_content_sha256':row['content_sha256'],
        'original_node_id':row['original_source'].get('original_node_id'),
        'constraints':wanted,'spans':spans,'excluded_intervals':excluded,
        'semantics':'query_eligible_original_intervals_not_new_citation_or_authorization'}}


def scoring_body(row):
    view=row.get('scoring_view')
    if view is None:return row['content']
    if view.get('format')!=FORMAT or view.get('original_content_sha256')!=row['content_sha256']:
        raise ValueError('scope_view_identity_mismatch')
    from .source_coordinates import verified_bounds
    space,start,end=verified_bounds(row)
    if view.get('original_node_id')!=space:raise ValueError('scope_view_coordinate_space_mismatch')
    previous=start;pieces=[]
    for span in view['spans']:
        lo,hi=span['source_char_start'],span['source_char_end']
        if type(lo) is not int or type(hi) is not int or not previous<=lo<hi<=end:
            raise ValueError('scope_view_invalid_interval')
        text=row['content'][lo-start:hi-start]
        if sha256(text.encode()).hexdigest()!=span['content_sha256']:
            raise ValueError('scope_view_span_mismatch')
        pieces.append(f'[Original node {space or "document"}, interval {lo}:{hi}; scope {span["state"]}]\n{text}')
        previous=hi
    if not pieces:raise ValueError('scope_view_empty')
    return '\n\n'.join(pieces)
