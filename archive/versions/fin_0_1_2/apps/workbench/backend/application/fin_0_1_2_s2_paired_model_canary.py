from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    read_registered_runtime_json,
)

from .deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from .fin_0_1_2_s2_runtime_contract_binding import (
    FIN_0_1_2_S2_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_S2_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
    load_fin_0_1_2_s2_runtime_contract_binding,
)


S2_MODEL_CANDIDATE_REGISTRY_RESOURCE_ID = (
    "fin_0_1_2.s2.deepseek_model_candidate_registry"
)
S2_PAIRED_CANARY_SCHEMA = (
    "fin_ia_0_1_2_s2_deepseek_model_candidate_registry_v1_0"
)
S2_CANARY_REQUEST_SCHEMA = (
    "fin_ia_0_1_2_s2_paired_model_canary_request_v1_0"
)
S2_CANARY_CAPTURE_SCHEMA = (
    "fin_ia_0_1_2_s2_paired_model_canary_capture_v1_0"
)
S2_CANARY_TERMINAL_SCHEMA = (
    "fin_ia_0_1_2_s2_paired_model_canary_terminal_result_v1_0"
)

FAMILY_SEGMENTS = {
    "specialist_fact_atoms": "facts_explanation_and_terminal",
    "claim_candidate_atoms": "owner_grade_claim_cards",
    "what_would_change_atoms": "actionable_what_would_change_tasks",
}
LOCAL_IDENTITY_OUTPUT_FIELDS = frozenset(
    {
        "program_cell_id",
        "case_ticker",
        "case_id",
        "case_version",
        "research_run_id",
        "attempt_id",
    }
)


class Fin012S2PairedCanaryError(ValueError):
    """Typed zero-call S2 comparator/compiler failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in pairs:
        if key in output:
            raise Fin012S2PairedCanaryError(
                f"s2_paired_canary_duplicate_json_key:{key}"
            )
        output[key] = value
    return output


def _repository_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF).is_file():
            return parent
    raise Fin012S2PairedCanaryError(
        "s2_paired_canary_repository_root_not_found"
    )


def _walk_mapping_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            keys.add(str(key))
            keys.update(_walk_mapping_keys(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            keys.update(_walk_mapping_keys(child))
    return keys


@dataclass(frozen=True)
class S2ModelCandidate:
    candidate_id: str
    model: str
    model_ref: str
    lifecycle: str


@dataclass(frozen=True)
class S2PairedCanaryCall:
    call_id: str
    candidate: S2ModelCandidate
    family_id: str
    segment_id: str
    messages: tuple[Mapping[str, str], ...]
    inference_arguments: Mapping[str, Any]
    model_visible_request_digest: str
    request_equivalence_digest: str

    def safe_payload(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "candidate_id": self.candidate.candidate_id,
            "provider": "deepseek",
            "model": self.candidate.model,
            "model_ref": self.candidate.model_ref,
            "lifecycle": self.candidate.lifecycle,
            "family_id": self.family_id,
            "segment_id": self.segment_id,
            "messages": [dict(row) for row in self.messages],
            "inference_arguments": dict(self.inference_arguments),
            "model_visible_request_digest": (
                self.model_visible_request_digest
            ),
            "request_equivalence_digest": self.request_equivalence_digest,
            "credentials_included": False,
            "business_promotable": False,
        }


class Fin012S2PairedModelCanaryCompiler:
    """Compile and zero-call exercise one fair six-call Flash/Pro matrix.

    Each family receives deterministic local prerequisites. Provider outputs
    never feed another family, and local identity is injected only after the
    raw output has passed the provider-surface check.
    """

    def __init__(
        self,
        *,
        cell_input: Mapping[str, Any],
        as_of: str,
        research_profile_ref: str,
    ) -> None:
        self.cell_input = deepcopy(dict(cell_input))
        self.as_of = str(as_of)
        self.research_profile_ref = str(research_profile_ref).strip()
        if not self.research_profile_ref:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_research_profile_missing"
            )
        self.program_cell_id = str(
            self.cell_input.get("program_cell_id") or ""
        )
        if not self.program_cell_id:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_program_cell_missing"
            )
        self.binding = load_fin_0_1_2_s2_runtime_contract_binding()
        if self.binding.binding_ref != FIN_0_1_2_S2_COMMON_RUNTIME_BINDING_REF:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_runtime_binding_invalid"
            )
        self.registry = self._load_and_validate_candidate_registry()
        self.candidates = tuple(
            S2ModelCandidate(
                candidate_id=str(row["candidate_id"]),
                model=str(row["model"]),
                model_ref=str(row["model_ref"]),
                lifecycle=str(row["lifecycle"]),
            )
            for row in self.registry["candidates"]
        )
        self._compilers = self._compile_isolated_family_inputs()
        self._calls_by_id: dict[str, S2PairedCanaryCall] = {}

    @staticmethod
    def _load_and_validate_candidate_registry() -> dict[str, Any]:
        try:
            registry = read_registered_runtime_json(
                _repository_root(),
                S2_MODEL_CANDIDATE_REGISTRY_RESOURCE_ID,
                registry_ref=FIN_0_1_2_S2_RUNTIME_RESOURCE_REGISTRY_REF,
            )
        except RuntimeResourceRegistryError as exc:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_model_registry_unreadable"
            ) from exc
        return Fin012S2PairedModelCanaryCompiler.validate_candidate_registry(
            registry
        )

    @staticmethod
    def validate_candidate_registry(
        registry: Mapping[str, Any],
    ) -> dict[str, Any]:
        expected_top = {
            "schema_version",
            "registry_id",
            "status",
            "provider_route",
            "candidates",
            "comparison",
        }
        if (
            set(registry) != expected_top
            or registry.get("schema_version") != S2_PAIRED_CANARY_SCHEMA
            or registry.get("status")
            != "paired_canary_candidates_only_no_runtime_mainline_selected"
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_model_registry_shape_invalid"
            )
        route = registry.get("provider_route")
        comparison = registry.get("comparison")
        candidates = registry.get("candidates")
        expected_route_keys = {
            "provider",
            "base_url",
            "wire_api",
            "api_key_env",
            "thinking",
            "reasoning_effort",
            "temperature",
            "stream",
            "timeout_seconds",
            "max_output_tokens_per_call",
            "max_transport_attempts_per_call",
            "retry_budget",
            "fallback_budget",
            "provider_hopping_budget",
        }
        if (
            not isinstance(route, Mapping)
            or set(route) != expected_route_keys
            or route.get("provider") != "deepseek"
            or route.get("base_url") != "https://api.deepseek.com/beta"
            or route.get("wire_api") != "chat_completions_json_object"
            or route.get("api_key_env") != "DEEPSEEK_API_KEY"
            or route.get("thinking") != "disabled"
            or route.get("reasoning_effort") != "none"
            or route.get("temperature") != 0.0
            or route.get("stream") is not False
            or route.get("max_transport_attempts_per_call") != 1
            or any(
                route.get(field) != 0
                for field in (
                    "retry_budget",
                    "fallback_budget",
                    "provider_hopping_budget",
                )
            )
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_provider_route_invalid"
            )
        expected_candidate_keys = {
            "candidate_id",
            "model",
            "model_ref",
            "lifecycle",
            "preferred_when_hard_integrity_and_quality_rule_pass",
            "automatic_runtime_mainline",
        }
        if (
            not isinstance(candidates, list)
            or len(candidates) != 2
            or not all(
                isinstance(row, Mapping)
                and set(row) == expected_candidate_keys
                for row in candidates
            )
            or [
                (
                    row.get("candidate_id"),
                    row.get("model"),
                    row.get("model_ref"),
                    row.get("automatic_runtime_mainline"),
                )
                for row in candidates
            ]
            != [
                (
                    "flash_stable",
                    "deepseek-v4-flash",
                    "deepseek:deepseek-v4-flash",
                    False,
                ),
                (
                    "pro_preview",
                    "deepseek-v4-pro",
                    "deepseek:deepseek-v4-pro",
                    False,
                ),
            ]
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_model_candidates_invalid"
            )
        expected_comparison_keys = {
            "case",
            "program_cell_id",
            "family_ids",
            "primary_call_count",
            "maximum_total_call_count",
            "request_equivalence_exclusions",
            "one_family_output_feeds_another",
            "business_run_or_artifact_writes",
        }
        if (
            not isinstance(comparison, Mapping)
            or set(comparison) != expected_comparison_keys
            or comparison.get("case") != "MU"
            or comparison.get("program_cell_id")
            != "demand_authenticity_and_sustainability"
            or comparison.get("family_ids") != list(FAMILY_SEGMENTS)
            or comparison.get("primary_call_count") != 6
            or comparison.get("maximum_total_call_count") != 8
            or comparison.get("request_equivalence_exclusions")
            != ["candidate_id", "model", "model_ref", "call_id"]
            or comparison.get("one_family_output_feeds_another") is not False
            or comparison.get("business_run_or_artifact_writes") != 0
        ):
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_comparison_contract_invalid"
            )
        return dict(registry)

    def _new_compiler(
        self,
        validated_segments: Mapping[str, Mapping[str, Any]],
    ) -> DeterministicJudgmentAtomCompiledContract:
        return DeterministicJudgmentAtomCompiledContract(
            cell_input=self.cell_input,
            validated_segments=validated_segments,
            as_of=self.as_of,
            contract_ref=(
                FIN_0_1_2_S2_COMMON_RUNTIME_COMPILED_CONTRACT_REF
            ),
            research_profile_ref=self.research_profile_ref,
            runtime_contract_family_binding_ref=self.binding.binding_ref,
            runtime_contract_family_source_digest=self.binding.source_digest,
        )

    @staticmethod
    def _assemble_fake(
        compiler: DeterministicJudgmentAtomCompiledContract,
        segment_id: str,
    ) -> dict[str, Any]:
        output = compiler.fake_provider_output(segment_id)
        encoded = _canonical_bytes(output)
        return compiler.assemble(
            segment_id,
            output,
            provider_output_utf8_bytes=len(encoded),
        )

    def _compile_isolated_family_inputs(
        self,
    ) -> dict[str, DeterministicJudgmentAtomCompiledContract]:
        fact = self._new_compiler({})
        fact_output = self._assemble_fake(
            fact,
            FAMILY_SEGMENTS["specialist_fact_atoms"],
        )
        claim = self._new_compiler(
            {FAMILY_SEGMENTS["specialist_fact_atoms"]: fact_output}
        )
        claim_output = self._assemble_fake(
            claim,
            FAMILY_SEGMENTS["claim_candidate_atoms"],
        )
        wwc = self._new_compiler(
            {
                FAMILY_SEGMENTS["specialist_fact_atoms"]: fact_output,
                FAMILY_SEGMENTS["claim_candidate_atoms"]: claim_output,
            }
        )
        return {
            "specialist_fact_atoms": fact,
            "claim_candidate_atoms": claim,
            "what_would_change_atoms": wwc,
        }

    def provider_wire_schema(self, family_id: str) -> dict[str, Any]:
        compiler = self._compilers[family_id]
        schema = deepcopy(
            compiler.wire_schema(FAMILY_SEGMENTS[family_id])
        )
        if schema.pop("program_cell_id", None) is None:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_local_identity_schema_missing"
            )
        return schema

    def _request_payload(self, family_id: str) -> dict[str, Any]:
        compiler = self._compilers[family_id]
        segment_id = FAMILY_SEGMENTS[family_id]
        surface = compiler.compiled_surface(segment_id)
        surface["wire_schema"] = self.provider_wire_schema(family_id)
        surface["model_visible_contract"].pop("program_cell_id", None)
        surface["model_visible_contract"][
            "program_cell_id_is_local_only"
        ] = True
        surface["model_visible_contract"]["contract_digest"] = _digest(
            {
                key: value
                for key, value in surface["model_visible_contract"].items()
                if key != "contract_digest"
            }
        )
        return {
            "schema_version": S2_CANARY_REQUEST_SCHEMA,
            "node_id": "s2_paired_model_canary",
            "family_id": family_id,
            "segment_id": segment_id,
            "compiled_judgment_atom_contract": surface[
                "model_visible_contract"
            ],
            "required_output_schema": surface["wire_schema"],
            "local_prerequisite_origin": (
                "deterministic_fake_fixture_not_other_model_output"
            ),
            "provider_output_program_cell_id_forbidden": True,
            "local_identity_injection_after_validation": [
                "program_cell_id"
            ],
        }

    def compile_primary_calls(self) -> tuple[S2PairedCanaryCall, ...]:
        route = self.registry["provider_route"]
        calls: list[S2PairedCanaryCall] = []
        self._calls_by_id.clear()
        for family_id, segment_id in FAMILY_SEGMENTS.items():
            payload = self._request_payload(family_id)
            compiler = self._compilers[family_id]
            messages = (
                {
                    "role": "system",
                    "content": (
                        compiler.provider_system_instruction(segment_id)
                        + " Do not return program_cell_id or any other local "
                        "identity field; the local runtime injects it only "
                        "after validation."
                    ),
                },
                {
                    "role": "user",
                    "content": _canonical_bytes(payload).decode("utf-8"),
                },
            )
            visible_digest = _digest([dict(row) for row in messages])
            equivalent_arguments = {
                "temperature": route["temperature"],
                "stream": route["stream"],
                "max_tokens": route["max_output_tokens_per_call"],
                "timeout_seconds": route["timeout_seconds"],
                "thinking": route["thinking"],
                "reasoning_effort": route["reasoning_effort"],
                "wire_api": route["wire_api"],
                "base_url": route["base_url"],
            }
            equivalence_digest = _digest(
                {
                    "messages": [dict(row) for row in messages],
                    "inference_arguments": equivalent_arguments,
                }
            )
            for candidate in self.candidates:
                call = S2PairedCanaryCall(
                    call_id=(
                        "fin012-s2-mu-"
                        f"{family_id}-{candidate.candidate_id}-r1"
                    ),
                    candidate=candidate,
                    family_id=family_id,
                    segment_id=segment_id,
                    messages=messages,
                    inference_arguments={
                        **equivalent_arguments,
                        "model": candidate.model,
                        "model_ref": candidate.model_ref,
                        "api_key_env": route["api_key_env"],
                        "max_transport_attempts": 1,
                        "retry_budget": 0,
                    },
                    model_visible_request_digest=visible_digest,
                    request_equivalence_digest=equivalence_digest,
                )
                calls.append(call)
                self._calls_by_id[call.call_id] = call
        if len(calls) != 6:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_primary_call_count_invalid"
            )
        return tuple(calls)

    def fake_provider_response(
        self,
        call: S2PairedCanaryCall,
    ) -> dict[str, Any]:
        compiler = self._compilers[call.family_id]
        output = deepcopy(compiler.fake_provider_output(call.segment_id))
        output.pop("program_cell_id", None)
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": _canonical_bytes(output).decode("utf-8"),
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            },
            "provider": "deepseek",
            "model": call.candidate.model,
            "latency_ms": 1,
            "transport_attempt_count": 1,
        }

    @staticmethod
    def _content_ref(prefix: str, value: Any) -> str:
        return f"{prefix}:sha256:{_digest(value)}"

    def materialize_response(
        self,
        call: S2PairedCanaryCall,
        response: Mapping[str, Any],
    ) -> dict[str, Any]:
        if self._calls_by_id.get(call.call_id) != call:
            raise Fin012S2PairedCanaryError(
                "s2_paired_canary_call_not_compiled"
            )
        content = response.get("content")
        assistant_text = (
            content
            if isinstance(content, str)
            else _canonical_bytes(content).decode("utf-8")
        )
        request_value = [dict(row) for row in call.messages]
        request_ref = self._content_ref("request_capture", request_value)
        assistant_ref = self._content_ref(
            "assistant_output_capture", assistant_text
        )
        capture = {
            "schema_version": S2_CANARY_CAPTURE_SCHEMA,
            "call_id": call.call_id,
            "candidate_id": call.candidate.candidate_id,
            "family_id": call.family_id,
            "provider": "deepseek",
            "model": call.candidate.model,
            "model_ref": call.candidate.model_ref,
            "model_visible_request": request_value,
            "model_visible_request_digest": (
                call.model_visible_request_digest
            ),
            "assistant_output_text": assistant_text,
            "finish_reason": response.get("finish_reason"),
            "usage": deepcopy(response.get("usage") or {}),
            "latency_ms": response.get("latency_ms"),
            "transport_attempt_count": response.get(
                "transport_attempt_count"
            ),
            "nonsecret_inference_arguments": {
                key: value
                for key, value in call.inference_arguments.items()
                if key != "api_key_env"
            },
            "request_capture_ref": request_ref,
            "assistant_output_capture_ref": assistant_ref,
            "capture_before_local_validation": True,
            "credentials_included": False,
            "private_reasoning_included": False,
            "raw_provider_response_included": False,
            "business_promotable": False,
            "runtime_contract_family_binding": {
                "binding_ref": self.binding.binding_ref,
                "source_digest": self.binding.source_digest,
                "consumer_binding": self.binding.consumer_receipt(
                    "capture_index"
                ),
            },
        }
        capture_ref = self._content_ref("capture", capture)
        phase = "post_provider_local_semantic_validation"
        code: str | None = None
        assembled: dict[str, Any] | None = None
        stop_remaining = False
        try:
            if response.get("status") != "ok":
                phase = "provider_transport"
                stop_remaining = True
                raise Fin012S2PairedCanaryError(
                    "s2_paired_canary_provider_status_invalid"
                )
            if response.get("finish_reason") != "stop":
                phase = "provider_transport"
                stop_remaining = True
                raise Fin012S2PairedCanaryError(
                    "s2_paired_canary_finish_reason_invalid"
                )
            if response.get("transport_attempt_count") != 1:
                phase = "provider_transport"
                stop_remaining = True
                raise Fin012S2PairedCanaryError(
                    "s2_paired_canary_transport_attempt_count_invalid"
                )
            parsed = json.loads(
                assistant_text,
                object_pairs_hook=_strict_object,
            )
            if not isinstance(parsed, dict):
                raise Fin012S2PairedCanaryError(
                    "s2_paired_canary_assistant_object_required"
                )
            forbidden = _walk_mapping_keys(parsed).intersection(
                LOCAL_IDENTITY_OUTPUT_FIELDS
            )
            if forbidden:
                raise Fin012S2PairedCanaryError(
                    "s2_paired_canary_provider_authored_local_identity:"
                    + sorted(forbidden)[0]
                )
            locally_bound = {
                "program_cell_id": self.program_cell_id,
                **parsed,
            }
            compiler = self._compilers[call.family_id]
            assembled = compiler.assemble(
                call.segment_id,
                locally_bound,
                provider_output_utf8_bytes=len(
                    assistant_text.encode("utf-8")
                ),
            )
            compiler.assert_rendered_capacity(
                call.segment_id,
                assembled,
                post_local_expansion_limit_utf8_bytes=(
                    self.binding.budget_contract[
                        "local_rendered_max_utf8_bytes"
                    ]
                ),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            code = getattr(exc, "code", None) or str(exc) or type(exc).__name__
        terminal_base = {
            "schema_version": S2_CANARY_TERMINAL_SCHEMA,
            "call_id": call.call_id,
            "candidate_id": call.candidate.candidate_id,
            "family_id": call.family_id,
            "status": "pass" if code is None else "failed",
            "phase": phase,
            "code": code,
            "request_capture_ref": request_ref,
            "assistant_output_capture_ref": assistant_ref,
            "capture_ref": capture_ref,
            "stdout_ref": self._content_ref("stdout", ""),
            "stderr_ref": self._content_ref("stderr", code or ""),
            "assembled_digest": _digest(assembled) if assembled else None,
            "business_promotable": False,
            "stop_remaining_calls": stop_remaining,
        }
        terminal_ref = self._content_ref("terminal_result", terminal_base)
        terminal = {**terminal_base, "terminal_result_ref": terminal_ref}
        return {
            "status": terminal["status"],
            "capture": capture,
            "capture_ref": capture_ref,
            "terminal_result": terminal,
            "assembled": assembled,
        }

    def run_fake_matrix(
        self,
        *,
        mutate_response: Callable[
            [S2PairedCanaryCall, dict[str, Any]], Mapping[str, Any]
        ]
        | None = None,
    ) -> tuple[dict[str, Any], ...]:
        outcomes: list[dict[str, Any]] = []
        stopped = False
        for call in self.compile_primary_calls():
            if stopped:
                outcomes.append(
                    {
                        "status": "not_started",
                        "call_id": call.call_id,
                        "family_id": call.family_id,
                        "candidate_id": call.candidate.candidate_id,
                        "reason": "prior_transport_auth_security_or_capture_failure",
                        "business_promotable": False,
                    }
                )
                continue
            response = self.fake_provider_response(call)
            if mutate_response is not None:
                response = dict(mutate_response(call, response))
            outcome = self.materialize_response(call, response)
            outcomes.append(outcome)
            stopped = bool(
                outcome["terminal_result"]["stop_remaining_calls"]
            )
        return tuple(outcomes)
