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

from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    load_runtime_resource_registry,
    read_registered_runtime_json,
)

from .bounded_agent_contract_policies import (
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
)
from .bounded_agent_executor import (
    S3ThreeCellBoundedAgentExecutor,
    S3ThreeCellBoundedAgentInputPack,
)
from .fin_0_1_2_s2_paired_model_canary import (
    S2_CANARY_CAPTURE_SCHEMA,
    Fin012S2PairedModelCanaryCompiler,
    S2PairedCanaryCall,
)


T03_RUNTIME_RESOURCE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s2_t03_runtime_resource_registry_v1_0.json"
)
T03_AUTHORITY_RESOURCE_ID = "fin_0_1_2.s2.t03.paired_canary_authority"
T03_MU_FIXTURE_RESOURCE_ID = "fin_0_1_2.s2.t03.mu_exact_input_fixture"
T03_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_mu_three_family_flash_stable_vs_pro_preview_"
    "paired_natural_output_canary_authority_decision_v1_0"
)
T03_FIXTURE_SCHEMA = (
    "fin_ia_0_1_2_mu_realistic_three_cell_exact_input_fixture_v1_0"
)
T03_PREFLIGHT_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_paired_canary_zero_call_preflight_v1_0"
)
T03_EXECUTION_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_paired_canary_exact_execution_result_v1_0"
)
T03_RUNNER_FAILURE_TERMINAL_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_paired_canary_runner_failure_terminal_v1_0"
)
T03_RESEARCH_PROFILE_REF = "fin01.s4.research_profile.mu_hbm_three_cell:v1"
T03_CAPTURE_NAMESPACE = "fin012/s2/t03/provider-interaction-captures"
T03_TERMINAL_NAMESPACE = "fin012/s2/t03/terminal-results"
T03_DEFAULT_RUNTIME_ROOT = Path(
    ".codex_runtime/fin012-s2-t03-mu-flash-pro-paired-r1"
)

# Frozen experiment-estimation rates. They are governance estimates, not a
# representation of provider billing truth.
T03_INPUT_CACHE_MISS_USD_PER_MILLION = 0.435
T03_OUTPUT_USD_PER_MILLION = 0.87


class Fin012S2PairedCanaryRunnerError(RuntimeError):
    """Typed, secret-safe T03 runner failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


Completion = Callable[[S2PairedCanaryCall], Mapping[str, Any]]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _content_ref(prefix: str, value: Any) -> str:
    return f"{prefix}:sha256:{_digest(value)}"


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / T03_RUNTIME_RESOURCE_REGISTRY_REF).is_file():
            return parent
    raise Fin012S2PairedCanaryRunnerError(
        "s2_t03_runner_repository_root_not_found"
    )


def _load_bound_inputs(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        load_runtime_resource_registry(
            repository_root,
            T03_RUNTIME_RESOURCE_REGISTRY_REF,
        )
        authority = read_registered_runtime_json(
            repository_root,
            T03_AUTHORITY_RESOURCE_ID,
            registry_ref=T03_RUNTIME_RESOURCE_REGISTRY_REF,
        )
        fixture = read_registered_runtime_json(
            repository_root,
            T03_MU_FIXTURE_RESOURCE_ID,
            registry_ref=T03_RUNTIME_RESOURCE_REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_registered_runtime_input_invalid"
        ) from exc
    if (
        authority.get("schema_version") != T03_AUTHORITY_SCHEMA
        or authority.get("status")
        != "pass_conditional_exact_six_call_authority_issued_preflight_pending"
        or authority.get("authority", {}).get(
            "future_exact_six_call_canary_authorized"
        )
        is not True
    ):
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_authority_not_effective_for_preflight"
        )
    if (
        fixture.get("schema_version") != T03_FIXTURE_SCHEMA
        or fixture.get("fixture_id")
        != "FIN-0.1.2-PRE-S2-MU-REALISTIC-THREE-CELL-EXACT-INPUT-V1"
        or fixture.get("source_input_digest")
        != fixture.get("input_pack", {}).get("input_digest")
    ):
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_mu_exact_input_fixture_invalid"
        )
    return authority, fixture


def build_bound_compiler(
    repository_root: str | Path | None = None,
) -> tuple[Fin012S2PairedModelCanaryCompiler, dict[str, Any]]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    authority, fixture = _load_bound_inputs(root)
    try:
        input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(
            fixture["input_pack"]
        )
        cell_input = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            input_pack.cell_inputs[0],
            policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
        )
        profile_ref = str(
            input_pack.s4_case_runtime["binding"]["research_profile_ref"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_mu_exact_input_compilation_invalid"
        ) from exc
    if (
        input_pack.company != "MU"
        or input_pack.program_cell_ids[0]
        != "demand_authenticity_and_sustainability"
        or profile_ref != T03_RESEARCH_PROFILE_REF
    ):
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_mu_exact_input_identity_invalid"
        )
    compiler = Fin012S2PairedModelCanaryCompiler(
        cell_input=cell_input,
        as_of=input_pack.as_of,
        research_profile_ref=profile_ref,
    )
    return compiler, authority


def _assert_exact_call_plan(
    compiler: Fin012S2PairedModelCanaryCompiler,
    authority: Mapping[str, Any],
) -> tuple[S2PairedCanaryCall, ...]:
    calls = compiler.compile_primary_calls()
    expected = authority.get("exact_canary", {}).get("call_plan")
    actual = [
        {
            "call_id": call.call_id,
            "family_id": call.family_id,
            "candidate_id": call.candidate.candidate_id,
            "model_ref": call.candidate.model_ref,
            "model_visible_request_digest": call.model_visible_request_digest,
            "request_equivalence_digest": call.request_equivalence_digest,
        }
        for call in calls
    ]
    if actual != expected:
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_exact_call_plan_digest_drift"
        )
    budget = authority.get("hard_budget", {})
    if (
        len(calls) != budget.get("primary_semantic_model_calls")
        or budget.get("maximum_transport_attempts_per_call") != 1
        or any(
            budget.get(key) != 0
            for key in (
                "retry_budget",
                "fallback_budget",
                "provider_hopping_budget",
                "prompt_only_retry_budget",
                "canonical_business_Run_or_Artifact_writes",
            )
        )
        or any(
            call.inference_arguments.get("max_transport_attempts") != 1
            or call.inference_arguments.get("retry_budget") != 0
            for call in calls
        )
    ):
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_exact_call_budget_invalid"
        )
    return calls


def _maximum_primary_cost(authority: Mapping[str, Any]) -> float:
    budget = authority["hard_budget"]
    return round(
        (
            budget["maximum_input_tokens_primary"]
            * T03_INPUT_CACHE_MISS_USD_PER_MILLION
            + budget["maximum_output_tokens_primary"]
            * T03_OUTPUT_USD_PER_MILLION
        )
        / 1_000_000,
        9,
    )


def run_zero_call_preflight(
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    compiler, authority = build_bound_compiler(root)
    calls = _assert_exact_call_plan(compiler, authority)
    projected_cost = _maximum_primary_cost(authority)
    if projected_cost > authority["hard_budget"]["maximum_total_cost_usd_primary"]:
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_projected_primary_cost_exceeds_authority"
        )
    with tempfile.TemporaryDirectory(prefix="fin012-s2-t03-preflight-") as tmp:
        store = FileCanonicalObjectStore(Path(tmp) / "objects")
        probe = {
            "schema_version": "fin_ia_atomic_capture_preflight_probe_v1",
            "call_count": len(calls),
            "contains_provider_output": False,
        }
        ref = store.put_json(
            probe,
            namespace="fin012/s2/t03/preflight-probe",
            artifact_type="atomic_capture_preflight_probe",
        )
        if store.get_json(
            ref["object_key"], expected_digest=ref["digest"]
        ) != probe:
            raise Fin012S2PairedCanaryRunnerError(
                "s2_t03_atomic_capture_roundtrip_failed"
            )
    return {
        "schema_version": T03_PREFLIGHT_SCHEMA,
        "status": "pass_zero_call_bound_runner_and_atomic_capture_preflight",
        "authority_decision_id": authority["decision_id"],
        "exact_call_count": len(calls),
        "exact_calls": [
            {
                "call_id": call.call_id,
                "family_id": call.family_id,
                "candidate_id": call.candidate.candidate_id,
                "model_ref": call.candidate.model_ref,
                "model_visible_request_digest": call.model_visible_request_digest,
                "request_equivalence_digest": call.request_equivalence_digest,
            }
            for call in calls
        ],
        "route": {
            "provider": "deepseek",
            "base_url": authority["exact_canary"]["base_url"],
            "wire_api": authority["exact_canary"]["wire_api"],
            "thinking": "disabled",
            "maximum_transport_attempts_per_call": 1,
        },
        "capture_contract": {
            "atomic_content_addressed_write_proved": True,
            "capture_before_local_validation_required": True,
            "terminal_result_persistence_required": True,
            "credentials_headers_cookies_private_reasoning_excluded": True,
            "business_promotable": False,
        },
        "budget": {
            "projected_worst_case_primary_cost_usd": projected_cost,
            "authorized_maximum_primary_cost_usd": authority["hard_budget"][
                "maximum_total_cost_usd_primary"
            ],
            "primary_calls": 6,
            "replacement_pair_calls_authorized": 0,
        },
        "credential_checked": False,
        "credential_reads": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_Run_or_Artifact_writes": 0,
        "next_action": (
            "FIN-0.1.2-S2-T03-MU-FLASH-STABLE-VS-PRO-PREVIEW-PAIRED-"
            "NATURAL-OUTPUT-CANARY-EXACT-SIX-CALL-EXECUTION"
        ),
    }


def _capture_for_response(
    compiler: Fin012S2PairedModelCanaryCompiler,
    call: S2PairedCanaryCall,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    content = response.get("content")
    assistant_text = (
        content
        if isinstance(content, str)
        else _canonical_bytes(content).decode("utf-8")
    )
    request_value = [dict(row) for row in call.messages]
    return {
        "schema_version": S2_CANARY_CAPTURE_SCHEMA,
        "call_id": call.call_id,
        "candidate_id": call.candidate.candidate_id,
        "family_id": call.family_id,
        "provider": "deepseek",
        "model": call.candidate.model,
        "model_ref": call.candidate.model_ref,
        "model_visible_request": request_value,
        "model_visible_request_digest": call.model_visible_request_digest,
        "assistant_output_text": assistant_text,
        "finish_reason": response.get("finish_reason"),
        "usage": deepcopy(response.get("usage") or {}),
        "latency_ms": response.get("latency_ms"),
        "transport_attempt_count": response.get("transport_attempt_count"),
        "nonsecret_inference_arguments": {
            key: value
            for key, value in call.inference_arguments.items()
            if key != "api_key_env"
        },
        "request_capture_ref": _content_ref("request_capture", request_value),
        "assistant_output_capture_ref": _content_ref(
            "assistant_output_capture", assistant_text
        ),
        "capture_before_local_validation": True,
        "credentials_included": False,
        "private_reasoning_included": False,
        "raw_provider_response_included": False,
        "business_promotable": False,
        "runtime_contract_family_binding": {
            "binding_ref": compiler.binding.binding_ref,
            "source_digest": compiler.binding.source_digest,
            "consumer_binding": compiler.binding.consumer_receipt(
                "capture_index"
            ),
        },
    }


def _normalized_gateway_response(response: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(response)
    if not isinstance(normalized.get("usage"), Mapping):
        normalized["usage"] = {
            "input_tokens": int(normalized.get("input_tokens") or 0),
            "output_tokens": int(normalized.get("output_tokens") or 0),
            "total_tokens": int(normalized.get("total_tokens") or 0),
        }
    return normalized


def _default_completion(call: S2PairedCanaryCall) -> Mapping[str, Any]:
    from sec_agent.llm_gateway import chat_completion

    args = call.inference_arguments
    return chat_completion(
        llm_backend="deepseek",
        base_url=str(args["base_url"]),
        chat_completions_path="/chat/completions",
        model=call.candidate.model,
        messages=[dict(row) for row in call.messages],
        response_format={"type": "json_object"},
        api_key_env=str(args["api_key_env"]),
        temperature=float(args["temperature"]),
        max_tokens=int(args["max_tokens"]),
        timeout_s=int(args["timeout_seconds"]),
        stream=bool(args["stream"]),
        enable_thinking=False,
        reasoning_effort="",
        role="s2_paired_model_canary",
        profile=call.family_id,
        trace_tags={
            "experiment": "FIN-0.1.2-S2-T03",
            "call_id": call.call_id,
            "candidate_id": call.candidate.candidate_id,
        },
        max_transport_attempts=1,
    )


def _claim_execution_identity(runtime_root: Path) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(runtime_root, 0o700)
    except OSError:
        pass
    state = runtime_root / "execution-state.json"
    try:
        descriptor = os.open(
            state,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
    except FileExistsError as exc:
        raise Fin012S2PairedCanaryRunnerError(
            "s2_t03_execution_identity_already_claimed"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(
            _canonical_bytes(
                {
                    "schema_version": T03_EXECUTION_SCHEMA,
                    "status": "execution_claimed",
                    "credential_value_persisted": False,
                    "business_promotable": False,
                }
            )
        )
        handle.flush()
        os.fsync(handle.fileno())


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            handle.write(_canonical_bytes(payload))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


@dataclass(frozen=True)
class _BudgetState:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, response: Mapping[str, Any]) -> "_BudgetState":
        usage = response.get("usage") or {}
        return _BudgetState(
            input_tokens=self.input_tokens + int(usage.get("input_tokens") or 0),
            output_tokens=self.output_tokens + int(usage.get("output_tokens") or 0),
        )


def execute_exact_six_call_canary(
    *,
    runtime_root: str | Path = T03_DEFAULT_RUNTIME_ROOT,
    repository_root: str | Path | None = None,
    completion: Completion | None = None,
    object_store_factory: Callable[[Path], FileCanonicalObjectStore]
    | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    runtime = Path(runtime_root).resolve()
    compiler, authority = build_bound_compiler(root)
    calls = _assert_exact_call_plan(compiler, authority)
    _claim_execution_identity(runtime)
    store_factory = object_store_factory or FileCanonicalObjectStore
    store = store_factory(runtime / "restricted-audit-objects")
    complete = completion or _default_completion
    outcomes: list[dict[str, Any]] = []
    budget_state = _BudgetState()
    stopped = False
    started = time.monotonic()

    for call in calls:
        if stopped:
            outcomes.append(
                {
                    "call_id": call.call_id,
                    "family_id": call.family_id,
                    "candidate_id": call.candidate.candidate_id,
                    "status": "not_started",
                    "reason": (
                        "prior_transport_auth_security_capture_or_budget_failure"
                    ),
                    "business_promotable": False,
                }
            )
            continue
        capture_object: dict[str, Any] | None = None
        try:
            response = _normalized_gateway_response(complete(call))
            capture = _capture_for_response(compiler, call, response)
            capture_object = store.put_json(
                capture,
                namespace=T03_CAPTURE_NAMESPACE,
                artifact_type="restricted_provider_interaction_capture",
            )
            if capture_object["digest"] != _digest(capture):
                raise Fin012S2PairedCanaryRunnerError(
                    "s2_t03_persisted_capture_digest_mismatch"
                )
            materialized = compiler.materialize_response(call, response)
            if materialized["capture"] != capture:
                raise Fin012S2PairedCanaryRunnerError(
                    "s2_t03_capture_compiler_parity_drift"
                )
            budget_state = budget_state.add(response)
            budget = authority["hard_budget"]
            usage = response["usage"]
            if (
                int(usage.get("output_tokens") or 0)
                > budget["maximum_output_tokens_per_call"]
                or budget_state.input_tokens
                > budget["maximum_input_tokens_primary"]
                or budget_state.output_tokens
                > budget["maximum_output_tokens_primary"]
                or time.monotonic() - started
                > budget["maximum_wall_clock_seconds_primary"]
            ):
                raise Fin012S2PairedCanaryRunnerError(
                    "s2_t03_runtime_budget_exceeded"
                )
            terminal_object = store.put_json(
                materialized["terminal_result"],
                namespace=T03_TERMINAL_NAMESPACE,
                artifact_type="paired_canary_terminal_result",
            )
            outcome = {
                "call_id": call.call_id,
                "family_id": call.family_id,
                "candidate_id": call.candidate.candidate_id,
                "status": materialized["status"],
                "phase": materialized["terminal_result"]["phase"],
                "code": materialized["terminal_result"]["code"],
                "capture_object": capture_object,
                "terminal_object": terminal_object,
                "usage": deepcopy(response["usage"]),
                "finish_reason": response.get("finish_reason"),
                "latency_ms": response.get("latency_ms"),
                "transport_attempt_count": response.get(
                    "transport_attempt_count"
                ),
                "business_promotable": False,
            }
            outcomes.append(outcome)
            stopped = bool(
                materialized["terminal_result"]["stop_remaining_calls"]
            )
        except Exception as exc:
            code = getattr(exc, "code", None) or type(exc).__name__
            failure_terminal = {
                "schema_version": T03_RUNNER_FAILURE_TERMINAL_SCHEMA,
                "call_id": call.call_id,
                "candidate_id": call.candidate.candidate_id,
                "family_id": call.family_id,
                "status": "runner_failed",
                "phase": "capture_or_runner_budget",
                "code": str(code),
                "capture_object_digest": (
                    capture_object["digest"] if capture_object else None
                ),
                "business_promotable": False,
                "stop_remaining_calls": True,
            }
            terminal_object: dict[str, Any] | None = None
            try:
                terminal_object = store.put_json(
                    failure_terminal,
                    namespace=T03_TERMINAL_NAMESPACE,
                    artifact_type="paired_canary_runner_failure_terminal",
                )
            except Exception:
                # A capture-store failure can also make its terminal namespace
                # unavailable. The sanitized atomic execution result remains
                # the final fail-closed receipt without echoing provider text.
                terminal_object = None
            outcomes.append(
                {
                    **{
                        key: value
                        for key, value in failure_terminal.items()
                        if key != "schema_version"
                    },
                    "capture_object": capture_object,
                    "terminal_object": terminal_object,
                }
            )
            stopped = True

    result = {
        "schema_version": T03_EXECUTION_SCHEMA,
        "status": (
            "completed_six_terminal_results"
            if len([row for row in outcomes if row["status"] != "not_started"])
            == 6
            else "stopped_fail_closed_before_six_terminal_results"
        ),
        "authority_decision_id": authority["decision_id"],
        "outcomes": outcomes,
        "observed_counts": {
            "started_model_calls": len(
                [row for row in outcomes if row["status"] != "not_started"]
            ),
            "business_Run_or_Artifact_writes": 0,
            "replacement_pair_calls": 0,
            "input_tokens": budget_state.input_tokens,
            "output_tokens": budget_state.output_tokens,
        },
        "credential_value_persisted": False,
        "raw_provider_response_persisted": False,
        "business_promotable": False,
    }
    _atomic_write_json(runtime / "execution-result.json", result)
    return result
