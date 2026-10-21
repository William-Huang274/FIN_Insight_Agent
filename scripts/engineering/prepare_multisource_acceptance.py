"""Prepare exact historical vectors and a new organization release, without API calls.

All generated data stays in an explicit external case directory. Library and
vector inputs are read-only. This is an ACL case, not a financial recall gold.
"""
import argparse
from hashlib import sha256, file_digest
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import uuid4

import numpy as np


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def write(path, value):
    with path.open('x', encoding='utf8') as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False)


def excerpts(args):
    from retrieval.library_vectors import ready_index
    output = args.case / 'excerpts'
    output.mkdir(parents=True, exist_ok=False)
    original = args.deployment / 'public-excerpt'
    previous = read(original / 'provenance.json')
    with args.library.open('rb') as stream:
        library_sha = file_digest(stream, 'sha256').hexdigest()
    assert library_sha == previous['source_library_sha256']
    manifest, matrix, mapping = ready_index(args.vectors, library_sha)
    assert manifest['embedding_model'] == previous['model']
    chunk_id = 'CHUNK::d8b6e528aaf706619b608442b6b6a153db65871a'
    with sqlite3.connect(args.library.resolve().as_uri() + '?mode=ro', uri=True) as db:
        row = db.execute('SELECT source_id,context,body FROM retrieval_chunks WHERE id=?', (chunk_id,)).fetchone()
    assert row is not None
    text = row[1] + '\n' + row[2]
    mapped = next(item for item in mapping if item['id'] == chunk_id)
    assert mapped['source_id'] == row[0]
    # Windows text-mode writes translate LF to CRLF; embedding identity is bytes.
    (output / 'AMD-historical-disclosure-excerpt.txt').write_bytes(text.encode('utf8'))
    np.save(output / 'AMD.npy', matrix[mapped['vector_index']], allow_pickle=False)
    shutil.copyfile(original / 'NVIDIA-historical-disclosure-excerpt.txt', output / 'NVIDIA-historical-disclosure-excerpt.txt')
    shutil.copyfile(original / 'document-vector.npy', output / 'NVIDIA.npy')
    shutil.copyfile(original / 'query-vector.json', output / 'query-vector.json')
    nvidia = (output / 'NVIDIA-historical-disclosure-excerpt.txt').read_bytes().decode('utf8')
    assert sha256(nvidia.encode()).hexdigest() == previous['content_sha256']
    write(output / 'manifest.json', {
        'model': previous['model'], 'source_library_sha256': library_sha,
        'original_query_request_id': previous['original_query_request_id'],
        'provider_calls': 0, 'financial_quality': 'not_assessed',
        'purpose': 'Two exact public excerpts in independently authorized spaces; no ranking quality claim',
        'sources': [
            {'name': 'NVIDIA', 'file': 'NVIDIA-historical-disclosure-excerpt.txt', 'vector': 'NVIDIA.npy',
             'content_sha256': previous['content_sha256'], 'source_id': previous['source_id'], 'chunk_id': previous['chunk_id']},
            {'name': 'AMD', 'file': 'AMD-historical-disclosure-excerpt.txt', 'vector': 'AMD.npy',
             'content_sha256': sha256(text.encode()).hexdigest(), 'source_id': row[0], 'chunk_id': chunk_id}],
    })
    return {'excerpts': 2, 'provider_calls': 0}


def publish(args):
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
    from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
    record = read(args.case / 'publication' / 'result.json')
    env = read(args.deployment / 'private' / 'business-env.private.json')
    reader = OrganizationExecutionReader(AssetWorkspace(args.deployment / 'state/project-library/organization-assets'),
        OrganizationExecutionAuthority(base_url=env['FINSIGHT_BUSINESS_API_URL'], secret=env['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'],
            execution_id=record['execution'], manifest_digest=record['manifest_digest']))
    organization, nodes = preparation_nodes(reader, workbench_url='https://localhost:18866')
    provenance = read(args.case / 'excerpts/manifest.json')
    by_digest = {s['content_sha256']: s for s in provenance['sources']}
    assert len(nodes) == 2 and {n['content_sha256'] for n in nodes} == set(by_digest)
    vectors = []
    for node in nodes:
        source = by_digest[node['content_sha256']]
        assert node['content'] == (args.case / 'excerpts' / source['file']).read_bytes().decode('utf8')
        vectors.append(np.load(args.case / 'excerpts' / source['vector'], allow_pickle=False))
    query = read(args.case / 'excerpts/query-vector.json')
    release = str(uuid4())
    digest = publish_prepared_index(args.deployment / 'state/organization-indexes', organization, nodes, vectors,
        {query['query']: query['values']}, model=provenance['model'], provenance=provenance, release_id=release)
    result = {'organization_id': organization, 'release_id': release, 'index_digest': digest, 'nodes': len(nodes), 'provider_calls': 0}
    write(args.case / 'release.json', result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['excerpts', 'publish'])
    parser.add_argument('--deployment', type=Path, required=True)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--library', type=Path)
    parser.add_argument('--vectors', type=Path)
    args = parser.parse_args()
    print(json.dumps(excerpts(args) if args.phase == 'excerpts' else publish(args)))
