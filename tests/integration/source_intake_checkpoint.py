"""Publication fixture snapshots, restored only into a fresh qualification stack.

Not a production workflow resume or a permission lease. No credentials are saved.
The manifest is published last; incomplete snapshots and old progress files fail.
"""
from hashlib import file_digest
import json
from pathlib import Path
import shutil
import subprocess
import zipfile


FILES = ('attachments.sqlite', 'organization-assets/attachments.sqlite')


def digest(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def own_postgres(stack):
    ids = subprocess.check_output([stack.docker, 'ps', '-q', '--filter',
        'label=com.docker.compose.project=' + stack.project, '--filter',
        'label=com.docker.compose.service=postgres'], text=True, timeout=15).split()
    if len(ids) != 1:
        raise ValueError('checkpoint_requires_one_owned_postgres')
    row = json.loads(subprocess.check_output([stack.docker, 'inspect', ids[0]],
                                            text=True, timeout=15))[0]
    labels = row['Config']['Labels']
    if (labels.get('com.docker.compose.project') != stack.project
            or labels.get('com.docker.compose.service') != 'postgres'
            or not stack.project.startswith('fin-intake-native-')):
        raise ValueError('checkpoint_postgres_ownership_mismatch')
    return row['Id']


def pack_assets(root, destination):
    root = Path(root)
    # Caller must first stop its BFF and Java writers. Never copy a live WAL DB.
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('checkpoint_asset_symlink')
        if path.is_file() and path.relative_to(root).as_posix() not in FILES:
            if not path.name.endswith(('-wal', '-shm')) or path.stat().st_size:
                raise ValueError('checkpoint_assets_not_quiescent_or_unknown')
    records = {name: {'sha256': digest(root/name), 'bytes': (root/name).stat().st_size}
               for name in FILES}
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=1) as archive:
        for name in FILES:
            archive.write(root/name, name)
    if any(digest(root/name) != record['sha256'] for name, record in records.items()):
        raise ValueError('checkpoint_assets_changed_during_pack')
    return records


def unpack_assets(archive_path, root, records):
    root = Path(root)
    if set(records) != set(FILES):
        raise ValueError('checkpoint_asset_manifest_mismatch')
    if any(root.rglob('*.sqlite')):
        raise ValueError('checkpoint_restore_requires_empty_assets')
    required = sum(r['bytes'] for r in records.values())
    if shutil.disk_usage(root).free < required + 512 * 2**20:
        raise ValueError('checkpoint_restore_disk_headroom')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if len(entries) != len(FILES) or {r.filename for r in entries} != set(FILES):
            raise ValueError('checkpoint_archive_members_mismatch')
        for item in entries:
            record = records[item.filename]
            if item.file_size != record['bytes']:
                raise ValueError('checkpoint_archive_size_mismatch')
            path = root/item.filename  # Exact whitelist; never extract arbitrary paths.
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError('checkpoint_restore_path_escape')
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, path.open('xb') as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if digest(path) != record['sha256']:
                raise ValueError('checkpoint_restored_asset_digest_mismatch')


def load_checkpoint(path, binding):
    path = Path(path).resolve()
    manifest = json.loads((path/'manifest.json').read_text(encoding='utf8'))
    if (manifest.get('schema') != 'source-publication-checkpoint.v1'
            or manifest.get('binding') != binding):
        raise ValueError('checkpoint_baseline_or_scope_mismatch')
    payload = manifest['publication']
    ids = [row['source_id'] for row in payload['captures']]
    expected = binding['source_ids'][:len(ids)]
    if (not ids or ids != expected or len(set(ids)) != len(ids)
            or set(payload['resources']) != set(ids) or set(payload['grants']) != set(ids)
            or len(payload['source_refs']) != len(ids)
            or len(set(payload['resources'].values())) != len(ids)
            or len({ref['version_id'] for ref in payload['source_refs']}) != len(ids)):
        raise ValueError('checkpoint_publication_scope_mismatch')
    if set(manifest['artifacts']) != {'assets.zip', 'business.dump'}:
        raise ValueError('checkpoint_artifact_manifest_mismatch')
    for name, expected_hash in manifest['artifacts'].items():
        if digest(path/name) != expected_hash:
            raise ValueError('checkpoint_artifact_digest_mismatch')
    return manifest


def save_checkpoint(stack, binding, publication):
    # Only an explicit safe boundary, not a finally-block guessing whether the
    # last HTTP request committed. Existing failed output directories stay intact.
    for process in stack.processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=20)
    output = stack.output/'publication-checkpoint'
    output.mkdir(exist_ok=False)
    container = own_postgres(stack)
    with (output/'business.dump').open('xb') as target:
        subprocess.run([stack.docker, 'exec', container, 'pg_dump', '-U', 'probe',
            '-d', 'business', '-Fc', '--no-owner', '--no-acl'], stdout=target,
            stderr=subprocess.PIPE, check=True, timeout=120)
    files = pack_assets(stack.state/'project-library', output/'assets.zip')
    manifest = {'schema': 'source-publication-checkpoint.v1', 'binding': binding,
        'origin_attempt': str(stack.output), 'origin_postgres': container,
        'publication': publication, 'asset_files': files,
        'artifacts': {name: digest(output/name) for name in ('assets.zip', 'business.dump')},
        'scope': 'isolated fixture snapshot; recheck current restored authority, not production resume'}
    # One final commit marker; consumers never trust a progress count.
    marker = output/'manifest.pending'
    marker.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    marker.replace(output/'manifest.json')
    return output


def restore_checkpoint(stack, path, manifest):
    if load_checkpoint(path, manifest['binding']) != manifest:
        raise ValueError('checkpoint_changed_before_restore')
    container = own_postgres(stack)
    if container == manifest['origin_postgres']:
        raise ValueError('checkpoint_must_restore_into_fresh_postgres')
    # No Java/BFF has booted and business was just created by this new stack.
    unpack_assets(Path(path)/'assets.zip', stack.state/'project-library', manifest['asset_files'])
    with (Path(path)/'business.dump').open('rb') as source:
        subprocess.run([stack.docker, 'exec', '-i', container, 'pg_restore', '-U', 'probe',
            '-d', 'business', '--no-owner', '--no-acl', '--exit-on-error', '--single-transaction'],
            stdin=source, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=120)
