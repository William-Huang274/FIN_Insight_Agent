from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Iterator, Mapping


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    estimate_provider_input_tokens,
    research_profile_for_ref,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.llm_gateway import chat_completion as _gateway_chat_completion
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    _compiled_runtime,
)


AUTHORITY_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_authority_decision_v1_0.json"
)
EXPECTED_AUTHORITY_SHA256 = (
    "e6f10a50d796d22bf03c48012442dbae1196be58984159cd4ef194053f124498"
)
PROJECT_OS_POSTFLIGHT_PATH = ROOT / (
    ".codex_runtime/"
    "s4_t06_mu_changed_family_canary_execution_authority_postflight.json"
)
EXPECTED_PROJECT_OS_POSTFLIGHT_SHA256 = (
    "bfb8a827111a280826f6e712363efa8a235432c2696bd205f734672ea43f62a7"
)
RESULT_PATH = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_changed_contract_family_"
    "single_node_natural_output_canaries_exact_once_execution_result_v1_0.json"
)
RESTRICTED_ROOT = ROOT / (
    ".codex_runtime/"
    "s4_t06_mu_changed_contract_family_single_node_canaries_exact_once_r1"
)
EXECUTION_STATE_PATH = RESTRICTED_ROOT / "execution_state.json"
CAPTURE_ROOT = RESTRICTED_ROOT / "captures"
WORK_ITEM_ID = (
    "S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-"
    "CANARIES-EXACT-ONCE-EXECUTION"
)
PROJECT_OS_RUN_SCOPE = (
    "S4_T06_MU_CHANGED_CONTRACT_FAMILY_SINGLE_NODE_NATURAL_OUTPUT_"
    "CANARIES_EXACT_ONCE_EXECUTION"
)
NEXT_ACTION = (
    "S4-T06-MU-CHANGED-CONTRACT-FAMILY-SINGLE-NODE-NATURAL-OUTPUT-"
    "CANARIES-POST-RESULT-DISPOSITION-DECISION"
)
RESULT_SCHEMA_VERSION = (
    "fin_ia_0_1_s4_t06_mu_changed_contract_family_single_node_natural_"
    "output_canaries_exact_once_execution_result_v1_0"
)
CANARY_RUN_ID = (
    "20260730_mu_single_node_changed_contract_natural_output_deepseek_pro_r1"
)

_provider_chat_completion = _gateway_chat_completion


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path_ref(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(_json_bytes(value))
    os.replace(temporary, path)


def _write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(_json_bytes(value))


@contextmanager
def _fixture_environment() -> Iterator[None]:
    names = ("LLM_GATEWAY_TRANSPORT_RETRIES", "DEEPSEEK_API_KEY")
    previous = {name: os.environ.get(name) for name in names}
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"
    os.environ["DEEPSEEK_API_KEY"] = "fixture-not-a-real-secret"
    try:
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _template_row(
    *,
    family_id: str,
    call: Mapping[str, Any],
) -> dict[str, Any]:
    request = call["request"]
    kwargs = call["kwargs"]
    contract = request["compiled_judgment_atom_contract"]
    system = kwargs["messages"][0]["content"]
    user = kwargs["messages"][1]["content"]
    return {
        "family_id": family_id,
        "segment_id": request["segment_id"],
        "system_prompt_sha256": hashlib.sha256(
            system.encode("utf-8")
        ).hexdigest(),
        "user_payload_sha256": hashlib.sha256(
            user.encode("utf-8")
        ).hexdigest(),
        "canonical_request_sha256": canonical_digest(request),
        "compiled_contract_digest": contract["contract_digest"],
        "wire_schema_sha256": canonical_digest(
            request["required_output_schema"]
        ),
        "required_top_level_keys": request["required_top_level_keys"],
        "allowed_alias_counts": {
            "supports": len(contract.get("allowed_supports", [])),
            "facts": len(contract.get("allowed_facts", [])),
            "claims": len(contract.get("allowed_claims", [])),
            "authorities": len(contract.get("allowed_authorities", [])),
            "dates": len(contract.get("allowed_date_aliases", [])),
        },
        "input_utf8_bytes": len((system + user).encode("utf-8")),
        "estimated_input_tokens": estimate_provider_input_tokens(
            system + "\n" + user
        ),
        "maximum_output_tokens": kwargs["max_tokens"],
    }


def _derive_execution_contexts(
    authority: Mapping[str, Any],
) -> dict[str, Any]:
    with _fixture_environment():
        input_pack, admission, fake = _compiled_runtime("MU")
        fixture_result = (
            build_s3_three_cell_bounded_agent_executor_for_admission(
                admission,
                chat_completion_fn=fake,
            ).execute(
                input_pack,
                admission,
                run_identity={
                    "research_run_id": "fixture-canary-execution-derive",
                    "attempt_id": "fixture-canary-execution-derive",
                },
            )
        )
    if (
        len(fake.calls) != 12
        or len(fake.compiled_outputs) != 9
        or len(fixture_result.artifacts) != 9
    ):
        raise RuntimeError("canary_template_fixture_not_closed")
    admission = admission.model_copy(
        update={
            "provider_output_capture_policy_ref": (
                S4_PROVIDER_INTERACTION_AUDIT_CAPTURE_POLICY_REF
            )
        }
    )
    admission.assert_profile_admissible()

    target_cell_id = str(
        authority["canary_isolation_contract"]["program_cell_id"]
    )
    compiled_calls: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    output_index = 0
    for call in fake.calls:
        request = call["request"]
        contract = request.get("compiled_judgment_atom_contract")
        if not isinstance(contract, Mapping):
            continue
        compiled_calls.append((call, fake.compiled_outputs[output_index]))
        output_index += 1
    target = {
        str(call["request"]["compiled_judgment_atom_contract"]["family_id"]): (
            call,
            wire_output,
        )
        for call, wire_output in compiled_calls
        if call["request"]["compiled_judgment_atom_contract"][
            "program_cell_id"
        ]
        == target_cell_id
    }
    order = list(authority["canary_isolation_contract"]["execution_order"])
    if set(target) != set(order):
        raise RuntimeError("canary_target_family_template_missing")

    raw_cell = next(
        row
        for row in input_pack.cell_inputs
        if row.get("program_cell_id") == target_cell_id
    )
    cell_input = (
        S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            raw_cell,
            policy_ref=admission.case_numeric_authority_policy_ref,
        )
    )
    fact_segment = "facts_explanation_and_terminal"
    claim_segment = "owner_grade_claim_cards"
    wwc_segment = "actionable_what_would_change_tasks"
    fact_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell_input,
        validated_segments={},
        as_of=str(admission.as_of),
    )
    seed_fact_wire = target["specialist_fact_atoms"][1]
    seed_fact = fact_compiler.assemble(
        fact_segment,
        seed_fact_wire,
        provider_output_utf8_bytes=len(
            json.dumps(seed_fact_wire, ensure_ascii=False).encode("utf-8")
        ),
    )
    claim_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell_input,
        validated_segments={fact_segment: seed_fact},
        as_of=str(admission.as_of),
    )
    seed_claim_wire = target["claim_candidate_atoms"][1]
    seed_claim = claim_compiler.assemble(
        claim_segment,
        seed_claim_wire,
        provider_output_utf8_bytes=len(
            json.dumps(seed_claim_wire, ensure_ascii=False).encode("utf-8")
        ),
    )
    seed_claim = (
        DeepSeekS3ThreeCellNodeExecutor
        ._expand_specialist_claim_fact_links(
            output=seed_claim,
            cell_input=cell_input,
            validated_segments={fact_segment: seed_fact},
            policy_ref=admission.claim_fact_link_policy_ref,
        )
    )
    seed_claim = (
        DeepSeekS3ThreeCellNodeExecutor
        ._assemble_specialist_claim_scopes_v6(
            output=seed_claim,
            cell_input=cell_input,
            validated_segments={fact_segment: seed_fact},
        )
    )
    wwc_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell_input,
        validated_segments={
            fact_segment: seed_fact,
            claim_segment: seed_claim,
        },
        as_of=str(admission.as_of),
    )
    compilers = {
        "specialist_fact_atoms": fact_compiler,
        "claim_candidate_atoms": claim_compiler,
        "what_would_change_atoms": wwc_compiler,
    }
    prior_segments = {
        "specialist_fact_atoms": {},
        "claim_candidate_atoms": {fact_segment: seed_fact},
        "what_would_change_atoms": {
            fact_segment: seed_fact,
            claim_segment: seed_claim,
        },
    }

    frozen = {
        row["family_id"]: row
        for row in authority["exact_canary_requests"]
    }
    for family_id in order:
        derived = _template_row(
            family_id=family_id,
            call=target[family_id][0],
        )
        if derived != frozen[family_id]:
            raise RuntimeError(
                f"canary_exact_template_drift:{family_id}"
            )
    return {
        "input_pack": input_pack,
        "admission": admission,
        "cell_input": cell_input,
        "calls": {family: target[family][0] for family in order},
        "compilers": compilers,
        "prior_segments": prior_segments,
        "order": order,
    }


def preflight(
    *,
    result_path: Path = RESULT_PATH,
    state_path: Path = EXECUTION_STATE_PATH,
    capture_root: Path = CAPTURE_ROOT,
) -> dict[str, Any]:
    if not AUTHORITY_PATH.is_file() or (
        _sha256(AUTHORITY_PATH) != EXPECTED_AUTHORITY_SHA256
    ):
        raise RuntimeError("canary_authority_binding_mismatch")
    if not PROJECT_OS_POSTFLIGHT_PATH.is_file() or (
        _sha256(PROJECT_OS_POSTFLIGHT_PATH)
        != EXPECTED_PROJECT_OS_POSTFLIGHT_SHA256
    ):
        raise RuntimeError("canary_project_os_postflight_binding_mismatch")
    project_os = json.loads(
        PROJECT_OS_POSTFLIGHT_PATH.read_text(encoding="utf-8")
    )
    if (
        project_os.get("status") != "pass"
        or project_os.get("open_full_chain_blockers") != []
        or project_os.get("run_scope") != PROJECT_OS_RUN_SCOPE
    ):
        raise RuntimeError("canary_project_os_postflight_not_passed")
    authority = json.loads(AUTHORITY_PATH.read_text(encoding="utf-8"))
    if (
        authority.get("next_action") != WORK_ITEM_ID
        or authority.get("next_action_authorized") is not True
        or authority["authority"].get(
            "future_exact_once_three_family_canary_execution_authorized"
        )
        is not True
    ):
        raise RuntimeError("canary_execution_not_authorized")
    if result_path.exists() or state_path.exists() or capture_root.exists():
        raise RuntimeError("canary_exact_once_identity_already_consumed")
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("canary_credential_missing")
    retries = os.environ.get("LLM_GATEWAY_TRANSPORT_RETRIES")
    if retries not in {None, "", "0"}:
        raise RuntimeError("canary_transport_retry_budget_not_zero")

    contexts = _derive_execution_contexts(authority)
    admission = contexts["admission"]
    budget = authority["hard_budget"]
    frozen_requests = authority["exact_canary_requests"]
    projected_cost = (
        sum(int(row["estimated_input_tokens"]) for row in frozen_requests)
        * admission.input_cache_miss_usd_per_million
        + int(budget["maximum_output_tokens_total"])
        * admission.output_usd_per_million
    ) / 1_000_000
    if (
        admission.provider != authority["provider_route"]["provider"]
        or admission.model != authority["provider_route"]["model"]
        or admission.base_url != authority["provider_route"]["base_url"]
        or admission.api_key_env
        != authority["provider_route"]["api_key_env"]
        or admission.provider_output_capture_policy_ref
        != authority["capture_and_validation_contract"][
            "capture_policy_ref"
        ]
        or projected_cost > float(budget["maximum_total_cost_usd"])
    ):
        raise RuntimeError("canary_provider_or_budget_binding_mismatch")
    return {
        "status": "pass_exact_zero_call_execution_preflight",
        "work_item_id": WORK_ITEM_ID,
        "canary_run_id": CANARY_RUN_ID,
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "project_os_postflight_sha256": (
            EXPECTED_PROJECT_OS_POSTFLIGHT_SHA256
        ),
        "credential_present_value_persisted": [True, False],
        "provider_model_route": [
            admission.provider,
            admission.model,
            admission.base_url,
        ],
        "execution_order": contexts["order"],
        "maximum_model_provider_network_calls": [3, 3, 3],
        "maximum_output_tokens_total": int(
            budget["maximum_output_tokens_total"]
        ),
        "maximum_cost_usd": float(budget["maximum_total_cost_usd"]),
        "projected_worst_case_cost_usd": round(projected_cost, 8),
        "retry_fallback_replay_provider_hopping": [0, 0, 0, 0],
        "result_absent": True,
        "execution_state_absent": True,
        "capture_root_absent": True,
        "canonical_work_unit_attempt_run_or_artifact_writes": 0,
        "_contexts": contexts,
        "_authority": authority,
    }


def _capture_provider_interaction(
    *,
    sequence: int,
    family_id: str,
    call: Mapping[str, Any],
    result: Mapping[str, Any],
    receipt: Mapping[str, Any],
    admission: Any,
    capture_root: Path,
) -> tuple[dict[str, Any], str, str]:
    kwargs = call["kwargs"]
    content = result.get("content")
    capture = DeepSeekS3ThreeCellNodeExecutor._provider_interaction_capture(
        admission=admission,
        capture_sequence=sequence,
        stage=f"changed_contract_canary:{family_id}",
        receipt=receipt,
        result=result,
        assistant_output_text=content if isinstance(content, str) else "",
        model_visible_request=kwargs["messages"],
        nonsecret_inference_arguments={
            "api_surface": "chat_completions",
            "tools": None,
            "tool_choice": None,
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": kwargs["max_tokens"],
            "timeout_seconds": kwargs["timeout_s"],
            "stream": False,
            "enable_thinking": False,
            "reasoning_effort": "none",
        },
        request_path="/chat/completions",
    )
    digest = canonical_digest(capture)
    path = capture_root / f"{sequence:02d}_{family_id}_{digest}.json"
    try:
        capture_ref = path.relative_to(ROOT).as_posix()
    except ValueError:
        capture_ref = str(path)
    _write_json_exclusive(path, capture)
    return capture, capture_ref, digest


def _validate_natural_output(
    *,
    family_id: str,
    call: Mapping[str, Any],
    content: str,
    contexts: Mapping[str, Any],
) -> dict[str, Any]:
    request = call["request"]
    segment_id = str(request["segment_id"])
    parsed = DeepSeekS3ThreeCellNodeExecutor._parse_native_json_object(
        content
    )
    compiler = contexts["compilers"][family_id]
    assembled = compiler.assemble(
        segment_id,
        parsed,
        provider_output_utf8_bytes=len(content.encode("utf-8")),
    )
    if family_id == "claim_candidate_atoms":
        assembled = (
            DeepSeekS3ThreeCellNodeExecutor
            ._expand_specialist_claim_fact_links(
                output=assembled,
                cell_input=contexts["cell_input"],
                validated_segments=contexts["prior_segments"][family_id],
                policy_ref=(
                    contexts["admission"].claim_fact_link_policy_ref
                ),
            )
        )
        assembled = (
            DeepSeekS3ThreeCellNodeExecutor
            ._assemble_specialist_claim_scopes_v6(
                output=assembled,
                cell_input=contexts["cell_input"],
                validated_segments=contexts["prior_segments"][family_id],
            )
        )
    profile = research_profile_for_ref(
        contexts["admission"].research_profile_ref
    )
    DeepSeekS3ThreeCellNodeExecutor._validate_specialist_segment(
        segment_id=segment_id,
        output=assembled,
        cell_input=contexts["cell_input"],
        validated_segments=contexts["prior_segments"][family_id],
        transport_ref=contexts["admission"].transport_ref,
        research_profile=profile,
        judgment_atom_compiled_contract_ref=(
            contexts["admission"].judgment_atom_compiled_contract_ref
        ),
        as_of=str(contexts["admission"].as_of),
    )
    return {
        "top_level_keys": sorted(parsed),
        "provider_output_utf8_bytes": len(content.encode("utf-8")),
        "provider_item_count": len(
            parsed.get(
                {
                    "specialist_fact_atoms": "fact_atoms",
                    "claim_candidate_atoms": "claim_candidate_atoms",
                    "what_would_change_atoms": "what_would_change_atoms",
                }[family_id],
                [],
            )
        ),
        "compiled_wire_pass": True,
        "local_deterministic_assembly_pass": True,
        "local_rendered_digest": canonical_digest(assembled),
    }


def _failure_code(exc: BaseException) -> str:
    text = str(exc).strip().lower()
    if text and all(
        character.isalnum() or character in "_:.-"
        for character in text
    ) and len(text) <= 180:
        return text
    return f"canary_{type(exc).__name__.lower()}"


def execute(
    *,
    result_path: Path = RESULT_PATH,
    state_path: Path = EXECUTION_STATE_PATH,
    capture_root: Path = CAPTURE_ROOT,
) -> dict[str, Any]:
    preflight_result = preflight(
        result_path=result_path,
        state_path=state_path,
        capture_root=capture_root,
    )
    contexts = preflight_result.pop("_contexts")
    authority = preflight_result.pop("_authority")
    started_monotonic = time.monotonic()
    started_at = _utc_now()
    state: dict[str, Any] = {
        "schema_version": "fin01_s4_t06_changed_family_canary_state_v1",
        "canary_run_id": CANARY_RUN_ID,
        "work_item_id": WORK_ITEM_ID,
        "status": "started_exact_once",
        "started_at": started_at,
        "completed_families": [],
        "capture_refs": [],
        "retry_fallback_replay_provider_hopping": [0, 0, 0, 0],
    }
    _write_json_exclusive(state_path, state)
    os.environ["LLM_GATEWAY_TRANSPORT_RETRIES"] = "0"

    rows: list[dict[str, Any]] = []
    total_cost = 0.0
    total_input = 0
    total_output = 0
    total_tokens = 0
    terminal_failure: str | None = None
    for sequence, family_id in enumerate(contexts["order"], 1):
        call = contexts["calls"][family_id]
        kwargs = dict(call["kwargs"])
        kwargs["trace_tags"] = {
            "canary_run_id": CANARY_RUN_ID,
            "work_item_id": WORK_ITEM_ID,
            "family_id": family_id,
            "sequence": sequence,
        }
        try:
            provider_result = _provider_chat_completion(**kwargs)
        except BaseException as exc:  # preserve attempted request before stop
            provider_result = {
                "status": "provider_exception",
                "finish_reason": None,
                "content": "",
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "call_id": f"{CANARY_RUN_ID}:{sequence}",
                "provider": contexts["admission"].provider,
                "model": contexts["admission"].model,
                "latency_ms": 0,
                "transport_attempt_count": 1,
                "raw_response": {},
            }
            call_exception: BaseException | None = exc
        else:
            call_exception = None

        receipt = DeepSeekS3ThreeCellNodeExecutor._usage_receipt(
            provider_result,
            contexts["admission"],
            node_id=f"changed_contract_canary:{family_id}",
        )
        capture, capture_ref, capture_digest = (
            _capture_provider_interaction(
                sequence=sequence,
                family_id=family_id,
                call=call,
                result=provider_result,
                receipt=receipt,
                admission=contexts["admission"],
                capture_root=capture_root,
            )
        )
        total_cost = round(
            total_cost + float(receipt["estimated_cost_usd"]), 8
        )
        total_input += int(receipt["input_tokens"])
        total_output += int(receipt["output_tokens"])
        total_tokens += int(receipt["total_tokens"])
        row: dict[str, Any] = {
            "sequence": sequence,
            "family_id": family_id,
            "segment_id": call["request"]["segment_id"],
            "canonical_request_sha256": canonical_digest(
                call["request"]
            ),
            "provider_status": receipt["status"],
            "finish_reason": receipt["finish_reason"],
            "usage_receipt": receipt,
            "capture_ref": capture_ref,
            "capture_digest": capture_digest,
            "capture_policy_ref": capture["capture_policy_ref"],
            "capture_persisted_before_local_validation": True,
            "raw_provider_envelope_persisted": False,
            "business_promotion": False,
        }
        try:
            if call_exception is not None:
                raise RuntimeError(
                    f"provider_exception:{type(call_exception).__name__}"
                )
            if receipt["transport_attempt_count"] != 1:
                raise ValueError("canary_transport_attempt_violation")
            if receipt["status"] != "ok":
                raise ValueError("canary_provider_status_not_ok")
            if receipt["finish_reason"] != "stop":
                raise ValueError("canary_finish_reason_not_stop")
            if int(receipt["output_tokens"]) > int(kwargs["max_tokens"]):
                raise ValueError("canary_output_token_cap_exceeded")
            if total_cost > float(
                authority["hard_budget"]["maximum_total_cost_usd"]
            ):
                raise ValueError("canary_actual_cost_cap_exceeded")
            content = provider_result.get("content")
            if not isinstance(content, str) or not content:
                raise ValueError("canary_assistant_output_empty")
            row["validation"] = _validate_natural_output(
                family_id=family_id,
                call=call,
                content=content,
                contexts=contexts,
            )
            row["status"] = "pass"
        except BaseException as exc:
            terminal_failure = _failure_code(exc)
            row.update(
                {
                    "status": "terminal_failed",
                    "failure_code": terminal_failure,
                    "validation": {
                        "compiled_wire_pass": False,
                        "local_deterministic_assembly_pass": False,
                    },
                }
            )
        rows.append(row)
        state["completed_families"].append(family_id)
        state["capture_refs"].append(capture_ref)
        state["last_family_status"] = row["status"]
        _write_json_atomic(state_path, state)
        if terminal_failure is not None:
            break
        if (
            time.monotonic() - started_monotonic
            > float(authority["hard_budget"]["maximum_wall_clock_seconds"])
        ):
            terminal_failure = "canary_wall_clock_cap_exceeded"
            break

    completed = [row["family_id"] for row in rows]
    skipped = [
        family_id
        for family_id in contexts["order"]
        if family_id not in completed
    ]
    status = (
        "terminal_succeeded_exact_once"
        if terminal_failure is None and not skipped
        else "terminal_failed_no_retry"
    )
    completed_at = _utc_now()
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "work_item_id": WORK_ITEM_ID,
        "canary_run_id": CANARY_RUN_ID,
        "status": status,
        "started_at": started_at,
        "completed_at": completed_at,
        "authority_ref": _path_ref(AUTHORITY_PATH),
        "authority_sha256": EXPECTED_AUTHORITY_SHA256,
        "runner_ref": _path_ref(Path(__file__)),
        "project_os_preflight": {
            "status": "pass",
            "open_blockers": 0,
            "ref": _path_ref(PROJECT_OS_POSTFLIGHT_PATH),
            "sha256": EXPECTED_PROJECT_OS_POSTFLIGHT_SHA256,
        },
        "provider_route": {
            "provider": contexts["admission"].provider,
            "model": contexts["admission"].model,
            "base_url": contexts["admission"].base_url,
            "wire_api": "chat_completions_json_object",
        },
        "credential_present_value_persisted": [True, False],
        "execution_order": contexts["order"],
        "family_results": rows,
        "completed_families": completed,
        "skipped_after_first_failure": skipped,
        "first_credible_failure": terminal_failure,
        "totals": {
            "model_calls": len(rows),
            "provider_calls": len(rows),
            "network_calls": len(rows),
            "transport_attempts": sum(
                int(row["usage_receipt"]["transport_attempt_count"])
                for row in rows
            ),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "estimated_cost_usd": total_cost,
            "captures": len(rows),
        },
        "budget": {
            "maximum_model_provider_network_calls": [3, 3, 3],
            "maximum_output_tokens_total": 4200,
            "maximum_cost_usd": 0.03,
            "maximum_wall_clock_seconds": 360,
            "retry_fallback_replay_provider_hopping": [0, 0, 0, 0],
        },
        "canonical_work_unit_attempt_run_or_artifact_writes": 0,
        "business_artifact_promotions": 0,
        "R7_admission_or_exact_live": False,
        "paired_assessment_or_owner_acceptance": False,
        "next_action": NEXT_ACTION,
        "known_boundary": (
            "This is a bounded three-family single-node natural-output "
            "canary result. It is not a formal MU full-chain run, final L1 "
            "proof, paired assessment, owner acceptance, or T06 closeout. "
            "A separate zero-call post-result disposition is mandatory."
        ),
    }
    _write_json_exclusive(result_path, result)
    state.update(
        {
            "status": status,
            "completed_at": completed_at,
            "result_ref": _path_ref(result_path),
            "first_credible_failure": terminal_failure,
        }
    )
    _write_json_atomic(state_path, state)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Consume the exact-once three-family canary identity.",
    )
    args = parser.parse_args()
    if args.execute:
        result = execute()
    else:
        result = preflight()
        result.pop("_contexts", None)
        result.pop("_authority", None)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if str(result["status"]).startswith("pass") or str(
        result["status"]
    ).startswith("terminal_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
