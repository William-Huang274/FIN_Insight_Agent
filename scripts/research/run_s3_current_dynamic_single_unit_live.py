from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
from typing import Any, Callable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    value = str(candidate)
    if value not in sys.path:
        sys.path.insert(0, value)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from apps.workbench.backend.application.research_evidence_pack_service import (  # noqa: E402
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)
from apps.workbench.backend.application.research_retrieval_service import (  # noqa: E402
    ResearchRetrievalPrincipal,
    ResearchRetrievalService,
    ResearchRetrievalServiceError,
)
from retrieval.cuda_execution import required_cuda_fp16_receipt  # noqa: E402
from sec_agent.canonical_runtime.session import (  # noqa: E402
    append_session_event,
    apply_accepted_plan_delta,
    canonical_digest,
    create_agent_session,
)
from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.dynamic_single_unit_loop import (  # noqa: E402
    DynamicSingleUnitLoopError,
    REFLECTION_TOOL_NAME,
    REQUEST_TOOL_NAME,
    compile_controlled_batch_projection,
    compile_initial_messages,
    compile_material_requirement_blueprints,
    compile_reflection_artifacts,
    compile_request_catalog,
    compile_round_feedback_receipts,
    compile_round_response,
    compile_workpaper_context,
    load_dynamic_single_unit_policy,
    public_round_response,
    reflection_tool,
    request_evidence_tool,
    validate_reflection_payload,
    validate_request_selection,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    MultiAgentPreviewError,
    compile_specialist_workpaper_messages,
    specialist_workpaper_tool,
    validate_specialist_workpaper,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402


AUTHORITY_SCHEMA = "fin_ia_s3_current_dynamic_single_unit_live_authority_v1_0"
AUTHORITY_STATUS = "signed_exact_once_DELL_current_dynamic_value_capture_live"
FULL_RESULT_SCHEMA = "fin_ia_s3_current_dynamic_single_unit_live_full_v1_0"
PUBLIC_RESULT_SCHEMA = "fin_ia_s3_current_dynamic_single_unit_live_result_v1_0"


class CurrentDynamicSingleUnitLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CurrentDynamicSingleUnitLiveError(code)


def _resolve(ref: str | Path) -> Path:
    raw = str(ref)
    relative = PurePosixPath(raw)
    _require(
        not relative.is_absolute() and "\\" not in raw and ".." not in relative.parts,
        "current_dynamic_live_path_invalid",
    )
    path = (ROOT / Path(*relative.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise CurrentDynamicSingleUnitLiveError(
            "current_dynamic_live_path_outside_repository"
        ) from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "current_dynamic_live_json_object_required")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
    except FileExistsError as exc:
        raise CurrentDynamicSingleUnitLiveError(
            "current_dynamic_live_output_identity_consumed"
        ) from exc


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_blob_sha256(*, commit: str, ref: str) -> str:
    _resolve(ref)
    _require(
        bool(re.fullmatch(r"[0-9a-f]{40}", commit.lower())),
        "current_dynamic_live_implementation_commit_invalid",
    )
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    _require(
        completed.returncode == 0,
        f"current_dynamic_live_bound_git_blob_missing:{ref}",
    )
    return hashlib.sha256(completed.stdout).hexdigest()


def _force_tool(name: str) -> dict[str, Any]:
    return {"type": "function", "function": {"name": name}}


def _public_provider_step(step: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "finish_reason": str(step.get("finish_reason") or ""),
        "usage": deepcopy(dict(step.get("usage") or {})),
        "request_digest": str(step.get("request_digest") or ""),
        "response_digest": str(step.get("response_digest") or ""),
        "request_capture_ref": _relative(str(step["request_capture_ref"])),
        "response_capture_ref": _relative(str(step["response_capture_ref"])),
        "private_reasoning_fields_redacted": int(
            step.get("private_reasoning_fields_redacted") or 0
        ),
        "reasoning_content_persisted": False,
    }


def _tool_arguments(
    step: ChatCompletionToolStepResult, *, expected_name: str
) -> tuple[dict[str, Any], str]:
    _require(
        len(step.tool_calls) == 1,
        "current_dynamic_live_exactly_one_tool_call_required",
    )
    call = dict(step.tool_calls[0])
    function = call.get("function")
    _require(
        isinstance(function, Mapping)
        and str(function.get("name") or "") == expected_name,
        "current_dynamic_live_unexpected_tool_call",
    )
    try:
        arguments = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise CurrentDynamicSingleUnitLiveError(
            "current_dynamic_live_tool_arguments_json_invalid"
        ) from exc
    _require(
        isinstance(arguments, dict),
        "current_dynamic_live_tool_arguments_object_required",
    )
    return arguments, str(call.get("id") or "")


def _request_rows(
    program: Mapping[str, Any], request_ids: Sequence[str]
) -> list[dict[str, Any]]:
    by_id = {
        str(row.get("request_id") or ""): deepcopy(dict(row))
        for row in program.get("evidence_requests") or ()
        if isinstance(row, Mapping)
    }
    _require(
        all(request_id in by_id for request_id in request_ids),
        "current_dynamic_live_request_program_binding_missing",
    )
    return [by_id[request_id] for request_id in request_ids]


def _event(
    events: list[dict[str, Any]],
    *,
    session_id: str,
    event_type: str,
    actor_id: str,
    occurred_at: str,
    attempt_id: str | None = None,
    input_refs: Sequence[str] = (),
    output_refs: Sequence[str] = (),
    feedback_refs: Sequence[str] = (),
) -> None:
    events.append(
        append_session_event(
            events,
            session_id=session_id,
            event_type=event_type,
            actor_id=actor_id,
            occurred_at=occurred_at,
            attempt_id=attempt_id,
            input_refs=input_refs,
            output_refs=output_refs,
            feedback_refs=feedback_refs,
        )
    )


def validate_authority(
    authority: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    expected = {
        "schema_version",
        "status",
        "signed_at",
        "implementation_commit",
        "case_key",
        "cell_id",
        "execution_budget",
        "bound_inputs",
        "output_contract",
        "known_boundary",
    }
    _require(
        set(authority) == expected
        and authority.get("schema_version") == AUTHORITY_SCHEMA
        and authority.get("status") == AUTHORITY_STATUS
        and authority.get("case_key") == "DELL"
        and authority.get("cell_id") == "CELL::value_capture",
        "current_dynamic_live_authority_identity_invalid",
    )
    budget = authority.get("execution_budget")
    _require(
        isinstance(budget, Mapping)
        and dict(budget)
        == {
            "maximum_model_calls": 4,
            "maximum_transport_attempts": 4,
            "maximum_retrieval_rounds": 2,
            "maximum_s1_s2_requests": 12,
            "maximum_external_source_network_calls": 0,
            "retries_per_model_node": 0,
            "fallbacks": 0,
            "candidate_promotions": 0,
            "current_product_pointer_mutations": 0,
        },
        "current_dynamic_live_authority_budget_invalid",
    )
    bound = authority.get("bound_inputs")
    _require(
        isinstance(bound, Mapping),
        "current_dynamic_live_authority_bound_inputs_invalid",
    )
    ref_names = (
        "runtime_registry",
        "loop_policy",
        "zero_call_result",
        "provider_profile",
        "runner",
        "loop_runtime",
        "provider_transport",
    )
    _require(
        set(bound)
        == {
            *(f"{name}_ref" for name in ref_names),
            *(f"{name}_sha256" for name in ref_names),
            "zero_call_result_digest",
            "current_evidence_pack_payload_digest",
            "task_readiness_result_digest",
        },
        "current_dynamic_live_authority_bound_inputs_invalid",
    )
    paths: dict[str, Path] = {}
    commit = str(authority.get("implementation_commit") or "").lower()
    for name in ref_names:
        ref = str(bound.get(f"{name}_ref") or "")
        expected_sha = str(bound.get(f"{name}_sha256") or "").lower()
        path = _resolve(ref)
        _require(
            path.is_file()
            and bool(re.fullmatch(r"[0-9a-f]{64}", expected_sha))
            and _sha(path) == expected_sha,
            f"current_dynamic_live_bound_input_drift:{name}",
        )
        paths[f"{name}_ref"] = path
    for name in ("runner", "loop_runtime", "provider_transport"):
        _require(
            _git_blob_sha256(
                commit=commit, ref=str(bound[f"{name}_ref"])
            )
            == str(bound[f"{name}_sha256"]),
            f"current_dynamic_live_implementation_blob_drift:{name}",
        )
    zero = _json(paths["zero_call_result_ref"])
    _require(
        zero.get("status") == "current_dynamic_single_unit_zero_call_proven"
        and zero.get("result_digest") == bound["zero_call_result_digest"]
        and zero.get("checks", {}).get(
            "two_real_current_runtime_rounds_executed"
        )
        is True
        and zero.get("checks", {}).get(
            "all_seven_proposition_groups_covered"
        )
        is True,
        "current_dynamic_live_zero_call_predecessor_invalid",
    )
    policy = load_dynamic_single_unit_policy(_json(paths["loop_policy_ref"]))
    _require(
        canonical_digest(policy) == canonical_digest(_json(paths["loop_policy_ref"])),
        "current_dynamic_live_authority_bound_policy_drift",
    )
    task_readiness = _json(
        _resolve(str(policy["source_refs"]["task_readiness_ref"]))
    )
    _require(
        task_readiness.get("result_digest")
        == bound["task_readiness_result_digest"]
        and task_readiness.get("evidence_pack_payload_digest")
        == bound["current_evidence_pack_payload_digest"],
        "current_dynamic_live_task_readiness_drift",
    )
    output = authority.get("output_contract")
    _require(
        isinstance(output, Mapping)
        and set(output)
        == {
            "capture_root_ref",
            "private_output_root_ref",
            "public_result_ref",
            "run_id",
            "attempt_ids",
            "product_publication",
        }
        and output.get("product_publication") == "forbidden",
        "current_dynamic_live_output_contract_invalid",
    )
    attempts = output.get("attempt_ids")
    _require(
        isinstance(attempts, list)
        and 4 == len(attempts) == len(set(str(value) for value in attempts))
        and all(str(value).strip() for value in attempts),
        "current_dynamic_live_attempt_ids_invalid",
    )
    for key in ("private_output_root_ref", "public_result_ref"):
        _require(
            not _resolve(str(output[key])).exists(),
            "current_dynamic_live_output_identity_consumed",
        )
    _require(
        authority_path.resolve() == authority_path
        and authority_path.is_file()
        and bool(str(authority.get("signed_at") or "").strip())
        and len(str(authority.get("known_boundary") or "").strip()) >= 80,
        "current_dynamic_live_authority_metadata_invalid",
    )
    return paths


def _execute_round(
    *,
    policy: Mapping[str, Any],
    program: Mapping[str, Any],
    request_ids: Sequence[str],
    round_index: int,
    retrieval: ResearchRetrievalService,
    retrieval_principal: ResearchRetrievalPrincipal,
    evidence_pack: Mapping[str, Any],
    truth_policy: Mapping[str, Any],
    consumer_policy: Mapping[str, Any],
    task_quantitative: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    requests = _request_rows(program, request_ids)
    batch = retrieval.execute_current_runtime_requests(
        "DELL",
        requests,
        retrieval_principal,
        material_requirement_blueprints=compile_material_requirement_blueprints(
            program=program, request_ids=request_ids
        ),
    )
    controlled = compile_controlled_batch_projection(
        policy=policy,
        selected_requests=requests,
        batch_result=batch,
    )
    response = compile_round_response(
        policy=policy,
        controlled_plan=controlled,
        evidence_pack=evidence_pack,
        truth_spine_policy=truth_policy,
        consumer_policy=consumer_policy,
        task_quantitative_result=task_quantitative,
        round_index=round_index,
    )
    return batch, response


def run(
    authority_path: Path,
    *,
    executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority_path = authority_path.resolve()
    authority = _json(authority_path)
    paths = validate_authority(authority, authority_path=authority_path)
    output = dict(authority["output_contract"])
    private_root = _resolve(str(output["private_output_root_ref"]))
    public_path = _resolve(str(output["public_result_ref"]))
    capture_root = _resolve(str(output["capture_root_ref"]))
    attempt_ids = [str(value) for value in output["attempt_ids"]]
    recorded_at = _now()

    policy = load_dynamic_single_unit_policy(_json(paths["loop_policy_ref"]))
    source_refs = policy["source_refs"]
    program = _json(_resolve(str(source_refs["request_program_ref"])))
    task_readiness = _json(_resolve(str(source_refs["task_readiness_ref"])))
    truth_policy = _json(_resolve(str(source_refs["truth_spine_policy_ref"])))
    consumer_policy = _json(_resolve(str(source_refs["consumer_policy_ref"])))
    task_quantitative = _json(
        _resolve(str(source_refs["task_quantitative_result_ref"]))
    )
    catalog = compile_request_catalog(
        policy=policy,
        program=program,
        task_readiness=task_readiness,
    )
    runtime_paths = resolve_runtime_paths(ROOT)
    permissions = frozenset({"current_product:read"})
    retrieval_principal = ResearchRetrievalPrincipal("current", permissions)
    evidence_principal = ResearchEvidencePackPrincipal("current", permissions)
    retrieval = ResearchRetrievalService.from_runtime_paths(ROOT, runtime_paths)
    evidence_service = ResearchEvidencePackService.from_runtime_paths(
        ROOT, runtime_paths
    )
    evidence_pack = evidence_service.get_case("DELL", evidence_principal)
    _require(
        evidence_pack.get("pack_payload_digest")
        == authority["bound_inputs"]["current_evidence_pack_payload_digest"],
        "current_dynamic_live_evidence_pack_drift",
    )
    cuda = required_cuda_fp16_receipt(
        purpose="DELL current dynamic single-unit natural live"
    )
    profile = load_chat_completion_profile(_json(paths["provider_profile_ref"]))

    session_seed = {
        "run_id": output["run_id"],
        "authority_sha256": _sha(authority_path),
        "policy_digest": canonical_digest(policy),
        "catalog_digest": catalog["catalog_digest"],
    }
    session_id = "SESSION::" + canonical_digest(session_seed)[:24].upper()
    base_plan_body = {
        "case_key": "DELL",
        "objective_id": policy["objective"]["objective_id"],
        "executed_request_ids": [],
        "next_request_ids": [],
        "latest_reflection_digest": None,
        "latest_feedback_refs": [],
    }
    base_plan = {**base_plan_body, "plan_digest": canonical_digest(base_plan_body)}
    base_graph_digest = canonical_digest(
        {
            "case_key": "DELL",
            "state": "current_reviewed_graph_plus_run_local_hypotheses",
        }
    )
    session = create_agent_session(
        session_id=session_id,
        run_id=str(output["run_id"]),
        case_id="case_dell_current",
        case_version="FIN_0_1_3",
        as_of_date="2026-08-06",
        objective_ref=f"objective://{policy['objective']['objective_id']}",
        active_plan_ref="PLAN::" + base_plan["plan_digest"][:24].upper(),
        created_at=recorded_at,
    )
    events: list[dict[str, Any]] = []
    _event(
        events,
        session_id=session_id,
        event_type="session_created",
        actor_id="S0.CanonicalRuntime",
        occurred_at=recorded_at,
        output_refs=(session_id,),
    )
    messages: list[dict[str, Any]] = list(
        compile_initial_messages(policy=policy, request_catalog=catalog)
    )
    provider_steps: list[dict[str, Any]] = []
    selections: list[dict[str, Any]] = []
    batches: list[dict[str, Any]] = []
    round_responses: list[dict[str, Any]] = []
    feedback_receipts: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    reflection_artifacts: list[dict[str, Any]] = []
    executed_ids: list[str] = []
    accepted_evidence_refs: set[str] = set()
    workpaper: dict[str, Any] = {}
    workpaper_context: dict[str, Any] = {}
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    provider_calls_attempted = 0

    try:
        request_tool = request_evidence_tool(
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=1,
        )
        provider_calls_attempted += 1
        request_step = executor(
            profile=profile,
            messages=messages,
            tools=[request_tool],
            capture_root=capture_root,
            run_id=str(output["run_id"]),
            attempt_id=attempt_ids[0],
            tool_choice=_force_tool(REQUEST_TOOL_NAME),
        )
        provider_steps.append(request_step.as_dict())
        request_payload, request_call_id = _tool_arguments(
            request_step, expected_name=REQUEST_TOOL_NAME
        )
        selection = validate_request_selection(
            request_payload,
            policy=policy,
            request_catalog=catalog,
            executed_request_ids=executed_ids,
            round_index=1,
        )
        selections.append(selection)
        batch, response = _execute_round(
            policy=policy,
            program=program,
            request_ids=selection["request_ids"],
            round_index=1,
            retrieval=retrieval,
            retrieval_principal=retrieval_principal,
            evidence_pack=evidence_pack,
            truth_policy=truth_policy,
            consumer_policy=consumer_policy,
            task_quantitative=task_quantitative,
        )
        batches.append(batch)
        round_responses.append(response)
        executed_ids.extend(selection["request_ids"])
        accepted_evidence_refs.update(
            str(row["evidence_ref"])
            for row in response.get("reviewed_evidence") or ()
        )
        feedback = compile_round_feedback_receipts(
            session_id=session_id,
            round_response=response,
            request_catalog=catalog,
            created_at=recorded_at,
        )
        feedback_receipts.extend(feedback)
        messages.extend(
            [
                request_step.continuation_assistant_message(),
                {
                    "role": "tool",
                    "tool_call_id": request_call_id,
                    "content": json.dumps(
                        {
                            "round_response": public_round_response(response),
                            "feedback_receipts": feedback,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                },
            ]
        )

        maximum_rounds = int(policy["loop_limits"]["maximum_retrieval_rounds"])
        for round_index in range(1, maximum_rounds + 1):
            current_feedback = [
                row
                for row in feedback_receipts
                if str(row.get("round_id") or "") == f"ROUND::{round_index}"
            ]
            reflect_tool = reflection_tool(
                policy=policy,
                request_catalog=catalog,
                feedback_receipts=current_feedback,
                accepted_evidence_refs=sorted(accepted_evidence_refs),
                executed_request_ids=executed_ids,
                round_index=round_index,
            )
            provider_calls_attempted += 1
            reflection_step = executor(
                profile=profile,
                messages=messages,
                tools=[reflect_tool],
                capture_root=capture_root,
                run_id=str(output["run_id"]),
                attempt_id=attempt_ids[round_index],
                tool_choice=_force_tool(REFLECTION_TOOL_NAME),
            )
            provider_steps.append(reflection_step.as_dict())
            reflection_payload, reflection_call_id = _tool_arguments(
                reflection_step, expected_name=REFLECTION_TOOL_NAME
            )
            reflection = validate_reflection_payload(
                reflection_payload,
                policy=policy,
                request_catalog=catalog,
                feedback_receipts=current_feedback,
                accepted_evidence_refs=sorted(accepted_evidence_refs),
                executed_request_ids=executed_ids,
                round_index=round_index,
            )
            reflections.append(reflection)
            open_gap_refs = sorted(
                {
                    str(row["gap_ref"])
                    for current in round_responses
                    for row in current.get("residual_gaps") or ()
                }
            )
            artifacts = compile_reflection_artifacts(
                policy=policy,
                reflection=reflection,
                session_id=session_id,
                agent_id="AGENT::VALUE_CAPTURE",
                base_plan=base_plan,
                base_graph_digest=base_graph_digest,
                executed_request_ids=executed_ids,
                open_gap_refs=open_gap_refs,
                model_calls_used=provider_calls_attempted,
            )
            reflection_artifacts.append(artifacts)
            session = apply_accepted_plan_delta(
                session=session,
                plan_delta=artifacts["plan_delta"],
                expected_base_plan_digest=base_plan["plan_digest"],
                accepted_plan_digest=artifacts["accepted_plan"]["plan_digest"],
                accepted_plan_ref=artifacts["accepted_plan_ref"],
                updated_at=recorded_at,
            )
            base_plan = artifacts["accepted_plan"]
            base_graph_digest = artifacts["graph_delta"]["graph_delta_digest"]
            _event(
                events,
                session_id=session_id,
                event_type="plan_delta_accepted",
                actor_id="S3.DynamicSingleUnitHarness",
                occurred_at=recorded_at,
                attempt_id=attempt_ids[round_index],
                output_refs=(artifacts["accepted_plan_ref"],),
                feedback_refs=reflection["feedback_refs"],
            )
            decision = str(reflection["proposed_stop_decision"])
            if decision != "continue":
                messages.extend(
                    [
                        reflection_step.continuation_assistant_message(),
                        {
                            "role": "tool",
                            "tool_call_id": reflection_call_id,
                            "content": json.dumps(
                                {
                                    "accepted": True,
                                    "stop_decision": artifacts["stop_decision"],
                                },
                                ensure_ascii=False,
                                sort_keys=True,
                                separators=(",", ":"),
                            ),
                        },
                    ]
                )
                break

            next_ids = list(reflection["next_request_ids"])
            batch, response = _execute_round(
                policy=policy,
                program=program,
                request_ids=next_ids,
                round_index=round_index + 1,
                retrieval=retrieval,
                retrieval_principal=retrieval_principal,
                evidence_pack=evidence_pack,
                truth_policy=truth_policy,
                consumer_policy=consumer_policy,
                task_quantitative=task_quantitative,
            )
            batches.append(batch)
            round_responses.append(response)
            executed_ids.extend(next_ids)
            accepted_evidence_refs.update(
                str(row["evidence_ref"])
                for row in response.get("reviewed_evidence") or ()
            )
            feedback = compile_round_feedback_receipts(
                session_id=session_id,
                round_response=response,
                request_catalog=catalog,
                created_at=recorded_at,
            )
            feedback_receipts.extend(feedback)
            messages.extend(
                [
                    reflection_step.continuation_assistant_message(),
                    {
                        "role": "tool",
                        "tool_call_id": reflection_call_id,
                        "content": json.dumps(
                            {
                                "accepted_plan_delta": artifacts["plan_delta"],
                                "next_round_response": public_round_response(response),
                                "feedback_receipts": feedback,
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    },
                ]
            )
        _require(
            bool(reflection_artifacts)
            and reflection_artifacts[-1]["stop_decision"]["decision"]
            in {"stop_sufficient", "stop_no_progress"},
            "current_dynamic_live_terminal_stop_missing",
        )
        workpaper_context = compile_workpaper_context(
            policy=policy,
            round_responses=round_responses,
            feedback_receipts=feedback_receipts,
            reflections=reflections,
            stop_decision=reflection_artifacts[-1]["stop_decision"],
        )
        provider_calls_attempted += 1
        workpaper_step = executor(
            profile=profile,
            messages=compile_specialist_workpaper_messages(
                context=workpaper_context
            ),
            tools=[
                specialist_workpaper_tool(
                    agent_id="AGENT::VALUE_CAPTURE",
                    context=workpaper_context,
                )
            ],
            capture_root=capture_root,
            run_id=str(output["run_id"]),
            attempt_id=attempt_ids[3],
            tool_choice=_force_tool("submit_specialist_workpaper"),
        )
        provider_steps.append(workpaper_step.as_dict())
        workpaper_payload, _ = _tool_arguments(
            workpaper_step, expected_name="submit_specialist_workpaper"
        )
        workpaper = validate_specialist_workpaper(
            workpaper_payload,
            context=workpaper_context,
            expected_agent_id="AGENT::VALUE_CAPTURE",
        )
        workpaper["workpaper_digest"] = canonical_digest(workpaper)
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except ResearchRetrievalServiceError as exc:
        failure_phase = "current_S1_S2_retrieval"
        failure_code = exc.error_code
    except ResearchEvidencePackServiceError as exc:
        failure_phase = "current_reviewed_evidence_pack"
        failure_code = exc.error_code
    except DynamicSingleUnitLoopError as exc:
        failure_phase = "dynamic_research_loop_contract"
        failure_code = exc.code
    except MultiAgentPreviewError as exc:
        failure_phase = "specialist_workpaper_contract"
        failure_code = str(exc)
    except CurrentDynamicSingleUnitLiveError as exc:
        failure_phase = "current_dynamic_live_orchestration"
        failure_code = exc.code

    succeeded = bool(workpaper)
    status = (
        "completed_current_dynamic_single_unit_contract_valid_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    full_body: dict[str, Any] = {
        "schema_version": FULL_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "session": session,
        "session_events": events,
        "initial_messages_digest": canonical_digest(
            list(compile_initial_messages(policy=policy, request_catalog=catalog))
        ),
        "provider_steps": [_public_provider_step(row) for row in provider_steps],
        "selections": selections,
        "round_batches": batches,
        "round_responses": [public_round_response(row) for row in round_responses],
        "feedback_receipts": feedback_receipts,
        "reflections": reflections,
        "reflection_artifacts": reflection_artifacts,
        "workpaper_context": workpaper_context,
        "workpaper": workpaper,
        "execution": {
            "provider_calls_attempted": provider_calls_attempted,
            "maximum_provider_calls": 4,
            "retrieval_rounds_executed": len(round_responses),
            "request_ids_executed": executed_ids,
            "unique_request_ids_executed": len(set(executed_ids)),
            "candidate_promotions": 0,
            "external_source_network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "cuda_receipt": cuda,
        },
        "failure": {
            "phase": failure_phase,
            "code": failure_code,
            "capture_ref": (
                _relative(failure_capture_ref) if failure_capture_ref else ""
            ),
        },
        "claims": {
            "natural_dynamic_research_executed": succeeded,
            "initial_evidence_prefeed": False,
            "model_selected_initial_research_actions": bool(selections),
            "model_consumed_feedback_and_submitted_reflection": bool(reflections),
            "model_changed_plan": any(
                row.get("proposed_stop_decision") == "continue"
                and bool(row.get("next_request_ids"))
                for row in reflections
            ),
            "current_S1_S2_executed": bool(round_responses),
            "model_generated_specialist_judgment": succeeded,
            "single_unit_only": True,
            "multi_agent_execution": False,
            "S1_pass": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_new(private_root / "full_result.json", full)
    public_body = {
        "schema_version": PUBLIC_RESULT_SCHEMA,
        "status": status,
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "model": profile.model,
        "execution": full["execution"],
        "provider_steps": provider_steps,
        "selections": selections,
        "round_summaries": [
            {
                "round_id": row["round_id"],
                "reviewed_evidence_count": len(row.get("reviewed_evidence") or ()),
                "numeric_fact_count": len(row.get("numeric_facts") or ()),
                "numeric_relation_count": len(row.get("numeric_relations") or ()),
                "residual_gap_count": len(row.get("residual_gaps") or ()),
                "authority": row.get("authority"),
            }
            for row in round_responses
        ],
        "reflections": reflections,
        "coverage_state": (
            reflection_artifacts[-1]["coverage_state"]
            if reflection_artifacts
            else {}
        ),
        "stop_decision": (
            reflection_artifacts[-1]["stop_decision"]
            if reflection_artifacts
            else {}
        ),
        "workpaper": workpaper,
        "failure": full["failure"],
        "claims": full["claims"],
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "dynamic_single_unit_contract_pass": succeeded,
            "L1_assessment_pending": succeeded,
            "eight_dimension_content_assessment_pending": succeeded,
            "multi_agent_execution": False,
            "S3_pass": False,
            "product_acceptance": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_path, public)
    return public


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run(args.authority.resolve())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"].startswith("completed_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
