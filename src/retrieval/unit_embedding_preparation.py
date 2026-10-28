"""Explicit bounded publication embeddings with durable no-resubmit receipts."""
from dataclasses import asdict
from hashlib import sha256
import json
import zlib
import numpy as np
from sec_agent.adapters.local_records import LocalRecords


class UnitEmbeddingPreparation:
    def __init__(self,path,api,*,snapshot,budget):
        if (api.embedding_model!='qwen3.7-text-embedding' or len(snapshot)!=64
                or any(c not in '0123456789abcdef' for c in snapshot)):
            raise ValueError('unit_embedding_requires_fixed_model_and_snapshot')
        self.path,self.api,self.snapshot,self.budget=path,api,snapshot,budget

    def key(self,texts):
        return sha256(json.dumps(['unit-embedding-batch.v1',self.snapshot,self.api.embedding_model,1024,
            [sha256(t.encode()).hexdigest() for t in texts]],separators=(',',':')).encode()).hexdigest()

    def embed(self,texts):
        if (not 1<=len(texts)<=20 or any(not t.strip() or len(t.encode())>16384 for t in texts)
                or sum(len(t.encode()) for t in texts)>131072):
            raise ValueError('unit_embedding_batch_outside_frozen_limits')
        key=self.key(texts);submitted=False
        with LocalRecords(self.path) as records:
            saved=records.get(key)
            if saved is not None and saved.get('status')!='completed':
                raise RuntimeError('unit_embedding_failed_or_pending_no_resubmission')
            if saved is None:
                basis={**self.budget,'batch_input_scale':{'texts':len(texts),
                    'utf8_bytes':sum(len(t.encode()) for t in texts)},'batch_request_limit':1}
                if not records.add(key,{'status':'started','TokenBudgetBasis':basis}):
                    raise RuntimeError('unit_embedding_concurrent_no_resubmission')
                result=None
                try:
                    submitted=True
                    result=asdict(self.api.embed(texts,dimensions=1024))
                    values=np.asarray(result.pop('values'),dtype=np.float64)
                    if (result['model']!=self.api.embedding_model or values.shape!=(len(texts),1024)
                            or not np.isfinite(values).all() or not np.all(np.any(values!=0,axis=1))):
                        raise ValueError('unit_embedding_response_invalid')
                    saved={'status':'completed','TokenBudgetBasis':basis,'result':result,
                        'count':len(texts),'float64_vectors':zlib.compress(values.astype('<f8').tobytes(),1),
                        'input_sha256':[sha256(t.encode()).hexdigest() for t in texts]}
                    records[key]=saved
                except Exception as exc:
                    records[key]={'status':'failed_usage_unknown','TokenBudgetBasis':basis,'error_type':type(exc).__name__,
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
