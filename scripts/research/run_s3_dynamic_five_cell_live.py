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
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_node_profile,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    validate_current_research_output,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_research_input_projection,
)
from sec_agent.research.dynamic_truth_spine import (  # noqa: E402
    DynamicTruthSpineError,
)
from sec_agent.research.five_cell_runtime import (  # noqa: E402
    FiveCellResearchError,
    compile_five_cell_analysis_messages,
    compile_five_cell_report,
    compile_five_cell_submission,
    compile_five_cell_synthesis_analysis_messages,
    compile_five_cell_synthesis_submission,
    validate_five_cell_synthesis,
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


AUTHORITY_SCHEMA = "fin_ia_s3_dynamic_five_cell_live_authority_v1_0"
AUTHORITY_STATUS = "signed_exact_once_DELL_dynamic_five_cell_chat_live"
RESULT_SCHEMA = "fin_ia_s3_dynamic_five_cell_live_result_v1_0"
FULL_RESULT_SCHEMA = "fin_ia_s3_dynamic_five_cell_live_full_v1_0"
SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_successor_live_authority_v1_0"
)
SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_five_cell_remaining_twelve_nodes"
)
SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_successor_live_result_v1_0"
)
SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_successor_live_full_v1_0"
)

REQUIRED_CELL_IDS = (
    "CELL::demand_quality",
    "CELL::operating_performance",
    "CELL::value_capture",
    "CELL::cash_conversion",
    "CELL::counterevidence",
)
EXPECTED_BUDGET = {
    "maximum_model_calls": 13,
    "maximum_transport_attempts": 13,
    "maximum_planner_calls": 1,
    "maximum_cell_analysis_calls": 5,
    "maximum_cell_submission_calls": 5,
    "maximum_synthesis_analysis_calls": 1,
    "maximum_synthesis_submission_calls": 1,
    "maximum_evidence_requests": 8,
    "maximum_tool_calls": 6,
    "retries": 0,
    "fallbacks": 0,
    "external_source_network_calls": 0,
    "protocol_switches": 0,
    "current_product_pointer_mutations": 0,
}
SUCCESSOR_EXPECTED_BUDGET = {
    "maximum_model_calls": 12,
    "maximum_transport_attempts": 12,
    "maximum_planner_calls": 0,
    "reused_predecessor_planner_calls": 1,
    "maximum_cell_analysis_calls": 5,
    "maximum_cell_submission_calls": 5,
    "maximum_synthesis_analysis_calls": 1,
    "maximum_synthesis_submission_calls": 1,
    "maximum_evidence_requests": 0,
    "reused_predecessor_evidence_requests": 8,
    "maximum_tool_calls": 6,
    "retries": 0,
    "fallbacks": 0,
    "external_source_network_calls": 0,
    "protocol_switches": 0,
    "current_product_pointer_mutations": 0,
}


class DynamicFiveCellLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _resolve(ref: str) -> Path:
    relative = PurePosixPath(str(ref or ""))
    if relative.is_absolute() or "\\" in str(ref) or ".." in relative.parts:
        raise DynamicFiveCellLiveError("five_cell_live_path_invalid")
    path = (ROOT / Path(*relative.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise DynamicFiveCellLiveError("five_cell_live_path_outside_repo") from exc
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
        raise DynamicFiveCellLiveError("five_cell_live_bound_inputs_invalid")
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "planner_profile_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "five_cell_context_result_ref",
        "dynamic_single_cell_assessment_ref",
        "runner_zero_call_result_ref",
        "scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "five_cell_runtime_ref",
        "current_consumer_ref",
        "bounded_loop_ref",
        "provider_transport_ref",
    }
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "five_cell_context_result_digest",
        "runner_zero_call_result_digest",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError("five_cell_live_bound_inputs_invalid")
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_live_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _bound_successor_paths(authority: Mapping[str, Any]) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_bound_inputs_invalid"
        )
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "capacity_successor_result_ref",
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "successor_scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "five_cell_runtime_ref",
        "current_consumer_ref",
        "bounded_loop_ref",
        "provider_transport_ref",
    }
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "predecessor_plan_digest",
        "predecessor_controlled_plan_digest",
        "predecessor_public_result_digest",
        "predecessor_private_result_digest",
        "capacity_successor_result_digest",
        "expected_research_input_digest",
        "expected_evidence_pack_artifact_digest",
        "expected_evidence_pack_payload_digest",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError(
            "five_cell_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_successor_bound_input_drift:{key}"
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


def _validate_initial_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == AUTHORITY_SCHEMA
        and payload.get("status") == AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and payload.get("execution_budget") == EXPECTED_BUDGET
    ):
        raise DynamicFiveCellLiveError("five_cell_live_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError("five_cell_live_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError("five_cell_live_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError("five_cell_live_upstream_drift")
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError("five_cell_live_worktree_not_clean")

    paths = _bound_paths(payload)
    context = _json(paths["five_cell_context_result_ref"])
    single = _json(paths["dynamic_single_cell_assessment_ref"])
    proof = _json(paths["runner_zero_call_result_ref"])
    decision = _json(paths["scope_decision_ref"])
    bound = payload["bound_inputs"]
    if not (
        context.get("status")
        == "engineering_pass_zero_call_current_consumer_contract_successor"
        and context.get("result_digest")
        == bound["five_cell_context_result_digest"]
        and context.get("acceptance", {}).get(
            "all_five_cells_have_role_method_pack"
        )
        is True
        and context.get("acceptance", {}).get(
            "all_graph_context_compiled_from_current_case"
        )
        is True
        and context.get("acceptance", {}).get("natural_model_quality_proven")
        is False
        and single.get("status")
        == "dynamic_single_cell_L1_and_applicable_content_pass_S1_sync_then_five_cell"
        and single.get("acceptance", {}).get("dynamic_single_cell_L1")
        is True
        and proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_runner_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_stable_five_cell_runner"
        and proof.get("result_digest")
        == bound["runner_zero_call_result_digest"]
        and proof.get("acceptance", {}).get(
            "success_path_exact_thirteen_calls"
        )
        is True
        and proof.get("acceptance", {}).get(
            "cell_failure_does_not_hide_later_cells"
        )
        is True
        and proof.get("acceptance", {}).get(
            "synthesis_requires_all_five_cells"
        )
        is True
        and proof.get("acceptance", {}).get(
            "natural_model_quality_proven"
        )
        is False
        and decision.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_live_scope_decision_v1_0"
        and decision.get("status")
        == "approved_one_DELL_dynamic_five_cell_exact_once"
        and tuple(decision.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and decision.get("execution_budget") == EXPECTED_BUDGET
        and decision.get("continue_after_cell_failure") is True
        and decision.get("synthesis_requires_all_cells") is True
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
    ):
        raise DynamicFiveCellLiveError("five_cell_live_predecessor_invalid")
    kernel, route, planning, objective, messages = _compile_planner_contract(paths)
    del kernel, route, planning
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError("five_cell_live_planner_binding_drift")

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
        "cell_attempt_ids",
        "synthesis_attempt_ids",
        "product_publication",
    }
    if not isinstance(output, Mapping) or set(output) != required_output:
        raise DynamicFiveCellLiveError("five_cell_live_output_invalid")
    cells = output.get("cell_attempt_ids")
    synthesis = output.get("synthesis_attempt_ids")
    if not (
        output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output
            - {"cell_attempt_ids", "synthesis_attempt_ids", "product_publication"}
        )
        and isinstance(cells, Mapping)
        and set(cells) == set(REQUIRED_CELL_IDS)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"analysis_attempt_id", "submission_attempt_id"}
            and all(str(value or "") for value in row.values())
            for row in cells.values()
        )
        and isinstance(synthesis, Mapping)
        and set(synthesis) == {"analysis_attempt_id", "submission_attempt_id"}
        and all(str(value or "") for value in synthesis.values())
    ):
        raise DynamicFiveCellLiveError("five_cell_live_output_invalid")
    identities = {
        str(output["planner_attempt_id"]),
        *(str(value) for row in cells.values() for value in row.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 13:
        raise DynamicFiveCellLiveError("five_cell_live_output_identity_invalid")
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError("five_cell_live_identity_consumed")
    return paths


def _validate_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status") == SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and payload.get("execution_budget") == SUCCESSOR_EXPECTED_BUDGET
    ):
        raise DynamicFiveCellLiveError("five_cell_successor_authority_invalid")
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError("five_cell_successor_commit_invalid")
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError("five_cell_successor_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError("five_cell_successor_upstream_drift")
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError("five_cell_successor_worktree_not_clean")

    paths = _bound_successor_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    capacity = _json(paths["capacity_successor_result_ref"])
    decision = _json(paths["successor_scope_decision_ref"])
    capacity_acceptance = capacity.get("acceptance") or {}
    predecessor_execution = predecessor_full.get("execution") or {}
    predecessor_failure = predecessor_full.get("orchestration_failure") or {}
    if not (
        predecessor_authority.get("schema_version") == AUTHORITY_SCHEMA
        and predecessor_public.get("status")
        == "terminal_failed_or_partial_no_retry"
        and predecessor_full.get("status")
        == "terminal_failed_or_partial_no_retry"
        and predecessor_public.get("result_digest")
        == bound["predecessor_public_result_digest"]
        and predecessor_full.get("full_result_digest")
        == bound["predecessor_private_result_digest"]
        and (predecessor_full.get("compiled_plan") or {}).get("plan_digest")
        == bound["predecessor_plan_digest"]
        and canonical_digest(predecessor_full.get("controlled_plan") or {})
        == bound["predecessor_controlled_plan_digest"]
        and predecessor_failure.get("failure_phase")
        == "five_cell_deliverable_validation"
        and predecessor_failure.get("failure_code")
        == "research_consumer_cell_capacity_exceeded"
        and predecessor_execution.get("model_calls_attempted") == 1
        and predecessor_execution.get("planner_calls_completed") == 1
        and predecessor_execution.get("cell_analysis_calls_attempted") == 0
        and predecessor_execution.get("cell_submission_calls_attempted") == 0
        and predecessor_execution.get("retries") == 0
        and predecessor_execution.get("fallbacks") == 0
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_predecessor_invalid"
        )
    if not (
        capacity.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_capacity_successor_zero_call_result_v1_0"
        and capacity.get("status")
        == "engineering_pass_zero_call_R1_capacity_contract_successor"
        and capacity.get("result_digest")
        == bound["capacity_successor_result_digest"]
        and (capacity.get("replay") or {}).get("research_input_digest")
        == bound["expected_research_input_digest"]
        and (capacity.get("current_pack_binding") or {}).get("artifact_digest")
        == bound["expected_evidence_pack_artifact_digest"]
        and (capacity.get("current_pack_binding") or {}).get(
            "pack_payload_digest"
        )
        == bound["expected_evidence_pack_payload_digest"]
        and capacity_acceptance.get("R1_preserved") is True
        and capacity_acceptance.get(
            "planner_and_current_S1_S2_reused_not_rerun"
        )
        is True
        and capacity_acceptance.get(
            "value_capture_five_metrics_two_periods_equal_ten"
        )
        is True
        and capacity_acceptance.get("all_five_cells_compile") is True
        and capacity_acceptance.get("all_five_cell_tool_schemas_compile")
        is True
        and capacity_acceptance.get("synthesis_preconditions_compile") is True
        and capacity_acceptance.get("successor_live_authorized") is False
        and capacity_acceptance.get("natural_financial_L1_proven") is False
        and capacity_acceptance.get("content_quality_proven") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_capacity_proof_invalid"
        )
    if not (
        decision.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_live_scope_decision_v1_0"
        and decision.get("status")
        == "approved_one_DELL_dynamic_five_cell_remaining_twelve_nodes_exact_once"
        and decision.get("run_scope_id")
        == "one_DELL_dynamic_five_cell_successor_remaining_twelve_nodes"
        and decision.get("evidence_mode")
        == "immutable_dynamic_R1_planner_current_S1_S2_prefix_no_new_evidence"
        and tuple(decision.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and decision.get("execution_budget") == SUCCESSOR_EXPECTED_BUDGET
        and decision.get("reuse_predecessor_planner") is True
        and decision.get("reuse_predecessor_current_S1_S2") is True
        and decision.get("rerun_planner") is False
        and decision.get("rerun_current_S1_S2") is False
        and decision.get("continue_after_cell_failure") is True
        and decision.get("synthesis_requires_all_cells") is True
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and decision.get("heterogeneous_generalization_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_scope_decision_invalid"
        )

    _, _, _, objective, messages = _compile_planner_contract(paths)
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_planner_prefix_binding_drift"
        )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
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
        "cell_attempt_ids",
        "synthesis_attempt_ids",
        "product_publication",
    }
    if not isinstance(output, Mapping) or set(output) != required_output:
        raise DynamicFiveCellLiveError("five_cell_successor_output_invalid")
    cells = output.get("cell_attempt_ids")
    synthesis = output.get("synthesis_attempt_ids")
    if not (
        output.get("product_publication") == "forbidden"
        and all(
            str(output.get(key) or "")
            for key in required_output
            - {"cell_attempt_ids", "synthesis_attempt_ids", "product_publication"}
        )
        and isinstance(cells, Mapping)
        and set(cells) == set(REQUIRED_CELL_IDS)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"analysis_attempt_id", "submission_attempt_id"}
            and all(str(value or "") for value in row.values())
            for row in cells.values()
        )
        and isinstance(synthesis, Mapping)
        and set(synthesis) == {"analysis_attempt_id", "submission_attempt_id"}
        and all(str(value or "") for value in synthesis.values())
    ):
        raise DynamicFiveCellLiveError("five_cell_successor_output_invalid")
    identities = {
        *(str(value) for row in cells.values() for value in row.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 12:
        raise DynamicFiveCellLiveError(
            "five_cell_successor_output_identity_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError("five_cell_successor_identity_consumed")
    return paths


def validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if payload.get("schema_version") == SUCCESSOR_AUTHORITY_SCHEMA:
        return _validate_successor_authority(
            payload, authority_path=authority_path
        )
    return _validate_initial_authority(payload, authority_path=authority_path)


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
) -> dict[str, Any]:
    if result.finish_reason == "length":
        raise DynamicFiveCellLiveError("five_cell_live_submission_length_stop")
    if len(result.tool_calls) != 1:
        raise DynamicFiveCellLiveError(
            "five_cell_live_submission_tool_call_count_invalid"
        )
    function = result.tool_calls[0].get("function")
    if not isinstance(function, Mapping) or function.get("name") != expected_tool:
        raise DynamicFiveCellLiveError("five_cell_live_submission_tool_invalid")
    try:
        value = json.loads(str(function.get("arguments") or ""))
    except json.JSONDecodeError as exc:
        raise DynamicFiveCellLiveError(
            "five_cell_live_submission_arguments_json_invalid"
        ) from exc
    if not isinstance(value, dict):
        raise DynamicFiveCellLiveError(
            "five_cell_live_submission_arguments_invalid"
        )
    if expected_tool == SUBMIT_RESEARCH_JUDGMENT_TOOL:
        wwc = value.get("what_would_change")
        if isinstance(wwc, Mapping) and wwc.get("threshold_numeric_ref") == "":
            value["what_would_change"] = dict(wwc)
            value["what_would_change"]["threshold_numeric_ref"] = None
    return value


def _require_controlled_plan_binding(
    controlled_plan: Mapping[str, Any], *, expected_plan_digest: str
) -> None:
    actual = str(
        (controlled_plan.get("compiled_plan") or {}).get("plan_digest") or ""
    )
    if actual != expected_plan_digest:
        raise DynamicFiveCellLiveError("five_cell_live_plan_digest_drift")


def _failure(
    *, phase: str, code: str, capture_ref: str = ""
) -> dict[str, str]:
    return {
        "failure_phase": phase,
        "failure_code": code,
        "failure_capture_ref": _relative(capture_ref) if capture_ref else "",
    }


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
    successor_mode = authority.get("schema_version") == SUCCESSOR_AUTHORITY_SCHEMA
    paths = validate_authority(authority, authority_path=authority_path)
    output = authority["output_contract"]
    capture_root = _resolve(str(output["capture_root_ref"]))
    private_root = _resolve(str(output["private_output_root_ref"]))
    run_id = str(output["run_id"])
    kernel, route, planning, objective, planner_messages = _compile_planner_contract(
        paths
    )
    planner_profile = (
        None
        if successor_mode
        else load_chat_completion_profile(_json(paths["planner_profile_ref"]))
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
    cell_steps: list[dict[str, Any]] = []
    accepted_raw_cells: list[dict[str, Any]] = []
    judgment_output: dict[str, Any] = {}
    structured_deliverable: dict[str, Any] = {}
    synthesis_steps: dict[str, Any] = {
        "analysis_messages_digest": "",
        "submission_messages_digest": "",
        "analysis_step": {},
        "submission_step": {},
        "validated_synthesis": {},
        "failure_phase": "not_attempted",
        "failure_code": "five_cell_synthesis_requires_all_cells",
        "failure_capture_ref": "",
    }
    final_report: dict[str, Any] = {}
    orchestration_failure = _failure(phase="", code="")
    model_calls_attempted = 0

    try:
        if successor_mode:
            predecessor = _json(paths["predecessor_private_result_ref"])
            planner_step = deepcopy(predecessor["planner_step"])
            planner_output = deepcopy(predecessor["planner_output"])
            compiled_plan = deepcopy(predecessor["compiled_plan"])
            controlled_plan = deepcopy(predecessor["controlled_plan"])
            _require_controlled_plan_binding(
                controlled_plan,
                expected_plan_digest=str(
                    authority["bound_inputs"]["predecessor_plan_digest"]
                ),
            )
        else:
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
                raise DynamicFiveCellLiveError(
                    "five_cell_live_planner_finish_invalid"
                )
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
        if successor_mode and not (
            evidence_pack.get("artifact_digest")
            == authority["bound_inputs"][
                "expected_evidence_pack_artifact_digest"
            ]
            and evidence_pack.get("pack_payload_digest")
            == authority["bound_inputs"][
                "expected_evidence_pack_payload_digest"
            ]
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_successor_current_pack_binding_drift"
            )
        dynamic_projection = compile_dynamic_research_input_projection(
            truth_spine_policy=_json(paths["truth_spine_policy_ref"]),
            consumer_policy=_json(paths["consumer_policy_ref"]),
            controlled_plan=controlled_plan,
            evidence_pack=evidence_pack,
        )
        research_input = dynamic_projection["dynamic_research_input"]
        if not research_input:
            raise DynamicFiveCellLiveError(
                "five_cell_live_no_reviewed_evidence_selected"
            )
        if successor_mode and research_input.get("research_input_digest") != (
            authority["bound_inputs"]["expected_research_input_digest"]
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_successor_research_input_drift"
            )
        actual_cells = tuple(row["cell_id"] for row in research_input["cells"])
        if actual_cells != REQUIRED_CELL_IDS:
            raise DynamicFiveCellLiveError("five_cell_live_cell_scope_drift")

        for cell_id in REQUIRED_CELL_IDS:
            attempts = output["cell_attempt_ids"][cell_id]
            row: dict[str, Any] = {
                "cell_id": cell_id,
                "analysis_messages_digest": "",
                "submission_messages_digest": "",
                "tool_schema_digest": "",
                "analysis_step": {},
                "submission_step": {},
                "raw_model_arguments": {},
                "validated_cell": {},
                "failure_phase": "",
                "failure_code": "",
                "failure_capture_ref": "",
            }
            cell_steps.append(row)
            try:
                analysis_messages = compile_five_cell_analysis_messages(
                    research_input=research_input,
                    cell_id=cell_id,
                )
                row["analysis_messages_digest"] = canonical_digest(
                    list(analysis_messages)
                )
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
                    raise DynamicFiveCellLiveError(
                        "five_cell_live_cell_analysis_length_stop"
                    )
                submission_messages, tool = compile_five_cell_submission(
                    research_input=research_input,
                    cell_id=cell_id,
                    analysis_draft=analysis.content,
                )
                row["submission_messages_digest"] = canonical_digest(
                    list(submission_messages)
                )
                row["tool_schema_digest"] = canonical_digest(tool)
                model_calls_attempted += 1
                submission = submission_executor(
                    profile=submission_profile,
                    messages=submission_messages,
                    tools=[tool],
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=str(attempts["submission_attempt_id"]),
                    tool_choice=None,
                )
                row["submission_step"] = submission.as_dict()
                raw = _tool_arguments(
                    submission, expected_tool=SUBMIT_RESEARCH_JUDGMENT_TOOL
                )
                row["raw_model_arguments"] = raw
                validated = validate_current_research_output(
                    {"cells": [raw]},
                    research_input=research_input,
                    required_cell_ids=[cell_id],
                )["cells"][0]
                row["validated_cell"] = validated
                accepted_raw_cells.append(raw)
            except ModelGatewayError as exc:
                row.update(
                    _failure(
                        phase="provider_transport_or_response",
                        code=exc.code,
                        capture_ref=exc.capture_ref,
                    )
                )
            except CurrentResearchConsumerError as exc:
                row.update(
                    _failure(phase="cell_judgment_contract", code=exc.code)
                )
            except FiveCellResearchError as exc:
                row.update(
                    _failure(phase="cell_analysis_submission", code=exc.code)
                )
            except DynamicFiveCellLiveError as exc:
                row.update(
                    _failure(phase="cell_live_orchestration", code=exc.code)
                )

        if len(accepted_raw_cells) == 5:
            judgment_output = validate_current_research_output(
                {"cells": accepted_raw_cells},
                research_input=research_input,
                required_cell_ids=REQUIRED_CELL_IDS,
            )
            structured_deliverable = compile_current_research_deliverable(
                research_input=research_input,
                judgment_output={"cells": accepted_raw_cells},
                required_cell_ids=REQUIRED_CELL_IDS,
            )
            synthesis_attempts = output["synthesis_attempt_ids"]
            try:
                synthesis_messages = compile_five_cell_synthesis_analysis_messages(
                    research_input=research_input,
                    judgment_output=judgment_output,
                    structured_deliverable=structured_deliverable,
                )
                synthesis_steps["analysis_messages_digest"] = canonical_digest(
                    list(synthesis_messages)
                )
                model_calls_attempted += 1
                analysis = analysis_executor(
                    profile=analysis_profile,
                    messages=synthesis_messages,
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=str(synthesis_attempts["analysis_attempt_id"]),
                )
                synthesis_steps["analysis_step"] = analysis.as_dict()
                if analysis.finish_reason == "length":
                    raise DynamicFiveCellLiveError(
                        "five_cell_live_synthesis_analysis_length_stop"
                    )
                submission_messages, synthesis_tool = (
                    compile_five_cell_synthesis_submission(
                        research_input=research_input,
                        judgment_output=judgment_output,
                        structured_deliverable=structured_deliverable,
                        analysis_draft=analysis.content,
                    )
                )
                synthesis_steps["submission_messages_digest"] = canonical_digest(
                    list(submission_messages)
                )
                synthesis_steps["tool_schema_digest"] = canonical_digest(
                    synthesis_tool
                )
                model_calls_attempted += 1
                submission = submission_executor(
                    profile=submission_profile,
                    messages=submission_messages,
                    tools=[synthesis_tool],
                    capture_root=capture_root,
                    run_id=run_id,
                    attempt_id=str(synthesis_attempts["submission_attempt_id"]),
                    tool_choice=None,
                )
                synthesis_steps["submission_step"] = submission.as_dict()
                raw_synthesis = _tool_arguments(
                    submission, expected_tool="submit_five_cell_synthesis"
                )
                validated_synthesis = validate_five_cell_synthesis(
                    raw_synthesis,
                    research_input=research_input,
                    judgment_output=judgment_output,
                )
                synthesis_steps["validated_synthesis"] = validated_synthesis
                synthesis_steps["failure_phase"] = ""
                synthesis_steps["failure_code"] = ""
                final_report = compile_five_cell_report(
                    research_input=research_input,
                    structured_deliverable=structured_deliverable,
                    synthesis=validated_synthesis,
                )
            except ModelGatewayError as exc:
                synthesis_steps.update(
                    _failure(
                        phase="provider_transport_or_response",
                        code=exc.code,
                        capture_ref=exc.capture_ref,
                    )
                )
            except FiveCellResearchError as exc:
                synthesis_steps.update(
                    _failure(phase="synthesis_contract", code=exc.code)
                )
            except DynamicFiveCellLiveError as exc:
                synthesis_steps.update(
                    _failure(phase="synthesis_orchestration", code=exc.code)
                )
    except ModelGatewayError as exc:
        orchestration_failure = _failure(
            phase="planner_provider_transport_or_response",
            code=exc.code,
            capture_ref=exc.capture_ref,
        )
    except ResearchPlanningError as exc:
        orchestration_failure = _failure(
            phase="natural_planner_contract", code=str(exc)
        )
    except ResearchRetrievalServiceError as exc:
        orchestration_failure = _failure(
            phase="current_S1_S2_retrieval", code=exc.error_code
        )
    except ResearchEvidencePackServiceError as exc:
        orchestration_failure = _failure(
            phase="current_reviewed_evidence_pack", code=exc.error_code
        )
    except DynamicTruthSpineError as exc:
        orchestration_failure = _failure(
            phase="dynamic_truth_spine", code=str(exc)
        )
    except CurrentResearchConsumerError as exc:
        orchestration_failure = _failure(
            phase="five_cell_deliverable_validation", code=exc.code
        )
    except FiveCellResearchError as exc:
        orchestration_failure = _failure(
            phase="five_cell_runtime", code=exc.code
        )
    except DynamicFiveCellLiveError as exc:
        orchestration_failure = _failure(
            phase="five_cell_live_orchestration", code=exc.code
        )

    accepted_count = sum(bool(row["validated_cell"]) for row in cell_steps)
    succeeded = bool(final_report)
    status = (
        "completed_five_cell_report_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_or_partial_no_retry"
    )
    full_body = {
        "schema_version": (
            SUCCESSOR_FULL_RESULT_SCHEMA
            if successor_mode
            else FULL_RESULT_SCHEMA
        ),
        "status": status,
        "recorded_at": _now(),
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority["implementation_commit"],
        "case_key": "DELL",
        "required_cell_ids": list(REQUIRED_CELL_IDS),
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
        "successor_prefix_reuse": (
            {
                "predecessor_authority_ref": _relative(
                    paths["predecessor_authority_ref"]
                ),
                "predecessor_public_result_ref": _relative(
                    paths["predecessor_public_result_ref"]
                ),
                "predecessor_private_result_ref": _relative(
                    paths["predecessor_private_result_ref"]
                ),
                "planner_reused": True,
                "current_S1_S2_reused": True,
                "planner_rerun": False,
                "current_S1_S2_rerun": False,
            }
            if successor_mode
            else {}
        ),
        "dynamic_projection": dynamic_projection,
        "cell_steps": cell_steps,
        "judgment_output": judgment_output,
        "structured_deliverable": structured_deliverable,
        "synthesis_steps": synthesis_steps,
        "final_report": final_report,
        "orchestration_failure": orchestration_failure,
        "execution": {
            "model_calls_attempted": model_calls_attempted,
            "maximum_model_calls": (
                SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
                if successor_mode
                else EXPECTED_BUDGET["maximum_model_calls"]
            ),
            "planner_calls_completed": (
                0 if successor_mode else int(bool(planner_output))
            ),
            "planner_calls_reused": int(successor_mode and bool(planner_output)),
            "cell_analysis_calls_attempted": sum(
                bool(row["analysis_step"]) for row in cell_steps
            ),
            "cell_submission_calls_attempted": sum(
                bool(row["submission_step"]) for row in cell_steps
            ),
            "cell_judgments_accepted": accepted_count,
            "synthesis_analysis_attempted": int(
                bool(synthesis_steps["analysis_step"])
            ),
            "synthesis_submission_attempted": int(
                bool(synthesis_steps["submission_step"])
            ),
            "current_S1_S2_executed": bool(controlled_plan) and not successor_mode,
            "current_S1_S2_reused": bool(controlled_plan) and successor_mode,
            "candidate_promotions": int(
                (dynamic_projection or {}).get("candidate_promotions") or 0
            ),
            "external_source_network_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "protocol_switches": 0,
            "product_publication": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    full = {**full_body, "full_result_digest": canonical_digest(full_body)}
    _write_new(private_root / "full_result.json", full)

    responses = (dynamic_projection or {}).get("evidence_responses") or {}
    public_body = {
        "schema_version": (
            SUCCESSOR_RESULT_SCHEMA if successor_mode else RESULT_SCHEMA
        ),
        "status": status,
        "recorded_at": full["recorded_at"],
        "authority_ref": full["authority_ref"],
        "authority_sha256": full["authority_sha256"],
        "implementation_commit": full["implementation_commit"],
        "case_key": "DELL",
        "required_cell_ids": list(REQUIRED_CELL_IDS),
        "objective_id": objective.objective_id,
        "planner": {
            "provider_step": _public_provider_step(planner_step),
            "reused_from_predecessor": successor_mode,
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
        "cells": [
            {
                "cell_id": row["cell_id"],
                "analysis_messages_digest": row["analysis_messages_digest"],
                "submission_messages_digest": row["submission_messages_digest"],
                "tool_schema_digest": row["tool_schema_digest"],
                "analysis": _public_provider_step(row["analysis_step"]),
                "submission": _public_provider_step(row["submission_step"]),
                "validated_cell_digest": (
                    canonical_digest(row["validated_cell"])
                    if row["validated_cell"]
                    else ""
                ),
                "failure_phase": row["failure_phase"],
                "failure_code": row["failure_code"],
                "failure_capture_ref": row["failure_capture_ref"],
            }
            for row in cell_steps
        ],
        "synthesis": {
            "analysis_messages_digest": synthesis_steps[
                "analysis_messages_digest"
            ],
            "submission_messages_digest": synthesis_steps[
                "submission_messages_digest"
            ],
            "tool_schema_digest": synthesis_steps.get("tool_schema_digest", ""),
            "analysis": _public_provider_step(synthesis_steps["analysis_step"]),
            "submission": _public_provider_step(
                synthesis_steps["submission_step"]
            ),
            "validated_synthesis_digest": (
                synthesis_steps["validated_synthesis"].get(
                    "synthesis_digest", ""
                )
                if synthesis_steps["validated_synthesis"]
                else ""
            ),
            "failure_phase": synthesis_steps["failure_phase"],
            "failure_code": synthesis_steps["failure_code"],
            "failure_capture_ref": synthesis_steps["failure_capture_ref"],
        },
        "cell_workpaper_digest": structured_deliverable.get(
            "deliverable_digest", ""
        ),
        "report_digest": final_report.get("report_digest", ""),
        "orchestration_failure": orchestration_failure,
        "execution": full["execution"],
        "private_full_result_ref": _relative(private_root / "full_result.json"),
        "private_full_result_sha256": _sha(private_root / "full_result.json"),
        "acceptance": {
            "natural_planner_executed": bool(planner_output),
            "natural_planner_reused_not_rerun": successor_mode,
            "current_S1_S2_EvidenceResponse_executed": bool(responses),
            "current_S1_S2_reused_not_rerun": successor_mode,
            "all_five_cell_judgments_contract_valid": accepted_count == 5,
            "cross_cell_synthesis_contract_valid": bool(
                synthesis_steps["validated_synthesis"]
            ),
            "five_cell_report_compiled": succeeded,
            "financial_L1_assessment_pending": succeeded,
            "absolute_content_quality_pending": succeeded,
            "paired_gain_pending": succeeded,
            "qualified_human_acceptance": False,
            "heterogeneous_generalization": False,
            "s3_product_acceptance": False,
            "workbench_publication": False,
            "release_ready": False,
        },
        "known_boundary": authority["known_boundary"],
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(_resolve(str(output["public_result_ref"])), public)
    return public


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"].startswith("completed_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
