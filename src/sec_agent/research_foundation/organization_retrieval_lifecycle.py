"""Run-scoped retrieval readiness; no permission leases or implicit latest release.

Initial preparation precedes model/tool access. Source-store changes schedule one
bounded background refresh and fail closed until its complete generation is ready.
Each stage keeps its own observations while reusing verified retrieval state.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
from threading import RLock

from .organization_execution_access import OrganizationExecutionUnavailable
from .organization_source_navigation import OrganizationSourceNavigation


class OrganizationRetrievalLifecycle:
    def __init__(self, reader, *, workbench_url, retrieval_root, grant):
        self.reader = reader
        self.workbench_url, self.retrieval_root = workbench_url, retrieval_root
        self.grant = deepcopy(grant)
        self._lock = RLock()
        self._state = 'unprepared'
        self._navigation = None
        self._executor = self._future = None
        self._generation = 0
        self._failure = None

    def _build(self):
        self.reader._after(self.grant)
        navigation = OrganizationSourceNavigation(self.reader, workbench_url=self.workbench_url,
                                                   retrieval_root=self.retrieval_root)
        navigation.warm_release()
        self.reader._after(self.grant)
        return navigation

    def prepare(self, *, retry_failed=False):
        """Synchronous admission/stage gate, before any model call; no embedding."""
        with self._lock:
            if self._state == 'closed':
                raise OrganizationExecutionUnavailable('organization_retrieval_closed')
            if self._state == 'ready':
                self._check_ready()
                return self.status()
            if self._state == 'refreshing':
                raise OrganizationExecutionUnavailable('organization_retrieval_refresh_pending')
            if self._state == 'failed' and not retry_failed:
                raise OrganizationExecutionUnavailable('organization_retrieval_failed')
            if self._state != 'preparing':
                self._schedule_refresh(state='preparing')
            future = self._future
        # Concurrent admission callers wait for the same build. Status remains
        # observable, and tool calls fail closed instead of waiting for the scan.
        future.result()
        with self._lock:
            self._check_ready()
            return self.status()

    def status(self):
        """Operational snapshot only. It neither authorizes nor serves content."""
        with self._lock:
            return {'state':self._state, 'generation':self._generation,
                    'failure_type':self._failure}

    def _check_ready(self):
        if self._state != 'ready':
            raise OrganizationExecutionUnavailable('organization_retrieval_'+self._state)
        # Revocation is never converted into a refresh that might grant access.
        try:
            self.reader._after(self.grant)
        except Exception as error:
            self._state, self._failure = 'failed', type(error).__name__
            raise
        nav = self._navigation
        try:
            nav.hybrid.release_cache.check()
        except Exception as error:
            self._state, self._failure = 'failed', type(error).__name__
            raise
        candidate = nav._candidate_index
        if candidate is not None and nav._search_cache.epoch() != candidate.epoch:
            self._schedule_refresh()
            raise OrganizationExecutionUnavailable('organization_retrieval_refresh_pending')

    def _schedule_refresh(self, *, state='refreshing'):
        # Caller holds the lock. There is at most one worker/future per run.
        if self._executor is None:
            self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='organization-retrieval')
        self._state, self._failure = state, None
        self._future = self._executor.submit(self._refresh)

    def _refresh(self):
        try:
            navigation = self._build()
        except Exception as error:
            with self._lock:
                if self._state != 'closed':
                    self._state, self._failure = 'failed', type(error).__name__
            raise
        with self._lock:
            if self._state == 'closed':
                return
            # Publish only a fully checked replacement for the SAME fixed grant.
            self._navigation = navigation
            self._generation += 1
            self._state = 'ready'

    def wait_for_refresh(self, timeout=None):
        """Host/test drain; ordinary queries never wait on background full scans."""
        with self._lock:
            future = self._future
        if future is not None:
            future.result(timeout=timeout)
        return self.status()

    def navigation(self):
        self.prepare()
        navigation = OrganizationSourceNavigation(self.reader, workbench_url=self.workbench_url,
                                                  retrieval_root=self.retrieval_root)
        navigation._retrieval_lifecycle = self
        return navigation

    @contextmanager
    def access(self, navigation):
        with self._lock:
            self._check_ready()
            if navigation.reader is not self.reader or navigation.workbench_url != self.workbench_url.rstrip('/'):
                raise OrganizationExecutionUnavailable('organization_retrieval_scope_mismatch')
            shared = self._navigation
            for field in ('hybrid', '_search_cache', '_projection_cache', '_candidate_index'):
                setattr(navigation, field, getattr(shared, field))
            try:
                yield
            finally:
                # Retrieval caches can be populated by legacy paths. Observed
                # sources and calculations always remain private to each stage.
                for field in ('_search_cache', '_projection_cache', '_candidate_index'):
                    setattr(shared, field, getattr(navigation, field))

    def close(self):
        with self._lock:
            self._state = 'closed'
            executor = self._executor
            self._navigation = None
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)
