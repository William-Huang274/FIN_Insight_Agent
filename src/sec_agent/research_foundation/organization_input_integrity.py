"""Reusable storage proofs for admission; callers still check live authority.

Reuse requires the same current local versions, instrumented content revisions,
cutoff, implementation and sealed release file identities. No grant or body is
cached. Unsupported stores/SEC assets retain the complete verification path.
"""
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

from .organization_hybrid_retrieval import digest
from .organization_index_release import ReleaseLoadCache, validate_contract
from .organization_search_cache import OrganizationSearchCache
from .source_verification_cache import SourceVerificationCache, versions


def verify(workspace, org, inputs, cutoff, contract, root, full_verify):
    if any(item['binding']['ref']['kind'] != 'document' for item in inputs):
        return full_verify()
    store = workspace.library.documents
    observer = OrganizationSearchCache(store.path)
    try:
        from filelock import FileLock
        cache = SourceVerificationCache(store.root)
        code = sha256(Path(__file__).read_bytes() + Path(__file__).with_name('organization_index_release.py').read_bytes()).hexdigest()
        key_scope = digest([str(observer.path), org])
        with FileLock(str(Path(store.root)/f'.input-integrity-{key_scope}.lock'), timeout=60):
            epoch = observer.epoch()
            revision = versions(observer)
            if revision is None:
                return full_verify()
            grouped = defaultdict(set)
            for item in inputs:
                ref = item['binding']['ref']
                grouped[ref['project_id']].add(ref['version_id'])
            current = {space: workspace.document_version_batch('organization:'+org, space, sorted(ids))
                       for space, ids in grouped.items()}
            tokens, checked = {}, []
            for item in inputs:
                ref = item['binding']['ref']
                version = current[ref['project_id']][ref['version_id']]
                if version['access_status'] != 'active' or version['ref'] != ref:
                    raise ValueError('organization_input_current_version_or_access_mismatch')
                token = revision['tokens'].get(ref['version_id'])
                if token is None:
                    return full_verify()
                tokens[ref['version_id']] = token
                checked.append({'resource_id': item['resource_id'], 'ref': version['ref']})
            directory = None
            signature = None
            if contract is not None:
                validate_contract(contract)
                directory = Path(root).resolve()/org/'releases'/contract['release_id']
                signature = ReleaseLoadCache._signature(directory)
            key = digest({'purpose':'admission-storage-integrity.v1', 'code':code, 'source_code':cache.code,
                          'store':revision['store'], 'tokens':tokens, 'versions':current,
                          'inputs':inputs, 'org':org, 'cutoff':cutoff, 'contract':contract,
                          'directory':str(directory), 'files':signature})
            hit = cache.get(key)
            if hit is not None and hit != {'checked':checked}:
                raise ValueError('organization_input_receipt_mismatch')
            result = checked if hit is not None else full_verify()
            if result != checked:
                raise ValueError('organization_input_verified_version_mismatch')
            if observer.epoch() != epoch or (directory is not None and ReleaseLoadCache._signature(directory) != signature):
                raise ValueError('organization_input_storage_changed_during_verification')
            if hit is None:
                cache.put(key, {'checked':checked})
            return result
    finally:
        observer.db.close()
