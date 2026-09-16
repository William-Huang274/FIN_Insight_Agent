from pathlib import Path
import sqlite3
from uuid import uuid4

import pytest

from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.service_backup import backup_service, restore_service
from apps.workbench.backend.submission_receipts import SubmissionReceipts


class Archive:
    def __init__(self,name,hook=lambda:None): self.database,self.hook,self.restored=name,hook,False
    def check_idle(self,**kwargs): pass
    def dump(self,path): path.write_bytes(b'synthetic native dump');self.hook()
    def restore_new(self,path): self.restored=True


def setup(root):
    project=ProjectLibrary(root/'projects');pid=str(uuid4())
    project.save('alice',0,{'projects':[{'id':pid,'name':'Test'}],'assignments':{},'pinned':[]})
    project.documents.add(project.scope('alice',pid),'Source.md',b'original')
    TaskAttachmentStore(root/'tasks').add(str(uuid4()),'Task.md',b'original task')
    memory=WorkingMemory(root/'notes.sqlite',owner='alice',workspace='w',actor='a')
    memory.save('Note','version 1')
    SubmissionReceipts(None,root/'receipts').claim('uncertain','fingerprint')
    audit=root/'audit';audit.mkdir();(audit/'call.json').write_text('{"status":"unknown"}')
    return dict(project_root=root/'projects',task_root=root/'tasks',working_memory=root/'notes.sqlite',
        submission_receipts=root/'receipts'/'records-v1.sqlite',audit_root=audit,
        databases={'native':Archive('n'),'budget':Archive('b')},maintenance_confirmed=True)


def test_offline_full_snapshot_no_overwrite_and_corruption_before_pg(tmp_path):
    args=setup(tmp_path/'source');backup=tmp_path/'backup';target=tmp_path/'restore'
    result=backup_service(**args,target=backup)
    assert result['automatic_resume'] is False
    databases={'native':Archive('restored_n'),'budget':Archive('restored_b')}
    result=restore_service(backup,target,databases=databases)
    assert result['status']=='restored_offline'
    assert SubmissionReceipts(None,target/'assets'/'submission-receipts').claim('uncertain','fingerprint')['status']=='dispatching'
    with pytest.raises(FileExistsError): restore_service(backup,target,databases=databases)
    (backup/'postgres'/'native.dump').write_bytes(b'bad')
    databases={k:Archive(v.database) for k,v in databases.items()}
    with pytest.raises(ValueError,match='integrity'): restore_service(backup,tmp_path/'bad',databases=databases)
    assert not (tmp_path/'bad').exists() and not any(d.restored for d in databases.values())


def test_missing_quiescence_or_mid_backup_write_never_completes(tmp_path):
    args=setup(tmp_path/'source')
    with pytest.raises(ValueError,match='stop_ingress'): backup_service(**{**args,'maintenance_confirmed':False},target=tmp_path/'not-started')
    assert not (tmp_path/'not-started').exists()
    def mutate():
        memory=WorkingMemory(args['working_memory'],owner='alice',workspace='w',actor='a')
        memory.save('Note','unexpected concurrent write',1)
    args['databases']['native']=Archive('native',mutate)
    with pytest.raises(ValueError,match='changed_during'): backup_service(**args,target=tmp_path/'partial')
    assert not (tmp_path/'partial'/'manifest.json').exists()


def test_audit_mutation_or_restore_failure_has_no_completion_marker(tmp_path):
    args=setup(tmp_path/'source')
    args['databases']['native']=Archive('n',lambda:(args['audit_root']/'late.json').write_text('late'))
    with pytest.raises(ValueError,match='changed_during'): backup_service(**args,target=tmp_path/'partial')
    args['databases']['native']=Archive('n');backup=tmp_path/'good'
    backup_service(**args,target=backup)
    class Failure(Archive):
        def restore_new(self,path): raise RuntimeError('restore failed')
    with pytest.raises(RuntimeError,match='restore failed'):
        restore_service(backup,tmp_path/'restore',databases={'native':Failure('n'),'budget':Archive('b')})
    assert not (tmp_path/'restore'/'restore-result.json').exists()
