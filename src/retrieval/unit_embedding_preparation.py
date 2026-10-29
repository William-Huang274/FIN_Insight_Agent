"""Explicit bounded publication embeddings with durable no-resubmit receipts."""
from dataclasses import asdict
from hashlib import sha256
import json
import zlib
import numpy as np
from sec_agent.adapters.local_records import LocalRecords, _pack


def receipt_digest(receipt):
    return sha256(json.dumps(_pack(receipt), sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()


class UnitEmbeddingPreparation:
    def __init__(self,path,api,*,snapshot,budget):
        if (api.embedding_model!='qwen3.7-text-embedding' or len(snapshot)!=64
                or any(c not in '0123456789abcdef' for c in snapshot)):
            raise ValueError('unit_embedding_requires_fixed_model_and_snapshot')
        self.path,self.api,self.snapshot,self.budget=path,api,snapshot,budget
        self.submitted_calls=0

    def key(self,texts):
        return sha256(json.dumps(['unit-embedding-batch.v1',self.snapshot,self.api.embedding_model,1024,
            [sha256(t.encode()).hexdigest() for t in texts]],separators=(',',':')).encode()).hexdigest()

    def embed(self,texts,*,retry_authorization=None):
        if (not 1<=len(texts)<=20 or any(not t.strip() or len(t.encode())>16384 for t in texts)
                or sum(len(t.encode()) for t in texts)>131072):
            raise ValueError('unit_embedding_batch_outside_frozen_limits')
        key=self.key(texts);submitted=False
        with LocalRecords(self.path) as records:
            saved=records.get(key)
            recovered=False;history=[];authorization=None
            if retry_authorization is not None:
                authorization=dict(retry_authorization)
                if (saved is None or saved.get('status')!='failed_usage_unknown'
                        or not isinstance(authorization.get('id'),str) or not authorization['id'].strip()
                        or not isinstance(authorization.get('reason'),str) or not authorization['reason'].strip()
                        or authorization.get('failed_receipt_sha256')!=receipt_digest(saved)):
                    raise RuntimeError('unit_embedding_retry_requires_exact_failed_receipt_and_authorization')
                history=[*saved.get('previous_attempts',[]),
                    {k:v for k,v in saved.items() if k!='previous_attempts'}]
                claim='unit-embedding-retry.v1:'+sha256(json.dumps([key,authorization['id']]).encode()).hexdigest()
                if not records.add(claim,{'batch_key':key,'authorization':authorization}):
                    raise RuntimeError('unit_embedding_retry_authorization_already_used')
                started={'status':'started','previous_attempts':history,'retry_authorization':authorization,
                    'TokenBudgetBasis':self.budget}
                if not records.compare_and_set(key,saved,started):
                    raise RuntimeError('unit_embedding_retry_receipt_changed')
                recovered=True
            if saved is not None and saved.get('status')!='completed' and not recovered:
                raise RuntimeError('unit_embedding_failed_or_pending_no_resubmission')
            if saved is None or recovered:
                basis={**self.budget,'batch_input_scale':{'texts':len(texts),
                    'utf8_bytes':sum(len(t.encode()) for t in texts)},'batch_request_limit':1}
                if not recovered and not records.add(key,{'status':'started','TokenBudgetBasis':basis}):
                    raise RuntimeError('unit_embedding_concurrent_no_resubmission')
                recovery={'previous_attempts':history,'retry_authorization':authorization} if recovered else {}
                result=None
                try:
                    submitted=True
                    self.submitted_calls+=1
                    result=asdict(self.api.embed(texts,dimensions=1024))
                    values=np.asarray(result.pop('values'),dtype=np.float64)
                    if (result['model']!=self.api.embedding_model or values.shape!=(len(texts),1024)
                            or not np.isfinite(values).all() or not np.all(np.any(values!=0,axis=1))):
                        raise ValueError('unit_embedding_response_invalid')
                    saved={'status':'completed','TokenBudgetBasis':basis,'result':result,**recovery,
                        'count':len(texts),'float64_vectors':zlib.compress(values.astype('<f8').tobytes(),1),
                        'input_sha256':[sha256(t.encode()).hexdigest() for t in texts]}
                    records[key]=saved
                except Exception as exc:
                    records[key]={'status':'failed_usage_unknown','TokenBudgetBasis':basis,'error_type':type(exc).__name__,**recovery,
                        'provider_receipt':result if result is not None else {'usage':'unknown'}}
                    raise
        values=np.frombuffer(zlib.decompress(saved['float64_vectors']),dtype='<f8')
        if (saved['input_sha256']!=[sha256(t.encode()).hexdigest() for t in texts]
                or values.size!=len(texts)*1024 or saved['result']['model']!=self.api.embedding_model):
            raise ValueError('unit_embedding_saved_identity_mismatch')
        values=values.reshape(len(texts),1024)
        if not np.isfinite(values).all() or not np.all(np.any(values!=0,axis=1)):
            raise ValueError('unit_embedding_saved_vector_invalid')
        return values,{'batch_key':key,'provider_calls':int(submitted),'cache_hit':not submitted,
            'input_sha256':saved['input_sha256'],**saved['result'],
            'newly_reported_usage':saved['result'].get('usage',{}) if submitted else {}}
