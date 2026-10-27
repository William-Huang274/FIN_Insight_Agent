"""Resume load after a completed HTTP quality phase, never resume old permissions.

Product source tree, built Java artifact, configuration, corpus/release binding,
and every quality artifact are checked. Harness-only repairs may differ and are
recorded; this is a staged run, not an uninterrupted same-version acceptance.
"""
from hashlib import file_digest, sha256
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PRODUCT_PATHS = ('src', 'apps', 'configs', 'deploy', 'pyproject.toml', 'uv.lock',
                 'tests/integration/source_intake_runtime.py')


def digest(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def product_tree(revision='HEAD'):
    tree = subprocess.check_output(['git', 'ls-tree', '-r', revision, '--', *PRODUCT_PATHS], cwd=ROOT)
    return sha256(tree).hexdigest()


def seal(root):
    root = Path(root).resolve(strict=True)
    quality = json.loads((root/'service-quality.json').read_bytes())
    baseline = json.loads((root.parent/'baseline.json').read_bytes())
    if quality['status'] != 'completed' or not quality['batch_quality_passed']:
        raise ValueError('quality_checkpoint_requires_completed_quality')
    expected = ['service-quality.json', 'retained-index-current-verification.json'] + [
        'service-quality-question-'+r['id']+'.json' for r in quality['rows']]
    if len(expected) != len(set(expected)):
        raise ValueError('quality_checkpoint_duplicate_questions')
    record = {'schema': 'retained-http-quality.v1', 'root': str(root),
        'source_git': baseline['git_head'], 'product_tree_sha256': product_tree(baseline['git_head']),
        'baseline': baseline, 'files': {name: digest(root/name) for name in expected}}
    target = root/'retained-http-quality.json'
    with target.open('x', encoding='utf8') as handle:
        json.dump(record, handle, indent=2)
    return target


def restore(path, *, binding, question_ids, manifest_digest, contract, baseline, save):
    record = json.loads(Path(path).read_bytes())
    if record.get('schema') != 'retained-http-quality.v1':
        raise ValueError('quality_checkpoint_schema')
    if record['product_tree_sha256'] != product_tree():
        raise ValueError('quality_checkpoint_product_changed')
    if subprocess.check_output(['git', 'status', '--porcelain', '--', *PRODUCT_PATHS], cwd=ROOT).strip():
        raise ValueError('quality_checkpoint_product_dirty')
    for key in ('jar_sha256', 'configuration', 'configuration_files'):
        if record['baseline'][key] != baseline[key]:
            raise ValueError('quality_checkpoint_configuration_changed')
    root = Path(record['root']).resolve(strict=True)
    expected = {'service-quality.json', 'retained-index-current-verification.json'} | {
        'service-quality-question-'+q+'.json' for q in question_ids}
    if set(record['files']) != expected:
        raise ValueError('quality_checkpoint_question_scope_changed')
    for name, expected_hash in record['files'].items():
        target = (root/name).resolve(strict=True)
        if target.parent != root or digest(target) != expected_hash:
            raise ValueError('quality_checkpoint_artifact_changed')
    quality = json.loads((root/'service-quality.json').read_bytes())
    verified = json.loads((root/'retained-index-current-verification.json').read_bytes())
    if (quality['status'] != 'completed' or not quality['batch_quality_passed']
            or quality['binding'] != binding or verified['status'] != 'passed'
            or verified['index_contract'] != contract
            or len(quality['rows']) != len(question_ids)
            or {r['id'] for r in quality['rows']} != set(question_ids)):
        raise ValueError('quality_checkpoint_binding_changed')
    for q in question_ids:
        result = json.loads((root/('service-quality-question-'+q+'.json')).read_bytes())['search']
        if result['source_snapshot_sha256'] != manifest_digest:
            raise ValueError('quality_checkpoint_manifest_changed')
    quality['resumed_evidence'] = {'source_git': record['source_git'], 'root': str(root),
        'product_tree_unchanged': True, 'interrupted_between_phases': True,
        'current_permissions_rechecked_separately': True, 'harness_git': baseline['git_head']}
    save('service-quality', quality)
    save('quality-phase-resume', quality['resumed_evidence'])
    return root, [r['request'] for r in quality['rows']]
