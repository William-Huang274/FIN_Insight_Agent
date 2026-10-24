from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from threading import Event, current_thread

import pytest

from test_organization_candidate_index import prepared, query, items
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_retrieval_lifecycle import OrganizationRetrievalLifecycle


def lifecycle(tmp_path, monkeypatch):
    _, reader, state, directory, grant = prepared(tmp_path, monkeypatch)
    before, _, _ = reader._grant()
    manager = OrganizationRetrievalLifecycle(reader, workbench_url='http://localhost',
        retrieval_root=tmp_path/'indices', grant=before)
    return manager, reader, state, directory, grant


def change_store(reader, corrupt=None):
    with sqlite3.connect(reader.workspace.library.documents.path) as db:
        if corrupt:
            db.execute('UPDATE attachments SET body=? WHERE id=?',(b'broken',corrupt))
        else:
            db.execute('CREATE TABLE unrelated_change (value INTEGER)')


def test_parallel_stage_open_warms_once_and_keeps_observations_separate(tmp_path,monkeypatch):
    manager, reader, _, _, _ = lifecycle(tmp_path,monkeypatch)
    calls=[]
    original=reader._read_storage
    def counted(*args):
        calls.append(args[0])
        return original(*args)
    monkeypatch.setattr(reader,'_read_storage',counted)
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            stages=list(executor.map(lambda _:manager.navigation(),range(3)))
        assert len(calls)==2 and manager.status()['generation']==1
        calls.clear()
        first=stages[0].navigate(query())
        second=stages[1].navigate(query(query='USD millions'))
        assert not calls and items(first)
        assert first.items[0]['retrieval']['source_generation_original_reads']==0
        assert second.items[0]['retrieval']['candidate_body_reads']<=36
        assert stages[0].observed is not stages[1].observed
        assert all(stage._candidate_index is None for stage in stages)
        assert manager._navigation._candidate_index is not None
    finally:
        manager.close()


def test_write_refreshes_once_in_background_without_blocking_or_serving_stale(tmp_path,monkeypatch):
    manager,reader,_,_,_=lifecycle(tmp_path,monkeypatch)
    stage=manager.navigation()
    before=stage.navigate(query())
    started,release=Event(),Event()
    original=reader._read_storage
    calls=[]
    def paused(*args):
        calls.append(current_thread().name)
        started.set()
        assert release.wait(10)
        return original(*args)
    monkeypatch.setattr(reader,'_read_storage',paused)
    change_store(reader)
    try:
        with pytest.raises(OrganizationExecutionUnavailable,match='refresh_pending'):
            stage.navigate(query())
        assert started.wait(5)
        with pytest.raises(TimeoutError):
            manager.wait_for_refresh(0)
        # A host drain timeout neither publishes a partial generation nor
        # starts a second worker. Queries remain denied until completion.
        assert manager.status()=={'state':'refreshing','generation':1,'failure_type':None}
        for _ in range(3):
            with pytest.raises(OrganizationExecutionUnavailable,match='refreshing'):
                stage.navigate(query())
        assert len(calls)==1 and manager.status()['state']=='refreshing'
        release.set()
        assert manager.wait_for_refresh(10)['generation']==2
        after=stage.navigate(query())
        assert len(calls)==2 and all(name.startswith('organization-retrieval') for name in calls)
        assert items(before)==items(after)
    finally:
        release.set()
        manager.close()
    with pytest.raises(OrganizationExecutionUnavailable,match='closed'):
        stage.navigate(query())


def test_non_candidate_corruption_fails_refresh_without_automatic_retry(tmp_path,monkeypatch):
    manager,reader,_,_,grant=lifecycle(tmp_path,monkeypatch)
    stage=manager.navigation()
    second=grant['manifest']['inputs'][1]['ref']['version_id']
    change_store(reader,second)
    try:
        with pytest.raises(OrganizationExecutionUnavailable,match='refresh_pending'):
            stage.navigate(query(document_id=stage._identity(grant['manifest']['inputs'][0])))
        with pytest.raises((OrganizationExecutionUnavailable,KeyError)):
            manager.wait_for_refresh(10)
        assert manager.status()['state']=='failed' and manager.status()['generation']==1
        with pytest.raises(OrganizationExecutionUnavailable,match='failed'):
            manager.navigation()
    finally:
        manager.close()


@pytest.mark.parametrize('fault',['revoke','index'])
def test_permission_or_release_failure_never_selects_another_release(tmp_path,monkeypatch,fault):
    manager,_,state,directory,_=lifecycle(tmp_path,monkeypatch)
    stage=manager.navigation()
    stage.navigate(query())
    if fault=='revoke':
        state['status']=404
    else:
        with sqlite3.connect(directory/'navigation.sqlite') as db:
            db.execute('UPDATE nodes SET payload=?',(b'corrupt',))
    try:
        with pytest.raises((OrganizationExecutionUnavailable,ValueError)):
            stage.navigate(query())
        assert manager.status()['state']=='failed' and manager.status()['generation']==1
    finally:
        manager.close()


def test_failed_initial_warmup_requires_explicit_retry_and_new_manager_rechecks(tmp_path,monkeypatch):
    manager,reader,_,_,_=lifecycle(tmp_path,monkeypatch)
    original=reader._read_storage
    def broken(*args):raise ValueError('temporary original read failure')
    monkeypatch.setattr(reader,'_read_storage',broken)
    with pytest.raises(ValueError,match='temporary'):
        manager.prepare()
    assert manager.status()['generation']==0
    monkeypatch.setattr(reader,'_read_storage',original)
    with pytest.raises(OrganizationExecutionUnavailable,match='failed'):
        manager.prepare()
    assert manager.prepare(retry_failed=True)['state']=='ready'
    manager.close()
    restarted=OrganizationRetrievalLifecycle(reader,workbench_url='http://localhost',
        retrieval_root=tmp_path/'indices',grant=reader._grant()[0])
    monkeypatch.setattr(reader,'_read_storage',broken)
    try:
        with pytest.raises(ValueError,match='temporary'):
            restarted.prepare()
    finally:restarted.close()


def test_factory_reuses_retrieval_across_actual_stage_contexts(tmp_path,monkeypatch):
    from pathlib import Path
    from sec_agent.agent_runtime.organization_data_composition import OrganizationDataFactory
    from sec_agent.agent_runtime.current_research_contract import current_foundation
    from sec_agent.research_foundation.contracts import load_research_graph_foundation
    from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
    manager,reader,_,_,grant=lifecycle(tmp_path,monkeypatch)
    manager.close()
    cutoff=grant['manifest']['research_as_of']+'T12:00:00+08:00'
    root=Path(__file__).resolve().parents[1]
    foundation=current_foundation(load_research_graph_foundation(),thread_id=reader.authority.execution_id,
        profile=json.loads((root/'configs/research/cases/growth_quality.json').read_text(encoding='utf8')),
        research_as_of=cutoff)
    factory=OrganizationDataFactory(reader,foundation=foundation,research_as_of=cutoff,
        workbench_url='http://localhost',retrieval_root=tmp_path/'indices')
    seen=[]
    restore=OrganizationSourceNavigation.restore
    def observe(self,*args):
        seen.append(self)
        return restore(self,*args)
    monkeypatch.setattr(OrganizationSourceNavigation,'restore',observe)
    try:
        assert factory.prepare_retrieval()['generation']==1
        for invocation in ('lead','expert','review'):
            with factory(run_invocation_id=invocation,source_read_enabled=True) as opened:
                opened.access_check()
        assert len(seen)==3
        assert all(nav._retrieval_lifecycle is factory.retrieval for nav in seen)
        assert len({id(nav.observed) for nav in seen})==3
        assert factory.retrieval.status()['generation']==1
    finally:factory.close()


def test_new_publication_never_moves_an_existing_frozen_run(tmp_path,monkeypatch):
    from uuid import uuid4
    from sec_agent.research_foundation.organization_hybrid_retrieval import preparation_nodes, publish_prepared_index
    from sec_agent.research_foundation.organization_source_projection import PROJECTION
    manager,reader,_,directory,_=lifecycle(tmp_path,monkeypatch)
    try:
        stage=manager.navigation()
        before=stage.navigate(query())
        org,nodes=preparation_nodes(reader,workbench_url='http://localhost')
        new_release=str(uuid4())
        vector=[1.]+[0.]*1023
        publish_prepared_index(tmp_path/'indices',org,nodes,[vector]*len(nodes),{'disclosure':vector},
            model='qwen3.7-text-embedding',provenance={'fixture':True},release_id=new_release,projection=PROJECTION)
        after=stage.navigate(query())
        assert items(before)==items(after)
        assert manager._navigation._candidate_index.directory==directory
        assert directory.name!=new_release and manager.status()['generation']==1
    finally:manager.close()


def test_readiness_observable_during_initial_prepare_and_close_cancels_publication(tmp_path,monkeypatch):
    manager,reader,_,_,_=lifecycle(tmp_path,monkeypatch)
    started,release=Event(),Event()
    original=reader._read_storage
    def paused(*args):
        started.set()
        assert release.wait(10)
        return original(*args)
    monkeypatch.setattr(reader,'_read_storage',paused)
    with ThreadPoolExecutor(max_workers=2) as host:
        initial=host.submit(manager.prepare)
        try:
            assert started.wait(5)
            assert manager.status()['state']=='preparing'
            # Hold the state lock so close cannot race with this assertion.
            with manager._lock:
                closing=host.submit(manager.close)
            # close sets state before draining the worker; wait for that signal.
            from time import monotonic, sleep
            deadline=monotonic()+5
            while manager.status()['state']!='closed' and monotonic()<deadline:
                sleep(.01)
            assert manager.status()['state']=='closed'
        finally:
            release.set()
        closing.result(timeout=10)
        with pytest.raises(OrganizationExecutionUnavailable,match='closed'):
            initial.result(timeout=10)
    assert manager.status()['generation']==0


def test_idle_stages_do_not_pin_replaced_generation_or_closed_caches(tmp_path, monkeypatch):
    import gc
    import weakref
    manager, reader, _, _, _ = lifecycle(tmp_path, monkeypatch)
    stages = [manager.navigation() for _ in range(3)]
    try:
        expected = stages[0].navigate(query())
        stages[1].navigate(query())
        old = weakref.ref(manager._navigation._candidate_index)
        old_loader = weakref.ref(manager._navigation.hybrid.release_cache)
        change_store(reader)
        with pytest.raises(OrganizationExecutionUnavailable, match='refresh_pending'):
            stages[2].navigate(query())
        manager.wait_for_refresh(10)
        gc.collect()
        assert old() is None and old_loader() is None
        assert items(stages[0].navigate(query())) == items(expected)
        current = weakref.ref(manager._navigation._candidate_index)
    finally:
        manager.close()
    gc.collect()
    assert current() is None
    assert all(stage.hybrid is None and stage._candidate_index is None for stage in stages)
    with pytest.raises(OrganizationExecutionUnavailable, match='closed'):
        stages[1].navigate(query())
