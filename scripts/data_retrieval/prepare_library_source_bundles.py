"""Offline source-preserving intake; no organization publication or provider calls."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

import numpy as np

from retrieval.library_source_bundle import build_source_bundle, VectorReuseVerifier, text_digest
from retrieval.library_vectors import digest, ready_index


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(library, index, source_ids, output, recovery_catalog=None, node_catalog=None):
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError('unique_nonempty_source_selection_required')
    library, index, output = Path(library).resolve(), Path(index).resolve(), Path(output).resolve()
    if any(output == root or output.is_relative_to(root) for root in (index, library.parent)):
        raise ValueError('output_must_not_modify_source_directory')
    # No overwrite: failed batches remain inspectable and require a new directory.
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='incomplete', provider_calls=0, sources=[], organization_published=False,
                  scope='selected parsed texts or indexed node sets as typed per source; not full-corpus or retrieval acceptance')
    dump(output / 'result.json', report)
    try:
        library_sha = digest(library)
        manifest, matrix, mapping = ready_index(index, library_sha)
        report['library_sha256'] = library_sha
        report['source_index'] = manifest
        with closing(sqlite3.connect(library.as_uri() + '?mode=ro', uri=True)) as db, closing(
                sqlite3.connect((index / 'chunk-embeddings.sqlite').as_uri() + '?mode=ro', uri=True)) as cache:
            db.row_factory = sqlite3.Row
            # Keep a coherent read snapshot. Source hash is checked again before success.
            db.execute('BEGIN')
            cache.execute('BEGIN')
            verifier = VectorReuseVerifier(manifest, matrix, mapping, cache)
            for source_id in source_ids:
                record = dict(source_id=source_id, status='failed')
                try:
                    bundle = build_source_bundle(db, source_id, library_sha, recovery_catalog, node_catalog)
                    rows, vectors = verifier.verify(bundle)
                    folder = output / text_digest(source_id)[:32]
                    folder.mkdir()
                    dump(folder / 'source.json', bundle)
                    dump(folder / 'vector-map.json', rows)
                    np.save(folder / 'vectors.npy', vectors, allow_pickle=False)
                    record.update(status='verified', directory=folder.name,
                                  text_scope='indexed_node_directory' if 'node_recovery' in bundle else 'parsed_source_text',
                                  indexed_node_characters=sum(len(p['body']) for p in bundle['parents']) if 'node_recovery' in bundle else None,
                                  title=bundle['source']['title'], parsed_characters=None if 'node_recovery' in bundle else len(bundle['text']),
                                  directory_characters=len(bundle['text']) if 'node_recovery' in bundle else None,
                                  source_digest=bundle['source']['digest'], parents=len(bundle['parents']),
                                  chunks=len(bundle['chunks']), edges=len(bundle['edges']),
                                  edge_links=len(bundle['edge_chunk_links']),
                                  reused_vectors=len(rows), files={name: digest(folder / name) for name in
                                      ('source.json', 'vector-map.json', 'vectors.npy')})
                except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                    record.update(error_type=type(exc).__name__, error=str(exc))
                report['sources'].append(record)
                dump(output / 'result.json', report)
        if digest(library) != library_sha:
            raise ValueError('source_library_changed_during_export')
        # ready_index rechecks file identities and hashes after export.
        final_manifest, _, _ = ready_index(index, library_sha)
        if final_manifest != manifest:
            raise ValueError('source_vector_index_changed_during_export')
        report['status'] = 'verified' if all(r['status'] == 'verified' for r in report['sources']) else 'failed'
    except Exception as exc:
        report.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        dump(output / 'result.json', report)
        raise
    dump(output / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--source-id', action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--recovery-catalog', type=Path)
    parser.add_argument('--recovery-sha256')
    parser.add_argument('--node-catalog',type=Path)
    parser.add_argument('--node-sha256')
    args = parser.parse_args()
    from retrieval.library_archive_recovery import ArchiveRecoveryCatalog
    if bool(args.recovery_catalog) != bool(args.recovery_sha256):
        parser.error('recovery catalog and SHA256 must be supplied together')
    catalog = ArchiveRecoveryCatalog(args.recovery_catalog, args.recovery_sha256) if args.recovery_catalog else None
    from retrieval.library_node_recovery import NodeRecoveryCatalog
    if bool(args.node_catalog)!=bool(args.node_sha256):parser.error('node catalog and SHA256 must be supplied together')
    nodes=NodeRecoveryCatalog(args.node_catalog,args.node_sha256) if args.node_catalog else None
    result = prepare(args.library, args.index, args.source_id, args.output, catalog, nodes)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_index'}, ensure_ascii=False))
    if result['status'] != 'verified':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
