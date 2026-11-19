"""Bounded, audited reranking of already-authorized immutable candidates.

The caller owns candidate recall and authority. Failure is an execution error,
never an empty result, an automatic retry or a silent RRF fallback.
"""
from dataclasses import asdict
from hashlib import sha256
import json
import math

from sec_agent.adapters.local_records import LocalRecords


class ScopedReranker:
    def __init__(self, path, api):
        self.path, self.api = path, api

    def rank(self, query, candidates, *, scope, index_digest, check_access, instruct=None):
        if (not isinstance(scope, str) or not scope or len(scope)>256
                or len(index_digest)!=64 or any(c not in '0123456789abcdef' for c in index_digest)):
            raise ValueError('rerank_requires_fixed_server_scope')
        if not query.strip() or len(query.encode())>8192 or not 1<=len(candidates)<=48:
            raise ValueError('rerank_input_outside_budget')
        if instruct is not None and (not isinstance(instruct,str) or not instruct.strip()
                                     or len(instruct.encode())>4096):
            raise ValueError('rerank_instruction_outside_budget')
        ids=[r['node_id'] for r in candidates]
        if len(set(ids))!=len(ids):
            raise ValueError('rerank_duplicate_candidate')
        documents=[]
        for row in candidates:
            body=row['content']
            if sha256(body.encode()).hexdigest()!=row['content_sha256']:
                raise ValueError('rerank_candidate_body_mismatch')
            # Fixed original context, no gold labels, generated hints or answers.
            text=(row.get('embedding_context','')+'\n'+body).strip()
            if row.get('rerank_document_metadata'):
                from .rerank_document_context import document_context_text
                text=document_context_text(row['rerank_document_metadata'])+'\n\n'+text
            if not text or len(text.encode())>32768:
                raise ValueError('rerank_document_outside_budget_no_truncation')
            documents.append(text)
        if sum(len(x.encode()) for x in documents)>524288:
            raise ValueError('rerank_total_input_outside_budget')
        identity={'format':'scoped-rerank.v1','scope':scope,'index':index_digest,
                  'model':self.api.rerank_model,'query':query,'candidates':[
                      [n,sha256(t.encode()).hexdigest()] for n,t in zip(ids,documents)]}
        # Preserve historical no-instruction keys exactly; a different task
        # instruction must never reuse the old paid response.
        if instruct is not None:
            identity['instruct']=instruct
        key=sha256(json.dumps(identity,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        basis={'purpose':'Compare and rank the fixed authorized retrieval candidate union',
            'input_scale':{'candidate_count':len(documents),'utf8_bytes':sum(len(x.encode()) for x in documents),
                           'query_utf8_bytes':len(query.encode())},
            'required_output':'One provider rank and score for every candidate; IDs preserved',
            'quality_risk':'Reranking cannot recover evidence absent from candidate union; preserve period, unit, revision',
            'reasoning_profile':'Qwen relevance reranking only, no Agent or answer generation',
            'limits':{'requests':1,'max_candidates':48,'max_document_bytes':32768,'max_total_bytes':524288},
            'stop_behavior':'Fail closed on current denial; retain failed/unknown usage; no resubmission or truncation'}
        if instruct is not None:
            basis['input_scale']['instruction_utf8_bytes']=len(instruct.encode())
        check_access()
        calls=0
        with LocalRecords(self.path) as records:
            saved=records.get(key)
            if saved and saved.get('status')!='completed':
                raise RuntimeError('rerank_pending_or_failed_no_resubmission')
            if saved:
                result=saved['result']
            else:
                if not records.add(key,{'status':'started','identity':identity,'TokenBudgetBasis':basis}):
                    raise RuntimeError('rerank_pending_no_resubmission')
                try:
                    check_access()
                    calls=1
                    options={'instruct':instruct} if instruct is not None else {}
                    result=asdict(self.api.rerank(query,documents,top_n=len(documents),**options))
                    self._validate(result,len(documents))
                    records[key]={'status':'completed','identity':identity,'TokenBudgetBasis':basis,'result':result}
                except Exception as error:
                    records[key]={'status':'failed_usage_unknown' if calls else 'not_submitted',
                        'identity':identity,'TokenBudgetBasis':basis,'error_type':type(error).__name__}
                    raise
        self._validate(result,len(documents))
        check_access()  # Successful billing receipt survives a mid-call revocation.
        return [candidates[r['index']] for r in result['values']], {
            'model':self.api.rerank_model,'provider_calls':calls,'cache_hit':not bool(calls),
            'request_key':key,'request_id':result.get('request_id'),'usage':result.get('usage',{}),
            'newly_reported_usage':result.get('usage',{}) if calls else {},
            'scores':[[ids[r['index']],r['relevance_score']] for r in result['values']]}

    def _validate(self,result,count):
        rows=result.get('values',[])
        if (result.get('model')!=self.api.rerank_model or len(rows)!=count
                or any(type(r.get('index')) is not int for r in rows)
                or sorted(r['index'] for r in rows)!=list(range(count))
                or any(type(r.get('relevance_score')) not in (int,float)
                       or not math.isfinite(r['relevance_score']) for r in rows)):
            raise ValueError('rerank_invalid_provider_or_cached_response')


class ConfiguredReranker:
    """Server-configured provider, never selected by an Agent/tool argument."""
    def __init__(self,path):
        import os
        self.path=path
        self.model=os.environ.get('FINSIGHT_ORGANIZATION_RERANK_MODEL','qwen3-rerank')
        if self.model not in {'qwen3-rerank','qwen3.7-text-rerank'}:
            raise ValueError('organization_rerank_model_invalid')

    def rank(self,*args,**kwargs):
        from contextlib import closing
        import os
        from retrieval.qwen_api import QwenRetrieval
        if not os.environ.get('QWEN_API_KEY'):
            raise ValueError('organization_rerank_not_configured')
        with closing(QwenRetrieval(os.environ['QWEN_API_KEY'],embedding_model='qwen3.7-text-embedding',
                                   rerank_model=self.model)) as api:
            return ScopedReranker(self.path,api).rank(*args,**kwargs)
