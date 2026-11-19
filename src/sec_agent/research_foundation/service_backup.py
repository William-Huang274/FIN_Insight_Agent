"""Maintenance snapshots using SQLite backup and PostgreSQL's native tools.

Ingress, workers, and importers must be stopped before invoking this module.
No scheduler, retention engine, credential archive, or automatic restart is added.
"""
from contextlib import ExitStack, closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess

from .asset_backup import _hash
from .asset_set_backup import backup_asset_set, restore_asset_set, _safe, _connect

SCHEMA = 'service_backup.v1'


@dataclass
class PostgresArchive:
    """Native client invocation; credentials stay in libpq/container environment."""
    database: str
    user: str
    prefix: list[str] = field(default_factory=list)

    def run(self, program, *args, source=None, target=None):
        command = [*self.prefix, program, '-U', self.user, *args]
        with ExitStack() as stack:
            inp = stack.enter_context(open(source, 'rb')) if source else subprocess.DEVNULL
            out = stack.enter_context(open(target, 'xb')) if target else subprocess.PIPE
            result = subprocess.run(command, stdin=inp, stdout=out, stderr=subprocess.PIPE, timeout=300)
        if result.returncode:
            # stderr can contain credentials/connection strings; never expose it.
            raise RuntimeError(f'postgres_{program}_failed_exit_{result.returncode}')
        if result.stderr.strip():
            raise RuntimeError(f'postgres_{program}_warning_requires_operator_review')
        return result.stdout.decode('utf-8').strip() if result.stdout else ''

    def check_idle(self, *, native=False):
        # Also rejects idle API connections: all writers must really be stopped.
        count = self.run('psql', '-d', self.database, '-At', '-v', 'ON_ERROR_STOP=1', '-c',
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")
        if count != '0':
            raise ValueError('postgres_clients_must_be_stopped')
        if native:
            count = self.run('psql', '-d', self.database, '-At', '-v', 'ON_ERROR_STOP=1', '-c',
                            "SELECT count(*) FROM public.run WHERE status IN ('pending','running')")
            if count != '0':
                raise ValueError('native_pending_runs_must_be_resolved_before_backup')

    def dump(self, target):
        self.run('pg_dump', '-d', self.database, '-Fc', target=target)

    def restore_new(self, archive):
        # createdb fails for an existing DB. No --clean/overwrite or --no-acl.
        self.run('createdb', '--template=template0', self.database)
        self.run('pg_restore', '-d', self.database, '--exit-on-error', '--single-transaction', source=archive)


def _inventory(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError('audit_directory_missing')
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError('audit_links_not_supported')
        if path.is_file():
            result[path.relative_to(root).as_posix()] = _hash(path)
    return result


def backup_service(project_root, task_root, target, *, working_memory, submission_receipts,
                   audit_root, databases, maintenance_confirmed=False, public_library=None, financial_mart=None, research_library=None):
    if not maintenance_confirmed:
        raise ValueError('stop_ingress_workers_importers_before_backup')
    if set(databases) != {'native', 'budget'}:
        raise ValueError('native_and_budget_databases_required')
    target = Path(target).resolve()
    roots = [Path(p).resolve() for p in (project_root, task_root, working_memory, submission_receipts, audit_root)]
    for root in roots:
        if target == root or target.is_relative_to(root) or root.is_relative_to(target):
            raise ValueError('service_backup_roots_must_be_separate')
    for key, database in databases.items():
        database.check_idle(native=key == 'native')
    audits = _inventory(audit_root)
    target.mkdir(parents=True, exist_ok=False)
    with ExitStack() as stack:
        sources = [Path(project_root)/'attachments.sqlite', Path(task_root)/'attachments.sqlite',
                   Path(working_memory), Path(submission_receipts)]
        # Long-lived read connections detect SQLite changes across ALL snapshots.
        handles = [stack.enter_context(closing(_connect(p))) for p in sources]
        versions = [db.execute('PRAGMA data_version').fetchone()[0] for db in handles]
        backup_asset_set(project_root, task_root, target/'assets', public_library=public_library, financial_mart=financial_mart,research_library=research_library)
        for db, relative in zip(handles[2:], ('working-memory/notes.sqlite', 'submission-receipts/records-v1.sqlite')):
            dest = target/relative; dest.parent.mkdir(parents=True)
            with closing(sqlite3.connect(dest)) as output:
                db.backup(output)
                if output.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise ValueError('service_sqlite_backup_invalid')
        (target/'postgres').mkdir()
        for key, database in databases.items():
            database.dump(target/'postgres'/f'{key}.dump')
        for relative, digest in audits.items():
            dest = _safe(target/'audit', relative); dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_safe(Path(audit_root).resolve(), relative), dest)
            if _hash(dest) != digest:
                raise ValueError('audit_changed_during_backup')
        if _inventory(audit_root) != audits or versions != [db.execute('PRAGMA data_version').fetchone()[0] for db in handles]:
            raise ValueError('service_changed_during_backup')
        for key, database in databases.items():
            database.check_idle(native=key == 'native')
    manifest = {'schema_version': SCHEMA, 'created_at': datetime.now(timezone.utc).isoformat(),
                'files': {p.relative_to(target).as_posix(): _hash(p) for p in target.rglob('*') if p.is_file()},
                'automatic_resume': False, 'consistency': 'operator_quiesced_service',
                'required_databases': ['native', 'budget'],
                'excluded': ['credentials', 'postgres_cluster_roles', 'redis_ephemeral_notifications'],
                'recovery_rule': 'Provision the same database roles with new credentials; inspect unknown dispatches before allowing any calls.'}
    (target/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return manifest


def restore_service(backup, target, *, databases):
    backup, target = Path(backup).resolve(), Path(target).resolve()
    if set(databases) != {'native', 'budget'} or databases['native'].database == databases['budget'].database:
        raise ValueError('two_distinct_new_restore_databases_required')
    if backup == target or backup.is_relative_to(target) or target.is_relative_to(backup):
        raise ValueError('service_restore_roots_must_be_separate')
    manifest = json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    required = {'assets/manifest.json', 'working-memory/notes.sqlite', 'submission-receipts/records-v1.sqlite',
                'postgres/native.dump', 'postgres/budget.dump'}
    if manifest.get('schema_version') != SCHEMA or not required <= manifest.get('files', {}).keys():
        raise ValueError('service_manifest_invalid')
    for relative, digest in manifest['files'].items():
        _safe(target, relative)
        if _hash(_safe(backup, relative)) != digest:
            raise ValueError('service_backup_integrity_failure')
    target.mkdir(parents=True, exist_ok=False)
    assets = restore_asset_set(backup/'assets', target/'assets')
    for relative, digest in manifest['files'].items():
        if relative.startswith(('working-memory/', 'submission-receipts/', 'audit/')):
            # BFF locates receipts beside attachments/settings, not at an
            # independently configurable root. Rebind that layout explicitly.
            destination = 'assets/'+relative if relative.startswith('submission-receipts/') else relative
            dest = _safe(target, destination); dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(_safe(backup, relative), dest)
            if _hash(dest) != digest:
                raise ValueError('service_restore_copy_failure')
    for relative in ('working-memory/notes.sqlite', 'assets/submission-receipts/records-v1.sqlite'):
        with closing(_connect(target/relative)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('service_restored_sqlite_invalid')
    for key, database in databases.items():
        database.restore_new(backup/'postgres'/f'{key}.dump')
    result = {'schema_version': SCHEMA, 'status': 'restored_offline', 'automatic_resume': False,
              'assets': assets, 'databases': {key: db.database for key, db in databases.items()},
              'settings_directory': str(target/'assets'), 'working_memory': str(target/'working-memory'/'notes.sqlite'),
              'audit_root': str(target/'audit'), 'submission_receipts': str(target/'assets'/'submission-receipts'),
              'activation_required': 'Verify owners, checkpoint IDs, original citations, pending submissions and unknown budget holds; configure restored paths before reopening ingress.'}
    (target/'restore-result.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('settings', type=Path, help='Private JSON paths and native client names; no passwords')
    args = parser.parse_args()
    data = json.loads(args.settings.read_text(encoding='utf-8'))
    data['databases'] = {key: PostgresArchive(**value) for key, value in data['databases'].items()}
    result = backup_service(**data) if args.action == 'backup' else restore_service(**data)
    print(json.dumps({'schema_version': result['schema_version'], 'automatic_resume': False, 'status': 'complete'}))


if __name__ == '__main__':
    main()
