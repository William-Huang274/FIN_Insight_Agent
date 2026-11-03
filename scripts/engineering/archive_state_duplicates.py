"""Deduplicate exact historical files in a standard ZIP with old-path restore.

Build/verify never delete originals. A verified retirement list is an operator
artifact, not permission to remove whole run directories. Restore refuses to
overwrite changed files or traverse links outside the requested root.
"""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import zipfile


def digest_stream(stream):
    h = sha256()
    size = 0
    for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
        h.update(chunk)
        size += len(chunk)
    return h.hexdigest(), size


def bounded(root, relative):
    rel = PurePosixPath(relative)
    if rel.is_absolute() or '..' in rel.parts or '\\' in relative or ':' in relative:
        raise ValueError('archive_relative_path_invalid')
    result = (root / relative).resolve()
    if not result.is_relative_to(root.resolve()) or result == root.resolve():
        raise ValueError('archive_path_outside_root')
    return result


def build(root, groups_path, archive):
    root, archive = Path(root).resolve(), Path(archive).resolve()
    if archive.exists():
        raise FileExistsError(archive)
    groups = json.loads(Path(groups_path).read_text(encoding='utf-8-sig'))['groups']
    manifest = {'format': 'fin.exact-state-archive.v1', 'source_root': str(root), 'files': []}
    archive.parent.mkdir(parents=True, exist_ok=True)
    temp = archive.with_suffix('.building.zip')
    if temp.exists():
        raise FileExistsError(temp)
    seen = set()
    with zipfile.ZipFile(temp, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for group in groups:
            source = Path(group['retained_original']).resolve()
            relative = source.relative_to(root).as_posix()
            source = bounded(root, relative)
            key = group['sha256']
            entry = 'objects/' + key
            if key not in seen:
                with source.open('rb') as src, z.open(entry, 'w', force_zip64=True) as dst:
                    h, size = sha256(), 0
                    for block in iter(lambda: src.read(4 * 1024 * 1024), b''):
                        dst.write(block); h.update(block); size += len(block)
                if h.hexdigest() != key or size != group['bytes']:
                    raise ValueError('archive_source_changed:' + str(source))
                seen.add(key)
            for member in group['members']:
                p = Path(member['path']).resolve()
                rel = p.relative_to(root).as_posix()
                bounded(root, rel)
                # Preserve the selected canonical copy and latest delivery in
                # place. The archive can restore every other legacy exact path.
                retire = p != source and rel.split('/')[0] not in {'live-native140', 'delivery-reviewed'}
                manifest['files'].append({'path': rel, 'sha256': key, 'bytes': group['bytes'],
                                          'object': entry, 'retire_candidate': retire})
        z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    verify(temp)
    os.replace(temp, archive)
    return manifest


def verify(archive, *, check_originals=False, allow_missing_originals=False):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        if manifest['format'] != 'fin.exact-state-archive.v1':
            raise ValueError('archive_format_invalid')
        unique = {f['object']: f for f in manifest['files']}
        for name, row in unique.items():
            with z.open(name) as src:
                actual = digest_stream(src)
            if actual != (row['sha256'], row['bytes']):
                raise ValueError('archive_object_corrupt:' + name)
        verified_ids = {}
        missing = []
        if check_originals:
            for row in manifest['files']:
                p = bounded(Path(manifest['source_root']), row['path'])
                if not p.exists() and allow_missing_originals:
                    missing.append(row['path'])
                    continue
                s = p.stat()
                identity = (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
                if identity not in verified_ids:
                    with p.open('rb') as src:
                        verified_ids[identity] = digest_stream(src)
                if verified_ids[identity] != (row['sha256'], row['bytes']):
                    raise ValueError('archive_original_changed:' + row['path'])
        return {'objects': len(unique), 'paths': len(manifest['files']),
                'retire_candidates': sum(f['retire_candidate'] for f in manifest['files']),
                'originals_checked': check_originals, 'missing_originals': missing,
                'status': 'verified_existing_originals_missing_listed' if missing else 'verified'}


def restore(archive, relative, *, target_root=None):
    with zipfile.ZipFile(archive) as z:
        manifest = json.loads(z.read('manifest.json'))
        rows = [f for f in manifest['files'] if f['path'] == relative]
        if len(rows) != 1:
            raise ValueError('archive_path_not_unique_or_missing')
        row = rows[0]
        root = Path(target_root or manifest['source_root']).resolve()
        dest = bounded(root, relative)
        if dest.exists():
            with dest.open('rb') as src:
                if digest_stream(src) != (row['sha256'], row['bytes']):
                    raise ValueError('restore_refuses_changed_original')
            return str(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as tmp:
            temp = Path(tmp.name)
            with z.open(row['object']) as src:
                shutil.copyfileobj(src, tmp, length=4 * 1024 * 1024)
            tmp.flush(); os.fsync(tmp.fileno())
        try:
            with temp.open('rb') as src:
                if digest_stream(src) != (row['sha256'], row['bytes']):
                    raise ValueError('restore_digest_mismatch')
            # Hard-link publication is atomic and cannot replace a concurrently
            # created file. The temporary name is unlinked after publication.
            os.link(temp, dest)
        finally:
            temp.unlink(missing_ok=True)
        return str(dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    b = sub.add_parser('build'); b.add_argument('--root', required=True); b.add_argument('--groups', required=True); b.add_argument('--archive', required=True)
    v = sub.add_parser('verify'); v.add_argument('--archive', required=True); v.add_argument('--check-originals', action='store_true'); v.add_argument('--allow-missing-originals', action='store_true')
    r = sub.add_parser('restore'); r.add_argument('--archive', required=True); r.add_argument('--path', required=True); r.add_argument('--target-root')
    args = vars(p.parse_args()); command = args.pop('command')
    if command == 'build':
        result = build(args['root'], args['groups'], args['archive'])
        result = {'status': 'built_verified_no_originals_deleted', 'paths': len(result['files'])}
    elif command == 'verify':
        result = verify(**args)
    else:
        result = {'restored': restore(args['archive'], args['path'], target_root=args['target_root'])}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
