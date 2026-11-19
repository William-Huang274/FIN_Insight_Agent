"""Versioned library retrieval with lexical, dense and graph evidence candidates.

Child-chunk releases use the prepared persistent full-text matrix. Older releases
retain document-card routing. Paid query/rerank calls use the audited cache.
"""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

from langchain_core.vectorstores import InMemoryVectorStore
from sec_agent.adapters.local_records import LocalRecords as Cache
from retrieval.source_hybrid import CachedRetrieval
from retrieval.qwen_api import QwenRetrieval


def document_cards(library):
    # One stable, bounded routing representation per document. The scope is
    # recorded in the index manifest and never described as full-text embeddings.
    rows=library._query('SELECT s.id,s.title,s.metadata,s.published_at,s.vintage,s.access_state,p.body '
        "FROM sources s JOIN passages p ON p.rowid=(SELECT min(p2.rowid) FROM passages p2 WHERE p2.source_id=s.id) WHERE s.access_state='readable' ORDER BY s.id")
    return [{'id':r['id'],'text':r['title']+'\n'+json.loads(r['metadata']).get('routing_metadata_v1',r['metadata'])+'\n'+r['body'][:2000]} for r in rows]


def prepare(library,path,api):
    cards=document_cards(library)
    with Cache(path) as cache:
        client=CachedRetrieval(cache,api,'library-document-router.v1',prepare=True)
        client.embed_documents([c['text'] for c in cards])
        result={'scope':'one navigation card per document; original passages remain fully FTS indexed',
            'documents':len(cards),'characters':sum(len(c['text']) for c in cards),'calls':client.calls,'cache_hits':client.hits,
            'library_sha256':library.manifest['sha256'],'embedding_model':api.embedding_model,'dimensions':1024}
    Path(path).parent.joinpath('library-vector-manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


def rank(library,query,as_of,lexical,*,path,document_id=None,entity_id=None,api=None,graph_result=None):
    if getattr(library,'has_retrieval_chunks',False):
        return rank_chunks(library,query,as_of,lexical,path=path,document_id=document_id,entity_id=entity_id,api=api,graph_result=graph_result)
    owned=api is None
    api=api or QwenRetrieval(os.environ['QWEN_API_KEY'])
    try:
        eligible={s['id'] for s in library.catalog(as_of) if s['eligible'] and (not document_id or s['id']==document_id)}
        cards=[c for c in document_cards(library) if c['id'] in eligible]
        if not cards:return lexical,{'mode':'bm25','reason':'no_eligible_document_cards'}
        with Cache(path) as cache:
            client=CachedRetrieval(cache,api,'library-document-router.v1')
            vectorstore=InMemoryVectorStore(client)
            vectorstore.add_texts([c['text'] for c in cards],metadatas=[{'source_id':c['id']} for c in cards])
            dense=vectorstore.similarity_search(query,k=min(10,len(cards)))
            source_ids=[d.metadata['source_id'] for d in dense]
            if entity_id:
                source_ids += [e['source_id'] for e in library.graph_search(entity_id,as_of,depth=1)['edges'] if e['source_id'] in eligible]
            scoped=library.search(query.split(),as_of,source_ids=list(dict.fromkeys(source_ids)),limit=20) if source_ids else []
            candidates={p['id']:p for p in [*lexical[:12],*scoped]}
            # Dense-only sources still need a readable entry point even when
            # cross-language FTS has no token overlap. No inferred claim text.
            for sid in source_ids[:10]:
                if any(p['source_id']==sid for p in candidates.values()):continue
                p=library.read(sid,as_of,limit=1).get('items',[])
                if p:candidates[p[0]['id']]=p[0]
            rows=list(candidates.values())[:32]
            if not rows:return lexical,{'mode':'bm25','reason':'no_passage_candidates'}
            ranked=client.call('rerank',[query,[p['body'][:6000] for p in rows]])['values']
            return [rows[r['index']] for r in ranked],{'mode':'document_dense_fts5_bm25_source_rerank','calls':client.calls,'cache_hits':client.hits,
                'dense_document_count':len(dense),'candidate_passages':len(rows),'embedding_scope':'document_navigation_cards',
                'dense_documents':source_ids[:10]}
    finally:
        if owned:api.close()


def rank_chunks(library,query,as_of,lexical,*,path,document_id=None,entity_id=None,api=None,graph_result=None):
    """Independent lexical/dense/graph quotas; no first-6000 truncation."""
    from retrieval.library_vectors import dense_search,ready_index
    manifest,_,_=ready_index(path,library.manifest['sha256'])
    if api is not None and api.embedding_model!=manifest['embedding_model']:
        raise ValueError('query_embedding_model_mismatch')
    owned=api is None;api=api or QwenRetrieval(os.environ['QWEN_API_KEY'],embedding_model=manifest['embedding_model'])
    try:
        eligible={s['id'] for s in library.catalog(as_of) if s['eligible'] and (not document_id or s['id']==document_id)}
        if not eligible:return [],{'mode':'chunk_hybrid','reason':'no_eligible_sources'}
        with Cache(Path(path)/'query-cache') as cache:
            client=CachedRetrieval(cache,api,'library-child-query.v1')
            dense_ids=dense_search(path,library.manifest['sha256'],client.embed_query(query),eligible,k=24)
            graph=[];graph_truncated=False
            if entity_id:
                if graph_result is None:
                    graph_result=library.graph_search(entity_id,as_of,depth=1,max_edges=1000)
                graph_truncated=graph_result['truncated']
                edges=[e for e in graph_result['edges']
                       if e['source_id'] in eligible and e['status']!='needs_semantic_review']
                eids=[e['id'] for e in edges]
                if eids:
                    marks=','.join('?' for _ in eids)
                    terms=query.casefold().split()
                    expression=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
                    # Rank evidence-linked chunks before limiting: a document's
                    # early pages must not crowd out a matching later quotation.
                    if expression:
                        graph=library.search_chunk_ids(expression,sorted(eligible),edge_ids=eids,limit=12)
                    fallback=library._query(f'SELECT DISTINCT c.id FROM edge_chunk_links l JOIN retrieval_chunks c ON c.id=l.chunk_id JOIN edges e ON e.id=l.edge_id WHERE l.edge_id IN ({marks}) ORDER BY e.published_at DESC,c.id LIMIT 12',eids)
                    graph=list(dict.fromkeys([*graph,*(p['id'] for p in fallback)]))[:12]
            candidate_ids=list(dict.fromkeys([*(p['id'] for p in lexical[:12]),*dense_ids[:24],*graph[:12]]))
            rows=library.chunks_by_ids(candidate_ids)
            ranks = {}
            for channel, ids in [('lexical',[p['id'] for p in lexical[:12]]),('dense',dense_ids[:24]),('graph',graph[:12])]:
                for position, cid in enumerate(ids, 1):
                    ranks.setdefault(cid, {})[channel] = position
            for row in rows:
                row['candidate_ranks'] = ranks[row['id']]
            if not rows:return [],{'mode':'chunk_hybrid','reason':'no_candidates'}
            texts=[p['context']+'\n'+p['body'] for p in rows]
            if any(len(t)>6000 for t in texts):raise ValueError('retrieval_chunk_exceeds_rerank_contract')
            ranked=client.call('rerank',[query,texts])['values']
            for result in ranked:
                rows[result['index']]['rerank_score'] = result.get('relevance_score')
            return [rows[r['index']] for r in ranked],{'mode':'chunk_dense_fts5_bm25_graph_rerank','embedding_scope':'readable_child_chunks',
                'candidate_chunks':len(rows),'dense_chunks':len(dense_ids),'graph_chunks':len(graph[:12]),
                'graph_window_truncated':graph_truncated,'calls':client.calls,'cache_hits':client.hits}
    finally:
        if owned:api.close()
