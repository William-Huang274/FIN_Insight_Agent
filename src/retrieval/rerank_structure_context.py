"""Verified fact and same-table context for independent candidate scoring."""
from hashlib import sha256
import json


def structure_context_text(row):
    structure=row.get('source_structure',{})
    completion=row.get('rerank_table_completion')
    if completion is None:return ''
    from .source_coordinates import VERIFIED, verified_bounds
    if structure.get('status') not in VERIFIED:return ''
    _,start,end=verified_bounds(row);origin=row['original_source']
    texts=[]
    for item in completion.get('contexts',[]):
        lo,hi=item['source_char_start'],item['source_char_end'];text=item['text']
        if (item['document_id']!=row['parent_document_id'] or item['source_digest']!=origin['source_digest']
                or item.get('original_node_id')!=origin.get('original_node_id')
                or type(lo) is not int or type(hi) is not int or not 0<=lo<hi or hi-lo!=len(text)
                or sha256(text.encode()).hexdigest()!=item['content_sha256']):
            raise ValueError('rerank_table_context_identity_mismatch')
        texts.append(f'[{item["role"]}, original node {item.get("original_node_id") or "document"}, interval {lo}:{hi}]\n{text}')
    periods=[]
    for item in structure.get('period_evidence',[]):
        lo,hi=item['source_char_start'],item['source_char_end']
        if not lo<end or not start<hi:raise ValueError('rerank_period_outside_candidate')
        if row.get('scoring_view') and not any(s['source_char_start']<hi and s['source_char_end']>lo for s in row['scoring_view']['spans']):
            continue
        record={k:item[k] for k in ('concept','role','period','entity','entity_scheme') if k in item}
        # Preserve all distinct bindings, without repeating a full table header
        # for every numeric cell. The source body remains the numeric evidence.
        if record not in periods:periods.append(record)
    metadata={'fact_period_bindings':periods,'table_context_status':completion.get('status'),
              'unresolved':completion.get('unresolved',[])}
    text=json.dumps(metadata,ensure_ascii=False,sort_keys=True)+'\n'+'\n\n'.join(texts)
    if len(text.encode())>16384:raise ValueError('rerank_structure_context_outside_budget')
    return ('Verified original structural context for THIS candidate only. '
        'A neighboring header or footnote is context, not independent evidence of an answer. '
        'Keep each fact entity, period and unit separate; unresolved bindings remain unknown:\n'+text)
