"""Short-lived full-scope verifier; release its metadata before HTTP load."""
import json
import os
import subprocess
import sys


def verify(options):
    from pathlib import Path
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionAuthority, OrganizationExecutionReader
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    reader = OrganizationExecutionReader(AssetWorkspace(Path(options['assets'])),
        OrganizationExecutionAuthority(base_url=options['java_url'], secret=options['runtime_secret'],
            execution_id=options['execution'], manifest_digest=options['manifest_digest']))
    before, manifest, _ = reader._grant()
    if len(manifest['inputs']) != options['sources'] or manifest['retrieval_index'] != options['contract']:
        raise ValueError('warm_worker_scope_changed')
    nav = OrganizationSourceNavigation(reader, workbench_url='http://localhost', retrieval_root=Path(options['indices']))
    if nav.warm_release() != options['contract']:
        raise ValueError('warm_worker_contract_changed')
    candidate = nav._candidate_index
    if (candidate.original_reads + candidate.verification_hits != options['sources']
            or len(candidate.rows) != options['chunks']):
        raise ValueError('warm_worker_incomplete_scope')
    reader._after(before)
    return {'status': 'passed', 'sources': options['sources'], 'chunks': options['chunks'],
        'original_reads': candidate.original_reads, 'verified_receipt_hits': candidate.verification_hits,
        'current_permissions_rechecked': True, 'index_contract': options['contract'],
        'verification_process_exits_before_load': True}


def run(options):
    env = dict(os.environ)
    env.pop('QWEN_API_KEY', None)
    result = subprocess.run([sys.executable, '-m', 'tests.integration.source_intake_warm'],
        input=json.dumps(options), text=True, encoding='utf8', capture_output=True, env=env, timeout=900)
    # No config/body/secret or raw child diagnostics in the parent error.
    if result.returncode:
        raise RuntimeError('full_scope_verification_child_failed')
    record = json.loads(result.stdout)
    if record.get('status') != 'passed':
        raise ValueError('full_scope_verification_child_incomplete')
    return record


if __name__ == '__main__':
    try:
        print(json.dumps(verify(json.load(sys.stdin))))
    except BaseException as error:
        print(json.dumps({'status': 'failed', 'error_type': type(error).__name__}))
        sys.exit(1)
