from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Mapping

from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.research_runtime import (
    S3ThreeCellPreparedExecution,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


BUSINESS_PROJECTION_SCHEMA = (
    "fin_ia_0_1_2_s3_stable_business_input_projection_v1_0"
)
EXECUTION_ENVELOPE_SCHEMA = (
    "fin_ia_0_1_2_s3_t03_fresh_identity_execution_envelope_v1_0"
)
CAPTURE_SCHEMA = "fin_ia_0_1_2_s3_t03_restricted_provider_capture_v1_0"
CAPTURE_INDEX_SCHEMA = "fin_ia_0_1_2_s3_t03_capture_index_v1_0"
TERMINAL_SCHEMA = "fin_ia_0_1_2_s3_t03_typed_terminal_result_v1_0"
EXECUTION_RESULT_SCHEMA = "fin_ia_0_1_2_s3_t03_execution_result_v1_0"
EXECUTION_STATE_SCHEMA = "fin_ia_0_1_2_s3_t03_execution_state_v1_0"
BOUND_ENVELOPE_REF = (
    "configs/runtime/fin_ia_0_1_2_s3_t03_nvda_fresh_identity_"
    "execution_envelope_v1_0.json"
)

CAPTURE_NAMESPACE = "s3-t03/restricted-provider-captures"
TERMINAL_NAMESPACE = "s3-t03/terminal-results"

_EXECUTION_DERIVED_KEYS = {
    "input_digest",
    "research_run_id",
    "branch_version_ref",
    "cell_route_digest",
    "evidence_operator_context_plan_ref",
    "boundary_digest",
    "boundary_id",
    "cell_projection_digest",
    "cell_projection_id",
    "edge_projection_digest",
    "edge_projection_id",
    "risk_context_digest",
    "risk_context_id",
    "observation_digest",
    "observation_id",
    "followup_request_digest",
    "followup_request_id",
    "originating_graph_observation_ref",
    "source_followup_request_ref",
    "context_input_digest",
    "context_plan_id",
    "context_plan_version_ref",
}
_EXECUTION_DERIVED_REF_PREFIXES = (
    "branch_fin01_s3_",
    "context_plan_fin01_s3_",
    "research_run_fin01_",
    "s3_financial_numeric_pack_",
    "s3_graph_decision_cell_",
    "s3_graph_edge_projection_",
    "s3_graph_observation_",
    "s3_risk_context_",
    "s3_source_followup_",
    "s3_sourcehunter_boundary_",
)
_EXECUTION_REF_FIELDS = {
    "context_ref",
    "dependency_refs",
    "followup_refs",
    "graph_context_refs_not_evidence",
    "graph_edge_projection_ref",
    "risk_context_ref",
    "source_followup_refs",
    "source_ref",
}
_SAFE_INFERENCE_ARGUMENTS = {
    "llm_backend",
    "base_url",
    "chat_completions_path",
    "model",
    "messages",
    "tools",
    "tool_choice",
    "response_format",
    "temperature",
    "max_tokens",
    "timeout_s",
    "stream",
    "enable_thinking",
    "reasoning_effort",
    "role",
    "profile",
    "trace_tags",
    "max_transport_attempts",
}


class Fin012S3T03RunnerError(RuntimeError):
    pass


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / BOUND_ENVELOPE_REF).is_file():
            return parent
    raise Fin012S3T03RunnerError("s3_t03_repository_root_not_found")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _is_execution_ref(value: str) -> bool:
    return value.startswith(_EXECUTION_DERIVED_REF_PREFIXES)


def _stable_value(value: Any, *, parent_key: str = "") -> Any:
    if isinstance(value, Mapping):
        projected: dict[str, Any] = {}
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            if key in _EXECUTION_DERIVED_KEYS:
                continue
            projected[key] = _stable_value(raw_value, parent_key=key)
        return projected
    if isinstance(value, (list, tuple)):
        return [_stable_value(row, parent_key=parent_key) for row in value]
    if (
        isinstance(value, str)
        and parent_key in _EXECUTION_REF_FIELDS
        and _is_execution_ref(value)
    ):
        return "__execution_derived_ref__"
    return deepcopy(value)


def build_fin_0_1_2_s3_business_input_projection(
    input_pack: S3ThreeCellBoundedAgentInputPack | Mapping[str, Any],
) -> dict[str, Any]:
    """Project business semantics without weakening evidence or numeric authority.

    Only fields proven to be derived from WorkUnit/Attempt/Run identity are
    removed or normalized. Query, case head, accepted evidence and numeric
    authority remain content-bound.
    """

    raw = (
        input_pack.model_dump(mode="json")
        if isinstance(input_pack, S3ThreeCellBoundedAgentInputPack)
        else deepcopy(dict(input_pack))
    )
    raw.pop("lineage", None)
    projected = _stable_value(raw)
    return {
        "schema_version": BUSINESS_PROJECTION_SCHEMA,
        "projection_policy": (
            "explicit_execution_identity_derived_field_normalization"
        ),
        "business_input": projected,
    }


def business_input_digest(
    input_pack: S3ThreeCellBoundedAgentInputPack | Mapping[str, Any],
) -> str:
    return canonical_digest(build_fin_0_1_2_s3_business_input_projection(input_pack))


def load_bound_s3_t03_execution_envelope(
    repository_root: str | Path | None = None,
    *,
    envelope_ref: str = BOUND_ENVELOPE_REF,
) -> dict[str, Any]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    relative = Path(envelope_ref)
    if relative.is_absolute() or ".." in relative.parts:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_ref_invalid")
    payload = json.loads((root / relative).read_text(encoding="utf-8"))
    if payload.get("schema_version") != EXECUTION_ENVELOPE_SCHEMA:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_schema_mismatch")
    declared = payload.get("envelope_digest")
    actual = canonical_digest(
        {key: value for key, value in payload.items() if key != "envelope_digest"}
    )
    if declared != actual:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_digest_mismatch")
    if payload.get("admission") != {
        "issued": False,
        "persisted": False,
        "execution_enabled": False,
    }:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_admission_drift")
    return payload


def compile_fresh_identity_execution_envelope(
    *,
    tracked_t02: S3ThreeCellPreparedExecution,
    fresh_t03: S3ThreeCellPreparedExecution,
    authority_ref: str,
    authority_sha256: str,
    runtime_contract_binding_ref: str,
    runtime_contract_source_digest: str,
    hard_budget: Mapping[str, Any],
) -> dict[str, Any]:
    tracked_business_digest = business_input_digest(tracked_t02.input_pack)
    fresh_business_digest = business_input_digest(fresh_t03.input_pack)
    if tracked_business_digest != fresh_business_digest:
        raise Fin012S3T03RunnerError("s3_t03_stable_business_input_mismatch")
    if tracked_t02.input_digest == fresh_t03.input_digest:
        raise Fin012S3T03RunnerError("s3_t03_fresh_identity_did_not_change_full_input")
    if fresh_t03.execution_identity == tracked_t02.execution_identity:
        raise Fin012S3T03RunnerError("s3_t03_execution_identity_not_fresh")
    required_budget = {
        "semantic_model_calls": 9,
        "provider_calls": 9,
        "execution_network_calls": 9,
        "maximum_transport_attempts_per_call": 1,
        "retry_budget": 0,
        "fallback_budget": 0,
        "provider_hopping_budget": 0,
        "maximum_input_tokens": 60000,
        "maximum_output_tokens": 10000,
        "maximum_total_cost_usd": 0.06,
        "maximum_wall_clock_seconds": 900,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "failed_output_business_promotions": 0,
    }
    observed = {key: hard_budget.get(key) for key in required_budget}
    if observed != required_budget:
        raise Fin012S3T03RunnerError("s3_t03_hard_budget_binding_mismatch")
    payload = {
        "schema_version": EXECUTION_ENVELOPE_SCHEMA,
        "authority": {
            "ref": authority_ref,
            "sha256": authority_sha256,
        },
        "stable_business_input": {
            "projection_schema": BUSINESS_PROJECTION_SCHEMA,
            "digest": fresh_business_digest,
            "case_id": fresh_t03.case_id,
            "case_version": fresh_t03.case_version,
            "input_head_digest": fresh_t03.input_pack.input_head_digest,
        },
        "historical_t02": {
            "execution_identity": tracked_t02.execution_identity,
            "input_digest": tracked_t02.input_digest,
            "preparation_digest": tracked_t02.preparation_digest,
        },
        "fresh_t03": {
            "execution_identity": fresh_t03.execution_identity,
            "work_unit_id": fresh_t03.work_unit_id,
            "attempt_id": fresh_t03.attempt_id,
            "research_run_id": fresh_t03.research_run_id,
            "input_digest": fresh_t03.input_digest,
            "preparation_digest": fresh_t03.preparation_digest,
            "lineage": deepcopy(fresh_t03.input_pack.lineage),
        },
        "runtime_contract": {
            "binding_ref": runtime_contract_binding_ref,
            "source_digest": runtime_contract_source_digest,
        },
        "hard_budget": required_budget,
        "admission": {
            "issued": False,
            "persisted": False,
            "execution_enabled": False,
        },
        "observed_counts": {
            "credential_reads_or_probes": 0,
            "admissions_issued_or_persisted": 0,
            "model_calls": 0,
            "provider_calls": 0,
            "network_calls": 0,
            "business_Runs": 0,
            "business_Artifacts": 0,
        },
        "business_promotable": False,
    }
    return {**payload, "envelope_digest": canonical_digest(payload)}


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def claim_supervised_execution_identity(
    runtime_root: str | Path,
    envelope: Mapping[str, Any],
    *,
    supervision_root: str | Path,
) -> dict[str, Any]:
    """Atomically consume the one execution identity before child launch.

    The parent owns this claim. A child may only transition the exact claim to
    ``execution_claimed``; a second parent or an unsupervised replay fails.
    """

    runtime = Path(runtime_root).resolve()
    runtime.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(runtime, 0o700)
    except OSError:
        pass
    path = runtime / "execution-state.json"
    payload = {
        "schema_version": EXECUTION_STATE_SCHEMA,
        "status": "supervisor_claimed",
        "execution_identity": envelope["fresh_t03"]["execution_identity"],
        "envelope_digest": envelope["envelope_digest"],
        "supervision_root": str(Path(supervision_root).resolve()),
        "terminal_materialized": False,
        "credential_value_persisted": False,
        "business_promotable": False,
    }
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Fin012S3T03RunnerError(
            "s3_t03_execution_identity_already_claimed"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_canonical_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())
    return payload


def _claim_execution_identity(runtime_root: Path, envelope: Mapping[str, Any]) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(runtime_root, 0o700)
    except OSError:
        pass
    path = runtime_root / "execution-state.json"
    payload = {
        "schema_version": EXECUTION_STATE_SCHEMA,
        "status": "execution_claimed",
        "execution_identity": envelope["fresh_t03"]["execution_identity"],
        "envelope_digest": envelope["envelope_digest"],
        "terminal_materialized": False,
        "credential_value_persisted": False,
        "business_promotable": False,
    }
    if path.exists():
        current = json.loads(path.read_text(encoding="utf-8"))
        if (
            current.get("status") != "supervisor_claimed"
            or current.get("execution_identity")
            != envelope["fresh_t03"]["execution_identity"]
            or current.get("envelope_digest") != envelope["envelope_digest"]
            or not current.get("supervision_root")
        ):
            raise Fin012S3T03RunnerError(
                "s3_t03_execution_identity_already_claimed"
            )
        _atomic_write_json(
            path,
            {
                **current,
                "status": "execution_claimed",
                "terminal_materialized": False,
                "credential_value_persisted": False,
                "business_promotable": False,
            },
        )
        return
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Fin012S3T03RunnerError(
            "s3_t03_execution_identity_already_claimed"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(_canonical_bytes(payload))
        handle.flush()
        os.fsync(handle.fileno())


@dataclass
class _BudgetState:
    call_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class _CaptureFirstCompletion:
    def __init__(
        self,
        *,
        completion: Callable[..., Mapping[str, Any]],
        store: FileCanonicalObjectStore,
        runtime_root: Path,
        admission: S3ThreeCellBoundedAgentAdmission,
        clock: Callable[[], float],
        started: float,
    ) -> None:
        self._completion = completion
        self._store = store
        self._runtime_root = runtime_root
        self._admission = admission
        self._clock = clock
        self._started = started
        self.state = _BudgetState()
        self.capture_objects: list[dict[str, Any]] = []

    def _assert_pre_call_budget(self) -> None:
        if self.state.call_count >= 9:
            raise Fin012S3T03RunnerError("s3_t03_provider_call_budget_exceeded")
        if self._clock() - self._started > 900:
            raise Fin012S3T03RunnerError("s3_t03_wall_clock_budget_exceeded")

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        self._assert_pre_call_budget()
        self.state.call_count += 1
        response = self._completion(**kwargs)
        if not isinstance(response, Mapping):
            raise Fin012S3T03RunnerError("s3_t03_provider_envelope_invalid")
        input_tokens = int(response.get("input_tokens") or 0)
        output_tokens = int(response.get("output_tokens") or 0)
        total_cost = round(
            self.state.estimated_cost_usd
            + input_tokens * self._admission.input_cache_miss_usd_per_million / 1_000_000
            + output_tokens * self._admission.output_usd_per_million / 1_000_000,
            8,
        )
        assistant = response.get("content")
        assistant_text = (
            assistant
            if isinstance(assistant, str)
            else _canonical_bytes(assistant).decode("utf-8")
        )
        capture = {
            "schema_version": CAPTURE_SCHEMA,
            "capture_sequence": len(self.capture_objects) + 1,
            "stage": str(kwargs.get("role") or "unknown"),
            "model_visible_request": deepcopy(kwargs.get("messages") or []),
            "assistant_output_text": assistant_text,
            "finish_reason": response.get("finish_reason"),
            "usage": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": int(response.get("total_tokens") or input_tokens + output_tokens),
            },
            "latency_ms": response.get("latency_ms"),
            "transport_attempt_count": response.get("transport_attempt_count"),
            "nonsecret_inference_arguments": {
                key: deepcopy(value)
                for key, value in kwargs.items()
                if key in _SAFE_INFERENCE_ARGUMENTS and key != "messages"
            },
            "capture_before_local_parse_or_validation": True,
            "credentials_included": False,
            "authorization_headers_included": False,
            "cookies_included": False,
            "private_reasoning_included": False,
            "raw_provider_response_included": False,
            "business_promotable": False,
        }
        capture_object = self._store.put_json(
            capture,
            namespace=CAPTURE_NAMESPACE,
            artifact_type="restricted_provider_interaction_capture",
        )
        if capture_object["digest"] != canonical_digest(capture):
            raise Fin012S3T03RunnerError("s3_t03_capture_digest_mismatch")
        self.capture_objects.append(capture_object)
        _atomic_write_json(
            self._runtime_root / "capture-index.json",
            {
                "schema_version": CAPTURE_INDEX_SCHEMA,
                "capture_objects": self.capture_objects,
                "capture_count": len(self.capture_objects),
                "terminal_materialized": False,
                "business_promotable": False,
            },
        )
        self.state.input_tokens += input_tokens
        self.state.output_tokens += output_tokens
        self.state.estimated_cost_usd = total_cost
        if int(response.get("transport_attempt_count") or 0) != 1:
            raise Fin012S3T03RunnerError("s3_t03_transport_attempt_budget_exceeded")
        if (
            self.state.input_tokens > 60000
            or self.state.output_tokens > 10000
            or total_cost > 0.06
        ):
            raise Fin012S3T03RunnerError("s3_t03_token_or_cost_budget_exceeded")
        if self._clock() - self._started > 900:
            raise Fin012S3T03RunnerError("s3_t03_wall_clock_budget_exceeded")
        return response


def _typed_terminal(
    *,
    status: str,
    phase: str,
    code: str,
    envelope: Mapping[str, Any],
    capture_objects: list[dict[str, Any]],
    budget: _BudgetState,
    local_fact_receipts: list[Mapping[str, Any]] | None = None,
    artifact_count: int = 0,
) -> dict[str, Any]:
    return {
        "schema_version": TERMINAL_SCHEMA,
        "status": status,
        "phase": phase,
        "code": code,
        "execution_identity": envelope["fresh_t03"]["execution_identity"],
        "envelope_digest": envelope["envelope_digest"],
        "capture_objects": deepcopy(capture_objects),
        "capture_count": len(capture_objects),
        "local_fact_receipts": [dict(row) for row in (local_fact_receipts or ())],
        "artifact_count": artifact_count,
        "observed_budget": {
            "provider_calls": budget.call_count,
            "input_tokens": budget.input_tokens,
            "output_tokens": budget.output_tokens,
            "estimated_cost_usd": budget.estimated_cost_usd,
        },
        "failed_output_quarantined": status != "success",
        "business_promotable": status == "success" and artifact_count == 9,
        "credential_value_persisted": False,
        "raw_provider_response_persisted": False,
        "private_reasoning_persisted": False,
    }


def execute_bound_s3_t03(
    *,
    runtime_root: str | Path,
    prepared: S3ThreeCellPreparedExecution,
    admission: S3ThreeCellBoundedAgentAdmission,
    execution_envelope: Mapping[str, Any],
    completion: Callable[..., Mapping[str, Any]],
    object_store_factory: Callable[[Path], FileCanonicalObjectStore] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    runtime = Path(runtime_root).resolve()
    if execution_envelope.get("envelope_digest") != canonical_digest(
        {key: value for key, value in execution_envelope.items() if key != "envelope_digest"}
    ):
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_digest_mismatch")
    if prepared.execution_identity != execution_envelope["fresh_t03"]["execution_identity"]:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_identity_mismatch")
    if prepared.input_digest != execution_envelope["fresh_t03"]["input_digest"]:
        raise Fin012S3T03RunnerError("s3_t03_execution_envelope_input_mismatch")
    if admission.input_digest != prepared.input_digest or not admission.execution_enabled:
        raise Fin012S3T03RunnerError("s3_t03_admission_not_exact_or_enabled")
    if (
        admission.max_provider_calls != 9
        or admission.max_semantic_model_calls != 9
        or admission.max_network_calls != 9
        or admission.max_transport_attempts_per_call != 1
        or admission.retry_budget != 0
        or admission.max_total_cost_usd != 0.06
    ):
        raise Fin012S3T03RunnerError("s3_t03_admission_budget_mismatch")

    _claim_execution_identity(runtime, execution_envelope)
    store = (object_store_factory or FileCanonicalObjectStore)(
        runtime / "restricted-audit-objects"
    )
    started = clock()
    wrapped = _CaptureFirstCompletion(
        completion=completion,
        store=store,
        runtime_root=runtime,
        admission=admission,
        clock=clock,
        started=started,
    )
    local_receipts: list[Mapping[str, Any]] = []
    artifacts: list[Mapping[str, Any]] = []
    terminal: dict[str, Any]
    try:
        executor = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=wrapped,
        )
        output = executor.execute(
            prepared.input_pack,
            admission,
            run_identity={
                "research_run_id": prepared.research_run_id,
                "attempt_id": prepared.attempt_id,
            },
        )
        local_receipts = list(output.execution_observation.get("local_fact_receipts") or ())
        artifacts = [row.model_dump(mode="json") for row in output.artifacts]
        if len(wrapped.capture_objects) != 9 or len(output.provider_output_captures) != 9:
            raise Fin012S3T03RunnerError("s3_t03_success_capture_topology_mismatch")
        if len(local_receipts) != 3 or len(artifacts) != 9:
            raise Fin012S3T03RunnerError("s3_t03_success_artifact_topology_mismatch")
        terminal = _typed_terminal(
            status="success",
            phase="complete",
            code="s3_t03_success_nine_artifacts",
            envelope=execution_envelope,
            capture_objects=wrapped.capture_objects,
            budget=wrapped.state,
            local_fact_receipts=local_receipts,
            artifact_count=len(artifacts),
        )
    except Exception as exc:
        if isinstance(exc, BoundedAgentExecutionError):
            phase = exc.stage
            codes = exc.failure_observation.get("failure_codes") or ()
            code = str(codes[0] if codes else "bounded_agent_execution_failed")
            local_receipts = list(exc.failure_observation.get("local_fact_receipts") or ())
        else:
            phase = "runner_or_transport"
            code = str(getattr(exc, "code", None) or str(exc) or type(exc).__name__)
        terminal = _typed_terminal(
            status="failed",
            phase=phase,
            code=code,
            envelope=execution_envelope,
            capture_objects=wrapped.capture_objects,
            budget=wrapped.state,
            local_fact_receipts=local_receipts,
            artifact_count=0,
        )

    terminal_object: dict[str, Any] | None = None
    try:
        terminal_object = store.put_json(
            terminal,
            namespace=TERMINAL_NAMESPACE,
            artifact_type="s3_t03_typed_terminal_result",
        )
    except Exception:
        terminal_object = None
    result = {
        "schema_version": EXECUTION_RESULT_SCHEMA,
        "status": terminal["status"],
        "terminal": terminal,
        "terminal_object": terminal_object,
        "capture_objects": deepcopy(wrapped.capture_objects),
        "artifacts": artifacts if terminal["status"] == "success" else [],
        "business_promotable": terminal["business_promotable"],
    }
    _atomic_write_json(runtime / "execution-result.json", result)
    _atomic_write_json(
        runtime / "execution-state.json",
        {
            "schema_version": EXECUTION_STATE_SCHEMA,
            "status": "terminal",
            "execution_identity": prepared.execution_identity,
            "envelope_digest": execution_envelope["envelope_digest"],
            "terminal_materialized": True,
            "terminal_status": terminal["status"],
            "terminal_object": terminal_object,
            "credential_value_persisted": False,
            "business_promotable": result["business_promotable"],
        },
    )
    if (runtime / "capture-index.json").exists():
        index = json.loads((runtime / "capture-index.json").read_text(encoding="utf-8"))
        index["terminal_materialized"] = True
        _atomic_write_json(runtime / "capture-index.json", index)
    return result


def finalize_supervisor_exit(
    *,
    runtime_root: str | Path,
    execution_envelope: Mapping[str, Any],
    exit_code: int | None,
    reason: str,
) -> dict[str, Any]:
    """Materialize a fail-closed terminal after an abnormal child exit."""

    runtime = Path(runtime_root).resolve()
    state_path = runtime / "execution-state.json"
    if not state_path.exists():
        raise Fin012S3T03RunnerError("s3_t03_supervisor_state_missing")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("status") == "terminal":
        return json.loads((runtime / "execution-result.json").read_text(encoding="utf-8"))
    index_path = runtime / "capture-index.json"
    indexed_objects: list[dict[str, Any]] = []
    if index_path.exists():
        indexed_objects = json.loads(index_path.read_text(encoding="utf-8")).get(
            "capture_objects", []
        )
    store = FileCanonicalObjectStore(runtime / "restricted-audit-objects")
    capture_by_digest = {str(row["digest"]): dict(row) for row in indexed_objects}
    capture_root = store.root / CAPTURE_NAMESPACE
    if capture_root.exists():
        for path in capture_root.rglob("*.json"):
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            payload = json.loads(data)
            if payload.get("schema_version") != CAPTURE_SCHEMA:
                continue
            capture_by_digest[digest] = {
                "object_key": path.relative_to(store.root).as_posix(),
                "digest": digest,
                "byte_size": len(data),
                "media_type": "application/json",
                "artifact_type": "restricted_provider_interaction_capture",
            }
    verified: list[tuple[int, dict[str, Any]]] = []
    for row in capture_by_digest.values():
        payload = store.get_json(row["object_key"], expected_digest=row["digest"])
        verified.append((int(payload["capture_sequence"]), row))
    verified.sort(key=lambda item: item[0])
    capture_objects = [row for _, row in verified]
    terminal = _typed_terminal(
        status="failed",
        phase="supervisor_exit",
        code="s3_t03_supervisor_exit",
        envelope=execution_envelope,
        capture_objects=list(capture_objects),
        budget=_BudgetState(call_count=len(capture_objects)),
        artifact_count=0,
    )
    terminal["supervisor_exit"] = {
        "exit_code": exit_code,
        "reason": reason,
        "capture_readback_verified": True,
    }
    terminal_object = store.put_json(
        terminal,
        namespace=TERMINAL_NAMESPACE,
        artifact_type="s3_t03_supervisor_exit_terminal",
    )
    result = {
        "schema_version": EXECUTION_RESULT_SCHEMA,
        "status": "failed",
        "terminal": terminal,
        "terminal_object": terminal_object,
        "capture_objects": list(capture_objects),
        "artifacts": [],
        "business_promotable": False,
    }
    _atomic_write_json(runtime / "execution-result.json", result)
    _atomic_write_json(
        state_path,
        {
            **state,
            "status": "terminal",
            "terminal_materialized": True,
            "terminal_status": "failed",
            "terminal_object": terminal_object,
            "business_promotable": False,
        },
    )
    _atomic_write_json(
        index_path,
        {
            "schema_version": CAPTURE_INDEX_SCHEMA,
            "capture_objects": capture_objects,
            "capture_count": len(capture_objects),
            "terminal_materialized": True,
            "business_promotable": False,
        },
    )
    return result
