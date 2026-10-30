"""Semantic receipt contracts and explicit, exact-scope migration; no model calls."""
import sqlite3
from copy import deepcopy

import pytest

from test_organization_candidate_index import prepared
from sec_agent.research_foundation import organization_index_release as release
from sec_agent.research_foundation.organization_input_integrity import proof_scope, verify
from sec_agent.research_foundation.organization_search_cache import OrganizationSearchCache
from sec_agent.research_foundation.organization_hybrid_retrieval import digest
from sec_agent.research_foundation.source_verification_cache import SourceVerificationCache, versions, FORMAT
from sec_agent.research_foundation.verification_receipt_migration import migrate_code_hash_receipts

LEGACY = dict(source_revision='reviewed-fixture', source_code='1'*64, admission_code='2'*64,
              release_loader='3'*64, vector_validator='4'*64)


def fixture(tmp_path, monkeypatch):
    nav, reader, state, directory, grant = prepared(tmp_path, monkeypatch)
    nav.warm_release()
    manifest = grant['manifest']; workspace = reader.workspace; root = tmp_path/'indices'
    observer = OrganizationSearchCache(workspace.library.documents.path)
    revision = versions(observer); observer.db.close()
    cache = SourceVerificationCache(root)
    for item in manifest['inputs']:
        key = cache.key(revision, item, manifest)
        old = digest({'format':FORMAT, 'code':LEGACY['source_code'], 'store':revision['store'],
            'token':revision['tokens'][item['ref']['version_id']], 'item':item,
            'organization_id':manifest['organization_id'], 'research_as_of':manifest['research_as_of'],
            'index':manifest['retrieval_index']})
        cache.put(old, cache.get(key))
        with sqlite3.connect(cache.path) as db: db.execute('DELETE FROM receipts WHERE key=?',(key,))
    scope = proof_scope(workspace, manifest['organization_id'], grant['inputs'], manifest['research_as_of'],
                        manifest['retrieval_index'], root, revision)
    identity, checked, _, signature = scope
    old = dict(identity); del old['proof_contract'], old['source_contract']
    old.update(code=LEGACY['admission_code'], source_code=LEGACY['source_code'])
    SourceVerificationCache(workspace.library.documents.root).put(digest(old), {'checked':checked})
    old_release = release.canonical_digest({'directory':str(directory), 'signature':signature,
        'expected':manifest['retrieval_index'], 'loader':LEGACY['release_loader'], 'vector_validator':LEGACY['vector_validator']})
    with sqlite3.connect(root/'verified-releases.sqlite') as db:
        db.execute('DELETE FROM verified')
        db.execute('INSERT INTO verified VALUES(?)',(old_release,))
    return nav, reader, state, grant, root


def test_explicit_migration_reuses_exact_proofs_and_is_idempotent(tmp_path, monkeypatch):
    nav, reader, state, grant, root = fixture(tmp_path, monkeypatch)
    args = reader.workspace, grant['manifest'], grant['inputs'], root
    dry = migrate_code_hash_receipts(*args, reviewed_legacy=LEGACY)
    assert dry['legacy_sources']==2 and dry['missing_sources']==0 and not dry['applied']
    first = migrate_code_hash_receipts(*args, reviewed_legacy=LEGACY, apply=True)
    assert first['applied'] and first['admission_available'] and first['release_available']
    assert migrate_code_hash_receipts(*args, reviewed_legacy=LEGACY, apply=True)['existing_sources']==2
    monkeypatch.setattr(reader, '_read_storage', lambda *a: pytest.fail('original reread'))
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    new = OrganizationSourceNavigation(reader,workbench_url='http://localhost',retrieval_root=root)
    new.warm_release()
    assert new._candidate_index.original_reads==0 and new._candidate_index.verification_hits==2
    m=grant['manifest']
    assert len(verify(reader.workspace,m['organization_id'],grant['inputs'],m['research_as_of'],m['retrieval_index'],root,
               lambda: pytest.fail('full admission check')))==2
    state['status']=404
    with pytest.raises(Exception): new.warm_release()


@pytest.mark.parametrize('fault',['legacy_hash','source_revision','corrupt'])
def test_migration_never_invents_missing_or_corrupt_proofs(tmp_path, monkeypatch, fault):
    _, reader, _, grant, root = fixture(tmp_path, monkeypatch)
    legacy=deepcopy(LEGACY)
    if fault=='legacy_hash': legacy['source_code']='f'*64
    elif fault=='source_revision':
        with sqlite3.connect(reader.workspace.library.documents.path) as db: db.execute('UPDATE attachments SET body=body')
    else:
        with sqlite3.connect(root/'source-verification.sqlite') as db: db.execute("UPDATE receipts SET digest='bad'")
    with pytest.raises(ValueError):
        migrate_code_hash_receipts(reader.workspace,grant['manifest'],grant['inputs'],root,reviewed_legacy=legacy,apply=True)


def test_proof_keys_do_not_read_code_and_semantic_contract_changes_invalidate(tmp_path, monkeypatch):
    from pathlib import Path
    from sec_agent.research_foundation import source_verification_cache as source
    cache=SourceVerificationCache(tmp_path)
    revision={'store':['store',1,2,'identity'],'tokens':{'version':'token'}}
    item={'ref':{'version_id':'version'}}
    manifest={'organization_id':'org','research_as_of':'cutoff','retrieval_index':{'release':'one'}}
    key=cache.key(revision,item,manifest)
    release_key=release.release_verification_key('/release',('signature',),{'release':'one'})
    monkeypatch.setattr(Path,'read_bytes',lambda *a: pytest.fail('proof identity reads implementation bytes'))
    assert SourceVerificationCache(tmp_path).key(revision,item,manifest)==key
    assert release.release_verification_key('/release',('signature',),{'release':'one'})==release_key
    monkeypatch.setattr(source,'PROOF_CONTRACT','changed-projection-contract')
    assert SourceVerificationCache(tmp_path).key(revision,item,manifest)!=key
    monkeypatch.setattr(release,'RELEASE_PROOF_CONTRACT','changed-validation-contract')
    assert release.release_verification_key('/release',('signature',),{'release':'one'})!=release_key
