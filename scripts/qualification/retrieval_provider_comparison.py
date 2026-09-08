"""Paired development retrieval qualification over an immutable public corpus.

Uses SentenceTransformers/OpenAI SDK/numpy; no production index changes.
Ground-truth relevance stays out of inference and is evaluated separately.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import time

import numpy as np

QUERY_PREFIX = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main(args):
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    if len({row['id'] for row in corpus}) != len(corpus):
        raise ValueError('corpus_document_ids_not_unique')
    args.output.mkdir(parents=True, exist_ok=False)
    basis = {"purpose": f"Paired public retrieval qualification: {args.arm}",
        "input_scale": {"documents": len(corpus), "queries": len(queries), "characters": sum(len(r['text']) for r in corpus)},
        "required_outputs": "1024D normalized vectors or ranked shared candidate indices",
        "schema_burden": "Native numeric output; no generative report",
        "materiality_quality_risk": "Development corpus, not blind benchmark or financial evidence admission",
        "comparable_run_evidence": "Local Qwen3-Embedding-0.6B and BGE reranker vs Qwen hosted API",
        "reasoning_profile": "Embedding and cross-encoder scoring, no generative reasoning",
        "stop_truncation_behavior": "No automatic retries; local token length checked; all API calls saved before next",
        "corpus_sha256": digest(args.corpus), "queries_sha256": digest(args.queries),
        "query_prefix": QUERY_PREFIX, "dimensions": 1024,
        "price_basis": "Qwen text-embedding-v4/qwen3-rerank CNY0.5 per million input tokens, official model pages 2026-09-09; actual free credit deduction unknown"}
    save(args.output/'basis.json', basis)
    if basis['input_scale']['characters'] > 700_000 or len(queries) > 12:
        raise ValueError('qualification_input_limit')
    started = time.perf_counter()
    calls=[]
    def recorded(operation, call):
        number=len(calls)
        save(args.output/f'call-{number:03d}-started.json', {'operation':operation,'usage':'pending'})
        clock=time.perf_counter()
        try:
            result=call()
        except Exception as exc:
            save(args.output/f'call-{number:03d}-failure.json', {'type':type(exc).__name__,
                'status':getattr(exc,'status_code',None),'usage':'unknown','seconds':time.perf_counter()-clock})
            raise RuntimeError(f'qualification_call_failed:{number}:{type(exc).__name__}') from None
        row={**asdict(result),'seconds':time.perf_counter()-clock}
        save(args.output/f'call-{number:03d}.json',row)
        calls.append({'operation':operation,'seconds':row['seconds'],'usage':result.usage})
        print(json.dumps({'call':number,'operation':operation,'usage':result.usage}),flush=True)
        return result.values
    api=None
    if args.arm.startswith('api'):
        from retrieval.qwen_api import QwenRetrieval
        api=QwenRetrieval(os.environ['QWEN_API_KEY'])
    try:
        if args.arm.endswith('embedding'):
            texts=[r['text'] for r in corpus]+[QUERY_PREFIX+q['text'] for q in queries]
            if api:
                vectors=[]
                for offset in range(0,len(texts),10):
                    batch=texts[offset:offset+10]
                    vectors.extend(recorded('embedding',lambda:api.embed(batch)))
                vectors=np.asarray(vectors,dtype=np.float32)
            else:
                from sentence_transformers import SentenceTransformer
                import torch
                model=SentenceTransformer(str(args.model),device='cuda',local_files_only=True,trust_remote_code=False)
                model.half(); model.eval(); model.max_seq_length=1024
                counts=[len(ids) for ids in model.tokenizer(texts,truncation=False)['input_ids']]
                if max(counts)>model.max_seq_length:
                    raise ValueError('local_embedding_would_truncate')
                torch.cuda.reset_peak_memory_stats()
                vectors=model.encode(texts,batch_size=8,normalize_embeddings=True,convert_to_numpy=True,show_progress_bar=False)
                basis.update({'local_model':str(args.model),'input_tokens':sum(counts),
                    'maximum_input_tokens':max(counts),'peak_cuda_bytes':torch.cuda.max_memory_allocated()})
            if vectors.shape!=(len(texts),1024) or not np.isfinite(vectors).all():
                raise ValueError('embedding_shape_or_finiteness')
            norms=np.linalg.norm(vectors,axis=1,keepdims=True)
            if np.any(norms==0): raise ValueError('zero_embedding')
            vectors=vectors/norms
            np.save(args.output/'vectors.npy',vectors,allow_pickle=False)
            scores=vectors[len(corpus):]@vectors[:len(corpus)].T
            rankings=np.argsort(-scores,axis=1,kind='stable').tolist()
        else:
            candidate_data=json.loads(args.candidates.read_text(encoding='utf-8'))
            if candidate_data['corpus_sha256']!=digest(args.corpus) or candidate_data['queries_sha256']!=digest(args.queries):
                raise ValueError('paired_candidate_input_mismatch')
            model=None
            if not api:
                from sentence_transformers import CrossEncoder
                model=CrossEncoder(str(args.model),device='cuda',local_files_only=True,trust_remote_code=False,max_length=2048)
                model.model.half(); model.model.eval()
            rankings=[]
            for q,indices in zip(queries,candidate_data['indices'],strict=True):
                docs=[corpus[i]['text'] for i in indices]
                if api:
                    rows=recorded('rerank',lambda:api.rerank(q['text'],docs))
                    order=[row['index'] for row in rows]
                else:
                    lengths=[len(row) for row in model.tokenizer([q['text']]*len(docs),docs,truncation=False)['input_ids']]
                    if max(lengths)>2048: raise ValueError('local_reranker_would_truncate')
                    clock=time.perf_counter()
                    scores=model.predict([(q['text'],d) for d in docs],batch_size=4,show_progress_bar=False)
                    calls.append({'operation':'local_rerank','seconds':time.perf_counter()-clock,'input_tokens':sum(lengths)})
                    order=np.argsort(-np.asarray(scores),kind='stable').tolist()
                rankings.append([indices[i] for i in order])
        save(args.output/'rankings.json',rankings)
        save(args.output/'summary.json',{'arm':args.arm,'corpus_sha256':digest(args.corpus),
            'queries_sha256':digest(args.queries),'seconds':time.perf_counter()-started,'calls':calls,
            'reported_tokens':sum(c.get('usage',{}).get('total_tokens',0) for c in calls),
            'quality':'not_evaluated','basis':basis})
    finally:
        if api: api.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--arm',choices=['local_embedding','api_embedding','local_rerank','api_rerank'],required=True)
    for name in ['corpus','queries','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--model',type=Path)
    parser.add_argument('--candidates',type=Path)
    main(parser.parse_args())
