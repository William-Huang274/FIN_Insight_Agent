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
    Fin012S2PairedCanaryError,
    Fin012S2PairedModelCanaryCompiler,
    S2PairedCanaryCall,
)


T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF = (
    "configs/runtime/fin_ia_0_1_2_s2_t03_wwc_replacement_pair_"
    "runtime_resource_registry_v1_0.json"
)
T03_WWC_REPLACEMENT_AUTHORITY_RESOURCE_ID = (
    "fin_0_1_2.s2.t03.wwc_v12_replacement_pair_authority"
)
T03_WWC_REPLACEMENT_MU_FIXTURE_RESOURCE_ID = (
    "fin_0_1_2.s2.t03.wwc_v12_mu_exact_input_fixture"
)
T03_WWC_REPLACEMENT_AUTHORITY_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_wwc_v12_independent_zero_call_proof_and_"
    "replacement_pair_conditional_authority_decision_v1_0"
)
T03_WWC_REPLACEMENT_FIXTURE_SCHEMA = (
    "fin_ia_0_1_2_mu_realistic_three_cell_exact_input_fixture_v1_0"
)
T03_WWC_REPLACEMENT_PREFLIGHT_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_wwc_v12_replacement_pair_zero_call_"
    "preflight_v1_0"
)
T03_WWC_REPLACEMENT_EXECUTION_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_wwc_v12_replacement_pair_exact_execution_"
    "result_v1_0"
)
T03_WWC_REPLACEMENT_FAILURE_TERMINAL_SCHEMA = (
    "fin_ia_0_1_2_s2_t03_wwc_v12_replacement_pair_runner_failure_"
    "terminal_v1_0"
)
T03_WWC_REPLACEMENT_FAMILY = "what_would_change_atoms"
T03_WWC_REPLACEMENT_RESEARCH_PROFILE_REF = (
    "fin01.s4.research_profile.mu_hbm_three_cell:v1"
)
T03_WWC_REPLACEMENT_BINDING_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family_binding:v1.2"
)
T03_WWC_REPLACEMENT_CONTRACT_REF = (
    "fin_0_1_2.common_runtime.judgment_atom_family:v1.2.0"
)
T03_WWC_REPLACEMENT_CAPTURE_NAMESPACE = (
    "fin012/s2/t03/wwc-v12-replacement/provider-interaction-captures"
)
T03_WWC_REPLACEMENT_TERMINAL_NAMESPACE = (
    "fin012/s2/t03/wwc-v12-replacement/terminal-results"
)
T03_WWC_REPLACEMENT_DEFAULT_RUNTIME_ROOT = Path(
    ".codex_runtime/fin012-s2-t03-mu-wwc-v12-replacement-pair-r1"
)

# Frozen experiment-estimation rates. They are governance estimates, not a
# representation of provider billing truth.
T03_WWC_INPUT_USD_PER_MILLION = 0.435
T03_WWC_OUTPUT_USD_PER_MILLION = 0.87


class Fin012S2WWCReplacementPairRunnerError(RuntimeError):
    """Typed, secret-safe replacement-pair runner failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


Completion = Callable[[S2PairedCanaryCall], Mapping[str, Any]]
EventObserver = Callable[[str, S2PairedCanaryCall], None]


class Fin012S2WWCReplacementPairCompiler(
    Fin012S2PairedModelCanaryCompiler
):
    """Authority-ID adapter that leaves the hash-frozen compiler untouched."""

    def compile_family_pair(
        self,
        family_id: str,
        *,
        call_ids_by_candidate: Mapping[str, str],
    ) -> tuple[S2PairedCanaryCall, ...]:
        if family_id != T03_WWC_REPLACEMENT_FAMILY:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_family_pair_unknown"
            )
        expected_candidates = {
            candidate.candidate_id for candidate in self.candidates
        }
        normalized_ids = {
            str(candidate_id): str(call_id).strip()
            for candidate_id, call_id in call_ids_by_candidate.items()
        }
        if (
            set(normalized_ids) != expected_candidates
            or any(not call_id for call_id in normalized_ids.values())
            or len(set(normalized_ids.values())) != len(expected_candidates)
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_family_pair_call_identity_invalid"
            )

        primary = self.compile_primary_calls()
        selected = tuple(
            S2PairedCanaryCall(
                call_id=normalized_ids[call.candidate.candidate_id],
                candidate=call.candidate,
                family_id=call.family_id,
                segment_id=call.segment_id,
                messages=call.messages,
                inference_arguments=call.inference_arguments,
                model_visible_request_digest=call.model_visible_request_digest,
                request_equivalence_digest=call.request_equivalence_digest,
            )
            for call in primary
            if call.family_id == family_id
        )
        if (
            len(selected) != len(expected_candidates)
            or {call.candidate.candidate_id for call in selected}
            != expected_candidates
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_family_pair_count_invalid"
            )
        self._calls_by_id = {call.call_id: call for call in selected}
        return selected


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
        if (parent / T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF).is_file():
            return parent
    raise Fin012S2WWCReplacementPairRunnerError(
        "s2_t03_wwc_replacement_repository_root_not_found"
    )


def _load_bound_inputs(
    repository_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        load_runtime_resource_registry(
            repository_root,
            T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF,
        )
        authority = read_registered_runtime_json(
            repository_root,
            T03_WWC_REPLACEMENT_AUTHORITY_RESOURCE_ID,
            registry_ref=T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF,
        )
        fixture = read_registered_runtime_json(
            repository_root,
            T03_WWC_REPLACEMENT_MU_FIXTURE_RESOURCE_ID,
            registry_ref=T03_WWC_REPLACEMENT_RUNTIME_RESOURCE_REGISTRY_REF,
        )
    except RuntimeResourceRegistryError as exc:
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_registered_input_invalid"
        ) from exc
    authority_state = authority.get("replacement_pair_conditional_authority", {})
    if (
        authority.get("schema_version")
        != T03_WWC_REPLACEMENT_AUTHORITY_SCHEMA
        or authority.get("status")
        != (
            "pass_two_fresh_process_zero_call_proof_replacement_pair_"
            "conditionally_authorized_runner_preflight_pending"
        )
        or authority.get("authority", {}).get(
            "future_replacement_pair_conditionally_authorized"
        )
        is not True
        or authority_state.get("status")
        != "conditional_future_exact_two_call_authority_issued_unconsumed"
        or authority_state.get("automatic_execution_now") is not False
    ):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_authority_invalid"
        )
    if (
        fixture.get("schema_version") != T03_WWC_REPLACEMENT_FIXTURE_SCHEMA
        or fixture.get("fixture_id")
        != "FIN-0.1.2-PRE-S2-MU-REALISTIC-THREE-CELL-EXACT-INPUT-V1"
        or fixture.get("source_input_digest")
        != fixture.get("input_pack", {}).get("input_digest")
    ):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_mu_fixture_invalid"
        )
    return authority, fixture


def build_bound_replacement_pair(
    repository_root: str | Path | None = None,
) -> tuple[
    Fin012S2PairedModelCanaryCompiler,
    tuple[S2PairedCanaryCall, ...],
    dict[str, Any],
]:
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
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_input_compilation_invalid"
        ) from exc
    replacement = authority["replacement_pair_conditional_authority"]
    if (
        input_pack.company != replacement.get("case")
        or input_pack.program_cell_ids[0]
        != replacement.get("program_cell_id")
        or profile_ref != T03_WWC_REPLACEMENT_RESEARCH_PROFILE_REF
        or replacement.get("family") != T03_WWC_REPLACEMENT_FAMILY
        or replacement.get("Fact_or_Claim_rerun") is not False
    ):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_identity_invalid"
        )
    compiler = Fin012S2WWCReplacementPairCompiler(
        cell_input=cell_input,
        as_of=input_pack.as_of,
        research_profile_ref=profile_ref,
    )
    if (
        compiler.binding.binding_ref != T03_WWC_REPLACEMENT_BINDING_REF
        or compiler.binding.compiled_contract_ref
        != T03_WWC_REPLACEMENT_CONTRACT_REF
    ):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_v12_binding_invalid"
        )
    call_plan = replacement.get("call_plan")
    if not isinstance(call_plan, list):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_call_plan_invalid"
        )
    call_ids = {
        str(row.get("candidate_id")): str(row.get("call_id"))
        for row in call_plan
        if isinstance(row, Mapping)
    }
    calls = compiler.compile_family_pair(
        T03_WWC_REPLACEMENT_FAMILY,
        call_ids_by_candidate=call_ids,
    )
    _assert_exact_call_plan(compiler, calls, authority)
    return compiler, calls, authority


def _assert_exact_call_plan(
    compiler: Fin012S2PairedModelCanaryCompiler,
    calls: tuple[S2PairedCanaryCall, ...],
    authority: Mapping[str, Any],
) -> None:
    replacement = authority["replacement_pair_conditional_authority"]
    actual = [
        {
            "call_id": call.call_id,
            "candidate_id": call.candidate.candidate_id,
            "family_id": call.family_id,
            "model": call.candidate.model,
            "model_ref": call.candidate.model_ref,
            "model_visible_request_digest": call.model_visible_request_digest,
            "request_equivalence_digest": call.request_equivalence_digest,
        }
        for call in calls
    ]
    budget = replacement.get("hard_budget", {})
    route = replacement.get("provider_route", {})
    if (
        actual != replacement.get("call_plan")
        or len(calls) != replacement.get("exact_call_count")
        or len(calls) != budget.get("semantic_model_calls")
        or {call.family_id for call in calls}
        != {T03_WWC_REPLACEMENT_FAMILY}
        or replacement.get("Fact_or_Claim_rerun") is not False
        or budget.get("maximum_transport_attempts_per_call") != 1
        or any(
            budget.get(key) != 0
            for key in (
                "retry_budget",
                "fallback_budget",
                "provider_hopping_budget",
                "prompt_only_retry_budget",
                "business_Run_or_Artifact_writes",
            )
        )
        or any(
            call.inference_arguments.get("max_transport_attempts") != 1
            or call.inference_arguments.get("retry_budget") != 0
            or call.inference_arguments.get("base_url") != route.get("base_url")
            or call.inference_arguments.get("wire_api") != route.get("wire_api")
            or call.inference_arguments.get("thinking") != route.get("thinking")
            for call in calls
        )
        or len({call.model_visible_request_digest for call in calls}) != 1
        or len({call.request_equivalence_digest for call in calls}) != 1
        or calls[0].model_visible_request_digest != replacement.get("request_digest")
        or calls[0].request_equivalence_digest
        != replacement.get("equivalence_digest")
        or compiler.program_cell_id != replacement.get("program_cell_id")
    ):
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_exact_call_plan_drift"
        )


def _maximum_cost(authority: Mapping[str, Any]) -> float:
    budget = authority["replacement_pair_conditional_authority"]["hard_budget"]
    return round(
        (
            budget["maximum_input_tokens"] * T03_WWC_INPUT_USD_PER_MILLION
            + budget["maximum_output_tokens"] * T03_WWC_OUTPUT_USD_PER_MILLION
        )
        / 1_000_000,
        9,
    )


def _capture_for_response(
    compiler: Fin012S2PairedModelCanaryCompiler,
    call: S2PairedCanaryCall,
    response: Mapping[str, Any],
) -> dict[str, Any]:
    content = response.get("content")
    assistant_text = (
        content if isinstance(content, str) else _canonical_bytes(content).decode("utf-8")
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
            "consumer_binding": compiler.binding.consumer_receipt("capture_index"),
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
        role="s2_wwc_v12_replacement_pair",
        profile=call.family_id,
        trace_tags={
            "experiment": "FIN-0.1.2-S2-T03-WWC-V1.2-REPLACEMENT",
            "call_id": call.call_id,
            "candidate_id": call.candidate.candidate_id,
        },
        max_transport_attempts=1,
    )


def _claim_execution_identity(runtime_root: Path, execution_identity: str) -> None:
    runtime_root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(runtime_root, 0o700)
    except OSError:
        pass
    state = runtime_root / "execution-state.json"
    try:
        descriptor = os.open(state, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_execution_identity_already_claimed"
        ) from exc
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(
            _canonical_bytes(
                {
                    "schema_version": T03_WWC_REPLACEMENT_EXECUTION_SCHEMA,
                    "status": "execution_claimed",
                    "execution_identity": execution_identity,
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


def execute_exact_replacement_pair(
    *,
    runtime_root: str | Path = T03_WWC_REPLACEMENT_DEFAULT_RUNTIME_ROOT,
    repository_root: str | Path | None = None,
    completion: Completion | None = None,
    live_execution_authorized: bool = False,
    object_store_factory: Callable[[Path], FileCanonicalObjectStore] | None = None,
    event_observer: EventObserver | None = None,
) -> dict[str, Any]:
    if completion is None and not live_execution_authorized:
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_live_execution_not_authorized"
        )
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    runtime = Path(runtime_root).resolve()
    compiler, calls, authority = build_bound_replacement_pair(root)
    replacement = authority["replacement_pair_conditional_authority"]
    _claim_execution_identity(runtime, str(replacement["execution_identity"]))
    store_factory = object_store_factory or FileCanonicalObjectStore
    store = store_factory(runtime / "restricted-audit-objects")
    complete = completion or _default_completion
    outcomes: list[dict[str, Any]] = []
    budget_state = _BudgetState()
    stopped = False
    started_calls = 0
    started = time.monotonic()
    budget = replacement["hard_budget"]

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
            started_calls += 1
            response = _normalized_gateway_response(complete(call))
            capture = _capture_for_response(compiler, call, response)
            capture_object = store.put_json(
                capture,
                namespace=T03_WWC_REPLACEMENT_CAPTURE_NAMESPACE,
                artifact_type="restricted_provider_interaction_capture",
            )
            if capture_object["digest"] != _digest(capture):
                raise Fin012S2WWCReplacementPairRunnerError(
                    "s2_t03_wwc_replacement_capture_digest_mismatch"
                )
            if event_observer is not None:
                event_observer("capture_persisted", call)
            budget_state = budget_state.add(response)
            if (
                budget_state.input_tokens > budget["maximum_input_tokens"]
                or budget_state.output_tokens > budget["maximum_output_tokens"]
                or time.monotonic() - started > budget["maximum_wall_clock_seconds"]
            ):
                raise Fin012S2WWCReplacementPairRunnerError(
                    "s2_t03_wwc_replacement_runtime_budget_exceeded"
                )
            if event_observer is not None:
                event_observer("local_validation_started", call)
            materialized = compiler.materialize_response(call, response)
            if materialized["capture"] != capture:
                raise Fin012S2WWCReplacementPairRunnerError(
                    "s2_t03_wwc_replacement_capture_compiler_parity_drift"
                )
            terminal_object = store.put_json(
                materialized["terminal_result"],
                namespace=T03_WWC_REPLACEMENT_TERMINAL_NAMESPACE,
                artifact_type="wwc_replacement_pair_terminal_result",
            )
            if event_observer is not None:
                event_observer("terminal_persisted", call)
            outcomes.append(
                {
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
            )
            stopped = bool(materialized["terminal_result"]["stop_remaining_calls"])
        except Exception as exc:
            code = getattr(exc, "code", None) or type(exc).__name__
            failure_terminal = {
                "schema_version": T03_WWC_REPLACEMENT_FAILURE_TERMINAL_SCHEMA,
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
                    namespace=T03_WWC_REPLACEMENT_TERMINAL_NAMESPACE,
                    artifact_type="wwc_replacement_pair_runner_failure_terminal",
                )
            except Exception:
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
        "schema_version": T03_WWC_REPLACEMENT_EXECUTION_SCHEMA,
        "status": (
            "completed_two_terminal_results"
            if len([row for row in outcomes if row["status"] != "not_started"]) == 2
            else "stopped_fail_closed_before_two_terminal_results"
        ),
        "authority_decision_id": authority["decision_id"],
        "replacement_authority_id": replacement["authority_id"],
        "execution_identity": replacement["execution_identity"],
        "outcomes": outcomes,
        "observed_counts": {
            "started_model_calls": started_calls,
            "business_Run_or_Artifact_writes": 0,
            "Fact_or_Claim_calls": 0,
            "input_tokens": budget_state.input_tokens,
            "output_tokens": budget_state.output_tokens,
        },
        "credential_value_persisted": False,
        "raw_provider_response_persisted": False,
        "business_promotable": False,
    }
    _atomic_write_json(runtime / "execution-result.json", result)
    return result


def run_zero_call_preflight(
    repository_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve() if repository_root else _repository_root()
    compiler, calls, authority = build_bound_replacement_pair(root)
    replacement = authority["replacement_pair_conditional_authority"]
    projected_cost = _maximum_cost(authority)
    if projected_cost > replacement["hard_budget"]["maximum_total_cost_usd"]:
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_projected_cost_exceeds_authority"
        )
    canonical_state = (
        root / T03_WWC_REPLACEMENT_DEFAULT_RUNTIME_ROOT / "execution-state.json"
    )
    if canonical_state.exists():
        raise Fin012S2WWCReplacementPairRunnerError(
            "s2_t03_wwc_replacement_execution_identity_already_claimed"
        )

    def fake_completion(call: S2PairedCanaryCall) -> Mapping[str, Any]:
        return compiler.fake_provider_response(call)

    events: list[str] = []

    def observe(event: str, call: S2PairedCanaryCall) -> None:
        events.append(f"{event}:{call.call_id}")

    with tempfile.TemporaryDirectory(prefix="fin012-s2-t03-wwc-pair-preflight-") as tmp:
        temp_root = Path(tmp)
        store = FileCanonicalObjectStore(temp_root / "atomic-probe")
        probe = {
            "schema_version": "fin_ia_atomic_capture_preflight_probe_v1",
            "call_count": len(calls),
            "contains_provider_output": False,
        }
        probe_ref = store.put_json(
            probe,
            namespace="fin012/s2/t03/wwc-v12-replacement/preflight-probe",
            artifact_type="atomic_capture_preflight_probe",
        )
        if store.get_json(
            probe_ref["object_key"], expected_digest=probe_ref["digest"]
        ) != probe:
            raise Fin012S2WWCReplacementPairRunnerError(
                "s2_t03_wwc_replacement_atomic_roundtrip_failed"
            )

        happy_root = temp_root / "happy"
        happy = execute_exact_replacement_pair(
            runtime_root=happy_root,
            repository_root=root,
            completion=fake_completion,
            event_observer=observe,
        )
        expected_events: list[str] = []
        for call in calls:
            expected_events.extend(
                [
                    f"capture_persisted:{call.call_id}",
                    f"local_validation_started:{call.call_id}",
                    f"terminal_persisted:{call.call_id}",
                ]
            )
        if (
            happy["status"] != "completed_two_terminal_results"
            or [row["status"] for row in happy["outcomes"]] != ["pass", "pass"]
            or events != expected_events
        ):
            raise Fin012S2WWCReplacementPairRunnerError(
                "s2_t03_wwc_replacement_happy_fake_preflight_failed"
            )
        try:
            execute_exact_replacement_pair(
                runtime_root=happy_root,
                repository_root=root,
                completion=fake_completion,
            )
        except Fin012S2WWCReplacementPairRunnerError as exc:
            if exc.code != (
                "s2_t03_wwc_replacement_execution_identity_already_claimed"
            ):
                raise
        else:
            raise Fin012S2WWCReplacementPairRunnerError(
                "s2_t03_wwc_replacement_identity_reuse_not_blocked"
            )

        semantic_calls: list[str] = []

        def semantic_failure(call: S2PairedCanaryCall) -> Mapping[str, Any]:
            semantic_calls.append(call.call_id)
            response = deepcopy(compiler.fake_provider_response(call))
            if len(semantic_calls) == 1:
                response["content"] = "{}"
            return response

        semantic = execute_exact_replacement_pair(
            runtime_root=temp_root / "semantic",
            repository_root=root,
            completion=semantic_failure,
        )
        if (
            len(semantic_calls) != 2
            or [row["status"] for row in semantic["outcomes"]]
            != ["failed", "pass"]
        ):
            raise Fin012S2WWCReplacementPairRunnerError(
                "s2_t03_wwc_replacement_semantic_continue_preflight_failed"
            )

        transport_calls: list[str] = []

        def transport_failure(call: S2PairedCanaryCall) -> Mapping[str, Any]:
            transport_calls.append(call.call_id)
            response = deepcopy(compiler.fake_provider_response(call))
            response.update(status="provider_error", finish_reason=None)
            return response

        transport = execute_exact_replacement_pair(
            runtime_root=temp_root / "transport",
            repository_root=root,
            completion=transport_failure,
        )
        if (
            len(transport_calls) != 1
            or [row["status"] for row in transport["outcomes"]]
            != ["failed", "not_started"]
            or transport["outcomes"][0].get("capture_object") is None
        ):
            raise Fin012S2WWCReplacementPairRunnerError(
                "s2_t03_wwc_replacement_transport_stop_preflight_failed"
            )

    return {
        "schema_version": T03_WWC_REPLACEMENT_PREFLIGHT_SCHEMA,
        "status": (
            "pass_zero_call_exact_two_call_runner_atomic_capture_terminal_"
            "budget_identity_and_stop_rule_preflight"
        ),
        "authority_decision_id": authority["decision_id"],
        "replacement_authority_id": replacement["authority_id"],
        "execution_identity": replacement["execution_identity"],
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
            "base_url": replacement["provider_route"]["base_url"],
            "wire_api": replacement["provider_route"]["wire_api"],
            "thinking": "disabled",
            "maximum_transport_attempts_per_call": 1,
        },
        "capture_contract": {
            "atomic_content_addressed_write_and_readback_proved": True,
            "capture_before_local_validation_proved": True,
            "terminal_result_persistence_proved": True,
            "credentials_headers_cookies_private_reasoning_excluded": True,
            "business_promotable": False,
        },
        "fake_execution_proofs": {
            "happy_pair_statuses": ["pass", "pass"],
            "semantic_failure_continues_pair": True,
            "transport_failure_stops_pair": True,
            "execution_identity_reuse_fails_closed": True,
            "Fact_or_Claim_calls": 0,
        },
        "budget": {
            "projected_worst_case_cost_usd": projected_cost,
            "authorized_maximum_cost_usd": replacement["hard_budget"][
                "maximum_total_cost_usd"
            ],
            "replacement_pair_calls": 2,
            "Fact_or_Claim_calls": 0,
        },
        "fresh_canonical_execution_identity_unclaimed": True,
        "credential_checked": False,
        "credential_reads": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "business_Run_or_Artifact_writes": 0,
        "next_action": (
            "FIN-0.1.2-S2-T03-MU-WWC-V1.2-FLASH-STABLE-VS-PRO-"
            "PREVIEW-REPLACEMENT-PAIR-EXACT-EXECUTION"
        ),
    }
