"""Explicit, resumable vector preparation for one published source snapshot."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from retrieval.qwen_api import QwenRetrieval
from retrieval.source_hybrid import prepare_source_index, source_chunks
from scripts.deployment.dell_report_workbench import configured_key


def main():
    p=argparse.ArgumentParser(); p.add_argument('--nodes',type=Path,required=True); p.add_argument('--cache',required=True)
    p.add_argument('--output',type=Path,required=True); p.add_argument('--execute',action='store_true')
    p.add_argument('--reuse-snapshot', help='Reuse only exact-text vectors from this previously prepared snapshot')
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    body=a.nodes.read_bytes(); snapshot=sha256(body).hexdigest()
    rows=[json.loads(line) for line in body.decode('utf-8').splitlines() if line.strip()]
    chunks=source_chunks([r for r in rows if r['node_kind']!='section'])
    basis={'node_purpose':'Prepare expanded case-company public source vectors for existing production hybrid RAG',
        'input_scale':{'chunks':len(chunks),'characters':sum(len(c['text']) for c in chunks)},
        'required_outputs':'1024-dimensional vectors for all admitted public original passages; persist for subsequent searches',
        'schema_burden':'Native embedding API; no generated report or financial judgment',
        'materiality_quality_risk':'Candidate recall only; actual claims require original reads and numeric fact authority',
        'comparable_run_evidence':'208 739-leaf Qwen hybrid retrieval qualification; new five-company SEC documents 210',
        'reasoning_profile':'Non-generative text-embedding-v4',
        'stop_truncation_behavior':'No document truncation; no retry on unknown/failed request; existing DiskCache resumes successful batches',
        'snapshot':snapshot, 'reuse_snapshot':a.reuse_snapshot,
        'cost_basis':'Historical 2026-09-09 provider price CNY0.5/million tokens; log actual tokens, credit usage unavailable'}
    (a.output/'basis.json').write_text(json.dumps(basis,ensure_ascii=False,indent=2),encoding='utf-8')
    if not a.execute: print(json.dumps(basis)); return
    if basis['input_scale']['characters']>16_000_000: raise ValueError('outside_210_qualified_corpus_size')
    class AuditedAPI(QwenRetrieval):
        def embed(self,texts,**kwargs):
            result=super().embed(texts,**kwargs)
            with (a.output/'usage.jsonl').open('a',encoding='utf-8') as stream:
                stream.write(json.dumps({'request_id':result.request_id,'model':result.model,'usage':result.usage})+'\n')
            return result
    api=AuditedAPI(configured_key('QWEN_API_KEY'))
    try:
        result=prepare_source_index(rows,snapshot,a.cache,api,reuse_snapshot=a.reuse_snapshot)
        (a.output/'result.json').write_text(json.dumps(result),encoding='utf-8');print(json.dumps(result))
    finally: api.close()


if __name__=='__main__':main()
