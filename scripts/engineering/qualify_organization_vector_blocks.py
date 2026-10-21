"""Offline numerical replay over every exported source matrix; no ACL/recall claim."""
import argparse
from hashlib import file_digest
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from sec_agent.research_foundation.organization_vector_math import cosine_scores, unit_vectors


def digest(path):
    with path.open('rb') as handle:
        return file_digest(handle,'sha256').hexdigest()


def qualify(intake, query_index, query_index_sha256, output):
    intake,query_index,output=map(lambda p:Path(p).resolve(),(intake,query_index,output))
    if output==intake or output.is_relative_to(intake) or output.is_relative_to(query_index.parent):
        raise ValueError('output_must_not_modify_source_directory')
    output.mkdir(parents=True,exist_ok=False)
    result={'status':'incomplete','sources':[],'provider_calls':0,
            'scope':'per-source offline exact cosine arithmetic only; no authorization, global ranking, recall or concurrency claim'}
    def save():
        (output/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    started=perf_counter()
    save()
    try:
        manifest_path=intake/'result.json'
        initial=digest(manifest_path)
        manifest=json.loads(manifest_path.read_text(encoding='utf8'))
        if manifest['status']!='verified' or digest(query_index)!=query_index_sha256:
            raise ValueError('unverified_replay_input')
        index=json.loads(query_index.read_text(encoding='utf8'))
        key=sorted(index['queries'])[0]
        query=np.asarray(index['queries'][key],dtype=np.float32)
        if query.shape!=(1024,) or not unit_vectors(query.reshape(1,-1)):
            raise ValueError('query_vector_invalid')
        result.update(intake_sha256=initial,query_index_sha256=query_index_sha256,query_sha256=key)
        for source in manifest['sources']:
            if source['status']!='verified':raise ValueError('source_not_verified')
            folder=intake/source['directory']
            path=folder/'vectors.npy'
            mapping_path=folder/'vector-map.json'
            if digest(path)!=source['files']['vectors.npy'] or digest(mapping_path)!=source['files']['vector-map.json']:
                raise ValueError('source_vector_input_changed')
            mapping=json.loads(mapping_path.read_text(encoding='utf8'))
            matrix=np.load(path,mmap_mode='r',allow_pickle=False)
            if matrix.dtype!=np.float32 or matrix.shape!=(len(mapping),1024):
                raise ValueError('source_vector_shape_mismatch')
            positions=[r['vector_index'] for r in mapping]
            if sorted(positions)!=list(range(len(matrix))):raise ValueError('source_vector_positions_invalid')
            if not unit_vectors(matrix):raise ValueError('source_vector_not_normalized')
            # Reference expression needs only one source; do not copy the corpus.
            expected=(matrix @ query)[positions]
            actual=cosine_scores(matrix,positions,query)
            np.testing.assert_allclose(actual,expected,rtol=1e-5,atol=1e-7)
            rank=lambda scores:sorted(range(len(scores)),key=lambda i:(-float(scores[i]),mapping[i]['chunk_id']))[:24]
            if rank(actual)!=rank(expected):raise ValueError('per_source_top24_changed')
            result['sources'].append({'source_id':source['source_id'],'vectors':len(matrix),
                'max_score_error':float(np.max(np.abs(actual-expected))),'top24_equal':True})
            del matrix
            if digest(path)!=source['files']['vectors.npy']:raise ValueError('source_vectors_changed_during_replay')
            if len(result['sources'])%50==0:save()
        if digest(manifest_path)!=initial or digest(query_index)!=query_index_sha256:
            raise ValueError('replay_input_changed')
        result.update(status='passed',vectors=sum(r['vectors'] for r in result['sources']))
    except BaseException as exc:
        result.update(status='failed',error_type=type(exc).__name__,error=str(exc))
        raise
    finally:
        result['wall_seconds']=perf_counter()-started
        save()
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--intake',required=True,type=Path)
    parser.add_argument('--query-index',required=True,type=Path)
    parser.add_argument('--query-index-sha256',required=True)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    result=qualify(args.intake,args.query_index,args.query_index_sha256,args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},ensure_ascii=False))


if __name__=='__main__':main()
