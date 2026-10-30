"""Explicit host maintenance for the retired code-hash receipt identity.

Not invoked by requests. An operator must first review that the old projection,
admission and release proof semantics match the target contracts. Only exact
current-scope legacy receipts are copied; missing proofs are reported, never
replaced by a corpus scan. Original rows and research state are untouched.
"""
from contextlib import closing
from pathlib import Path
import sqlite3
import zlib
from hashlib import sha256

from .organization_hybrid_retrieval import digest
from .organization_input_integrity import proof_scope
from .organization_index_release import ReleaseLoadCache, release_verification_key, canonical_digest
from .organization_search_cache import OrganizationSearchCache
from .source_verification_cache import FORMAT, SourceVerificationCache, versions


def migrate_code_hash_receipts(workspace, manifest, inputs, root, *, reviewed_legacy, apply=False, layers=("sources", "admission", "release")):
    layers = frozenset(layers)
    if not layers or not layers <= {'sources', 'admission', 'release'}:
        raise ValueError('receipt_migration_layers_invalid')
    required = {'source_revision', 'source_code', 'admission_code', 'release_loader', 'vector_validator'}
    if set(reviewed_legacy) != required or not reviewed_legacy['source_revision']:
        raise ValueError('receipt_migration_requires_reviewed_legacy_contract')
    for field in required - {'source_revision'}:
        value = reviewed_legacy[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('receipt_migration_legacy_digest_invalid')
    store = workspace.library.documents
    observer = OrganizationSearchCache(store.path)
    source_cache, admission_cache = SourceVerificationCache(root), SourceVerificationCache(store.root)
    org, cutoff, contract = manifest['organization_id'], manifest['research_as_of'], manifest['retrieval_index']
    directory = Path(root).resolve()/org/'releases'/contract['release_id']
    try:
        epoch, revision = observer.epoch(), versions(observer)
        if revision is None:
            raise ValueError('receipt_migration_revision_tracking_unavailable')
        scope = proof_scope(workspace, org, inputs, cutoff, contract, root, revision)
        if scope is None:
            raise ValueError('receipt_migration_source_revision_unavailable')
        identity, checked, _, signature = scope
        legacy_admission = dict(identity)
        del legacy_admission['proof_contract'], legacy_admission['source_contract']
        legacy_admission.update(code=reviewed_legacy['admission_code'], source_code=reviewed_legacy['source_code'])
        old_admission = admission_cache.get(digest(legacy_admission))
        new_admission = admission_cache.get(digest(identity))
        expected = {'checked':checked}
        for value in (old_admission, new_admission):
            if value is not None and value != expected:
                raise ValueError('receipt_migration_admission_mismatch')
        old_release_key = canonical_digest({'directory':str(directory), 'signature':signature,
            'expected':contract, 'loader':reviewed_legacy['release_loader'],
            'vector_validator':reviewed_legacy['vector_validator']})
        new_release_key = release_verification_key(directory, signature, contract)
        release_db = Path(root)/'verified-releases.sqlite'
        with closing(sqlite3.connect(f'{release_db.as_uri()}?mode=ro', uri=True)) as db:
            release_hit = bool(db.execute('SELECT 1 FROM verified WHERE key IN (?,?)',
                                         (old_release_key, new_release_key)).fetchone())
        counts = {'sources':len(manifest['inputs']), 'existing_sources':0, 'legacy_sources':0,
                  'missing_sources':0, 'admission_available':old_admission is not None or new_admission is not None,
                  'release_available':release_hit, 'applied':False,
                  'reviewed_revision':reviewed_legacy['source_revision'], 'layers':sorted(layers)}
        # Preserve the exact compressed payload. Migration checks its digest but
        # does not parse/rebuild every source's navigation trees or metadata.
        with closing(sqlite3.connect(source_cache.path, timeout=10)) as db, db:
            for item in manifest['inputs'] if 'sources' in layers else []:
                target_key = source_cache.key(revision, item, manifest)
                token = revision['tokens'].get(item['ref']['version_id'])
                old_key = digest({'format': FORMAT, 'code': reviewed_legacy['source_code'],
                    'store': revision['store'], 'token': token, 'item': item, 'organization_id': org,
                    'research_as_of': cutoff, 'index': contract}) if token else None
                row = db.execute('SELECT payload,digest FROM receipts WHERE key=?',(target_key,)).fetchone()
                existed = row is not None
                if row is None:
                    row = db.execute('SELECT payload,digest FROM receipts WHERE key=?',(old_key,)).fetchone()
                if row is None:
                    counts['missing_sources'] += 1
                    continue
                raw = zlib.decompress(row[0]) if isinstance(row[0],bytes) else row[0].encode()
                if sha256(raw).hexdigest() != row[1]:
                    raise ValueError('organization_source_receipt_corrupt')
                del raw
                counts['existing_sources' if existed else 'legacy_sources'] += 1
                if apply and not existed:
                    db.execute('INSERT INTO receipts VALUES(?,?,?)',(target_key,*row))
            if observer.epoch() != epoch or ReleaseLoadCache._signature(directory) != signature:
                raise ValueError('receipt_migration_scope_changed')
            if apply and (counts['missing_sources'] or ('admission' in layers and not counts['admission_available'])
                          or ('release' in layers and not release_hit)):
                raise ValueError('receipt_migration_required_proof_missing')
        if apply:
            if 'admission' in layers and new_admission is None:
                admission_cache.put(digest(identity), old_admission)
            if 'release' in layers:
                with closing(sqlite3.connect(release_db)) as db, db:
                    db.execute('INSERT OR IGNORE INTO verified VALUES(?)', (new_release_key,))
            counts['applied'] = True
        return counts
    finally:
        observer.db.close()
