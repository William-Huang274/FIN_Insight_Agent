"""Copy sealed qualification data into a new environment; never adopt its DB."""
import json
import os
from pathlib import Path
import shutil
import subprocess

from tests.integration.source_intake_retained import digest
from tests.integration.source_intake_checkpoint import own_postgres


def copy_publication(stack, publication_path, index_path):
    archive = Path(publication_path).resolve(strict=True)
    seal = json.loads(archive.read_bytes())
    release = json.loads(Path(index_path).read_bytes())
    if seal['schema'] != 'retained-source-publication.v1' or release['schema'] != 'retained-http-index.v1':
        raise ValueError('unsupported_frozen_publication')
    if any(seal[k] != release[k] for k in ('intake_sha256', 'geometry_sha256')):
        raise ValueError('publication_index_scope_mismatch')
    expected = {'state/project-library/attachments.sqlite', 'state/project-library/organization-assets/attachments.sqlite',
                'business-after-publication.dump', 'complete-source-publication-progress.json'}
    if set(seal['files']) != expected or set(release['files']) != {'index.json','vectors.npy','lexical.sqlite','navigation.sqlite','graph.sqlite'}:
        raise ValueError('unexpected_copy_manifest')
    from uuid import UUID
    relative = Path(str(UUID(release['organization_id']))) / 'releases' / str(UUID(release['contract']['release_id']))
    targets = [(archive.parent / name, stack.output / name, sha) for name, sha in seal['files'].items()]
    targets += [(Path(release['index_root']) / relative / name, stack.output / 'indices' / relative / name, sha)
                for name, sha in release['files'].items()]
    reuse = os.getenv('FIN_QUALIFICATION_REUSE_COPY')
    if reuse:
        root = Path(reuse).resolve(strict=True)
        receipt = json.loads((root/'independent-copy.json').read_bytes())
        previous = json.loads((root/'environment.json').read_bytes())
        if (root.parent != stack.output.parent or root == stack.output or not previous['project'].startswith('fin-intake-native-')
                or receipt['source_publication_seal'] != digest(archive)
                or receipt['source_index_seal'] != digest(index_path)):
            raise ValueError('reuse_requires_same_owned_independent_copy')
        active = subprocess.check_output([stack.docker,'ps','-q','--filter',
            'label=com.docker.compose.project='+previous['project']], text=True).strip()
        if active:
            raise ValueError('copy_in_use')
        targets = [(root / target.relative_to(stack.output), target, sha) for _, target, sha in targets]
    required = sum(a.stat().st_size for a, _, _ in targets)
    if shutil.disk_usage(stack.output).free < (0 if reuse else required) + 1024**3:
        raise ValueError('insufficient_independent_copy_space')
    checked = []
    for source, target, sha in targets:
        if source.resolve() == target.resolve() or target.exists():
            raise ValueError('copy_requires_fresh_destination')
        if digest(source) != sha:
            raise ValueError('sealed_source_changed')
        target.parent.mkdir(parents=True, exist_ok=True)
        # Only already independent, stopped qualification copies may be linked.
        # Never hard-link the sealed archive or its original publication files.
        if reuse:
            os.link(source, target)
        else:
            shutil.copyfile(source, target)
        if digest(target) != sha:
            raise ValueError('independent_copy_digest_mismatch')
        checked.append({'file': str(target.relative_to(stack.output)), 'sha256': sha, 'bytes': target.stat().st_size})
    stack.save('independent-copy', {'status':'passed', 'files':checked, 'bytes':required,
        'source_publication_seal':digest(archive), 'source_index_seal':digest(index_path),
        'origin_database_started':False, 'origin_archive_written':False,
        'reused_owned_copy':str(root) if reuse else None})
    return release


def restore_business(stack):
    container = own_postgres(stack)
    with (stack.output / 'business-after-publication.dump').open('rb') as source:
        result = subprocess.run([stack.docker,'exec','-i',container,'pg_restore','-U','probe','-d','business',
            '--no-owner','--no-acl','--exit-on-error','--single-transaction'], stdin=source,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
    if result.returncode:
        raise RuntimeError('isolated_business_restore_failed')
