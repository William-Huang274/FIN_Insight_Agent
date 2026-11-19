"""Coordinate project and task source copies; native execution stays separately owned.

SQLite write reservations hold both catalogs stable while native backup copies
them. No cross-store write transaction or custom checkpoint engine is introduced.
"""
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import UUID

from .asset_backup import backup_assets, _hash

SCHEMA = 'asset_set_backup.v1'


def _connect(path, mode='ro'):
    return sqlite3.connect(Path(path).resolve().as_uri()+'?mode='+mode, uri=True, timeout=15)


def _table(db, name):
    return db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone()


def _safe(root, relative):
    path = (root / relative).resolve()
    if path == root or not path.is_relative_to(root):
        raise ValueError('backup_path_outside_root')
    return path


def _financial_files(db):
    if not _table(db, 'task_financial_snapshots'):
        return []
    files = []
    for thread, body in db.execute('SELECT thread,body FROM task_financial_snapshots'):
        info = json.loads(body)
        if info['status'] != 'ready':
            continue  # Preserve unfinished state; never promote or retry it.
        folder = Path('financial-snapshots') / str(UUID(thread))
        files.append((folder/'facts.sqlite', info['mart_sha256']))
        for kind in ('sec_companyfacts','sec_submissions'):
            digest = next(s['sha256'] for s in info['raw_sources'] if s['kind']==kind)
            files.extend([(folder/(kind+'.json'), digest), (folder/(kind+'.metadata.json'), None)])
        files.append((folder/'build-result.json', None))
    return files


def _validate_links(project_path, task_path):
    """Check references without suppressing revoked/history records."""
    with closing(_connect(project_path)) as project, closing(_connect(task_path)) as tasks:
        for db in (project,tasks):
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('asset_set_database_invalid')
            for body,digest in db.execute('SELECT body,digest FROM attachments'):
                if sha256(body).hexdigest()!=digest:
                    raise ValueError('asset_set_original_integrity_failure')
        def check(origin, kind='document'):
            for dep in origin.get('research_origin',{}).get('source_dependencies',[]):
                check(dep, dep.get('asset_kind','document'))
            if not origin.get('project_id'):
                return
            if kind=='document':
                row=project.execute('SELECT thread,digest FROM attachments WHERE id=?',(origin['document_id'],)).fetchone()
                if not row or row[1]!=origin['raw_body_sha256'] or (origin.get('source_scope') and row[0]!=origin['source_scope']):
                    raise ValueError('asset_set_document_reference_invalid')
            else:
                row=project.execute('SELECT body FROM project_sec_versions WHERE scope=? AND version=?',
                                    (origin['source_scope'],origin['sec_version'])).fetchone()
                if not row or json.loads(row[0])['status']!='complete':
                    raise ValueError('asset_set_sec_reference_invalid')
        for db in (project,tasks):
            if _table(db,'attachment_origins'):
                for row in db.execute('SELECT origin FROM attachment_origins'):
                    check(json.loads(row[0]))
        if _table(tasks,'task_financial_snapshots'):
            for row in tasks.execute('SELECT body FROM task_financial_snapshots'):
                info=json.loads(row[0]);check(info['project_origin'],'sec')
        if _table(tasks,'task_asset_updates'):
            from .asset_workspace import _digest
            for thread,revision,state,raw in tasks.execute('SELECT thread,revision,state,body FROM task_asset_updates'):
                body=json.loads(raw)
                if state!='ready':
                    continue
                context=body['context'];scope=str(UUID(body['scope']))
                if context['digest']!=_digest({k:v for k,v in context.items() if k!='digest'}):
                    raise ValueError('asset_set_input_context_invalid')
                actual={(json.loads(origin)['document_id'],digest) for origin,digest in tasks.execute(
                    'SELECT o.origin,a.digest FROM attachments a JOIN attachment_origins o ON o.object_id=a.id WHERE a.thread=?',(scope,))}
                expected={(r['version_id'],r['digest']) for r in context['refs'] if r['kind']=='document'}
                if actual!=expected:
                    raise ValueError('asset_set_input_documents_missing')
                sec=next((r for r in context['refs'] if r['kind']=='sec'),None)
                if sec:
                    row=tasks.execute('SELECT body FROM task_financial_snapshots WHERE thread=?',(scope,)).fetchone() if _table(tasks,'task_financial_snapshots') else None
                    if not row or json.loads(row[0])['status']!='ready' or json.loads(row[0])['project_origin']['sec_version']!=sec['version_id']:
                        raise ValueError('asset_set_input_financial_binding_missing')
        if _table(tasks,'task_asset_runs'):
            for thread,revision in tasks.execute('SELECT thread,revision FROM task_asset_runs WHERE revision>0'):
                if not _table(tasks,'task_asset_updates') or not tasks.execute(
                    "SELECT 1 FROM task_asset_updates WHERE thread=? AND revision=? AND state='ready'",(thread,revision)).fetchone():
                    raise ValueError('asset_set_adopted_revision_missing')
        return _financial_files(tasks)


def backup_asset_set(project_root, task_root, target, *, public_library=None, financial_mart=None, research_library=None):
    project_root,task_root,target=map(lambda p:Path(p).resolve(),(project_root,task_root,target))
    if project_root==task_root or any(target==p or target.is_relative_to(p) or p.is_relative_to(target) for p in (project_root,task_root)):
        raise ValueError('backup_roots_must_be_separate')
    paths=[p/'attachments.sqlite' for p in (project_root,task_root)]
    if not all(p.is_file() for p in paths):
        raise ValueError('asset_set_database_missing')
    for source in (public_library,financial_mart,research_library):
        if source and (not Path(source).is_file() or Path(source).resolve().is_relative_to(target)):
            raise ValueError('global_asset_source_invalid')
    target.mkdir(parents=True,exist_ok=False)
    with ExitStack() as stack:
        # Stable order, bounded busy timeout. Reservations block writes, not reads.
        for path in sorted(paths):
            lock=stack.enter_context(closing(_connect(path,'rw')))
            lock.execute('BEGIN IMMEDIATE')
        with closing(_connect(paths[1])) as db:
            if _table(db,'task_project_stores'):
                if any(Path(r[0]).resolve()!=paths[0] for r in db.execute('SELECT path FROM task_project_stores')):
                    raise ValueError('asset_set_external_project_binding')
        backup_assets(project_root,target/'project-library')
        task_target=target/'attachments';task_target.mkdir()
        with closing(_connect(paths[1])) as src, closing(sqlite3.connect(task_target/'attachments.sqlite')) as dst:
            src.backup(dst)
        required=_validate_links(target/'project-library'/'attachments.sqlite',task_target/'attachments.sqlite')
        for relative,digest in required:
            source=_safe(task_root,relative)
            if digest and _hash(source)!=digest:
                raise ValueError('task_financial_snapshot_integrity_failure')
            dest=_safe(task_target,relative);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,dest)
            if digest and _hash(dest)!=digest:
                raise ValueError('task_financial_snapshot_copy_failure')
    global_sources={}
    if public_library or financial_mart or research_library:
        (target/'library').mkdir()
    if public_library:
        source=Path(public_library).resolve();digest=_hash(source)
        dest=target/'attachments'/'public-library'/'retrieval_nodes.jsonl';dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
        if _hash(dest)!=digest or _hash(source)!=digest:
            raise ValueError('public_library_changed_during_backup')
        global_sources['public_library']='attachments/public-library/retrieval_nodes.jsonl'
    if financial_mart:
        with closing(_connect(financial_mart)) as src, closing(sqlite3.connect(target/'library'/'financial-facts.sqlite')) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                raise ValueError('financial_library_backup_invalid')
        global_sources['financial_mart']='library/financial-facts.sqlite'
    if research_library:
        from .research_library import ResearchLibrary
        source=Path(research_library).resolve();published=ResearchLibrary(source)
        dest=target/'library'/'research-library.sqlite'
        shutil.copyfile(source,dest)
        shutil.copyfile(source.with_suffix(source.suffix+'.manifest.json'),dest.with_suffix(dest.suffix+'.manifest.json'))
        if ResearchLibrary(dest).manifest['sha256']!=published.manifest['sha256']:
            raise ValueError('research_library_changed_during_backup')
        global_sources['research_library']='library/research-library.sqlite'
    files={p.relative_to(target).as_posix():_hash(p) for p in target.rglob('*') if p.is_file()}
    manifest={'schema_version':SCHEMA,'created_at':datetime.now(timezone.utc).isoformat(),
              'files':files,'source_project_database':str(paths[0]),
              'scope':'project_assets_and_task_source_copies','native_threads_included':False,
              'global_sources':global_sources,
              'excluded':['native_threads_runs_checkpoints','submission_receipts','provider_usage_and_dispatch']+
                         [name for name in ('public_library','financial_mart','research_library') if name not in global_sources],
              'automatic_resume':False}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


def restore_asset_set(backup, target):
    backup,target=map(lambda p:Path(p).resolve(),(backup,target))
    if backup==target or target.is_relative_to(backup) or backup.is_relative_to(target):
        raise ValueError('restore_roots_must_be_separate')
    manifest=json.loads((backup/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema_version')!=SCHEMA or not {'project-library/attachments.sqlite','attachments/attachments.sqlite','project-library/manifest.json'}<=manifest.get('files',{}).keys():
        raise ValueError('asset_set_manifest_invalid')
    for relative,digest in manifest['files'].items():
        _safe(target,relative)
        if _hash(_safe(backup,relative))!=digest:
            raise ValueError('asset_set_integrity_failure')
    for name,relative in manifest.get('global_sources',{}).items():
        expected={'public_library':'attachments/public-library/retrieval_nodes.jsonl','financial_mart':'library/financial-facts.sqlite','research_library':'library/research-library.sqlite'}
        if expected.get(name)!=relative or relative not in manifest['files']:
            raise ValueError('asset_set_global_source_invalid')
        if name=='financial_mart':
            with closing(_connect(backup/relative)) as db:
                if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('financial_library_backup_invalid')
        if name=='research_library':
            from .research_library import ResearchLibrary
            if relative+'.manifest.json' not in manifest['files']:
                raise ValueError('research_library_manifest_missing_from_backup')
            ResearchLibrary(backup/relative)
    # The nested manifest also defines every required project SEC original.
    project_manifest=json.loads((backup/'project-library'/'manifest.json').read_text(encoding='utf-8'))
    for relative,digest in project_manifest['files'].items():
        if manifest['files'].get('project-library/'+relative)!=digest:
            raise ValueError('asset_set_project_file_missing')
    required=_validate_links(backup/'project-library'/'attachments.sqlite',backup/'attachments'/'attachments.sqlite')
    for relative,digest in required:
        recorded=manifest['files'].get('attachments/'+relative.as_posix())
        if not recorded or (digest and recorded!=digest):
            raise ValueError('asset_set_task_file_missing')
    target.mkdir(parents=True,exist_ok=False)
    for relative in manifest['files']:
        path=_safe(target,relative);path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(_safe(backup,relative),path)
        if _hash(path)!=manifest['files'][relative]:
            raise ValueError('asset_set_restore_copy_failure')
    with closing(_connect(target/'attachments'/'attachments.sqlite','rw')) as db:
        with db:
            if _table(db,'task_project_stores'):
                for row in db.execute('SELECT path FROM task_project_stores'):
                    if Path(row[0]).resolve()!=Path(manifest['source_project_database']).resolve():
                        raise ValueError('asset_set_unexpected_project_binding')
                db.execute('UPDATE task_project_stores SET path=?',(str(target/'project-library'/'attachments.sqlite'),))
    _validate_links(target/'project-library'/'attachments.sqlite',target/'attachments'/'attachments.sqlite')
    receipt={'schema_version':SCHEMA,'status':'restored','native_threads_included':False,
             'automatic_resume':False,'rebound_project_database':str(target/'project-library'/'attachments.sqlite'),
             'backup_created_at':manifest['created_at'],
             'global_sources':{name:str(_safe(target,relative)) for name,relative in manifest.get('global_sources',{}).items()}}
    # Completion marker is last; a partial directory must never be activated.
    (target/'restore-result.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    return receipt


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='action',required=True)
    save=commands.add_parser('backup');save.add_argument('project_root');save.add_argument('task_root');save.add_argument('target')
    save.add_argument('--public-library',help='Configured retrieval_nodes.jsonl')
    save.add_argument('--financial-mart',help='Configured read-only financial SQLite')
    save.add_argument('--research-library',help='Published public research graph/FTS SQLite release')
    restore=commands.add_parser('restore');restore.add_argument('backup');restore.add_argument('target')
    args=parser.parse_args()
    result=backup_asset_set(args.project_root,args.task_root,args.target,public_library=args.public_library,financial_mart=args.financial_mart,research_library=args.research_library) if args.action=='backup' else restore_asset_set(args.backup,args.target)
    print(json.dumps({'status':'complete','scope':result.get('scope'),'native_threads_included':False,'automatic_resume':False}))
