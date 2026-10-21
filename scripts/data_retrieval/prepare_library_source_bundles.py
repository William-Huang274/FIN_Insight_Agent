"""Offline source-preserving intake; no organization publication or provider calls."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

import numpy as np

from retrieval.library_source_bundle import build_source_bundle, reusable_vectors, text_digest
from retrieval.library_vectors import digest, ready_index


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


def prepare(library, index, source_ids, output):
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError('unique_nonempty_source_selection_required')
    library, index, output = Path(library).resolve(), Path(index).resolve(), Path(output).resolve()
    if any(output == root or output.is_relative_to(root) for root in (index, library.parent)):
        raise ValueError('output_must_not_modify_source_directory')
    # No overwrite: failed batches remain inspectable and require a new directory.
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='incomplete', provider_calls=0, sources=[], organization_published=False,
                  scope='complete selected parsed sources; not full-corpus or retrieval acceptance')
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
            for source_id in source_ids:
                record = dict(source_id=source_id, status='failed')
                try:
                    bundle = build_source_bundle(db, source_id, library_sha)
                    rows, vectors = reusable_vectors(bundle, manifest, matrix, mapping, cache)
                    folder = output / text_digest(source_id)[:32]
                    folder.mkdir()
                    dump(folder / 'source.json', bundle)
                    dump(folder / 'vector-map.json', rows)
                    np.save(folder / 'vectors.npy', vectors, allow_pickle=False)
                    record.update(status='verified', directory=folder.name,
                                  title=bundle['source']['title'], parsed_characters=len(bundle['text']),
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
    args = parser.parse_args()
    result = prepare(args.library, args.index, args.source_id, args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_index'}, ensure_ascii=False))
    if result['status'] != 'verified':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
