"""Build an isolated unit overlay from sealed plans and completed paid receipts.

No provider calls. This is a scoped diagnostic publication, not activation of a
Java preparation or modification of an existing organization release.
"""
import argparse
from contextlib import closing
from hashlib import sha256,file_digest
import json
from pathlib import Path
import sqlite3
import zlib
import numpy as np


def build(index_path,catalog,scope_path,receipt_paths,output):
    from retrieval.semantic_unit_catalog import select_parents
    from retrieval.semantic_unit_index import build as publish,validate
    from retrieval.unit_embedding_receipts import UnitEmbeddingReceiptReader
    from sec_agent.research_foundation.organization_index_release import canonical_digest
    index_path=Path(index_path).resolve();raw=index_path.read_bytes();index=json.loads(raw)
    scope=json.loads(Path(scope_path).read_bytes())
    if scope['snapshot_digest']!=canonical_digest(index):raise ValueError('unit_overlay_scope_snapshot_mismatch')
    selected=set(scope['parent_node_ids']);parents=[r for r in index['records'] if r['node_id'] in selected]
    if {r['node_id'] for r in parents}!=selected:raise ValueError('unit_overlay_parent_missing')
    for name,expected in [('navigation.sqlite',index['navigation_index']['sha256']),('vectors.npy',index['matrix_sha256'])]:
        with (index_path.parent/name).open('rb') as stream:
            if file_digest(stream,'sha256').hexdigest()!=expected:raise ValueError('unit_overlay_original_file_changed')
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    subset=select_parents(catalog,output/'plan.sqlite',selected)
    reader=UnitEmbeddingReceiptReader(receipt_paths)
    try:
        matrix=np.load(index_path.parent/'vectors.npy',mmap_mode='r',allow_pickle=False)
        with closing(sqlite3.connect((index_path.parent/'navigation.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
            def original(record):
                row=db.execute('SELECT payload FROM nodes WHERE node_id=?',(record['node_id'],)).fetchone()
                if not row:raise ValueError('unit_overlay_original_missing')
                raw=zlib.decompress(row[0])
                if sha256(raw).hexdigest()!=record['navigation_sha256']:raise ValueError('unit_overlay_original_row_changed')
                return json.loads(raw)
            descriptor=publish(output,output/'plan.sqlite',parents,matrix,reader,
                model=index['model'],original_reader=original)
        validate(output,descriptor,parents,index['model'])
        result={'status':'isolated_overlay_validated','index_file_sha256':sha256(raw).hexdigest(),
            'snapshot_digest':scope['snapshot_digest'],'parent_scope':sorted(selected),'catalog':subset,
            'descriptor':descriptor,'completed_receipt_batches':reader.completed_batches,'provider_calls':0,
            'qualification':'declared_scope_only_not_full_corpus_or_live_service_acceptance'}
        (output/'overlay.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
        return {k:v for k,v in result.items() if k!='parent_scope'}
    finally:reader.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('index','catalog','scope','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--receipts',type=Path,action='append',required=True)
    args=parser.parse_args()
    print(json.dumps(build(args.index,args.catalog,args.scope,args.receipts,args.output),ensure_ascii=False))
