"""SQLite online snapshot plus immutable SEC originals; restore into a new root."""
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing


def _hash(path):
    return sha256(path.read_bytes()).hexdigest()


def backup_assets(source, target):
    source, target = Path(source).resolve(), Path(target).resolve()
    if target == source or target.is_relative_to(source):
        raise ValueError('backup_must_be_outside_source')
    if not (source / 'attachments.sqlite').is_file():
        raise ValueError('asset_database_missing')
    target.mkdir(parents=True, exist_ok=False)
    with closing(sqlite3.connect((source / 'attachments.sqlite').as_uri() + '?mode=ro', uri=True)) as src:
        with closing(sqlite3.connect(target / 'attachments.sqlite')) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('backup_database_invalid')
            rows = dst.execute('SELECT scope,version,body FROM project_sec_versions').fetchall() if dst.execute(
                "SELECT 1 FROM sqlite_master WHERE name='project_sec_versions'").fetchone() else []
    files = {'attachments.sqlite': _hash(target / 'attachments.sqlite')}
    for scope, version, body in rows:
        record = json.loads(body)
        if record['status'] != 'complete':
            continue
        relative = Path('sec-snapshots') / scope / version / 'raw' / record['ticker']
        folder = (source / relative).resolve()
        if not folder.is_relative_to(source):
            raise ValueError('snapshot_path_outside_source')
        for kind in ('sec_companyfacts', 'sec_submissions'):
            original = folder / (kind + '.json')
            expected = next(s['sha256'] for s in record['sources'] if s['kind'] == kind)
            if _hash(original) != expected:
                raise ValueError('snapshot_integrity_failure')
            # Metadata is needed to rebuild the original financial task mapping.
            for path in (original, folder / (kind + '.metadata.json')):
                destination = target / relative / path.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                files[destination.relative_to(target).as_posix()] = _hash(destination)
    manifest = {'schema_version': 'asset_backup.v1', 'files': files,
                'scope': 'project_assets_profiles_contexts_only', 'native_threads_included': False}
    (target / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def restore_assets(backup, target):
    backup, target = Path(backup).resolve(), Path(target).resolve()
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version') != 'asset_backup.v1' or 'attachments.sqlite' not in manifest['files']:
        raise ValueError('backup_protocol_invalid')
    for relative, digest in manifest['files'].items():
        path = (backup / relative).resolve()
        if not path.is_relative_to(backup) or not (target / relative).resolve().is_relative_to(target) or _hash(path) != digest:
            raise ValueError('backup_integrity_failure')
    if target == backup or target.is_relative_to(backup):
        raise ValueError('restore_must_be_outside_backup')
    with closing(sqlite3.connect((backup / 'attachments.sqlite').as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('backup_database_invalid')
    target.mkdir(parents=True, exist_ok=False)
    for relative in manifest['files']:
        path = target / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(backup / relative, path)
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('source')
    parser.add_argument('target', help='New directory; existing directories are never overwritten')
    args = parser.parse_args()
    result = (backup_assets if args.action == 'backup' else restore_assets)(args.source, args.target)
    print(json.dumps({'status': 'complete', 'files': len(result['files']), 'native_threads_included': False}))
