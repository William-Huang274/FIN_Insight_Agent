"""Explicit reuse of this task's stopped publication fixture, never shared services.

The input seal identifies exact SQLite files and the stopped Compose container.
Current Java permissions and every original are checked again. This is fixture
replay across recorded code versions, not an uninterrupted same-version pass.
"""
from hashlib import file_digest
import json
from pathlib import Path
import subprocess

import psycopg


def digest(path):
    with Path(path).open('rb') as handle:
        return file_digest(handle, 'sha256').hexdigest()


def adopt(stack, path, *, intake_sha256, geometry_sha256):
    seal_path = Path(path).resolve(strict=True)
    seal = json.loads(seal_path.read_bytes())
    root = seal_path.parent
    if seal.get('schema') != 'retained-source-publication.v1':
        raise ValueError('retained_publication_schema')
    if seal.get('intake_sha256') != intake_sha256 or seal.get('geometry_sha256') != geometry_sha256:
        raise ValueError('retained_publication_input_scope_changed')
    old = json.loads((root/'environment.json').read_bytes())
    if not old['project'].startswith('fin-intake-native-'):
        raise ValueError('retained_publication_not_owned_fixture')
    for relative, expected in seal['files'].items():
        if relative not in {'state/project-library/attachments.sqlite',
                            'state/project-library/organization-assets/attachments.sqlite',
                            'complete-source-publication-progress.json', 'business-after-publication.dump'}:
            raise ValueError('retained_publication_path_not_allowed')
        if not (root/relative).resolve().is_relative_to(root) or digest(root/relative) != expected:
            raise ValueError('retained_publication_changed')
    if len(seal['files']) != 4:
        raise ValueError('retained_publication_incomplete_seal')
    import psutil
    for service in ('java', 'bff'):
        resource = json.loads((root/(service+'-fixed-process-resources.json')).read_bytes())
        if psutil.pid_exists(resource['pid']):
            raise ValueError('retained_publication_process_still_present')
    row = json.loads(subprocess.check_output([stack.docker, 'inspect', seal['container_id']], text=True, timeout=15))[0]
    labels = row['Config']['Labels']
    if (row['State']['Running'] or labels.get('com.docker.compose.project') != old['project']
            or labels.get('com.docker.compose.service') != 'postgres'):
        raise ValueError('retained_publication_running_or_foreign_container')
    networks = list(row['NetworkSettings']['Networks'])
    if len(networks) != 1: raise ValueError('retained_publication_network_ambiguous')
    network = json.loads(subprocess.check_output([stack.docker, 'network', 'inspect', networks[0]], text=True, timeout=15))[0]
    subnet = network['IPAM']['Config'][0]['Subnet']
    values = dict(item.split('=', 1) for item in row['Config']['Env'])
    lease = root/'retained-publication.lease'
    with lease.open('x', encoding='utf8') as handle: handle.write(str(stack.output))
    stack.retained_lease = lease
    stack.project, stack.pg_port = old['project'], old['ports']['postgres']
    stack.password = values['POSTGRES_PASSWORD']
    stack.redactions.append(stack.password)
    stack.state = root/'state'
    stack.env.update(FIN_PROBE_SUBNET=subnet, FIN_PROBE_PG_PORT=str(stack.pg_port),
        FIN_PROBE_PASSWORD=stack.password, FINSIGHT_BUSINESS_DB_PASSWORD=stack.password,
        FINSIGHT_BUSINESS_JDBC_URL=f'jdbc:postgresql://127.0.0.1:{stack.pg_port}/business',
        FINSIGHT_LOCAL_STATE_ROOT=str(stack.state),
        FIN_PROBE_ORGANIZATION_ASSETS=(stack.state/'project-library'/'organization-assets').as_posix(),
        FIN_COMPLETE_SOURCE_HTTP_EVIDENCE_ROOT=str(stack.output))
    record = json.loads((stack.output/'environment.json').read_bytes())
    record.update(project=stack.project, retained_publication_origin=str(root),
                  retained_publication_source_git=old['git_head'], retained_seal_sha256=digest(seal_path))
    record['ports']['postgres'] = stack.pg_port
    stack.save('environment', record)
    stack.save('retained-publication', {'status': 'adopted_stopped_owned_fixture',
        'origin': str(root), 'source_git': old['git_head'], 'seal_sha256': digest(seal_path),
        'cross_baseline_fixture_replay': True, 'permissions_not_cached': True})
    return {'root': root, 'seal': seal, 'source_git': old['git_head']}


def recover(stack, retained, api, assets, bundles):
    from sec_agent.research_foundation.asset_workspace import AssetWorkspace
    with psycopg.connect(host='127.0.0.1', port=stack.pg_port, dbname='business',
                         user='probe', password=stack.password) as db:
        organizations = db.execute('SELECT id FROM resource_organization').fetchall()
        spaces = db.execute("SELECT id FROM resource_space WHERE kind='team'").fetchall()
        projects = db.execute('SELECT id FROM organization_project').fetchall()
        bindings = db.execute('SELECT id,binding FROM space_resource WHERE active').fetchall()
    if any(len(rows) != 1 for rows in (organizations, spaces, projects)) or len(bindings) != len(bundles):
        raise ValueError('retained_publication_scope_changed')
    org, space, project = (str(rows[0][0]) for rows in (organizations, spaces, projects))
    private_projects = assets.library.index('oidc:alice')['projects']
    if len(private_projects) != 1: raise ValueError('retained_private_scope_changed')
    private = private_projects[0]['id']
    shared = AssetWorkspace(stack.state/'project-library'/'organization-assets')
    refs = {}
    for item in assets.catalog('oidc:alice', private)['items']:
        for version in item['versions']:
            bundle = assets.read_source('oidc:alice', version['ref'])['source_bundle']
            sid = bundle['source']['id']
            if sid in refs or bundle != bundles[sid]: raise ValueError('retained_private_original_changed')
            refs[sid] = version['ref']
    resources = {}
    for rid, binding in bindings:
        rid = str(rid)
        grant = api('POST', f'/projects/{project}/resources/{rid}/access')
        if grant['binding'] != binding: raise ValueError('retained_binding_changed')
        bundle = shared.read_source('organization:'+org, binding['ref'])['source_bundle']
        sid = bundle['source']['id']
        if sid in resources or bundle != bundles[sid]: raise ValueError('retained_organization_original_changed')
        if api('POST', f'/projects/{project}/resources/{rid}/access') != grant:
            raise ValueError('retained_authority_changed_during_read')
        resources[sid] = rid
    captures = json.loads((retained['root']/'complete-source-publication-progress.json').read_bytes())['sources']
    if [r['source_id'] for r in captures] != list(bundles) or set(refs) != set(bundles) or set(resources) != set(bundles):
        raise ValueError('retained_source_coverage_mismatch')
    stack.save('retained-publication-verified', {'status': 'passed', 'sources': len(bundles),
        'scope': 'current Java grants and both exact stored originals compared to immutable intake',
        'source_git': retained['source_git'], 'cross_baseline_fixture_replay': True})
    return dict(org=org, space=space, project=project, private=private, captures=captures,
                resources=resources, source_refs=[refs[r['source_id']] for r in captures])
