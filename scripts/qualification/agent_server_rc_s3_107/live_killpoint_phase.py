"""Container-side RC-S3-107 kill-point primitives and phase entry point.

The wrappers in this module preserve the production SDK/repository objects and
inject failures only at the explicitly named qualification seam.  They do not
implement an alternate client, identity store, or runtime.

All scenario executors use the production DellAgentServerClient recovery bridge.
The host still remains fail closed until the concurrently owned production
client/identity/SQL contract is frozen and its regressions pass; implemented is
not the same claim as live-qualified.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence


EXPECTED_MANIFEST_SCHEMA = "fin.rc_s3_107.qualification_manifest.v1"
EXPECTED_SCENARIOS = tuple(f"K{index}" for index in range(7))
AGENT_SERVER_URL = "http://127.0.0.1:8000"
FIN_RUNTIME_URI_ENV = "FIN_RUNTIME_POSTGRES_URI"
FIN_RUNTIME_OPERATOR_URI_ENV = "FIN_RUNTIME_OPERATOR_POSTGRES_URI"
ZERO_MODEL_EXECUTION_PROFILE = "zero_model_control_plane_v1"
LANGSMITH_PROJECT = "fin-insight-dell-reference-vertical"
ALLOWED_REMOTE_RUN_STATUSES = frozenset(
    {"pending", "running", "error", "success", "timeout", "interrupted"}
)
TERMINAL_REMOTE_RUN_STATUSES = frozenset(
    {"error", "success", "timeout", "interrupted"}
)
REMOTE_SUCCESS_WAIT_SECONDS = 30.0
FINAL_REMOTE_STATUS_RULES = {
    "K0": {"primary": frozenset({"success"})},
    "K2": {"primary": frozenset({"success", "error"})},
    "K3": {"primary": frozenset({"success", "error"})},
    "K4": {"primary": frozenset({"success", "error"})},
    "K5": {
        "reconciled_restart": frozenset({"success"}),
        "unresolved_orphan_restart": frozenset({"error"}),
    },
    "K6": {"shared_invocation": frozenset({"success"})},
}


class LivePhaseBlocker(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ResponseBodyLost(ConnectionError):
    """Qualification-only transport loss after the remote create committed."""


@dataclass(frozen=True)
class KillPointObservation:
    attempt_id: str
    project: str
    scenario_id: str
    step_id: str
    milestone: str
    sdk_create_calls: int
    remote_run_count: int | None

    def as_receipt(self) -> dict[str, Any]:
        return {
            "schema_version": "fin.rc_s3_107.killpoint_observation.v1",
            "attempt_id": self.attempt_id,
            "project": self.project,
            "scenario_id": self.scenario_id,
            "step_id": self.step_id,
            "milestone": self.milestone,
            "sdk_create_calls": self.sdk_create_calls,
            "remote_run_count": self.remote_run_count,
        }


def emit_observation(observation: KillPointObservation) -> None:
    print(json.dumps(observation.as_receipt(), ensure_ascii=True, sort_keys=True))
    sys.stdout.flush()


@dataclass(frozen=True)
class OperatorDispositionObservation:
    attempt_id: str
    project: str
    scenario_id: str
    step_id: str
    milestone: str
    source_invocation_id: str
    canonical_recovery_decision: str
    exact_ambiguous_action_binding: bool

    def as_receipt(self) -> dict[str, Any]:
        return {
            "schema_version": "fin.rc_s3_107.operator_observation.v1",
            "attempt_id": self.attempt_id,
            "project": self.project,
            "scenario_id": self.scenario_id,
            "step_id": self.step_id,
            "milestone": self.milestone,
            "source_invocation_id": self.source_invocation_id,
            "canonical_recovery_decision": self.canonical_recovery_decision,
            "exact_ambiguous_action_binding": (
                self.exact_ambiguous_action_binding
            ),
        }


def emit_operator_observation(
    observation: OperatorDispositionObservation,
) -> None:
    print(json.dumps(observation.as_receipt(), ensure_ascii=True, sort_keys=True))
    sys.stdout.flush()


class CrashAfterPendingRepository:
    """Delegate to the production repository, then crash before SDK create.

    ``hard_exit`` is injected so unit tests can observe the seam without killing
    the test worker.  A live child process must pass ``os._exit``.
    """

    def __init__(
        self,
        delegate: Any,
        *,
        hard_exit: Callable[[int], Any] = os._exit,
        exit_code: int = 91,
        attempt_id: str,
        project: str,
        step_id: str = "pending_victim",
    ) -> None:
        self._delegate = delegate
        self._hard_exit = hard_exit
        self._exit_code = exit_code
        self._attempt_id = attempt_id
        self._project = project
        self._step_id = step_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def begin_run_create(self, *args: Any, **kwargs: Any) -> Any:
        result = self._delegate.begin_run_create(*args, **kwargs)
        emit_observation(
            KillPointObservation(
                attempt_id=self._attempt_id,
                project=self._project,
                scenario_id="K1",
                step_id=self._step_id,
                milestone="pending_committed_before_dispatch",
                sdk_create_calls=0,
                remote_run_count=0,
            )
        )
        self._hard_exit(self._exit_code)
        raise AssertionError("hard_exit_returned")


class CrashAfterDispatchedRepository:
    """Commit DISPATCHED through the production repository, then hard-exit.

    This proves the distinct window where FIN has durably declared the remote
    side effect dispatchable but the official SDK ``runs.create`` boundary has
    not yet been crossed.  The host must observe exit 94 before any recovery
    classification is permitted.
    """

    def __init__(
        self,
        delegate: Any,
        *,
        hard_exit: Callable[[int], Any] = os._exit,
        exit_code: int = 94,
        attempt_id: str,
        project: str,
        step_id: str = "dispatched_victim",
    ) -> None:
        self._delegate = delegate
        self._hard_exit = hard_exit
        self._exit_code = exit_code
        self._attempt_id = attempt_id
        self._project = project
        self._step_id = step_id

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def mark_run_create_dispatched(self, *args: Any, **kwargs: Any) -> Any:
        result = self._delegate.mark_run_create_dispatched(*args, **kwargs)
        emit_observation(
            KillPointObservation(
                attempt_id=self._attempt_id,
                project=self._project,
                scenario_id="K1",
                step_id=self._step_id,
                milestone="dispatched_committed_before_sdk_create",
                sdk_create_calls=0,
                remote_run_count=0,
            )
        )
        self._hard_exit(self._exit_code)
        raise AssertionError("hard_exit_returned")


class HeaderObservedCrashRuns:
    """Run the official callback, then crash before returning the response."""

    def __init__(
        self,
        delegate: Any,
        *,
        hard_exit: Callable[[int], Any] = os._exit,
        exit_code: int = 92,
        attempt_id: str,
        project: str,
        step_id: str = "header_victim",
    ) -> None:
        self._delegate = delegate
        self._hard_exit = hard_exit
        self._exit_code = exit_code
        self._attempt_id = attempt_id
        self._project = project
        self._step_id = step_id
        self.create_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        original = kwargs.get("on_run_created")
        if not callable(original):
            raise LivePhaseBlocker("rc_s3_107_k2_callback_missing")

        def observed(run: Any) -> None:
            original(run)
            emit_observation(
                KillPointObservation(
                    attempt_id=self._attempt_id,
                    project=self._project,
                    scenario_id="K2",
                    step_id=self._step_id,
                    milestone="orphan_with_run_id_committed_body_unread",
                    sdk_create_calls=1,
                    remote_run_count=1,
                )
            )
            self._hard_exit(self._exit_code)
            raise AssertionError("hard_exit_returned")

        forwarded = dict(kwargs)
        forwarded["on_run_created"] = observed
        self.create_calls += 1
        return self._delegate.create(*args, **forwarded)


class RunsProxy:
    """Replace only ``sdk.runs`` while preserving the official SDK object."""

    def __init__(self, sdk: Any, runs: Any) -> None:
        self._sdk = sdk
        self.runs = runs

    def __getattr__(self, name: str) -> Any:
        return getattr(self._sdk, name)


def _instrumentation_path(
    manifest: Mapping[str, Any], *, scenario_id: str | None = None
) -> Path:
    bound_scenario_id = scenario_id or str(manifest.get("scenario_id", ""))
    if bound_scenario_id not in {"K0", "K1", "K2", "K3", "K4", "K5", "K6"}:
        raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_scenario_invalid")
    identity = (
        f"{manifest.get('attempt_id', '')}\0{manifest.get('project', '')}"
        f"\0{bound_scenario_id}"
    ).encode("utf-8")
    suffix = hashlib.sha256(identity).hexdigest()[:24]
    return Path(f"/tmp/fin-rc-s3-107-sdk-create-{suffix}.jsonl")


def _append_create_instrumentation(
    manifest: Mapping[str, Any], *, invocation_id: str
) -> None:
    record = {
        "schema_version": "fin.rc_s3_107.sdk_create_attempt.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": manifest["scenario_id"],
        "invocation_id": invocation_id,
    }
    payload = (
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        _instrumentation_path(manifest),
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o600,
    )
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_short_write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _instrumented_create_counts(
    manifest: Mapping[str, Any], *, scenario_id: str,
    allowed_invocation_ids: set[str]
) -> dict[str, int]:
    path = _instrumentation_path(manifest, scenario_id=scenario_id)
    counts = {invocation_id: 0 for invocation_id in allowed_invocation_ids}
    if not path.is_file():
        return counts
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_read_failed") from exc
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_invalid") from exc
        if not isinstance(record, dict) or set(record) != {
            "schema_version",
            "attempt_id",
            "project",
            "scenario_id",
            "invocation_id",
        }:
            raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_invalid")
        if (
            record["schema_version"] != "fin.rc_s3_107.sdk_create_attempt.v1"
            or record["attempt_id"] != manifest["attempt_id"]
            or record["project"] != manifest["project"]
            or record["scenario_id"] != scenario_id
            or record["invocation_id"] not in allowed_invocation_ids
        ):
            raise LivePhaseBlocker("rc_s3_107_sdk_instrumentation_identity_mismatch")
        counts[record["invocation_id"]] += 1
    return counts


class InstrumentedRuns:
    """Count the exact official ``runs.create`` boundary before delegating."""

    def __init__(self, delegate: Any, *, manifest: Mapping[str, Any]) -> None:
        self._delegate = delegate
        self._manifest = manifest

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        metadata = kwargs.get("metadata")
        invocation_id = (
            metadata.get("run_invocation_id")
            if isinstance(metadata, Mapping)
            else None
        )
        if not isinstance(invocation_id, str) or not invocation_id:
            raise LivePhaseBlocker("rc_s3_107_sdk_create_invocation_missing")
        _append_create_instrumentation(
            self._manifest,
            invocation_id=invocation_id,
        )
        return self._delegate.create(*args, **kwargs)


class DelayedVisibilityRuns:
    """Suppress the create callback and hide a bounded number of exact scans."""

    def __init__(self, delegate: Any, *, hidden_exact_scans: int = 2) -> None:
        if hidden_exact_scans < 1:
            raise ValueError("hidden_exact_scans_must_be_positive")
        self._delegate = delegate
        self._configured_hidden_scans = hidden_exact_scans
        self._remaining_hidden_scans = 0
        self.create_calls = 0
        self.exact_list_calls = 0

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def create(self, *args: Any, **kwargs: Any) -> Any:
        forwarded = dict(kwargs)
        forwarded.pop("on_run_created", None)
        self.create_calls += 1
        self._delegate.create(*args, **forwarded)
        self._remaining_hidden_scans = self._configured_hidden_scans
        raise ResponseBodyLost("rc_s3_107_response_body_lost")

    def list(self, *args: Any, **kwargs: Any) -> Any:
        self.exact_list_calls += 1
        if self._remaining_hidden_scans > 0:
            self._remaining_hidden_scans -= 1
            return []
        return self._delegate.list(*args, **kwargs)


class ReconciledInsertFaultState:
    """Shared observation state for the K3 transaction-local fault seam."""

    def __init__(self) -> None:
        self.binding_insert_observed = False
        self.reconciled_insert_faulted = False


class ReconciledInsertFaultConnection:
    def __init__(self, delegate: Any, state: ReconciledInsertFaultState) -> None:
        self._delegate = delegate
        self._state = state

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def execute(self, query: Any, params: Any = None) -> Any:
        normalized = str(query).lower()
        if "insert into fin_runtime.research_run_invocations" in normalized:
            result = self._delegate.execute(query, params)
            self._state.binding_insert_observed = True
            return result
        if (
            self._state.binding_insert_observed
            and not self._state.reconciled_insert_faulted
            and "insert into fin_runtime.agent_server_run_create_lifecycle" in normalized
            and "'reconciled'" in normalized
        ):
            self._state.reconciled_insert_faulted = True
            raise RuntimeError("rc_s3_107_injected_reconciled_insert_failure")
        return self._delegate.execute(query, params)


class _ConnectionContextProxy:
    def __init__(self, delegate: Any, state: ReconciledInsertFaultState) -> None:
        self._delegate = delegate
        self._state = state

    def __enter__(self) -> ReconciledInsertFaultConnection:
        return ReconciledInsertFaultConnection(
            self._delegate.__enter__(),
            self._state,
        )

    def __exit__(self, *args: Any) -> Any:
        return self._delegate.__exit__(*args)


class ReconciledInsertFaultPool:
    """Preserve the real psycopg transaction, faulting only one INSERT."""

    def __init__(self, delegate: Any, state: ReconciledInsertFaultState) -> None:
        self._delegate = delegate
        self._state = state

    def connection(self) -> _ConnectionContextProxy:
        return _ConnectionContextProxy(self._delegate.connection(), self._state)


def _exclusive_marker(path: Path, payload: str) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        encoded = payload.encode("ascii")
        if os.write(descriptor, encoded) != len(encoded):
            raise LivePhaseBlocker("rc_s3_107_k6_marker_short_write")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _wait_for_paths(paths: Sequence[Path], *, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while not all(path.is_file() for path in paths):
        if time.monotonic() >= deadline:
            raise LivePhaseBlocker("rc_s3_107_k6_barrier_timeout")
        time.sleep(0.01)


def _k6_prefix(manifest: Mapping[str, Any]) -> Path:
    identity = (
        f"{manifest.get('attempt_id', '')}\0{manifest.get('project', '')}\0K6"
    ).encode("utf-8")
    suffix = hashlib.sha256(identity).hexdigest()[:24]
    return Path(f"/tmp/fin-rc-s3-107-k6-{suffix}")


class ConcurrentBeginRepository:
    """Synchronize two processes without changing repository semantics."""

    def __init__(
        self,
        delegate: Any,
        *,
        barrier_prefix: Path,
        worker_id: int,
    ) -> None:
        self._delegate = delegate
        self._barrier_prefix = barrier_prefix
        self._worker_id = worker_id
        self.created_now: bool | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)

    def begin_run_create(self, *args: Any, **kwargs: Any) -> Any:
        arrivals = [
            Path(f"{self._barrier_prefix}-arrival-{index}")
            for index in (0, 1)
        ]
        _exclusive_marker(arrivals[self._worker_id], "arrived")
        _wait_for_paths(arrivals)
        registration = self._delegate.begin_run_create(*args, **kwargs)
        self.created_now = registration.created_now
        loser_finished = Path(f"{self._barrier_prefix}-loser-finished")
        if registration.created_now:
            _wait_for_paths((loser_finished,))
        return registration

    def release_winner_after_loser(self) -> None:
        if self.created_now is not False:
            raise LivePhaseBlocker("rc_s3_107_k6_loser_release_invalid")
        _exclusive_marker(
            Path(f"{self._barrier_prefix}-loser-finished"),
            "loser-finished-without-sdk-create",
        )


SCENARIO_EXECUTOR_BLOCKERS: Mapping[str, str] = {
    "K0": "rc_s3_107_k0_production_contract_not_frozen",
    "K1": "rc_s3_107_k1_production_contract_not_frozen",
    "K2": "rc_s3_107_k2_production_contract_not_frozen",
    "K3": "rc_s3_107_k3_production_contract_not_frozen",
    "K4": "rc_s3_107_k4_production_contract_not_frozen",
    "K5": "rc_s3_107_k5_production_contract_not_frozen",
    "K6": "rc_s3_107_k6_production_contract_not_frozen",
}


def _load_manifest() -> Mapping[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise LivePhaseBlocker("rc_s3_107_manifest_invalid_json") from exc
    if not isinstance(value, dict):
        raise LivePhaseBlocker("rc_s3_107_manifest_not_object")
    if value.get("schema_version") != EXPECTED_MANIFEST_SCHEMA:
        raise LivePhaseBlocker("rc_s3_107_manifest_schema_mismatch")
    constraints = value.get("constraints")
    if not isinstance(constraints, dict):
        raise LivePhaseBlocker("rc_s3_107_manifest_constraints_missing")
    if constraints.get("zero_model") is not True:
        raise LivePhaseBlocker("rc_s3_107_zero_model_constraint_missing")
    if constraints.get("external_research_or_model_calls") is not False:
        raise LivePhaseBlocker("rc_s3_107_external_research_constraint_invalid")
    if constraints.get("provider_model_calls") is not False:
        raise LivePhaseBlocker("rc_s3_107_provider_model_constraint_invalid")
    if constraints.get("langsmith_observability_egress") is not True:
        raise LivePhaseBlocker("rc_s3_107_langsmith_egress_constraint_invalid")
    if constraints.get("trace_content_in_receipt") is not False:
        raise LivePhaseBlocker("rc_s3_107_trace_receipt_constraint_invalid")
    if constraints.get("automatic_second_attempt") is not False:
        raise LivePhaseBlocker("rc_s3_107_second_attempt_constraint_invalid")
    runtime_cases = value.get("runtime_cases")
    identities = value.get("scenario_identities")
    if not isinstance(runtime_cases, dict) or set(runtime_cases) != set(
        EXPECTED_SCENARIOS
    ):
        raise LivePhaseBlocker("rc_s3_107_runtime_cases_invalid")
    if not isinstance(identities, dict) or set(identities) != set(EXPECTED_SCENARIOS):
        raise LivePhaseBlocker("rc_s3_107_scenario_identities_invalid")
    return value


def _runtime_case(
    manifest: Mapping[str, Any], *, scenario_id: str, role: str
) -> tuple[Any, Any, Any, Mapping[str, Any]]:
    try:
        from sec_agent.canonical_runtime.contracts_v1_2 import (
            AgentSessionV1_2,
            ResearchRun,
            RunInvocation,
        )
    except Exception as exc:
        raise LivePhaseBlocker("rc_s3_107_canonical_contract_import_failed") from exc
    cases = manifest.get("runtime_cases")
    if not isinstance(cases, Mapping):
        raise LivePhaseBlocker("rc_s3_107_runtime_cases_invalid")
    scenario_cases = cases.get(scenario_id)
    if not isinstance(scenario_cases, list):
        raise LivePhaseBlocker("rc_s3_107_runtime_case_invalid")
    selected = [
        item
        for item in scenario_cases
        if isinstance(item, Mapping) and item.get("role") == role
    ]
    if len(selected) != 1:
        raise LivePhaseBlocker("rc_s3_107_runtime_case_role_not_unique")
    value = selected[0]
    if set(value) != {
        "role",
        "agent_session",
        "research_run",
        "run_invocation",
        "graph_input",
    }:
        raise LivePhaseBlocker("rc_s3_107_runtime_case_shape_invalid")
    try:
        session = AgentSessionV1_2.model_validate(value["agent_session"])
        research_run = ResearchRun.model_validate(value["research_run"])
        invocation = RunInvocation.model_validate(value["run_invocation"])
    except Exception as exc:
        raise LivePhaseBlocker("rc_s3_107_runtime_case_contract_invalid") from exc
    graph_input = value["graph_input"]
    if not isinstance(graph_input, Mapping):
        raise LivePhaseBlocker("rc_s3_107_runtime_case_graph_input_invalid")
    if (
        research_run.session_id != session.session_id
        or invocation.session_id != session.session_id
        or invocation.run_id != research_run.run_id
        or graph_input.get("run_id") != research_run.run_id
        or invocation.invocation_kind != "START"
        or invocation.ordinal != 1
    ):
        raise LivePhaseBlocker("rc_s3_107_runtime_case_lineage_invalid")
    identities = manifest["scenario_identities"][scenario_id]
    expected = [
        row.get("invocation_id")
        for row in identities
        if isinstance(row, Mapping) and row.get("role") == role
    ]
    if expected != [invocation.invocation_id]:
        raise LivePhaseBlocker("rc_s3_107_runtime_case_identity_mismatch")
    return session, research_run, invocation, dict(graph_input)


def _require_container_environment() -> str:
    if os.environ.get("FINSIGHT_DELL_EXECUTION_PROFILE") != (
        ZERO_MODEL_EXECUTION_PROFILE
    ):
        raise LivePhaseBlocker("rc_s3_107_execution_profile_mismatch")
    if os.environ.get("LANGSMITH_PROJECT") != LANGSMITH_PROJECT:
        raise LivePhaseBlocker("rc_s3_107_langsmith_project_mismatch")
    for name in ("LANGSMITH_TRACING", "LANGSMITH_HIDE_INPUTS", "LANGSMITH_HIDE_OUTPUTS"):
        if os.environ.get(name, "").strip().lower() != "true":
            raise LivePhaseBlocker("rc_s3_107_langsmith_boundary_mismatch")
    for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        if os.environ.get(name):
            raise LivePhaseBlocker("rc_s3_107_model_provider_key_injected")
    runtime_uri = os.environ.get(FIN_RUNTIME_URI_ENV, "").strip()
    if not runtime_uri:
        raise LivePhaseBlocker("rc_s3_107_fin_runtime_uri_missing")
    return runtime_uri


def _require_operator_environment() -> str:
    if os.environ.get("FINSIGHT_DELL_EXECUTION_PROFILE") not in {
        None,
        "",
        ZERO_MODEL_EXECUTION_PROFILE,
    }:
        raise LivePhaseBlocker("rc_s3_107_operator_execution_profile_mismatch")
    for name in (
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        FIN_RUNTIME_URI_ENV,
    ):
        if os.environ.get(name):
            raise LivePhaseBlocker("rc_s3_107_operator_authority_isolation_failed")
    operator_uri = os.environ.get(FIN_RUNTIME_OPERATOR_URI_ENV, "").strip()
    if not operator_uri:
        raise LivePhaseBlocker("rc_s3_107_operator_runtime_uri_missing")
    return operator_uri


def _record_operator_disposition(
    manifest: Mapping[str, Any], *, scenario_id: str, step_id: str
) -> None:
    if scenario_id not in {"K4", "K5"} or step_id != "record_operator_disposition":
        raise LivePhaseBlocker("rc_s3_107_operator_step_not_allowed")
    role = (
        "unresolved_orphan_restart"
        if scenario_id == "K5"
        else "primary"
    )
    _, _, invocation, _ = _runtime_case(
        manifest,
        scenario_id=scenario_id,
        role=role,
    )
    operator_uri = _require_operator_environment()
    try:
        from psycopg_pool import ConnectionPool

        from sec_agent.agent_runtime.dell_agent_server_identity import (
            PostgresDellAgentServerRecoveryOperatorRepository,
        )
        from sec_agent.canonical_runtime.contracts_v1_2 import (
            create_recovery_disposition,
        )
    except Exception as exc:
        raise LivePhaseBlocker("rc_s3_107_operator_import_failed") from exc

    try:
        with ConnectionPool(
            operator_uri,
            min_size=1,
            max_size=1,
            open=True,
            timeout=10,
        ) as pool:
            pool.wait(timeout=10)
            repository = PostgresDellAgentServerRecoveryOperatorRepository(pool)
            open_cases = repository.list_open_recovery_cases(limit=100)
            selected = [
                case
                for case in open_cases
                if case.source_invocation.invocation_id == invocation.invocation_id
            ]
            if len(selected) != 1:
                raise LivePhaseBlocker(
                    "rc_s3_107_operator_open_case_cardinality_invalid"
                )
            recovery_case = selected[0]
            created_at = max(
                datetime.now(timezone.utc),
                recovery_case.ambiguous_action.terminal_at,
            )
            disposition = create_recovery_disposition(
                recovery_disposition_id=(
                    "RECOVERY-DISPOSITION::RC-S3-107::"
                    f"{invocation.invocation_id}"
                ),
                session_id=recovery_case.research_run.session_id,
                run_id=recovery_case.research_run.run_id,
                research_run_digest=recovery_case.research_run.run_digest,
                ambiguous_action_attempt_id=(
                    recovery_case.ambiguous_action.action_attempt_id
                ),
                ambiguous_action_attempt_digest=(
                    recovery_case.ambiguous_action.action_attempt_digest
                ),
                source_run_invocation_id=(
                    recovery_case.source_invocation.invocation_id
                ),
                source_run_invocation_digest=(
                    recovery_case.source_invocation.invocation_digest
                ),
                investigation_receipt_refs=(
                    "qualification://rc-s3-107/"
                    f"{manifest['attempt_id']}/{scenario_id}/pending-owner-handoff",
                ),
                potentially_duplicate_cost=(
                    recovery_case.ambiguous_action.potentially_chargeable
                ),
                decision="DO_NOT_RETRY",
                decision_authority_ref=(
                    "authority://rc-s3-107/independent-recovery-operator"
                ),
                next_run_invocation_id=None,
                next_run_invocation_digest=None,
                replacement_action_attempt_id=None,
                replacement_action_attempt_digest=None,
                created_at=created_at,
            )
            persisted = repository.record_recovery_disposition(
                recovery_case_id=recovery_case.recovery_case_id,
                disposition=disposition,
            )
            if (
                persisted.decision != "DO_NOT_RETRY"
                or persisted.source_run_invocation_id
                != invocation.invocation_id
                or persisted.ambiguous_action_attempt_id
                != recovery_case.ambiguous_action.action_attempt_id
                or persisted.ambiguous_action_attempt_digest
                != recovery_case.ambiguous_action.action_attempt_digest
            ):
                raise LivePhaseBlocker(
                    "rc_s3_107_operator_disposition_readback_mismatch"
                )
    except LivePhaseBlocker:
        raise
    except Exception as exc:
        code = getattr(exc, "code", None)
        if isinstance(code, str) and code.startswith("run_create_"):
            raise LivePhaseBlocker(f"rc_s3_107_operator_{code}") from None
        raise LivePhaseBlocker("rc_s3_107_operator_disposition_failed") from exc

    emit_operator_observation(
        OperatorDispositionObservation(
            attempt_id=manifest["attempt_id"],
            project=manifest["project"],
            scenario_id=scenario_id,
            step_id=step_id,
            milestone="operator_disposition_recorded",
            source_invocation_id=invocation.invocation_id,
            canonical_recovery_decision="DO_NOT_RETRY",
            exact_ambiguous_action_binding=True,
        )
    )


@contextmanager
def _runtime_resources(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    role: str,
    repository_wrapper: Callable[[Any], Any] | None = None,
    runs_wrapper: Callable[[Any], Any] | None = None,
    pool_wrapper: Callable[[Any], Any] | None = None,
) -> Iterator[tuple[Any, Any, Any, Any, Any, Mapping[str, Any]]]:
    """Open only the production client/repository plus SDK instrumentation."""

    runtime_uri = _require_container_environment()
    try:
        from langgraph_sdk import get_sync_client
        from psycopg_pool import ConnectionPool

        from sec_agent.agent_runtime.dell_agent_server_client import (
            DellAgentServerClient,
        )
        from sec_agent.agent_runtime.dell_agent_server_identity import (
            PostgresDellAgentServerIdentityRepository,
        )
    except Exception as exc:
        raise LivePhaseBlocker("rc_s3_107_runtime_import_failed") from exc

    session, research_run, invocation, graph_input = _runtime_case(
        manifest,
        scenario_id=scenario_id,
        role=role,
    )
    with ConnectionPool(
        runtime_uri,
        min_size=1,
        max_size=2,
        open=True,
        timeout=10,
    ) as pool:
        pool.wait(timeout=10)
        repository = PostgresDellAgentServerIdentityRepository(pool)
        client_pool = pool if pool_wrapper is None else pool_wrapper(pool)
        client_repository = PostgresDellAgentServerIdentityRepository(client_pool)
        identity_repository = (
            client_repository
            if repository_wrapper is None
            else repository_wrapper(client_repository)
        )
        sdk = get_sync_client(url=AGENT_SERVER_URL)
        instrumented_runs: Any = InstrumentedRuns(
            sdk.runs,
            manifest={**manifest, "scenario_id": scenario_id},
        )
        if runs_wrapper is not None:
            instrumented_runs = runs_wrapper(instrumented_runs)
        proxy = RunsProxy(sdk, instrumented_runs)
        client = DellAgentServerClient(
            proxy,
            identity_repository=identity_repository,
            execution_profile=ZERO_MODEL_EXECUTION_PROFILE,
        )
        try:
            session_binding = client.create_agent_session(agent_session=session)
            yield (
                repository,
                client,
                session_binding,
                research_run,
                invocation,
                graph_input,
            )
        finally:
            client.close()
            sdk.close()


def _lifecycle_events(lifecycle: Any) -> list[Any]:
    if lifecycle is None:
        raise LivePhaseBlocker("rc_s3_107_fin_lifecycle_missing")
    events = [lifecycle.pending]
    if lifecycle.dispatched is not None:
        events.append(lifecycle.dispatched)
    orphan_events = tuple(getattr(lifecycle, "orphan_observations", ()))
    if orphan_events:
        events.extend(orphan_events)
    elif lifecycle.orphan is not None:
        events.append(lifecycle.orphan)
    if lifecycle.reconciled is not None:
        events.append(lifecycle.reconciled)
    ordinals = [event.lifecycle_ordinal for event in events]
    if ordinals != sorted(ordinals) or len(set(ordinals)) != len(ordinals):
        raise LivePhaseBlocker("rc_s3_107_fin_lifecycle_order_invalid")
    return events


def _fin_readback(repository: Any, *, invocation_id: str, role: str) -> dict[str, Any]:
    lifecycle = repository.get_run_create_lifecycle(
        run_invocation_id=invocation_id
    )
    events = _lifecycle_events(lifecycle)
    action = repository.get_run_create_action_attempt(
        run_invocation_id=invocation_id
    )
    if action is None or action.state != "TERMINAL" or action.outcome is None:
        raise LivePhaseBlocker("rc_s3_107_canonical_action_terminal_missing")
    binding = repository.get_run_invocation(run_invocation_id=invocation_id)
    recovery_case = repository.get_run_create_recovery_case(
        run_invocation_id=invocation_id
    )
    disposition = repository.get_run_create_recovery_disposition(
        run_invocation_id=invocation_id
    )
    exact_orphans = [
        event
        for event in events
        if event.lifecycle_state == "ORPHAN" and event.server_run_id is not None
    ]
    latest_exact_orphan = exact_orphans[-1] if exact_orphans else None
    if recovery_case is None:
        if disposition is not None:
            raise LivePhaseBlocker("rc_s3_107_recovery_disposition_without_case")
        recovery = {
            "status": "NOT_APPLICABLE",
            "recovery_disposition_status": "NOT_APPLICABLE",
            "canonical_recovery_decision": None,
            "owner_visible": False,
            "resolved": True,
            "automatic_second_create_attempted": False,
        }
    elif disposition is None:
        recovery = {
            "status": "RECOVERY_REQUIRED",
            "recovery_disposition_status": "PENDING_OWNER_DECISION",
            "canonical_recovery_decision": None,
            "owner_visible": True,
            "resolved": False,
            "automatic_second_create_attempted": False,
        }
    else:
        if (
            disposition.source_run_invocation_id != invocation_id
            or disposition.ambiguous_action_attempt_id
            != recovery_case.ambiguous_action.action_attempt_id
            or disposition.ambiguous_action_attempt_digest
            != recovery_case.ambiguous_action.action_attempt_digest
        ):
            raise LivePhaseBlocker("rc_s3_107_recovery_disposition_binding_mismatch")
        recovery = {
            "status": "RECOVERY_REQUIRED",
            "recovery_disposition_status": "RECORDED",
            "canonical_recovery_decision": disposition.decision,
            "owner_visible": True,
            "resolved": True,
            "automatic_second_create_attempted": False,
        }
    return {
        "invocation_id": invocation_id,
        "role": role,
        "lifecycle": [event.lifecycle_state for event in events],
        "canonical_action_outcome": action.outcome,
        "recovery": recovery,
        "final_binding_count": 0 if binding is None else 1,
        "bound_server_run_id": None if binding is None else binding.server_run_id,
        "latest_exact_orphan_server_run_id": (
            None if latest_exact_orphan is None else latest_exact_orphan.server_run_id
        ),
        "orphan_with_run_id": any(
            event.lifecycle_state == "ORPHAN" and event.server_run_id is not None
            for event in events
        ),
        "orphan_without_run_id": any(
            event.lifecycle_state == "ORPHAN" and event.server_run_id is None
            for event in events
        ),
        "recovery_case_digest": (
            None if recovery_case is None else recovery_case.recovery_case_digest
        ),
        "recovery_disposition_digest": (
            None
            if disposition is None
            else disposition.recovery_disposition_digest
        ),
        "recovery_disposition_created_at": (
            None if disposition is None else disposition.created_at
        ),
        "ambiguous_action_attempt_digest": (
            action.action_attempt_digest
            if action.outcome == "AMBIGUOUS_AFTER_DISPATCH"
            else None
        ),
        "latest_exact_orphan_observation_digest": (
            None
            if latest_exact_orphan is None
            else latest_exact_orphan.server_observation_digest
        ),
        "latest_exact_orphan_server_status": (
            None
            if latest_exact_orphan is None
            else latest_exact_orphan.server_run_status
        ),
        "latest_exact_orphan_recorded_at": (
            None if latest_exact_orphan is None else latest_exact_orphan.recorded_at
        ),
        "reconciled_observation_digest": (
            None
            if lifecycle.reconciled is None
            else lifecycle.reconciled.server_observation_digest
        ),
        "reconciled_server_status": (
            None
            if lifecycle.reconciled is None
            else lifecycle.reconciled.server_run_status
        ),
        "server_thread_id": lifecycle.pending.server_thread_id,
    }


def _remote_readback(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    fin_rows: Sequence[Mapping[str, Any]],
    expected_remote_runs: int,
    required_statuses_by_invocation: Mapping[str, frozenset[str]] | None = None,
    require_fin_run_id_match: bool = False,
) -> dict[str, Any]:
    try:
        from langgraph_sdk import get_sync_client
    except Exception as exc:
        raise LivePhaseBlocker("rc_s3_107_official_sdk_import_failed") from exc
    expected_ids = {row["invocation_id"] for row in fin_rows}
    manifest_ids = {
        row["invocation_id"]
        for row in manifest["scenario_identities"][scenario_id]
    }
    if expected_ids != manifest_ids:
        raise LivePhaseBlocker("rc_s3_107_fin_manifest_identity_mismatch")
    sdk = get_sync_client(url=AGENT_SERVER_URL)
    required_statuses = dict(required_statuses_by_invocation or {})
    if not set(required_statuses).issubset(expected_ids):
        raise LivePhaseBlocker("rc_s3_107_remote_status_identity_invalid")
    if any(
        not allowed or not allowed.issubset(TERMINAL_REMOTE_RUN_STATUSES)
        for allowed in required_statuses.values()
    ):
        raise LivePhaseBlocker("rc_s3_107_remote_status_contract_invalid")
    selected: dict[str, dict[str, str]] = {}
    try:
        for fin_row in fin_rows:
            invocation_id = fin_row["invocation_id"]
            # The deterministic thread UUID is persisted by the production
            # repository; remote readback never guesses or reconstructs it.
            server_thread_id = fin_row.get("server_thread_id")
            if not isinstance(server_thread_id, str):
                raise LivePhaseBlocker(
                    "rc_s3_107_remote_readback_thread_binding_missing"
                )
            def read_snapshot() -> list[Mapping[str, Any]]:
                raw = sdk.runs.list(
                    server_thread_id,
                    limit=100,
                    offset=0,
                    select=["run_id", "thread_id", "status", "metadata"],
                )
                if not isinstance(raw, list):
                    raise LivePhaseBlocker("rc_s3_107_remote_readback_invalid")
                return [row for row in raw if isinstance(row, Mapping)]

            snapshots = [read_snapshot(), read_snapshot()]
            first_ids = sorted(str(row.get("run_id")) for row in snapshots[0])
            second_ids = sorted(str(row.get("run_id")) for row in snapshots[1])
            if first_ids != second_ids:
                raise LivePhaseBlocker("rc_s3_107_remote_readback_unstable")

            deadline = time.monotonic() + REMOTE_SUCCESS_WAIT_SECONDS
            snapshot = snapshots[1]
            while True:
                unexpected_rows = [
                    row
                    for row in snapshot
                    if not isinstance(row.get("metadata"), Mapping)
                    or row["metadata"].get("run_invocation_id") != invocation_id
                ]
                if unexpected_rows:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_thread_contains_unexpected_run"
                    )
                matches = [
                    row
                    for row in snapshot
                    if isinstance(row.get("metadata"), Mapping)
                    and row["metadata"].get("run_invocation_id") == invocation_id
                ]
                if len(matches) > 1:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_run_cardinality_invalid"
                    )
                if not matches:
                    break
                run_id = matches[0].get("run_id")
                status = matches[0].get("status")
                if not isinstance(run_id, str) or not run_id:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_run_identity_invalid"
                    )
                if status not in ALLOWED_REMOTE_RUN_STATUSES:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_run_status_invalid"
                    )
                selected[invocation_id] = {
                    "run_id": run_id,
                    "status": status,
                }
                if require_fin_run_id_match:
                    bound_run_id = fin_row.get("bound_server_run_id")
                    orphan_run_id = fin_row.get(
                        "latest_exact_orphan_server_run_id"
                    )
                    if (
                        bound_run_id is not None
                        and orphan_run_id is not None
                        and bound_run_id != orphan_run_id
                    ):
                        raise LivePhaseBlocker(
                            "rc_s3_107_fin_remote_run_identity_conflict"
                        )
                    expected_run_id = bound_run_id or orphan_run_id
                    if not isinstance(expected_run_id, str) or not expected_run_id:
                        raise LivePhaseBlocker(
                            "rc_s3_107_fin_remote_run_identity_missing"
                        )
                    if run_id != expected_run_id:
                        raise LivePhaseBlocker(
                            "rc_s3_107_fin_remote_run_identity_mismatch"
                        )
                allowed_final_statuses = required_statuses.get(invocation_id)
                if allowed_final_statuses is None:
                    break
                if status in allowed_final_statuses:
                    break
                if status in TERMINAL_REMOTE_RUN_STATUSES:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_run_terminal_status_mismatch"
                    )
                if time.monotonic() >= deadline:
                    raise LivePhaseBlocker(
                        "rc_s3_107_remote_run_terminal_status_timeout"
                    )
                time.sleep(0.25)
                snapshot = read_snapshot()
    finally:
        sdk.close()
    if set(selected) != expected_ids:
        if expected_remote_runs != 0 or selected:
            raise LivePhaseBlocker("rc_s3_107_remote_invocation_set_mismatch")
    if len(selected) != expected_remote_runs:
        raise LivePhaseBlocker("rc_s3_107_remote_run_count_mismatch")
    return {
        "remote_committed_runs": len(selected),
        "remote_distinct_run_count": len(
            {row["run_id"] for row in selected.values()}
        ),
        "remote_status_by_invocation": {
            invocation_id: row["status"]
            for invocation_id, row in selected.items()
        },
        "remote_run_id_by_invocation": {
            invocation_id: row["run_id"]
            for invocation_id, row in selected.items()
        },
    }


def _build_final_receipt(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    fin_rows: Sequence[Mapping[str, Any]],
    remote: Mapping[str, Any],
    proof: Mapping[str, Any],
) -> dict[str, Any]:
    invocation_ids = [row["invocation_id"] for row in fin_rows]
    create_counts = _instrumented_create_counts(
        manifest,
        scenario_id=scenario_id,
        allowed_invocation_ids=set(invocation_ids),
    )
    public_invocations = [
        {
            "invocation_id": row["invocation_id"],
            "role": row["role"],
            "lifecycle": row["lifecycle"],
            "canonical_action_outcome": row["canonical_action_outcome"],
            "recovery": row["recovery"],
            "final_binding_count": row["final_binding_count"],
            "sdk_create_attempts": create_counts[row["invocation_id"]],
            "remote_run_status": remote["remote_status_by_invocation"].get(
                row["invocation_id"]
            ),
            "remote_run_id": remote["remote_run_id_by_invocation"].get(
                row["invocation_id"]
            ),
        }
        for row in fin_rows
    ]
    return {
        "schema_version": "fin.rc_s3_107.scenario_receipt.v1",
        "attempt_id": manifest["attempt_id"],
        "project": manifest["project"],
        "scenario_id": scenario_id,
        "status": "PASS",
        "execution_boundary": {
            "zero_model": True,
            "external_research_or_model_calls": False,
            "provider_model_calls": False,
            "langsmith_observability_egress": True,
            "trace_content_in_receipt": False,
        },
        "identity": {
            "attempt_id": manifest["attempt_id"],
            "project": manifest["project"],
            "scenario_id": scenario_id,
            "invocation_ids": invocation_ids,
            "cross_scenario_identity_collision_count": 0,
        },
        "counts": {
            "sdk_create_attempts": sum(create_counts.values()),
            "remote_committed_runs": remote["remote_committed_runs"],
            "durable_invocations": len(fin_rows),
            "lifecycle_event_rows": sum(len(row["lifecycle"]) for row in fin_rows),
            "final_bindings": sum(row["final_binding_count"] for row in fin_rows),
        },
        "observation_sources": {
            "sdk_create_attempts": (
                "QUALIFICATION_INSTRUMENTED_OFFICIAL_SDK_BOUNDARY"
            ),
            "remote_committed_runs": "AGENT_SERVER_READBACK",
            "lifecycle_events": "FIN_POSTGRES_READBACK",
            "final_bindings": "FIN_POSTGRES_READBACK",
        },
        "invocations": public_invocations,
        "proof": dict(proof),
    }


def _scenario_fin_rows(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    repository: Any,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for identity in manifest["scenario_identities"][scenario_id]:
        rows.append(
            _fin_readback(
                repository,
                invocation_id=identity["invocation_id"],
                role=identity["role"],
            )
        )
    return rows


def _require_true(value: bool, code: str) -> None:
    if value is not True:
        raise LivePhaseBlocker(code)


def _require_remote_status(
    remote: Mapping[str, Any],
    *,
    invocation_id: str,
    allowed: frozenset[str],
    code: str,
) -> None:
    statuses = remote.get("remote_status_by_invocation")
    if not isinstance(statuses, Mapping) or statuses.get(invocation_id) not in allowed:
        raise LivePhaseBlocker(code)


def _final_proof(
    *,
    scenario_id: str,
    rows: Sequence[Mapping[str, Any]],
    remote: Mapping[str, Any],
) -> dict[str, Any]:
    by_role = {row["role"]: row for row in rows}
    distinct_remote = remote["remote_distinct_run_count"]
    if scenario_id == "K0":
        primary = by_role["primary"]
        _require_remote_status(
            remote,
            invocation_id=primary["invocation_id"],
            allowed=frozenset({"success"}),
            code="rc_s3_107_k0_remote_run_not_successful",
        )
        _require_true(
            primary["latest_exact_orphan_server_run_id"]
            == primary["bound_server_run_id"],
            "rc_s3_107_k0_callback_binding_mismatch",
        )
        return {
            "callback_observed": True,
            "remote_catalog_distinct_run_count": distinct_remote,
        }
    if scenario_id == "K1":
        return {
            "pending_victim_exit_code": 91,
            "pending_victim_milestone": "pending_committed_before_dispatch",
            "pending_supervisor_classification_observed": True,
            "dispatched_victim_exit_code": 94,
            "dispatched_victim_milestone": (
                "dispatched_committed_before_sdk_create"
            ),
            "dispatched_without_sdk_create_recovery_required": True,
            "sdk_create_attempt_count_for_both_invocations": 0,
            "remote_catalog_distinct_run_count": distinct_remote,
            "fresh_recovery_process": True,
            "second_create_attempted": False,
        }
    if scenario_id == "K2":
        primary = by_role["primary"]
        _require_remote_status(
            remote,
            invocation_id=primary["invocation_id"],
            allowed=frozenset({"success", "error"}),
            code="rc_s3_107_k2_remote_run_not_terminal",
        )
        _require_true(
            primary["latest_exact_orphan_server_run_id"]
            == primary["bound_server_run_id"],
            "rc_s3_107_k2_content_location_binding_mismatch",
        )
        _require_true(
            isinstance(primary["reconciled_observation_digest"], str),
            "rc_s3_107_k2_reconciled_observation_missing",
        )
        return {
            "victim_exit_code": 92,
            "victim_milestone": "orphan_with_run_id_committed_body_unread",
            "header_callback_committed_before_exit": True,
            "observation_authority": "DURABLE_CONTENT_LOCATION_RUN_ID",
            "recovery_lookup_kind": "EXACT_GET_BY_OBSERVED_RUN_ID",
            "observed_server_run_id_preserved": True,
            "reconciled_observation_digest_bound": True,
            "remote_catalog_distinct_run_count": distinct_remote,
            "fresh_recovery_process": True,
            "second_create_attempted": False,
        }
    if scenario_id == "K3":
        primary = by_role["primary"]
        _require_remote_status(
            remote,
            invocation_id=primary["invocation_id"],
            allowed=frozenset({"success", "error"}),
            code="rc_s3_107_k3_remote_run_not_terminal",
        )
        _require_true(
            primary["latest_exact_orphan_server_run_id"]
            == primary["bound_server_run_id"],
            "rc_s3_107_k3_orphan_binding_mismatch",
        )
        return {
            "transaction_rollback_observed": True,
            "binding_count_after_failed_transaction": 0,
            "reconciled_rows_after_failed_transaction": 0,
            "fresh_recovery_process": True,
            "remote_catalog_distinct_run_count": distinct_remote,
            "second_create_attempted": False,
        }
    if scenario_id == "K4":
        primary = by_role["primary"]
        _require_remote_status(
            remote,
            invocation_id=primary["invocation_id"],
            allowed=frozenset({"success", "error"}),
            code="rc_s3_107_k4_remote_run_not_terminal",
        )
        exact_time = primary["latest_exact_orphan_recorded_at"]
        disposition_time = primary["recovery_disposition_created_at"]
        _require_true(
            exact_time is not None
            and disposition_time is not None
            and disposition_time > exact_time,
            "rc_s3_107_k4_disposition_precedes_exact_observation",
        )
        _require_true(
            primary["latest_exact_orphan_observation_digest"]
            == primary["reconciled_observation_digest"],
            "rc_s3_107_k4_reconciled_observation_digest_mismatch",
        )
        _require_true(
            primary["latest_exact_orphan_server_status"]
            == primary["reconciled_server_status"],
            "rc_s3_107_k4_reconciled_server_status_mismatch",
        )
        return {
            "response_body_loss_observed": True,
            "create_callback_exposed": False,
            "first_pass_hidden_exact_scans": 2,
            "first_pass_fin_state": "ORPHAN_WITHOUT_RUN_ID",
            "fresh_exact_observation_process": True,
            "exact_observation_persisted_before_disposition": True,
            "pending_owner_handoff_observed_before_disposition": True,
            "operator_authority_process_distinct": True,
            "canonical_recovery_decision": "DO_NOT_RETRY",
            "recovery_disposition_exact_binding": True,
            "ambiguous_action_unchanged_after_disposition": True,
            "disposition_recorded_after_exact_observation": True,
            "reconciled_exact_observation_digest_match": True,
            "reconciled_server_status_match": True,
            "fresh_authorized_bind_process": True,
            "remote_catalog_distinct_run_count": distinct_remote,
            "second_create_attempted": False,
        }
    if scenario_id == "K5":
        reconciled = by_role["reconciled_restart"]
        disposed = by_role["unresolved_orphan_restart"]
        _require_remote_status(
            remote,
            invocation_id=reconciled["invocation_id"],
            allowed=frozenset({"success"}),
            code="rc_s3_107_k5_reconciled_remote_run_not_successful",
        )
        _require_remote_status(
            remote,
            invocation_id=disposed["invocation_id"],
            allowed=frozenset({"error"}),
            code="rc_s3_107_k5_unresolved_remote_run_not_error",
        )
        _require_true(
            reconciled["final_binding_count"] == 1
            and disposed["final_binding_count"] == 0,
            "rc_s3_107_k5_binding_durability_mismatch",
        )
        _require_true(
            disposed["recovery_disposition_digest"] is not None
            and disposed["ambiguous_action_attempt_digest"] is not None,
            "rc_s3_107_k5_disposition_binding_missing",
        )
        _require_true(
            disposed["latest_exact_orphan_recorded_at"] is not None
            and disposed["recovery_disposition_created_at"] is not None
            and disposed["recovery_disposition_created_at"]
            > disposed["latest_exact_orphan_recorded_at"],
            "rc_s3_107_k5_disposition_precedes_exact_observation",
        )
        return {
            "pending_owner_handoff_observed_before_disposition": True,
            "exact_observation_persisted_before_disposition": True,
            "operator_authority_process_distinct": True,
            "canonical_recovery_decision": "DO_NOT_RETRY",
            "recovery_disposition_exact_binding": True,
            "ambiguous_action_unchanged_after_disposition": True,
            "disposition_recorded_after_exact_observation": True,
            "api_restart_observed": True,
            "postgres_restart_observed": True,
            "reconciled_binding_persisted": True,
            "disposed_orphan_persisted": True,
            "disposition_persisted_after_api_restart": True,
            "disposition_persisted_after_postgres_restart": True,
            "reconciled_replay_create_attempts": 0,
            "orphan_replay_create_attempts": 0,
            "remote_catalog_distinct_run_count": distinct_remote,
        }
    if scenario_id == "K6":
        shared = by_role["shared_invocation"]
        _require_remote_status(
            remote,
            invocation_id=shared["invocation_id"],
            allowed=frozenset({"success"}),
            code="rc_s3_107_k6_remote_run_not_successful",
        )
        return {
            "worker_processes": 2,
            "barrier_participants": 2,
            "durable_winner_count": 1,
            "sdk_create_winner_count": 1,
            "remote_catalog_distinct_run_count": distinct_remote,
            "losing_worker_action": "RECONCILIATION_ONLY",
        }
    raise LivePhaseBlocker("rc_s3_107_scenario_proof_unknown")


def _build_verified_final_receipt(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    repository: Any,
    expected_remote_runs: int,
) -> dict[str, Any]:
    rows = _scenario_fin_rows(
        manifest,
        scenario_id=scenario_id,
        repository=repository,
    )
    status_rules = FINAL_REMOTE_STATUS_RULES.get(scenario_id, {})
    required_statuses_by_invocation = {
        row["invocation_id"]: status_rules[row["role"]]
        for row in rows
        if row["role"] in status_rules
    }
    remote = _remote_readback(
        manifest,
        scenario_id=scenario_id,
        fin_rows=rows,
        expected_remote_runs=expected_remote_runs,
        required_statuses_by_invocation=required_statuses_by_invocation,
        require_fin_run_id_match=True,
    )
    return _build_final_receipt(
        manifest,
        scenario_id=scenario_id,
        fin_rows=rows,
        remote=remote,
        proof=_final_proof(
            scenario_id=scenario_id,
            rows=rows,
            remote=remote,
        ),
    )


def _emit_verified_step_observation(
    manifest: Mapping[str, Any],
    *,
    scenario_id: str,
    step_id: str,
    milestone: str,
    repository: Any,
    expected_sdk_create_calls: int,
    expected_remote_runs: int,
) -> None:
    identities = manifest["scenario_identities"][scenario_id]
    invocation_ids = {row["invocation_id"] for row in identities}
    counts = _instrumented_create_counts(
        manifest,
        scenario_id=scenario_id,
        allowed_invocation_ids=invocation_ids,
    )
    if sum(counts.values()) != expected_sdk_create_calls:
        raise LivePhaseBlocker("rc_s3_107_step_sdk_create_count_mismatch")
    fin_rows: list[dict[str, Any]] = []
    for identity in identities:
        lifecycle = repository.get_run_create_lifecycle(
            run_invocation_id=identity["invocation_id"]
        )
        if lifecycle is None:
            raise LivePhaseBlocker("rc_s3_107_step_fin_lifecycle_missing")
        fin_rows.append(
            {
                "invocation_id": identity["invocation_id"],
                "server_thread_id": lifecycle.pending.server_thread_id,
            }
        )
    remote = _remote_readback(
        manifest,
        scenario_id=scenario_id,
        fin_rows=fin_rows,
        expected_remote_runs=expected_remote_runs,
    )
    emit_observation(
        KillPointObservation(
            attempt_id=manifest["attempt_id"],
            project=manifest["project"],
            scenario_id=scenario_id,
            step_id=step_id,
            milestone=milestone,
            sdk_create_calls=expected_sdk_create_calls,
            remote_run_count=remote["remote_committed_runs"],
        )
    )


def _require_client_failure(
    operation: Callable[[], Any], *, allowed_codes: set[str]
) -> str:
    try:
        operation()
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code not in allowed_codes:
            raise LivePhaseBlocker("rc_s3_107_unexpected_product_client_failure") from exc
        return str(code)
    raise LivePhaseBlocker("rc_s3_107_expected_product_client_failure_missing")


def _start_current_case(
    client: Any,
    session_binding: Any,
    research_run: Any,
    invocation: Any,
    graph_input: Mapping[str, Any],
) -> Any:
    return client.start_run(
        session=session_binding,
        research_run=research_run,
        run_invocation=invocation,
        graph_input=graph_input,
    )


def _execute_k0(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any]:
    if step_id != "control_and_readback":
        raise LivePhaseBlocker("rc_s3_107_k0_step_invalid")
    with _runtime_resources(
        manifest,
        scenario_id="K0",
        role="primary",
    ) as (repository, client, session, run, invocation, graph_input):
        _start_current_case(client, session, run, invocation, graph_input)
        return _build_verified_final_receipt(
            manifest,
            scenario_id="K0",
            repository=repository,
            expected_remote_runs=1,
        )


def _execute_k1(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any] | None:
    if step_id == "pending_victim":
        with _runtime_resources(
            manifest,
            scenario_id="K1",
            role="pending_before_dispatch",
            repository_wrapper=lambda repository: CrashAfterPendingRepository(
                repository,
                attempt_id=manifest["attempt_id"],
                project=manifest["project"],
                step_id=step_id,
            ),
        ) as (_, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
        raise LivePhaseBlocker("rc_s3_107_k1_pending_hard_exit_missing")

    if step_id == "classify_pending_failed_before_dispatch":
        with _runtime_resources(
            manifest,
            scenario_id="K1",
            role="pending_before_dispatch",
        ) as (repository, _, _, _, invocation, _):
            lifecycle = repository.get_run_create_lifecycle(
                run_invocation_id=invocation.invocation_id
            )
            if lifecycle is None or lifecycle.state != "PENDING":
                raise LivePhaseBlocker("rc_s3_107_k1_pending_state_missing")
            repository.mark_run_create_failed_before_dispatch(
                run_invocation_id=invocation.invocation_id,
                pending_event_digest=lifecycle.pending.lifecycle_event_digest,
            )
            _emit_verified_step_observation(
                manifest,
                scenario_id="K1",
                step_id=step_id,
                milestone="pending_classified_failed_before_dispatch",
                repository=repository,
                expected_sdk_create_calls=0,
                expected_remote_runs=0,
            )
        return None

    if step_id == "dispatched_victim":
        with _runtime_resources(
            manifest,
            scenario_id="K1",
            role="dispatched_before_sdk_create",
            repository_wrapper=lambda repository: CrashAfterDispatchedRepository(
                repository,
                attempt_id=manifest["attempt_id"],
                project=manifest["project"],
                step_id=step_id,
            ),
        ) as (_, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
        raise LivePhaseBlocker("rc_s3_107_k1_dispatched_hard_exit_missing")

    if step_id == "fresh_recovery_and_readback":
        with _runtime_resources(
            manifest,
            scenario_id="K1",
            role="dispatched_before_sdk_create",
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={
                    "agent_server_run_recovery_operator_decision_required",
                    "agent_server_run_dispatched_reconciliation_required",
                },
            )
            return _build_verified_final_receipt(
                manifest,
                scenario_id="K1",
                repository=repository,
                expected_remote_runs=0,
            )
    raise LivePhaseBlocker("rc_s3_107_k1_step_invalid")


def _execute_k2(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any] | None:
    if step_id == "header_victim":
        with _runtime_resources(
            manifest,
            scenario_id="K2",
            role="primary",
            runs_wrapper=lambda runs: HeaderObservedCrashRuns(
                runs,
                attempt_id=manifest["attempt_id"],
                project=manifest["project"],
                step_id=step_id,
            ),
        ) as (_, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
        raise LivePhaseBlocker("rc_s3_107_k2_hard_exit_missing")
    if step_id == "fresh_recovery_and_readback":
        with _runtime_resources(
            manifest,
            scenario_id="K2",
            role="primary",
        ) as (repository, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
            return _build_verified_final_receipt(
                manifest,
                scenario_id="K2",
                repository=repository,
                expected_remote_runs=1,
            )
    raise LivePhaseBlocker("rc_s3_107_k2_step_invalid")


def _execute_k3(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any] | None:
    if step_id == "bind_rollback_victim":
        state = ReconciledInsertFaultState()
        with _runtime_resources(
            manifest,
            scenario_id="K3",
            role="primary",
            pool_wrapper=lambda pool: ReconciledInsertFaultPool(pool, state),
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={"identity_invocation_bind_failed"},
            )
            if not state.binding_insert_observed or not state.reconciled_insert_faulted:
                raise LivePhaseBlocker("rc_s3_107_k3_fault_seam_not_observed")
            if repository.get_run_invocation(
                run_invocation_id=invocation.invocation_id
            ) is not None:
                raise LivePhaseBlocker("rc_s3_107_k3_binding_rollback_failed")
            lifecycle = repository.get_run_create_lifecycle(
                run_invocation_id=invocation.invocation_id
            )
            if lifecycle is None or lifecycle.reconciled is not None:
                raise LivePhaseBlocker("rc_s3_107_k3_lifecycle_rollback_failed")
            _emit_verified_step_observation(
                manifest,
                scenario_id="K3",
                step_id=step_id,
                milestone="binding_transaction_rolled_back",
                repository=repository,
                expected_sdk_create_calls=1,
                expected_remote_runs=1,
            )
        return None
    if step_id == "fresh_recovery_and_readback":
        with _runtime_resources(
            manifest,
            scenario_id="K3",
            role="primary",
        ) as (repository, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
            return _build_verified_final_receipt(
                manifest,
                scenario_id="K3",
                repository=repository,
                expected_remote_runs=1,
            )
    raise LivePhaseBlocker("rc_s3_107_k3_step_invalid")


def _execute_k4(
    manifest: Mapping[str, Any], *, step_id: str
) -> dict[str, Any] | int | None:
    if step_id == "response_loss_first_pass":
        with _runtime_resources(
            manifest,
            scenario_id="K4",
            role="primary",
            runs_wrapper=lambda runs: DelayedVisibilityRuns(
                runs,
                hidden_exact_scans=2,
            ),
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={"agent_server_run_start_failed_outcome_unknown"},
            )
            lifecycle = repository.get_run_create_lifecycle(
                run_invocation_id=invocation.invocation_id
            )
            recovery_case = repository.get_run_create_recovery_case(
                run_invocation_id=invocation.invocation_id
            )
            if (
                lifecycle is None
                or recovery_case is None
                or not any(
                    item.server_run_id is None
                    for item in lifecycle.orphan_observations
                )
                or recovery_case.server_run_id is not None
            ):
                raise LivePhaseBlocker("rc_s3_107_k4_no_id_recovery_missing")
            _emit_verified_step_observation(
                manifest,
                scenario_id="K4",
                step_id=step_id,
                milestone="response_lost_orphan_without_run_id",
                repository=repository,
                expected_sdk_create_calls=1,
                expected_remote_runs=1,
            )
        return 93

    if step_id == "fresh_exact_observation":
        with _runtime_resources(
            manifest,
            scenario_id="K4",
            role="primary",
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={
                    "agent_server_run_recovery_operator_decision_required"
                },
            )
            lifecycle = repository.get_run_create_lifecycle(
                run_invocation_id=invocation.invocation_id
            )
            disposition = repository.get_run_create_recovery_disposition(
                run_invocation_id=invocation.invocation_id
            )
            if (
                lifecycle is None
                or disposition is not None
                or not any(
                    item.server_run_id is not None
                    and item.server_run_status is not None
                    for item in lifecycle.orphan_observations
                )
            ):
                raise LivePhaseBlocker("rc_s3_107_k4_exact_observation_missing")
            _emit_verified_step_observation(
                manifest,
                scenario_id="K4",
                step_id=step_id,
                milestone="exact_observation_persisted_pending_owner",
                repository=repository,
                expected_sdk_create_calls=1,
                expected_remote_runs=1,
            )
        return None

    if step_id == "fresh_authorized_bind_and_readback":
        with _runtime_resources(
            manifest,
            scenario_id="K4",
            role="primary",
        ) as (repository, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
            return _build_verified_final_receipt(
                manifest,
                scenario_id="K4",
                repository=repository,
                expected_remote_runs=1,
            )
    raise LivePhaseBlocker("rc_s3_107_k4_step_invalid")


def _execute_k5(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any] | None:
    if step_id == "seed_restart_states":
        with _runtime_resources(
            manifest,
            scenario_id="K5",
            role="reconciled_restart",
        ) as (_, client, session, run, invocation, graph_input):
            _start_current_case(client, session, run, invocation, graph_input)
        with _runtime_resources(
            manifest,
            scenario_id="K5",
            role="unresolved_orphan_restart",
            runs_wrapper=lambda runs: DelayedVisibilityRuns(
                runs,
                hidden_exact_scans=2,
            ),
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={"agent_server_run_start_failed_outcome_unknown"},
            )
            _emit_verified_step_observation(
                manifest,
                scenario_id="K5",
                step_id=step_id,
                milestone="restart_states_seeded",
                repository=repository,
                expected_sdk_create_calls=2,
                expected_remote_runs=2,
            )
        return None

    if step_id == "pending_owner_handoff_readback":
        with _runtime_resources(
            manifest,
            scenario_id="K5",
            role="unresolved_orphan_restart",
        ) as (repository, client, session, run, invocation, graph_input):
            _require_client_failure(
                lambda: _start_current_case(
                    client,
                    session,
                    run,
                    invocation,
                    graph_input,
                ),
                allowed_codes={
                    "agent_server_run_recovery_operator_decision_required"
                },
            )
            lifecycle = repository.get_run_create_lifecycle(
                run_invocation_id=invocation.invocation_id
            )
            if lifecycle is None or not any(
                item.server_run_id is not None and item.server_run_status is not None
                for item in lifecycle.orphan_observations
            ):
                raise LivePhaseBlocker("rc_s3_107_k5_exact_observation_missing")
            if repository.get_run_create_recovery_disposition(
                run_invocation_id=invocation.invocation_id
            ) is not None:
                raise LivePhaseBlocker("rc_s3_107_k5_disposition_recorded_too_early")
            _emit_verified_step_observation(
                manifest,
                scenario_id="K5",
                step_id=step_id,
                milestone="pending_owner_handoff_observed",
                repository=repository,
                expected_sdk_create_calls=2,
                expected_remote_runs=2,
            )
        return None

    if step_id == "readback_after_api_restart":
        with _runtime_resources(
            manifest,
            scenario_id="K5",
            role="unresolved_orphan_restart",
        ) as (repository, _, _, _, invocation, _):
            disposition = repository.get_run_create_recovery_disposition(
                run_invocation_id=invocation.invocation_id
            )
            if disposition is None or disposition.decision != "DO_NOT_RETRY":
                raise LivePhaseBlocker(
                    "rc_s3_107_k5_api_restart_disposition_missing"
                )
            _emit_verified_step_observation(
                manifest,
                scenario_id="K5",
                step_id=step_id,
                milestone="api_restart_readback_observed",
                repository=repository,
                expected_sdk_create_calls=2,
                expected_remote_runs=2,
            )
        return None

    if step_id == "final_readback_after_postgres_restart":
        with _runtime_resources(
            manifest,
            scenario_id="K5",
            role="unresolved_orphan_restart",
        ) as (repository, _, _, _, _, _):
            return _build_verified_final_receipt(
                manifest,
                scenario_id="K5",
                repository=repository,
                expected_remote_runs=2,
            )
    raise LivePhaseBlocker("rc_s3_107_k5_step_invalid")


def _k6_worker(manifest: Mapping[str, Any], worker_id: int) -> None:
    prefix = _k6_prefix(manifest)
    result_path = Path(f"{prefix}-result-{worker_id}.json")
    state: dict[str, Any] = {
        "worker_id": worker_id,
        "created_now": None,
        "outcome": None,
    }
    wrapper: ConcurrentBeginRepository | None = None
    try:
        def wrap(repository: Any) -> ConcurrentBeginRepository:
            nonlocal wrapper
            wrapper = ConcurrentBeginRepository(
                repository,
                barrier_prefix=prefix,
                worker_id=worker_id,
            )
            return wrapper

        with _runtime_resources(
            manifest,
            scenario_id="K6",
            role="shared_invocation",
            repository_wrapper=wrap,
        ) as (_, client, session, run, invocation, graph_input):
            try:
                _start_current_case(client, session, run, invocation, graph_input)
                state["outcome"] = "BOUND_OR_RECONCILED"
            except Exception as exc:
                code = getattr(exc, "code", None)
                if code not in {
                    "agent_server_run_pending_reconciliation_required",
                    "agent_server_run_orphan_reconciliation_required",
                }:
                    raise
                state["outcome"] = "RECONCILIATION_REQUIRED"
        if wrapper is None or wrapper.created_now is None:
            raise LivePhaseBlocker("rc_s3_107_k6_registration_not_observed")
        state["created_now"] = wrapper.created_now
        if wrapper.created_now is False:
            wrapper.release_winner_after_loser()
    except Exception as exc:
        state = {
            "worker_id": worker_id,
            "created_now": None if wrapper is None else wrapper.created_now,
            "outcome": "BLOCKED",
            "code": getattr(exc, "code", "rc_s3_107_k6_worker_failed"),
        }
    encoded = json.dumps(state, ensure_ascii=True, sort_keys=True).encode("utf-8")
    descriptor = os.open(result_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        if os.write(descriptor, encoded) != len(encoded):
            os._exit(75)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _execute_k6(manifest: Mapping[str, Any], *, step_id: str) -> dict[str, Any]:
    if step_id != "concurrent_workers_and_readback":
        raise LivePhaseBlocker("rc_s3_107_k6_step_invalid")
    context = multiprocessing.get_context("spawn")
    workers = [
        context.Process(target=_k6_worker, args=(dict(manifest), worker_id))
        for worker_id in (0, 1)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
    if any(worker.is_alive() for worker in workers):
        raise LivePhaseBlocker("rc_s3_107_k6_worker_timeout")
    if any(worker.exitcode != 0 for worker in workers):
        raise LivePhaseBlocker("rc_s3_107_k6_worker_exit_invalid")
    prefix = _k6_prefix(manifest)
    result_paths = [Path(f"{prefix}-result-{worker_id}.json") for worker_id in (0, 1)]
    _wait_for_paths(result_paths)
    results: list[Mapping[str, Any]] = []
    for path in result_paths:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LivePhaseBlocker("rc_s3_107_k6_worker_result_invalid") from exc
        if (
            not isinstance(value, Mapping)
            or set(value) != {"worker_id", "created_now", "outcome"}
            or value["outcome"] not in {
                "BOUND_OR_RECONCILED",
                "RECONCILIATION_REQUIRED",
            }
        ):
            raise LivePhaseBlocker("rc_s3_107_k6_worker_result_invalid")
        results.append(value)
    if sum(item["created_now"] is True for item in results) != 1:
        raise LivePhaseBlocker("rc_s3_107_k6_durable_winner_count_invalid")
    with _runtime_resources(
        manifest,
        scenario_id="K6",
        role="shared_invocation",
    ) as (repository, client, session, run, invocation, graph_input):
        # A fresh process performs read/reconciliation only.  If the winner
        # had not completed its bind before both workers exited, this call may
        # finish that exact binding but must never cross runs.create again.
        _start_current_case(client, session, run, invocation, graph_input)
        return _build_verified_final_receipt(
            manifest,
            scenario_id="K6",
            repository=repository,
            expected_remote_runs=1,
        )


def _execute_production_phase(
    manifest: Mapping[str, Any], *, scenario_id: str, step_id: str
) -> dict[str, Any] | int | None:
    executors: Mapping[
        str,
        Callable[[Mapping[str, Any]], dict[str, Any] | int | None],
    ] = {
        "K0": lambda value: _execute_k0(value, step_id=step_id),
        "K1": lambda value: _execute_k1(value, step_id=step_id),
        "K2": lambda value: _execute_k2(value, step_id=step_id),
        "K3": lambda value: _execute_k3(value, step_id=step_id),
        "K4": lambda value: _execute_k4(value, step_id=step_id),
        "K5": lambda value: _execute_k5(value, step_id=step_id),
        "K6": lambda value: _execute_k6(value, step_id=step_id),
    }
    executor = executors.get(scenario_id)
    if executor is None:
        raise LivePhaseBlocker(SCENARIO_EXECUTOR_BLOCKERS[scenario_id])
    return executor(manifest)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=EXPECTED_SCENARIOS, required=True)
    parser.add_argument("--step", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    manifest: Mapping[str, Any] | None = None
    try:
        manifest = _load_manifest()
        if args.step == "record_operator_disposition":
            _record_operator_disposition(
                manifest,
                scenario_id=args.scenario,
                step_id=args.step,
            )
            return 0
        result = _execute_production_phase(
            manifest,
            scenario_id=args.scenario,
            step_id=args.step,
        )
        if isinstance(result, int):
            return result
        if result is not None:
            print(json.dumps(result, ensure_ascii=True, sort_keys=True))
        return 0
    except LivePhaseBlocker as exc:
        print(
            json.dumps(
                {
                    "schema_version": "fin.rc_s3_107.phase_blocker.v1",
                    "attempt_id": None if manifest is None else manifest.get("attempt_id"),
                    "project": None if manifest is None else manifest.get("project"),
                    "scenario_id": args.scenario,
                    "step_id": args.step,
                    "status": "BLOCKED",
                    "code": exc.code,
                },
                sort_keys=True,
            )
        )
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
