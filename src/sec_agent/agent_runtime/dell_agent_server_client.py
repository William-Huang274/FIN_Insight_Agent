"""Thin LangGraph Agent Server SDK client for the Dell reference vertical.

Agent Server owns threads, runs, queues, checkpointing, resumable streams, and
state storage.  This module only returns the identity mappings that FIN's
``AgentSession`` / ``ResearchRun`` / ``RunInvocation`` store must durably
persist, and fixes the qualified client options.  It is not itself that durable
store.  It deliberately has no direct graph invocation, SQLite checkpointer,
HTTP server, retry loop, or alternate runtime path.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass
import re
from typing import Any, Literal
from urllib.parse import urlsplit
from uuid import UUID

from langgraph_sdk import get_sync_client
from langgraph_sdk.schema import StreamPart, ThreadState

from .dell_reference_vertical_graph import DellReferenceVerticalGraphInput


DELL_AGENT_SERVER_ASSISTANT_ID = "dell_reference_vertical"
DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION = "fin_ia_dell_agent_server_client_v1_0"

_STREAM_ID_PATTERN = re.compile(r"^(?P<milliseconds>[0-9]+)-(?P<sequence>[0-9]+)$")
_ALLOWED_STREAM_EVENTS = frozenset({"metadata", "updates", "end"})


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


def _stream_order_key(value: str, *, code: str) -> tuple[int, int]:
    match = _STREAM_ID_PATTERN.fullmatch(value)
    if match is None:
        raise DellAgentServerClientError(code)
    return int(match.group("milliseconds")), int(match.group("sequence"))


@dataclass(frozen=True, slots=True)
class DellAgentServerSessionBinding:
    """One FIN AgentSession bound to one server-assigned thread UUID."""

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

    __slots__ = ("_closed", "_owns_sdk_client", "_sdk")

    def __init__(
        self,
        sdk_client: Any,
        *,
        owns_sdk_client: bool = False,
    ) -> None:
        if sdk_client is None:
            raise DellAgentServerClientError("agent_server_sdk_client_required")
        if not isinstance(owns_sdk_client, bool):
            raise DellAgentServerClientError("agent_server_sdk_ownership_invalid")
        self._sdk = sdk_client
        self._owns_sdk_client = owns_sdk_client
        self._closed = False

    @classmethod
    def connect(
        cls,
        *,
        url: str,
        timeout: Any | None = None,
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
            owns_sdk_client=True,
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
        agent_session_id: str,
    ) -> DellAgentServerSessionBinding:
        """Create the Agent Server thread owned by one FIN AgentSession.

        Agent Server 0.13.3 requires thread IDs to be UUIDs.  The server assigns
        that UUID.  This method only returns the mapping; the canonical FIN
        AgentSession store must still persist it durably instead of reusing the
        FIN session ID as a server ID.
        """

        self._ensure_open()
        session_id = _required_identifier(
            agent_session_id,
            code="fin_agent_session_id_invalid",
            maximum=180,
        )
        metadata = {
            "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
            "agent_session_id": session_id,
        }
        try:
            created = self._sdk.threads.create(
                metadata=metadata,
                if_exists="raise",
                graph_id=DELL_AGENT_SERVER_ASSISTANT_ID,
            )
        except Exception:
            raise DellAgentServerClientError(
                "agent_server_session_create_failed"
            ) from None
        if not isinstance(created, Mapping):
            raise DellAgentServerClientError("agent_server_session_response_invalid")
        server_thread_id = _server_uuid(
            created.get("thread_id"),
            code="agent_server_session_response_invalid",
        )
        returned_metadata = created.get("metadata")
        if not isinstance(returned_metadata, Mapping) or returned_metadata.get(
            "agent_session_id"
        ) != session_id:
            raise DellAgentServerClientError(
                "agent_server_session_identity_mismatch"
            )
        return DellAgentServerSessionBinding(
            agent_session_id=session_id,
            server_thread_id=server_thread_id,
        )

    def start_run(
        self,
        *,
        session: DellAgentServerSessionBinding,
        research_run_id: str,
        run_invocation_id: str,
        graph_input: Mapping[str, Any],
    ) -> DellAgentServerRunBinding:
        """Create a background server run for a new FIN ResearchRun invocation."""

        self._ensure_open()
        if not isinstance(session, DellAgentServerSessionBinding):
            raise DellAgentServerClientError("agent_server_session_binding_invalid")
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
        if validated_input.run_id != research_run_id:
            raise DellAgentServerClientError("fin_research_run_input_mismatch")
        return self._create_run(
            session=session,
            research_run_id=research_run_id,
            run_invocation_id=run_invocation_id,
            invocation_kind="start",
            graph_input=validated_input.model_dump(mode="json"),
            resume_payload=None,
        )

    def resume_run(
        self,
        *,
        prior_run: DellAgentServerRunBinding,
        run_invocation_id: str,
        resume_payload: Mapping[str, Any],
    ) -> DellAgentServerRunBinding:
        """Resume an interrupted ResearchRun as a new server RunInvocation."""

        self._ensure_open()
        if not isinstance(prior_run, DellAgentServerRunBinding):
            raise DellAgentServerClientError("agent_server_prior_run_binding_invalid")
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
            maximum=180,
        )
        if invocation_id == prior_run.run_invocation_id:
            raise DellAgentServerClientError("fin_run_invocation_id_reused")
        if not isinstance(resume_payload, Mapping) or not resume_payload:
            raise DellAgentServerClientError("agent_server_resume_payload_invalid")
        session = DellAgentServerSessionBinding(
            agent_session_id=prior_run.agent_session_id,
            server_thread_id=prior_run.server_thread_id,
        )
        return self._create_run(
            session=session,
            research_run_id=prior_run.research_run_id,
            run_invocation_id=invocation_id,
            invocation_kind="resume",
            graph_input=None,
            resume_payload=dict(resume_payload),
        )

    def _create_run(
        self,
        *,
        session: DellAgentServerSessionBinding,
        research_run_id: str,
        run_invocation_id: str,
        invocation_kind: Literal["start", "resume"],
        graph_input: Mapping[str, Any] | None,
        resume_payload: Mapping[str, Any] | None,
    ) -> DellAgentServerRunBinding:
        research_id = _required_identifier(
            research_run_id,
            code="fin_research_run_id_invalid",
            maximum=180,
        )
        invocation_id = _required_identifier(
            run_invocation_id,
            code="fin_run_invocation_id_invalid",
            maximum=180,
        )
        context = {
            "agent_session_id": session.agent_session_id,
            "research_run_id": research_id,
            "run_invocation_id": invocation_id,
        }
        metadata = {
            "fin_client_schema_version": DELL_AGENT_SERVER_CLIENT_SCHEMA_VERSION,
            **context,
            "invocation_kind": invocation_kind,
        }
        kwargs: dict[str, Any] = {
            "stream_mode": ["updates"],
            "stream_resumable": True,
            "durability": "sync",
            "multitask_strategy": "reject",
            "if_not_exists": "reject",
            "context": context,
            "metadata": metadata,
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
            raise DellAgentServerClientError(error_code) from None
        if not isinstance(created, Mapping):
            raise DellAgentServerClientError("agent_server_run_response_invalid")
        server_thread_id = _server_uuid(
            created.get("thread_id"),
            code="agent_server_run_response_invalid",
        )
        if server_thread_id != session.server_thread_id:
            raise DellAgentServerClientError("agent_server_run_thread_mismatch")
        return DellAgentServerRunBinding(
            agent_session_id=session.agent_session_id,
            research_run_id=research_id,
            run_invocation_id=invocation_id,
            server_thread_id=server_thread_id,
            server_run_id=_server_uuid(
                created.get("run_id"),
                code="agent_server_run_response_invalid",
            ),
            invocation_kind=invocation_kind,
            server_status=_required_identifier(
                created.get("status"),
                code="agent_server_run_response_invalid",
                maximum=80,
            ),
        )

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
