"""Opt-in original-document retrieval: LangChain vectors + BM25 union + Qwen.

The caller filters the snapshot/document/page scope before ranking. DiskCache
stores provider responses, not evidence authority. Index preparation is explicit:
ordinary search never starts an unbounded corpus embedding job.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
from diskcache import Cache
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_text_splitters import RecursiveCharacterTextSplitter
from .qwen_api import QwenRetrieval


def cache_path():
    if os.environ.get('FINSIGHT_SOURCE_HYBRID') != '1':
        return None
    path = os.environ.get('FINSIGHT_WORKING_MEMORY_PATH')
    return str(Path(path).parent / 'source-rag') if path else None


class CachedRetrieval(Embeddings):
    def __init__(self, cache, api, scope, *, prepare=False):
        self.cache, self.api, self.scope, self.prepare = cache, api, scope, prepare
        self.calls = self.hits = 0

    def key(self, operation, payload):
        return sha256(json.dumps([self.scope, self.api.embedding_model, self.api.rerank_model,
            1024, operation, payload], ensure_ascii=False).encode()).hexdigest()

    def call(self, operation, payload):
        key = self.key(operation, payload)
        saved = self.cache.get(key)
        if saved and saved.get('result'):
            self.hits += 1
            return saved['result']
        if saved:
            raise RuntimeError('检索请求待完成或曾失败，未自动重发')
        basis = {'node_purpose': operation+' for original source navigation',
            'input_scale': len(json.dumps(payload, ensure_ascii=False)),
            'required_outputs': '1024-dimensional vectors or ranked original chunk indices',
            'schema_burden': 'Provider native retrieval schema',
            'materiality_quality_risk': 'Search candidates only; issuer/period/units remain in immutable originals',
            'comparable_run_evidence': 'Existing Qwen working-paper adapter; original-source retrieval under qualification',
            'reasoning_profile': 'Embedding/reranking, no generative reasoning',
            'stop_truncation_behavior': 'Explicit corpus preparation; search at most query embedding and rerank; no retry of failed/unknown calls'}
        if not self.cache.add(key, {'status': 'started', 'basis': basis}):
            raise RuntimeError('相同检索请求正在处理中')
        self.calls += 1
        try:
            response = self.api.embed(payload) if operation == 'embedding' else self.api.rerank(payload[0], payload[1])
            result = asdict(response)
            self.cache[key] = {'status':'completed', 'basis':basis, 'result':result}
            return result
        except Exception:
            self.cache[key] = {'status':'failed_usage_unknown', 'basis':basis}
            raise

    def embed_documents(self, texts):
        keys = [self.key('vector', t) for t in texts]
        missing = list(dict.fromkeys(t for t,k in zip(texts,keys) if self.cache.get(k) is None))
        if missing and not self.prepare:
            raise RuntimeError(f'原文向量索引尚有 {len(missing)} 个片段未准备；本次仅使用 BM25')
        for start in range(0,len(missing),10):
            batch=missing[start:start+10]
            result=self.call('embedding',batch)
            for text,vector in zip(batch,result['values']): self.cache[self.key('vector',text)]=vector
        return [self.cache[k] for k in keys]

    def embed_query(self, text):
        return self.call('embedding',[text])['values'][0]


def source_chunks(rows):
    splitter=RecursiveCharacterTextSplitter(chunk_size=2000,chunk_overlap=200)
    result=[]
    for row in rows:
        text=str(row.get('model_text') or row.get('content') or '')
        prefix=' / '.join(str(row[k]) for k in ('company','fiscal_period','title','section_path') if row.get(k))
        for part,body in enumerate(splitter.split_text(text)):
            result.append({'text':prefix+'\n'+body,'node_id':row['node_id'],'part':part})
    return result


def prepare_source_index(rows, snapshot, path, api, *, reuse_snapshot=None):
    chunks=source_chunks([r for r in rows if r.get('node_kind')!='section'])
    with Cache(path) as cache:
        client=CachedRetrieval(cache,api,snapshot,prepare=True)
        reused=0
        if reuse_snapshot and reuse_snapshot != snapshot:
            # Identical full text, provider models and dimensions only. Reuse
            # vectors, never query/rerank receipts or financial source authority.
            previous=CachedRetrieval(cache,api,reuse_snapshot)
            for text in dict.fromkeys(c['text'] for c in chunks):
                target=client.key('vector',text)
                if cache.get(target) is None:
                    vector=cache.get(previous.key('vector',text))
                    if vector is not None:
                        cache.add(target,vector)
                        reused+=1
        client.embed_documents([c['text'] for c in chunks])
        return {'chunks':len(chunks),'calls':client.calls,'cache_hits':client.hits,'embedding_model':api.embedding_model,
                'reused_vectors':reused}


def rank_sources(rows, query, snapshot, literal, *, path, api=None, diagnostics=False):
    owned=api is None
    api=api or QwenRetrieval(os.environ['QWEN_API_KEY'])
    try:
        chunks=source_chunks(rows)
        if not chunks:return literal, {'mode':'bm25','notice':'没有可索引原文'}
        with Cache(path) as cache:
            client=CachedRetrieval(cache,api,snapshot)
            vectorstore=InMemoryVectorStore(client)
            # This reads prepared vectors only; missing vectors cause explicit fallback.
            vectorstore.add_texts([c['text'] for c in chunks],metadatas=[{'index':i} for i in range(len(chunks))])
            dense=vectorstore.similarity_search(query,k=min(24,len(chunks)))
            indices=[d.metadata['index'] for d in dense]
            dense_ids=list(dict.fromkeys(chunks[i]['node_id'] for i in indices))
            lexical_ids={r['node_id'] for r in literal[:12]}
            indices=list(dict.fromkeys([*indices,*[i for i,c in enumerate(chunks) if c['node_id'] in lexical_ids][:24]]))
            ranked=client.call('rerank',[query,[chunks[i]['text'] for i in indices]])['values']
            node_ids=list(dict.fromkeys(chunks[indices[r['index']]]['node_id'] for r in ranked))
            by_id={r['node_id']:r for r in rows}
            return [by_id[i] for i in node_ids], {'mode':'qwen_dense_bm25_rerank','calls':client.calls,'cache_hits':client.hits,
                'embedding_model':api.embedding_model,'rerank_model':api.rerank_model,'candidates':len(indices),
                **({'dense_node_ids':dense_ids,'candidate_node_ids':list(dict.fromkeys(chunks[i]['node_id'] for i in indices))} if diagnostics else {})}
    finally:
        if owned:api.close()
