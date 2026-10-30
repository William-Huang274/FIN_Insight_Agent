"""Document-level publication metadata. Never projects originals on a query."""
from pathlib import Path
import json
from .organization_hybrid_retrieval import digest
from .organization_execution_access import OrganizationSourceStorageUnavailable


def identity(manifest):
    return digest({'organization': manifest['organization_id'], 'release': manifest.get('retrieval_index'),
        'as_of': manifest['research_as_of'], 'inputs': sorted(manifest['inputs'], key=lambda x:x['resource_id'])})


def publish(root, manifest, descriptors):
    """Explicit deployment step; caller supplies previously verified descriptors."""
    expected = {x['resource_id']: x['ref'] for x in manifest['inputs']}
    if set(descriptors) != set(expected) or any(descriptors[k]['ref'] != v for k,v in expected.items()):
        raise ValueError('document_catalog_publication_scope_mismatch')
    value = {'identity':identity(manifest), 'documents':descriptors}
    directory=Path(root)/'document-catalogs';directory.mkdir(exist_ok=True)
    path=directory/(identity(manifest)+'.json')
    raw=json.dumps({'value':value,'digest':digest(value)},ensure_ascii=False,separators=(',',':'))
    if path.exists():
        if path.read_text(encoding='utf8')!=raw:raise ValueError('document_catalog_immutable')
    else:
        with path.open('x',encoding='utf8') as f:f.write(raw)
    return path


def load(root, manifest):
    path=Path(root)/'document-catalogs'/(identity(manifest)+'.json')
    if not path.exists():
        raise OrganizationSourceStorageUnavailable('document_catalog_not_published_prepare_metadata_offline_no_runtime_corpus_scan')
    try:
        saved=json.loads(path.read_text(encoding='utf8'));value=saved['value']
        if saved['digest']!=digest(value) or value['identity']!=identity(manifest):
            raise OrganizationSourceStorageUnavailable('document_catalog_publication_mismatch')
        return value['documents']
    except OrganizationSourceStorageUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError):
        raise OrganizationSourceStorageUnavailable('document_catalog_unreadable') from None


def publish_from_receipts(reader, root):
    """Deployment migration from existing proofs; never reads original bodies.

    Missing proofs require explicit publication preparation, not a live scan.
    """
    from .source_verification_cache import SourceVerificationCache, versions
    from .organization_search_cache import OrganizationSearchCache
    from contextlib import closing
    before, manifest, _ = reader._grant()
    observer = OrganizationSearchCache(reader.workspace.library.documents.path)
    try:
        revisions = versions(observer)
        proofs = SourceVerificationCache(root)
        descriptors = {}
        items = manifest['inputs']
        with closing(proofs.iter_get(proofs.key(revisions, i, manifest) for i in items)) as rows:
            for item, (_, saved) in zip(items, rows):
                if saved is None or saved['version']['ref'] != item['ref']:
                    raise ValueError('document_catalog_source_proof_missing_prepare_publication_offline')
                descriptors[item['resource_id']] = {'ref':item['ref'],
                    'metadata':saved['metadata'], 'original_metadata':saved['original_metadata']}
        if versions(observer) != revisions:
            raise ValueError('document_catalog_publication_changed')
        reader._after(before)
        return publish(root, manifest, descriptors)
    finally:
        observer.db.close()
