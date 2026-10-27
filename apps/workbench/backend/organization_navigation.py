"""Bound research navigation over HTTP, with current browser AND runtime authority.

The server keeps a bounded number of user-private navigation sessions. A cached
result is never an authorization lease, and this endpoint cannot admit a run.
"""
from collections import OrderedDict
from copy import deepcopy
import os
from threading import Lock

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


class OrganizationNavigationService:
    """One admitted operation at a time, two retained scopes, bounded queue wait.

    This conservative single-process profile protects developer/small deployments
    from concurrent full-index loads. Queue time and 429s must count in load tests.
    It does not promise parallel provider execution or multi-process cache sharing.
    """
    def __init__(self, workspace, business, *, maximum_sessions=2, wait_seconds=30):
        self.workspace, self.business = workspace, business
        self.maximum_sessions, self.wait_seconds = maximum_sessions, wait_seconds
        self._lock, self._sessions = Lock(), OrderedDict()

    def navigate(self, actor, project, draft, execution, origin, request):
        if request.source_space != 'organization' or request.operation not in {'catalog', 'outline', 'search', 'read'}:
            raise HTTPException(422, '组织检索只接受固定组织资料的目录、检索与原文读取')
        if request.operation != 'search' and not request.document_id:
            # Browsing the authorized project resource list belongs to Java's
            # paged resource API. The legacy unscoped source catalog projects
            # every original before paging and is unsafe on this HTTP surface.
            raise HTTPException(422, '目录、提纲和原文读取需指定资料；请从项目资料列表选择')
        if not self._lock.acquire(timeout=self.wait_seconds):
            raise HTTPException(429, '组织检索繁忙；本次未执行检索，请稍后手动重试')
        try:
            key = (actor, project, draft, execution, origin)
            navigation = self._sessions.get(key)
            if navigation is None:
                # Evict before allocating another full-corpus navigation state.
                while len(self._sessions) >= self.maximum_sessions:
                    self._sessions.popitem(last=False)
                grant = from_thread.run(self.business, actor, 'POST',
                    f'projects/{project}/research-drafts/{draft}/material-access')
                validate_grant(grant, project, draft)
                authority = UserExecutionAuthority(actor, project, draft, execution, grant, self.business)
                reader = OrganizationExecutionReader(self.workspace, authority)
                navigation = OrganizationSourceNavigation(reader, workbench_url=origin,
                    retrieval_root=os.environ['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'])
                self._sessions[key] = navigation
            self._sessions.move_to_end(key)
            try:
                # The production navigator owns before/after I/O and provider
                # checks. Do not wrap them in another identical grant cycle.
                result = navigation.navigate(request)
                return result
            except BaseException:
                # Failed authorization/storage/provider state is not kept warm.
                self._sessions.pop(key, None)
                raise
        finally:
            self._lock.release()
