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
from sec_agent.providers.deepseek_strict import (  # noqa: E402
    project_deepseek_strict_tool,
    validate_deepseek_strict_submission_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    SUBMIT_RESEARCH_JUDGMENT_TOOL,
    validate_deepseek_ga_profile,
    validate_deepseek_ga_json_profile,
    validate_deepseek_ga_node_profile,
)
from sec_agent.research.current_consumer import (  # noqa: E402
    CurrentResearchConsumerError,
    compile_current_research_deliverable,
    validate_current_research_output,
)
from sec_agent.research.dynamic_research_runtime import (  # noqa: E402
    compile_dynamic_claim_surface_projection,
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
    compile_five_cell_submission_repair,
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
PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_partial_successor_live_authority_v1_0"
)
PARTIAL_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_five_cell_failed_three_plus_synthesis"
)
PARTIAL_SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_partial_successor_live_result_v1_0"
)
PARTIAL_SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_partial_successor_live_full_v1_0"
)
NODE_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_node_successor_live_authority_v1_0"
)
NODE_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_five_cell_two_submissions_plus_synthesis"
)
NODE_SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_node_successor_live_result_v1_0"
)
NODE_SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_node_successor_live_full_v1_0"
)
CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_live_authority_v1_0"
)
CLAIM_SURFACE_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_five_cell_claim_surface_successor"
)
CLAIM_SURFACE_SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_live_result_v1_0"
)
CLAIM_SURFACE_SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_live_full_v1_0"
)
VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_live_authority_v1_0"
)
VALUE_REPAIR_SUCCESSOR_AUTHORITY_STATUS = (
    "signed_exact_once_DELL_dynamic_five_cell_value_submission_"
    "repair_plus_synthesis"
)
VALUE_REPAIR_SUCCESSOR_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_live_result_v1_0"
)
VALUE_REPAIR_SUCCESSOR_FULL_RESULT_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_live_full_v1_0"
)
VALUE_REPAIR_SUCCESSOR_SCOPE_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_scope_decision_v1_0"
)
VALUE_REPAIR_SUCCESSOR_SCOPE_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_value_submission_"
    "repair_plus_synthesis_exact_once"
)
CLAIM_SURFACE_SUCCESSOR_SCOPE_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_scope_decision_v1_0"
)
CLAIM_SURFACE_SUCCESSOR_SCOPE_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
)
CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_scope_decision_v1_1"
)
CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_exact_once"
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
PARTIAL_SUCCESSOR_REUSED_CELL_IDS = (
    "CELL::demand_quality",
    "CELL::operating_performance",
)
PARTIAL_SUCCESSOR_REMAINING_CELL_IDS = (
    "CELL::value_capture",
    "CELL::cash_conversion",
    "CELL::counterevidence",
)
PARTIAL_SUCCESSOR_EXPECTED_BUDGET = {
    "maximum_model_calls": 8,
    "maximum_transport_attempts": 8,
    "maximum_planner_calls": 0,
    "reused_predecessor_planner_calls": 1,
    "maximum_cell_analysis_calls": 3,
    "maximum_cell_submission_calls": 3,
    "reused_predecessor_cell_judgments": 2,
    "maximum_synthesis_analysis_calls": 1,
    "maximum_synthesis_submission_calls": 1,
    "maximum_evidence_requests": 0,
    "reused_predecessor_evidence_requests": 8,
    "maximum_tool_calls": 4,
    "retries": 0,
    "fallbacks": 0,
    "external_source_network_calls": 0,
    "protocol_switches": 0,
    "current_product_pointer_mutations": 0,
}
NODE_SUCCESSOR_REUSED_CELL_IDS = (
    "CELL::demand_quality",
    "CELL::operating_performance",
    "CELL::cash_conversion",
)
NODE_SUCCESSOR_RESUBMISSION_CELL_IDS = (
    "CELL::value_capture",
    "CELL::counterevidence",
)
NODE_SUCCESSOR_EXPECTED_BUDGET = {
    "maximum_model_calls": 4,
    "maximum_transport_attempts": 4,
    "maximum_planner_calls": 0,
    "reused_predecessor_planner_calls": 1,
    "maximum_cell_analysis_calls": 0,
    "reused_predecessor_cell_analysis_drafts": 2,
    "maximum_cell_submission_calls": 2,
    "reused_predecessor_cell_judgments": 3,
    "maximum_synthesis_analysis_calls": 1,
    "maximum_synthesis_submission_calls": 1,
    "maximum_evidence_requests": 0,
    "reused_predecessor_evidence_requests": 8,
    "maximum_tool_calls": 3,
    "retries": 0,
    "fallbacks": 0,
    "external_source_network_calls": 0,
    "protocol_switches": 0,
    "current_product_pointer_mutations": 0,
}
CLAIM_SURFACE_SUCCESSOR_EXPECTED_BUDGET = {
    **SUCCESSOR_EXPECTED_BUDGET,
    "maximum_tool_calls": 6,
}
VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS = (
    "CELL::demand_quality",
    "CELL::operating_performance",
    "CELL::cash_conversion",
    "CELL::counterevidence",
)
VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS = ("CELL::value_capture",)
VALUE_REPAIR_SUCCESSOR_EXPECTED_BUDGET = {
    "maximum_model_calls": 3,
    "maximum_transport_attempts": 3,
    "maximum_planner_calls": 0,
    "reused_predecessor_planner_calls": 1,
    "maximum_cell_analysis_calls": 0,
    "reused_predecessor_cell_analysis_drafts": 1,
    "maximum_cell_submission_calls": 1,
    "reused_predecessor_cell_judgments": 4,
    "maximum_synthesis_analysis_calls": 1,
    "maximum_synthesis_submission_calls": 1,
    "maximum_evidence_requests": 0,
    "reused_predecessor_evidence_requests": 8,
    "maximum_tool_calls": 2,
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


def _resolve_capture_ref(ref: str) -> Path:
    value = Path(str(ref or ""))
    path = value.resolve() if value.is_absolute() else (ROOT / value).resolve()
    capture_root = (ROOT / "data/captures/provider_calls").resolve()
    try:
        path.relative_to(capture_root)
    except ValueError as exc:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_capture_path_invalid"
        ) from exc
    if not path.is_file():
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_capture_missing"
        )
    return path


def _reused_analysis_digest(row: Mapping[str, Any]) -> str:
    step = row.get("analysis_step") or {}
    body = {
        "cell_id": str(row.get("cell_id") or ""),
        "analysis_messages_digest": str(
            row.get("analysis_messages_digest") or ""
        ),
        "finish_reason": str(step.get("finish_reason") or ""),
        "request_digest": str(step.get("request_digest") or ""),
        "response_digest": str(step.get("response_digest") or ""),
        "content": str(step.get("content") or ""),
    }
    return canonical_digest(body)


def _validate_reused_analysis_capture(
    row: Mapping[str, Any],
) -> dict[str, Any]:
    step = row.get("analysis_step")
    if not (
        isinstance(step, Mapping)
        and step.get("finish_reason") == "stop"
        and str(step.get("content") or "").strip()
        and str(row.get("analysis_messages_digest") or "")
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_analysis_step_invalid"
        )
    request_path = _resolve_capture_ref(str(step.get("request_capture_ref") or ""))
    response_path = _resolve_capture_ref(
        str(step.get("response_capture_ref") or "")
    )
    request = _json(request_path)
    response = _json(response_path)
    request_body = request.get("request_body")
    response_body = response.get("response_body")
    if not isinstance(request_body, Mapping) or not isinstance(
        response_body, Mapping
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_capture_body_invalid"
        )
    choices = response_body.get("choices")
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else {}
    message = choice.get("message") if isinstance(choice, Mapping) else {}
    captured_content = (
        str(message.get("content") or "") if isinstance(message, Mapping) else ""
    )
    if not (
        request.get("request_digest") == step.get("request_digest")
        and request.get("request_digest") == canonical_digest(request_body)
        and response.get("response_digest") == step.get("response_digest")
        and response.get("response_digest") == canonical_digest(response_body)
        and request.get("run_id") == response.get("run_id")
        and request.get("attempt_id") == response.get("attempt_id")
        and canonical_digest(list(request_body.get("messages") or ()))
        == row.get("analysis_messages_digest")
        and choice.get("finish_reason") == "stop"
        and captured_content == step.get("content")
        and response.get("response_body_complete") is True
        and response.get("response_body_persisted") is True
        and response.get("eligible_for_contract_parse") is True
        and response.get("partial_response_received") is False
        and response.get("truncated") is False
        and not response.get("transport_error")
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_capture_integrity_invalid"
        )
    return {
        "schema_version": "fin_ia_s3_reused_analysis_capture_receipt_v1_0",
        "cell_id": str(row.get("cell_id") or ""),
        "request_capture_ref": _relative(request_path),
        "request_capture_sha256": _sha(request_path),
        "response_capture_ref": _relative(response_path),
        "response_capture_sha256": _sha(response_path),
        "request_digest": str(step.get("request_digest") or ""),
        "response_digest": str(step.get("response_digest") or ""),
        "analysis_reuse_digest": _reused_analysis_digest(row),
        "content_digest": canonical_digest({"content": captured_content}),
    }


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


def _bound_partial_successor_paths(
    authority: Mapping[str, Any],
) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_bound_inputs_invalid"
        )
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "predecessor_failure_assessment_ref",
        "partial_successor_zero_call_result_ref",
        "partial_successor_scope_decision_ref",
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
        "partial_successor_zero_call_result_digest",
        "expected_research_input_digest",
        "expected_evidence_pack_artifact_digest",
        "expected_evidence_pack_payload_digest",
        "expected_reused_cell_digests",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_partial_successor_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _bound_node_successor_paths(
    authority: Mapping[str, Any],
) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_bound_inputs_invalid"
        )
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "predecessor_failure_assessment_ref",
        "strict_canary_result_ref",
        "node_successor_zero_call_result_ref",
        "node_successor_scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "five_cell_runtime_ref",
        "current_consumer_ref",
        "bounded_loop_ref",
        "provider_transport_ref",
        "strict_projection_ref",
    }
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "predecessor_plan_digest",
        "predecessor_controlled_plan_digest",
        "predecessor_public_result_digest",
        "predecessor_private_result_digest",
        "strict_canary_result_digest",
        "node_successor_zero_call_result_digest",
        "expected_research_input_digest",
        "expected_evidence_pack_artifact_digest",
        "expected_evidence_pack_payload_digest",
        "expected_reused_cell_digests",
        "expected_reused_analysis_digests",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_node_successor_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _bound_claim_surface_successor_paths(
    authority: Mapping[str, Any],
) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_bound_inputs_invalid"
        )
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "claim_authority_template_ref",
        "claim_surface_template_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "predecessor_failure_assessment_ref",
        "scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "claim_authority_runtime_ref",
        "claim_surface_runtime_ref",
        "five_cell_runtime_ref",
        "current_consumer_ref",
        "reviewed_anchor_runtime_ref",
        "provider_transport_ref",
        "strict_projection_ref",
    }
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "predecessor_plan_digest",
        "predecessor_controlled_plan_digest",
        "predecessor_public_result_digest",
        "predecessor_private_result_digest",
        "predecessor_failure_assessment_result_digest",
        "expected_base_research_input_digest",
        "expected_claim_surface_research_input_digest",
        "expected_evidence_pack_artifact_digest",
        "expected_evidence_pack_payload_digest",
        "expected_reviewed_anchor_digest",
        "expected_reviewed_anchor_target_id",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_claim_surface_successor_bound_input_drift:{key}"
            )
        paths[key] = path
    return paths


def _bound_value_repair_successor_paths(
    authority: Mapping[str, Any],
) -> dict[str, Path]:
    bound = authority.get("bound_inputs")
    if not isinstance(bound, Mapping):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_bound_inputs_invalid"
        )
    required_refs = {
        "objective_ref",
        "runtime_registry_ref",
        "truth_spine_policy_ref",
        "consumer_policy_ref",
        "claim_authority_template_ref",
        "claim_surface_template_ref",
        "analysis_profile_ref",
        "submission_profile_ref",
        "predecessor_authority_ref",
        "predecessor_public_result_ref",
        "predecessor_private_result_ref",
        "predecessor_failure_assessment_ref",
        "value_repair_zero_call_result_ref",
        "scope_decision_ref",
        "runner_ref",
        "dynamic_runtime_ref",
        "claim_authority_runtime_ref",
        "claim_surface_runtime_ref",
        "five_cell_runtime_ref",
        "current_consumer_ref",
        "reviewed_anchor_runtime_ref",
        "provider_transport_ref",
        "strict_projection_ref",
    }
    scalar_keys = {
        "objective_id",
        "planner_messages_digest",
        "predecessor_plan_digest",
        "predecessor_controlled_plan_digest",
        "predecessor_public_result_digest",
        "predecessor_private_result_digest",
        "predecessor_failure_assessment_digest",
        "value_repair_zero_call_result_digest",
        "expected_base_research_input_digest",
        "expected_claim_surface_research_input_digest",
        "expected_evidence_pack_artifact_digest",
        "expected_evidence_pack_payload_digest",
        "expected_reviewed_anchor_digest",
        "expected_reviewed_anchor_target_id",
        "expected_reused_cell_digests",
        "expected_value_analysis_reuse_digest",
        "expected_rejected_arguments_digest",
    }
    expected = {
        item
        for key in required_refs
        for item in (key, key[:-4] + "_sha256")
    } | scalar_keys
    ref_keys = {key for key in bound if key.endswith("_ref")}
    if ref_keys != required_refs or set(bound) != expected:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_bound_inputs_invalid"
        )
    paths: dict[str, Path] = {}
    for key in required_refs:
        path = _resolve(str(bound[key]))
        if not path.is_file() or _sha(path) != str(bound[key[:-4] + "_sha256"]):
            raise DynamicFiveCellLiveError(
                f"five_cell_value_repair_successor_bound_input_drift:{key}"
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


def _validate_partial_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status") == PARTIAL_SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and tuple(payload.get("reused_cell_ids") or ())
        == PARTIAL_SUCCESSOR_REUSED_CELL_IDS
        and tuple(payload.get("remaining_cell_ids") or ())
        == PARTIAL_SUCCESSOR_REMAINING_CELL_IDS
        and payload.get("execution_budget")
        == PARTIAL_SUCCESSOR_EXPECTED_BUDGET
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_worktree_not_clean"
        )

    paths = _bound_partial_successor_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    failure_assessment = _json(paths["predecessor_failure_assessment_ref"])
    proof = _json(paths["partial_successor_zero_call_result_ref"])
    decision = _json(paths["partial_successor_scope_decision_ref"])
    predecessor_steps = {
        str(row.get("cell_id") or ""): row
        for row in predecessor_full.get("cell_steps") or []
    }
    expected_reused = bound.get("expected_reused_cell_digests")
    if not (
        predecessor_authority.get("schema_version")
        == SUCCESSOR_AUTHORITY_SCHEMA
        and predecessor_public.get("schema_version") == SUCCESSOR_RESULT_SCHEMA
        and predecessor_full.get("schema_version")
        == SUCCESSOR_FULL_RESULT_SCHEMA
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
        and (predecessor_full.get("execution") or {}).get(
            "model_calls_attempted"
        )
        == 7
        and (predecessor_full.get("execution") or {}).get(
            "cell_judgments_accepted"
        )
        == 2
        and (predecessor_full.get("execution") or {}).get("retries") == 0
        and (predecessor_full.get("execution") or {}).get("fallbacks") == 0
        and set(predecessor_steps) == set(REQUIRED_CELL_IDS)
        and isinstance(expected_reused, Mapping)
        and set(expected_reused) == set(PARTIAL_SUCCESSOR_REUSED_CELL_IDS)
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_predecessor_invalid"
        )
    for cell_id in PARTIAL_SUCCESSOR_REUSED_CELL_IDS:
        row = predecessor_steps[cell_id]
        if not (
            row.get("validated_cell")
            and row.get("raw_model_arguments")
            and not row.get("failure_code")
            and canonical_digest(row["validated_cell"])
            == str(expected_reused[cell_id])
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_partial_successor_reused_cell_invalid"
            )
    expected_failure_codes = {
        "CELL::value_capture": "model_gateway_reasoning_budget_exhausted",
        "CELL::cash_conversion": "five_cell_live_cell_analysis_length_stop",
        "CELL::counterevidence": "model_gateway_reasoning_budget_exhausted",
    }
    for cell_id in PARTIAL_SUCCESSOR_REMAINING_CELL_IDS:
        row = predecessor_steps[cell_id]
        if row.get("validated_cell") or row.get("failure_code") != (
            expected_failure_codes[cell_id]
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_partial_successor_failed_cell_invalid"
            )
    if not (
        failure_assessment.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_live_failure_assessment_v1_0"
        and failure_assessment.get("status")
        == "terminal_partial_two_of_five_contract_valid_three_analysis_budget_exhausted"
        and failure_assessment.get("result_digest")
        == bound["predecessor_public_result_digest"]
        and tuple(
            (failure_assessment.get("successor_disposition") or {}).get(
                "remaining_cell_ids"
            )
            or ()
        )
        == PARTIAL_SUCCESSOR_REMAINING_CELL_IDS
        and (failure_assessment.get("successor_disposition") or {}).get(
            "maximum_fresh_model_calls"
        )
        == 8
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_failure_assessment_invalid"
        )
    proof_acceptance = proof.get("acceptance") or {}
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_compact_analysis_partial_resume"
        and proof.get("result_digest")
        == bound["partial_successor_zero_call_result_digest"]
        and proof_acceptance.get("R2_preserved") is True
        and proof_acceptance.get("two_valid_cells_reused_not_rerun") is True
        and proof_acceptance.get("only_three_failed_cells_executed") is True
        and proof_acceptance.get("compact_analysis_projection_lossless") is True
        and proof_acceptance.get("fresh_model_calls_equal_eight") is True
        and proof_acceptance.get("synthesis_requires_all_five_cells") is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("partial_successor_live_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_zero_call_proof_invalid"
        )
    if not (
        decision.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_live_scope_decision_v1_0"
        and decision.get("status")
        == "approved_one_DELL_dynamic_five_cell_failed_three_plus_synthesis_exact_once"
        and decision.get("run_scope_id")
        == "one_DELL_dynamic_five_cell_partial_successor_failed_three_plus_synthesis"
        and decision.get("evidence_mode")
        == "immutable_dynamic_R2_prefix_two_valid_cells_no_new_evidence"
        and tuple(decision.get("reused_cell_ids") or ())
        == PARTIAL_SUCCESSOR_REUSED_CELL_IDS
        and tuple(decision.get("remaining_cell_ids") or ())
        == PARTIAL_SUCCESSOR_REMAINING_CELL_IDS
        and decision.get("execution_budget")
        == PARTIAL_SUCCESSOR_EXPECTED_BUDGET
        and decision.get("reuse_predecessor_planner") is True
        and decision.get("reuse_predecessor_current_S1_S2") is True
        and decision.get("reuse_predecessor_valid_cells") is True
        and decision.get("rerun_planner") is False
        and decision.get("rerun_current_S1_S2") is False
        and decision.get("rerun_valid_cells") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and decision.get("heterogeneous_generalization_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_scope_decision_invalid"
        )

    _, _, _, objective, messages = _compile_planner_contract(paths)
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_planner_prefix_binding_drift"
        )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    if analysis_profile.request_defaults.get("max_tokens") != 16000:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_analysis_profile_invalid"
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
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_output_invalid"
        )
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
        and set(cells) == set(PARTIAL_SUCCESSOR_REMAINING_CELL_IDS)
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
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_output_invalid"
        )
    identities = {
        *(str(value) for row in cells.values() for value in row.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 8:
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_output_identity_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_partial_successor_identity_consumed"
        )
    return paths


def _validate_node_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == NODE_SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status") == NODE_SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and tuple(payload.get("reused_cell_ids") or ())
        == NODE_SUCCESSOR_REUSED_CELL_IDS
        and tuple(payload.get("resubmission_cell_ids") or ())
        == NODE_SUCCESSOR_RESUBMISSION_CELL_IDS
        and payload.get("execution_budget") == NODE_SUCCESSOR_EXPECTED_BUDGET
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError("five_cell_node_successor_head_drift")
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_worktree_not_clean"
        )

    paths = _bound_node_successor_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    failure_assessment = _json(paths["predecessor_failure_assessment_ref"])
    strict_canary = _json(paths["strict_canary_result_ref"])
    proof = _json(paths["node_successor_zero_call_result_ref"])
    decision = _json(paths["node_successor_scope_decision_ref"])
    predecessor_steps = {
        str(row.get("cell_id") or ""): row
        for row in predecessor_full.get("cell_steps") or []
    }
    expected_reused = bound.get("expected_reused_cell_digests")
    expected_analyses = bound.get("expected_reused_analysis_digests")
    execution = predecessor_full.get("execution") or {}
    if not (
        predecessor_authority.get("schema_version")
        == PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA
        and predecessor_public.get("schema_version")
        == PARTIAL_SUCCESSOR_RESULT_SCHEMA
        and predecessor_full.get("schema_version")
        == PARTIAL_SUCCESSOR_FULL_RESULT_SCHEMA
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
        and execution.get("model_calls_attempted") == 6
        and execution.get("cell_analysis_calls_attempted") == 3
        and execution.get("cell_submission_calls_attempted") == 3
        and execution.get("cell_judgments_accepted") == 3
        and execution.get("synthesis_analysis_attempted") == 0
        and execution.get("synthesis_submission_attempted") == 0
        and execution.get("retries") == 0
        and execution.get("fallbacks") == 0
        and set(predecessor_steps) == set(REQUIRED_CELL_IDS)
        and isinstance(expected_reused, Mapping)
        and set(expected_reused) == set(NODE_SUCCESSOR_REUSED_CELL_IDS)
        and isinstance(expected_analyses, Mapping)
        and set(expected_analyses) == set(NODE_SUCCESSOR_RESUBMISSION_CELL_IDS)
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_predecessor_invalid"
        )
    for cell_id in NODE_SUCCESSOR_REUSED_CELL_IDS:
        row = predecessor_steps[cell_id]
        if not (
            row.get("validated_cell")
            and row.get("raw_model_arguments")
            and not row.get("failure_code")
            and canonical_digest(row["validated_cell"])
            == str(expected_reused[cell_id])
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_node_successor_reused_cell_invalid"
            )
    expected_failure_codes = {
        "CELL::value_capture": "research_consumer_mechanism_atom_invalid",
        "CELL::counterevidence": "research_consumer_thesis_atom_invalid",
    }
    for cell_id in NODE_SUCCESSOR_RESUBMISSION_CELL_IDS:
        row = predecessor_steps[cell_id]
        receipt = _validate_reused_analysis_capture(row)
        if not (
            not row.get("validated_cell")
            and row.get("failure_phase") == "cell_judgment_contract"
            and row.get("failure_code") == expected_failure_codes[cell_id]
            and receipt["analysis_reuse_digest"]
            == str(expected_analyses[cell_id])
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_node_successor_reused_analysis_invalid"
            )
    if not (
        failure_assessment.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_live_failure_assessment_v1_0"
        and failure_assessment.get("status")
        == "terminal_partial_three_of_five_contract_valid_two_strict_submission_surface_rejected"
        and failure_assessment.get("result_digest")
        == bound["predecessor_public_result_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_failure_assessment_invalid"
        )
    if not (
        strict_canary.get("schema_version")
        == "fin_ia_s3_deepseek_strict_pattern_canary_result_v1_0"
        and strict_canary.get("status")
        == "completed_deepseek_beta_strict_pattern_qualified"
        and strict_canary.get("result_digest")
        == bound["strict_canary_result_digest"]
        and (strict_canary.get("acceptance") or {}).get(
            "deepseek_beta_endpoint_accepted_schema"
        )
        is True
        and (strict_canary.get("acceptance") or {}).get(
            "strict_pattern_output_locally_valid"
        )
        is True
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_strict_canary_invalid"
        )
    proof_acceptance = proof.get("acceptance") or {}
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_node_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_R3_node_successor_strict_resubmission"
        and proof.get("result_digest")
        == bound["node_successor_zero_call_result_digest"]
        and proof_acceptance.get("R3_preserved") is True
        and proof_acceptance.get("three_valid_judgments_reused_not_rerun")
        is True
        and proof_acceptance.get(
            "two_analysis_drafts_capture_verified_and_reused"
        )
        is True
        and proof_acceptance.get("only_two_cell_submissions_executed") is True
        and proof_acceptance.get(
            "strict_projection_applied_to_all_three_submission_tools"
        )
        is True
        and proof_acceptance.get("fresh_model_calls_equal_four") is True
        and proof_acceptance.get("synthesis_requires_all_five_cells") is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("node_successor_live_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_zero_call_proof_invalid"
        )
    if not (
        decision.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_node_successor_live_scope_decision_v1_0"
        and decision.get("status")
        == "approved_one_DELL_dynamic_five_cell_two_submissions_plus_synthesis_exact_once"
        and decision.get("run_scope_id")
        == "one_DELL_dynamic_five_cell_node_successor_two_submissions_plus_synthesis"
        and decision.get("evidence_mode")
        == "immutable_dynamic_R3_three_valid_cells_two_analysis_drafts_no_new_evidence"
        and tuple(decision.get("reused_cell_ids") or ())
        == NODE_SUCCESSOR_REUSED_CELL_IDS
        and tuple(decision.get("resubmission_cell_ids") or ())
        == NODE_SUCCESSOR_RESUBMISSION_CELL_IDS
        and decision.get("execution_budget") == NODE_SUCCESSOR_EXPECTED_BUDGET
        and decision.get("reuse_predecessor_planner") is True
        and decision.get("reuse_predecessor_current_S1_S2") is True
        and decision.get("reuse_predecessor_valid_cells") is True
        and decision.get("reuse_predecessor_analysis_drafts") is True
        and decision.get("rerun_planner") is False
        and decision.get("rerun_current_S1_S2") is False
        and decision.get("rerun_cell_analysis") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and decision.get("heterogeneous_generalization_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_scope_decision_invalid"
        )

    _, _, _, objective, messages = _compile_planner_contract(paths)
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_planner_prefix_binding_drift"
        )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    if analysis_profile.request_defaults.get("max_tokens") != 16000:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_analysis_profile_invalid"
        )
    validate_deepseek_strict_submission_profile(submission_profile)

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
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_output_invalid"
        )
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
        and set(cells) == set(NODE_SUCCESSOR_RESUBMISSION_CELL_IDS)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"submission_attempt_id"}
            and str(row.get("submission_attempt_id") or "")
            for row in cells.values()
        )
        and isinstance(synthesis, Mapping)
        and set(synthesis) == {"analysis_attempt_id", "submission_attempt_id"}
        and all(str(value or "") for value in synthesis.values())
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_output_invalid"
        )
    identities = {
        *(str(row["submission_attempt_id"]) for row in cells.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 4:
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_output_identity_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_node_successor_identity_consumed"
        )
    return paths


def _validate_claim_surface_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version")
        == CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status")
        == CLAIM_SURFACE_SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and payload.get("execution_budget")
        == CLAIM_SURFACE_SUCCESSOR_EXPECTED_BUDGET
        and payload.get("rerun_cell_ids") == list(REQUIRED_CELL_IDS)
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_worktree_not_clean"
        )

    paths = _bound_claim_surface_successor_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    failure_assessment = _json(paths["predecessor_failure_assessment_ref"])
    decision = _json(paths["scope_decision_ref"])
    predecessor_steps = {
        str(row.get("cell_id") or ""): row
        for row in predecessor_full.get("cell_steps") or ()
    }
    expected_failures = {
        "CELL::value_capture": "research_consumer_mechanism_atom_invalid",
        "CELL::counterevidence": (
            "research_consumer_supported_judgment_without_evidence"
        ),
    }
    if not (
        predecessor_authority.get("schema_version")
        == NODE_SUCCESSOR_AUTHORITY_SCHEMA
        and predecessor_public.get("schema_version")
        == NODE_SUCCESSOR_RESULT_SCHEMA
        and predecessor_full.get("schema_version")
        == NODE_SUCCESSOR_FULL_RESULT_SCHEMA
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
        and set(predecessor_steps) == set(REQUIRED_CELL_IDS)
        and all(
            not predecessor_steps[cell_id].get("validated_cell")
            and predecessor_steps[cell_id].get("failure_code") == code
            for cell_id, code in expected_failures.items()
        )
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_predecessor_invalid"
        )
    if not (
        failure_assessment.get("schema_version")
        == (
            "fin_ia_s3_dynamic_five_cell_node_successor_live_"
            "failure_assessment_v1_0"
        )
        and failure_assessment.get("status")
        == (
            "terminal_three_of_five_contract_valid_remote_strict_pattern_"
            "nonconforming_and_financial_authority_fail_closed"
        )
        and failure_assessment.get("result_digest")
        == bound["predecessor_failure_assessment_result_digest"]
        and (failure_assessment.get("disposition") or {}).get(
            "preserve_R1_R2_R3_and_R4_immutable"
        )
        is True
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_failure_assessment_invalid"
        )
    cell_scoped_successor = (
        decision.get("schema_version")
        == CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE_DECISION_SCHEMA
    )
    expected_decision_status = (
        CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE_DECISION_STATUS
        if cell_scoped_successor
        else CLAIM_SURFACE_SUCCESSOR_SCOPE_DECISION_STATUS
    )
    if not (
        decision.get("schema_version")
        in {
            CLAIM_SURFACE_SUCCESSOR_SCOPE_DECISION_SCHEMA,
            CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE_DECISION_SCHEMA,
        }
        and decision.get("status") == expected_decision_status
        and decision.get("execution_budget")
        == CLAIM_SURFACE_SUCCESSOR_EXPECTED_BUDGET
        and decision.get("reuse_predecessor_planner_and_controlled_plan") is True
        and decision.get("rerun_all_five_analysis_and_submission_nodes") is True
        and decision.get("reuse_predecessor_cell_analysis_or_judgments") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and decision.get("heterogeneous_generalization_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_scope_decision_invalid"
        )
    if cell_scoped_successor:
        zero_path = _resolve(
            str(decision.get("cell_scoped_zero_call_result_ref") or "")
        )
        failed_path = _resolve(
            str(decision.get("failed_attempt_result_ref") or "")
        )
        assessment_path = _resolve(
            str(
                decision.get("failed_attempt_failure_assessment_ref") or ""
            )
        )
        if not all(path.is_file() for path in (zero_path, failed_path, assessment_path)):
            raise DynamicFiveCellLiveError(
                "five_cell_claim_surface_successor_repair_artifact_missing"
            )
        zero_result = _json(zero_path)
        failed_result = _json(failed_path)
        failed_assessment = _json(assessment_path)
        if not (
            _sha(zero_path)
            == decision.get("cell_scoped_zero_call_result_sha256")
            and zero_result.get("result_digest")
            == decision.get("cell_scoped_zero_call_result_digest")
            and _sha(failed_path)
            == decision.get("failed_attempt_result_sha256")
            and failed_result.get("result_digest")
            == decision.get("failed_attempt_result_digest")
            and _sha(assessment_path)
            == decision.get("failed_attempt_failure_assessment_sha256")
            and failed_assessment.get("assessment_digest")
            == decision.get("failed_attempt_failure_assessment_digest")
            and decision.get("cell_scoped_claim_contract_required") is True
            and decision.get("typed_unexpected_exception_terminal_required")
            is True
            and decision.get("failed_attempt_run_id")
            == "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R5"
            and decision.get("failed_attempt_authority_consumed") is True
            and decision.get("failed_attempt_reuse_forbidden") is True
            and failed_result.get("status")
            == "terminal_unexpected_project_exception_preserved_no_retry"
            and (failed_assessment.get("disposition") or {}).get(
                "R5_rerun_forbidden"
            )
            is True
            and (zero_result.get("contract_proof") or {}).get(
                "nonqualified_messages_omit_claim_contracts_and_relation_aliases"
            )
            is True
            and (zero_result.get("contract_proof") or {}).get(
                "unexpected_project_exception_materializes_terminal_result"
            )
            is True
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_claim_surface_successor_repair_artifact_invalid"
            )

    _, _, _, objective, messages = _compile_planner_contract(paths)
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_planner_binding_drift"
        )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    if analysis_profile.request_defaults.get("max_tokens") != 16000:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_analysis_profile_invalid"
        )
    validate_deepseek_strict_submission_profile(submission_profile)

    evidence_service, _ = _services()
    permissions = frozenset({"current_product:read"})
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    if not (
        evidence_pack.get("artifact_digest")
        == bound["expected_evidence_pack_artifact_digest"]
        and evidence_pack.get("pack_payload_digest")
        == bound["expected_evidence_pack_payload_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_pack_binding_drift"
        )
    base_projection = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(paths["truth_spine_policy_ref"]),
        consumer_policy=_json(paths["consumer_policy_ref"]),
        controlled_plan=predecessor_full["controlled_plan"],
        evidence_pack=evidence_pack,
    )
    base_input = base_projection["dynamic_research_input"]
    surface_projection = compile_dynamic_claim_surface_projection(
        dynamic_research_input=base_input,
        claim_authority_template=_json(paths["claim_authority_template_ref"]),
        claim_surface_template=_json(paths["claim_surface_template_ref"]),
    )
    surface_input = surface_projection["claim_surface_research_input"]
    margin_evidence = next(
        (
            row
            for row in surface_input.get("evidence_cards") or ()
            if row.get("evidence_ref") == "EV::5388E016C17032C1"
        ),
        None,
    )
    value_cell = next(
        (
            row
            for row in surface_input.get("cells") or ()
            if row.get("cell_id") == "CELL::value_capture"
        ),
        None,
    )
    if not (
        base_input.get("research_input_digest")
        == bound["expected_base_research_input_digest"]
        and surface_input.get("research_input_digest")
        == bound["expected_claim_surface_research_input_digest"]
        and isinstance(margin_evidence, Mapping)
        and margin_evidence.get("target_id")
        == bound["expected_reviewed_anchor_target_id"]
        and (margin_evidence.get("reviewed_anchor_receipt") or {}).get(
            "anchor_digest"
        )
        == bound["expected_reviewed_anchor_digest"]
        and isinstance(value_cell, Mapping)
        and "CR::DELL::HISTORICAL_MIX_PRESSURE"
        in set(
            (surface_input.get("model_output_contract") or {}).get(
                "allowed_claim_relation_refs"
            )
            or ()
        )
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_projection_drift"
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
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_output_invalid"
        )
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
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_output_invalid"
        )
    identities = {
        *(str(value) for row in cells.values() for value in row.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 12:
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_output_identity_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_claim_surface_successor_identity_consumed"
        )
    return paths


def _validate_value_repair_successor_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if not (
        payload.get("schema_version") == VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA
        and payload.get("status") == VALUE_REPAIR_SUCCESSOR_AUTHORITY_STATUS
        and payload.get("case_key") == "DELL"
        and tuple(payload.get("required_cell_ids") or ()) == REQUIRED_CELL_IDS
        and tuple(payload.get("reused_cell_ids") or ())
        == VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS
        and tuple(payload.get("resubmission_cell_ids") or ())
        == VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS
        and payload.get("execution_budget")
        == VALUE_REPAIR_SUCCESSOR_EXPECTED_BUDGET
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_authority_invalid"
        )
    commit = str(payload.get("implementation_commit") or "").lower()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_commit_invalid"
        )
    if _git("rev-parse", "HEAD").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_head_drift"
        )
    if _git("rev-parse", "@{upstream}").lower() != commit:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_upstream_drift"
        )
    allowed = f"?? {_relative(authority_path)}"
    status = _git("status", "--porcelain=v1", "--untracked-files=all")
    if [line for line in status.splitlines() if line] != [allowed]:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_worktree_not_clean"
        )

    paths = _bound_value_repair_successor_paths(payload)
    bound = payload["bound_inputs"]
    predecessor_authority = _json(paths["predecessor_authority_ref"])
    predecessor_public = _json(paths["predecessor_public_result_ref"])
    predecessor_full = _json(paths["predecessor_private_result_ref"])
    failure_assessment = _json(paths["predecessor_failure_assessment_ref"])
    proof = _json(paths["value_repair_zero_call_result_ref"])
    decision = _json(paths["scope_decision_ref"])
    predecessor_steps = {
        str(row.get("cell_id") or ""): row
        for row in predecessor_full.get("cell_steps") or ()
    }
    expected_reused = bound.get("expected_reused_cell_digests")
    execution = predecessor_full.get("execution") or {}
    if not (
        predecessor_authority.get("schema_version")
        == CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA
        and predecessor_public.get("schema_version")
        == CLAIM_SURFACE_SUCCESSOR_RESULT_SCHEMA
        and predecessor_full.get("schema_version")
        == CLAIM_SURFACE_SUCCESSOR_FULL_RESULT_SCHEMA
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
        and execution.get("model_calls_attempted") == 10
        and execution.get("cell_analysis_calls_attempted") == 5
        and execution.get("cell_submission_calls_attempted") == 5
        and execution.get("cell_judgments_accepted") == 4
        and execution.get("synthesis_analysis_attempted") == 0
        and execution.get("synthesis_submission_attempted") == 0
        and execution.get("retries") == 0
        and execution.get("fallbacks") == 0
        and set(predecessor_steps) == set(REQUIRED_CELL_IDS)
        and isinstance(expected_reused, Mapping)
        and set(expected_reused) == set(VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS)
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_predecessor_invalid"
        )
    for cell_id in VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS:
        row = predecessor_steps[cell_id]
        if not (
            row.get("validated_cell")
            and row.get("raw_model_arguments")
            and not row.get("failure_code")
            and canonical_digest(row["validated_cell"])
            == str(expected_reused[cell_id])
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_value_repair_successor_reused_cell_invalid"
            )
    value_row = predecessor_steps["CELL::value_capture"]
    analysis_receipt = _validate_reused_analysis_capture(value_row)
    if not (
        not value_row.get("validated_cell")
        and value_row.get("failure_phase") == "cell_judgment_contract"
        and value_row.get("failure_code")
        == "research_consumer_numeric_relation_boundary_invalid"
        and canonical_digest(value_row.get("raw_model_arguments") or {})
        == bound["expected_rejected_arguments_digest"]
        and analysis_receipt["analysis_reuse_digest"]
        == bound["expected_value_analysis_reuse_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_value_capture_invalid"
        )
    if not (
        failure_assessment.get("schema_version")
        == (
            "fin_ia_s3_dynamic_five_cell_cell_scoped_claim_contract_"
            "successor_failure_assessment_v1_0"
        )
        and failure_assessment.get("status")
        == (
            "terminal_four_of_five_value_relation_endpoint_and_"
            "structured_support_contract_failure"
        )
        and failure_assessment.get("assessment_digest")
        == bound["predecessor_failure_assessment_digest"]
        and (failure_assessment.get("disposition") or {}).get(
            "R6_authority_consumed"
        )
        is True
        and (failure_assessment.get("disposition") or {}).get(
            "R6_rerun_forbidden"
        )
        is True
        and (failure_assessment.get("disposition") or {}).get(
            "fresh_successor_maximum_model_calls"
        )
        == 3
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_failure_assessment_invalid"
        )

    proof_acceptance = proof.get("acceptance") or {}
    replay = proof.get("successor_fake_replay") or {}
    if not (
        proof.get("schema_version")
        == (
            "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
            "successor_zero_call_result_v1_0"
        )
        and proof.get("status")
        == "engineering_pass_zero_call_R6_value_repair_plus_synthesis_successor"
        and proof.get("result_digest")
        == bound["value_repair_zero_call_result_digest"]
        and replay.get("fresh_model_calls_attempted") == 3
        and replay.get("reused_predecessor_cell_judgments") == 4
        and replay.get("reused_predecessor_analysis_drafts") == 1
        and replay.get("cell_submission_calls_attempted") == 1
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_analysis_calls_attempted") == 1
        and replay.get("synthesis_submission_calls_attempted") == 1
        and proof_acceptance.get("R6_preserved") is True
        and proof_acceptance.get("four_valid_judgments_reused_not_rerun")
        is True
        and proof_acceptance.get("value_analysis_capture_verified_and_reused")
        is True
        and proof_acceptance.get("rejected_value_submission_not_promoted")
        is True
        and proof_acceptance.get("relation_endpoints_bind_locally") is True
        and proof_acceptance.get("structured_financial_support_recognized")
        is True
        and proof_acceptance.get("only_one_typed_value_repair_submission")
        is True
        and proof_acceptance.get("synthesis_requires_all_five_cells") is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("successor_live_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_zero_call_proof_invalid"
        )
    if not (
        decision.get("schema_version")
        == VALUE_REPAIR_SUCCESSOR_SCOPE_DECISION_SCHEMA
        and decision.get("status")
        == VALUE_REPAIR_SUCCESSOR_SCOPE_DECISION_STATUS
        and decision.get("run_scope_id")
        == "one_DELL_dynamic_five_cell_value_submission_repair_plus_synthesis"
        and decision.get("evidence_mode")
        == "immutable_R6_four_valid_cells_value_analysis_and_current_S1_S2"
        and tuple(decision.get("reused_cell_ids") or ())
        == VALUE_REPAIR_SUCCESSOR_REUSED_CELL_IDS
        and tuple(decision.get("resubmission_cell_ids") or ())
        == VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS
        and decision.get("execution_budget")
        == VALUE_REPAIR_SUCCESSOR_EXPECTED_BUDGET
        and decision.get("reuse_predecessor_planner") is True
        and decision.get("reuse_predecessor_current_S1_S2") is True
        and decision.get("reuse_predecessor_valid_cells") is True
        and decision.get("reuse_predecessor_value_analysis") is True
        and decision.get("reuse_rejected_value_call_only_as_typed_feedback")
        is True
        and decision.get("rerun_planner") is False
        and decision.get("rerun_current_S1_S2") is False
        and decision.get("rerun_cell_analysis") is False
        and decision.get("product_publication_authorized") is False
        and decision.get("S3_acceptance_authorized") is False
        and decision.get("heterogeneous_generalization_authorized") is False
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_scope_decision_invalid"
        )

    _, _, _, objective, messages = _compile_planner_contract(paths)
    if not (
        objective.objective_id == bound["objective_id"]
        and canonical_digest(list(messages)) == bound["planner_messages_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_planner_binding_drift"
        )
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile_ref"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile_ref"])
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    if analysis_profile.request_defaults.get("max_tokens") != 16000:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_analysis_profile_invalid"
        )
    validate_deepseek_strict_submission_profile(submission_profile)

    evidence_service, _ = _services()
    permissions = frozenset({"current_product:read"})
    evidence_pack = evidence_service.get_case(
        "DELL", ResearchEvidencePackPrincipal("current", permissions)
    )
    base_projection = compile_dynamic_research_input_projection(
        truth_spine_policy=_json(paths["truth_spine_policy_ref"]),
        consumer_policy=_json(paths["consumer_policy_ref"]),
        controlled_plan=predecessor_full["controlled_plan"],
        evidence_pack=evidence_pack,
    )
    base_input = base_projection["dynamic_research_input"]
    surface_projection = compile_dynamic_claim_surface_projection(
        dynamic_research_input=base_input,
        claim_authority_template=_json(paths["claim_authority_template_ref"]),
        claim_surface_template=_json(paths["claim_surface_template_ref"]),
    )
    surface_input = surface_projection["claim_surface_research_input"]
    margin_evidence = next(
        (
            row
            for row in surface_input.get("evidence_cards") or ()
            if row.get("evidence_ref") == "EV::5388E016C17032C1"
        ),
        None,
    )
    if not (
        evidence_pack.get("artifact_digest")
        == bound["expected_evidence_pack_artifact_digest"]
        and evidence_pack.get("pack_payload_digest")
        == bound["expected_evidence_pack_payload_digest"]
        and base_input.get("research_input_digest")
        == bound["expected_base_research_input_digest"]
        and surface_input.get("research_input_digest")
        == bound["expected_claim_surface_research_input_digest"]
        and isinstance(margin_evidence, Mapping)
        and margin_evidence.get("target_id")
        == bound["expected_reviewed_anchor_target_id"]
        and (margin_evidence.get("reviewed_anchor_receipt") or {}).get(
            "anchor_digest"
        )
        == bound["expected_reviewed_anchor_digest"]
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_projection_drift"
        )
    try:
        validate_current_research_output(
            {"cells": [value_row["raw_model_arguments"]]},
            research_input=surface_input,
            required_cell_ids=VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS,
        )
    except CurrentResearchConsumerError as exc:
        if exc.code != "research_consumer_thesis_atom_invalid":
            raise DynamicFiveCellLiveError(
                "five_cell_value_repair_successor_replay_failure_drift"
            ) from exc
    else:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_rejected_call_became_valid"
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
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_output_invalid"
        )
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
        and set(cells) == set(VALUE_REPAIR_SUCCESSOR_RESUBMISSION_CELL_IDS)
        and all(
            isinstance(row, Mapping)
            and set(row) == {"submission_attempt_id"}
            and str(row.get("submission_attempt_id") or "")
            for row in cells.values()
        )
        and isinstance(synthesis, Mapping)
        and set(synthesis) == {"analysis_attempt_id", "submission_attempt_id"}
        and all(str(value or "") for value in synthesis.values())
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_output_invalid"
        )
    identities = {
        *(str(row["submission_attempt_id"]) for row in cells.values()),
        *(str(value) for value in synthesis.values()),
    }
    if len(identities) != 3:
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_output_identity_invalid"
        )
    capture_run = _resolve(str(output["capture_root_ref"])) / str(output["run_id"])
    if (
        capture_run.exists()
        or _resolve(str(output["private_output_root_ref"])).exists()
        or _resolve(str(output["public_result_ref"])).exists()
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_value_repair_successor_identity_consumed"
        )
    return paths


def validate_authority(
    payload: Mapping[str, Any], *, authority_path: Path
) -> dict[str, Path]:
    if payload.get("schema_version") == VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA:
        return _validate_value_repair_successor_authority(
            payload, authority_path=authority_path
        )
    if payload.get("schema_version") == CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA:
        return _validate_claim_surface_successor_authority(
            payload, authority_path=authority_path
        )
    if payload.get("schema_version") == NODE_SUCCESSOR_AUTHORITY_SCHEMA:
        return _validate_node_successor_authority(
            payload, authority_path=authority_path
        )
    if payload.get("schema_version") == PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA:
        return _validate_partial_successor_authority(
            payload, authority_path=authority_path
        )
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


def _unexpected_project_failure_code(exc: Exception) -> str:
    return "five_cell_unexpected_project_exception_" + type(exc).__name__.lower()


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
    value_repair_successor_mode = (
        authority.get("schema_version")
        == VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA
    )
    node_successor_mode = (
        authority.get("schema_version") == NODE_SUCCESSOR_AUTHORITY_SCHEMA
    )
    partial_successor_mode = (
        authority.get("schema_version") == PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA
    )
    claim_surface_successor_mode = (
        authority.get("schema_version")
        == CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA
    )
    claim_surface_input_mode = (
        claim_surface_successor_mode or value_repair_successor_mode
    )
    successor_mode = authority.get("schema_version") in {
        SUCCESSOR_AUTHORITY_SCHEMA,
        PARTIAL_SUCCESSOR_AUTHORITY_SCHEMA,
        NODE_SUCCESSOR_AUTHORITY_SCHEMA,
        CLAIM_SURFACE_SUCCESSOR_AUTHORITY_SCHEMA,
        VALUE_REPAIR_SUCCESSOR_AUTHORITY_SCHEMA,
    }
    paths = validate_authority(authority, authority_path=authority_path)
    reused_cell_ids = (
        tuple(authority.get("reused_cell_ids") or ())
        if (
            partial_successor_mode
            or node_successor_mode
            or value_repair_successor_mode
        )
        else ()
    )
    remaining_cell_ids = (
        tuple(authority.get("resubmission_cell_ids") or ())
        if node_successor_mode or value_repair_successor_mode
        else (
            tuple(authority.get("remaining_cell_ids") or ())
            if partial_successor_mode
            else REQUIRED_CELL_IDS
        )
    )
    if (
        partial_successor_mode
        or node_successor_mode
        or value_repair_successor_mode
    ) and not (
        set(reused_cell_ids).isdisjoint(remaining_cell_ids)
        and set(reused_cell_ids) | set(remaining_cell_ids)
        == set(REQUIRED_CELL_IDS)
    ):
        raise DynamicFiveCellLiveError(
            "five_cell_successor_resume_manifest_invalid"
        )
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
        "tool_schema_digest": "",
        "wire_tool_schema_digest": "",
        "tool_projection_receipt": {},
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
        base_research_input = dynamic_projection["dynamic_research_input"]
        if not base_research_input:
            raise DynamicFiveCellLiveError(
                "five_cell_live_no_reviewed_evidence_selected"
            )
        if claim_surface_input_mode:
            if base_research_input.get("research_input_digest") != authority[
                "bound_inputs"
            ]["expected_base_research_input_digest"]:
                raise DynamicFiveCellLiveError(
                    "five_cell_claim_surface_successor_base_input_drift"
                )
            claim_surface_projection = compile_dynamic_claim_surface_projection(
                dynamic_research_input=base_research_input,
                claim_authority_template=_json(
                    paths["claim_authority_template_ref"]
                ),
                claim_surface_template=_json(paths["claim_surface_template_ref"]),
            )
            research_input = claim_surface_projection[
                "claim_surface_research_input"
            ]
            dynamic_projection = {
                **dynamic_projection,
                "claim_surface_projection": claim_surface_projection,
                "effective_research_input_digest": research_input[
                    "research_input_digest"
                ],
            }
            if research_input.get("research_input_digest") != authority[
                "bound_inputs"
            ]["expected_claim_surface_research_input_digest"]:
                raise DynamicFiveCellLiveError(
                    "five_cell_claim_surface_successor_input_drift"
                )
        else:
            research_input = base_research_input
        if (
            successor_mode
            and not claim_surface_input_mode
            and research_input.get("research_input_digest")
            != authority["bound_inputs"]["expected_research_input_digest"]
        ):
            raise DynamicFiveCellLiveError(
                "five_cell_successor_research_input_drift"
            )
        actual_cells = tuple(row["cell_id"] for row in research_input["cells"])
        if actual_cells != REQUIRED_CELL_IDS:
            raise DynamicFiveCellLiveError("five_cell_live_cell_scope_drift")

        predecessor_cells = (
            {
                str(row.get("cell_id") or ""): row
                for row in predecessor.get("cell_steps") or []
            }
            if (
                partial_successor_mode
                or node_successor_mode
                or value_repair_successor_mode
            )
            else {}
        )
        for cell_id in REQUIRED_CELL_IDS:
            if (
                partial_successor_mode
                or node_successor_mode
                or value_repair_successor_mode
            ) and cell_id in reused_cell_ids:
                row = deepcopy(predecessor_cells[cell_id])
                raw = deepcopy(row.get("raw_model_arguments") or {})
                validated = validate_current_research_output(
                    {"cells": [raw]},
                    research_input=research_input,
                    required_cell_ids=[cell_id],
                )["cells"][0]
                if not (
                    validated
                    and canonical_digest(validated)
                    == canonical_digest(row.get("validated_cell") or {})
                    and not row.get("failure_code")
                ):
                    raise DynamicFiveCellLiveError(
                        "five_cell_partial_successor_reused_cell_drift"
                    )
                row["reused_from_predecessor"] = True
                row["analysis_reused_from_predecessor"] = True
                row.setdefault("analysis_capture_receipt", {})
                row.setdefault("wire_tool_schema_digest", "")
                row.setdefault("tool_projection_receipt", {})
                row.setdefault("submission_repair_receipt", {})
                cell_steps.append(row)
                accepted_raw_cells.append(raw)
                continue

            attempts = output["cell_attempt_ids"][cell_id]
            row: dict[str, Any] = {
                "cell_id": cell_id,
                "reused_from_predecessor": False,
                "analysis_reused_from_predecessor": False,
                "analysis_capture_receipt": {},
                "analysis_messages_digest": "",
                "submission_messages_digest": "",
                "tool_schema_digest": "",
                "wire_tool_schema_digest": "",
                "tool_projection_receipt": {},
                "submission_repair_receipt": {},
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
                if node_successor_mode or value_repair_successor_mode:
                    predecessor_row = predecessor_cells[cell_id]
                    receipt = _validate_reused_analysis_capture(predecessor_row)
                    expected_digest = str(
                        authority["bound_inputs"][
                            "expected_value_analysis_reuse_digest"
                        ]
                        if value_repair_successor_mode
                        else authority["bound_inputs"][
                            "expected_reused_analysis_digests"
                        ][cell_id]
                    )
                    if receipt["analysis_reuse_digest"] != expected_digest:
                        raise DynamicFiveCellLiveError(
                            "five_cell_successor_analysis_digest_drift"
                        )
                    row["analysis_reused_from_predecessor"] = True
                    row["analysis_capture_receipt"] = receipt
                    row["analysis_messages_digest"] = str(
                        predecessor_row["analysis_messages_digest"]
                    )
                    row["analysis_step"] = deepcopy(
                        predecessor_row["analysis_step"]
                    )
                    analysis_draft = str(row["analysis_step"]["content"])
                else:
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
                    analysis_draft = analysis.content
                if value_repair_successor_mode:
                    predecessor_row = predecessor_cells[cell_id]
                    submission_messages, tool, repair_receipt = (
                        compile_five_cell_submission_repair(
                            research_input=research_input,
                            cell_id=cell_id,
                            analysis_draft=analysis_draft,
                            rejected_arguments=predecessor_row[
                                "raw_model_arguments"
                            ],
                            terminal_failure_code=(
                                "research_consumer_thesis_atom_invalid"
                            ),
                        )
                    )
                    row["submission_repair_receipt"] = repair_receipt
                else:
                    submission_messages, tool = compile_five_cell_submission(
                        research_input=research_input,
                        cell_id=cell_id,
                        analysis_draft=analysis_draft,
                    )
                row["submission_messages_digest"] = canonical_digest(
                    list(submission_messages)
                )
                row["tool_schema_digest"] = canonical_digest(tool)
                wire_tool = tool
                if (
                    node_successor_mode
                    or claim_surface_successor_mode
                    or value_repair_successor_mode
                ):
                    wire_tool, projection = project_deepseek_strict_tool(tool)
                    row["tool_projection_receipt"] = projection
                row["wire_tool_schema_digest"] = canonical_digest(wire_tool)
                model_calls_attempted += 1
                submission = submission_executor(
                    profile=submission_profile,
                    messages=submission_messages,
                    tools=[wire_tool],
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
            except Exception as exc:
                row.update(
                    _failure(
                        phase="cell_unexpected_project_exception",
                        code=_unexpected_project_failure_code(exc),
                    )
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
                wire_synthesis_tool = synthesis_tool
                if (
                    node_successor_mode
                    or claim_surface_successor_mode
                    or value_repair_successor_mode
                ):
                    wire_synthesis_tool, projection = project_deepseek_strict_tool(
                        synthesis_tool
                    )
                    synthesis_steps["tool_projection_receipt"] = projection
                synthesis_steps["wire_tool_schema_digest"] = canonical_digest(
                    wire_synthesis_tool
                )
                model_calls_attempted += 1
                submission = submission_executor(
                    profile=submission_profile,
                    messages=submission_messages,
                    tools=[wire_synthesis_tool],
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
            except Exception as exc:
                synthesis_steps.update(
                    _failure(
                        phase="synthesis_unexpected_project_exception",
                        code=_unexpected_project_failure_code(exc),
                    )
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
    except Exception as exc:
        orchestration_failure = _failure(
            phase="five_cell_unexpected_project_exception",
            code=_unexpected_project_failure_code(exc),
        )

    accepted_count = sum(bool(row["validated_cell"]) for row in cell_steps)
    succeeded = bool(final_report)
    status = (
        "completed_five_cell_report_contract_valid_content_assessment_pending"
        if succeeded
        else "terminal_failed_or_partial_no_retry"
    )
    full_result_schema = (
        VALUE_REPAIR_SUCCESSOR_FULL_RESULT_SCHEMA
        if value_repair_successor_mode
        else (
            CLAIM_SURFACE_SUCCESSOR_FULL_RESULT_SCHEMA
            if claim_surface_successor_mode
            else (
                NODE_SUCCESSOR_FULL_RESULT_SCHEMA
                if node_successor_mode
                else (
                    PARTIAL_SUCCESSOR_FULL_RESULT_SCHEMA
                    if partial_successor_mode
                    else (
                        SUCCESSOR_FULL_RESULT_SCHEMA
                        if successor_mode
                        else FULL_RESULT_SCHEMA
                    )
                )
            )
        )
    )
    public_result_schema = (
        VALUE_REPAIR_SUCCESSOR_RESULT_SCHEMA
        if value_repair_successor_mode
        else (
            CLAIM_SURFACE_SUCCESSOR_RESULT_SCHEMA
            if claim_surface_successor_mode
            else (
                NODE_SUCCESSOR_RESULT_SCHEMA
                if node_successor_mode
                else (
                    PARTIAL_SUCCESSOR_RESULT_SCHEMA
                    if partial_successor_mode
                    else (
                        SUCCESSOR_RESULT_SCHEMA
                        if successor_mode
                        else RESULT_SCHEMA
                    )
                )
            )
        )
    )
    maximum_model_calls = (
        VALUE_REPAIR_SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
        if value_repair_successor_mode
        else (
            CLAIM_SURFACE_SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
            if claim_surface_successor_mode
            else (
                NODE_SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
                if node_successor_mode
                else (
                    PARTIAL_SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
                    if partial_successor_mode
                    else (
                        SUCCESSOR_EXPECTED_BUDGET["maximum_model_calls"]
                        if successor_mode
                        else EXPECTED_BUDGET["maximum_model_calls"]
                    )
                )
            )
        )
    )
    full_body = {
        "schema_version": full_result_schema,
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
                "reused_cell_ids": (
                    list(reused_cell_ids)
                    if (
                        partial_successor_mode
                        or node_successor_mode
                        or value_repair_successor_mode
                    )
                    else []
                ),
                "remaining_cell_ids": (
                    list(remaining_cell_ids)
                    if (
                        partial_successor_mode
                        or node_successor_mode
                        or value_repair_successor_mode
                    )
                    else list(REQUIRED_CELL_IDS)
                ),
                "valid_cells_rerun": claim_surface_successor_mode,
                "analysis_drafts_reused": (
                    node_successor_mode or value_repair_successor_mode
                ),
                "cell_analysis_rerun": (
                    False
                    if node_successor_mode or value_repair_successor_mode
                    else (True if claim_surface_successor_mode else None)
                ),
                "claim_surface_successor": claim_surface_successor_mode,
                "value_submission_repair_successor": (
                    value_repair_successor_mode
                ),
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
            "maximum_model_calls": maximum_model_calls,
            "planner_calls_completed": (
                0 if successor_mode else int(bool(planner_output))
            ),
            "planner_calls_reused": int(successor_mode and bool(planner_output)),
            "cell_analysis_calls_attempted": sum(
                bool(row["analysis_step"])
                and not row.get("reused_from_predecessor", False)
                and not row.get("analysis_reused_from_predecessor", False)
                for row in cell_steps
            ),
            "cell_analysis_drafts_reused": sum(
                bool(row["analysis_step"])
                and row.get("analysis_reused_from_predecessor", False)
                and not row.get("reused_from_predecessor", False)
                for row in cell_steps
            ),
            "cell_submission_calls_attempted": sum(
                bool(row["submission_step"])
                and not row.get("reused_from_predecessor", False)
                for row in cell_steps
            ),
            "cell_judgments_accepted": accepted_count,
            "cell_judgments_reused": sum(
                bool(row["validated_cell"])
                and row.get("reused_from_predecessor", False)
                for row in cell_steps
            ),
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
        "schema_version": public_result_schema,
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
            dynamic_projection.get("effective_research_input_digest")
            or (dynamic_projection.get("dynamic_research_input") or {}).get(
                "research_input_digest", ""
            )
            if dynamic_projection
            else ""
        ),
        "cells": [
            {
                "cell_id": row["cell_id"],
                "reused_from_predecessor": row.get(
                    "reused_from_predecessor", False
                ),
                "analysis_reused_from_predecessor": row.get(
                    "analysis_reused_from_predecessor", False
                ),
                "analysis_capture_receipt": row.get(
                    "analysis_capture_receipt", {}
                ),
                "analysis_messages_digest": row["analysis_messages_digest"],
                "submission_messages_digest": row["submission_messages_digest"],
                "tool_schema_digest": row["tool_schema_digest"],
                "wire_tool_schema_digest": row.get(
                    "wire_tool_schema_digest", ""
                ),
                "tool_projection_receipt": row.get(
                    "tool_projection_receipt", {}
                ),
                "submission_repair_receipt": row.get(
                    "submission_repair_receipt", {}
                ),
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
            "wire_tool_schema_digest": synthesis_steps.get(
                "wire_tool_schema_digest", ""
            ),
            "tool_projection_receipt": synthesis_steps.get(
                "tool_projection_receipt", {}
            ),
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
            "natural_planner_executed": bool(planner_output)
            and not successor_mode,
            "natural_planner_reused_not_rerun": successor_mode,
            "current_S1_S2_EvidenceResponse_available": bool(responses),
            "current_S1_S2_EvidenceResponse_executed": bool(responses)
            and not successor_mode,
            "current_S1_S2_reused_not_rerun": successor_mode,
            "valid_cell_judgments_reused_not_rerun": (
                (
                    partial_successor_mode
                    and full_body["execution"]["cell_judgments_reused"] == 2
                )
                or (
                    node_successor_mode
                    and full_body["execution"]["cell_judgments_reused"] == 3
                )
                or (
                    value_repair_successor_mode
                    and full_body["execution"]["cell_judgments_reused"] == 4
                )
            ),
            "analysis_drafts_reused_not_rerun": (
                (node_successor_mode or value_repair_successor_mode)
                and full_body["execution"]["cell_analysis_drafts_reused"]
                == (1 if value_repair_successor_mode else 2)
                and full_body["execution"]["cell_analysis_calls_attempted"] == 0
            ),
            "typed_value_submission_repair_executed": (
                value_repair_successor_mode
                and any(
                    bool(row.get("submission_repair_receipt"))
                    for row in cell_steps
                )
            ),
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
