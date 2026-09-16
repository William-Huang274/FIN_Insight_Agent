"""Full offline recovery on isolated native services; no paid/model calls."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from threading import Barrier
from uuid import uuid4

import pytest
from psycopg.conninfo import make_conninfo

from test_native_server_runtime import native
from test_model_budget_access import access, reserve, denied
from sec_agent.adapters.model_dispatch_store import ModelDispatchStore, DispatchBlocked
from sec_agent.agent_runtime.working_memory import WorkingMemory
from sec_agent.research_foundation.project_library import ProjectLibrary
from sec_agent.research_foundation.task_attachments import TaskAttachmentStore
from sec_agent.research_foundation.asset_workspace import AssetWorkspace
from sec_agent.research_foundation.service_backup import PostgresArchive, backup_service, restore_service
from apps.workbench.backend.submission_receipts import SubmissionReceipts

pytestmark = pytest.mark.skipif(os.getenv('FIN_NATIVE_QUALIFICATION') != '1', reason='isolated Docker opt-in')


def test_service_snapshot_and_native_checkpoint_recovery(access):
    a = access; native = a['native']; root = native.output/'source'
    library = ProjectLibrary(root/'project-library')
    tasks = TaskAttachmentStore(root/'attachments')
    notes = root/'working-memory'/'notes.sqlite'
    receipts = SubmissionReceipts(None, root/'submission-receipts')
    barrier = Barrier(2)

    def create(owner):
        project = str(uuid4())
        library.save(owner, 0, {'projects': [{'id':project,'name':owner}], 'assignments':{},'pinned':[]})
        scope = library.scope(owner, project)
        document = library.documents.add(scope, 'Original.md', f'{owner}: 2025 USD 123.456'.encode())
        thread = native.request('POST','/threads',json={'metadata':{'owner_id':owner,'graph':'runtime_probe','title':owner}})['thread_id']
        library.assign_new_thread(owner,project,thread)
        tasks.copy_project_materials(thread, project, [library.documents.get(scope,document['document_id'])])
        memory = WorkingMemory(notes, owner=owner, workspace=thread, actor='cash')
        note = memory.save('Assumption', f'{owner}: initial assumption')
        barrier.wait()
        updated = memory.save('Assumption', f'{owner}: user revision', 1, user_edit=True)
        assert updated['saved']
        for _ in range(20):
            assert library.search(owner,project)['total'] == 1
            assert memory.read(note['note_id'])['body'] == f'{owner}: user revision'
        return owner,project,thread,note['note_id']

    with ThreadPoolExecutor(2) as pool:
        users = list(pool.map(create, ['alice','bob']))
    for owner,project,thread,note in users:
        with pytest.raises(KeyError): library.scope('bob' if owner=='alice' else 'alice',project)
        foreign = WorkingMemory(notes,owner='bob' if owner=='alice' else 'alice',workspace=thread,actor='cash')
        assert foreign.read(note)['found'] is False
    # Same-owner two tabs: exactly one update wins; neither can erase the winner.
    owner,project,thread,note = users[0]; barrier2 = Barrier(2)
    def race(body):
        memory = WorkingMemory(notes,owner=owner,workspace=thread,actor='cash')
        barrier2.wait(); return memory.save('Assumption',body,2,user_edit=True)['saved']
    with ThreadPoolExecutor(2) as pool: assert sum(pool.map(race,['tab A','tab B'])) == 1
    assert receipts.claim('uncertain', 'same') is None
    assert receipts.claim('completed', 'known') is None
    receipts.complete('completed','known',200,b'{"thread_id":"saved"}')
    store = ModelDispatchStore(a['accounts']['budget_worker'])
    a['authorizer'].create_budget('alice','restore-service','CNY',10000,1000)
    reserve(store,'alice','saved','restore-service');store.received('alice','restore-service','saved',{'source':'exact reply'},200)
    reserve(store,'alice','unknown','restore-service');store.unknown('alice','restore-service','unknown')
    before_budget = store.snapshot('alice','restore-service')
    research_thread = users[0][2]
    run = native.request('POST',f'/threads/{research_thread}/runs',json={'assistant_id':'runtime_probe',
        'input':{'label':'service-recovery-review','require_review':True},'multitask_strategy':'reject'})
    pair = (research_thread,run['run_id']); native.terminal(pair)
    before = native.state(pair)
    assert before['next'] == ['review']
    prefix = ['docker','exec','-i',native.compose('ps','-q','postgres').strip()]
    dbs = {'native':PostgresArchive('probe','probe',prefix), 'budget':PostgresArchive('fin_budget_probe','probe',prefix)}
    # Active connection rejection is exercised before the maintenance window.
    with pytest.raises(ValueError,match='clients_must_be_stopped'):
        dbs['native'].check_idle(native=True)
    native.compose('stop','-t','5','api')
    backup = native.output/'service-backup'; restored = native.output/'restored'
    manifest = backup_service(root/'project-library',root/'attachments',backup,working_memory=notes,
        submission_receipts=root/'submission-receipts'/'records-v1.sqlite',audit_root=native.output/'events',
        databases=dbs,maintenance_confirmed=True)
    restore_dbs = {'native':PostgresArchive('fin_native_service_restore','probe',prefix),
                   'budget':PostgresArchive('fin_budget_service_restore','probe',prefix)}
    result = restore_service(backup,restored,databases=restore_dbs)
    assert result['automatic_resume'] is False
    restored_receipts = SubmissionReceipts(None,restored/'assets'/'submission-receipts')
    assert restored_receipts.claim('uncertain','same')['status'] == 'dispatching'
    assert restored_receipts.claim('completed','known')['body'] == b'{"thread_id":"saved"}'
    recovered_library = ProjectLibrary(restored/'assets'/'project-library')
    recovered_tasks = TaskAttachmentStore(restored/'assets'/'attachments')
    for owner,project,thread,note in users:
        assert recovered_library.search(owner,project)['total'] == 1
        assert recovered_library.index(owner)['assignments'][thread] == project
        material = recovered_tasks.list(thread)[0]
        assert recovered_tasks.get(thread,material['document_id'])['body'] == f'{owner}: 2025 USD 123.456'.encode()
        memory = WorkingMemory(restored/'working-memory'/'notes.sqlite',owner=owner,workspace=thread,actor='cash')
        assert memory.read(note,version=1)['body'] == f'{owner}: initial assumption'
        assert memory.read(note,version=2)['body'] == f'{owner}: user revision'
    restored_store = ModelDispatchStore(make_conninfo(a['accounts']['budget_worker'],dbname=restore_dbs['budget'].database))
    restored_store.require_runtime_role()
    assert restored_store.snapshot('alice','restore-service') == before_budget
    assert reserve(restored_store,'alice','saved','restore-service')['response'] == {'source':'exact reply'}
    with pytest.raises(DispatchBlocked,match='unresolved_no_retry'): reserve(restored_store,'alice','unknown','restore-service')
    denied(make_conninfo(a['accounts']['cost_bob'],dbname=restore_dbs['budget'].database),'SELECT * FROM public.fin_model_dispatch')
    # Now explicitly activate ONLY the isolated probe against the restored DB.
    native.env['FIN_E1_DATABASE'] = restore_dbs['native'].database
    native.compose('up','-d','--no-deps','--force-recreate','api');native.healthy()
    recovered = native.state(pair)
    for owner,project,thread,note in users:
        assert native.request('GET',f'/threads/{thread}')['metadata']['owner_id'] == owner
    assert recovered['checkpoint']['checkpoint_id'] == before['checkpoint']['checkpoint_id']
    assert recovered['values'] == before['values'] and recovered['next'] == ['review']
    assert len(native.events('service-recovery-review','work_started')) == 1
    resumed = native.request('POST', f'/threads/{pair[0]}/runs', json={'assistant_id':'runtime_probe','command':{'resume':True}})
    native.terminal((pair[0],resumed['run_id']))
    assert native.state(pair)['values']['reviewed'] is True
    assert len(native.events('service-recovery-review','work_started')) == 1
    native.save('service-recovery',{'checkpoint':before['checkpoint']['checkpoint_id'],'owners':2,'reads_per_owner':20,
        'competing_edits_winners':1,'budget_before':before_budget,'budget_after':restored_store.snapshot('alice','restore-service'),
        'unknown_still_blocks':True,'receipt_replays':True,'original_checkpoint_resumes':True,
        'files':len(manifest['files']),'model_calls':0,'automatic_resume':False})
