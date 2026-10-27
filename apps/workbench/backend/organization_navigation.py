"""Bound research navigation over HTTP, with current browser AND runtime authority.

The server keeps a bounded number of user-private navigation sessions. A cached
result is never an authorization lease, and this endpoint cannot admit a run.
"""
from collections import OrderedDict
import os
from threading import Lock

from anyio import from_thread
from fastapi import HTTPException

from .organization_research_inputs import validate_grant
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationExecutionAuthority, OrganizationExecutionReader, OrganizationExecutionUnavailable,
    validate_execution_grant,
)
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation


class UserExecutionAuthority:
    def __init__(self, actor, project, draft, execution, grant, business):
        self.actor, self.project, self.draft = actor, project, draft
        self.business = business
        self.execution_id, self.manifest_digest = execution, grant['manifest_digest']
        self.runtime = OrganizationExecutionAuthority(
            base_url=os.environ['FINSIGHT_BUSINESS_API_URL'],
            secret=os.environ['FINSIGHT_ORGANIZATION_RUNTIME_SECRET'],
            execution_id=execution, manifest_digest=self.manifest_digest)

    def user_grant(self):
        grant = from_thread.run(self.business, self.actor, 'POST',
            f'projects/{self.project}/research-drafts/{self.draft}/material-access')
        validate_grant(grant, self.project, self.draft)
        if grant['manifest_digest'] != self.manifest_digest:
            raise OrganizationExecutionUnavailable('organization_navigation_manifest_changed')
        return grant

    def __call__(self):
        before = self.user_grant()
        grant = self.runtime()
        manifest, bindings = validate_execution_grant(grant, self.execution_id, self.manifest_digest)
        if (manifest != before['manifest'] or manifest['project_id'] != self.project
                or manifest['draft_id'] != self.draft
                or bindings != {item['resource_id']: item['binding'] for item in before['inputs']}):
            raise OrganizationExecutionUnavailable('organization_navigation_binding_mismatch')
        if self.user_grant() != before:
            raise OrganizationExecutionUnavailable('organization_navigation_authority_changed')
        return grant


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

    def navigate(self, actor, project, draft, execution, grant, origin, request):
        if request.source_space != 'organization' or request.operation not in {'catalog', 'outline', 'search', 'read'}:
            raise HTTPException(422, '组织检索只接受固定组织资料的目录、检索与原文读取')
        if not self._lock.acquire(timeout=self.wait_seconds):
            raise HTTPException(429, '组织检索繁忙；本次未执行检索，请稍后手动重试')
        try:
            key = (actor, project, draft, execution, grant['manifest_digest'], origin)
            navigation = self._sessions.get(key)
            if navigation is None:
                # Evict before allocating another full-corpus navigation state.
                while len(self._sessions) >= self.maximum_sessions:
                    self._sessions.popitem(last=False)
                authority = UserExecutionAuthority(actor, project, draft, execution, grant, self.business)
                reader = OrganizationExecutionReader(self.workspace, authority)
                reader.check()  # Reject mismatched execution before index I/O/providers.
                navigation = OrganizationSourceNavigation(reader, workbench_url=origin,
                    retrieval_root=os.environ['FINSIGHT_ORGANIZATION_RETRIEVAL_ROOT'])
                self._sessions[key] = navigation
            self._sessions.move_to_end(key)
            try:
                before, _, _ = navigation.reader._grant()
                result = navigation.navigate(request)
                navigation.reader._after(before)
                return result
            except BaseException:
                # Failed authorization/storage/provider state is not kept warm.
                self._sessions.pop(key, None)
                raise
        finally:
            self._lock.release()
