"""Scoped Qwen + sqlite-vec retrieval over canonical working papers.

This optional local index is disposable. SQLite owns transactions, sqlite-vec
owns distance calculation, LangChain owns splitting, Qwen owns ranking.
"""
import hashlib
import json
import os
import time
from dataclasses import asdict

from langchain_text_splitters import RecursiveCharacterTextSplitter
from retrieval.qwen_api import QwenRetrieval


def enabled():
    return os.environ.get("FINSIGHT_WORKING_MEMORY_SEMANTIC") == "1"


class WorkingPaperSearch:
    def __init__(self, memory, api=None):
        self.memory, self.api = memory, api
        self.remote_calls = 0

    def setup(self, db):
        import sqlite_vec
        db.enable_load_extension(True)
        try:
            sqlite_vec.load(db)
        finally:
            db.enable_load_extension(False)
        db.execute("""CREATE TABLE IF NOT EXISTS working_vectors (
            note_id TEXT, version INTEGER, part INTEGER, start INTEGER, text TEXT,
            embedding BLOB, PRIMARY KEY(note_id,version,part))""")
        db.execute("""CREATE TABLE IF NOT EXISTS working_retrieval_cache (
            scope TEXT, key TEXT, result TEXT, started REAL, PRIMARY KEY(scope,key))""")
        db.execute("""CREATE TABLE IF NOT EXISTS working_retrieval_calls (
            id INTEGER PRIMARY KEY, scope TEXT, operation TEXT, input_characters INTEGER,
            started REAL, status TEXT, usage TEXT, request_id TEXT)""")
        db.execute("CREATE TABLE IF NOT EXISTS working_retrieval_budgets(call_id INTEGER PRIMARY KEY,basis TEXT)")
        db.commit()

    def call(self, db, operation, payload):
        # Include model, dimensions and tenant/workspace. Never share private caches across tenants.
        scope = json.dumps([self.memory.owner, self.memory.workspace])
        key = hashlib.sha256(json.dumps([operation, payload, self.api.embedding_model,
            self.api.rerank_model, 1024], ensure_ascii=False).encode()).hexdigest()
        cached = db.execute("SELECT result,started FROM working_retrieval_cache WHERE scope=? AND key=?", (scope,key)).fetchone()
        if cached and cached[0]:
            return json.loads(cached[0])
        if cached and time.time() - cached[1] < 120:
            raise RuntimeError("retrieval_pending_or_failed_cooldown")
        if self.remote_calls >= 4:
            raise RuntimeError("retrieval_request_budget_exhausted")
        # Reserve before transport. A failed/uncertain request cannot be immediately resent.
        db.execute("BEGIN IMMEDIATE")
        again = db.execute("SELECT result,started FROM working_retrieval_cache WHERE scope=? AND key=?", (scope,key)).fetchone()
        if again and (again[0] or time.time()-again[1] < 120):
            db.rollback()
            if again[0]: return json.loads(again[0])
            raise RuntimeError("retrieval_pending_or_failed_cooldown")
        db.execute("INSERT OR REPLACE INTO working_retrieval_cache VALUES (?,?,NULL,?)", (scope,key,time.time()))
        cursor = db.execute("INSERT INTO working_retrieval_calls(scope,operation,input_characters,started,status) VALUES(?,?,?,?,?)",
            (scope,operation,len(json.dumps(payload,ensure_ascii=False)),time.time(),"started"))
        call_id = cursor.lastrowid
        basis = {'node_purpose': operation+' of scoped working papers',
            'input_scale':len(json.dumps(payload,ensure_ascii=False)),
            'required_outputs':'Vectors or ranked candidate IDs; original text remains canonical',
            'schema_burden':'Provider native retrieval schema',
            'materiality_quality_risk':'Ranking is not financial verification; exact originals remain available',
            'comparable_run_evidence':'Open four-note paraphrase qualification; no broad quality claim',
            'reasoning_profile':'Embedding/reranking, no generative reasoning',
            'stop_truncation_behavior':'Four calls maximum/search; no automatic retry; literal fallback and explicit indexing backlog'}
        db.execute('INSERT INTO working_retrieval_budgets VALUES(?,?)',(call_id,json.dumps(basis)))
        db.commit()
        self.remote_calls += 1
        try:
            result = asdict(self.api.embed(payload) if operation == "embedding" else self.api.rerank(payload[0],payload[1]))
            db.execute("UPDATE working_retrieval_cache SET result=? WHERE scope=? AND key=?", (json.dumps(result),scope,key))
            db.execute("UPDATE working_retrieval_calls SET status='completed',usage=?,request_id=? WHERE id=?",
                (json.dumps(result['usage']),result['request_id'],call_id))
            db.commit()
            return result
        except Exception:
            db.execute("UPDATE working_retrieval_calls SET status='failed_usage_unknown' WHERE id=?", (call_id,))
            db.commit()
            raise

    def search(self, query, actor=None):
        import sqlite_vec
        query = query.strip()[:500]
        own_api = self.api is None
        if own_api:
            self.api = QwenRetrieval(os.environ["QWEN_API_KEY"])
        try:
            with self.memory.connection() as db:
                self.setup(db)
                rows = db.execute("SELECT * FROM working_notes WHERE owner=? AND workspace=? ORDER BY updated_at DESC,id",
                    (self.memory.owner,self.memory.workspace)).fetchall()
                splitter = RecursiveCharacterTextSplitter(chunk_size=1100,chunk_overlap=100,add_start_index=True)
                pending = []
                for row in rows:
                    existing = {r[0] for r in db.execute("SELECT part FROM working_vectors WHERE note_id=? AND version=?", (row['id'],row['version']))}
                    for part, doc in enumerate(splitter.create_documents([row['body']])):
                        if part not in existing:
                            prior = db.execute("SELECT embedding FROM working_vectors WHERE note_id=? AND text=? LIMIT 1",
                                (row['id'],doc.page_content)).fetchone()
                            if prior:
                                db.execute("INSERT OR IGNORE INTO working_vectors VALUES(?,?,?,?,?,?)",
                                    (row['id'],row['version'],part,doc.metadata['start_index'],doc.page_content,prior[0]))
                            else:
                                pending.append((row,part,doc))
                db.commit()
                # At most 20 new chunks per user search; explicit backlog, never a claim of full indexing.
                for start in range(0,min(20,len(pending)),10):
                    batch = pending[start:start+10]
                    values = self.call(db,"embedding",[row['title']+'\n'+doc.page_content for row,_,doc in batch])['values']
                    for (row,part,doc), vector in zip(batch,values):
                        db.execute("INSERT OR IGNORE INTO working_vectors VALUES(?,?,?,?,?,?)",
                            (row['id'],row['version'],part,doc.metadata['start_index'],doc.page_content,sqlite_vec.serialize_float32(vector)))
                    db.commit()
                vector = self.call(db,"embedding",[query])['values'][0]
                candidates = db.execute("""SELECT n.id,n.title,n.actor,n.version,v.start,v.text AS preview,
                    vec_distance_cosine(v.embedding,?) AS distance FROM working_vectors v
                    JOIN working_notes n ON n.id=v.note_id AND n.version=v.version
                    WHERE n.owner=? AND n.workspace=? AND (? IS NULL OR n.actor=?)
                    ORDER BY distance,n.id,v.part LIMIT 18""",
                    (sqlite_vec.serialize_float32(vector),self.memory.owner,self.memory.workspace,actor,actor)).fetchall()
                items = [dict(r) for r in candidates]
                literal = self.memory.search(query,actor=actor,limit=6)['items']
                # Candidate union; Qwen reranks, no custom financial relevance rules.
                known = {(r['id'],r.get('start',0)) for r in items}
                items += [{**r,'start':0} for r in literal if (r['id'],0) not in known]
                if items:
                    ranking = self.call(db,'rerank',[query,[r['title']+'\n'+r['preview'] for r in items]])['values']
                    items = [{**items[r['index']],'relevance':r['relevance_score']} for r in ranking[:12]]
                return {'items':items,'next_offset':None,'retrieval':'qwen_hybrid_working_papers',
                    'pending_chunks':max(0,len(pending)-20),'remote_calls':self.remote_calls,
                    'notice':'当前版本语义与关键词检索；命中不是事实核验。'+('仍有底稿待索引，可继续关键词或精确读取。' if len(pending)>20 else '')}
        finally:
            if own_api: self.api.close()


def search_working_papers(memory, query='', *, actor=None, offset=0):
    if not enabled() or not query.strip() or offset:
        return memory.search(query,actor=actor,offset=offset)
    try:
        return WorkingPaperSearch(memory).search(query,actor)
    except Exception:
        return {**memory.search(query,actor=actor,offset=offset), 'semantic_available':False,
                'notice':'语义检索暂不可用，当前为关键词结果；已保存正文可继续读取。'}
