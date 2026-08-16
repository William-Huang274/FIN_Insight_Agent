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
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)
from sec_agent.providers.chat_completions import (  # noqa: E402
    ChatCompletionResult,
    ChatCompletionToolStepResult,
    ModelGatewayError,
    execute_chat_completion_exact_once,
    execute_chat_completion_tool_step_exact_once,
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    BoundedFinanceLoopError,
    MICRO_JUDGMENT_TOOL_NAMES,
    SUBMIT_RESEARCH_THESIS_TOOL,
    compile_finance_micro_fragment_analysis_messages,
    compile_finance_micro_fragment_context,
    compile_finance_micro_fragment_submission_messages,
    compile_finance_micro_judgment_fragments,
    compile_finance_micro_judgment_tools,
    load_bounded_finance_loop_policy,
    load_dynamic_micro_judgment_policy,
    scope_bounded_finance_micro_judgment_policy,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_node_profile,
    validate_deepseek_ga_profile,
    validate_finance_micro_judgment_fragment,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_claim_surface_projection,
    compile_dynamic_research_input_projection,
)
from sec_agent.research.dynamic_truth_spine import (  # noqa: E402
    DynamicTruthSpineError,
)
from sec_agent.research.planning import (  # noqa: E402
    ResearchPlanningError,
    compile_research_objective,
    compile_research_plan,
    compile_research_planner_messages,
    load_research_planning_policy,
    parse_research_planner_output,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest,
)
from sec_agent.runtime_bridge.paths import resolve_runtime_paths  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    read_registered_runtime_json,
)


AUTHORITY_SCHEMA = "fin_ia_s3_dynamic_single_cell_live_authority_v1_0"
AUTHORITY_STATUS = "signed_exact_once_DELL_dynamic_value_capture_chat_live"
RESULT_SCHEMA = "fin_ia_s3_dynamic_single_cell_live_result_v1_0"
FULL_RESULT_SCHEMA = "fin_ia_s3_dynamic_single_cell_live_full_v1_0"
SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_authority_v1_1"
)
SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_counter_analysis_submission_successor"
)
SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_result_v1_1"
)
SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_full_v1_1"
)


class DynamicSingleCellLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise DynamicSingleCellLiveError("dynamic_live_path_invalid")
    path = (ROOT / Path(*relative.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise DynamicSingleCellLiveError("dynamic_live_path_outside_repo") from exc
    return path


def _relative(path: str | Path) -> str:
    return Path(path).resolve().relative_to(ROOT).as_posix()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


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
    if not re.fullmatch(r"[0-9a-f]{40}", commit.lower()):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_historical_commit_invalid"
        )
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise DynamicSingleCellLiveError(
            f"dynamic_successor_historical_blob_missing:{ref}"
        )
    return hashlib.sha256(completed.stdout).hexdigest()


def _validate_historical_authority_inputs(
    authority: Mapping[str, Any],
) -> None:
    commit = str(authority.get("implementation_commit") or "").lower()
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_historical_bound_inputs_invalid"
        )
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if not ref_keys:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_historical_bound_inputs_invalid"
        )
    for key in sorted(ref_keys):
        ref = str(bound.get(key) or "")
        expected_sha = str(bound.get(key[:-4] + "_sha256") or "")
        if (
            not re.fullmatch(r"[0-9a-f]{64}", expected_sha.lower())
            or _git_blob_sha256(commit=commit, ref=ref) != expected_sha
        ):
            raise DynamicSingleCellLiveError(
                f"dynamic_successor_historical_bound_input_drift:{key}"
            )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _services() -> tuple[ResearchEvidencePackService, ResearchRetrievalService]:
    paths = resolve_runtime_paths(ROOT)
    return (
        ResearchEvidencePackService.from_runtime_paths(ROOT, paths),
        ResearchRetrievalService.from_runtime_paths(ROOT, paths),
    )


def _runtime_contracts():
    kernel = load_financial_research_kernel(
        read_registered_runtime_json(
            ROOT, "application.config.current_financial_research_kernel"
        )
    )
    route = load_query_object_fact_route_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_query_object_fact_route_policy"
        ),
        kernel,
    )
    planning = load_research_planning_policy(
        read_registered_runtime_json(
            ROOT, "application.config.current_research_planning_policy"
        ),
        route,
    )
    return kernel, route, planning


def _bound_paths(authority: Mapping[str, Any]) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicSingleCellLiveError("dynamic_live_bound_inputs_invalid")
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "claim_authority_template_ref",
        "claim_surface_template_ref",
        "loop_policy_ref",
        "dynamic_micro_policy_ref",
        "planner_profile_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "zero_call_result_ref",
        "scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "bounded_loop_ref",
        "provider_transport_ref",
        "loop_policy_ref",
        "dynamic_micro_policy_ref",
    }
    ref_keys = {key for key in bound if key.endswith("_ref")}
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "zero_call_result_digest",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicSingleCellLiveError("dynamic_live_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicSingleCellLiveError(
                f"dynamic_live_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _compile_planner_contract(paths: Mapping[str, Path]):
    kernel, route, planning = _runtime_contracts()
    objective = compile_research_objective(
        _json(paths["objective_ref"]), kernel=kernel, policy=planning
    )
    messages = compile_research_planner_messages(
        objective=objective,
        kernel=kernel,
        route_policy=route,
        planning_policy=planning,
    )
    return kernel, route, planning, objective, messages


def validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status") == AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
    ):
        raise DynamicSingleCellLiveError("dynamic_live_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicSingleCellLiveError("dynamic_live_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicSingleCellLiveError("dynamic_live_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicSingleCellLiveError("dynamic_live_upstream_drift")
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicSingleCellLiveError("dynamic_live_worktree_not_clean")

    expected_budget = {
        "maximum_model_calls": 7,
        "maximum_transport_attempts": 7,
        "maximum_planner_calls": 1,
        "maximum_fragment_analysis_calls": 3,
        "maximum_fragment_submission_calls": 3,
        "maximum_evidence_requests": 8,
        "maximum_tool_calls": 3,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise DynamicSingleCellLiveError("dynamic_live_budget_invalid")
    paths = _bound_paths(payload)
    zero = _json(paths["zero_call_result_ref"])
    decision = _json(paths["scope_decision_ref"])
    bound = payload["bound_inputs"]
    zero_valid = (
        zero.get("schema_version")
        == "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_2"
        and zero.get("status")
        == "zero_call_dynamic_truth_spine_engineering_pass"
        and zero.get("result_digest") == bound["zero_call_result_digest"]
        and zero.get("observed_counts", {}).get("model_calls") == 0
        and zero.get("stage_acceptance", {}).get(
            "dynamic_dell_terminal_deliverable_compiled"
        )
        is True
        and zero.get("stage_acceptance", {}).get(
            "natural_model_planner_executed"
        )
        is False
        and zero.get("stage_acceptance", {}).get(
            "natural_model_judgment_executed"
        )
        is False
    )
    decision_valid = (
        decision.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_scope_decision_v1_0"
        and decision.get("status")
        == "approved_one_honest_DELL_SEC_only_dynamic_single_cell"
        and decision.get("case_key") == "DELL"
        and decision.get("cell_id") == "CELL::value_capture"
        and decision.get("execution_budget") == expected_budget
        and decision.get("natural_planner_required") is True
        and decision.get("current_S1_S2_execution_required") is True
        and decision.get("candidate_promotion_forbidden") is True
        and decision.get("transcript_prefeed_forbidden") is True
        and decision.get("S1_RC_S1_019_remains_open") is True
        and decision.get("five_cell_authorized") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
    )
    kernel, route, planning, objective, messages = _compile_planner_contract(
        paths
    )
    del kernel, route, planning
    if not (
        zero_valid
        and decision_valid
        and objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages))
        == bound["planner_messages_digest"]
    ):
        raise DynamicSingleCellLiveError("dynamic_live_predecessor_invalid")

    planner_profile = load_chat_completion_profile(
        _json(paths["planner_profile_ref"])
    )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_json_profile(planner_profile)
    validate_deepseek_ga_node_profile(
        analysis_profile, node_class="bounded_financial_analysis"
    )
    validate_deepseek_ga_node_profile(
        submission_profile, node_class="contract_submission_non_thinking"
    )

    output = payload.get("output_contract")
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "planner_attempt_id",
        "fragment_attempt_ids",
        "product_publication",
    }
    attempts = output.get("fragment_attempt_ids") if isinstance(output, Mapping) else None
    if not (
        isinstance(output, Mapping)
        and set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output
            - {"fragment_attempt_ids", "product_publication"}
        )
        and isinstance(attempts, Mapping)
        and set(attempts) == set(MICRO_JUDGMENT_TOOL_NAMES)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"analysis_attempt_id", "submission_attempt_id"}
            and all(str(value or "") for value in row.values())
            for row in attempts.values()
        )
        and len(
            {
                str(value)
                for row in attempts.values()
                for value in row.values()
            }
            | {str(output["planner_attempt_id"])}
        )
        == 7
    ):
        raise DynamicSingleCellLiveError("dynamic_live_output_invalid")
    capture_run = _resolve(str(output["capture_root_ref"])) / str(
        output["run_id"]
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicSingleCellLiveError("dynamic_live_identity_consumed")
    return paths


def _public_provider_step(value: Mapping[str, Any]) -> dict[str, Any]:
    if not value:
        return {}
    return {
        "finish_reason": value.get("finish_reason", ""),
        "usage": value.get("usage", {}),
        "request_digest": value.get("request_digest", ""),
        "response_digest": value.get("response_digest", ""),
        "request_capture_ref": (
            _relative(str(value["request_capture_ref"]))
            if value.get("request_capture_ref")
            else ""
        ),
        "response_capture_ref": (
            _relative(str(value["response_capture_ref"]))
            if value.get("response_capture_ref")
            else ""
        ),
    }


def _tool_arguments(
    result: ChatCompletionToolStepResult, *, expected_tool: str
) -> Mapping[str, Any]:
    if result.finish_reason == "length":
        raise DynamicSingleCellLiveError("dynamic_live_submission_length_stop")
    if len(result.tool_calls) != 1:
        raise DynamicSingleCellLiveError(
            "dynamic_live_submission_tool_call_count_invalid"
        )
    function = result.tool_calls[0].get("function")
    if not (
        isinstance(function, Mapping) and function.get("name") == expected_tool
    ):
        raise DynamicSingleCellLiveError("dynamic_live_submission_tool_invalid")
    try:
        arguments = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise DynamicSingleCellLiveError(
            "dynamic_live_submission_arguments_json_invalid"
        ) from exc
    if not isinstance(arguments, Mapping):
        raise DynamicSingleCellLiveError(
            "dynamic_live_submission_arguments_invalid"
        )
    return arguments


def _require_controlled_plan_binding(
    controlled_plan: Mapping[str, Any], *, expected_plan_digest: str
) -> None:
    if (
        controlled_plan.get("compiled_plan", {}).get("plan_digest")
        != expected_plan_digest
    ):
        raise DynamicSingleCellLiveError("dynamic_live_plan_digest_drift")


def _successor_bound_paths(authority: Mapping[str, Any]) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_bound_inputs_invalid"
        )
    required_refs = {
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "failure_assessment_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "runner_ref",
        "bounded_loop_ref",
        "provider_transport_ref",
    }
    scalar_keys = {
        "predecessor_public_result_digest",
        "predecessor_private_result_digest",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    if set(bound) != expected:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(
            bound[key[:-4] + "_sha256"]
        ):
            raise DynamicSingleCellLiveError(
                f"dynamic_successor_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _compile_successor_replay_state(
    predecessor_full: Mapping[str, Any],
) -> dict[str, Any]:
    surface_input = (
        predecessor_full.get("surface_projection") or {}
    ).get("claim_surface_research_input") or {}
    accepted_fragments = deepcopy(
        dict(predecessor_full.get("accepted_fragments") or {})
    )
    required_prefix = {
        "submit_research_thesis",
        "submit_research_mechanism",
    }
    if (
        not surface_input
        or set(accepted_fragments) != required_prefix
        or any(not accepted_fragments[key] for key in required_prefix)
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_predecessor_prefix_invalid"
        )
    failed_rows = [
        row
        for row in predecessor_full.get("fragment_steps") or ()
        if row.get("fragment_tool")
        == "submit_research_counterargument_and_wwc"
    ]
    if len(failed_rows) != 1:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_failed_fragment_state_invalid"
        )
    prior_failed_row = failed_rows[0]
    context = compile_finance_micro_fragment_context(
        research_input=surface_input,
        cell_id="CELL::value_capture",
        tool_name="submit_research_counterargument_and_wwc",
        accepted_fragments=accepted_fragments,
    )
    messages = compile_finance_micro_fragment_analysis_messages(context)
    if not (
        context.get("projection_digest")
        == (prior_failed_row.get("fragment_context") or {}).get(
            "projection_digest"
        )
        and canonical_digest(list(messages))
        == prior_failed_row.get("analysis_messages_digest")
        and not prior_failed_row.get("analysis_step")
        and not prior_failed_row.get("submission_step")
        and not prior_failed_row.get("validated_fragment")
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_failed_fragment_replay_drift"
        )
    return {
        "surface_input": surface_input,
        "accepted_fragments": accepted_fragments,
        "fragment_context": context,
        "analysis_messages": messages,
        "analysis_messages_digest": canonical_digest(list(messages)),
        "predecessor_fragment_context_digest": context[
            "projection_digest"
        ],
    }


def validate_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status") == SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and payload.get("cell_id") == "CELL::value_capture"
        and payload.get("failed_fragment_tool")
        == "submit_research_counterargument_and_wwc"
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicSingleCellLiveError("dynamic_successor_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_worktree_not_clean"
        )

    expected_budget = {
        "successful_predecessor_model_nodes_reused": 5,
        "maximum_fresh_model_calls": 2,
        "maximum_transport_attempts": 2,
        "maximum_counter_analysis_calls": 1,
        "maximum_counter_submission_calls": 1,
        "maximum_analysis_completion_tokens": 16000,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if payload.get("execution_budget") != expected_budget:
        raise DynamicSingleCellLiveError(
            "dynamic_successor_budget_invalid"
        )
    paths = _successor_bound_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    _validate_historical_authority_inputs(predecessor_authority)
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    assessment = _json(paths["failure_assessment_ref"])
    if not (
        predecessor_authority.get("schema_version") == AUTHORITY_SCHEMA
        and predecessor_public.get("schema_version") == RESULT_SCHEMA
        and predecessor_public.get("status") == "terminal_failed_no_retry"
        and predecessor_public.get("result_digest")
        == bound["predecessor_public_result_digest"]
        and predecessor_public.get("failure_code")
        == "model_gateway_generation_budget_exhausted"
        and predecessor_public.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (predecessor_public.get("execution") or {}).get(
            "model_calls_attempted"
        )
        == 6
        and (predecessor_public.get("execution") or {}).get(
            "fragment_tool_calls_accepted"
        )
        == 2
        and predecessor_full.get("schema_version") == FULL_RESULT_SCHEMA
        and predecessor_full.get("status") == "terminal_failed_no_retry"
        and predecessor_full.get("full_result_digest")
        == bound["predecessor_private_result_digest"]
        and assessment.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_failure_assessment_v1_0"
        and assessment.get("status")
        == "terminal_failed_counter_WWC_analysis_generation_budget_exhausted"
        and (assessment.get("successor_disposition") or {}).get(
            "maximum_fresh_model_calls"
        )
        == 2
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_predecessor_invalid"
        )
    _compile_successor_replay_state(predecessor_full)

    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    validate_deepseek_ga_node_profile(
        submission_profile, node_class="contract_submission_non_thinking"
    )

    output = payload.get("output_contract")
    required_output = {
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
        "run_id",
        "analysis_attempt_id",
        "submission_attempt_id",
        "product_publication",
    }
    if not (
        isinstance(output, Mapping)
        and set(output) == required_output
        and output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output - {"product_publication"}
        )
        and output.get("analysis_attempt_id")
        != output.get("submission_attempt_id")
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_output_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(
        output["run_id"]
    )
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicSingleCellLiveError(
            "dynamic_successor_identity_consumed"
        )
    return paths


def run(
    authority_path: Path,
    *,
    planner_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    analysis_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    submission_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_authority(authority, authority_path=authority_path)
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    kernel, route, planning, objective, planner_messages = (
        _compile_planner_contract(paths)
    )
    planner_profile = load_chat_completion_profile(
        _json(paths["planner_profile_ref"])
    )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    evidence_service, retrieval_service = _services()
    permissions = frozenset({"current_product:read"})

    planner_step: dict[str, Any] = {}
    planner_output: dict[str, Any] = {}
    compiled_plan: dict[str, Any] = {}
    controlled_plan: dict[str, Any] = {}
    evidence_pack: dict[str, Any] = {}
    dynamic_projection: dict[str, Any] = {}
    surface_projection: dict[str, Any] = {}
    fragment_steps: list[dict[str, Any]] = []
    accepted_fragments: dict[str, dict[str, Any]] = {}
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}
    model_calls_attempted = 0
    failure_phase = ""
    failure_code = ""
    failure_fragment_tool = ""
    failure_capture_ref = ""

    try:
        model_calls_attempted += 1
        planner_result = planner_executor(
            profile=planner_profile,
            messages=planner_messages,
            capture_root=capture_root,
            run_id=run_id,
            attempt_id=str(output["planner_attempt_id"]),
        )
        planner_step = planner_result.as_dict()
        if planner_result.finish_reason != "stop":
            raise DynamicSingleCellLiveError("dynamic_live_planner_finish_invalid")
        planner_output = parse_research_planner_output(planner_result.content)
        compiled = compile_research_plan(
            planner_output,
            objective=objective,
            kernel=kernel,
            route_policy=route,
            planning_policy=planning,
        )
        compiled_plan = compiled.as_dict()
        controlled_plan = retrieval_service.execute_controlled_plan(
            "DELL",
            _json(paths["objective_ref"]),
            planner_output,
            ResearchRetrievalPrincipal("current", permissions),
        )
        _require_controlled_plan_binding(
            controlled_plan, expected_plan_digest=compiled.plan_digest
        )
        evidence_pack = evidence_service.get_case(
            "DELL", ResearchEvidencePackPrincipal("current", permissions)
        )
        dynamic_projection = compile_dynamic_research_input_projection(
            truth_spine_policy=_json(paths["truth_spine_policy_ref"]),
            consumer_policy=_json(paths["consumer_policy_ref"]),
            controlled_plan=controlled_plan,
            evidence_pack=evidence_pack,
        )
        dynamic_input = dynamic_projection["dynamic_research_input"]
        if not dynamic_input:
            raise DynamicSingleCellLiveError(
                "dynamic_live_no_reviewed_evidence_selected"
            )
        surface_projection = compile_dynamic_claim_surface_projection(
            dynamic_research_input=dynamic_input,
            claim_authority_template=_json(
                paths["claim_authority_template_ref"]
            ),
            claim_surface_template=_json(
                paths["claim_surface_template_ref"]
            ),
        )
        surface_input = surface_projection["claim_surface_research_input"]
        micro_policy = load_dynamic_micro_judgment_policy(
            _json(paths["dynamic_micro_policy_ref"])
        )
        scoped = scope_bounded_finance_micro_judgment_policy(
            load_bounded_finance_loop_policy(_json(paths["loop_policy_ref"])),
            micro_policy=micro_policy,
            cell_count=1,
            maximum_evidence_requests=0,
        )
        tools = compile_finance_micro_judgment_tools(
            research_input=surface_input,
            required_cell_ids=["CELL::value_capture"],
            kernel=kernel,
            route_policy=route,
            policy=scoped,
            strict=True,
        )
        tool_by_name = {row["function"]["name"]: row for row in tools}
        for tool_name in MICRO_JUDGMENT_TOOL_NAMES:
            failure_fragment_tool = tool_name
            context = compile_finance_micro_fragment_context(
                research_input=surface_input,
                cell_id="CELL::value_capture",
                tool_name=tool_name,
                accepted_fragments=accepted_fragments,
            )
            analysis_messages = compile_finance_micro_fragment_analysis_messages(
                context
            )
            attempts = output["fragment_attempt_ids"][tool_name]
            row: dict[str, Any] = {
                "fragment_tool": tool_name,
                "fragment_context": context,
                "analysis_messages_digest": canonical_digest(
                    list(analysis_messages)
                ),
                "submission_messages_digest": "",
                "analysis_step": {},
                "submission_step": {},
                "validated_fragment": {},
            }
            fragment_steps.append(row)
            model_calls_attempted += 1
            analysis = analysis_executor(
                profile=analysis_profile,
                messages=analysis_messages,
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=str(attempts["analysis_attempt_id"]),
            )
            row["analysis_step"] = analysis.as_dict()
            if analysis.finish_reason == "length":
                raise DynamicSingleCellLiveError(
                    "dynamic_live_fragment_analysis_length_stop"
                )
            submission_messages = compile_finance_micro_fragment_submission_messages(
                fragment_context=context,
                analysis_draft=analysis.content,
            )
            row["submission_messages_digest"] = canonical_digest(
                list(submission_messages)
            )
            model_calls_attempted += 1
            submission = submission_executor(
                profile=submission_profile,
                messages=submission_messages,
                tools=[tool_by_name[tool_name]],
                capture_root=capture_root,
                run_id=run_id,
                attempt_id=str(attempts["submission_attempt_id"]),
                tool_choice=None,
            )
            row["submission_step"] = submission.as_dict()
            validated = validate_finance_micro_judgment_fragment(
                tool_name=tool_name,
                arguments=_tool_arguments(
                    submission, expected_tool=tool_name
                ),
                research_input=surface_input,
                cell_id="CELL::value_capture",
                thesis_fragment=accepted_fragments.get(
                    SUBMIT_RESEARCH_THESIS_TOOL
                ),
            )
            accepted_fragments[tool_name] = validated
            row["validated_fragment"] = validated
        cell = next(
            row
            for row in surface_input["cells"]
            if row["cell_id"] == "CELL::value_capture"
        )
        terminal = compile_finance_micro_judgment_fragments(
            accepted_fragments, cell=cell
        )
        judgment_output = {"cells": [terminal]}
        structured_deliverable = compile_current_research_deliverable(
            research_input=surface_input,
            judgment_output=judgment_output,
            required_cell_ids=["CELL::value_capture"],
        )
        failure_fragment_tool = ""
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except ResearchPlanningError as exc:
        failure_phase = "natural_planner_contract"
        failure_code = str(exc)
    except ResearchRetrievalServiceError as exc:
        failure_phase = "current_S1_S2_retrieval"
        failure_code = exc.error_code
    except ResearchEvidencePackServiceError as exc:
        failure_phase = "current_reviewed_evidence_pack"
        failure_code = exc.error_code
    except DynamicTruthSpineError as exc:
        failure_phase = "dynamic_truth_spine"
        failure_code = str(exc)
    except BoundedFinanceLoopError as exc:
        failure_phase = "dynamic_fragment_or_terminal_validation"
        failure_code = str(exc)
    except CurrentResearchConsumerError as exc:
        failure_phase = "dynamic_deliverable_validation"
        failure_code = exc.code
    except DynamicSingleCellLiveError as exc:
        failure_phase = "dynamic_live_orchestration"
        failure_code = exc.code

    succeeded = bool(structured_deliverable)
    status = (
        "completed_dynamic_single_cell_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    full_body: dict[str, Any] = {
        "schema_version": FULL_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "objective": objective.as_dict(),
        "planner_messages_digest": canonical_digest(list(planner_messages)),
        "planner_step": planner_step,
        "planner_output": planner_output,
        "compiled_plan": compiled_plan,
        "controlled_plan": controlled_plan,
        "evidence_pack_binding": {
            "artifact_digest": evidence_pack.get("artifact_digest", ""),
            "pack_payload_digest": evidence_pack.get("pack_payload_digest", ""),
        },
        "dynamic_projection": dynamic_projection,
        "surface_projection": surface_projection,
        "fragment_steps": fragment_steps,
        "accepted_fragments": accepted_fragments,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_fragment_tool": failure_fragment_tool,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "model_calls_attempted": model_calls_attempted,
            "maximum_model_calls": 7,
            "planner_calls_completed": int(bool(planner_output)),
            "fragment_tool_calls_accepted": len(accepted_fragments),
            "current_S1_S2_executed": bool(controlled_plan),
            "external_source_network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "protocol_switches": 0,
            "candidate_promotions": int(
                (dynamic_projection or {}).get("candidate_promotions") or 0
            ),
            "product_publication": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_new(private_root / "full_result.json", full)

    responses = (dynamic_projection or {}).get("evidence_responses") or {}
    surface_input = (surface_projection or {}).get(
        "claim_surface_research_input"
    ) or {}
    terminal = (judgment_output.get("cells") or [{}])[0]
    public_body: dict[str, Any] = {
        "schema_version": RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "objective_id": objective.objective_id,
        "planner": {
            "provider_step": _public_provider_step(planner_step),
            "proposed_atom_count": len(compiled_plan.get("proposed_atoms", ())),
            "selected_atom_count": len(compiled_plan.get("planner_atoms", ())),
            "deferred_atom_count": len(compiled_plan.get("deferred_atoms", ())),
            "plan_digest": compiled_plan.get("plan_digest", ""),
        },
        "evidence_response_summary": responses.get("summary", {}),
        "evidence_response_set_digest": responses.get(
            "evidence_response_set_digest", ""
        ),
        "dynamic_research_input_digest": (
            (dynamic_projection.get("dynamic_research_input") or {}).get(
                "research_input_digest", ""
            )
            if dynamic_projection
            else ""
        ),
        "claim_surface_input_digest": surface_input.get(
            "research_input_digest", ""
        ),
        "allowed_claim_relation_refs": [
            row.get("claim_relation_ref", "")
            for row in (
                (surface_projection or {}).get(
                    "dynamic_claim_surface_policy", {}
                ).get("allowed_structured_claim_combinations", ())
            )
        ],
        "fragment_steps": [
            {
                "fragment_tool": row["fragment_tool"],
                "fragment_context_digest": row["fragment_context"].get(
                    "projection_digest", ""
                ),
                "analysis_messages_digest": row[
                    "analysis_messages_digest"
                ],
                "submission_messages_digest": row[
                    "submission_messages_digest"
                ],
                "analysis": _public_provider_step(row["analysis_step"]),
                "submission": _public_provider_step(row["submission_step"]),
                "validated_fragment_digest": (
                    canonical_digest(row["validated_fragment"])
                    if row["validated_fragment"]
                    else ""
                ),
            }
            for row in fragment_steps
        ],
        "terminal_disposition": {
            "judgment_status": terminal.get("judgment_status", ""),
            "inference_authority": terminal.get("inference_authority", ""),
            "causal_bridge_authority": terminal.get(
                "causal_bridge_authority", ""
            ),
        },
        "terminal_judgment_digest": (
            canonical_digest(terminal) if terminal else ""
        ),
        "deliverable_digest": structured_deliverable.get(
            "deliverable_digest", ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_fragment_tool": failure_fragment_tool,
        "failure_capture_ref": full["failure_capture_ref"],
        "execution": full["execution"],
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "natural_planner_executed": bool(planner_output),
            "current_S1_S2_EvidenceResponse_executed": bool(responses),
            "natural_dynamic_judgment_executed": succeeded,
            "single_cell_contract_pass": succeeded,
            "L1_content_assessment_pending": succeeded,
            "five_cell_execution": False,
            "heterogeneous_generalization": False,
            "qualified_human_acceptance": False,
            "s3_product_acceptance": False,
            "workbench_publication": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), public)
    return public


def run_successor(
    authority_path: Path,
    *,
    analysis_executor: Callable[..., ChatCompletionResult] = (
        execute_chat_completion_exact_once
    ),
    submission_executor: Callable[..., ChatCompletionToolStepResult] = (
        execute_chat_completion_tool_step_exact_once
    ),
) -> dict[str, Any]:
    authority = _json(authority_path)
    paths = validate_successor_authority(
        authority, authority_path=authority_path
    )
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    replay = _compile_successor_replay_state(predecessor_full)
    surface_input = replay["surface_input"]
    accepted_fragments = replay["accepted_fragments"]
    fragment_context = replay["fragment_context"]
    analysis_messages = replay["analysis_messages"]
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    kernel, route, _ = _runtime_contracts()
    micro_policy = load_dynamic_micro_judgment_policy(
        _json(paths["dynamic_micro_policy_ref"])
    )
    scoped = scope_bounded_finance_micro_judgment_policy(
        load_bounded_finance_loop_policy(
            _json(paths["loop_policy_ref"])
        ),
        micro_policy=micro_policy,
        cell_count=1,
        maximum_evidence_requests=0,
    )
    tools = compile_finance_micro_judgment_tools(
        research_input=surface_input,
        required_cell_ids=["CELL::value_capture"],
        kernel=kernel,
        route_policy=route,
        policy=scoped,
        strict=True,
    )
    tool_name = "submit_research_counterargument_and_wwc"
    tool_by_name = {row["function"]["name"]: row for row in tools}

    analysis_step: dict[str, Any] = {}
    submission_step: dict[str, Any] = {}
    validated_fragment: dict[str, Any] = {}
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}
    submission_messages_digest = ""
    model_calls_attempted = 0
    failure_phase = ""
    failure_code = ""
    failure_capture_ref = ""
    try:
        model_calls_attempted += 1
        analysis = analysis_executor(
            profile=analysis_profile,
            messages=analysis_messages,
            capture_root=capture_root,
            run_id=str(output["run_id"]),
            attempt_id=str(output["analysis_attempt_id"]),
        )
        analysis_step = analysis.as_dict()
        if analysis.finish_reason == "length":
            raise DynamicSingleCellLiveError(
                "dynamic_successor_analysis_length_stop"
            )
        submission_messages = compile_finance_micro_fragment_submission_messages(
            fragment_context=fragment_context,
            analysis_draft=analysis.content,
        )
        submission_messages_digest = canonical_digest(
            list(submission_messages)
        )
        model_calls_attempted += 1
        submission = submission_executor(
            profile=submission_profile,
            messages=submission_messages,
            tools=[tool_by_name[tool_name]],
            capture_root=capture_root,
            run_id=str(output["run_id"]),
            attempt_id=str(output["submission_attempt_id"]),
            tool_choice=None,
        )
        submission_step = submission.as_dict()
        validated_fragment = validate_finance_micro_judgment_fragment(
            tool_name=tool_name,
            arguments=_tool_arguments(
                submission, expected_tool=tool_name
            ),
            research_input=surface_input,
            cell_id="CELL::value_capture",
            thesis_fragment=accepted_fragments[
                SUBMIT_RESEARCH_THESIS_TOOL
            ],
        )
        accepted_fragments[tool_name] = validated_fragment
        cell = next(
            row
            for row in surface_input["cells"]
            if row["cell_id"] == "CELL::value_capture"
        )
        terminal = compile_finance_micro_judgment_fragments(
            accepted_fragments, cell=cell
        )
        judgment_output = {"cells": [terminal]}
        structured_deliverable = compile_current_research_deliverable(
            research_input=surface_input,
            judgment_output=judgment_output,
            required_cell_ids=["CELL::value_capture"],
        )
    except ModelGatewayError as exc:
        failure_phase = "provider_transport_or_response"
        failure_code = exc.code
        failure_capture_ref = exc.capture_ref
    except BoundedFinanceLoopError as exc:
        failure_phase = "dynamic_fragment_or_terminal_validation"
        failure_code = str(exc)
    except CurrentResearchConsumerError as exc:
        failure_phase = "dynamic_deliverable_validation"
        failure_code = exc.code
    except DynamicSingleCellLiveError as exc:
        failure_phase = "dynamic_successor_orchestration"
        failure_code = exc.code

    succeeded = bool(structured_deliverable)
    status = (
        "completed_dynamic_counter_successor_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_no_retry"
    )
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    full_body: dict[str, Any] = {
        "schema_version": SUCCESSOR_FULL_RESULT_SCHEMA,
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": tool_name,
        "predecessor_public_result_ref": _relative(
            paths["predecessor_public_result_ref"]
        ),
        "predecessor_public_result_digest": predecessor_public[
            "result_digest"
        ],
        "predecessor_private_result_ref": _relative(
            paths["predecessor_private_result_ref"]
        ),
        "predecessor_private_result_digest": predecessor_full[
            "full_result_digest"
        ],
        "predecessor_successful_model_nodes_reused": 5,
        "predecessor_accepted_fragments": {
            key: predecessor_full["accepted_fragments"][key]
            for key in (
                "submit_research_thesis",
                "submit_research_mechanism",
            )
        },
        "fragment_context": fragment_context,
        "analysis_messages_digest": replay["analysis_messages_digest"],
        "analysis_step": analysis_step,
        "submission_messages_digest": submission_messages_digest,
        "submission_step": submission_step,
        "validated_fragment": validated_fragment,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": (
            _relative(failure_capture_ref) if failure_capture_ref else ""
        ),
        "execution": {
            "successful_predecessor_model_nodes_reused": 5,
            "fresh_model_calls_attempted": model_calls_attempted,
            "maximum_fresh_model_calls": 2,
            "fresh_tool_calls_accepted": int(bool(validated_fragment)),
            "total_fragments_accepted": len(accepted_fragments),
            "planner_calls_rerun": 0,
            "current_S1_S2_rerun": 0,
            "thesis_or_mechanism_calls_rerun": 0,
            "new_evidence": 0,
            "candidate_promotions": 0,
            "retries": 0,
            "fallbacks": 0,
            "external_source_network_calls": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {
        **full_body,
        "full_result_digest": canonical_digest(full_body),
    }
    _write_new(private_root / "full_result.json", full)
    terminal = (judgment_output.get("cells") or [{}])[0]
    public_body: dict[str, Any] = {
        "schema_version": SUCCESSOR_RESULT_SCHEMA,
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": tool_name,
        "predecessor_public_result_digest": predecessor_public[
            "result_digest"
        ],
        "predecessor_private_result_digest": predecessor_full[
            "full_result_digest"
        ],
        "predecessor_fragment_context_digest": replay[
            "predecessor_fragment_context_digest"
        ],
        "analysis_messages_digest": replay["analysis_messages_digest"],
        "analysis": _public_provider_step(analysis_step),
        "submission_messages_digest": submission_messages_digest,
        "submission": _public_provider_step(submission_step),
        "validated_fragment_digest": (
            canonical_digest(validated_fragment)
            if validated_fragment
            else ""
        ),
        "terminal_disposition": {
            "judgment_status": terminal.get("judgment_status", ""),
            "inference_authority": terminal.get(
                "inference_authority", ""
            ),
            "causal_bridge_authority": terminal.get(
                "causal_bridge_authority", ""
            ),
        },
        "terminal_judgment_digest": (
            canonical_digest(terminal) if terminal else ""
        ),
        "deliverable_digest": structured_deliverable.get(
            "deliverable_digest", ""
        ),
        "failure_phase": failure_phase,
        "failure_code": failure_code,
        "failure_capture_ref": full["failure_capture_ref"],
        "execution": full["execution"],
        "private_full_result_ref": _relative(
            private_root / "full_result.json"
        ),
        "private_full_result_sha256": _sha(
            private_root / "full_result.json"
        ),
        "acceptance": {
            "immutable_successful_prefix_reused": True,
            "failed_counter_analysis_naturally_completed": bool(
                analysis_step
            ),
            "failed_counter_submission_naturally_completed": bool(
                validated_fragment
            ),
            "dynamic_single_cell_contract_pass": succeeded,
            "L1_content_assessment_pending": succeeded,
            "five_cell_execution": False,
            "heterogeneous_generalization": False,
            "qualified_human_acceptance": False,
            "s3_product_acceptance": False,
            "workbench_publication": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {
        **public_body,
        "result_digest": canonical_digest(public_body),
    }
    _write_new(_resolve(str(output["public_result_ref"])), public)
    return public


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", type=Path, required=True)
    args = parser.parse_args(argv)
    authority_path = args.authority.resolve()
    schema = _json(authority_path).get("schema_version")
    result = (
        run_successor(authority_path)
        if schema == SUCCESSOR_AUTHORITY_SCHEMA
        else run(authority_path)
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"].startswith("completed_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
