"""Deterministic admission races; these do not establish service capacity."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.workbench.backend.organization_navigation import OrganizationNavigationService, _Session
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest


READ = SourceDocumentRequest(source_space='organization', operation='read', document_id='document')
SEARCH = SourceDocumentRequest(source_space='organization', operation='search', query='evidence')


def key(actor):
    return actor, 'project', 'draft', 'execution', 'http://localhost'


def call(service, actor, request=READ):
    return service.navigate(*key(actor), request)


def install(service, actor, operation, *, cold=False):
    candidate = None if cold else SimpleNamespace(generation='ready', observer=SimpleNamespace(epoch=lambda: 1), epoch=1)
    nav = SimpleNamespace(navigate=operation, _candidate_index=candidate)
    service._sessions[key(actor)] = _Session(navigation=nav)
    return nav


def test_distinct_warm_users_overlap_without_sharing_results():
    service = OrganizationNavigationService(None, None, maximum_parallel=2)
    barrier = Barrier(2)
    for actor in ('alice', 'bob'):
        def operation(request, actor=actor):
            barrier.wait(timeout=2)
            return actor
        install(service, actor, operation)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(call, service, actor, SEARCH) for actor in ('alice', 'bob')]
        assert [f.result(timeout=3) for f in futures] == ['alice', 'bob']


def test_same_user_serializes_and_busy_sessions_cannot_be_evicted():
    service = OrganizationNavigationService(None, None, maximum_sessions=1, wait_seconds=.1)
    entered, release = Event(), Event()
    calls = []
    def operation(request):
        calls.append(1)
        entered.set()
        assert release.wait(3)
        return 'private'
    nav = install(service, 'alice', operation)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(call, service, 'alice')
        assert entered.wait(2)
        try:
            for actor in ('alice', 'bob'):
                with pytest.raises(HTTPException) as error:
                    call(service, actor)
                assert error.value.status_code == 429
            assert service._sessions[key('alice')].navigation is nav
            assert len(calls) == 1
        finally:
            release.set()
        assert first.result(timeout=2) == 'private'
    assert service._sessions[key('alice')].users == 0


def test_cold_queries_serialize_but_other_users_reads_proceed():
    service = OrganizationNavigationService(None, None, wait_seconds=.1, maximum_parallel=2)
    entered, release = Event(), Event()
    def operation(request):
        entered.set()
        assert release.wait(3)
        return 'cold'
    install(service, 'alice', operation, cold=True)
    install(service, 'bob', lambda request: 'read', cold=True)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(call, service, 'alice', SEARCH)
        assert entered.wait(2)
        try:
            with pytest.raises(HTTPException) as error:
                call(service, 'bob', SEARCH)
            assert error.value.status_code == 429
            assert call(service, 'bob', READ) == 'read'
        finally:
            release.set()
        assert first.result(timeout=2) == 'cold'


def test_revocation_during_parallel_operation_discards_only_failed_session():
    service = OrganizationNavigationService(None, None, maximum_parallel=2)
    entered, revoke = Event(), Event()
    def operation(request):
        entered.set()
        assert revoke.wait(3)
        raise HTTPException(404, 'current permission revoked')
    install(service, 'alice', operation)
    install(service, 'bob', lambda request: 'bob')
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(call, service, 'alice')
        assert entered.wait(2)
        try:
            assert call(service, 'bob') == 'bob'
        finally:
            revoke.set()
        with pytest.raises(HTTPException):
            first.result(timeout=2)
    assert key('alice') not in service._sessions
    assert call(service, 'bob') == 'bob'


def test_idle_eviction_releases_only_unpinned_session():
    service = OrganizationNavigationService(None, None, maximum_sessions=1)
    install(service, 'alice', lambda request: 'unused')
    from time import monotonic
    session = service._claim(key('bob'), monotonic()+1)
    assert session.users == 1 and key('alice') not in service._sessions


def test_default_remains_single_operation_until_parallel_profile_is_enabled(monkeypatch):
    monkeypatch.delenv('FINSIGHT_ORGANIZATION_NAVIGATION_CONCURRENCY', raising=False)
    service = OrganizationNavigationService(None, None, wait_seconds=0)
    install(service, 'alice', lambda request: 'alice')
    assert service._admission.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as error:
            call(service, 'alice')
        assert error.value.status_code == 429
    finally:
        service._admission.release()
    assert call(service, 'alice') == 'alice'


@pytest.mark.parametrize('value', ['0', '3', '-1', 'invalid'])
def test_invalid_parallel_configuration_fails_closed(monkeypatch, value):
    monkeypatch.setenv('FINSIGHT_ORGANIZATION_NAVIGATION_CONCURRENCY', value)
    with pytest.raises(ValueError):
        OrganizationNavigationService(None, None)
