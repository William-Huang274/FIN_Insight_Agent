"""Read completed publication-vector receipts without a provider client."""
from hashlib import sha256
import json
from pathlib import Path
import zlib
import sqlite3
import numpy as np
from sec_agent.adapters.local_records import _unpack


class _ReadOnlyRecords:
    def __init__(self,path):
        self.db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)

    def get(self,key):
        row=self.db.execute('SELECT value FROM records WHERE key=? AND expires IS NULL',(key,)).fetchone()
        return _unpack(json.loads(row[0])) if row else None

    def close(self):
        self.db.close()


class UnitEmbeddingReceiptReader:
    def __init__(self,outputs,*,allow_partial=False):
        self.records=[];self.inputs={};self._last=None
        self.completed_batches=0;self.incomplete_batches=0
        try:
            for output in outputs:
                output=Path(output);plan=json.loads((output/'plan.json').read_text(encoding='utf8'))
                raw=(output/'jobs.jsonl').read_bytes()
                if sha256(raw).hexdigest()!=plan['jobs_sha256']:
                    raise ValueError('unit_receipt_jobs_changed')
                records=_ReadOnlyRecords(output/'receipts'/'records-v1.sqlite');source=len(self.records);self.records.append(records)
                for line in raw.decode().splitlines():
                    job=json.loads(line);hashes=[item['input_sha256'] for item in job['units']]
                    key=sha256(json.dumps(['unit-embedding-batch.v1',plan['snapshot_digest'],
                        'qwen3.7-text-embedding',1024,hashes],separators=(',',':')).encode()).hexdigest()
                    saved=records.get(key)
                    if saved is None or saved.get('status')!='completed':
                        self.incomplete_batches+=1
                        if not allow_partial:raise ValueError('unit_receipt_preparation_incomplete_no_provider_fallback')
                        continue
                    if saved['input_sha256']!=hashes or saved['result']['model']!='qwen3.7-text-embedding':
                        raise ValueError('unit_receipt_model_or_input_mismatch')
                    self.completed_batches+=1
                    for position,digest in enumerate(hashes):self.inputs.setdefault(digest,(source,key,position))
        except Exception:
            self.close();raise

    def __call__(self,unit):
        digest=unit['embedding_input_sha256'];reference=self.inputs.get(digest)
        if reference is None:raise ValueError('unit_vector_receipt_missing_no_provider_fallback')
        source,key,position=reference
        if self._last is None or self._last[0]!=(source,key):
            saved=self.records[source].get(key)
            if saved is None or saved.get('status')!='completed':raise ValueError('unit_vector_receipt_no_longer_completed')
            values=np.frombuffer(zlib.decompress(saved['float64_vectors']),dtype='<f8')
            if values.size!=len(saved['input_sha256'])*1024:raise ValueError('unit_vector_receipt_shape')
            values=values.reshape(-1,1024)
            if not np.isfinite(values).all() or not np.all(np.any(values!=0,axis=1)):
                raise ValueError('unit_vector_receipt_invalid_values')
            self._last=(source,key),saved,values
        _,saved,values=self._last
        if saved['input_sha256'][position]!=digest:raise ValueError('unit_vector_receipt_identity_changed')
        return {'input_sha256':digest,'model':saved['result']['model'],'vector':values[position],
            'batch_key':key,'request_id':saved['result'].get('request_id'),'provider_calls':0}

    def close(self):
        for record in self.records:record.close()
        self.records=[];self._last=None
