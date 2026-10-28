"""Offline original reader for scoring parity; never an organization grant.

Reuses production materialization/context completion methods under a declared
frozen diagnostic scope. Cannot exercise Java authorization or HTTP behavior.
"""
from hashlib import sha256,file_digest
import json
from pathlib import Path
import sqlite3
import zlib
from types import SimpleNamespace
from sec_agent.research_foundation.organization_candidate_index import VerifiedCandidateIndex


class _Fields:
    def __init__(self,owner,position):self.owner,self.position=owner,position
    def __getitem__(self,document):
        from sec_agent.research_foundation.prepared_source_metadata import restore
        return restore(self.owner._document(document))[self.position]


class FrozenRetrievalContext:
    materialize=VerifiedCandidateIndex.materialize
    contextualize=VerifiedCandidateIndex.contextualize
    complete_tables=VerifiedCandidateIndex.complete_tables

    def __init__(self,index_path,context_root,*,index=None,retained_documents=None,lazy_structures=False):
        from sec_agent.research_foundation.organization_index_release import canonical_digest
        self.directory=Path(index_path).resolve().parent;self.context_root=Path(context_root)
        if index is None:index=json.loads(Path(index_path).read_bytes())
        context=json.loads((self.context_root/'context.json').read_bytes())
        from sec_agent.research_foundation.source_verification_cache import implementation_digest
        if context.get('structure_implementation_sha256')!=implementation_digest():
            raise ValueError('offline_context_structure_implementation_changed')
        if canonical_digest(index)!=context['snapshot_digest']:raise ValueError('offline_context_snapshot_mismatch')
        self.proofs={b['document_id']:b for b in context['bindings']}
        retained=set(self.proofs) if retained_documents is None else set(retained_documents)
        if retained-set(self.proofs):raise ValueError('offline_context_retained_document_missing')
        self.allowed_documents=retained
        self.db=sqlite3.connect((self.context_root/'contexts.sqlite').resolve().as_uri()+'?mode=ro',uri=True)
        if self.db.execute("SELECT value FROM metadata WHERE key='sealed'").fetchone()!=('frozen-production-structure.v1',):
            raise ValueError('offline_context_not_sealed')
        with (self.directory/'navigation.sqlite').open('rb') as stream:
            if file_digest(stream,'sha256').hexdigest()!=index['navigation_index']['sha256']:
                raise ValueError('offline_context_navigation_changed')
        self.signatures={p:self._signature(p) for p in (self.directory/'navigation.sqlite',self.context_root/'contexts.sqlite')}
        self.source_metadata={};self.rows={};self.neighbors={};self.origins={};self.candidate_reads=0
        self.records={r['node_id']:r for r in index['records'] if r['document_id'] in retained}
        try:
            for document in self.proofs:
                value=self._document(document);self.source_metadata[document]=value['metadata']
                # All catalog fields are verified and retained for global planning.
                # Hold per-node structures only for this declared diagnostic release.
                # The caller still rejects any selected source outside that release.
                if document in retained and not lazy_structures:self._retain(document,value)
        except BaseException:
            self.db.close()
            raise
        self.structures=_Fields(self,0);self.locations=_Fields(self,1)
        self.workbench_url='offline://not-a-product-link'
        # An offline source guard only. This marker cannot be submitted to Java.
        self.reader=SimpleNamespace(_grant=lambda:({'offline_frozen_scope':context['snapshot_digest']},),
                                    _after=lambda _:self.check())

    def _retain(self,document,value):
        from retrieval.fact_scope import verified_fact_owner
        self.neighbors.update(value['prepared_navigation']['neighbors'])
        complete=set(value.get('evidence_scope_complete',[]))
        fact_owner=verified_fact_owner(value['metadata'])
        for node in value['nodes']:
            self.rows[node]={**self.records[node],'parent_document_id':document,
                'evidence_scopes':value.get('evidence_scopes',{}).get(node,[]),
                'period_evidence':value.get('period_evidence',{}).get(node,[]),
                'fact_owner':fact_owner,'source_interval':value['source_intervals'].get(node),
                'evidence_scope_complete':node in complete}
        self.origins[document]={'resource_id':'offline-source'}

    def select_documents(self,documents):
        """Switch resident structures, never the verified planning population.

        Callers must finish using the previous query before switching. Every
        selected payload is verified again; failure leaves no partial scope.
        """
        selected=set(documents)
        if selected-self.allowed_documents:raise ValueError('offline_context_selection_outside_release')
        self.check()
        self.rows.clear();self.neighbors.clear();self.origins.clear()
        try:
            for document in sorted(selected):self._retain(document,self._document(document))
            self.check()
        except BaseException:
            self.rows.clear();self.neighbors.clear();self.origins.clear()
            raise

    @staticmethod
    def _signature(path):
        stat=path.stat();return stat.st_size,stat.st_mtime_ns

    def _document(self,document):
        raw=self.db.execute('SELECT payload FROM documents WHERE id=?',(document,)).fetchone()
        if not raw or sha256(raw[0]).hexdigest()!=self.proofs[document]['context_sha256']:
            raise ValueError('offline_context_document_changed')
        return json.loads(zlib.decompress(raw[0]))

    def check(self):
        if any(self._signature(p)!=s for p,s in self.signatures.items()):raise ValueError('offline_context_generation_changed')

    def close(self):self.db.close()
