from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

AUTHORITY_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_authority_decision_v1_0.json"
)
RESULT_PATH = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_exact_once_execution_result_v1_0.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "7789999fb9e00f353a00337ece72361d0a30fcdec5d239068e1695da83b79446"
)
CANARY_ID = "fin01-s4-t06-entry-openai-strict-schema-dell-demand-r1"
RESULT_SCHEMA_VERSION = (
    "fin_ia_0_1_s4_t06_entry_shared_runtime_blocker_"
    "single_node_strict_schema_canary_exact_once_execution_result_v1_0"
)
WORK_ITEM_ID = (
    "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-SINGLE-NODE-"
    "STRICT-SCHEMA-CANARY-EXACT-ONCE-EXECUTION"
)
EXPECTED_NEXT_ACTION = WORK_ITEM_ID
SUCCESS_NEXT_ACTION = (
    "S4-T06-ENTRY-SHARED-RUNTIME-BLOCKER-POST-CANARY-"
    "PROGRAM-DISPOSITION-DECISION"
)
INPUT_USD_PER_MILLION = 5.0
CACHED_INPUT_USD_PER_MILLION = 0.5
OUTPUT_USD_PER_MILLION = 30.0


def _canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_repo_api_key_if_needed() -> bool:
    current = os.environ.get("OPENAI_API_KEY", "")
    if re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", current):
        return True
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(
                r"""^\s*OPENAI_API_KEY\s*=\s*(?:"([^"]+)"|'([^']+)'|([^\s#]+))\s*(?:#.*)?$""",
                line,
            )
            if not match:
                continue
            value = next(
                (item for item in match.groups() if item is not None),
                "",
            )
            if re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", value):
                os.environ["OPENAI_API_KEY"] = value
                return True
    return False


def _derive_exact_request() -> tuple[dict[str, Any], Any]:
    from apps.workbench.backend.application.bounded_agent_contract_policies import (
        StrictTruthKernelPolicy,
    )
    from apps.workbench.backend.application.bounded_agent_executor import (
        S3ThreeCellBoundedAgentExecutor,
        build_s3_three_cell_bounded_agent_executor_for_admission,
    )
    from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
        _shared_local_id_specialists,
    )
    from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
        _NumericIdentitySafeFake,
    )
    from test_fin_0_1_s4_t06_entry_shared_runtime_blocker_minimum_zero_call_implementation import (
        _OpenAIChatFake,
        _StrictResponsesFake,
        _case_fixture_input_and_admission,
        _strict_admission,
    )

    input_pack, source_admission = _case_fixture_input_and_admission("DELL")
    admission = _strict_admission(input_pack, source_admission)
    _, specialist_source = _shared_local_id_specialists()
    specialists = {
        cell_id: deepcopy(specialist)
        for cell_id, specialist in specialist_source.items()
    }
    chat = _OpenAIChatFake(_NumericIdentitySafeFake(input_pack, specialists))
    strict_fake = _StrictResponsesFake()
    captured: list[Mapping[str, Any]] = []

    def responses(**kwargs: Any) -> Mapping[str, Any]:
        captured.append(deepcopy(kwargs))
        return strict_fake(**kwargs)

    previous_retry = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    previous_key = os.environ.get("OPENAI_API_KEY")
    try:
        os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
        os.environ["OPENAI_API_KEY"] = "fixture-not-a-real-secret"
        output = build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=chat,
            responses_completion_fn=responses,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-canary-exact-execution",
                "attempt_id": "fixture-canary-exact-execution",
            },
        )
    finally:
        if previous_retry is None:
            os.environ.pop("LLM_GATEWAY_TRANSPORT_RETRIES", None)
        else:
            os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = previous_retry
        if previous_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous_key

    if (
        len(captured) != 3
        or len(chat.calls) != 9
        or len(output.provider_output_captures) != 12
        or len(output.artifacts) != 9
    ):
        raise RuntimeError("fake_provider_full_chain_preflight_failed")
    first = captured[0]
    request = json.loads(first["input"][1]["content"])
    policy = StrictTruthKernelPolicy.from_cell_input(
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            input_pack.cell_inputs[0]
        )
    )
    template = {
        "provider": "openai",
        "base_url": "https://api.openai.com/v1",
        "endpoint": "/responses",
        "model": "gpt-5.6-sol",
        "input": first["input"],
        "text": first["text"],
        "reasoning": {"effort": "none"},
        "max_output_tokens": 512,
        "timeout_s": 120,
        "stream": False,
        "role": first["role"],
        "profile": first["profile"],
    }
    template["_derived_request"] = request
    template["_derived_input_digest"] = input_pack.input_digest
    return template, policy


def preflight(
    *,
    result_path: Path = RESULT_PATH,
    require_credential: bool = True,
) -> dict[str, Any]:
    if _file_sha256(AUTHORITY_PATH) != EXPECTED_AUTHORITY_SHA256:
        raise RuntimeError("canary_authority_digest_mismatch")
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    if (
        authority.get("next_action") != EXPECTED_NEXT_ACTION
        or authority.get("next_action_authorized") is not True
    ):
        raise RuntimeError("canary_exact_once_execution_not_authorized")
    if result_path.exists():
        raise RuntimeError("canary_identity_already_consumed")
    if os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES") != "0":
        raise RuntimeError("LLM_GATEWAY_TRANSPORT_RETRIES_must_equal_0")
    credential_present = _load_repo_api_key_if_needed()
    if require_credential and not credential_present:
        raise RuntimeError("OPENAI_API_KEY_missing")

    template, policy = _derive_exact_request()
    request = template.pop("_derived_request")
    input_digest = template.pop("_derived_input_digest")
    exact = authority["exact_canary"]
    observed = {
        "input_digest": input_digest,
        "canonical_request_sha256": _canonical_sha256(request),
        "server_schema_sha256": _canonical_sha256(
            template["text"]["format"]["schema"]
        ),
        "text_format_sha256": _canonical_sha256(template["text"]),
        "system_prompt_sha256": _text_sha256(
            template["input"][0]["content"]
        ),
        "user_payload_sha256": _text_sha256(
            template["input"][1]["content"]
        ),
        "exact_request_template_sha256": _canonical_sha256(template),
    }
    expected = {key: exact[key] for key in observed}
    if observed != expected:
        raise RuntimeError("canary_exact_request_digest_mismatch")
    if policy.schema_name != exact["schema_name"]:
        raise RuntimeError("canary_schema_name_mismatch")
    return {
        "status": "pass_zero_call_exact_execution_preflight",
        "canary_id": CANARY_ID,
        "authority_decision_digest": EXPECTED_AUTHORITY_SHA256,
        "exact_request_digests": observed,
        "credential_present": credential_present,
        "credential_value_persisted": False,
        "transport_retry_budget": 0,
        "fake_provider_strict_wire_and_local_validator_pass": True,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "template": template,
        "policy": policy,
    }


def _usage_and_cost(result: Mapping[str, Any]) -> dict[str, Any]:
    raw = result.get("raw_response")
    usage = raw.get("usage") if isinstance(raw, Mapping) else {}
    usage = usage if isinstance(usage, Mapping) else {}
    details = usage.get("input_tokens_details")
    details = details if isinstance(details, Mapping) else {}
    input_tokens = int(result.get("input_tokens") or 0)
    cached_input_tokens = int(details.get("cached_tokens") or 0)
    uncached_input_tokens = max(0, input_tokens - cached_input_tokens)
    output_tokens = int(result.get("output_tokens") or 0)
    estimated_cost = (
        uncached_input_tokens * INPUT_USD_PER_MILLION
        + cached_input_tokens * CACHED_INPUT_USD_PER_MILLION
        + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "uncached_input_tokens": uncached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": int(result.get("total_tokens") or 0),
        "estimated_cost_usd": round(estimated_cost, 8),
        "pricing_usd_per_million": {
            "input": INPUT_USD_PER_MILLION,
            "cached_input": CACHED_INPUT_USD_PER_MILLION,
            "output": OUTPUT_USD_PER_MILLION,
        },
    }


def _failure_class(result: Mapping[str, Any]) -> str:
    reason = str(result.get("failure_reason") or "")
    if reason in {"HTTP 400", "HTTP 422"}:
        return "strict_schema_request_rejected"
    if reason in {"HTTP 401", "HTTP 403", "HTTP 404", "HTTP 429"}:
        return "model_or_endpoint_access_rejected"
    if result.get("status") == "timeout":
        return "transport_error_or_timeout"
    return "transport_error_or_timeout"


def _base_result(
    preflight_result: Mapping[str, Any],
    provider_result: Mapping[str, Any],
) -> dict[str, Any]:
    call_id = str(provider_result.get("call_id") or "")
    return {
        "schema_version": RESULT_SCHEMA_VERSION,
        "recorded_at": _utc_now(),
        "work_item_id": WORK_ITEM_ID,
        "canary_id": CANARY_ID,
        "authority_decision_digest": EXPECTED_AUTHORITY_SHA256,
        "exact_request_digests": preflight_result["exact_request_digests"],
        "provider_contract": {
            "provider": "openai",
            "model": "gpt-5.6-sol",
            "base_url": "https://api.openai.com/v1",
            "endpoint": "/responses",
            "reasoning_effort": "none",
            "max_output_tokens": 512,
            "timeout_seconds": 120,
        },
        "provider_status": str(provider_result.get("status") or "unknown"),
        "response_status": str(
            provider_result.get("response_status") or ""
        ),
        "call_id_digest": (
            hashlib.sha256(call_id.encode("utf-8")).hexdigest()
            if call_id
            else ""
        ),
        "usage": _usage_and_cost(provider_result),
        "latency_ms": int(provider_result.get("latency_ms") or 0),
        "transport_attempt_count": int(
            provider_result.get("transport_attempt_count") or 0
        ),
        "observed_counts": {
            "semantic_model_calls": 1,
            "provider_calls": 1,
            "network_calls": 1,
            "transport_attempts": int(
                provider_result.get("transport_attempt_count") or 0
            ),
            "source_network_calls": 0,
            "external_tool_calls": 0,
            "chat_completions_calls": 0,
            "canonical_work_unit_attempt_run_writes": 0,
            "business_artifact_writes": 0,
        },
        "raw_provider_response_persisted": False,
        "provider_output_text_persisted": False,
        "private_reasoning_persisted": False,
        "credential_persisted": False,
        "headers_persisted": False,
        "stack_trace_persisted": False,
        "result_is_only_live_provider_capability_evidence": True,
        "result_is_not_research_or_product_acceptance": True,
    }


def _persist_once(result_path: Path, payload: Mapping[str, Any]) -> None:
    result_path.parent.mkdir(parents=True, exist_ok=True)
    with result_path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(
            payload,
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        handle.write("\n")


def execute(
    *,
    result_path: Path = RESULT_PATH,
    completion_fn: Callable[..., Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    preflight_result = preflight(result_path=result_path)
    template = dict(preflight_result.pop("template"))
    policy = preflight_result.pop("policy")
    if completion_fn is None:
        from sec_agent.llm_gateway import responses_completion

        completion_fn = responses_completion

    try:
        provider_result = completion_fn(
            llm_backend=template["provider"],
            base_url=template["base_url"],
            responses_path=template["endpoint"],
            model=template["model"],
            input=template["input"],
            text=template["text"],
            api_key_env="OPENAI_API_KEY",
            max_output_tokens=template["max_output_tokens"],
            timeout_s=template["timeout_s"],
            stream=template["stream"],
            reasoning=template["reasoning"],
            role=template["role"],
            profile=template["profile"],
            trace_tags={
                "canary_id": CANARY_ID,
                "scope": "provider_contract_canary_only",
            },
        )
    except Exception as exc:
        provider_result = {
            "status": "provider_error",
            "failure_reason": f"transport_exception:{type(exc).__name__}",
            "transport_attempt_count": 1,
        }

    if not isinstance(provider_result, Mapping):
        provider_result = {
            "status": "provider_error",
            "failure_reason": "provider_envelope_not_mapping",
            "transport_attempt_count": 1,
        }
    result = _base_result(preflight_result, provider_result)
    result["strict_schema_parse_pass"] = False
    result["local_semantic_validation_and_rendering_pass"] = False
    result["content_free_output_shape"] = {}

    if int(result["transport_attempt_count"]) != 1:
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": "transport_attempt_count_not_one",
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result
    if provider_result.get("status") != "ok":
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": _failure_class(provider_result),
                "sanitized_failure_detail": str(
                    provider_result.get("failure_reason") or "provider_error"
                ),
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result
    if provider_result.get("response_status") != "completed":
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": "response_not_completed",
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result
    if float(result["usage"]["estimated_cost_usd"]) > 0.05:
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": "token_or_cost_budget_exceeded",
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result

    from apps.workbench.backend.application.bounded_agent_executor import (
        NativeJsonSchemaResponseError,
        StrictTruthKernelJsonSchemaAdapter,
    )

    try:
        atoms = StrictTruthKernelJsonSchemaAdapter.parse_response(
            provider_result
        )
    except NativeJsonSchemaResponseError:
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": "strict_schema_parse_failed",
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result
    result["strict_schema_parse_pass"] = True
    rendered, violation = policy.render_provider_output(atoms)
    if violation is not None or rendered is None:
        result.update(
            {
                "status": "terminal_failed_no_retry",
                "failure_class": (
                    "local_semantic_validation_or_rendering_failed"
                ),
                "local_failure_subtype": (
                    violation.subtype if violation is not None else "unknown"
                ),
                "next_action": (
                    "return_to_program_level_blocked_decision"
                ),
            }
        )
        _persist_once(result_path, result)
        return result

    judgments = atoms.get("fact_judgments")
    judgments = judgments if isinstance(judgments, list) else []
    result.update(
        {
            "status": "pass_exact_once_live_provider_capability_proven",
            "failure_class": None,
            "strict_schema_parse_pass": True,
            "local_semantic_validation_and_rendering_pass": True,
            "content_free_output_shape": {
                "top_level_field_count": len(atoms),
                "top_level_fields": sorted(atoms),
                "fact_judgment_count": len(judgments),
                "fact_judgment_field_count": (
                    len(judgments[0])
                    if judgments and isinstance(judgments[0], Mapping)
                    else 0
                ),
                "program_cell_id_matches": (
                    atoms.get("program_cell_id") == policy.program_cell_id
                ),
                "terminal_class_is_closed_enum_member": (
                    atoms.get("terminal_class") in policy._TERMINAL_CLASSES
                ),
            },
            "provider_authored_material_number_or_free_narrative_present": (
                False
            ),
            "next_action": SUCCESS_NEXT_ACTION,
        }
    )
    _persist_once(result_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Consume the exact-once canary identity and make one provider call.",
    )
    args = parser.parse_args()
    if args.execute:
        result = execute()
    else:
        result = preflight()
        result.pop("template", None)
        result.pop("policy", None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(result["status"]).startswith("pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
