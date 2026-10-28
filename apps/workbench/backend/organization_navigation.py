"""Bound research navigation over HTTP, with current browser AND runtime authority.

The server keeps a bounded number of user-private navigation sessions. A cached
result is never an authorization lease, and this endpoint cannot admit a run.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, field
import os
from threading import BoundedSemaphore, Condition, Lock, RLock
from time import monotonic

from anyio import from_thread
from fastapi import HTTPException

from .organization_research_inputs import validate_grant
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionReader, OrganizationExecutionUnavailable,
    validate_execution_grant,
)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation


class UserExecutionAuthority:
    def __init__(self, actor, project, draft, execution, grant, business):
        self.actor, self.project, self.draft = actor, project, draft
        self.business = business
        self.execution_id, self.manifest_digest = execution, grant['manifest_digest']
        self.frozen = grant
        self.snapshot = None

    def __call__(self):
        reply = from_thread.run(self.business, self.actor, 'POST',
            f'projects/{self.project}/research-drafts/{self.draft}/execution-bindings/{self.execution_id}/navigation-access',
            {'thread_id': self.execution_id, 'manifest_digest': self.manifest_digest,
             'include_grant': self.snapshot is None})
        if reply.get('contract_version') != 'organization_navigation_access.v1':
            raise OrganizationExecutionUnavailable('organization_navigation_access_contract_mismatch')
        if self.snapshot is None:
            grant = reply.get('grant', {})
            manifest, bindings = validate_execution_grant(grant, self.execution_id, self.manifest_digest)
            if (manifest != self.frozen['manifest'] or manifest['project_id'] != self.project
                    or manifest['draft_id'] != self.draft
                    or bindings != {item['resource_id']: item['binding'] for item in self.frozen['inputs']}):
                raise OrganizationExecutionUnavailable('organization_navigation_binding_mismatch')
            self.snapshot = deepcopy(grant)
        expected = {key: value for key, value in self.snapshot.items() if key not in {'manifest_text', 'inputs'}}
        if reply.get('binding') != expected:
            raise OrganizationExecutionUnavailable('organization_navigation_authority_changed')
        # Reuse immutable payload only after this call's fresh Java verdict.
        return deepcopy(self.snapshot)


@dataclass
class _Session:
    lock: object = field(default_factory=Lock)
    navigation: object = None
    users: int = 0


class OrganizationNavigationService:
    """Independent bounded user sessions; serialize each session and cold loads.

    Active or queued sessions cannot be evicted. Session/cache/observer state is
    never shared between actors. A single deadline bounds all admission waits.
    """
    def __init__(self, workspace, business, *, maximum_sessions=2, wait_seconds=30, maximum_parallel=None):
        self.workspace, self.business = workspace, business
        self.maximum_sessions, self.wait_seconds = maximum_sessions, wait_seconds
        if maximum_sessions < 1 or wait_seconds < 0:
            raise ValueError('invalid_navigation_admission_limits')
        if maximum_parallel is None:
            maximum_parallel = int(os.getenv('FINSIGHT_ORGANIZATION_NAVIGATION_CONCURRENCY', '1'))
        if not 1 <= maximum_parallel <= maximum_sessions:
            raise ValueError('invalid_navigation_parallel_limit')
        self._lock, self._sessions = Lock(), OrderedDict()
        self._changed = Condition(self._lock)
        self._cold_lock = RLock()
        self._admission = BoundedSemaphore(maximum_parallel)

    @staticmethod
    def _busy():
        return HTTPException(429, '组织检索繁忙；本次未执行检索，请稍后手动重试')

    def _claim(self, key, deadline):
        if not self._lock.acquire(timeout=max(0, deadline-monotonic())):
            raise self._busy()
        try:
            while key not in self._sessions:
                if len(self._sessions) < self.maximum_sessions:
                    self._sessions[key] = _Session()
                    break
                idle = next((k for k, s in self._sessions.items() if s.users == 0), None)
                if idle is not None:
                    self._sessions.pop(idle)
                    continue
                remaining = deadline-monotonic()
                if remaining <= 0:
                    raise self._busy()
                self._changed.wait(remaining)
            session = self._sessions[key]
            session.users += 1
            self._sessions.move_to_end(key)
            return session
        finally:
            self._lock.release()

    @staticmethod
    def _needs_preparation(navigation, request):
        if request.operation != 'search':
            return False
        candidates = navigation._candidate_index
        return (candidates is None or candidates.generation is None
                or candidates.observer.epoch() != candidates.epoch)

    def navigate(self, actor, project, draft, execution, origin, request):
        if request.source_space != 'organization' or request.operation not in {'catalog', 'outline', 'search', 'read'}:
            raise HTTPException(422, '组织检索只接受固定组织资料的目录、检索与原文读取')
        if request.operation != 'search' and not request.document_id:
            # Browsing the authorized project resource list belongs to Java's
            # paged resource API. The legacy unscoped source catalog projects
            # every original before paging and is unsafe on this HTTP surface.
            raise HTTPException(422, '目录、提纲和原文读取需指定资料；请从项目资料列表选择')
        deadline = monotonic() + self.wait_seconds
        key = (actor, project, draft, execution, origin)
        session = self._claim(key, deadline)
        locked = cold_locked = admitted = False
        try:
            locked = session.lock.acquire(timeout=max(0, deadline-monotonic()))
            if not locked:
                raise self._busy()
            admitted = self._admission.acquire(timeout=max(0, deadline-monotonic()))
            if not admitted:
                raise self._busy()
            navigation = session.navigation
            if navigation is None:
                grant = from_thread.run(self.business, actor, 'POST',
                    f'projects/{project}/research-drafts/{draft}/material-access')
                validate_grant(grant, project, draft)
                authority = UserExecutionAuthority(actor, project, draft, execution, grant, self.business)
                reader = OrganizationExecutionReader(self.workspace, authority)
                navigation = OrganizationSourceNavigation(reader, workbench_url=origin,
                    retrieval_root=os.environ['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'],
                    preparation_lock=self._cold_lock)
                session.navigation = navigation
            if self._needs_preparation(navigation, request):
                cold_locked = self._cold_lock.acquire(timeout=max(0, deadline-monotonic()))
                if not cold_locked:
                    raise self._busy()
            try:
                # The production navigator owns before/after I/O and provider
                # checks. Do not wrap them in another identical grant cycle.
                result = navigation.navigate(request)
                return result
            except BaseException:
                # Failed authorization/storage/provider state is not kept warm.
                session.navigation = None
                raise
        finally:
            if cold_locked:
                self._cold_lock.release()
            if admitted:
                self._admission.release()
            if locked:
                session.lock.release()
            with self._changed:
                session.users -= 1
                if session.users == 0 and session.navigation is None:
                    self._sessions.pop(key, None)
                self._changed.notify_all()
