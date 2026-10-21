"""Build immutable parser receipts from explicitly allowed local archive roots."""
import argparse
from contextlib import closing
from importlib.metadata import version
import json
from pathlib import Path
import sqlite3

from retrieval.library_archive_recovery import CATALOG, create_receipt
from retrieval.library_vectors import digest


def prepare(library, source_ids, archive_roots, output):
    library, output = Path(library).resolve(), Path(output).resolve()
    roots = [Path(root).resolve() for root in archive_roots]
    if not roots or not source_ids or len(set(source_ids)) != len(source_ids):
        raise ValueError('explicit_unique_sources_and_archive_roots_required')
    if output.is_relative_to(library.parent) or any(output.is_relative_to(root) for root in roots):
        raise ValueError('recovery_output_must_be_independent')
    output.mkdir(parents=True, exist_ok=False)
    manifest = dict(format=CATALOG, status='incomplete', library_sha256=digest(library), sources={},
                    parser_versions={name:version(name) for name in ('beautifulsoup4','pypdf')},
                    provider_calls=0, organization_authorization=False)
    def save():
        (output/'catalog.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    save()
    try:
        with closing(sqlite3.connect(library.as_uri()+'?mode=ro', uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute('BEGIN')
            for sid in source_ids:
                found = db.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
                if found is None:
                    raise ValueError('archive_source_missing')
                source = dict(found)
                archive = Path(json.loads(source['metadata'])['archive']).resolve()
                if not any(archive.is_relative_to(root) for root in roots):
                    raise ValueError('archive_outside_allowed_roots')
                parents = [dict(row) for row in db.execute('SELECT * FROM passages WHERE source_id=?',(sid,))]
                receipt = create_receipt(source, parents, manifest['library_sha256'], archive)
                raw = json.dumps(receipt,ensure_ascii=False,indent=2).encode('utf8')
                from hashlib import sha256
                receipt_hash = sha256(raw).hexdigest()
                (output/(receipt_hash+'.json')).write_bytes(raw)
                manifest['sources'][sid] = dict(sha256=receipt_hash, raw_sha256=source['digest'],
                                                parser=receipt['parser'], pages=len(receipt['pages']))
                save()
        if digest(library) != manifest['library_sha256']:
            raise ValueError('archive_library_changed_during_replay')
        manifest['status'] = 'verified'
    except Exception as exc:
        manifest.update(status='failed', error_type=type(exc).__name__, error=str(exc))
        save()
        raise
    save()
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--source-id', action='append', required=True)
    parser.add_argument('--archive-root', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.library,args.source_id,args.archive_root,args.output)
    print(json.dumps(dict(status=result['status'], sources=len(result['sources']),
                         catalog_sha256=digest(args.output/'catalog.json'), provider_calls=0)))


if __name__ == '__main__':
    main()
