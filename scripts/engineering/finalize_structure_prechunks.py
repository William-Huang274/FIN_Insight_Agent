"""Classify diagnostic spans with the existing structural-only contract.

Keeps whitespace and layout markers in the ledger, out of prose candidates.
No vectors, rankings, live publication, or financial inference.
"""
import argparse
from collections import Counter
import gzip
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from retrieval.structural_surface import structural_only


def classify(document):
    records=[];groups=[];pending=[];pending_bytes=0;pending_path=None
    def flush():
        nonlocal pending,pending_bytes,pending_path
        if pending:
            groups.append({'atomic_record_indices':pending,'body_bytes_with_separators':pending_bytes,
                           'heading_path':list(pending_path),'hierarchy_status':'parser_hypothesis_not_independently_verified',
                           'oversize_complete_sentence':pending_bytes>10000})
        pending=[];pending_bytes=0;pending_path=None
    for c in document['pre_chunks']:
        b=document['blocks'][c['block']]
        text=b['text'] if c['kind']=='table' else b['text'][c['start']:c['end']]
        role='retained_structure' if structural_only(text) else 'table_candidate' if c['kind']=='table' else 'prose_candidate'
        records.append({**c,'role':role,'text_sha256':sha256(text.encode()).hexdigest(),
                        'heading_path_status':'parser_hypothesis_not_independently_verified',
                        'financial_semantics_inferred':False})
        if c['kind']=='table':flush();continue
        if role=='retained_structure':continue
        path=tuple(c['heading_path']);size=len(text.encode())
        if pending and (path!=pending_path or pending_bytes+1+size>10000):flush()
        if pending:pending_bytes+=1
        pending.append(len(records)-1);pending_bytes+=size;pending_path=path
    flush()
    return {'records':records,'headings':document['outline'],
            'counts':dict(Counter(r['role'] for r in records)),
            'prose_groups':groups,'prose_group_count':len(groups),
            'grouping_policy':'complete_sentence_pieces_within_heading_path_and_table_boundaries_10000_utf8_bytes',
            'published':False,'embedding_generated':False}


def finalize(directory,output):
    output.mkdir(parents=True,exist_ok=False);counts=Counter();rows=[];group_count=0
    for path in sorted((directory/'receipts').glob('*.json')):
        receipt=json.loads(path.read_bytes())
        if receipt['status']!='inspected':continue
        artifact=directory/'documents'/(receipt['id']+'.json.gz');raw=artifact.read_bytes()
        if sha256(raw).hexdigest()!=receipt['artifact_sha256']:raise ValueError('source_audit_changed')
        document=json.loads(gzip.decompress(raw));result=classify(document)
        result.update(source_sha256=receipt['id'],source_artifact_sha256=receipt['artifact_sha256'])
        with gzip.open(output/(receipt['id']+'.json.gz'),'wt',encoding='utf8',compresslevel=3) as out:
            json.dump(result,out,ensure_ascii=False)
        counts.update(result['counts']);group_count+=result['prose_group_count']
        rows.append({'id':receipt['id'],'counts':result['counts'],'prose_groups':result['prose_group_count']})
    summary={'documents':len(rows),'counts':dict(counts),'rows':rows,
             'prose_groups':group_count,
             'input_execution_identity':json.loads((directory/'execution-identity.json').read_bytes()),
             'implementation_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
             'structural_surface_sha256':sha256((ROOT/'src/retrieval/structural_surface.py').read_bytes()).hexdigest(),
             'published':False,'provider_calls':0}
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False),encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'rows','input_execution_identity'}},ensure_ascii=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();finalize(a.directory,a.output)
