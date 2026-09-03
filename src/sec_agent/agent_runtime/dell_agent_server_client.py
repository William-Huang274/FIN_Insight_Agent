"""Thin LangGraph Agent Server SDK client for the Dell reference vertical.

Agent Server owns threads, runs, queues, checkpointing, resumable streams, and
state storage. This module uses the FIN-owned PostgreSQL identity repository to
bind canonical ``AgentSession`` / ``ResearchRun`` / ``RunInvocation`` IDs to
opaque server IDs. It deliberately has no direct graph invocation, SQLite
checkpointer, HTTP server, retry loop, or alternate runtime path.

The Agent Server create and FIN database bind cannot share one transaction.
Runs therefore carry FIN identity and request digests in server-owned metadata.
Before creating a run, and after an uncertain create outcome, the client scans
the one deterministic thread and adopts exactly one matching remote run.  It
never chooses between duplicates and never retries a remote create internally.
Agent Server's reject strategy plus a short scheduled-start delay narrows the
concurrent check/create window while the server-side graph independently
requires the durable FIN binding before opening data or tool resources.  This
is bounded reconciliation, not a claim of distributed exactly-once delivery.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from langgraph_sdk import get_sync_client
from langgraph_sdk.schema import StreamPart, ThreadState

from sec_agent.canonical_runtime.contracts_v1_2 import (
    AgentSessionV1_2,
    ResearchRun,
    RunInvocation,
)

from .dell_agent_server_identity import (
    DELL_AGENT_SERVER_ASSISTANT_ID,
    DellAgentServerIdentityRepository,
    DellAgentServerIdentityStoreError,
    PersistedAgentSessionBinding,
    PersistedRunInvocationBinding,
    agent_session_identity_digest,
    research_run_identity_digest,
    run_invocation_identity_digest,
    validate_agent_session,
    validate_research_run,
    validate_run_invocation,
)
from .dell_reference_vertical_contracts import canonical_sha256
from .dell_reference_vertical_graph import DellReferenceVerticalGraphInput
from .dell_zero_model_graph_qualification import (
    DellExecutionProfile,
    DellZeroModelQualificationError,
    PRODUCT_EXECUTION_PROFILE,
    require_execution_profile,
)


_LEGACY_DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION = (
    "fin_ia_dell_agent_server_client_v1_0"
)
DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION = "fin_ia_dell_agent_server_client_v1_1"

_STREAM_ID_PATTERN = re.compile(r"^(?P<milliseconds>[0-9]+)-(?P<sequence>[0-9]+)$")
_ALLOWED_STREAM_EVENTS = frozenset({"metadata", "updates", "end"})
_ALLOWED_SERVER_RUN_STATUSES = frozenset(
    {"pending", "running", "error", "success", "timeout", "interrupted"}
)
_RUN_RECONCILIATION_PAGE_SIZE = 100
_RUN_RECONCILIATION_MAX_ROWS = 1_000
_RUN_RECONCILIATION_SELECT = [
    "run_id",
    "thread_id",
    "assistant_id",
    "status",
    "metadata",
]
# Agent Server 0.13.3 does not accept a caller-assigned run ID or idempotency
# key.  Scheduling the background run briefly in the future lets the ingress
# persist the returned server ID before the graph factory enforces that binding.
_RUN_BINDING_GRACE_SECONDS = 2
_DELL_SESSION_THREAD_NAMESPACE = uuid5(
    NAMESPACE_URL,
    "https://fin-insight.local/dell-agent-server/session/v1",
)


class DellAgentServerClientError(RuntimeError):
    """Secret-free, machine-readable client boundary failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _required_identifier(value: Any, *, code: str, maximum: int = 240) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or len(value) > maximum
    ):
        raise DellAgentServerClientError(code)
    return value


def _server_uuid(value: Any, *, code: str) -> str:
    identifier = _required_identifier(value, code=code)
    try:
        parsed = UUID(identifier)
    except (TypeError, ValueError, AttributeError):
        raise DellAgentServerClientError(code) from None
    if str(parsed) != identifier.lower():
        raise DellAgentServerClientError(code)
    return identifier


def _server_run_status(value: Any, *, code: str) -> str:
    status = _required_identifier(value, code=code, maximum=80)
    if status not in _ALLOWED_SERVER_RUN_STATUSES:
        raise DellAgentServerClientError(code)
    return status


def _metadata_contains(
    observed: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    return all(observed.get(key) == value for key, value in expected.items())


def _stream_order_key(value: str, *, code: str) -> tuple[int, int]:
    match = _STREAM_ID_PATTERN.fullmatch(value)
    if match is None:
        raise DellAgentServerClientError(code)
    return int(match.group("milliseconds")), int(match.group("sequence"))


def _deterministic_session_thread_id(session: AgentSessionV1_2) -> str:
    """Derive the stable Agent Server thread UUID for one FIN session key."""

    return str(
        uuid5(
            _DELL_SESSION_THREAD_NAMESPACE,
            f"{session.session_id}\0{session.thread_id}",
        )
    )


def _validate_identity_contract(validator: Any, value: Any) -> Any:
    try:
        return validator(value)
    except DellAgentServerIdentityStoreError as exc:
        raise DellAgentServerClientError(exc.code) from None
    except Exception:
        raise DellAgentServerClientError("fin_identity_contract_invalid") from None


@dataclass(frozen=True, slots=True)
class DellAgentServerSessionBinding:
    """One FIN AgentSession bound to one Agent Server thread UUID."""

    agent_session_id: str
    server_thread_id: str
    assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID
    schema_version: str = DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _required_identifier(
            self.agent_session_id,
            code="fin_agent_session_id_invalid",
            maximum=180,
        )
        _server_uuid(
            self.server_thread_id,
            code="agent_server_thread_id_invalid",
        )
        if self.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID:
            raise DellAgentServerClientError("agent_server_assistant_id_invalid")
        if self.schema_version != DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION:
            raise DellAgentServerClientError("agent_server_client_schema_invalid")


@dataclass(frozen=True, slots=True)
class DellAgentServerRunBinding:
    """One FIN RunInvocation bound to one server-assigned run UUID."""

    agent_session_id: str
    research_run_id: str
    run_invocation_id: str
    server_thread_id: str
    server_run_id: str
    invocation_kind: Literal["start", "resume"]
    server_status: str
    execution_profile: DellExecutionProfile = PRODUCT_EXECUTION_PROFILE
    assistant_id: str = DELL_AGENT_SERVER_ASSISTANT_ID
    schema_version: str = DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for value, code in (
            (self.agent_session_id, "fin_agent_session_id_invalid"),
            (self.research_run_id, "fin_research_run_id_invalid"),
            (self.run_invocation_id, "fin_run_invocation_id_invalid"),
        ):
            _required_identifier(value, code=code, maximum=180)
        _server_uuid(
            self.server_thread_id,
            code="agent_server_thread_id_invalid",
        )
        _server_uuid(self.server_run_id, code="agent_server_run_id_invalid")
        if self.invocation_kind not in {"start", "resume"}:
            raise DellAgentServerClientError("fin_run_invocation_kind_invalid")
        try:
            require_execution_profile(self.execution_profile)
        except DellZeroModelQualificationError:
            raise DellAgentServerClientError(
                "agent_server_execution_profile_invalid"
            ) from None
        _required_identifier(
            self.server_status,
            code="agent_server_run_status_invalid",
            maximum=80,
        )
        if self.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID:
            raise DellAgentServerClientError("agent_server_assistant_id_invalid")
        if self.schema_version != DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION:
            raise DellAgentServerClientError("agent_server_client_schema_invalid")


class DellAgentServerClient:
    """Product caller for the single Agent-Server-hosted Dell graph.

    LangSmith tracing and its single project are mandatory server deployment
    configuration (``LANGSMITH_TRACING`` / ``LANGSMITH_PROJECT``), not run-level
    client options.  Agent Server 0.13.3 replicates traces when a run-level
    project is supplied in addition to the deployment default, so this client
    deliberately sends no ``langsmith_tracing`` override.  That is neither a
    tracing opt-out nor a runtime fallback.  Credentials are never accepted or
    retained by this wrapper; the official SDK resolves its client credential
    from supported environment variables.
    """

    __slots__ = (
        "_closed",
        "_identity_repository",
        "_owns_sdk_client",
        "_sdk",
        "_execution_profile",
        "_server_assistant_uuid",
    )

    def __init__(
        self,
        sdk_client: Any,
        *,
        identity_repository: DellAgentServerIdentityRepository,
        owns_sdk_client: bool = False,
        execution_profile: DellExecutionProfile = PRODUCT_EXECUTION_PROFILE,
    ) -> None:
        if sdk_client is None:
            raise DellAgentServerClientError("agent_server_sdk_client_required")
        if identity_repository is None:
            raise DellAgentServerClientError(
                "fin_identity_repository_required"
            )
        if not isinstance(owns_sdk_client, bool):
            raise DellAgentServerClientError("agent_server_sdk_ownership_invalid")
        try:
            selected_execution_profile = require_execution_profile(
                execution_profile
            )
        except DellZeroModelQualificationError:
            raise DellAgentServerClientError(
                "agent_server_execution_profile_invalid"
            ) from None
        self._sdk = sdk_client
        self._identity_repository = identity_repository
        self._owns_sdk_client = owns_sdk_client
        self._execution_profile = selected_execution_profile
        self._closed = False
        self._server_assistant_uuid: str | None = None

    @classmethod
    def connect(
        cls,
        *,
        url: str,
        identity_repository: DellAgentServerIdentityRepository,
        timeout: Any | None = None,
        execution_profile: DellExecutionProfile = PRODUCT_EXECUTION_PROFILE,
    ) -> "DellAgentServerClient":
        """Create the official sync SDK client without handling a key itself."""

        server_url = _required_identifier(
            url,
            code="agent_server_url_invalid",
            maximum=2_048,
        )
        parsed = urlsplit(server_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise DellAgentServerClientError("agent_server_url_invalid")
        if parsed.query or parsed.fragment:
            raise DellAgentServerClientError("agent_server_url_invalid")
        if parsed.username is not None or parsed.password is not None:
            raise DellAgentServerClientError("agent_server_url_credentials_forbidden")
        try:
            kwargs = {"url": server_url}
            if timeout is not None:
                kwargs["timeout"] = timeout
            sdk_client = get_sync_client(**kwargs)
        except Exception:
            raise DellAgentServerClientError("agent_server_sdk_connect_failed") from None
        return cls(
            sdk_client,
            identity_repository=identity_repository,
            owns_sdk_client=True,
            execution_profile=execution_profile,
        )

    def __enter__(self) -> "DellAgentServerClient":
        self._ensure_open()
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_value: BaseException | None,
        _traceback: Any,
    ) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise DellAgentServerClientError("agent_server_client_closed")

    def close(self) -> None:
        """Close a wrapper-owned SDK client; injected clients remain caller-owned."""

        if self._closed:
            return
        if self._owns_sdk_client:
            close = getattr(self._sdk, "close", None)
            if not callable(close):
                raise DellAgentServerClientError("agent_server_sdk_close_unavailable")
            try:
                close()
            except Exception:
                raise DellAgentServerClientError("agent_server_sdk_close_failed") from None
        self._closed = True

    def create_agent_session(
        self,
        *,
        agent_session: AgentSessionV1_2,
    ) -> DellAgentServerSessionBinding:
        """Return or create the one thread durably owned by an AgentSession.

        Agent Server 0.13.3 accepts a caller-supplied thread UUID and supports
        ``if_exists=do_nothing``. New sessions therefore use a deterministic
        UUID and every call idempotently ensures that exact remote thread. A
        previously persisted non-deterministic UUID remains readable for
        migration compatibility and is also ensured rather than replaced.
        """

        self._ensure_open()
        session_contract = _validate_identity_contract(
            validate_agent_session,
            agent_session,
        )
        session_id = session_contract.session_id
        identity_digest = agent_session_identity_digest(session_contract)
        persisted = self._identity_read(
            self._identity_repository.get_agent_session,
            agent_session_id=session_id,
        )
        if persisted is not None:
            durable_binding = self._session_binding_from_persisted(
                persisted,
                agent_session=session_contract,
                expected_identity_digest=identity_digest,
            )
            server_thread_id = durable_binding.server_thread_id
        else:
            durable_binding = None
            server_thread_id = _deterministic_session_thread_id(
                session_contract
            )

        metadata = {
            "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
            "agent_session_id": session_id,
            "fin_thread_id": session_contract.thread_id,
            "session_identity_digest": identity_digest,
        }
        try:
            created = self._sdk.threads.create(
                metadata=metadata,
                thread_id=server_thread_id,
                if_exists="do_nothing",
                graph_id=DELL_AGENT_SERVER_ASSISTANT_ID,
            )
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_session_create_failed"
            ) from None
        if not isinstance(created, Mapping):
            raise DellAgentServerClientError("agent_server_session_response_invalid")
        returned_thread_id = _server_uuid(
            created.get("thread_id"),
            code="agent_server_session_response_invalid",
        )
        if returned_thread_id != server_thread_id:
            raise DellAgentServerClientError(
                "agent_server_session_identity_mismatch"
            )
        returned_metadata = created.get("metadata")
        legacy_metadata = {
            **metadata,
            "fin_client_schema_version": (
                _LEGACY_DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
            ),
        }
        metadata_matches = isinstance(returned_metadata, Mapping) and (
            _metadata_contains(returned_metadata, metadata)
            or (
                durable_binding is not None
                and _metadata_contains(returned_metadata, legacy_metadata)
            )
        )
        if not metadata_matches:
            raise DellAgentServerClientError(
                "agent_server_session_identity_mismatch"
            )
        if durable_binding is not None:
            return durable_binding
        return self._persist_session_binding(
            agent_session=session_contract,
            server_thread_id=returned_thread_id,
        )

    def start_run(
        self,
        *,
        session: DellAgentServerSessionBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        graph_input: Mapping[str, Any],
    ) -> DellAgentServerRunBinding:
        """Create a background server run for a new FIN ResearchRun invocation."""

        self._ensure_open()
        if not isinstance(session, DellAgentServerSessionBinding):
            raise DellAgentServerClientError("agent_server_session_binding_invalid")
        run_contract = _validate_identity_contract(
            validate_research_run,
            research_run,
        )
        invocation_contract = _validate_identity_contract(
            validate_run_invocation,
            run_invocation,
        )
        self._validate_run_lineage(
            session=session,
            research_run=run_contract,
            run_invocation=invocation_contract,
            invocation_kind="start",
        )
        if not isinstance(graph_input, Mapping):
            raise DellAgentServerClientError("agent_server_graph_input_invalid")
        try:
            validated_input = DellReferenceVerticalGraphInput.model_validate(
                graph_input
            )
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_graph_input_invalid"
            ) from None
        if validated_input.run_id != run_contract.run_id:
            raise DellAgentServerClientError("fin_research_run_input_mismatch")
        return self._create_run(
            session=session,
            research_run=run_contract,
            run_invocation=invocation_contract,
            invocation_kind="start",
            graph_input=validated_input.model_dump(mode="json"),
            resume_payload=None,
        )

    def resume_run(
        self,
        *,
        prior_run: DellAgentServerRunBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        resume_payload: Mapping[str, Any],
    ) -> DellAgentServerRunBinding:
        """Resume an interrupted ResearchRun as a new server RunInvocation."""

        self._ensure_open()
        if not isinstance(prior_run, DellAgentServerRunBinding):
            raise DellAgentServerClientError("agent_server_prior_run_binding_invalid")
        run_contract = _validate_identity_contract(
            validate_research_run,
            research_run,
        )
        invocation_contract = _validate_identity_contract(
            validate_run_invocation,
            run_invocation,
        )
        if invocation_contract.invocation_id == prior_run.run_invocation_id:
            raise DellAgentServerClientError("fin_run_invocation_id_reused")
        if prior_run.execution_profile != self._execution_profile:
            raise DellAgentServerClientError(
                "agent_server_resume_execution_profile_mismatch"
            )
        if (
            prior_run.agent_session_id != run_contract.session_id
            or prior_run.research_run_id != run_contract.run_id
        ):
            raise DellAgentServerClientError("fin_research_run_lineage_mismatch")
        if not isinstance(resume_payload, Mapping) or not resume_payload:
            raise DellAgentServerClientError("agent_server_resume_payload_invalid")
        session = DellAgentServerSessionBinding(
            agent_session_id=prior_run.agent_session_id,
            server_thread_id=prior_run.server_thread_id,
        )
        self._validate_run_lineage(
            session=session,
            research_run=run_contract,
            run_invocation=invocation_contract,
            invocation_kind="resume",
        )
        self._validate_durable_resume_predecessor(
            prior_run=prior_run,
            research_run=run_contract,
            run_invocation=invocation_contract,
        )
        return self._create_run(
            session=session,
            research_run=run_contract,
            run_invocation=invocation_contract,
            invocation_kind="resume",
            graph_input=None,
            resume_payload=dict(resume_payload),
        )

    def _create_run(
        self,
        *,
        session: DellAgentServerSessionBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        invocation_kind: Literal["start", "resume"],
        graph_input: Mapping[str, Any] | None,
        resume_payload: Mapping[str, Any] | None,
    ) -> DellAgentServerRunBinding:
        research_id = research_run.run_id
        invocation_id = run_invocation.invocation_id
        persisted_session = self._identity_read(
            self._identity_repository.get_agent_session,
            agent_session_id=session.agent_session_id,
        )
        if persisted_session is None:
            raise DellAgentServerClientError(
                "fin_agent_session_durable_binding_missing"
            )
        if (
            persisted_session.server_thread_id != session.server_thread_id
            or persisted_session.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID
        ):
            raise DellAgentServerClientError(
                "fin_agent_session_durable_binding_conflict"
            )
        server_assistant_uuid = self._resolve_server_assistant_uuid()
        context = {
            "agent_session_id": session.agent_session_id,
            "research_run_id": research_id,
            "run_invocation_id": invocation_id,
        }
        launch_contract = {
            "client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
            "assistant_id": DELL_AGENT_SERVER_ASSISTANT_ID,
            "server_assistant_uuid": server_assistant_uuid,
            "execution_profile": self._execution_profile,
            "server_thread_id": session.server_thread_id,
            "invocation_kind": invocation_kind,
            "context": context,
            "graph_input": graph_input if invocation_kind == "start" else None,
            "command": (
                None
                if invocation_kind == "start"
                else {"resume": resume_payload}
            ),
            "transport": {
                "stream_mode": ["updates"],
                "stream_resumable": True,
                "durability": "sync",
                "multitask_strategy": "reject",
                "if_not_exists": "reject",
                "after_seconds": _RUN_BINDING_GRACE_SECONDS,
            },
        }
        metadata = {
            "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
            "fin_assistant_graph_id": DELL_AGENT_SERVER_ASSISTANT_ID,
            "server_assistant_uuid": server_assistant_uuid,
            "execution_profile": self._execution_profile,
            **context,
            "invocation_ordinal": run_invocation.ordinal,
            "invocation_kind": invocation_kind,
            "session_identity_digest": persisted_session.session_identity_digest,
            "research_run_identity_digest": research_run_identity_digest(
                research_run
            ),
            "run_invocation_identity_digest": run_invocation_identity_digest(
                run_invocation
            ),
            "launch_request_digest": canonical_sha256(launch_contract),
            "durable_identity_gate_version": (
                "fin_ia_dell_agent_server_durable_identity_gate_v1_0"
            ),
        }
        legacy_bound_metadata = {
            "fin_client_schema_version": (
                _LEGACY_DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
            ),
            **context,
            "invocation_kind": invocation_kind,
        }
        existing = self._identity_read(
            self._identity_repository.get_run_invocation,
            run_invocation_id=invocation_id,
        )
        if existing is not None:
            observed = self._get_bound_server_run(
                server_thread_id=session.server_thread_id,
                server_run_id=existing.server_run_id,
                expected_metadata=metadata,
                legacy_expected_metadata=legacy_bound_metadata,
                expected_assistant_id=server_assistant_uuid,
            )
            return self._run_binding_from_persisted(
                existing,
                session=session,
                research_run=research_run,
                run_invocation=run_invocation,
                invocation_kind=invocation_kind,
                observed_server_status=observed["status"],
            )
        if invocation_kind == "start":
            aggregate = self._identity_read(
                self._identity_repository.get_research_run_aggregate,
                research_run_id=research_id,
            )
            if aggregate is not None:
                raise DellAgentServerClientError(
                    "fin_start_durable_invocation_conflict"
                )

        reconciled = self._find_reconcilable_server_run(
            server_thread_id=session.server_thread_id,
            expected_metadata=metadata,
        )
        if reconciled is not None:
            return self._persist_reconciled_run_binding(
                reconciled,
                research_run=research_run,
                run_invocation=run_invocation,
                invocation_kind=invocation_kind,
            )

        kwargs: dict[str, Any] = {
            "stream_mode": ["updates"],
            "stream_resumable": True,
            "durability": "sync",
            "multitask_strategy": "reject",
            "if_not_exists": "reject",
            "context": context,
            "metadata": metadata,
            "after_seconds": _RUN_BINDING_GRACE_SECONDS,
        }
        if invocation_kind == "start":
            kwargs["input"] = graph_input
            error_code = "agent_server_run_start_failed"
        else:
            kwargs["command"] = {"resume": resume_payload}
            error_code = "agent_server_run_resume_failed"
        try:
            created = self._sdk.runs.create(
                session.server_thread_id,
                DELL_AGENT_SERVER_ASSISTANT_ID,
                **kwargs,
            )
        except Exception:
            try:
                reconciled = self._find_reconcilable_server_run(
                    server_thread_id=session.server_thread_id,
                    expected_metadata=metadata,
                )
            except DellAgentServerClientError:
                raise DellAgentServerClientError(
                    f"{error_code}_outcome_unknown"
                ) from None
            if reconciled is None:
                raise DellAgentServerClientError(
                    f"{error_code}_outcome_unknown"
                ) from None
            return self._persist_reconciled_run_binding(
                reconciled,
                research_run=research_run,
                run_invocation=run_invocation,
                invocation_kind=invocation_kind,
            )

        try:
            validated_created = self._validate_server_run(
                created,
                expected_thread_id=session.server_thread_id,
                expected_metadata=metadata,
                expected_assistant_id=server_assistant_uuid,
            )
        except DellAgentServerClientError:
            try:
                reconciled = self._find_reconcilable_server_run(
                    server_thread_id=session.server_thread_id,
                    expected_metadata=metadata,
                )
            except DellAgentServerClientError as scan_error:
                if scan_error.code in {
                    "agent_server_run_reconciliation_identity_conflict",
                    "agent_server_run_reconciliation_ambiguous",
                }:
                    raise
                raise DellAgentServerClientError(
                    "agent_server_run_response_invalid_outcome_unknown"
                ) from None
            if reconciled is None:
                raise DellAgentServerClientError(
                    "agent_server_run_response_invalid_outcome_unknown"
                ) from None
            validated_created = reconciled
        return self._persist_run_binding(
            research_run=research_run,
            run_invocation=run_invocation,
            invocation_kind=invocation_kind,
            server_thread_id=validated_created["thread_id"],
            server_run_id=validated_created["run_id"],
            server_status=validated_created["status"],
        )

    def _validate_server_run(
        self,
        value: Any,
        *,
        expected_thread_id: str,
        expected_metadata: Mapping[str, Any] | None = None,
        expected_assistant_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise DellAgentServerClientError("agent_server_run_response_invalid")
        thread_id = _server_uuid(
            value.get("thread_id"),
            code="agent_server_run_response_invalid",
        )
        if thread_id != expected_thread_id:
            raise DellAgentServerClientError("agent_server_run_thread_mismatch")
        run_id = _server_uuid(
            value.get("run_id"),
            code="agent_server_run_response_invalid",
        )
        # Agent Server resolves the graph selector to a concrete assistant UUID.
        # FIN persists the stable graph selector separately; the observed UUID is
        # still required to be a well-formed server identity.
        assistant_id = _server_uuid(
            value.get("assistant_id"),
            code="agent_server_run_response_invalid",
        )
        if (
            expected_assistant_id is not None
            and assistant_id != expected_assistant_id
        ):
            raise DellAgentServerClientError(
                "agent_server_run_assistant_identity_mismatch"
            )
        status = _server_run_status(
            value.get("status"),
            code="agent_server_run_response_invalid",
        )
        raw_metadata = value.get("metadata")
        if not isinstance(raw_metadata, Mapping):
            raise DellAgentServerClientError("agent_server_run_response_invalid")
        metadata = dict(raw_metadata)
        try:
            canonical_sha256(metadata)
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_run_response_invalid"
            ) from None
        if expected_metadata is not None and any(
            metadata.get(key) != expected
            for key, expected in expected_metadata.items()
        ):
            raise DellAgentServerClientError(
                "agent_server_run_metadata_mismatch"
            )
        return {
            "run_id": run_id,
            "thread_id": thread_id,
            "assistant_id": assistant_id,
            "status": status,
            "metadata": metadata,
        }

    def _get_bound_server_run(
        self,
        *,
        server_thread_id: str,
        server_run_id: str,
        expected_metadata: Mapping[str, Any],
        legacy_expected_metadata: Mapping[str, Any],
        expected_assistant_id: str,
    ) -> dict[str, Any]:
        """Read one durable binding, accepting only the explicit legacy shape."""

        try:
            observed = self._sdk.runs.get(server_thread_id, server_run_id)
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_bound_run_read_failed"
            ) from None
        validated = self._validate_server_run(
            observed,
            expected_thread_id=server_thread_id,
            expected_assistant_id=expected_assistant_id,
        )
        if validated["run_id"] != server_run_id:
            raise DellAgentServerClientError(
                "agent_server_bound_run_identity_mismatch"
            )
        metadata = validated["metadata"]
        if _metadata_contains(metadata, expected_metadata):
            return validated
        if (
            self._execution_profile == PRODUCT_EXECUTION_PROFILE
            and metadata.get("fin_client_schema_version")
            == _LEGACY_DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION
            and _metadata_contains(metadata, legacy_expected_metadata)
        ):
            return validated
        raise DellAgentServerClientError("agent_server_run_metadata_mismatch")

    def _scan_server_runs_once(
        self,
        *,
        server_thread_id: str,
    ) -> tuple[dict[str, Any], ...]:
        rows_by_id: dict[str, dict[str, Any]] = {}
        offset = 0
        while offset < _RUN_RECONCILIATION_MAX_ROWS:
            limit = min(
                _RUN_RECONCILIATION_PAGE_SIZE,
                _RUN_RECONCILIATION_MAX_ROWS - offset,
            )
            try:
                page = self._sdk.runs.list(
                    server_thread_id,
                    limit=limit,
                    offset=offset,
                    select=list(_RUN_RECONCILIATION_SELECT),
                )
            except Exception:
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_list_failed"
                ) from None
            if (
                not isinstance(page, Sequence)
                or isinstance(page, (str, bytes, bytearray))
                or len(page) > limit
            ):
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_page_invalid"
                )
            for raw in page:
                row = self._validate_server_run(
                    raw,
                    expected_thread_id=server_thread_id,
                )
                if row["run_id"] in rows_by_id:
                    raise DellAgentServerClientError(
                        "agent_server_run_reconciliation_duplicate_run_id"
                    )
                rows_by_id[row["run_id"]] = row
            offset += len(page)
            if len(page) < limit:
                break
        else:  # pragma: no cover - loop always exits through offset ceiling
            pass

        if offset == _RUN_RECONCILIATION_MAX_ROWS:
            try:
                overflow = self._sdk.runs.list(
                    server_thread_id,
                    limit=1,
                    offset=offset,
                    select=list(_RUN_RECONCILIATION_SELECT),
                )
            except Exception:
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_list_failed"
                ) from None
            if (
                not isinstance(overflow, Sequence)
                or isinstance(overflow, (str, bytes, bytearray))
                or len(overflow) > 1
            ):
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_page_invalid"
                )
            if overflow:
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_scan_limit_exceeded"
                )

        return tuple(rows_by_id[key] for key in sorted(rows_by_id))

    @staticmethod
    def _run_snapshot_fingerprint(rows: Sequence[Mapping[str, Any]]) -> str:
        # Status is intentionally excluded: pending -> running -> terminal is a
        # legitimate transition while the two offset scans execute.  Identity,
        # assistant and metadata are immutable for the reconciliation decision.
        return canonical_sha256(
            [
                {
                    "run_id": row["run_id"],
                    "thread_id": row["thread_id"],
                    "assistant_id": row["assistant_id"],
                    "metadata": row["metadata"],
                }
                for row in rows
            ]
        )

    def _stable_server_run_snapshot(
        self,
        *,
        server_thread_id: str,
    ) -> tuple[dict[str, Any], ...]:
        first = self._scan_server_runs_once(server_thread_id=server_thread_id)
        second = self._scan_server_runs_once(server_thread_id=server_thread_id)
        if self._run_snapshot_fingerprint(first) != self._run_snapshot_fingerprint(
            second
        ):
            raise DellAgentServerClientError(
                "agent_server_run_reconciliation_snapshot_unstable"
            )
        return second

    def _find_reconcilable_server_run(
        self,
        *,
        server_thread_id: str,
        expected_metadata: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        rows = self._stable_server_run_snapshot(
            server_thread_id=server_thread_id
        )
        exact: list[dict[str, Any]] = []
        expected_invocation_id = expected_metadata["run_invocation_id"]
        expected_research_id = expected_metadata["research_run_id"]
        expected_ordinal = expected_metadata["invocation_ordinal"]
        for row in rows:
            metadata = row["metadata"]
            same_invocation = (
                metadata.get("run_invocation_id") == expected_invocation_id
            )
            same_run_ordinal = (
                metadata.get("research_run_id") == expected_research_id
                and metadata.get("invocation_ordinal") == expected_ordinal
            )
            if not same_invocation and not same_run_ordinal:
                continue
            if any(
                metadata.get(key) != expected
                for key, expected in expected_metadata.items()
            ) or row["assistant_id"] != expected_metadata["server_assistant_uuid"]:
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_identity_conflict"
                )
            exact.append(row)
        if len(exact) > 1:
            raise DellAgentServerClientError(
                "agent_server_run_reconciliation_ambiguous"
            )
        return exact[0] if exact else None

    def _resolve_server_assistant_uuid(self) -> str:
        if self._server_assistant_uuid is not None:
            return self._server_assistant_uuid
        try:
            rows = self._sdk.assistants.search(
                graph_id=DELL_AGENT_SERVER_ASSISTANT_ID,
                limit=2,
                offset=0,
            )
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_assistant_resolution_failed"
            ) from None
        if (
            not isinstance(rows, Sequence)
            or isinstance(rows, (str, bytes, bytearray))
            or len(rows) != 1
            or not isinstance(rows[0], Mapping)
            or rows[0].get("graph_id") != DELL_AGENT_SERVER_ASSISTANT_ID
        ):
            raise DellAgentServerClientError(
                "agent_server_assistant_resolution_ambiguous"
            )
        resolved = _server_uuid(
            rows[0].get("assistant_id"),
            code="agent_server_assistant_resolution_invalid",
        )
        self._server_assistant_uuid = resolved
        return resolved

    def _persist_reconciled_run_binding(
        self,
        observed: Mapping[str, Any],
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        invocation_kind: Literal["start", "resume"],
    ) -> DellAgentServerRunBinding:
        existing = self._identity_read(
            self._identity_repository.get_run_invocation,
            run_invocation_id=run_invocation.invocation_id,
        )
        if existing is not None:
            if (
                existing.server_thread_id != observed["thread_id"]
                or existing.server_run_id != observed["run_id"]
            ):
                raise DellAgentServerClientError(
                    "agent_server_run_reconciliation_concurrent_binding_conflict"
                )
            return self._run_binding_from_persisted(
                existing,
                session=DellAgentServerSessionBinding(
                    agent_session_id=research_run.session_id,
                    server_thread_id=observed["thread_id"],
                ),
                research_run=research_run,
                run_invocation=run_invocation,
                invocation_kind=invocation_kind,
                observed_server_status=observed["status"],
            )
        if observed["status"] in {"running", "success"}:
            raise DellAgentServerClientError(
                "agent_server_run_reconciliation_operator_review_required"
            )
        return self._persist_run_binding(
            research_run=research_run,
            run_invocation=run_invocation,
            invocation_kind=invocation_kind,
            server_thread_id=observed["thread_id"],
            server_run_id=observed["run_id"],
            server_status=observed["status"],
        )

    def _persist_session_binding(
        self,
        *,
        agent_session: AgentSessionV1_2,
        server_thread_id: str,
    ) -> DellAgentServerSessionBinding:
        persisted = self._identity_write(
            self._identity_repository.bind_agent_session,
            agent_session=agent_session,
            server_thread_id=server_thread_id,
            assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
        )
        return self._session_binding_from_persisted(
            persisted,
            agent_session=agent_session,
            expected_identity_digest=agent_session_identity_digest(agent_session),
        )

    def _persist_run_binding(
        self,
        *,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        invocation_kind: Literal["start", "resume"],
        server_thread_id: str,
        server_run_id: str,
        server_status: str,
    ) -> DellAgentServerRunBinding:
        persisted = self._identity_write(
            self._identity_repository.bind_run_invocation,
            research_run=research_run,
            run_invocation=run_invocation,
            server_thread_id=server_thread_id,
            server_run_id=server_run_id,
            server_invocation_kind=invocation_kind,
            first_server_status=server_status,
            assistant_id=DELL_AGENT_SERVER_ASSISTANT_ID,
        )
        return self._run_binding_from_persisted(
            persisted,
            session=DellAgentServerSessionBinding(
                agent_session_id=research_run.session_id,
                server_thread_id=server_thread_id,
            ),
            research_run=research_run,
            run_invocation=run_invocation,
            invocation_kind=invocation_kind,
            observed_server_status=server_status,
        )

    def _session_binding_from_persisted(
        self,
        persisted: PersistedAgentSessionBinding,
        *,
        agent_session: AgentSessionV1_2,
        expected_identity_digest: str,
    ) -> DellAgentServerSessionBinding:
        if (
            persisted.agent_session_id != agent_session.session_id
            or persisted.fin_thread_id != agent_session.thread_id
            or persisted.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID
            or persisted.session_identity_digest != expected_identity_digest
        ):
            raise DellAgentServerClientError(
                "fin_agent_session_durable_binding_conflict"
            )
        return DellAgentServerSessionBinding(
            agent_session_id=persisted.agent_session_id,
            server_thread_id=persisted.server_thread_id,
        )

    def _run_binding_from_persisted(
        self,
        persisted: PersistedRunInvocationBinding,
        *,
        session: DellAgentServerSessionBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        invocation_kind: Literal["start", "resume"],
        observed_server_status: str | None = None,
    ) -> DellAgentServerRunBinding:
        aggregate = self._identity_read(
            self._identity_repository.get_research_run_aggregate,
            research_run_id=research_run.run_id,
        )
        if aggregate is None:
            raise DellAgentServerClientError(
                "fin_research_run_durable_aggregate_missing"
            )
        if (
            aggregate.research_run.run_identity_digest
            != research_run_identity_digest(research_run)
            or persisted.run_invocation_id != run_invocation.invocation_id
            or persisted.research_run_id != research_run.run_id
            or persisted.agent_session_id != research_run.session_id
            or persisted.invocation_ordinal != run_invocation.ordinal
            or persisted.invocation_identity_digest
            != run_invocation_identity_digest(run_invocation)
            or persisted.server_invocation_kind != invocation_kind
            or persisted.server_thread_id != session.server_thread_id
            or persisted.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID
        ):
            raise DellAgentServerClientError(
                "fin_run_invocation_durable_binding_conflict"
            )
        return DellAgentServerRunBinding(
            agent_session_id=persisted.agent_session_id,
            research_run_id=persisted.research_run_id,
            run_invocation_id=persisted.run_invocation_id,
            server_thread_id=persisted.server_thread_id,
            server_run_id=persisted.server_run_id,
            invocation_kind=invocation_kind,
            server_status=(
                observed_server_status or persisted.first_server_status
            ),
            execution_profile=self._execution_profile,
        )

    def _validate_run_lineage(
        self,
        *,
        session: DellAgentServerSessionBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
        invocation_kind: Literal["start", "resume"],
    ) -> None:
        if research_run.session_id != session.agent_session_id:
            raise DellAgentServerClientError("fin_research_run_session_mismatch")
        if (
            run_invocation.session_id != research_run.session_id
            or run_invocation.run_id != research_run.run_id
        ):
            raise DellAgentServerClientError("fin_run_invocation_lineage_mismatch")
        if invocation_kind == "start":
            if (
                run_invocation.invocation_kind != "START"
                or run_invocation.ordinal != 1
            ):
                raise DellAgentServerClientError(
                    "fin_run_invocation_kind_mismatch"
                )
        elif (
            run_invocation.invocation_kind not in {"RESUME", "RECOVERY"}
            or run_invocation.ordinal <= 1
        ):
            raise DellAgentServerClientError("fin_run_invocation_kind_mismatch")

    def _validate_durable_resume_predecessor(
        self,
        *,
        prior_run: DellAgentServerRunBinding,
        research_run: ResearchRun,
        run_invocation: RunInvocation,
    ) -> None:
        aggregate = self._identity_read(
            self._identity_repository.get_research_run_aggregate,
            research_run_id=research_run.run_id,
        )
        if aggregate is None or not aggregate.invocations:
            raise DellAgentServerClientError(
                "fin_resume_durable_predecessor_missing"
            )
        if (
            aggregate.research_run.agent_session_id != research_run.session_id
            or aggregate.research_run.run_identity_digest
            != research_run_identity_digest(research_run)
        ):
            raise DellAgentServerClientError(
                "fin_resume_durable_predecessor_conflict"
            )
        first = aggregate.invocations[0]
        if (
            first.invocation_ordinal != 1
            or first.canonical_invocation_kind != "START"
            or first.server_invocation_kind != "start"
        ):
            raise DellAgentServerClientError(
                "fin_resume_durable_start_missing"
            )
        predecessor_index = run_invocation.ordinal - 2
        if predecessor_index < 0 or predecessor_index >= len(
            aggregate.invocations
        ):
            raise DellAgentServerClientError(
                "fin_resume_durable_predecessor_missing"
            )
        predecessor = aggregate.invocations[predecessor_index]
        if (
            predecessor.run_invocation_id != prior_run.run_invocation_id
            or predecessor.research_run_id != prior_run.research_run_id
            or predecessor.agent_session_id != prior_run.agent_session_id
            or predecessor.server_thread_id != prior_run.server_thread_id
            or predecessor.server_run_id != prior_run.server_run_id
            or predecessor.server_invocation_kind != prior_run.invocation_kind
            or predecessor.assistant_id != DELL_AGENT_SERVER_ASSISTANT_ID
        ):
            raise DellAgentServerClientError(
                "fin_resume_durable_predecessor_conflict"
            )
        matching_current = tuple(
            item
            for item in aggregate.invocations
            if item.run_invocation_id == run_invocation.invocation_id
        )
        if matching_current:
            if (
                len(matching_current) != 1
                or matching_current[0].invocation_ordinal
                != run_invocation.ordinal
            ):
                raise DellAgentServerClientError(
                    "fin_resume_durable_invocation_conflict"
                )
        elif run_invocation.ordinal != len(aggregate.invocations) + 1:
            raise DellAgentServerClientError(
                "fin_resume_durable_invocation_gap"
            )

    def _identity_read(self, operation: Any, **kwargs: Any) -> Any:
        try:
            return operation(**kwargs)
        except DellAgentServerIdentityStoreError as exc:
            raise DellAgentServerClientError(exc.code) from None
        except Exception:
            raise DellAgentServerClientError(
                "fin_identity_repository_read_failed"
            ) from None

    def _identity_write(self, operation: Any, **kwargs: Any) -> Any:
        try:
            return operation(**kwargs)
        except DellAgentServerIdentityStoreError as exc:
            raise DellAgentServerClientError(exc.code) from None
        except Exception:
            raise DellAgentServerClientError(
                "fin_identity_repository_write_failed"
            ) from None

    def join_updates(
        self,
        run: DellAgentServerRunBinding,
        *,
        last_event_id: str = "-1",
    ) -> Iterator[StreamPart]:
        """Join or replay the one qualified ``updates`` stream.

        ``-1`` requests the whole persisted stream.  A previously received
        event ID requests the strict suffix.  ``values`` or malformed event
        IDs fail closed; callers obtain complete graph state with ``get_state``.
        """

        self._ensure_open()
        if not isinstance(run, DellAgentServerRunBinding):
            raise DellAgentServerClientError("agent_server_run_binding_invalid")
        cursor = _required_identifier(
            last_event_id,
            code="agent_server_last_event_id_invalid",
            maximum=180,
        )
        cursor_key = (
            None
            if cursor == "-1"
            else _stream_order_key(
                cursor,
                code="agent_server_last_event_id_invalid",
            )
        )
        seen: set[str] = set()
        previous_key = cursor_key
        try:
            stream = self._sdk.runs.join_stream(
                run.server_thread_id,
                run.server_run_id,
                cancel_on_disconnect=False,
                stream_mode="updates",
                last_event_id=cursor,
            )
            for part in stream:
                if not isinstance(part, StreamPart):
                    raise DellAgentServerClientError(
                        "agent_server_stream_part_invalid"
                    )
                if part.event == "error":
                    raise DellAgentServerClientError("agent_server_stream_error")
                if part.event == "values":
                    raise DellAgentServerClientError(
                        "agent_server_values_stream_forbidden"
                    )
                if part.event not in _ALLOWED_STREAM_EVENTS:
                    raise DellAgentServerClientError(
                        "agent_server_stream_event_unexpected"
                    )
                if part.event != "end":
                    event_id = _required_identifier(
                        part.id,
                        code="agent_server_stream_event_id_missing",
                        maximum=180,
                    )
                    if event_id in seen:
                        raise DellAgentServerClientError(
                            "agent_server_stream_event_id_duplicate"
                        )
                    event_key = _stream_order_key(
                        event_id,
                        code="agent_server_stream_event_id_invalid",
                    )
                    if previous_key is not None and event_key <= previous_key:
                        raise DellAgentServerClientError(
                            "agent_server_stream_event_id_not_advanced"
                        )
                    seen.add(event_id)
                    previous_key = event_key
                yield part
        except DellAgentServerClientError:
            raise
        except Exception:
            raise DellAgentServerClientError("agent_server_stream_join_failed") from None

    def get_state(
        self,
        session: DellAgentServerSessionBinding,
    ) -> ThreadState:
        """Read complete server-owned state, not a public-safe FIN projection.

        Callers must apply the separate FIN redaction/authorization projection
        before exposing any portion of this response to a browser or export.
        """

        self._ensure_open()
        if not isinstance(session, DellAgentServerSessionBinding):
            raise DellAgentServerClientError("agent_server_session_binding_invalid")
        try:
            state = self._sdk.threads.get_state(
                session.server_thread_id,
                subgraphs=False,
            )
        except Exception:
            raise DellAgentServerClientError("agent_server_state_read_failed") from None
        if not isinstance(state, Mapping):
            raise DellAgentServerClientError("agent_server_state_response_invalid")
        return state


__all__ = [
    "DELL_AGENT_SERVER_ASSISTANT_ID",
    "DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION",
    "DellAgentServerClient",
    "DellAgentServerClientError",
    "DellAgentServerRunBinding",
    "DellAgentServerSessionBinding",
]
