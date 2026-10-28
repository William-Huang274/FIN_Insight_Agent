"""Original-coordinate retrieval units; not rewritten financial evidence.

Publication owns this overlay. Query-time scoring must not split text and then
reuse a vector of a different input. Every unit covers an exact original span;
the original node remains the citation/readback identity.
"""
from hashlib import sha256
import json
import re

FORMAT='original-retrieval-units.v2'
PROSE_TARGET=1800


def _digest(value):
    return sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def split_original(row):
    """Partition without dropping characters or joining separate tables.

    Table boundaries come from verified original geometry or original explicit
    delimiters. Scope boundaries prevent cross-table keyword co-occurrence.
    Prose uses paragraph boundaries, never model-generated summaries. A long
    paragraph remains whole instead of silently clipping text to a budget.
    """
    from .source_coordinates import VERIFIED, verified_bounds
    body=row['content']
    if sha256(body.encode()).hexdigest()!=row['content_sha256']:
        raise ValueError('semantic_unit_original_body_mismatch')
    structure=row.get('source_structure',{})
    if structure.get('status') not in VERIFIED:
        raise ValueError('semantic_units_require_verified_original_coordinates')
    space,start,end=verified_bounds(row)
    if len(body)!=end-start:raise ValueError('semantic_unit_coordinate_length_mismatch')
    tables=[(t['source_char_start'],t['source_char_end']) for t in structure.get('tables',[])]
    tables += [(d['table']['source_char_start'],d['table']['source_char_end'])
               for d in structure.get('table_dependencies',[])]
    # Exact original marker locations are navigation geometry, not guessed
    # table subjects or column ownership. An incomplete marker stays partial.
    for m in re.finditer(r'\[TABLE:[^\n]*?\].*?\[/TABLE\]',body,re.S):
        if '[TABLE:' not in m[0][7:]:tables.append((start+m.start(),start+m.end()))
    tables=sorted(set(tables))
    regions=structure.get('evidence_scopes',[])
    bounds={start,end}
    for lo,hi in tables+[(s['source_char_start'],s['source_char_end']) for s in regions]:
        if type(lo) is not int or type(hi) is not int or not 0<=lo<hi:
            raise ValueError('semantic_unit_invalid_structure_interval')
        if lo<end and hi>start:bounds.update((max(start,lo),min(end,hi)))
    intervals=[]
    for lo,hi in zip(sorted(bounds),sorted(bounds)[1:]):
        roles=[(a,b) for a,b in tables if a<hi and b>lo]
        if roles:
            intervals.append((lo,hi,'table',roles));continue
        # Keep paragraphs within each single scope interval. Paragraph grouping
        # amortizes tiny lines, but never crosses a verified table boundary.
        segment=body[lo-start:hi-start];cursor=lo
        for m in re.finditer(r'\n[ \t]*\n+',segment):
            stop=lo+m.end()
            if stop-cursor>=PROSE_TARGET:
                intervals.append((cursor,stop,'prose',[]));cursor=stop
        if cursor<hi:intervals.append((cursor,hi,'prose',[]))
    output=[]
    for lo,hi,role,tables_for_unit in intervals:
        text=body[lo-start:hi-start]
        scopes=[s for s in regions if s['source_char_start']<=lo and s['source_char_end']>=hi]
        identity={'format':FORMAT,'parent_node_id':row['node_id'],
            'parent_document_id':row['parent_document_id'],'source_digest':row['original_source']['source_digest'],
            'original_node_id':space,'source_char_start':lo,'source_char_end':hi,
            'content_sha256':sha256(text.encode()).hexdigest()}
        from .original_input_context import document_context,POLICY as CONTEXT_POLICY
        context=document_context(row)
        identity['context_policy']=CONTEXT_POLICY
        model_input=context+'\n'+text
        output.append({**identity,'unit_id':'UNIT::'+_digest(identity),'role':role,
            'content':text,'embedding_context':context,'embedding_input_sha256':sha256(model_input.encode()).hexdigest(),
            'parent_content_sha256':row['content_sha256'],
            'evidence_scopes':scopes,'evidence_scope_complete':bool(scopes),
            'source_interval':[lo,hi], 'table_intervals':tables_for_unit,
            'reusable_parent_vector':lo==start and hi==end and
                sha256(model_input.encode()).hexdigest()==row.get('embedding_input_sha256'),
            'retrievable':bool(text.strip()),
            'citation_semantics':'parent_original_node_and_exact_span_no_new_source'})
    validate_partition(row,output)
    return output


def validate_partition(row,units):
    from .source_coordinates import verified_bounds
    space,start,end=verified_bounds(row);cursor=start
    for unit in units:
        lo,hi=unit['source_char_start'],unit['source_char_end']
        if (unit['parent_node_id']!=row['node_id'] or unit['parent_document_id']!=row['parent_document_id']
                or unit['parent_content_sha256']!=row['content_sha256'] or unit['original_node_id']!=space
                or unit['source_digest']!=row['original_source']['source_digest']
                or type(lo) is not int or type(hi) is not int or lo!=cursor or not lo<hi<=end):
            raise ValueError('semantic_unit_partition_identity_mismatch')
        text=row['content'][lo-start:hi-start]
        if unit['content']!=text or sha256(text.encode()).hexdigest()!=unit['content_sha256']:
            raise ValueError('semantic_unit_partition_content_mismatch')
        if sha256((unit['embedding_context']+'\n'+text).encode()).hexdigest()!=unit['embedding_input_sha256']:
            raise ValueError('semantic_unit_embedding_input_mismatch')
        cursor=hi
    if cursor!=end:raise ValueError('semantic_unit_partition_incomplete')
