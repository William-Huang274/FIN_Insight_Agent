"""Plan exact-span units for a frozen release, streaming one document at a time.

No provider, service mutation, source overwrite or generated relevance labels.
The result is a publication plan, not a ready-to-query index.
"""
import argparse
from collections import defaultdict
from hashlib import sha256,file_digest
import json
from pathlib import Path
import sqlite3
import zlib


def plan(index_path,output):
    from retrieval.source_coordinates import origin_bounds
    from retrieval.evidence_scope import source_scopes
    from retrieval.source_structure import TABLE
    from retrieval.fact_period_matching import markdown_tables
    from retrieval.semantic_unit_catalog import build
    from retrieval import semantic_units,business_scope_attributes,table_captions,evidence_scope
    index_path=index_path.resolve();raw=index_path.read_bytes();index=json.loads(raw)
    input_digest=sha256(raw).hexdigest();del raw
    navigation=index_path.parent/'navigation.sqlite'
    with navigation.open('rb') as stream:
        if file_digest(stream,'sha256').hexdigest()!=index['navigation_index']['sha256']:
            raise ValueError('unit_plan_navigation_hash_mismatch')
    grouped=defaultdict(list)
    for record in index['records']:grouped[record['document_id']].append(record)
    output.mkdir(parents=True,exist_ok=False)
    def rows():
        with sqlite3.connect(navigation.as_uri()+'?mode=ro',uri=True) as db:
            for ordinal,(document,records) in enumerate(grouped.items(),1):
                frames=defaultdict(list)
                for record in records:
                    item=db.execute('SELECT payload FROM nodes WHERE node_id=?',(record['node_id'],)).fetchone()
                    if not item:raise ValueError('unit_plan_original_missing')
                    raw=zlib.decompress(item[0])
                    if sha256(raw).hexdigest()!=record['navigation_sha256']:
                        raise ValueError('unit_plan_navigation_row_mismatch')
                    row=json.loads(raw);space,lo,hi=origin_bounds(row['original_source'])
                    if row['node_id']!=record['node_id'] or row['parent_document_id']!=document:
                        raise ValueError('unit_plan_row_identity_mismatch')
                    if len(row['content'])!=hi-lo or sha256(row['content'].encode()).hexdigest()!=record['content_sha256']:
                        raise ValueError('unit_plan_original_mismatch')
                    frames[space].append((lo,hi,row,record['vector_index']))
                for space,items in frames.items():
                    items.sort(key=lambda item:(item[0],item[1],item[2]['node_id']))
                    segments=[]
                    for lo,hi,row,_ in items:
                        text=row['content']
                        if segments and lo<=segments[-1][1]:
                            a,b,old=segments[-1];overlap=min(b,hi)-lo
                            if old[lo-a:lo-a+overlap]!=text[:overlap]:
                                raise ValueError('unit_plan_original_overlap_conflict')
                            if hi>b:segments[-1]=(a,hi,old+text[b-lo:])
                        else:segments.append((lo,hi,text))
                    scopes=[];tables=[]
                    for lo,hi,text in segments:
                        scopes.extend({**s,'source_char_start':lo+s['source_char_start'],
                            'source_char_end':lo+s['source_char_end']} for s in source_scopes(text))
                        for m in TABLE.finditer(text):
                            if '[TABLE:' in m[1]:continue
                            tables.append({'source_char_start':lo+m.start(),'source_char_end':lo+m.end(),
                                'content_sha256':sha256(m[0].encode()).hexdigest()})
                        tables.extend({**t,'source_char_start':lo+t['source_char_start'],
                            'source_char_end':lo+t['source_char_end']} for t in markdown_tables(text))
                    for lo,hi,row,position in items:
                        structure={'status':'verified_original_node_coordinates' if space else 'verified_original_coordinates',
                            'coordinate_space':{'original_node_id':space},
                            'evidence_scopes':[s for s in scopes if s['source_char_start']<hi and s['source_char_end']>lo],
                            'tables':[t for t in tables if t['source_char_start']<hi and t['source_char_end']>lo]}
                        yield {**row,'source_structure':structure},position
                if ordinal%100==0:print(json.dumps({'documents_planned':ordinal,'total':len(grouped)}),flush=True)
    summary=build(output/'units.sqlite',rows())
    summary.update(documents=len(grouped),index_sha256=input_digest,
        original_index_digest=__import__('sec_agent.research_foundation.organization_index_release',
            fromlist=['canonical_digest']).canonical_digest(index),
        code_sha256={Path(m.__file__).name:sha256(Path(m.__file__).read_bytes()).hexdigest()
            for m in (semantic_units,business_scope_attributes,table_captions,evidence_scope)},
        purpose='dry_publication_plan_no_paid_calls_or_quality_claim',publication_state='vectors_not_prepared')
    (output/'plan.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(plan(args.index,args.output),ensure_ascii=False),flush=True)
