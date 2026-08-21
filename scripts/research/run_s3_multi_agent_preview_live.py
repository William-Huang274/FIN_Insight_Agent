from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[2]
for candidate in (ROOT, ROOT / "src"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sec_agent.canonical_runtime import (  # noqa: E402
    canonical_digest,
    create_context_checkpoint,
    resume_agent_session,
    validate_runtime_artifact,
)
from sec_agent.providers import (  # noqa: E402
    load_chat_completion_profile,
)
from sec_agent.research.bounded_finance_loop import (  # noqa: E402
    validate_deepseek_ga_node_profile,
    validate_deepseek_ga_profile,
)
from sec_agent.research.case_truth_reconciliation import (  # noqa: E402
    compile_case_truth_model_view,
)
from sec_agent.research.multi_agent_preview import (  # noqa: E402
    RESEARCH_LEAD_AGENT_ID,
    ROLE_EVALUATION_PROGRESS_CHECKPOINT_CHAIN_SCHEMA_VERSION,
    SPECIALIST_AGENT_IDS,
    WRITER_AGENT_ID,
    compile_challenge_catalog,
    compile_cross_role_evaluation_messages,
    compile_evaluation_messages,
    compile_lead_coordination_messages,
    compile_lead_plan_messages,
    compile_report_messages,
    compile_role_evaluation_messages,
    compile_specialist_context,
    compile_specialist_repair_context,
    compile_specialist_workpaper_messages,
    evaluation_allowed_refs,
    evaluation_tool,
    lead_coordination_tool,
    lead_plan_tool,
    load_multi_agent_role_topology,
    local_case_absence_findings,
    merge_analysis_draft_fragments,
    merge_hierarchical_evaluations,
    report_draft_tool,
    revalidate_bound_specialist_workpaper,
    specialist_workpaper_tool,
    validate_analysis_fragment_checkpoint,
    validate_analysis_completion_checkpoint,
    validate_downstream_repair_progress_checkpoint,
    validate_downstream_repair_progress_checkpoint_v2,
    validate_specialist_plan_checkpoint,
    validate_evaluation,
    validate_lead_coordination_decision,
    validate_lead_coordination_checkpoint,
    validate_lead_plan,
    validate_lead_plan_checkpoint,
    validate_report_draft,
    validate_role_evaluation,
    validate_role_evaluation_progress_checkpoint,
    validate_role_evaluation_submission_replay,
    validate_specialist_workpaper,
    validate_specialist_workpaper_checkpoint,
)
from sec_agent.research.multi_agent_preview_runtime import (  # noqa: E402
    MultiAgentPreviewRuntimeError,
    PreviewAgentSessionState,
    compile_cross_role_feedback_receipt,
    compile_multi_agent_preview_materialization,
    execute_analyzed_preview_node,
    execute_checkpointed_preview_submission,
    rebind_preview_session_plan,
    start_preview_agent_session,
)
from sec_agent.research.multi_agent_successor import (  # noqa: E402
    COMPLETED_DISPOSITIONS,
    HIERARCHICAL_EVALUATION_STRATEGY,
    MONOLITHIC_EVALUATION_STRATEGY,
    validate_hierarchical_evaluator_zero_call_proof,
    validate_successor_execution_frontier,
)
from sec_agent.project_os_preflight import (  # noqa: E402
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS,
    MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE,
    validate_multi_agent_preview_analysis_successor_scope_decision,
    validate_multi_agent_preview_submission_successor_scope_decision,
    validate_multi_agent_preview_lead_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_specialist_analysis_successor_scope_decision,
    validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision,
    validate_multi_agent_preview_downstream_analysis_successor_scope_decision,
    validate_multi_agent_preview_repair_context_successor_scope_decision,
    validate_multi_agent_preview_generic_successor_scope_decision,
    validate_multi_agent_preview_plan_successor_scope_decision,
)


PLAN_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_3"
)
ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_4"
)
SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_5"
)
LEAD_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_6"
)
WORKPAPER_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_7"
)
SPECIALIST_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_8"
)
COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_9"
)
DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_10"
)
DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_11"
)
DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_12"
)
DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_13"
)
DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_14"
)
GENERIC_SUCCESSOR_AUTHORITY_SCHEMA = (
    "fin_ia_s3_multi_agent_compiled_successor_authority_v1_0"
)
FULL_SCHEMA_V1 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_1"
FULL_SCHEMA_V2 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_2"
PUBLIC_SCHEMA_V1 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_1"
PUBLIC_SCHEMA_V2 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_2"
FULL_SCHEMA_V3 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_3"
PUBLIC_SCHEMA_V3 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_3"
FULL_SCHEMA_V4 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_4"
PUBLIC_SCHEMA_V4 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_4"
FULL_SCHEMA_V5 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_5"
PUBLIC_SCHEMA_V5 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_5"
FULL_SCHEMA_V6 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_6"
PUBLIC_SCHEMA_V6 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_6"
FULL_SCHEMA_V7 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_7"
PUBLIC_SCHEMA_V7 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_7"
FULL_SCHEMA_V8 = "fin_ia_s3_dell_multi_agent_preview_live_full_result_v1_8"
PUBLIC_SCHEMA_V8 = "fin_ia_s3_dell_multi_agent_preview_live_result_v1_8"
ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING = 8000
CROSS_ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING = 10000


class MultiAgentPreviewLiveError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(ref: str) -> Path:
    path = (ROOT / ref).resolve()
    path.relative_to(ROOT)
    return path


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _write_new(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
    except FileExistsError as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_output_identity_consumed"
        ) from exc


def _result_schemas_for_authority(authority_schema: str) -> tuple[str, str]:
    if authority_schema in {
        DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA,
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA,
        GENERIC_SUCCESSOR_AUTHORITY_SCHEMA,
    }:
        return FULL_SCHEMA_V8, PUBLIC_SCHEMA_V8
    if authority_schema == COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V7, PUBLIC_SCHEMA_V7
    if authority_schema == SPECIALIST_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V6, PUBLIC_SCHEMA_V6
    if authority_schema == WORKPAPER_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V5, PUBLIC_SCHEMA_V5
    if authority_schema == LEAD_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V4, PUBLIC_SCHEMA_V4
    if authority_schema == SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V3, PUBLIC_SCHEMA_V3
    if authority_schema == ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA:
        return FULL_SCHEMA_V2, PUBLIC_SCHEMA_V2
    return FULL_SCHEMA_V1, PUBLIC_SCHEMA_V1


def _compile_hierarchical_evaluator_proof_binding(
    *,
    proof_path: Path,
    frontier: Mapping[str, Any],
) -> dict[str, Any]:
    proof = validate_hierarchical_evaluator_zero_call_proof(
        _json(proof_path),
        frontier=frontier,
    )
    return {
        "ref": _relative(proof_path),
        "sha256": _sha(proof_path),
        "result_digest": proof["result_digest"],
        "provider_model_calls": 0,
        "local_retrieval_materialization_replayed": True,
    }


def _compile_generic_successor_bindings(
    *,
    paths: Mapping[str, Path],
    lead_plan_checkpoint: Mapping[str, Any],
    workpaper_checkpoint: Mapping[str, Any],
    coordination_checkpoint: Mapping[str, Any],
    active_progress_checkpoint: Mapping[str, Any],
    completed_repairs: Mapping[str, Any],
    hierarchical_proof_binding: Mapping[str, Any] | None,
    role_evaluation_checkpoint: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    bindings = {
        "predecessor_lead_plan_checkpoint": {
            "ref": _relative(paths["lead_plan_checkpoint"]),
            "sha256": _sha(paths["lead_plan_checkpoint"]),
            "checkpoint_digest": lead_plan_checkpoint["checkpoint_digest"],
            "lead_plan_digest": lead_plan_checkpoint["lead_plan"][
                "lead_plan_digest"
            ],
            "source_run_status_preserved_as_failure": True,
        },
        "predecessor_workpaper_checkpoint": {
            "ref": _relative(paths["workpaper_checkpoint"]),
            "sha256": _sha(paths["workpaper_checkpoint"]),
            "checkpoint_digest": workpaper_checkpoint["checkpoint_digest"],
            "source_run_status_preserved_as_failure": True,
        },
        "predecessor_lead_coordination_checkpoint": {
            "ref": _relative(paths["lead_coordination_checkpoint"]),
            "sha256": _sha(paths["lead_coordination_checkpoint"]),
            "checkpoint_digest": coordination_checkpoint["checkpoint_digest"],
            "reused_workpaper_count": 6,
            "reused_lead_coordination_count": 1,
            "source_run_status_preserved_as_failure": True,
        },
        "compiled_successor_frontier": {
            "ref": _relative(paths["successor_execution_frontier"]),
            "sha256": _sha(paths["successor_execution_frontier"]),
            "result_digest": active_progress_checkpoint["checkpoint_digest"],
            "completed_repair_count": len(completed_repairs),
            "pending_repair_count": len(
                active_progress_checkpoint["pending_challenge_repairs"]
            ),
        },
    }
    if hierarchical_proof_binding is not None:
        bindings["hierarchical_evaluator_zero_call_proof"] = dict(
            hierarchical_proof_binding
        )
    if role_evaluation_checkpoint is not None:
        bindings["role_evaluation_progress_checkpoint"] = {
            "ref": _relative(paths["role_evaluation_progress_checkpoint"]),
            "sha256": _sha(paths["role_evaluation_progress_checkpoint"]),
            "checkpoint_digest": role_evaluation_checkpoint[
                "checkpoint_digest"
            ],
            "reused_role_evaluation_count": role_evaluation_checkpoint[
                "reused_role_evaluation_count"
            ],
            "completed_agent_ids": list(
                role_evaluation_checkpoint["completed_agent_ids"]
            ),
        }
    return bindings


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _validate_authority(
    authority_path: Path,
) -> tuple[dict[str, Any], dict[str, Path], dict[str, Any]]:
    authority = _json(authority_path)
    expected = {
        "schema_version",
        "status",
        "authorized_at",
        "implementation_commit",
        "bound_inputs",
        "execution_limits",
        "outputs",
        "authority_statement",
    }
    schema = str(authority.get("schema_version") or "")
    analysis_successor = schema == ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    submission_successor = schema == SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA
    lead_checkpoint_successor = (
        schema == LEAD_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    workpaper_checkpoint_successor = (
        schema == WORKPAPER_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    specialist_analysis_successor = (
        schema == SPECIALIST_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    )
    coordination_checkpoint_successor = (
        schema == COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    context_replay_replacement = (
        schema == DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA
    )
    continuation_profile_replacement = (
        schema == DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA
    )
    repair_context_replacement = (
        schema == DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA
    )
    generic_successor = schema == GENERIC_SUCCESSOR_AUTHORITY_SCHEMA
    role_scoped_repair_successor = (
        repair_context_replacement or generic_successor
    )
    preprovider_replacement = schema in {
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA,
    }
    downstream_analysis_successor = schema in {
        DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA,
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA,
        GENERIC_SUCCESSOR_AUTHORITY_SCHEMA,
    }
    expected_status_by_schema = {
        PLAN_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R3_plan_checkpoint_analysis_submission_"
            "successor_after_project_os_preflight"
        ),
        ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R4_analysis_checkpoint_feedback_continuation_"
            "successor_after_project_os_preflight"
        ),
        SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R5_completed_analysis_strict_submission_"
            "successor_after_project_os_preflight"
        ),
        LEAD_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R6_validated_lead_plan_downstream_"
            "successor_after_project_os_preflight"
        ),
        WORKPAPER_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R7_five_workpaper_checkpoint_downstream_"
            "successor_after_project_os_preflight"
        ),
        SPECIALIST_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R8_counterevidence_analysis_checkpoint_"
            "downstream_successor_after_project_os_preflight"
        ),
        COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R9_lead_coordination_checkpoint_downstream_"
            "successor_after_project_os_preflight"
        ),
        DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_R10_downstream_repair_analysis_checkpoint_"
            "successor_after_project_os_preflight"
        ),
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA: (
            "approved_for_one_R12_preprovider_replacement_after_"
            "project_os_preflight"
        ),
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA: (
            "approved_for_one_R13_source_context_replay_replacement_after_"
            "project_os_preflight"
        ),
        DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA: (
            "approved_for_one_R14_non_thinking_continuation_profile_"
            "replacement_after_project_os_preflight"
        ),
        DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA: (
            "approved_for_one_R15_role_scoped_repair_context_"
            "replacement_after_project_os_preflight"
        ),
        GENERIC_SUCCESSOR_AUTHORITY_SCHEMA: (
            "approved_for_one_compiled_multi_agent_successor_after_"
            "project_os_preflight"
        ),
    }
    expected_status = expected_status_by_schema.get(schema)
    if not (
        set(authority) == expected
        and schema in expected_status_by_schema
        and authority.get("status") == expected_status
        and authority.get("implementation_commit") == _git_head()
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_authority_identity_invalid"
        )
    inputs: dict[str, Path] = {}
    for name, raw in authority["bound_inputs"].items():
        if set(raw) != {"ref", "sha256"}:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_authority_binding_invalid"
            )
        path = _resolve(str(raw["ref"]))
        if not path.is_file() or _sha(path) != str(raw["sha256"]):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_authority_binding_drift:{name}"
            )
        inputs[name] = path
    base_inputs = {
        "project_os_scope_decision",
        "topology",
        "objective",
        "zero_call_proof",
        "successor_zero_call_proof",
        "planning_overlay",
        "analysis_profile",
        "submission_profile",
        "historical_five_cell_assessment",
        "predecessor_plan_checkpoint",
    }
    if generic_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "workpaper_checkpoint",
            "lead_coordination_checkpoint",
            "successor_execution_frontier",
            "repair_analysis_profile",
        }
    elif downstream_analysis_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "workpaper_checkpoint",
            "lead_coordination_checkpoint",
            "downstream_repair_progress_checkpoint",
            "downstream_analysis_fragment_checkpoint",
            "downstream_analysis_successor_zero_call_proof",
            "analysis_continuation_profile",
        }
        if preprovider_replacement:
            required_inputs |= {
                "failed_preprovider_authority",
                "failed_preprovider_result",
                "preprovider_failure_disposition_zero_call_proof",
            }
        if continuation_profile_replacement:
            required_inputs |= {
                "failed_continuation_authority",
                "failed_continuation_result",
                "continuation_profile_failure_disposition_zero_call_proof",
                "analysis_completion_profile",
            }
        if repair_context_replacement:
            required_inputs |= {
                "failed_repair_authority",
                "failed_repair_result",
                "repair_context_failure_disposition_zero_call_proof",
                "downstream_repair_progress_checkpoint_v2",
                "repair_analysis_profile",
            }
    elif coordination_checkpoint_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "workpaper_checkpoint",
            "lead_coordination_checkpoint",
            "coordination_checkpoint_successor_zero_call_proof",
        }
    elif specialist_analysis_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "workpaper_checkpoint",
            "specialist_analysis_checkpoint",
            "specialist_analysis_successor_zero_call_proof",
            "analysis_continuation_profile",
        }
    elif workpaper_checkpoint_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "workpaper_checkpoint",
            "workpaper_checkpoint_successor_zero_call_proof",
        }
    elif lead_checkpoint_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "lead_plan_checkpoint",
            "lead_checkpoint_successor_zero_call_proof",
        }
    elif submission_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "analysis_completion_checkpoint",
            "submission_successor_zero_call_proof",
        }
    elif analysis_successor:
        required_inputs = base_inputs | {
            "predecessor_scope_decision",
            "predecessor_authority",
            "predecessor_result",
            "analysis_checkpoint",
            "analysis_successor_zero_call_proof",
            "analysis_continuation_profile",
        }
    else:
        required_inputs = base_inputs | {
            "predecessor_authority",
            "predecessor_result",
        }
    if generic_successor:
        allowed_input_sets = {
            frozenset(required_inputs),
            frozenset(
                required_inputs | {"hierarchical_evaluator_zero_call_proof"}
            ),
            frozenset(
                required_inputs
                | {
                    "hierarchical_evaluator_zero_call_proof",
                    "evaluator_analysis_profile",
                }
            ),
            frozenset(
                required_inputs
                | {
                    "hierarchical_evaluator_zero_call_proof",
                    "evaluator_analysis_profile",
                    "role_evaluation_progress_checkpoint",
                }
            ),
        }
        inputs_valid = frozenset(inputs) in allowed_input_sets
    else:
        inputs_valid = set(inputs) == required_inputs
    if not inputs_valid:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_authority_inputs_invalid"
        )
    scope_decision = _json(inputs["project_os_scope_decision"])
    if generic_successor:
        scope_projection = (
            validate_multi_agent_preview_generic_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        cursor = predecessor_scope_decision
        visited: set[str] = set()
        while (
            cursor.get("schema_version")
            != MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
        ):
            ref = str(cursor.get("predecessor_scope_decision_ref") or "")
            if not ref or ref in visited:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_scope_lineage_invalid"
                )
            visited.add(ref)
            cursor = _json(_resolve(ref))
        base_scope_decision = cursor
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_GENERIC_SUCCESSOR_SCOPE
            and scope_projection.get("multi_agent_preview_generic_successor")
            is True
        )
    elif repair_context_replacement:
        scope_projection = (
            validate_multi_agent_preview_repair_context_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        cursor = predecessor_scope_decision
        visited: set[str] = set()
        while (
            cursor.get("schema_version")
            != MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
        ):
            ref = str(cursor.get("predecessor_scope_decision_ref") or "")
            if not ref or ref in visited:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_scope_lineage_invalid"
                )
            visited.add(ref)
            cursor = _json(_resolve(ref))
        base_scope_decision = cursor
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_repair_context_successor"
            )
            is True
        )
    elif downstream_analysis_successor:
        scope_projection = (
            validate_multi_agent_preview_downstream_analysis_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        cursor = predecessor_scope_decision
        visited: set[str] = set()
        while (
            cursor.get("schema_version")
            != MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
        ):
            ref = str(cursor.get("predecessor_scope_decision_ref") or "")
            if not ref or ref in visited:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_scope_lineage_invalid"
                )
            visited.add(ref)
            cursor = _json(_resolve(ref))
        base_scope_decision = cursor
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_downstream_analysis_checkpoint_successor"
            )
            is True
        )
    elif coordination_checkpoint_successor:
        scope_projection = (
            validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        cursor = predecessor_scope_decision
        visited: set[str] = set()
        while (
            cursor.get("schema_version")
            != MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
        ):
            ref = str(cursor.get("predecessor_scope_decision_ref") or "")
            if not ref or ref in visited:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_scope_lineage_invalid"
                )
            visited.add(ref)
            cursor = _json(_resolve(ref))
        base_scope_decision = cursor
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_coordination_checkpoint_successor"
            )
            is True
        )
    elif specialist_analysis_successor:
        scope_projection = (
            validate_multi_agent_preview_specialist_analysis_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        lead_scope_decision = _json(
            _resolve(
                str(
                    predecessor_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        submission_scope_decision = _json(
            _resolve(str(lead_scope_decision["predecessor_scope_decision_ref"]))
        )
        analysis_scope_decision = _json(
            _resolve(
                str(
                    submission_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        base_scope_decision = _json(
            _resolve(
                str(analysis_scope_decision["predecessor_scope_decision_ref"])
            )
        )
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_specialist_analysis_checkpoint_successor"
            )
            is True
        )
    elif workpaper_checkpoint_successor:
        scope_projection = (
            validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        submission_scope_decision = _json(
            _resolve(
                str(
                    predecessor_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        analysis_scope_decision = _json(
            _resolve(
                str(
                    submission_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        base_scope_decision = _json(
            _resolve(
                str(analysis_scope_decision["predecessor_scope_decision_ref"])
            )
        )
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_workpaper_checkpoint_downstream_successor"
            )
            is True
        )
    elif lead_checkpoint_successor:
        scope_projection = (
            validate_multi_agent_preview_lead_checkpoint_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        analysis_scope_decision = _json(
            _resolve(
                str(
                    predecessor_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        base_scope_decision = _json(
            _resolve(str(analysis_scope_decision["predecessor_scope_decision_ref"]))
        )
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_lead_checkpoint_downstream_successor"
            )
            is True
        )
    elif submission_successor:
        scope_projection = (
            validate_multi_agent_preview_submission_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        predecessor_scope_decision = _json(
            inputs["predecessor_scope_decision"]
        )
        base_scope_decision = _json(
            _resolve(
                str(
                    predecessor_scope_decision[
                        "predecessor_scope_decision_ref"
                    ]
                )
            )
        )
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_submission_checkpoint_successor"
            )
            is True
        )
    elif analysis_successor:
        scope_projection = (
            validate_multi_agent_preview_analysis_successor_scope_decision(
                root=ROOT, decision=scope_decision
            )
        )
        base_scope_decision = _json(inputs["predecessor_scope_decision"])
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_analysis_checkpoint_successor"
            )
            is True
        )
    else:
        scope_projection = validate_multi_agent_preview_plan_successor_scope_decision(
            root=ROOT, decision=scope_decision
        )
        base_scope_decision = scope_decision
        scope_valid = (
            scope_decision.get("schema_version")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
            and scope_decision.get("status")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS
            and scope_decision.get("run_scope_id")
            == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE
            and scope_projection.get(
                "multi_agent_preview_plan_checkpoint_successor"
            )
            is True
        )
    if not scope_valid:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_project_os_scope_invalid"
        )
    base_scope_bindings = {
        "topology": ("topology_ref", "topology_sha256"),
        "objective": ("objective_ref", "objective_sha256"),
        "zero_call_proof": ("zero_call_proof_ref", "zero_call_proof_sha256"),
        "successor_zero_call_proof": (
            "successor_zero_call_proof_ref",
            "successor_zero_call_proof_sha256",
        ),
        "planning_overlay": (
            "planning_overlay_ref",
            "planning_overlay_sha256",
        ),
        "analysis_profile": (
            "analysis_profile_ref",
            "analysis_profile_sha256",
        ),
        "submission_profile": (
            "submission_profile_ref",
            "submission_profile_sha256",
        ),
        "historical_five_cell_assessment": (
            "historical_five_cell_assessment_ref",
            "historical_five_cell_assessment_sha256",
        ),
        "predecessor_plan_checkpoint": (
            "predecessor_plan_checkpoint_ref",
            "predecessor_plan_checkpoint_sha256",
        ),
    }
    for input_name, (ref_field, sha_field) in base_scope_bindings.items():
        if not (
            _relative(inputs[input_name]) == base_scope_decision.get(ref_field)
            and _sha(inputs[input_name]) == base_scope_decision.get(sha_field)
        ):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_project_os_binding_drift:{input_name}"
            )
    if generic_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "workpaper_checkpoint": (
                "workpaper_checkpoint_ref",
                "workpaper_checkpoint_sha256",
            ),
            "lead_coordination_checkpoint": (
                "lead_coordination_checkpoint_ref",
                "lead_coordination_checkpoint_sha256",
            ),
            "successor_execution_frontier": (
                "successor_execution_frontier_ref",
                "successor_execution_frontier_sha256",
            ),
            "repair_analysis_profile": (
                "repair_analysis_profile_ref",
                "repair_analysis_profile_sha256",
            ),
        }
        scope_requires_hierarchical_proof = (
            scope_projection.get(
                "hierarchical_evaluator_zero_call_proof_status"
            )
            is not None
        )
        if (
            "hierarchical_evaluator_zero_call_proof" in inputs
        ) != scope_requires_hierarchical_proof:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_hierarchical_evaluator_proof_"
                "authority_shape_invalid"
            )
        if scope_requires_hierarchical_proof:
            current_scope_bindings["hierarchical_evaluator_zero_call_proof"] = (
                "hierarchical_evaluator_zero_call_proof_ref",
                "hierarchical_evaluator_zero_call_proof_sha256",
            )
        scope_requires_evaluator_profile = (
            scope_projection.get("evaluator_analysis_profile_ref") is not None
        )
        if (
            "evaluator_analysis_profile" in inputs
        ) != scope_requires_evaluator_profile:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_evaluator_profile_authority_shape_invalid"
            )
        if scope_requires_evaluator_profile:
            current_scope_bindings["evaluator_analysis_profile"] = (
                "evaluator_analysis_profile_ref",
                "evaluator_analysis_profile_sha256",
            )
        scope_requires_role_evaluation_checkpoint = (
            scope_projection.get("role_evaluation_progress_checkpoint_ref")
            is not None
        )
        if (
            "role_evaluation_progress_checkpoint" in inputs
        ) != scope_requires_role_evaluation_checkpoint:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_role_evaluation_checkpoint_"
                "authority_shape_invalid"
            )
        if scope_requires_role_evaluation_checkpoint:
            current_scope_bindings["role_evaluation_progress_checkpoint"] = (
                "role_evaluation_progress_checkpoint_ref",
                "role_evaluation_progress_checkpoint_sha256",
            )
    elif downstream_analysis_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "workpaper_checkpoint": (
                "workpaper_checkpoint_ref",
                "workpaper_checkpoint_sha256",
            ),
            "lead_coordination_checkpoint": (
                "lead_coordination_checkpoint_ref",
                "lead_coordination_checkpoint_sha256",
            ),
            "downstream_repair_progress_checkpoint": (
                "downstream_repair_progress_checkpoint_ref",
                "downstream_repair_progress_checkpoint_sha256",
            ),
            "downstream_analysis_fragment_checkpoint": (
                "downstream_analysis_fragment_checkpoint_ref",
                "downstream_analysis_fragment_checkpoint_sha256",
            ),
            "downstream_analysis_successor_zero_call_proof": (
                "downstream_analysis_successor_zero_call_proof_ref",
                "downstream_analysis_successor_zero_call_proof_sha256",
            ),
            "analysis_continuation_profile": (
                "analysis_continuation_profile_ref",
                "analysis_continuation_profile_sha256",
            ),
        }
    elif coordination_checkpoint_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "workpaper_checkpoint": (
                "workpaper_checkpoint_ref",
                "workpaper_checkpoint_sha256",
            ),
            "lead_coordination_checkpoint": (
                "lead_coordination_checkpoint_ref",
                "lead_coordination_checkpoint_sha256",
            ),
            "coordination_checkpoint_successor_zero_call_proof": (
                "coordination_checkpoint_successor_zero_call_proof_ref",
                "coordination_checkpoint_successor_zero_call_proof_sha256",
            ),
        }
    elif specialist_analysis_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "workpaper_checkpoint": (
                "workpaper_checkpoint_ref",
                "workpaper_checkpoint_sha256",
            ),
            "specialist_analysis_checkpoint": (
                "specialist_analysis_checkpoint_ref",
                "specialist_analysis_checkpoint_sha256",
            ),
            "specialist_analysis_successor_zero_call_proof": (
                "specialist_analysis_successor_zero_call_proof_ref",
                "specialist_analysis_successor_zero_call_proof_sha256",
            ),
            "analysis_continuation_profile": (
                "analysis_continuation_profile_ref",
                "analysis_continuation_profile_sha256",
            ),
        }
    elif workpaper_checkpoint_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "workpaper_checkpoint": (
                "workpaper_checkpoint_ref",
                "workpaper_checkpoint_sha256",
            ),
            "workpaper_checkpoint_successor_zero_call_proof": (
                "workpaper_checkpoint_successor_zero_call_proof_ref",
                "workpaper_checkpoint_successor_zero_call_proof_sha256",
            ),
        }
    elif lead_checkpoint_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "lead_plan_checkpoint": (
                "lead_plan_checkpoint_ref",
                "lead_plan_checkpoint_sha256",
            ),
            "lead_checkpoint_successor_zero_call_proof": (
                "lead_checkpoint_successor_zero_call_proof_ref",
                "lead_checkpoint_successor_zero_call_proof_sha256",
            ),
        }
    elif submission_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "analysis_completion_checkpoint": (
                "analysis_completion_checkpoint_ref",
                "analysis_completion_checkpoint_sha256",
            ),
            "submission_successor_zero_call_proof": (
                "submission_successor_zero_call_proof_ref",
                "submission_successor_zero_call_proof_sha256",
            ),
        }
    elif analysis_successor:
        current_scope_bindings = {
            "predecessor_scope_decision": (
                "predecessor_scope_decision_ref",
                "predecessor_scope_decision_sha256",
            ),
            "predecessor_authority": (
                "predecessor_live_authority_ref",
                "predecessor_live_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_live_result_ref",
                "predecessor_live_result_sha256",
            ),
            "analysis_checkpoint": (
                "analysis_checkpoint_ref",
                "analysis_checkpoint_sha256",
            ),
            "analysis_successor_zero_call_proof": (
                "analysis_successor_zero_call_proof_ref",
                "analysis_successor_zero_call_proof_sha256",
            ),
            "analysis_continuation_profile": (
                "analysis_continuation_profile_ref",
                "analysis_continuation_profile_sha256",
            ),
        }
    else:
        current_scope_bindings = {
            "predecessor_authority": (
                "predecessor_authority_ref",
                "predecessor_authority_sha256",
            ),
            "predecessor_result": (
                "predecessor_result_ref",
                "predecessor_result_sha256",
            ),
        }
    for input_name, (ref_field, sha_field) in current_scope_bindings.items():
        if not (
            _relative(inputs[input_name]) == scope_decision.get(ref_field)
            and _sha(inputs[input_name]) == scope_decision.get(sha_field)
        ):
            raise MultiAgentPreviewLiveError(
                f"multi_agent_preview_project_os_binding_drift:{input_name}"
            )
    if generic_successor:
        frontier = validate_successor_execution_frontier(
            _json(inputs["successor_execution_frontier"])
        )
        if frontier.get("evaluation_strategy") == HIERARCHICAL_EVALUATION_STRATEGY:
            hierarchical_proof = validate_hierarchical_evaluator_zero_call_proof(
                _json(inputs["hierarchical_evaluator_zero_call_proof"]),
                frontier=frontier,
            )
            if not (
                hierarchical_proof["status"]
                == scope_projection.get(
                    "hierarchical_evaluator_zero_call_proof_status"
                )
                and hierarchical_proof["result_digest"]
                == scope_projection.get(
                    "hierarchical_evaluator_zero_call_proof_result_digest"
                )
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_hierarchical_evaluator_proof_invalid"
                )
        failed_authority = _json(inputs["predecessor_authority"])
        failed_result = _json(inputs["predecessor_result"])
        predecessor_failure = frontier["predecessor_failure"]
        terminal_path = _resolve(
            str(predecessor_failure["terminal_result_ref"])
        )
        terminal = _json(terminal_path)
        failed_execution = failed_result.get("execution") or {}
        terminal_execution = terminal.get("execution") or {}
        failed_authority_scope = (
            failed_authority.get("bound_inputs", {}).get(
                "project_os_scope_decision"
            )
            or {}
        )
        repair_profile = _json(inputs["repair_analysis_profile"])
        evaluator_profile = (
            _json(inputs["evaluator_analysis_profile"])
            if "evaluator_analysis_profile" in inputs
            else None
        )
        role_evaluation_checkpoint = (
            _json(inputs["role_evaluation_progress_checkpoint"])
            if "role_evaluation_progress_checkpoint" in inputs
            else None
        )
        evaluator_defaults = (
            evaluator_profile.get("request_defaults")
            if evaluator_profile is not None
            else None
        )
        if not (
            authority["execution_limits"] == frontier["execution_limits"]
            and predecessor_failure["authority_ref"]
            == _relative(inputs["predecessor_authority"])
            and predecessor_failure["authority_sha256"]
            == _sha(inputs["predecessor_authority"])
            and predecessor_failure["public_result_ref"]
            == _relative(inputs["predecessor_result"])
            and predecessor_failure["public_result_sha256"]
            == _sha(inputs["predecessor_result"])
            and predecessor_failure["public_result_digest"]
            == failed_result.get("result_digest")
            and predecessor_failure["terminal_result_sha256"]
            == _sha(terminal_path)
            and predecessor_failure["terminal_result_digest"]
            == terminal.get("full_result_digest")
            and predecessor_failure["failure_code"]
            == failed_result.get("failure_code")
            == terminal.get("failure_code")
            and bool(str(predecessor_failure["failure_code"]).strip())
            and predecessor_failure["provider_attempt_count"]
            == failed_execution.get("provider_attempts_preserved")
            == terminal_execution.get("provider_attempts_preserved")
            and failed_result.get("status")
            == terminal.get("status")
            == "multi_agent_preview_terminal_failure_preserved"
            and failed_execution.get("external_source_network_calls") == 0
            and failed_execution.get("candidate_promotions") == 0
            and failed_authority.get("outputs", {}).get("public_result_ref")
            == _relative(inputs["predecessor_result"])
            and failed_result.get("authority_ref")
            == _relative(inputs["predecessor_authority"])
            and failed_authority.get("schema_version")
            in {
                DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA,
                GENERIC_SUCCESSOR_AUTHORITY_SCHEMA,
            }
            and failed_authority_scope
            == {
                "ref": _relative(inputs["predecessor_scope_decision"]),
                "sha256": _sha(inputs["predecessor_scope_decision"]),
            }
            and repair_profile.get("provider_id") == "deepseek"
            and repair_profile.get("model") == "deepseek-v4-pro"
            and repair_profile.get("request_defaults")
            == {
                "max_tokens": 12000,
                "stream": False,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
            and (repair_profile.get("authority") or {}).get("retry_count")
            == 0
            and (
                evaluator_profile is None
                or (
                    evaluator_profile.get("provider_id") == "deepseek"
                    and evaluator_profile.get("model") == "deepseek-v4-pro"
                    and evaluator_profile.get("base_url")
                    == "https://api.deepseek.com"
                    and evaluator_profile.get("endpoint")
                    == "/chat/completions"
                    and (
                        (
                            role_evaluation_checkpoint is None
                            and evaluator_defaults
                            == {
                                "max_tokens": 10000,
                                "stream": False,
                                "thinking": {"type": "enabled"},
                                "reasoning_effort": "low",
                            }
                        )
                        or (
                            role_evaluation_checkpoint is not None
                            and evaluator_defaults
                            == {
                                "max_tokens": 10000,
                                "stream": False,
                                "thinking": {"type": "disabled"},
                            }
                        )
                    )
                    and (evaluator_profile.get("authority") or {}).get(
                        "retry_count"
                    )
                    == 0
                )
            )
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_successor_binding_invalid"
            )
        if role_evaluation_checkpoint is not None:
            if not (
                role_evaluation_checkpoint.get("checkpoint_digest")
                == frontier.get("evaluation_progress_checkpoint_digest")
                and role_evaluation_checkpoint.get("completed_agent_ids")
                == frontier.get("completed_role_evaluation_agent_ids")
                and role_evaluation_checkpoint.get("source_authority_ref")
                == _relative(inputs["predecessor_authority"])
                and role_evaluation_checkpoint.get("source_authority_sha256")
                == _sha(inputs["predecessor_authority"])
                and role_evaluation_checkpoint.get("source_public_result_ref")
                == _relative(inputs["predecessor_result"])
                and role_evaluation_checkpoint.get(
                    "source_public_result_sha256"
                )
                == _sha(inputs["predecessor_result"])
                and role_evaluation_checkpoint.get(
                    "source_public_result_digest"
                )
                == failed_result.get("result_digest")
                and role_evaluation_checkpoint.get(
                    "source_terminal_result_ref"
                )
                == predecessor_failure["terminal_result_ref"]
                and role_evaluation_checkpoint.get(
                    "source_terminal_result_sha256"
                )
                == predecessor_failure["terminal_result_sha256"]
                and role_evaluation_checkpoint.get(
                    "source_terminal_result_digest"
                )
                == predecessor_failure["terminal_result_digest"]
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_role_evaluation_checkpoint_binding_invalid"
                )
    if preprovider_replacement:
        failed_authority = _json(inputs["failed_preprovider_authority"])
        failed_result = _json(inputs["failed_preprovider_result"])
        disposition = _json(
            inputs["preprovider_failure_disposition_zero_call_proof"]
        )
        failed_execution = failed_result.get("execution") or {}
        failed_public_body = {
            key: value
            for key, value in failed_result.items()
            if key != "result_digest"
        }
        failed_terminal_path = _resolve(
            str(disposition.get("failed_terminal_result_ref") or "")
        )
        failed_terminal = _json(failed_terminal_path)
        failed_terminal_body = {
            key: value
            for key, value in failed_terminal.items()
            if key != "full_result_digest"
        }
        disposition_body = {
            key: value
            for key, value in disposition.items()
            if key != "result_digest"
        }
        replay = disposition.get("exact_completed_repair_replay") or {}
        source_replay = disposition.get("exact_source_context_replay") or {}
        mutations = disposition.get("mutation_results") or {}
        constraints = disposition.get("replacement_constraints") or {}
        source_request_ref = str(source_replay.get("request_capture_ref") or "")
        source_request_path = (
            _resolve(source_request_ref) if source_request_ref else ROOT
        )
        source_request = (
            _json(source_request_path) if source_request_path.is_file() else {}
        )
        source_request_body = source_request.get("request_body") or {}
        common_failure_binding_valid = (
            failed_authority.get("outputs", {}).get("public_result_ref")
            == _relative(inputs["failed_preprovider_result"])
            and failed_result.get("authority_ref")
            == _relative(inputs["failed_preprovider_authority"])
            and failed_result.get("status")
            == "multi_agent_preview_terminal_failure_preserved"
            and failed_result.get("result_digest")
            == canonical_digest(failed_public_body)
            and failed_execution.get("new_model_nodes_started") == 0
            and failed_execution.get("provider_attempts_preserved") == 0
            and failed_execution.get("analysis_calls_preserved") == 0
            and failed_execution.get("submission_attempts_preserved") == 0
            and disposition.get("failed_authority_ref")
            == _relative(inputs["failed_preprovider_authority"])
            and disposition.get("failed_authority_sha256")
            == _sha(inputs["failed_preprovider_authority"])
            and disposition.get("failed_public_result_ref")
            == _relative(inputs["failed_preprovider_result"])
            and disposition.get("failed_public_result_sha256")
            == _sha(inputs["failed_preprovider_result"])
            and disposition.get("failed_public_result_digest")
            == failed_result.get("result_digest")
            and disposition.get("failed_terminal_result_sha256")
            == _sha(failed_terminal_path)
            and disposition.get("failed_terminal_result_digest")
            == failed_terminal.get("full_result_digest")
            == canonical_digest(failed_terminal_body)
            and disposition.get("failure_stage")
            == "checkpoint_replay_before_provider"
            and disposition.get("model_calls") == 0
            and disposition.get("network_calls") == 0
            and disposition.get("candidate_promotions") == 0
            and disposition.get("result_digest")
            == canonical_digest(disposition_body)
        )
        legacy_replacement_valid = (
            not context_replay_replacement
            and common_failure_binding_valid
            and failed_authority.get("schema_version")
            == DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
            and failed_authority.get("outputs", {}).get("run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R11_20260820"
            and failed_result.get("failure_code")
            == "multi_agent_workpaper_identity_invalid"
            and disposition.get("schema_version")
            == (
                "fin_ia_s3_multi_agent_preview_preprovider_failure_"
                "disposition_zero_call_v1_0"
            )
            and disposition.get("status")
            == "R11_preprovider_derived_workpaper_projection_replay_pass"
            and disposition.get("failure_code")
            == "multi_agent_workpaper_identity_invalid"
            and replay.get("agent_id") == "AGENT::DEMAND_QUALITY"
            and replay.get("workpaper_digest")
            == "3914ddf8e0fde4ba7b82933795ada3feee70701f609fce901af684dcbeaf47e0"
            and replay.get("passed") is True
            and mutations.get("workpaper_digest_mutation_rejected") is True
            and mutations.get("context_digest_mutation_rejected") is True
            and constraints
            == {
                "new_attempt_id_required": True,
                "failed_authority_reuse_forbidden": True,
                "research_inputs_unchanged": True,
                "provider_budget_unchanged": True,
                "completed_node_reruns_forbidden": True,
            }
        )
        context_replay_valid = (
            context_replay_replacement
            and common_failure_binding_valid
            and failed_authority.get("schema_version")
            == DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA
            and failed_authority.get("outputs", {}).get("run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R12_20260820"
            and failed_result.get("failure_code")
            == "multi_agent_bound_workpaper_digest_invalid"
            and disposition.get("schema_version")
            == (
                "fin_ia_s3_multi_agent_preview_source_context_replay_"
                "failure_disposition_zero_call_v1_0"
            )
            and disposition.get("status")
            == "R12_preprovider_source_context_replay_pass"
            and disposition.get("failure_code")
            == "multi_agent_bound_workpaper_digest_invalid"
            and source_replay.get("source_run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R10_20260820"
            and source_replay.get("agent_id") == "AGENT::DEMAND_QUALITY"
            and source_replay.get("workpaper_digest")
            == "3914ddf8e0fde4ba7b82933795ada3feee70701f609fce901af684dcbeaf47e0"
            and source_replay.get("context_digest")
            == "1ddcce797a2fac8566024a3c2dd1ea1eb31c837637a3352bb7dac6d37f1f0e6b"
            and source_replay.get("request_digest")
            == "73cf2a22df258f2e554ac7acb2b3c71e2d87f9c2e36eaf0947916a4d923e20fa"
            and source_request_ref
            and source_request_path.is_file()
            and source_replay.get("request_capture_sha256")
            == _sha(source_request_path)
            and source_request.get("request_digest")
            == source_replay.get("request_digest")
            == canonical_digest(source_request_body)
            and source_replay.get("passed") is True
            and mutations.get("request_digest_mutation_rejected") is True
            and mutations.get("workpaper_digest_mutation_rejected") is True
            and mutations.get("context_digest_mutation_rejected") is True
            and mutations.get("fresh_feedback_context_rejected") is True
            and constraints
            == {
                "new_attempt_id_required": True,
                "failed_authority_reuse_forbidden": True,
                "research_inputs_unchanged": True,
                "provider_budget_unchanged": True,
                "completed_node_reruns_forbidden": True,
                "fresh_feedback_for_completed_node_forbidden": True,
            }
        )
        if not (legacy_replacement_valid or context_replay_valid):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_preprovider_replacement_invalid"
            )
    if continuation_profile_replacement:
        failed_authority = _json(inputs["failed_continuation_authority"])
        failed_result = _json(inputs["failed_continuation_result"])
        disposition = _json(
            inputs["continuation_profile_failure_disposition_zero_call_proof"]
        )
        failed_public_body = {
            key: value
            for key, value in failed_result.items()
            if key != "result_digest"
        }
        failed_terminal_path = _resolve(
            str(disposition.get("failed_terminal_result_ref") or "")
        )
        failed_terminal = _json(failed_terminal_path)
        failed_terminal_body = {
            key: value
            for key, value in failed_terminal.items()
            if key != "full_result_digest"
        }
        disposition_body = {
            key: value
            for key, value in disposition.items()
            if key != "result_digest"
        }
        terminal_attempts = failed_terminal.get("terminal_node_attempts") or []
        terminal_attempt = terminal_attempts[0] if len(terminal_attempts) == 1 else {}
        usage = terminal_attempt.get("usage") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        completion_profile = _json(inputs["analysis_completion_profile"])
        request_ref = str(disposition.get("request_capture_ref") or "")
        response_ref = str(disposition.get("response_capture_ref") or "")
        request_path = _resolve(request_ref) if request_ref else ROOT
        response_path = _resolve(response_ref) if response_ref else ROOT
        request_capture = _json(request_path) if request_path.is_file() else {}
        response_capture = _json(response_path) if response_path.is_file() else {}
        constraints = disposition.get("replacement_constraints") or {}
        if not (
            failed_authority.get("schema_version")
            == DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA
            and failed_authority.get("outputs", {}).get("run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R13_20260820"
            and failed_authority.get("outputs", {}).get("public_result_ref")
            == _relative(inputs["failed_continuation_result"])
            and failed_result.get("authority_ref")
            == _relative(inputs["failed_continuation_authority"])
            and failed_result.get("status")
            == "multi_agent_preview_terminal_failure_preserved"
            and failed_result.get("failure_code")
            == "multi_agent_preview_analysis_continuation_finish_reason_invalid:length"
            and failed_result.get("result_digest")
            == canonical_digest(failed_public_body)
            and (failed_result.get("execution") or {}).get(
                "new_model_nodes_started"
            )
            == 1
            and (failed_result.get("execution") or {}).get(
                "analysis_continuation_calls_preserved"
            )
            == 1
            and (failed_result.get("execution") or {}).get(
                "provider_attempts_preserved"
            )
            == 1
            and (failed_result.get("execution") or {}).get(
                "submission_attempts_preserved"
            )
            == 0
            and disposition.get("schema_version")
            == (
                "fin_ia_s3_multi_agent_preview_continuation_profile_"
                "failure_disposition_zero_call_v1_0"
            )
            and disposition.get("status")
            == "R13_thinking_budget_starvation_replay_pass"
            and disposition.get("failed_authority_ref")
            == _relative(inputs["failed_continuation_authority"])
            and disposition.get("failed_authority_sha256")
            == _sha(inputs["failed_continuation_authority"])
            and disposition.get("failed_public_result_ref")
            == _relative(inputs["failed_continuation_result"])
            and disposition.get("failed_public_result_sha256")
            == _sha(inputs["failed_continuation_result"])
            and disposition.get("failed_public_result_digest")
            == failed_result.get("result_digest")
            and disposition.get("failed_terminal_result_sha256")
            == _sha(failed_terminal_path)
            and disposition.get("failed_terminal_result_digest")
            == failed_terminal.get("full_result_digest")
            == canonical_digest(failed_terminal_body)
            and disposition.get("failure_stage")
            == "cash_repair_analysis_continuation_provider_completion"
            and disposition.get("failure_code")
            == failed_result.get("failure_code")
            and disposition.get("model_calls") == 1
            and disposition.get("network_calls") == 0
            and disposition.get("candidate_promotions") == 0
            and terminal_attempt.get("phase") == "analysis_continuation"
            and terminal_attempt.get("finish_reason") == "length"
            and usage.get("completion_tokens") == 4000
            and completion_details.get("reasoning_tokens") == 3705
            and usage.get("prompt_tokens") == 30656
            and disposition.get("reasoning_budget_observation")
            == {
                "completion_tokens": 4000,
                "reasoning_tokens": 3705,
                "visible_output_character_count": 1249,
                "provider_low_effort_was_not_low_thinking": True,
            }
            and disposition.get("failed_profile_ref")
            == _relative(inputs["analysis_continuation_profile"])
            and disposition.get("failed_profile_sha256")
            == _sha(inputs["analysis_continuation_profile"])
            and disposition.get("replacement_profile_ref")
            == _relative(inputs["analysis_completion_profile"])
            and disposition.get("replacement_profile_sha256")
            == _sha(inputs["analysis_completion_profile"])
            and request_path.is_file()
            and response_path.is_file()
            and disposition.get("request_capture_sha256") == _sha(request_path)
            and disposition.get("response_capture_sha256") == _sha(response_path)
            and disposition.get("request_digest")
            == request_capture.get("request_digest")
            == terminal_attempt.get("request_digest")
            and disposition.get("response_digest")
            == response_capture.get("response_digest")
            == terminal_attempt.get("response_digest")
            and Path(str(terminal_attempt.get("request_capture_ref") or "")).resolve()
            == request_path
            and Path(str(terminal_attempt.get("response_capture_ref") or "")).resolve()
            == response_path
            and disposition.get("result_digest")
            == canonical_digest(disposition_body)
            and completion_profile.get("provider_id") == "deepseek"
            and completion_profile.get("model") == "deepseek-v4-pro"
            and completion_profile.get("base_url") == "https://api.deepseek.com"
            and completion_profile.get("endpoint") == "/chat/completions"
            and completion_profile.get("request_defaults")
            == {
                "max_tokens": 2000,
                "stream": False,
                "thinking": {"type": "disabled"},
            }
            and (completion_profile.get("authority") or {}).get("retry_count")
            == 0
            and constraints
            == {
                "R13_terminal_failure_remains_immutable": True,
                "new_attempt_id_required": True,
                "failed_authority_reuse_forbidden": True,
                "research_inputs_unchanged": True,
                "analysis_fragment_unchanged": True,
                "completed_node_reruns_forbidden": True,
                "one_non_thinking_replacement_only": True,
                "further_cash_continuation_replacement_forbidden": True,
            }
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_continuation_profile_replacement_invalid"
            )
    if repair_context_replacement:
        failed_authority = _json(inputs["failed_repair_authority"])
        failed_result = _json(inputs["failed_repair_result"])
        disposition = _json(
            inputs[
                "repair_context_failure_disposition_zero_call_proof"
            ]
        )
        progress_v2 = validate_downstream_repair_progress_checkpoint_v2(
            _json(inputs["downstream_repair_progress_checkpoint_v2"])
        )
        repair_profile = _json(inputs["repair_analysis_profile"])
        failed_public_body = {
            key: value
            for key, value in failed_result.items()
            if key != "result_digest"
        }
        failed_terminal_path = _resolve(
            str(disposition.get("failed_terminal_result_ref") or "")
        )
        failed_terminal = _json(failed_terminal_path)
        failed_terminal_body = {
            key: value
            for key, value in failed_terminal.items()
            if key != "full_result_digest"
        }
        disposition_body = {
            key: value
            for key, value in disposition.items()
            if key != "result_digest"
        }
        request_path = _resolve(
            str(disposition.get("request_capture_ref") or "")
        )
        response_path = _resolve(
            str(disposition.get("response_capture_ref") or "")
        )
        request_capture = _json(request_path)
        response_capture = _json(response_path)
        request_body = request_capture.get("request_body") or {}
        messages = request_body.get("messages") or []
        try:
            analysis_envelope = json.loads(str(messages[1]["content"]))
            source_context_text = str(
                analysis_envelope["task_context"][0]["content"]
            )
            source_context = json.loads(source_context_text)
            repair_context = compile_specialist_repair_context(
                source_context
            )
        except (IndexError, KeyError, TypeError, json.JSONDecodeError):
            repair_context = {}
            source_context = {}
            source_context_text = ""
        compact = lambda value: json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        replay = disposition.get("source_context_replay") or {}
        provider_observation = disposition.get("provider_observation") or {}
        response_body = response_capture.get("response_body") or {}
        choices = response_body.get("choices") or []
        choice = choices[0] if len(choices) == 1 else {}
        response_usage = response_body.get("usage") or {}
        response_completion = (
            response_usage.get("completion_tokens_details") or {}
        )
        completed_rows = progress_v2.get(
            "completed_challenge_repairs"
        ) or []
        pending_rows = progress_v2.get("pending_challenge_repairs") or []
        constraints = disposition.get("replacement_constraints") or {}
        repair_scope_bindings_valid = all(
            _relative(inputs[input_name])
            == scope_decision.get(ref_field)
            and _sha(inputs[input_name]) == scope_decision.get(sha_field)
            for input_name, ref_field, sha_field in (
                (
                    "failed_repair_authority",
                    "failed_repair_authority_ref",
                    "failed_repair_authority_sha256",
                ),
                (
                    "failed_repair_result",
                    "failed_repair_result_ref",
                    "failed_repair_result_sha256",
                ),
                (
                    "repair_context_failure_disposition_zero_call_proof",
                    "repair_context_failure_disposition_ref",
                    "repair_context_failure_disposition_sha256",
                ),
                (
                    "downstream_repair_progress_checkpoint_v2",
                    "downstream_repair_progress_checkpoint_v2_ref",
                    "downstream_repair_progress_checkpoint_v2_sha256",
                ),
                (
                    "repair_analysis_profile",
                    "repair_analysis_profile_ref",
                    "repair_analysis_profile_sha256",
                ),
            )
        )
        if not (
            repair_scope_bindings_valid
            and failed_authority.get("schema_version")
            == DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA
            and failed_authority.get("outputs", {}).get("run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R14_20260820"
            and failed_authority.get("outputs", {}).get("public_result_ref")
            == _relative(inputs["failed_repair_result"])
            and failed_result.get("authority_ref")
            == _relative(inputs["failed_repair_authority"])
            and failed_result.get("status")
            == "multi_agent_preview_terminal_failure_preserved"
            and failed_result.get("failure_code")
            == "model_gateway_reasoning_budget_exhausted"
            and failed_result.get("result_digest")
            == canonical_digest(failed_public_body)
            and (failed_result.get("execution") or {}).get(
                "new_model_nodes_started"
            )
            == 2
            and (failed_result.get("execution") or {}).get(
                "reused_completed_challenge_repair_count"
            )
            == 1
            and (failed_result.get("execution") or {}).get(
                "new_counter_challenge_repairs_preserved"
            )
            == 1
            and disposition.get("schema_version")
            == (
                "fin_ia_s3_multi_agent_preview_role_repair_context_"
                "failure_disposition_zero_call_v1_0"
            )
            and disposition.get("status")
            == "R14_role_repair_context_and_task_profile_root_cause_replay_pass"
            and disposition.get("failed_authority_ref")
            == _relative(inputs["failed_repair_authority"])
            and disposition.get("failed_authority_sha256")
            == _sha(inputs["failed_repair_authority"])
            and disposition.get("failed_public_result_ref")
            == _relative(inputs["failed_repair_result"])
            and disposition.get("failed_public_result_sha256")
            == _sha(inputs["failed_repair_result"])
            and disposition.get("failed_public_result_digest")
            == failed_result.get("result_digest")
            and failed_terminal_path.is_file()
            and disposition.get("failed_terminal_result_sha256")
            == _sha(failed_terminal_path)
            and disposition.get("failed_terminal_result_digest")
            == failed_terminal.get("full_result_digest")
            == canonical_digest(failed_terminal_body)
            and disposition.get("failure_stage")
            == "supply_repair_analysis_provider_completion"
            and disposition.get("failure_code")
            == failed_result.get("failure_code")
            and request_path.is_file()
            and response_path.is_file()
            and disposition.get("request_capture_sha256")
            == _sha(request_path)
            and disposition.get("response_capture_sha256")
            == _sha(response_path)
            and disposition.get("request_digest")
            == request_capture.get("request_digest")
            and disposition.get("response_digest")
            == response_capture.get("response_digest")
            and response_capture.get("status_code") == 200
            and response_capture.get("response_body_complete") is True
            and choice.get("finish_reason") == "length"
            and (choice.get("message") or {}).get("content") == ""
            and response_usage.get("prompt_tokens") == 32271
            and response_usage.get("completion_tokens") == 12000
            and response_completion.get("reasoning_tokens") == 12000
            and provider_observation
            == {
                "status_code": 200,
                "response_body_complete": True,
                "finish_reason": "length",
                "prompt_tokens": 32271,
                "completion_tokens": 12000,
                "reasoning_tokens": 12000,
                "visible_output_character_count": 0,
                "request_max_tokens": 12000,
                "request_reasoning_effort": "max",
            }
            and len(messages) == 2
            and source_context.get("context_digest")
            == replay.get("source_context_digest")
            and len(source_context_text)
            == replay.get("source_context_character_count")
            and len(str(messages[1]["content"]))
            == replay.get("source_user_message_character_count")
            and sum(len(str(row.get("content") or "")) for row in messages)
            == replay.get("source_total_message_character_count")
            and repair_context.get("context_digest")
            == replay.get("repair_context_digest")
            and len(compact(repair_context))
            == replay.get("repair_context_character_count")
            and len(
                compact(repair_context.get("case_fact_presence") or {})
            )
            == replay.get("repair_case_truth_character_count")
            and len(compact(repair_context.get("lead_plan") or {}))
            == replay.get("repair_lead_plan_character_count")
            and len(
                (repair_context.get("cell_analysis_view") or {})
                .get("cell", {})
                .get("cell_evidence_views", [])
            )
            == replay.get("role_evidence_count_preserved")
            == 10
            and len(
                (repair_context.get("cell_analysis_view") or {})
                .get("cell", {})
                .get("residual_gap_cards", [])
            )
            == replay.get("role_typed_gap_count_preserved")
            == 4
            and disposition.get("result_digest")
            == canonical_digest(disposition_body)
            and progress_v2.get("source_run_id")
            == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R14_20260820"
            and progress_v2.get("source_public_result_digest")
            == failed_result.get("result_digest")
            and progress_v2.get("source_terminal_result_digest")
            == failed_terminal.get("full_result_digest")
            and progress_v2.get("repair_context_policy_digest")
            == disposition.get("result_digest")
            and len(completed_rows) == 2
            and [row.get("target_agent_id") for row in completed_rows]
            == ["AGENT::DEMAND_QUALITY", "AGENT::CASH_CONVERSION"]
            and pending_rows
            == [
                {
                    "challenge_id": "CHALLENGE::71AAF31E7FBD5A99163BBE8D",
                    "target_agent_id": "AGENT::SUPPLY_RELATIONSHIP",
                    "node_id": "AGENT::SUPPLY_RELATIONSHIP::COUNTER_REPAIR",
                }
            ]
            and repair_profile.get("provider_id") == "deepseek"
            and repair_profile.get("model") == "deepseek-v4-pro"
            and repair_profile.get("base_url") == "https://api.deepseek.com"
            and repair_profile.get("endpoint") == "/chat/completions"
            and repair_profile.get("request_defaults")
            == {
                "max_tokens": 12000,
                "stream": False,
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
            and (repair_profile.get("authority") or {}).get("retry_count")
            == 0
            and constraints
            == {
                "R14_terminal_failure_remains_immutable": True,
                "new_attempt_id_required": True,
                "failed_authority_reuse_forbidden": True,
                "research_inputs_unchanged": True,
                "completed_repair_reruns_forbidden": True,
                "cash_continuation_forbidden": True,
                "role_authorized_evidence_and_gaps_must_be_preserved": True,
                "whole_case_truth_omission_must_be_digest_receipted": True,
                "lead_plan_projection_must_remain_digest_bound": True,
                "candidate_promotion_forbidden": True,
            }
            and disposition.get("model_calls") == 0
            and disposition.get("network_calls") == 0
            and disposition.get("candidate_promotions") == 0
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_repair_context_replacement_invalid"
            )
    zero = _json(inputs["zero_call_proof"])
    if zero.get("status") != "zero_call_topology_and_current_tool_spine_pass":
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_zero_call_proof_not_passed"
        )
    successor_zero = _json(inputs["successor_zero_call_proof"])
    controlled = (
        (successor_zero.get("materialization_readiness") or {}).get(
            "controlled_plan_summary"
        )
        or {}
    )
    if not (
        successor_zero.get("status")
        == "R3_plan_checkpoint_successor_zero_call_pass"
        and successor_zero.get("result_digest")
        == base_scope_decision.get("successor_zero_call_proof_result_digest")
        and controlled.get("proposed_atom_count") == 13
        and controlled.get("selected_atom_count") == 12
        and controlled.get("deferred_atom_count") == 1
        and controlled.get("execution_request_budget") == 12
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_successor_zero_call_proof_not_passed"
        )
    if generic_successor:
        validated_frontier = validate_successor_execution_frontier(
            _json(inputs["successor_execution_frontier"])
        )
        if scope_projection.get("successor_zero_call_proof_status") != (
            validated_frontier["status"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_successor_frontier_not_passed"
            )
        if validated_frontier.get("evaluation_strategy") == (
            HIERARCHICAL_EVALUATION_STRATEGY
        ):
            hierarchical_proof = validate_hierarchical_evaluator_zero_call_proof(
                _json(inputs["hierarchical_evaluator_zero_call_proof"]),
                frontier=validated_frontier,
            )
            if hierarchical_proof["result_digest"] != scope_projection.get(
                "hierarchical_evaluator_zero_call_proof_result_digest"
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_hierarchical_evaluator_proof_not_passed"
                )
    elif downstream_analysis_successor:
        progress_checkpoint = validate_downstream_repair_progress_checkpoint(
            _json(inputs["downstream_repair_progress_checkpoint"])
        )
        downstream_fragment = validate_analysis_fragment_checkpoint(
            _json(inputs["downstream_analysis_fragment_checkpoint"])
        )
        downstream_zero = _json(
            inputs["downstream_analysis_successor_zero_call_proof"]
        )
        if not (
            progress_checkpoint.get("checkpoint_digest")
            == scope_decision.get("downstream_repair_progress_checkpoint_digest")
            and downstream_fragment.get("checkpoint_digest")
            == scope_decision.get(
                "downstream_analysis_fragment_checkpoint_digest"
            )
            and downstream_fragment.get("node_id")
            == "AGENT::CASH_CONVERSION::COUNTER_REPAIR"
            and downstream_zero.get("status")
            == (
                "R10_downstream_repair_analysis_checkpoint_successor_"
                "zero_call_pass"
            )
            and downstream_zero.get("result_digest")
            == scope_decision.get(
                "downstream_analysis_successor_zero_call_proof_result_digest"
            )
            and downstream_zero.get("maximum_new_model_nodes") == 7
            and downstream_zero.get("maximum_analysis_continuation_calls") == 1
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_downstream_analysis_checkpoint_not_passed"
            )
    elif coordination_checkpoint_successor:
        coordination_checkpoint = _json(inputs["lead_coordination_checkpoint"])
        coordination_zero = _json(
            inputs["coordination_checkpoint_successor_zero_call_proof"]
        )
        if not (
            coordination_checkpoint.get("status")
            == "six_workpapers_and_R9_lead_coordination_valid_for_downstream_resume"
            and coordination_checkpoint.get("checkpoint_digest")
            == scope_decision.get("lead_coordination_checkpoint_digest")
            and coordination_checkpoint.get("reused_workpaper_count") == 6
            and coordination_zero.get("status")
            == (
                "R9_six_workpapers_and_lead_coordination_checkpoint_"
                "downstream_successor_zero_call_pass"
            )
            and coordination_zero.get("result_digest")
            == scope_decision.get(
                "coordination_checkpoint_successor_zero_call_proof_result_digest"
            )
            and coordination_zero.get("lead_coordination_checkpoint_digest")
            == coordination_checkpoint.get("checkpoint_digest")
            and coordination_zero.get("maximum_new_model_nodes") == 8
            and coordination_zero.get("reused_lead_coordination_count") == 1
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_coordination_checkpoint_not_passed"
            )
    elif specialist_analysis_successor:
        specialist_analysis_checkpoint = validate_analysis_fragment_checkpoint(
            _json(inputs["specialist_analysis_checkpoint"])
        )
        specialist_analysis_successor_zero = _json(
            inputs["specialist_analysis_successor_zero_call_proof"]
        )
        if not (
            specialist_analysis_checkpoint.get("node_id")
            == "AGENT::COUNTEREVIDENCE::WORKPAPER_R1"
            and specialist_analysis_checkpoint.get("finish_reason") == "length"
            and specialist_analysis_checkpoint.get("checkpoint_digest")
            == scope_decision.get("specialist_analysis_checkpoint_digest")
            and specialist_analysis_checkpoint.get(
                "partial_draft_character_count"
            )
            == 918
            and specialist_analysis_checkpoint.get(
                "completed_required_outputs"
            )
            == []
            and specialist_analysis_checkpoint.get("partial_required_outputs")
            == ["thesis"]
            and specialist_analysis_successor_zero.get("status")
            == (
                "R8_counterevidence_analysis_checkpoint_downstream_"
                "successor_zero_call_pass"
            )
            and specialist_analysis_successor_zero.get("result_digest")
            == scope_decision.get(
                "specialist_analysis_successor_zero_call_proof_result_digest"
            )
            and specialist_analysis_successor_zero.get(
                "analysis_fragment_checkpoint_digest"
            )
            == specialist_analysis_checkpoint.get("checkpoint_digest")
            and specialist_analysis_successor_zero.get(
                "maximum_analysis_continuation_calls"
            )
            == 1
            and specialist_analysis_successor_zero.get(
                "new_initial_counterevidence_analysis_calls"
            )
            == 0
            and specialist_analysis_successor_zero.get(
                "maximum_new_model_nodes"
            )
            == 10
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_specialist_analysis_checkpoint_not_passed"
            )
    elif workpaper_checkpoint_successor:
        workpaper_checkpoint = _json(inputs["workpaper_checkpoint"])
        workpaper_checkpoint_zero = _json(
            inputs["workpaper_checkpoint_successor_zero_call_proof"]
        )
        if not (
            workpaper_checkpoint.get("status")
            == "five_R7_specialist_workpapers_valid_for_downstream_resume"
            and workpaper_checkpoint.get("checkpoint_digest")
            == scope_decision.get("workpaper_checkpoint_digest")
            and workpaper_checkpoint.get("reused_workpaper_count") == 5
            and workpaper_checkpoint.get("pending_agent_ids")
            == [SPECIALIST_AGENT_IDS[5]]
            and workpaper_checkpoint_zero.get("status")
            == "R7_five_workpaper_checkpoint_downstream_successor_zero_call_pass"
            and workpaper_checkpoint_zero.get("result_digest")
            == scope_decision.get(
                "workpaper_checkpoint_successor_zero_call_proof_result_digest"
            )
            and workpaper_checkpoint_zero.get("workpaper_checkpoint_digest")
            == workpaper_checkpoint.get("checkpoint_digest")
            and workpaper_checkpoint_zero.get("maximum_new_model_nodes") == 10
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_workpaper_checkpoint_not_passed"
            )
    elif lead_checkpoint_successor:
        lead_checkpoint_zero = _json(
            inputs["lead_checkpoint_successor_zero_call_proof"]
        )
        if not (
            lead_checkpoint_zero.get("status")
            == (
                "R6_validated_lead_plan_checkpoint_downstream_successor_"
                "zero_call_pass"
            )
            and lead_checkpoint_zero.get("result_digest")
            == scope_decision.get(
                "lead_checkpoint_successor_zero_call_proof_result_digest"
            )
            and lead_checkpoint_zero.get("maximum_new_model_nodes") == 15
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_lead_checkpoint_successor_zero_call_not_passed"
            )
    elif submission_successor:
        submission_successor_zero = _json(
            inputs["submission_successor_zero_call_proof"]
        )
        analysis_completion_checkpoint = (
            validate_analysis_completion_checkpoint(
                _json(inputs["analysis_completion_checkpoint"])
            )
        )
        if not (
            submission_successor_zero.get("status")
            == "R5_completed_analysis_submission_successor_zero_call_pass"
            and submission_successor_zero.get("result_digest")
            == scope_decision.get(
                "submission_successor_zero_call_proof_result_digest"
            )
            and analysis_completion_checkpoint.get("checkpoint_digest")
            == scope_decision.get("analysis_completion_checkpoint_digest")
            and analysis_completion_checkpoint.get("submission_policy", {}).get(
                "analysis_rerun_forbidden"
            )
            is True
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_submission_successor_zero_call_not_passed"
            )
    elif analysis_successor:
        analysis_successor_zero = _json(
            inputs["analysis_successor_zero_call_proof"]
        )
        analysis_checkpoint = validate_analysis_fragment_checkpoint(
            _json(inputs["analysis_checkpoint"])
        )
        if not (
            analysis_successor_zero.get("status")
            == "R4_visible_analysis_checkpoint_successor_zero_call_pass"
            and analysis_successor_zero.get("result_digest")
            == scope_decision.get(
                "analysis_successor_zero_call_proof_result_digest"
            )
            and analysis_checkpoint.get("checkpoint_digest")
            == scope_decision.get("analysis_checkpoint_digest")
            and analysis_checkpoint.get("continuation_policy", {}).get(
                "maximum_continuation_calls"
            )
            == 1
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_analysis_successor_zero_call_not_passed"
            )
    planning_overlay = _json(inputs["planning_overlay"])
    if not (
        planning_overlay.get("status")
        == "provider_neutral_preview_proposal_execution_budget_separation"
        and planning_overlay.get("max_proposed_atoms_override") == 20
        and planning_overlay.get("max_evidence_requests_must_remain") == 12
        and (planning_overlay.get("authority") or {}).get(
            "product_pointer_promotion"
        )
        is False
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_planning_overlay_not_bound"
        )
    limits = authority["execution_limits"]
    if limits != scope_decision.get("execution_limits"):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_project_os_limit_drift"
        )
    if generic_successor:
        completed_frontier_count = sum(
            row["disposition"] in COMPLETED_DISPOSITIONS
            for row in frontier["nodes"]
        )
        fresh_frontier_count = len(frontier["nodes"]) - completed_frontier_count
        hierarchical_evaluator = (
            frontier.get("evaluation_strategy")
            == HIERARCHICAL_EVALUATION_STRATEGY
        )
        reused_role_evaluation_count = int(
            limits.get("reused_role_evaluation_count", 0)
        )
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 0
            and limits.get("maximum_new_lead_coordination_model_calls") == 0
            and limits.get(
                "maximum_resumed_downstream_analysis_continuations"
            )
            == 0
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 6
            and limits.get("reused_lead_coordination_count") == 1
            and limits.get("reused_completed_challenge_repair_count")
            == completed_frontier_count
            and limits.get("maximum_new_counter_challenge_repairs")
            == fresh_frontier_count
            and (
                (
                    limits.get("maximum_initial_role_evaluation_nodes")
                    == 6 - reused_role_evaluation_count
                    and 0
                    <= reused_role_evaluation_count
                    <= len(SPECIALIST_AGENT_IDS)
                    and limits.get("maximum_cross_role_evaluation_nodes") == 2
                    and limits.get(
                        "maximum_affected_role_reevaluation_nodes"
                    )
                    == 2
                )
                if hierarchical_evaluator
                else (
                    "maximum_initial_role_evaluation_nodes" not in limits
                    and "maximum_cross_role_evaluation_nodes" not in limits
                    and "maximum_affected_role_reevaluation_nodes" not in limits
                )
            )
        )
        expected_new_nodes = fresh_frontier_count + (
            13 - reused_role_evaluation_count
            if hierarchical_evaluator
            else 5
        )
    elif role_scoped_repair_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 0
            and limits.get("maximum_new_lead_coordination_model_calls") == 0
            and limits.get(
                "maximum_resumed_downstream_analysis_continuations"
            )
            == 0
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 6
            and limits.get("reused_lead_coordination_count") == 1
            and limits.get("reused_completed_challenge_repair_count") == 2
            and limits.get("maximum_new_counter_challenge_repairs") == 1
        )
        expected_new_nodes = 6
    elif downstream_analysis_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 0
            and limits.get("maximum_new_lead_coordination_model_calls") == 0
            and limits.get(
                "maximum_resumed_downstream_analysis_continuations"
            )
            == 1
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 6
            and limits.get("reused_lead_coordination_count") == 1
            and limits.get("reused_completed_challenge_repair_count") == 1
            and limits.get("maximum_new_counter_challenge_repairs") == 2
        )
        expected_new_nodes = 7
    elif coordination_checkpoint_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 0
            and limits.get("maximum_new_lead_coordination_model_calls") == 0
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 6
            and limits.get("reused_lead_coordination_count") == 1
        )
        expected_new_nodes = 8
    elif specialist_analysis_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 0
            and limits.get(
                "maximum_resumed_specialist_analysis_continuations"
            )
            == 1
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 5
        )
        expected_new_nodes = 10
    elif workpaper_checkpoint_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_initial_workpaper_nodes") == 1
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
            and limits.get("reused_workpaper_count") == 5
        )
        expected_new_nodes = 10
    elif lead_checkpoint_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_plan_model_calls") == 0
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
            and limits.get("reused_lead_plan_count") == 1
        )
        expected_new_nodes = 15
    elif submission_successor:
        mode_limits_valid = (
            limits.get("maximum_new_lead_analysis_calls") == 0
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
        )
        expected_new_nodes = 16
    elif analysis_successor:
        mode_limits_valid = (
            limits.get("maximum_resumed_lead_analysis_continuations") == 1
            and limits.get("maximum_new_analysis_calls_per_other_node") == 1
        )
        expected_new_nodes = 16
    else:
        mode_limits_valid = limits.get("maximum_analysis_calls_per_node") == 1
        expected_new_nodes = 16
    if not (
        limits.get("maximum_new_model_nodes") == expected_new_nodes
        and mode_limits_valid
        and limits.get("maximum_submission_attempts_per_node") == 2
        and limits.get("reused_specialist_plan_count") == 6
        and limits.get("maximum_counter_challenge_repairs") == 3
        and limits.get("maximum_evaluator_repairs") == 2
        and limits.get("maximum_evaluation_rounds") == 2
        and limits.get("external_source_network_calls") == 0
        and limits.get("candidate_promotions") == 0
        and limits.get("product_publication") is False
        and limits.get("qualified_human_acceptance") is False
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_execution_limits_invalid"
        )
    topology = load_multi_agent_role_topology(_json(inputs["topology"]))
    checkpoint = validate_specialist_plan_checkpoint(
        _json(inputs["predecessor_plan_checkpoint"]), topology=topology
    )
    if not (
        checkpoint.get("reused_specialist_plan_count") == 6
        and checkpoint.get("new_model_calls") == 0
        and checkpoint.get("new_network_calls") == 0
        and checkpoint.get("new_candidate_promotions") == 0
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_plan_checkpoint_invalid"
        )
    if (
        lead_checkpoint_successor
        or workpaper_checkpoint_successor
        or specialist_analysis_successor
        or coordination_checkpoint_successor
        or downstream_analysis_successor
    ):
        lead_checkpoint = validate_lead_plan_checkpoint(
            _json(inputs["lead_plan_checkpoint"]),
            opinions=checkpoint["specialist_plans"],
            topology=topology,
        )
        expected_lead_checkpoint_digest = (
            lead_checkpoint["checkpoint_digest"]
            if downstream_analysis_successor
            else (
                predecessor_scope_decision.get("lead_plan_checkpoint_digest")
                if coordination_checkpoint_successor
                else scope_decision.get("lead_plan_checkpoint_digest")
            )
        )
        if not (
            lead_checkpoint["checkpoint_digest"]
            == expected_lead_checkpoint_digest
            and lead_checkpoint["specialist_plan_checkpoint_digest"]
            == checkpoint["checkpoint_digest"]
            and (
                coordination_checkpoint_successor
                or downstream_analysis_successor
                or workpaper_checkpoint_successor
                or specialist_analysis_successor
                or (
                    lead_checkpoint_zero.get("lead_plan_checkpoint_digest")
                    == lead_checkpoint["checkpoint_digest"]
                    and lead_checkpoint_zero.get("lead_plan_digest")
                    == lead_checkpoint["lead_plan"]["lead_plan_digest"]
                )
            )
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_lead_plan_checkpoint_invalid"
            )
    outputs = authority["outputs"]
    expected_outputs = {
        "run_id",
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
    }
    if set(outputs) != expected_outputs:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_outputs_invalid"
        )
    paths = {key: _resolve(str(value)) for key, value in outputs.items() if key != "run_id"}
    if (
        paths["capture_root_ref"].exists()
        or paths["private_output_root_ref"].exists()
        or paths["public_result_ref"].exists()
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_output_identity_consumed"
        )
    return authority, inputs, {**outputs, **paths}


def _input_ref_count(messages: Sequence[Mapping[str, Any]]) -> int:
    text = "".join(str(row.get("content") or "") for row in messages)
    return sum(text.count(prefix) for prefix in ("EV::", "NUM::", "REL::", "GAP::"))


def _load_bound_analysis_checkpoint_draft(
    checkpoint: Mapping[str, Any],
) -> str:
    response_path = _resolve(str(checkpoint["response_capture_ref"]))
    request_path = _resolve(str(checkpoint["request_capture_ref"]))
    if not (
        _sha(request_path) == checkpoint["request_capture_sha256"]
        and _sha(response_path) == checkpoint["response_capture_sha256"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_capture_drift"
        )
    request = _json(request_path)
    response = _json(response_path)
    try:
        choice = response["response_body"]["choices"][0]
        draft = str(choice["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_content_missing"
        ) from exc
    if not (
        request.get("request_digest") == checkpoint["request_digest"]
        and response.get("response_digest") == checkpoint["response_digest"]
        and response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and choice.get("finish_reason") == "length"
        and canonical_digest(draft) == checkpoint["partial_draft_digest"]
        and len(draft) == checkpoint["partial_draft_character_count"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_content_drift"
        )
    return draft


def _load_bound_analysis_checkpoint_source(
    checkpoint: Mapping[str, Any],
) -> tuple[str, tuple[dict[str, Any], ...]]:
    """Load the partial draft and the exact model-visible source conversation."""

    draft = _load_bound_analysis_checkpoint_draft(checkpoint)
    request = _json(_resolve(str(checkpoint["request_capture_ref"])))
    raw_messages = (request.get("request_body") or {}).get("messages")
    if not (
        isinstance(raw_messages, list)
        and len(raw_messages) == 2
        and [row.get("role") for row in raw_messages if isinstance(row, Mapping)]
        == ["system", "user"]
        and all(
            isinstance(row, Mapping)
            and isinstance(row.get("content"), str)
            and str(row["content"]).strip()
            for row in raw_messages
        )
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_checkpoint_conversation_invalid"
        )
    return draft, tuple(deepcopy(dict(row)) for row in raw_messages)


def _load_bound_completed_analysis_draft(
    checkpoint: Mapping[str, Any],
) -> str:
    fragment_path = _resolve(str(checkpoint["fragment_checkpoint_ref"]))
    request_path = _resolve(
        str(checkpoint["continuation_request_capture_ref"])
    )
    response_path = _resolve(
        str(checkpoint["continuation_response_capture_ref"])
    )
    if not (
        _sha(fragment_path) == checkpoint["fragment_checkpoint_sha256"]
        and _sha(request_path)
        == checkpoint["continuation_request_capture_sha256"]
        and _sha(response_path)
        == checkpoint["continuation_response_capture_sha256"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_analysis_capture_drift"
        )
    fragment = validate_analysis_fragment_checkpoint(_json(fragment_path))
    if fragment["checkpoint_digest"] != checkpoint["fragment_checkpoint_digest"]:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_analysis_fragment_drift"
        )
    partial_draft = _load_bound_analysis_checkpoint_draft(fragment)
    request = _json(request_path)
    response = _json(response_path)
    try:
        choice = response["response_body"]["choices"][0]
        continuation_draft = str(choice["message"]["content"]).strip()
        request_messages = request["request_body"]["messages"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_analysis_content_missing"
        ) from exc
    if not (
        request.get("request_digest") == checkpoint["continuation_request_digest"]
        and response.get("response_digest")
        == checkpoint["continuation_response_digest"]
        and canonical_digest(request_messages)
        == checkpoint["continuation_messages_digest"]
        and response.get("response_body_complete") is True
        and response.get("eligible_for_business_promotion") is False
        and choice.get("finish_reason") == "stop"
        and canonical_digest(continuation_draft)
        == checkpoint["continuation_draft_digest"]
        and len(continuation_draft)
        == checkpoint["continuation_draft_character_count"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_analysis_content_drift"
        )
    merged = merge_analysis_draft_fragments(
        checkpoint=fragment,
        partial_draft=partial_draft,
        continuation_draft=continuation_draft,
    )
    if not (
        canonical_digest(merged) == checkpoint["merged_analysis_draft_digest"]
        and len(merged) == checkpoint["merged_analysis_draft_character_count"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_analysis_merge_drift"
        )
    return merged


def _load_bound_counter_workpaper(
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    """Recover the exact validated Counter workpaper from the R9 terminal."""

    bound_artifacts: dict[str, dict[str, Any]] = {}
    for prefix in (
        "source_authority",
        "source_public_result",
        "predecessor_workpaper_checkpoint",
    ):
        ref = str(checkpoint.get(f"{prefix}_ref") or "")
        expected_sha = str(checkpoint.get(f"{prefix}_sha256") or "")
        if not ref or not expected_sha:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_coordination_source_binding_missing:"
                + prefix
            )
        path = _resolve(ref)
        if not path.is_file() or _sha(path) != expected_sha:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_coordination_source_binding_drift:"
                + prefix
            )
        bound_artifacts[prefix] = _json(path)
    if not (
        bound_artifacts["source_public_result"].get("result_digest")
        == checkpoint.get("source_public_result_digest")
        and bound_artifacts["predecessor_workpaper_checkpoint"].get(
            "checkpoint_digest"
        )
        == checkpoint.get("predecessor_workpaper_checkpoint_digest")
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_source_lineage_drift"
        )
    terminal_path = _resolve(str(checkpoint["source_terminal_result_ref"]))
    if not terminal_path.is_file() or _sha(terminal_path) != checkpoint[
        "source_terminal_result_sha256"
    ]:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_terminal_capture_drift"
        )
    terminal = _json(terminal_path)
    receipt = deepcopy(
        dict((checkpoint.get("source_receipts") or {}).get("counter_workpaper") or {})
    )
    rows = [
        deepcopy(dict(row))
        for row in terminal.get("node_executions") or []
        if isinstance(row, Mapping)
        and row.get("node_id") == "AGENT::COUNTEREVIDENCE::WORKPAPER_R1"
    ]
    if len(rows) != 1:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_counter_workpaper_missing"
        )
    row = rows[0]
    attempts = [deepcopy(dict(item)) for item in row.get("attempts") or []]
    payload = deepcopy(dict(row.get("validated_payload") or {}))
    if not (
        terminal.get("full_result_digest")
        == checkpoint["source_terminal_result_digest"]
        and terminal.get("implementation_commit")
        and terminal.get("failure_code")
        == "multi_agent_lead_coordination_identity_invalid"
        and receipt.get("source_run_id") == checkpoint["source_run_id"]
        and receipt.get("node_id") == row.get("node_id")
        and receipt.get("attempt_ids")
        == [attempt.get("attempt_id") for attempt in attempts]
        and receipt.get("request_digests")
        == [attempt.get("request_digest") for attempt in attempts]
        and receipt.get("response_digests")
        == [attempt.get("response_digest") for attempt in attempts]
        and payload.get("agent_id") == SPECIALIST_AGENT_IDS[-1]
        and payload.get("workpaper_digest")
        == receipt.get("validated_payload_digest")
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_counter_workpaper_drift"
        )
    return payload


def _load_bound_lead_coordination_decision(
    checkpoint: Mapping[str, Any],
) -> dict[str, Any]:
    """Recover one complete strict Tool Call without rerunning Lead."""

    receipt = deepcopy(
        dict((checkpoint.get("source_receipts") or {}).get("lead_coordination") or {})
    )
    request_ref = str(receipt.get("request_capture_ref") or "")
    response_ref = str(receipt.get("response_capture_ref") or "")
    if not request_ref or not response_ref:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_capture_binding_missing"
        )
    request_path = _resolve(request_ref)
    response_path = _resolve(response_ref)
    if not (
        request_path.is_file()
        and response_path.is_file()
        and _sha(request_path) == receipt.get("request_capture_sha256")
        and _sha(response_path) == receipt.get("response_capture_sha256")
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_capture_drift"
        )
    request = _json(request_path)
    response = _json(response_path)
    try:
        choice = response["response_body"]["choices"][0]
        calls = choice["message"]["tool_calls"]
        call = calls[0]
        payload = json.loads(call["function"]["arguments"])
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_tool_call_missing"
        ) from exc
    if not (
        request.get("attempt_id") == receipt.get("accepted_attempt_id")
        and response.get("attempt_id") == receipt.get("accepted_attempt_id")
        and request.get("request_digest") == receipt.get("request_digest")
        and response.get("response_digest") == receipt.get("response_digest")
        and response.get("response_body_complete") is True
        and response.get("response_body_parse_status") == "json"
        and response.get("eligible_for_contract_parse") is True
        and response.get("eligible_for_business_promotion") is False
        and response.get("partial_response_received") is False
        and response.get("truncated") is False
        and choice.get("finish_reason") == "tool_calls"
        and len(calls) == 1
        and call.get("type") == "function"
        and (call.get("function") or {}).get("name") == receipt.get("tool_name")
        == "submit_lead_coordination_decision"
        and isinstance(payload, Mapping)
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_coordination_tool_call_drift"
        )
    return deepcopy(dict(payload))


def _load_bound_completed_repair_context(
    *,
    row: Mapping[str, Any],
    receipt: Mapping[str, Any],
    source_run_id: str,
    coordination_checkpoint: Mapping[str, Any],
    context_session_run_id: str | None = None,
) -> dict[str, Any]:
    """Recover the exact source context instead of recompiling session-bound feedback."""

    attempts = [
        deepcopy(dict(item))
        for item in row.get("attempts") or ()
        if isinstance(item, Mapping)
    ]
    analysis_attempts = [
        item
        for item in attempts
        if (
            item.get("phase") == "analysis"
            and item.get("status") == "analysis_draft_valid"
        )
        or (
            item.get("phase") == "analysis_continuation"
            and item.get("status") == "analysis_continuation_valid"
        )
    ]
    if len(analysis_attempts) != 1:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_repair_analysis_attempt_invalid"
        )
    attempt = analysis_attempts[0]
    request_ref = str(attempt.get("request_capture_ref") or "")
    request_path = _resolve(request_ref)
    if not request_ref or not request_path.is_file():
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_repair_context_capture_missing"
        )
    request = _json(request_path)
    request_body = request.get("request_body") or {}
    raw_messages = request_body.get("messages")
    if not (
        request.get("capture_type") == "model_visible_request_without_credentials"
        and request.get("credential_or_authorization_captured") is False
        and request.get("run_id") == source_run_id
        and request.get("attempt_id") == attempt.get("attempt_id")
        and request.get("request_digest") == attempt.get("request_digest")
        == canonical_digest(request_body)
        and isinstance(raw_messages, list)
        and len(raw_messages) in {2, 4}
        and [
            item.get("role")
            for item in raw_messages[:2]
            if isinstance(item, Mapping)
        ]
        == ["system", "user"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_repair_context_capture_drift"
        )
    try:
        envelope = json.loads(str(raw_messages[1]["content"]))
        task_context = envelope["task_context"]
        context = json.loads(str(task_context[0]["content"]))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_repair_context_missing"
        ) from exc
    context_body = {
        key: value for key, value in context.items() if key != "context_digest"
    }
    feedback = list(context.get("feedback_receipts") or ())
    target = str(receipt["target_agent_id"])
    prior = context.get("prior_workpaper") or {}
    if not (
        envelope.get("phase") == "analysis_only_not_business_authority"
        and envelope.get("later_tool_name") == "submit_specialist_workpaper"
        and isinstance(task_context, list)
        and len(task_context) == 1
        and task_context[0].get("role") == "user"
        and context.get("schema_version")
        in {
            "fin_ia_specialist_context_v1_0",
            "fin_ia_specialist_repair_context_v1_0",
        }
        and (context.get("agent") or {}).get("agent_id") == target
        and context.get("context_digest") == canonical_digest(context_body)
        and len(feedback) == 1
        and feedback[0].get("target_node_id") == target
        and feedback[0].get("session_id", "").find(
            str(context_session_run_id or source_run_id)
        )
        >= 0
        and "challenge://" + str(receipt["challenge_id"])
        in (feedback[0].get("artifact_refs") or ())
        and prior.get("workpaper_digest")
        == (coordination_checkpoint.get("workpaper_digests") or {}).get(target)
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_completed_repair_context_invalid"
        )
    return deepcopy(dict(context))


def _load_bound_downstream_repair_progress_bundle_v2(
    *,
    checkpoint: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    """Recover inherited and newly completed repairs before a fresh pending node."""

    progress = validate_downstream_repair_progress_checkpoint_v2(checkpoint)
    bound_prefixes = (
        "source_authority",
        "source_public_result",
        "source_terminal_result",
        "predecessor_progress_checkpoint",
        "predecessor_analysis_fragment_checkpoint",
        "lead_coordination_checkpoint",
    )
    for prefix in bound_prefixes:
        ref = str(progress.get(f"{prefix}_ref") or "")
        expected_sha = str(progress.get(f"{prefix}_sha256") or "")
        path = _resolve(ref)
        if not ref or not path.is_file() or _sha(path) != expected_sha:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_downstream_progress_v2_binding_drift:"
                + prefix
            )

    predecessor_progress = _json(
        _resolve(progress["predecessor_progress_checkpoint_ref"])
    )
    predecessor_fragment = _json(
        _resolve(progress["predecessor_analysis_fragment_checkpoint_ref"])
    )
    inherited, inherited_contexts = (
        _load_bound_downstream_repair_progress_bundle(
            checkpoint=predecessor_progress,
            fragment_checkpoint=predecessor_fragment,
        )
    )
    inherited_count = int(progress["inherited_completed_repair_count"])
    inherited_receipts = progress["completed_challenge_repairs"][
        :inherited_count
    ]
    if not (
        predecessor_progress.get("checkpoint_digest")
        == progress["predecessor_progress_checkpoint_digest"]
        and predecessor_fragment.get("checkpoint_digest")
        == progress["predecessor_analysis_fragment_checkpoint_digest"]
        and len(inherited) == inherited_count
        and [str(row["challenge_id"]) for row in inherited_receipts]
        == list(inherited)
        and all(
            inherited[str(row["challenge_id"])]["workpaper_digest"]
            == row["workpaper_digest"]
            for row in inherited_receipts
        )
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_v2_predecessor_drift"
        )

    public_result = _json(_resolve(progress["source_public_result_ref"]))
    terminal = _json(_resolve(progress["source_terminal_result_ref"]))
    coordination = _json(
        _resolve(progress["lead_coordination_checkpoint_ref"])
    )
    if not (
        public_result.get("result_digest")
        == progress["source_public_result_digest"]
        and terminal.get("full_result_digest")
        == progress["source_terminal_result_digest"]
        and terminal.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and coordination.get("checkpoint_digest")
        == progress["lead_coordination_checkpoint_digest"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_v2_lineage_drift"
        )

    completed = dict(inherited)
    completed_contexts = dict(inherited_contexts)
    source_rows = {
        str(row.get("node_id")): deepcopy(dict(row))
        for row in terminal.get("node_executions") or ()
        if isinstance(row, Mapping)
    }
    for receipt in progress["completed_challenge_repairs"][inherited_count:]:
        row = source_rows.get(str(receipt["node_id"])) or {}
        payload = deepcopy(dict(row.get("validated_payload") or {}))
        if not (
            row
            and receipt["source_run_id"] == progress["source_run_id"]
            and payload.get("agent_id") == receipt["target_agent_id"]
            and payload.get("workpaper_digest") == receipt["workpaper_digest"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_downstream_progress_v2_completed_drift"
            )
        challenge_id = str(receipt["challenge_id"])
        completed[challenge_id] = payload
        completed_contexts[challenge_id] = _load_bound_completed_repair_context(
            row=row,
            receipt=receipt,
            source_run_id=str(receipt["source_run_id"]),
            context_session_run_id=str(receipt["context_session_run_id"]),
            coordination_checkpoint=coordination,
        )

    expected_completed = {
        str(row["challenge_id"])
        for row in progress["completed_challenge_repairs"]
    }
    if set(completed) != expected_completed or set(completed_contexts) != set(
        completed
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_v2_completed_set_invalid"
        )
    return completed, completed_contexts, progress


def _load_bound_generic_successor_frontier(
    *,
    frontier: Mapping[str, Any],
) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, Any],
]:
    """Load completed nodes from one data-compiled execution frontier."""

    trusted = validate_successor_execution_frontier(frontier)
    completed: dict[str, dict[str, Any]] = {}
    contexts: dict[str, dict[str, Any]] = {}
    completed_rows: list[dict[str, Any]] = []
    for frontier_row in trusted["nodes"]:
        if frontier_row["disposition"] not in COMPLETED_DISPOSITIONS:
            continue
        terminal_path = _resolve(str(frontier_row["source_terminal_ref"]))
        request_path = _resolve(str(frontier_row["source_request_ref"]))
        if not (
            terminal_path.is_file()
            and request_path.is_file()
            and _sha(terminal_path)
            == frontier_row["source_terminal_sha256"]
            and _sha(request_path) == frontier_row["source_request_sha256"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_source_binding_drift"
            )
        terminal = _json(terminal_path)
        terminal_body = {
            key: value
            for key, value in terminal.items()
            if key != "full_result_digest"
        }
        source_node = next(
            (
                deepcopy(dict(row))
                for row in terminal.get("node_executions") or ()
                if row.get("node_id") == frontier_row["node_id"]
            ),
            None,
        )
        if not (
            terminal.get("full_result_digest")
            == frontier_row["source_terminal_digest"]
            == canonical_digest(terminal_body)
            and source_node is not None
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_terminal_invalid"
            )
        source_payload = deepcopy(
            dict(source_node.get("validated_payload") or {})
        )
        source_business = {
            key: value
            for key, value in source_payload.items()
            if key not in {"context_digest", "workpaper_digest"}
        }
        normalized = deepcopy(dict(frontier_row["normalized_workpaper"]))
        normalized_business = {
            key: value
            for key, value in normalized.items()
            if key not in {"context_digest", "workpaper_digest"}
        }
        attempts = [
            deepcopy(dict(row))
            for row in source_node.get("attempts") or ()
            if (
                row.get("phase") == "analysis"
                and row.get("status") == "analysis_draft_valid"
            )
            or (
                row.get("phase") == "analysis_continuation"
                and row.get("status") == "analysis_continuation_valid"
            )
        ]
        if not (
            len(attempts) == 1
            and source_payload.get("agent_id")
            == frontier_row["target_agent_id"]
            and source_payload.get("workpaper_digest")
            == frontier_row["source_workpaper_digest"]
            and source_business == normalized_business
            and canonical_digest(source_business)
            == frontier_row["business_payload_digest"]
            and attempts[0].get("request_capture_ref")
            and _relative(_resolve(attempts[0]["request_capture_ref"]))
            == frontier_row["source_request_ref"]
            and attempts[0].get("request_digest")
            == frontier_row["source_request_digest"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_business_lineage_invalid"
            )
        request = _json(request_path)
        request_body = request.get("request_body") or {}
        messages = request_body.get("messages") or []
        if not (
            request.get("capture_type")
            == "model_visible_request_without_credentials"
            and request.get("credential_or_authorization_captured") is False
            and request.get("run_id") == frontier_row["source_run_id"]
            and request.get("attempt_id") == attempts[0].get("attempt_id")
            and request.get("request_digest")
            == frontier_row["source_request_digest"]
            == canonical_digest(request_body)
            and isinstance(messages, list)
            and len(messages) in {2, 4}
            and [row.get("role") for row in messages[:2]]
            == ["system", "user"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_request_invalid"
            )
        try:
            envelope = json.loads(str(messages[1]["content"]))
            context = json.loads(
                str(envelope["task_context"][0]["content"])
            )
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_context_missing"
            ) from exc
        context_body = {
            key: value for key, value in context.items() if key != "context_digest"
        }
        if not (
            context.get("context_digest")
            == frontier_row["model_visible_context_digest"]
            == canonical_digest(context_body)
            and normalized.get("context_digest")
            == frontier_row["model_visible_context_digest"]
            and normalized.get("workpaper_digest")
            == frontier_row["normalized_workpaper_digest"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_context_invalid"
            )
        revalidated = revalidate_bound_specialist_workpaper(
            normalized,
            context=context,
            expected_agent_id=str(frontier_row["target_agent_id"]),
        )
        if frontier_row["disposition"] == "exact_reuse":
            if not (
                frontier_row["source_workpaper_digest"]
                == frontier_row["normalized_workpaper_digest"]
                and frontier_row["source_validation_context_digest"]
                == frontier_row["model_visible_context_digest"]
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_generic_frontier_exact_reuse_invalid"
                )
        elif not (
            frontier_row["source_workpaper_digest"]
            != frontier_row["normalized_workpaper_digest"]
            and frontier_row["source_validation_context_digest"]
            != frontier_row["model_visible_context_digest"]
            and frontier_row["business_payload_byte_equivalent"] is True
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_generic_frontier_rebind_invalid"
            )
        challenge_id = str(frontier_row["challenge_id"])
        completed[challenge_id] = revalidated
        contexts[challenge_id] = deepcopy(dict(context))
        completed_rows.append(
            {
                "challenge_id": challenge_id,
                "target_agent_id": frontier_row["target_agent_id"],
                "node_id": frontier_row["node_id"],
                "workpaper_digest": revalidated["workpaper_digest"],
                "disposition": frontier_row["disposition"],
            }
        )
    active = {
        "accepted_challenge_ids": list(trusted["accepted_challenge_ids"]),
        "completed_challenge_repairs": completed_rows,
        "pending_challenge_repairs": [
            deepcopy(dict(row))
            for row in trusted["nodes"]
            if row["disposition"] not in COMPLETED_DISPOSITIONS
        ],
        "checkpoint_digest": trusted["result_digest"],
    }
    if set(completed) != {
        str(row["challenge_id"]) for row in completed_rows
    } or set(contexts) != set(completed):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_generic_frontier_completed_set_invalid"
        )
    return completed, contexts, active


def _load_bound_downstream_repair_progress_bundle(
    *,
    checkpoint: Mapping[str, Any],
    fragment_checkpoint: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Recover completed repairs while preserving the active failed fragment."""

    progress = validate_downstream_repair_progress_checkpoint(checkpoint)
    fragment = validate_analysis_fragment_checkpoint(fragment_checkpoint)
    for prefix in (
        "source_authority",
        "source_public_result",
        "source_terminal_result",
        "lead_coordination_checkpoint",
        "active_analysis_fragment_checkpoint",
    ):
        ref = str(progress.get(f"{prefix}_ref") or "")
        expected_sha = str(progress.get(f"{prefix}_sha256") or "")
        path = _resolve(ref)
        if not ref or not path.is_file() or _sha(path) != expected_sha:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_downstream_progress_binding_drift:"
                + prefix
            )
    public_result = _json(_resolve(progress["source_public_result_ref"]))
    terminal = _json(_resolve(progress["source_terminal_result_ref"]))
    coordination = _json(
        _resolve(progress["lead_coordination_checkpoint_ref"])
    )
    if not (
        public_result.get("result_digest")
        == progress["source_public_result_digest"]
        and terminal.get("full_result_digest")
        == progress["source_terminal_result_digest"]
        and terminal.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and coordination.get("checkpoint_digest")
        == progress["lead_coordination_checkpoint_digest"]
        and fragment.get("checkpoint_digest")
        == progress["active_analysis_fragment_checkpoint_digest"]
        and fragment.get("run_id") == progress["source_run_id"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_lineage_drift"
        )
    terminal_attempts = [
        deepcopy(dict(row))
        for row in terminal.get("terminal_node_attempts") or []
        if isinstance(row, Mapping)
    ]
    if not (
        len(terminal_attempts) == 1
        and terminal_attempts[0].get("finish_reason") == "length"
        and terminal_attempts[0].get("request_digest")
        == fragment["request_digest"]
        and terminal_attempts[0].get("response_digest")
        == fragment["response_digest"]
        and terminal_attempts[0].get("analysis_draft_digest")
        == fragment["partial_draft_digest"]
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_fragment_drift"
        )
    source_rows = {
        str(row.get("node_id")): deepcopy(dict(row))
        for row in terminal.get("node_executions") or []
        if isinstance(row, Mapping)
    }
    completed: dict[str, dict[str, Any]] = {}
    completed_contexts: dict[str, dict[str, Any]] = {}
    for receipt in progress["completed_challenge_repairs"]:
        row = source_rows.get(str(receipt["node_id"])) or {}
        payload = deepcopy(dict(row.get("validated_payload") or {}))
        if not (
            row
            and payload.get("agent_id") == receipt["target_agent_id"]
            and payload.get("workpaper_digest") == receipt["workpaper_digest"]
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_downstream_completed_repair_drift"
            )
        challenge_id = str(receipt["challenge_id"])
        completed[challenge_id] = payload
        completed_contexts[challenge_id] = _load_bound_completed_repair_context(
            row=row,
            receipt=receipt,
            source_run_id=str(progress["source_run_id"]),
            coordination_checkpoint=coordination,
        )
    if set(completed) != {
        str(row["challenge_id"])
        for row in progress["completed_challenge_repairs"]
    } or set(completed_contexts) != set(completed):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_completed_repair_set_invalid"
        )
    return completed, completed_contexts


def _load_bound_downstream_repair_progress(
    *,
    checkpoint: Mapping[str, Any],
    fragment_checkpoint: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    completed, _ = _load_bound_downstream_repair_progress_bundle(
        checkpoint=checkpoint,
        fragment_checkpoint=fragment_checkpoint,
    )
    return completed


def _validate_downstream_progress_runtime_alignment(
    *,
    active_progress_checkpoint: Mapping[str, Any],
    coordination: Mapping[str, Any],
    completed_repairs: Mapping[str, Mapping[str, Any]],
) -> None:
    """Bind runtime reuse to the active successor checkpoint, not its ancestor."""

    expected_completed = {
        str(row["challenge_id"])
        for row in active_progress_checkpoint["completed_challenge_repairs"]
    }
    if not (
        active_progress_checkpoint["accepted_challenge_ids"]
        == coordination["accepted_challenge_ids"]
        and set(completed_repairs) == expected_completed
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_downstream_progress_runtime_drift"
        )


def _compile_evaluator_feedback_receipt(
    *,
    target_session_id: str,
    finding: Mapping[str, Any],
) -> dict[str, Any]:
    identity = {
        "target_session_id": target_session_id,
        "finding_code": finding["finding_code"],
        "target_agent_id": finding["target_agent_id"],
    }
    body = {
        "feedback_id": "FEEDBACK::" + canonical_digest(identity)[:24].upper(),
        "session_id": target_session_id,
        "source_node_id": "EVAL::L1_AND_CONTENT",
        "target_node_id": str(finding["target_agent_id"]),
        "failure_class": "independent_evaluation_finding",
        "failure_code": str(finding["finding_code"]),
        "owning_plane": (
            "agent_work_mode_plane"
            if finding["failure_owner"]
            in {"agent_orchestration_and_role_design", "model_judgment"}
            else (
                "harness_control_plane"
                if finding["failure_owner"] == "harness_control"
                else "infrastructure_and_tool_plane"
            )
        ),
        "owning_stage": "S3",
        "artifact_refs": [
            f"evaluation-finding://{finding['finding_code']}",
            *[str(ref) for ref in finding["evidence_refs"]],
        ],
        "model_visible_summary": str(finding["explanation"]),
        "permitted_next_actions": [str(finding["permitted_repair"])],
        "forbidden_interpretations": [
            "The finding is not new Evidence or a NumericFact",
            "A role repair cannot conceal an infrastructure or Harness failure",
            "Do not broaden the conclusion or add sources, facts or numbers",
        ],
        "created_at": _now(),
    }
    validated = validate_runtime_artifact("FeedbackReceipt", body)
    return {**validated, "feedback_digest": canonical_digest(validated)}


def _merge_local_evaluation(
    *,
    model_evaluation: Mapping[str, Any],
    local_findings: Sequence[Mapping[str, Any]],
    workpapers: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not local_findings:
        return deepcopy(dict(model_evaluation))
    combined = {
        "schema_version": model_evaluation["schema_version"],
        "findings": [
            *[deepcopy(dict(row)) for row in model_evaluation["findings"]],
            *[deepcopy(dict(row)) for row in local_findings],
        ],
        "cross_role_conflicts": list(model_evaluation["cross_role_conflicts"]),
        "report_may_proceed": False,
    }
    return validate_evaluation(combined, workpapers=workpapers)


def _checkpoint_and_resume_for_feedback(
    *,
    state: PreviewAgentSessionState,
    context: Mapping[str, Any],
    prior_workpaper: Mapping[str, Any],
    feedback_receipts: Sequence[Mapping[str, Any]],
    objective_digest: str,
    plan_digest: str,
) -> None:
    feedback_ids = tuple(str(row["feedback_id"]) for row in feedback_receipts)
    for receipt in feedback_receipts:
        state.feedback_receipts.append(deepcopy(dict(receipt)))
    state.append(
        event_type="feedback_issued",
        actor_id="HARNESS::FEEDBACK_ROUTER",
        feedback_refs=feedback_ids,
    )
    checkpoint_id = (
        f"CHECKPOINT::DELL::{state.agent_id.split('::')[-1]}::"
        f"{len(state.checkpoints) + 1:02d}"
    )
    state.append(
        event_type="checkpoint_created",
        actor_id=state.agent_id,
        output_refs=(f"checkpoint://{checkpoint_id}",),
    )
    cell = context["cell_analysis_view"]["cell"]
    evidence_refs = tuple(
        str(row["evidence_ref"]) for row in cell["cell_evidence_views"]
    )
    numeric_refs = tuple(str(row) for row in cell["allowed_numeric_refs"])
    gap_refs = tuple(str(row["gap_ref"]) for row in cell["residual_gap_cards"])
    question_refs = tuple(
        "question://" + canonical_digest(text)
        for text in prior_workpaper["what_would_change"]
    )
    checkpoint = create_context_checkpoint(
        session=state.session,
        events=state.events,
        checkpoint_id=checkpoint_id,
        objective_digest=objective_digest,
        plan_digest=plan_digest,
        research_graph_digest=canonical_digest(
            context["cell_analysis_view"].get("numeric_relation_catalog") or []
        ),
        accepted_evidence_refs=evidence_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=gap_refs,
        unresolved_feedback_refs=feedback_ids,
        agent_local_state_refs=(
            f"workpaper://{prior_workpaper['workpaper_digest']}",
        ),
        authority_refs=(
            f"context://{context['context_digest']}",
            f"plan://{plan_digest}",
        ),
        counterevidence_refs=tuple(
            str(ref)
            for receipt in feedback_receipts
            for ref in receipt["artifact_refs"]
        ),
        open_question_refs=question_refs,
    )
    state.checkpoints.append(checkpoint)
    resume = resume_agent_session(
        session=state.session,
        events=state.events,
        checkpoint=checkpoint,
        expected_case_id="DELL",
        expected_case_version="fin-0.1.3-preview",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=state.session["active_plan_ref"],
        resumed_at=_now(),
        required_authority_refs=checkpoint["authority_refs"],
        required_open_gap_refs=gap_refs,
        required_unresolved_feedback_refs=feedback_ids,
        required_counterevidence_refs=checkpoint["counterevidence_refs"],
        required_open_question_refs=question_refs,
    )
    state.resume_receipts.append(resume)
    state.append(
        event_type="session_resumed",
        actor_id=state.agent_id,
        input_refs=(f"checkpoint://{checkpoint_id}",),
        output_refs=(f"resume://{resume['resume_receipt_digest']}",),
        feedback_refs=feedback_ids,
    )


def _bind_reused_workpaper_checkpoint(
    *,
    state: PreviewAgentSessionState,
    context: Mapping[str, Any],
    prior_workpaper: Mapping[str, Any],
    source_checkpoint_digest: str,
    objective_digest: str,
    plan_digest: str,
    checkpoint_suffix: str = "R7-WORKPAPER",
    actor_id: str = "HARNESS::R7_WORKPAPER_CHECKPOINT",
) -> None:
    """Resume a specialist session from an immutable validated workpaper."""

    checkpoint_id = (
        f"CHECKPOINT::DELL::{state.agent_id.split('::')[-1]}::"
        f"{checkpoint_suffix}"
    )
    source_ref = f"checkpoint://{source_checkpoint_digest}"
    state.append(
        event_type="checkpoint_created",
        actor_id=actor_id,
        input_refs=(source_ref,),
        output_refs=(f"checkpoint://{checkpoint_id}",),
    )
    cell = context["cell_analysis_view"]["cell"]
    evidence_refs = tuple(
        str(row["evidence_ref"]) for row in cell["cell_evidence_views"]
    )
    numeric_refs = tuple(str(row) for row in cell["allowed_numeric_refs"])
    gap_refs = tuple(str(row["gap_ref"]) for row in cell["residual_gap_cards"])
    counter_refs = tuple(
        "counterargument://" + canonical_digest(text)
        for text in prior_workpaper["strongest_counterarguments"]
    )
    question_refs = tuple(
        "question://" + canonical_digest(text)
        for text in prior_workpaper["what_would_change"]
    )
    checkpoint = create_context_checkpoint(
        session=state.session,
        events=state.events,
        checkpoint_id=checkpoint_id,
        objective_digest=objective_digest,
        plan_digest=plan_digest,
        research_graph_digest=canonical_digest(
            context["cell_analysis_view"].get("numeric_relation_catalog") or []
        ),
        accepted_evidence_refs=evidence_refs,
        numeric_fact_refs=numeric_refs,
        open_gap_refs=gap_refs,
        unresolved_feedback_refs=(),
        agent_local_state_refs=(
            f"workpaper://{prior_workpaper['workpaper_digest']}",
        ),
        authority_refs=(
            f"context://{context['context_digest']}",
            f"plan://{plan_digest}",
            source_ref,
        ),
        counterevidence_refs=counter_refs,
        open_question_refs=question_refs,
    )
    state.checkpoints.append(checkpoint)
    resume = resume_agent_session(
        session=state.session,
        events=state.events,
        checkpoint=checkpoint,
        expected_case_id="DELL",
        expected_case_version="fin-0.1.3-preview",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=state.session["active_plan_ref"],
        resumed_at=_now(),
        required_authority_refs=checkpoint["authority_refs"],
        required_open_gap_refs=gap_refs,
        required_unresolved_feedback_refs=(),
        required_counterevidence_refs=counter_refs,
        required_open_question_refs=question_refs,
    )
    state.resume_receipts.append(resume)
    state.append(
        event_type="session_resumed",
        actor_id=state.agent_id,
        input_refs=(f"checkpoint://{checkpoint_id}", source_ref),
        output_refs=(f"resume://{resume['resume_receipt_digest']}",),
    )


def _bind_reused_lead_coordination_checkpoint(
    *,
    state: PreviewAgentSessionState,
    checkpoint: Mapping[str, Any],
    objective_digest: str,
    plan_digest: str,
) -> None:
    """Resume Lead after its immutable R9 coordination decision."""

    checkpoint_id = "CHECKPOINT::DELL::RESEARCH_LEAD::R9-COORDINATION"
    source_ref = f"checkpoint://{checkpoint['checkpoint_digest']}"
    challenge_refs = tuple(
        f"challenge://{challenge_id}"
        for challenge_id in checkpoint["challenge_ids"]
    )
    deferred_refs = tuple(
        f"deferred-challenge://{challenge_id}"
        for challenge_id in checkpoint["deferred_challenge_ids"]
    )
    state.append(
        event_type="checkpoint_created",
        actor_id="HARNESS::R10_COORDINATION_CHECKPOINT",
        input_refs=(source_ref,),
        output_refs=(f"checkpoint://{checkpoint_id}",),
    )
    runtime_checkpoint = create_context_checkpoint(
        session=state.session,
        events=state.events,
        checkpoint_id=checkpoint_id,
        objective_digest=objective_digest,
        plan_digest=plan_digest,
        research_graph_digest=str(checkpoint["challenge_catalog_digest"]),
        accepted_evidence_refs=(),
        numeric_fact_refs=(),
        open_gap_refs=(),
        unresolved_feedback_refs=(),
        agent_local_state_refs=(
            f"coordination://{checkpoint['coordination_decision_digest']}",
            *(
                f"workpaper://{digest}"
                for digest in checkpoint["workpaper_digests"].values()
            ),
        ),
        authority_refs=(f"plan://{plan_digest}", source_ref),
        counterevidence_refs=challenge_refs,
        open_question_refs=deferred_refs,
    )
    state.checkpoints.append(runtime_checkpoint)
    resume = resume_agent_session(
        session=state.session,
        events=state.events,
        checkpoint=runtime_checkpoint,
        expected_case_id="DELL",
        expected_case_version="fin-0.1.3-preview",
        expected_as_of_date="2026-08-06",
        expected_active_plan_ref=state.session["active_plan_ref"],
        resumed_at=_now(),
        required_authority_refs=runtime_checkpoint["authority_refs"],
        required_open_gap_refs=(),
        required_unresolved_feedback_refs=(),
        required_counterevidence_refs=challenge_refs,
        required_open_question_refs=deferred_refs,
    )
    state.resume_receipts.append(resume)
    state.append(
        event_type="session_resumed",
        actor_id=state.agent_id,
        input_refs=(f"checkpoint://{checkpoint_id}", source_ref),
        output_refs=(f"resume://{resume['resume_receipt_digest']}",),
    )


def _stop_role(
    *,
    state: PreviewAgentSessionState,
    context: Mapping[str, Any] | None,
    evaluation: Mapping[str, Any],
) -> None:
    findings = [
        row
        for row in evaluation["findings"]
        if row["target_agent_id"] == state.agent_id and row["blocks_report"]
    ]
    gap_refs = (
        [
            str(row["gap_ref"])
            for row in context["cell_analysis_view"]["cell"]["residual_gap_cards"]
        ]
        if context is not None
        else []
    )
    if any(
        row["failure_owner"] == "data_infrastructure_or_tool"
        for row in findings
    ):
        decision = "pause_for_tool_recovery"
    elif findings:
        decision = "stop_contract_failure"
    elif gap_refs:
        decision = "stop_information_boundary"
    else:
        decision = "stop_sufficient"
    stop = {
        "stop_decision_id": (
            "STOP::" + canonical_digest(
                {"session_id": state.session["session_id"], "decision": decision}
            )[:24].upper()
        ),
        "session_id": state.session["session_id"],
        "decided_by_agent_id": state.agent_id,
        "decision": decision,
        "reason_codes": (
            [str(row["finding_code"]) for row in findings]
            or (["typed_information_boundary_preserved"] if gap_refs else ["role_workpaper_complete"])
        ),
        "coverage_state_refs": [
            "coverage://" + (str(context["context_digest"]) if context else state.agent_id)
        ],
        "unresolved_feedback_refs": [
            str(row["feedback_id"])
            for row in state.feedback_receipts
            if findings
        ],
        "remaining_gap_refs": gap_refs,
        "budget_state": {"new_model_steps_authorized": 0},
        "quality_risk": (
            "; ".join(str(row["explanation"]) for row in findings)
            if findings
            else "remaining typed gaps are visible and no blocking evaluator finding remains"
        ),
        "harness_validation_status": "accepted",
    }
    validated = validate_runtime_artifact("StopDecision", stop)
    state.stop_decisions.append(validated)
    state.append(
        event_type="stop_decided",
        actor_id=state.agent_id,
        output_refs=(f"stop://{validated['stop_decision_id']}",),
        feedback_refs=tuple(validated["unresolved_feedback_refs"]),
    )


def _run_authorized(authority_path: Path) -> dict[str, Any]:
    authority, paths, outputs = _validate_authority(authority_path)
    analysis_successor = (
        authority["schema_version"] == ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    )
    submission_successor = (
        authority["schema_version"] == SUBMISSION_SUCCESSOR_AUTHORITY_SCHEMA
    )
    lead_checkpoint_successor = (
        authority["schema_version"]
        == LEAD_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    workpaper_checkpoint_successor = (
        authority["schema_version"]
        == WORKPAPER_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    specialist_analysis_successor = (
        authority["schema_version"]
        == SPECIALIST_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA
    )
    coordination_checkpoint_successor = (
        authority["schema_version"]
        == COORDINATION_CHECKPOINT_SUCCESSOR_AUTHORITY_SCHEMA
    )
    preprovider_replacement = authority["schema_version"] in {
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA,
    }
    continuation_profile_replacement = (
        authority["schema_version"]
        == DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA
    )
    repair_context_replacement = (
        authority["schema_version"]
        == DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA
    )
    generic_successor = (
        authority["schema_version"] == GENERIC_SUCCESSOR_AUTHORITY_SCHEMA
    )
    role_scoped_repair_successor = (
        repair_context_replacement or generic_successor
    )
    downstream_analysis_successor = authority["schema_version"] in {
        DOWNSTREAM_ANALYSIS_SUCCESSOR_AUTHORITY_SCHEMA,
        DOWNSTREAM_ANALYSIS_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTEXT_REPLAY_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_CONTINUATION_PROFILE_REPLACEMENT_AUTHORITY_SCHEMA,
        DOWNSTREAM_REPAIR_CONTEXT_REPLACEMENT_AUTHORITY_SCHEMA,
        GENERIC_SUCCESSOR_AUTHORITY_SCHEMA,
    }
    coordination_resume = (
        coordination_checkpoint_successor or downstream_analysis_successor
    )
    full_schema, public_schema = _result_schemas_for_authority(
        authority["schema_version"]
    )
    if not os.environ.get("DEEPSEEK_API_KEY"):
        raise MultiAgentPreviewLiveError("deepseek_api_key_missing")
    topology = load_multi_agent_role_topology(_json(paths["topology"]))
    objective_payload = _json(paths["objective"])
    analysis_profile = load_chat_completion_profile(
        _json(paths["analysis_profile"])
    )
    submission_profile = load_chat_completion_profile(
        _json(paths["submission_profile"])
    )
    repair_analysis_profile = (
        load_chat_completion_profile(_json(paths["repair_analysis_profile"]))
        if role_scoped_repair_successor
        else None
    )
    evaluator_analysis_profile = (
        load_chat_completion_profile(_json(paths["evaluator_analysis_profile"]))
        if generic_successor and "evaluator_analysis_profile" in paths
        else None
    )
    continuation_profile = (
        load_chat_completion_profile(
            _json(
                paths[
                    "analysis_completion_profile"
                    if continuation_profile_replacement
                    else "analysis_continuation_profile"
                ]
            )
        )
        if analysis_successor
        or specialist_analysis_successor
        or (downstream_analysis_successor and not generic_successor)
        else None
    )
    validate_deepseek_ga_profile(analysis_profile, strict_tools=False)
    if repair_analysis_profile is not None:
        validate_deepseek_ga_profile(
            repair_analysis_profile,
            strict_tools=False,
            expected_reasoning_effort="high",
        )
    if evaluator_analysis_profile is not None:
        evaluator_profile_defaults = dict(
            evaluator_analysis_profile.request_defaults
        )
        if evaluator_profile_defaults.get("thinking") == {"type": "disabled"}:
            validate_deepseek_ga_node_profile(
                evaluator_analysis_profile,
                node_class="content_evaluation_non_thinking",
            )
        else:
            validate_deepseek_ga_profile(
                evaluator_analysis_profile,
                strict_tools=False,
                expected_reasoning_effort="low",
            )
    validate_deepseek_ga_node_profile(
        submission_profile,
        node_class="contract_submission_non_thinking",
    )
    if continuation_profile_replacement:
        validate_deepseek_ga_node_profile(
            continuation_profile,
            node_class="contract_submission_non_thinking",
        )
    elif (
        analysis_successor
        or specialist_analysis_successor
        or (downstream_analysis_successor and not generic_successor)
    ) and not (
        continuation_profile is not None
        and continuation_profile.provider_id == "deepseek"
        and continuation_profile.model == "deepseek-v4-pro"
        and continuation_profile.base_url == "https://api.deepseek.com"
        and continuation_profile.endpoint == "/chat/completions"
        and dict(continuation_profile.request_defaults)
        == {
            "max_tokens": 4000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "low",
        }
        and continuation_profile.authority.get("retry_count") == 0
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_analysis_continuation_profile_invalid"
        )
    plan_checkpoint = validate_specialist_plan_checkpoint(
        _json(paths["predecessor_plan_checkpoint"]), topology=topology
    )
    lead_plan_checkpoint = (
        validate_lead_plan_checkpoint(
            _json(paths["lead_plan_checkpoint"]),
            opinions=plan_checkpoint["specialist_plans"],
            topology=topology,
        )
        if lead_checkpoint_successor
        or workpaper_checkpoint_successor
        or specialist_analysis_successor
        or coordination_checkpoint_successor
        or downstream_analysis_successor
        else None
    )
    lead_checkpoint_successor_zero = (
        _json(paths["lead_checkpoint_successor_zero_call_proof"])
        if lead_checkpoint_successor
        else None
    )
    workpaper_checkpoint_raw = (
        _json(paths["workpaper_checkpoint"])
        if workpaper_checkpoint_successor
        or specialist_analysis_successor
        or coordination_checkpoint_successor
        or downstream_analysis_successor
        else None
    )
    workpaper_checkpoint_successor_zero = (
        _json(paths["workpaper_checkpoint_successor_zero_call_proof"])
        if workpaper_checkpoint_successor
        else None
    )
    workpaper_terminal_failure = (
        _json(
            _resolve(
                str(workpaper_checkpoint_raw["source_terminal_result_ref"])
            )
        )
        if workpaper_checkpoint_raw is not None
        else None
    )
    coordination_checkpoint_raw = (
        _json(paths["lead_coordination_checkpoint"])
        if coordination_checkpoint_successor or downstream_analysis_successor
        else None
    )
    coordination_checkpoint_successor_zero = (
        _json(paths["coordination_checkpoint_successor_zero_call_proof"])
        if coordination_checkpoint_successor
        else None
    )
    successor_zero = _json(paths["successor_zero_call_proof"])
    analysis_successor_zero = (
        _json(paths["analysis_successor_zero_call_proof"])
        if analysis_successor
        else None
    )
    analysis_checkpoint = (
        validate_analysis_fragment_checkpoint(
            _json(
                paths[
                    "specialist_analysis_checkpoint"
                    if specialist_analysis_successor
                    else "analysis_checkpoint"
                ]
            )
        )
        if analysis_successor
        or specialist_analysis_successor
        else None
    )
    if analysis_checkpoint is not None and specialist_analysis_successor:
        (
            analysis_checkpoint_draft,
            analysis_checkpoint_original_messages,
        ) = _load_bound_analysis_checkpoint_source(analysis_checkpoint)
    else:
        analysis_checkpoint_draft = (
            _load_bound_analysis_checkpoint_draft(analysis_checkpoint)
            if analysis_checkpoint is not None
            else None
        )
        analysis_checkpoint_original_messages = None
    downstream_progress_checkpoint = (
        validate_downstream_repair_progress_checkpoint(
            _json(paths["downstream_repair_progress_checkpoint"])
        )
        if downstream_analysis_successor and not generic_successor
        else None
    )
    downstream_progress_checkpoint_v2 = (
        validate_downstream_repair_progress_checkpoint_v2(
            _json(paths["downstream_repair_progress_checkpoint_v2"])
        )
        if repair_context_replacement
        else None
    )
    downstream_analysis_checkpoint = (
        validate_analysis_fragment_checkpoint(
            _json(paths["downstream_analysis_fragment_checkpoint"])
        )
        if downstream_analysis_successor and not generic_successor
        else None
    )
    if downstream_analysis_checkpoint is not None:
        (
            downstream_analysis_checkpoint_draft,
            downstream_analysis_checkpoint_original_messages,
        ) = _load_bound_analysis_checkpoint_source(
            downstream_analysis_checkpoint
        )
    else:
        downstream_analysis_checkpoint_draft = None
        downstream_analysis_checkpoint_original_messages = None
    downstream_analysis_successor_zero = (
        _json(paths["downstream_analysis_successor_zero_call_proof"])
        if downstream_analysis_successor and not generic_successor
        else None
    )
    successor_frontier = (
        _json(paths["successor_execution_frontier"])
        if generic_successor
        else None
    )
    role_evaluation_checkpoint_raw = (
        _json(paths["role_evaluation_progress_checkpoint"])
        if generic_successor
        and "role_evaluation_progress_checkpoint" in paths
        else None
    )
    role_evaluation_checkpoint_terminal = (
        _json(
            _resolve(
                str(
                    role_evaluation_checkpoint_raw[
                        "source_terminal_result_ref"
                    ]
                )
            )
        )
        if role_evaluation_checkpoint_raw is not None
        else None
    )
    hierarchical_evaluator = bool(
        successor_frontier is not None
        and successor_frontier.get("evaluation_strategy")
        == HIERARCHICAL_EVALUATION_STRATEGY
    )
    hierarchical_evaluator_proof_binding = (
        _compile_hierarchical_evaluator_proof_binding(
            proof_path=paths["hierarchical_evaluator_zero_call_proof"],
            frontier=successor_frontier,
        )
        if hierarchical_evaluator and successor_frontier is not None
        else None
    )
    if generic_successor:
        (
            completed_downstream_repairs,
            completed_downstream_repair_contexts,
            active_downstream_progress_checkpoint,
        ) = _load_bound_generic_successor_frontier(
            frontier=successor_frontier
        )
    else:
        (
            completed_downstream_repairs,
            completed_downstream_repair_contexts,
        ) = (
            _load_bound_downstream_repair_progress_bundle_v2(
                checkpoint=downstream_progress_checkpoint_v2,
            )[:2]
            if downstream_progress_checkpoint_v2 is not None
            else (
                _load_bound_downstream_repair_progress_bundle(
                    checkpoint=downstream_progress_checkpoint,
                    fragment_checkpoint=downstream_analysis_checkpoint,
                )
                if downstream_progress_checkpoint is not None
                and downstream_analysis_checkpoint is not None
                else ({}, {})
            )
        )
        active_downstream_progress_checkpoint = (
            downstream_progress_checkpoint_v2
            if downstream_progress_checkpoint_v2 is not None
            else downstream_progress_checkpoint
        )
    specialist_analysis_successor_zero = (
        _json(paths["specialist_analysis_successor_zero_call_proof"])
        if specialist_analysis_successor
        else None
    )
    submission_successor_zero = (
        _json(paths["submission_successor_zero_call_proof"])
        if submission_successor
        else None
    )
    analysis_completion_checkpoint = (
        validate_analysis_completion_checkpoint(
            _json(paths["analysis_completion_checkpoint"])
        )
        if submission_successor
        else None
    )
    completed_analysis_draft = (
        _load_bound_completed_analysis_draft(analysis_completion_checkpoint)
        if analysis_completion_checkpoint is not None
        else None
    )
    planning_overlay = _json(paths["planning_overlay"])
    run_id = str(outputs["run_id"])
    capture_root = outputs["capture_root_ref"]
    private_root = outputs["private_output_root_ref"]
    public_result_path = outputs["public_result_ref"]
    capture_root.mkdir(parents=True, exist_ok=True)
    analysis_successor_bindings = (
        {
            "predecessor_analysis_checkpoint": {
                "ref": _relative(paths["analysis_checkpoint"]),
                "sha256": _sha(paths["analysis_checkpoint"]),
                "checkpoint_digest": analysis_checkpoint["checkpoint_digest"],
                "source_run_id": analysis_checkpoint["run_id"],
                "partial_draft_character_count": analysis_checkpoint[
                    "partial_draft_character_count"
                ],
                "partial_draft_business_promoted": False,
            },
            "analysis_successor_zero_call_proof": {
                "ref": _relative(paths["analysis_successor_zero_call_proof"]),
                "sha256": _sha(paths["analysis_successor_zero_call_proof"]),
                "result_digest": analysis_successor_zero["result_digest"],
            },
        }
        if analysis_successor
        and analysis_checkpoint is not None
        and analysis_successor_zero is not None
        else {}
    )
    submission_successor_bindings = (
        {
            "predecessor_analysis_completion_checkpoint": {
                "ref": _relative(paths["analysis_completion_checkpoint"]),
                "sha256": _sha(paths["analysis_completion_checkpoint"]),
                "checkpoint_digest": analysis_completion_checkpoint[
                    "checkpoint_digest"
                ],
                "source_fragment_run_id": analysis_completion_checkpoint[
                    "source_fragment_run_id"
                ],
                "source_continuation_run_id": analysis_completion_checkpoint[
                    "source_continuation_run_id"
                ],
                "merged_analysis_draft_character_count": (
                    analysis_completion_checkpoint[
                        "merged_analysis_draft_character_count"
                    ]
                ),
                "analysis_draft_business_promoted": False,
            },
            "submission_successor_zero_call_proof": {
                "ref": _relative(
                    paths["submission_successor_zero_call_proof"]
                ),
                "sha256": _sha(
                    paths["submission_successor_zero_call_proof"]
                ),
                "result_digest": submission_successor_zero["result_digest"],
            },
        }
        if submission_successor
        and analysis_completion_checkpoint is not None
        and submission_successor_zero is not None
        else {}
    )
    lead_checkpoint_successor_bindings = (
        {
            "predecessor_lead_plan_checkpoint": {
                "ref": _relative(paths["lead_plan_checkpoint"]),
                "sha256": _sha(paths["lead_plan_checkpoint"]),
                "checkpoint_digest": lead_plan_checkpoint[
                    "checkpoint_digest"
                ],
                "source_run_id": lead_plan_checkpoint["source_run_id"],
                "lead_plan_digest": lead_plan_checkpoint["lead_plan"][
                    "lead_plan_digest"
                ],
                "source_run_status_preserved_as_failure": True,
            },
            "lead_checkpoint_successor_zero_call_proof": {
                "ref": _relative(
                    paths["lead_checkpoint_successor_zero_call_proof"]
                ),
                "sha256": _sha(
                    paths["lead_checkpoint_successor_zero_call_proof"]
                ),
                "result_digest": lead_checkpoint_successor_zero[
                    "result_digest"
                ],
            },
        }
        if lead_checkpoint_successor
        and lead_plan_checkpoint is not None
        and lead_checkpoint_successor_zero is not None
        else {}
    )
    workpaper_checkpoint_successor_bindings = (
        {
            "predecessor_workpaper_checkpoint": {
                "ref": _relative(paths["workpaper_checkpoint"]),
                "sha256": _sha(paths["workpaper_checkpoint"]),
                "checkpoint_digest": workpaper_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "source_run_id": workpaper_checkpoint_raw["source_run_id"],
                "reused_workpaper_count": 5,
                "pending_agent_ids": list(
                    workpaper_checkpoint_raw["pending_agent_ids"]
                ),
                "source_run_status_preserved_as_failure": True,
            },
            "workpaper_checkpoint_successor_zero_call_proof": {
                "ref": _relative(
                    paths[
                        "workpaper_checkpoint_successor_zero_call_proof"
                    ]
                ),
                "sha256": _sha(
                    paths[
                        "workpaper_checkpoint_successor_zero_call_proof"
                    ]
                ),
                "result_digest": workpaper_checkpoint_successor_zero[
                    "result_digest"
                ],
            },
        }
        if workpaper_checkpoint_successor
        and workpaper_checkpoint_raw is not None
        and workpaper_checkpoint_successor_zero is not None
        else {}
    )
    specialist_analysis_successor_bindings = (
        {
            "predecessor_lead_plan_checkpoint": {
                "ref": _relative(paths["lead_plan_checkpoint"]),
                "sha256": _sha(paths["lead_plan_checkpoint"]),
                "checkpoint_digest": lead_plan_checkpoint[
                    "checkpoint_digest"
                ],
                "lead_plan_digest": lead_plan_checkpoint["lead_plan"][
                    "lead_plan_digest"
                ],
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_workpaper_checkpoint": {
                "ref": _relative(paths["workpaper_checkpoint"]),
                "sha256": _sha(paths["workpaper_checkpoint"]),
                "checkpoint_digest": workpaper_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "reused_workpaper_count": 5,
                "pending_agent_ids": list(
                    workpaper_checkpoint_raw["pending_agent_ids"]
                ),
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_specialist_analysis_checkpoint": {
                "ref": _relative(paths["specialist_analysis_checkpoint"]),
                "sha256": _sha(paths["specialist_analysis_checkpoint"]),
                "checkpoint_digest": analysis_checkpoint[
                    "checkpoint_digest"
                ],
                "source_run_id": analysis_checkpoint["run_id"],
                "node_id": analysis_checkpoint["node_id"],
                "partial_draft_character_count": analysis_checkpoint[
                    "partial_draft_character_count"
                ],
                "partial_draft_business_promoted": False,
                "original_analysis_conversation_replayed": True,
            },
            "specialist_analysis_successor_zero_call_proof": {
                "ref": _relative(
                    paths[
                        "specialist_analysis_successor_zero_call_proof"
                    ]
                ),
                "sha256": _sha(
                    paths[
                        "specialist_analysis_successor_zero_call_proof"
                    ]
                ),
                "result_digest": specialist_analysis_successor_zero[
                    "result_digest"
                ],
            },
        }
        if specialist_analysis_successor
        and lead_plan_checkpoint is not None
        and workpaper_checkpoint_raw is not None
        and analysis_checkpoint is not None
        and specialist_analysis_successor_zero is not None
        else {}
    )
    coordination_checkpoint_successor_bindings = (
        {
            "predecessor_lead_plan_checkpoint": {
                "ref": _relative(paths["lead_plan_checkpoint"]),
                "sha256": _sha(paths["lead_plan_checkpoint"]),
                "checkpoint_digest": lead_plan_checkpoint[
                    "checkpoint_digest"
                ],
                "lead_plan_digest": lead_plan_checkpoint["lead_plan"][
                    "lead_plan_digest"
                ],
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_workpaper_checkpoint": {
                "ref": _relative(paths["workpaper_checkpoint"]),
                "sha256": _sha(paths["workpaper_checkpoint"]),
                "checkpoint_digest": workpaper_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "reused_workpaper_count": 5,
                "pending_agent_ids": list(
                    workpaper_checkpoint_raw["pending_agent_ids"]
                ),
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_lead_coordination_checkpoint": {
                "ref": _relative(paths["lead_coordination_checkpoint"]),
                "sha256": _sha(paths["lead_coordination_checkpoint"]),
                "checkpoint_digest": coordination_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "source_run_id": coordination_checkpoint_raw[
                    "source_run_id"
                ],
                "reused_workpaper_count": 6,
                "reused_lead_coordination_count": 1,
                "source_run_status_preserved_as_failure": True,
            },
            "coordination_checkpoint_successor_zero_call_proof": {
                "ref": _relative(
                    paths["coordination_checkpoint_successor_zero_call_proof"]
                ),
                "sha256": _sha(
                    paths["coordination_checkpoint_successor_zero_call_proof"]
                ),
                "result_digest": coordination_checkpoint_successor_zero[
                    "result_digest"
                ],
            },
        }
        if coordination_checkpoint_successor
        and lead_plan_checkpoint is not None
        and workpaper_checkpoint_raw is not None
        and coordination_checkpoint_raw is not None
        and coordination_checkpoint_successor_zero is not None
        else {}
    )
    legacy_downstream_analysis_successor_bindings = (
        {
            "predecessor_lead_plan_checkpoint": {
                "ref": _relative(paths["lead_plan_checkpoint"]),
                "sha256": _sha(paths["lead_plan_checkpoint"]),
                "checkpoint_digest": lead_plan_checkpoint[
                    "checkpoint_digest"
                ],
                "lead_plan_digest": lead_plan_checkpoint["lead_plan"][
                    "lead_plan_digest"
                ],
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_workpaper_checkpoint": {
                "ref": _relative(paths["workpaper_checkpoint"]),
                "sha256": _sha(paths["workpaper_checkpoint"]),
                "checkpoint_digest": workpaper_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "reused_workpaper_count": 5,
                "pending_agent_ids": list(
                    workpaper_checkpoint_raw["pending_agent_ids"]
                ),
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_lead_coordination_checkpoint": {
                "ref": _relative(paths["lead_coordination_checkpoint"]),
                "sha256": _sha(paths["lead_coordination_checkpoint"]),
                "checkpoint_digest": coordination_checkpoint_raw[
                    "checkpoint_digest"
                ],
                "source_run_id": coordination_checkpoint_raw[
                    "source_run_id"
                ],
                "reused_workpaper_count": 6,
                "reused_lead_coordination_count": 1,
                "source_run_status_preserved_as_failure": True,
            },
            "predecessor_downstream_repair_progress_checkpoint": {
                "ref": _relative(
                    paths["downstream_repair_progress_checkpoint"]
                ),
                "sha256": _sha(
                    paths["downstream_repair_progress_checkpoint"]
                ),
                "checkpoint_digest": downstream_progress_checkpoint[
                    "checkpoint_digest"
                ],
                "source_run_id": downstream_progress_checkpoint[
                    "source_run_id"
                ],
                "reused_completed_challenge_repair_count": len(
                    downstream_progress_checkpoint[
                        "completed_challenge_repairs"
                    ]
                ),
                "pending_challenge_repair_count": len(
                    downstream_progress_checkpoint["pending_challenge_ids"]
                ),
            },
            "predecessor_downstream_analysis_checkpoint": {
                "ref": _relative(
                    paths["downstream_analysis_fragment_checkpoint"]
                ),
                "sha256": _sha(
                    paths["downstream_analysis_fragment_checkpoint"]
                ),
                "checkpoint_digest": downstream_analysis_checkpoint[
                    "checkpoint_digest"
                ],
                "node_id": downstream_analysis_checkpoint["node_id"],
                "partial_draft_character_count": (
                    downstream_analysis_checkpoint[
                        "partial_draft_character_count"
                    ]
                ),
                "partial_draft_business_promoted": False,
                "original_analysis_conversation_replayed": True,
            },
            "downstream_analysis_successor_zero_call_proof": {
                "ref": _relative(
                    paths["downstream_analysis_successor_zero_call_proof"]
                ),
                "sha256": _sha(
                    paths["downstream_analysis_successor_zero_call_proof"]
                ),
                "result_digest": downstream_analysis_successor_zero[
                    "result_digest"
                ],
            },
            **(
                {
                    "preprovider_replacement": {
                        "failed_authority_ref": _relative(
                            paths["failed_preprovider_authority"]
                        ),
                        "failed_authority_sha256": _sha(
                            paths["failed_preprovider_authority"]
                        ),
                        "failed_public_result_ref": _relative(
                            paths["failed_preprovider_result"]
                        ),
                        "failed_public_result_sha256": _sha(
                            paths["failed_preprovider_result"]
                        ),
                        "disposition_ref": _relative(
                            paths[
                                "preprovider_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "disposition_sha256": _sha(
                            paths[
                                "preprovider_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "failed_provider_attempt_count": 0,
                        "failed_authority_reused": False,
                    }
                }
                if preprovider_replacement
                else {}
            ),
            **(
                {
                    "continuation_profile_replacement": {
                        "failed_authority_ref": _relative(
                            paths["failed_continuation_authority"]
                        ),
                        "failed_authority_sha256": _sha(
                            paths["failed_continuation_authority"]
                        ),
                        "failed_public_result_ref": _relative(
                            paths["failed_continuation_result"]
                        ),
                        "failed_public_result_sha256": _sha(
                            paths["failed_continuation_result"]
                        ),
                        "disposition_ref": _relative(
                            paths[
                                "continuation_profile_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "disposition_sha256": _sha(
                            paths[
                                "continuation_profile_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "replacement_profile_ref": _relative(
                            paths["analysis_completion_profile"]
                        ),
                        "replacement_profile_sha256": _sha(
                            paths["analysis_completion_profile"]
                        ),
                        "failed_provider_attempt_count": 1,
                        "failed_authority_reused": False,
                    }
                }
                if continuation_profile_replacement
                else {}
            ),
            **(
                {
                    "repair_context_replacement": {
                        "failed_authority_ref": _relative(
                            paths["failed_repair_authority"]
                        ),
                        "failed_authority_sha256": _sha(
                            paths["failed_repair_authority"]
                        ),
                        "failed_public_result_ref": _relative(
                            paths["failed_repair_result"]
                        ),
                        "failed_public_result_sha256": _sha(
                            paths["failed_repair_result"]
                        ),
                        "disposition_ref": _relative(
                            paths[
                                "repair_context_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "disposition_sha256": _sha(
                            paths[
                                "repair_context_failure_disposition_zero_call_proof"
                            ]
                        ),
                        "active_progress_checkpoint_ref": _relative(
                            paths["downstream_repair_progress_checkpoint_v2"]
                        ),
                        "active_progress_checkpoint_sha256": _sha(
                            paths["downstream_repair_progress_checkpoint_v2"]
                        ),
                        "active_progress_checkpoint_digest": (
                            downstream_progress_checkpoint_v2[
                                "checkpoint_digest"
                            ]
                        ),
                        "replacement_profile_ref": _relative(
                            paths["repair_analysis_profile"]
                        ),
                        "replacement_profile_sha256": _sha(
                            paths["repair_analysis_profile"]
                        ),
                        "reused_completed_repair_count": len(
                            completed_downstream_repairs
                        ),
                        "maximum_analysis_continuation_calls": 0,
                        "failed_provider_attempt_count": 1,
                        "failed_authority_reused": False,
                    }
                }
                if repair_context_replacement
                and downstream_progress_checkpoint_v2 is not None
                else {}
            ),
        }
        if downstream_analysis_successor
        and lead_plan_checkpoint is not None
        and workpaper_checkpoint_raw is not None
        and coordination_checkpoint_raw is not None
        and downstream_progress_checkpoint is not None
        and downstream_analysis_checkpoint is not None
        and downstream_analysis_successor_zero is not None
        else {}
    )
    generic_successor_bindings = (
        _compile_generic_successor_bindings(
            paths=paths,
            lead_plan_checkpoint=lead_plan_checkpoint,
            workpaper_checkpoint=workpaper_checkpoint_raw,
            coordination_checkpoint=coordination_checkpoint_raw,
            active_progress_checkpoint=active_downstream_progress_checkpoint,
            completed_repairs=completed_downstream_repairs,
            hierarchical_proof_binding=hierarchical_evaluator_proof_binding,
            role_evaluation_checkpoint=role_evaluation_checkpoint_raw,
        )
        if generic_successor
        and lead_plan_checkpoint is not None
        and workpaper_checkpoint_raw is not None
        and coordination_checkpoint_raw is not None
        and active_downstream_progress_checkpoint is not None
        else {}
    )
    downstream_analysis_successor_bindings = (
        generic_successor_bindings
        if generic_successor
        else legacy_downstream_analysis_successor_bindings
    )

    sessions: dict[str, PreviewAgentSessionState] = {}
    node_records: list[dict[str, Any]] = []
    node_index = 0
    counter_repairs = len(completed_downstream_repairs)
    new_counter_repairs = 0
    evaluator_repairs = 0
    evaluator_role_audits = 0
    evaluator_role_audit_reuses = 0
    evaluator_role_reaudits = 0
    evaluator_cross_role_audits = 0

    def state(agent_id: str) -> PreviewAgentSessionState:
        if agent_id not in sessions:
            sessions[agent_id] = start_preview_agent_session(
                agent_id=agent_id,
                run_id=run_id,
                objective_ref=f"objective://{_sha(paths['objective'])}",
                active_plan_ref="plan://pending-specialist-opinions",
            )
        return sessions[agent_id]

    def execute_node(
        *,
        agent_id: str,
        node_suffix: str,
        messages: Sequence[Mapping[str, Any]],
        tool: Mapping[str, Any],
        validator: Any,
        purpose: str,
        required_outputs: Sequence[str],
        risk: str,
        analysis_tokens: int,
        submission_tokens: int,
        resume_bound_analysis: bool = False,
        resume_completed_analysis: bool = False,
        analysis_resume_checkpoint: Mapping[str, Any] | None = None,
        analysis_resume_draft: str | None = None,
        analysis_resume_original_messages: (
            Sequence[Mapping[str, Any]] | None
        ) = None,
        analysis_profile_override: Any | None = None,
    ) -> dict[str, Any]:
        nonlocal node_index
        node_index += 1
        if node_index > authority["execution_limits"]["maximum_new_model_nodes"]:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_model_node_budget_exceeded"
            )
        explicit_analysis_resume = analysis_resume_checkpoint is not None
        if (
            resume_bound_analysis and explicit_analysis_resume
        ) or (
            resume_completed_analysis
            and (resume_bound_analysis or explicit_analysis_resume)
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_two_resume_modes_forbidden"
            )
        if not explicit_analysis_resume and (
            analysis_resume_draft is not None
            or analysis_resume_original_messages is not None
        ):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_unbound_analysis_resume_inputs"
            )
        selected_analysis_checkpoint = (
            analysis_resume_checkpoint
            if explicit_analysis_resume
            else (analysis_checkpoint if resume_bound_analysis else None)
        )
        selected_analysis_draft = (
            analysis_resume_draft
            if explicit_analysis_resume
            else (
                analysis_checkpoint_draft
                if resume_bound_analysis
                else None
            )
        )
        selected_analysis_original_messages = (
            analysis_resume_original_messages
            if explicit_analysis_resume
            else (
                analysis_checkpoint_original_messages
                if resume_bound_analysis
                else None
            )
        )
        common = {
            "submission_profile": submission_profile,
            "session_state": state(agent_id),
            "tool": tool,
            "validator": validator,
            "capture_root": capture_root,
            "run_id": run_id,
            "node_id": f"{agent_id}::{node_suffix}",
            "purpose": purpose,
            "required_outputs": required_outputs,
            "schema_burden": (
                "one strict nested financial research tool contract"
            ),
            "materiality_quality_risk": risk,
            "comparable_run_evidence": (
                "DELL dynamic five-cell R7 content assessment",
                "DELL multi-agent zero-call preview v1.2",
                "DELL hierarchical Demand audit high-reasoning length failure 2026-08-21",
            ),
            "submission_output_token_ceiling": submission_tokens,
            "maximum_submission_successor_attempts": (
                authority["execution_limits"][
                    "maximum_submission_attempts_per_node"
                ]
                - 1
            ),
        }
        if resume_completed_analysis:
            if (
                analysis_completion_checkpoint is None
                or completed_analysis_draft is None
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_completed_analysis_inputs_missing"
                )
            execution = execute_checkpointed_preview_submission(
                **common,
                completed_analysis_checkpoint=analysis_completion_checkpoint,
                merged_analysis_draft=completed_analysis_draft,
            )
        else:
            execution = execute_analyzed_preview_node(
                **common,
                analysis_profile=(
                    analysis_profile_override or analysis_profile
                ),
                messages=messages,
                input_reference_count=_input_ref_count(messages),
                analysis_output_token_ceiling=analysis_tokens,
                analysis_checkpoint=selected_analysis_checkpoint,
                analysis_checkpoint_draft=selected_analysis_draft,
                analysis_continuation_profile=(
                    continuation_profile
                    if selected_analysis_checkpoint is not None
                    else None
                ),
                analysis_checkpoint_original_messages=(
                    selected_analysis_original_messages
                ),
            )
        record = execution.as_dict()
        node_records.append(record)
        _write_new(
            private_root / f"node_{node_index:02d}_{node_suffix}.json", record
        )
        return deepcopy(dict(execution.validated_payload))

    try:
        opinions = [
            deepcopy(dict(row))
            for row in plan_checkpoint["specialist_plans"]
        ]
        opinions_by_agent = {
            str(row["agent_id"]): row for row in opinions
        }
        if set(opinions_by_agent) != set(SPECIALIST_AGENT_IDS):
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_checkpoint_specialist_set_invalid"
            )
        checkpoint_ref = (
            "checkpoint://" + str(plan_checkpoint["checkpoint_digest"])
        )
        for agent_id in SPECIALIST_AGENT_IDS:
            state(agent_id).append(
                event_type="plan_bound",
                actor_id="HARNESS::R3_PLAN_CHECKPOINT",
                input_refs=(
                    checkpoint_ref,
                    "predecessor-run://" + str(
                        plan_checkpoint["predecessor_run_id"]
                    ),
                ),
                output_refs=(
                    "plan-opinion://"
                    + str(opinions_by_agent[agent_id]["plan_opinion_digest"]),
                ),
            )

        if (
            lead_checkpoint_successor
            or workpaper_checkpoint_successor
            or specialist_analysis_successor
            or coordination_resume
        ):
            if lead_plan_checkpoint is None:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_lead_plan_checkpoint_missing"
                )
            lead = deepcopy(dict(lead_plan_checkpoint["lead_plan"]))
            state(RESEARCH_LEAD_AGENT_ID).append(
                event_type="plan_bound",
                actor_id="HARNESS::R6_LEAD_PLAN_CHECKPOINT",
                input_refs=(
                    "checkpoint://" + lead_plan_checkpoint["checkpoint_digest"],
                    "predecessor-run://" + lead_plan_checkpoint["source_run_id"],
                ),
                output_refs=("plan://" + lead["lead_plan_digest"],),
            )
        else:
            lead_messages = compile_lead_plan_messages(
                topology=topology,
                objective=objective_payload,
                opinions=opinions,
            )
            lead = execute_node(
                agent_id=RESEARCH_LEAD_AGENT_ID,
                node_suffix="LEAD_PLAN",
                messages=lead_messages,
                tool=lead_plan_tool(topology=topology),
                validator=lambda payload: validate_lead_plan(
                    payload, opinions=opinions, topology=topology
                ),
                purpose="汇总六个独立角色意见，覆盖全部研究面并冻结协调问题和终止条件。",
                required_outputs=(
                    "accepted_agent_ids",
                    "accepted_facets",
                    "coordination_questions",
                    "expected_information_boundaries",
                    "stop_conditions",
                ),
                risk="dropping a role or Evidence Slot would create a structurally incomplete preview",
                analysis_tokens=(
                    0
                    if submission_successor
                    else (4000 if analysis_successor else 12000)
                ),
                submission_tokens=4000,
                resume_bound_analysis=analysis_successor,
                resume_completed_analysis=submission_successor,
            )
        plan_ref = f"plan://{lead['lead_plan_digest']}"
        for session_state in sessions.values():
            rebind_preview_session_plan(session_state, active_plan_ref=plan_ref)

        materialization = compile_multi_agent_preview_materialization(
            repo_root=ROOT,
            topology=topology,
            objective_payload=objective_payload,
            opinions=opinions,
            lead_plan=lead,
        )
        readiness = materialization.readiness_summary()
        if readiness["blocking_empty_role_ids"]:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_role_authority_empty_after_materialization"
            )
        contexts = materialization.context_by_agent()
        evaluation_contexts = {
            agent_id: deepcopy(dict(context))
            for agent_id, context in contexts.items()
        }

        workpaper_checkpoint = (
            validate_specialist_workpaper_checkpoint(
                workpaper_checkpoint_raw,
                terminal_failure=workpaper_terminal_failure,
                contexts=contexts,
            )
            if (
                workpaper_checkpoint_successor
                or specialist_analysis_successor
                or coordination_resume
            )
            and workpaper_checkpoint_raw is not None
            and workpaper_terminal_failure is not None
            else None
        )
        workpapers_by_agent: dict[str, dict[str, Any]] = (
            {
                str(row["agent_id"]): deepcopy(dict(row))
                for row in workpaper_checkpoint["revalidated_workpapers"]
            }
            if workpaper_checkpoint is not None
            else {}
        )
        validated_coordination_checkpoint: dict[str, Any] | None = None
        coordination: dict[str, Any] | None = None
        if coordination_resume:
            if (
                workpaper_checkpoint is None
                or coordination_checkpoint_raw is None
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_coordination_checkpoint_missing"
                )
            counter_workpaper = _load_bound_counter_workpaper(
                coordination_checkpoint_raw
            )
            six_workpapers = [
                *[
                    workpapers_by_agent[agent_id]
                    for agent_id in SPECIALIST_AGENT_IDS[:5]
                ],
                counter_workpaper,
            ]
            coordination_challenge_catalog = compile_challenge_catalog(
                workpapers=six_workpapers
            )
            captured_coordination = _load_bound_lead_coordination_decision(
                coordination_checkpoint_raw
            )
            validated_coordination_checkpoint = (
                validate_lead_coordination_checkpoint(
                    coordination_checkpoint_raw,
                    workpapers=six_workpapers,
                    contexts=contexts,
                    challenge_catalog=coordination_challenge_catalog,
                    coordination_decision=captured_coordination,
                )
            )
            workpapers_by_agent = {
                str(row["agent_id"]): deepcopy(dict(row))
                for row in validated_coordination_checkpoint[
                    "revalidated_workpapers"
                ]
            }
            coordination = deepcopy(
                dict(
                    validated_coordination_checkpoint[
                        "coordination_decision"
                    ]
                )
            )
        if workpaper_checkpoint is not None:
            for agent_id, workpaper in workpapers_by_agent.items():
                _bind_reused_workpaper_checkpoint(
                    state=state(agent_id),
                    context=contexts[agent_id],
                    prior_workpaper=workpaper,
                    source_checkpoint_digest=(
                        validated_coordination_checkpoint["checkpoint_digest"]
                        if validated_coordination_checkpoint is not None
                        else workpaper_checkpoint["checkpoint_digest"]
                    ),
                    objective_digest=canonical_digest(objective_payload),
                    plan_digest=lead["lead_plan_digest"],
                    checkpoint_suffix=(
                        "R9-COORDINATION"
                        if coordination_resume
                        else "R7-WORKPAPER"
                    ),
                    actor_id=(
                        "HARNESS::R10_COORDINATION_CHECKPOINT"
                        if coordination_resume
                        else "HARNESS::R7_WORKPAPER_CHECKPOINT"
                    ),
                )
        workpaper_agents_to_execute = (
            []
            if coordination_resume
            else (
                list(workpaper_checkpoint["pending_agent_ids"])
                if workpaper_checkpoint is not None
                else list(lead["ordered_agent_ids"])
            )
        )
        if (
            workpaper_checkpoint_successor or specialist_analysis_successor
        ) and workpaper_agents_to_execute != [SPECIALIST_AGENT_IDS[5]]:
            raise MultiAgentPreviewLiveError(
                "multi_agent_preview_workpaper_checkpoint_pending_set_invalid"
            )
        for agent_id in workpaper_agents_to_execute:
            context = contexts[agent_id]
            messages = compile_specialist_workpaper_messages(context=context)
            workpapers_by_agent[agent_id] = execute_node(
                agent_id=agent_id,
                node_suffix="WORKPAPER_R1",
                messages=messages,
                tool=specialist_workpaper_tool(
                    agent_id=agent_id, context=context
                ),
                validator=lambda payload, current=agent_id, current_context=context: validate_specialist_workpaper(
                    payload,
                    context=current_context,
                    expected_agent_id=current,
                ),
                purpose="使用本角色已审证据、数字事实和关系上下文形成完整金融研究底稿。",
                required_outputs=(
                    "thesis",
                    "confidence",
                    "sourced_claims",
                    "mechanism",
                    "alternative_explanations",
                    "strongest_counterarguments",
                    "remaining_gap_refs",
                    "what_would_change",
                    "cross_role_challenges",
                    "stop_reason",
                ),
                risk="false absence, causal overreach or cross-company attribution is material L1/L2 risk",
                analysis_tokens=(
                    4000 if specialist_analysis_successor else 16000
                ),
                submission_tokens=8000,
                resume_bound_analysis=specialist_analysis_successor,
            )

        initial_workpapers = [
            workpapers_by_agent[agent_id] for agent_id in lead["ordered_agent_ids"]
        ]
        challenge_catalog = compile_challenge_catalog(
            workpapers=initial_workpapers
        )
        if coordination_resume:
            if (
                validated_coordination_checkpoint is None
                or coordination is None
                or challenge_catalog
                != validated_coordination_checkpoint["challenge_catalog"]
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_coordination_checkpoint_runtime_drift"
                )
            _bind_reused_lead_coordination_checkpoint(
                state=state(RESEARCH_LEAD_AGENT_ID),
                checkpoint=validated_coordination_checkpoint,
                objective_digest=canonical_digest(objective_payload),
                plan_digest=lead["lead_plan_digest"],
            )
        else:
            coordination = execute_node(
                agent_id=RESEARCH_LEAD_AGENT_ID,
                node_suffix="COORDINATION_R1",
                messages=compile_lead_coordination_messages(
                    workpapers=initial_workpapers,
                    challenge_catalog=challenge_catalog,
                ),
                tool=lead_coordination_tool(
                    challenge_catalog=challenge_catalog
                ),
                validator=lambda payload: validate_lead_coordination_decision(
                    payload, challenge_catalog=challenge_catalog
                ),
                purpose="审查跨角色挑战并把可局部修正问题路由回原角色，把数据或 Harness 缺陷留在原责任层。",
                required_outputs=(
                    "accepted_challenge_ids",
                    "deferred_challenge_ids",
                    "coordination_rationale",
                    "next_state",
                ),
                risk="misrouting a data defect to an agent would create false conclusions and hide the root cause",
                analysis_tokens=16000,
                submission_tokens=4500,
            )

        challenge_by_id = {
            str(row["challenge_id"]): row for row in challenge_catalog
        }
        accepted_challenges = [
            challenge_by_id[challenge_id]
            for challenge_id in coordination["accepted_challenge_ids"]
        ]
        if downstream_analysis_successor:
            if active_downstream_progress_checkpoint is None:
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_downstream_progress_runtime_missing"
                )
            _validate_downstream_progress_runtime_alignment(
                active_progress_checkpoint=(
                    active_downstream_progress_checkpoint
                ),
                coordination=coordination,
                completed_repairs=completed_downstream_repairs,
            )
        for challenge in accepted_challenges:
            challenge_id = str(challenge["challenge_id"])
            target = str(challenge["target_agent_id"])
            prior = workpapers_by_agent[target]
            if challenge_id in completed_downstream_repairs:
                source_context = completed_downstream_repair_contexts.get(
                    challenge_id
                )
                if source_context is None:
                    raise MultiAgentPreviewLiveError(
                        "multi_agent_preview_completed_repair_context_missing"
                    )
                completed_repair = revalidate_bound_specialist_workpaper(
                    completed_downstream_repairs[challenge_id],
                    context=source_context,
                    expected_agent_id=target,
                )
                workpapers_by_agent[target] = completed_repair
                evaluation_contexts[target] = deepcopy(dict(source_context))
                _bind_reused_workpaper_checkpoint(
                    state=state(target),
                    context=source_context,
                    prior_workpaper=completed_repair,
                    source_checkpoint_digest=(
                        active_downstream_progress_checkpoint[
                            "checkpoint_digest"
                        ]
                    ),
                    objective_digest=canonical_digest(objective_payload),
                    plan_digest=lead["lead_plan_digest"],
                    checkpoint_suffix="R10-COMPLETED-REPAIR",
                    actor_id="HARNESS::R10_COMPLETED_REPAIR_CHECKPOINT",
                )
                continue
            receipt = compile_cross_role_feedback_receipt(
                target_session_id=state(target).session["session_id"],
                challenge=challenge,
            )
            _checkpoint_and_resume_for_feedback(
                state=state(target),
                context=contexts[target],
                prior_workpaper=prior,
                feedback_receipts=[receipt],
                objective_digest=canonical_digest(objective_payload),
                plan_digest=lead["lead_plan_digest"],
            )
            repaired_context = compile_specialist_context(
                topology=topology,
                agent_id=target,
                research_input=materialization.research_input,
                tool_execution_input=materialization.dynamic_research_input,
                case_truth_packet=materialization.case_truth_packet,
                plan_opinion=next(row for row in opinions if row["agent_id"] == target),
                lead_plan=lead,
                feedback_receipts=[receipt],
                prior_workpaper=prior,
                context_scope="role_repair",
            )
            resume_active_fragment = (
                not role_scoped_repair_successor
                and downstream_analysis_successor
                and downstream_analysis_checkpoint is not None
                and downstream_progress_checkpoint is not None
                and challenge_id
                == downstream_progress_checkpoint["pending_challenge_ids"][0]
            )
            workpapers_by_agent[target] = execute_node(
                agent_id=target,
                node_suffix="COUNTER_REPAIR",
                messages=compile_specialist_workpaper_messages(
                    context=repaired_context
                ),
                tool=specialist_workpaper_tool(
                    agent_id=target, context=repaired_context
                ),
                validator=lambda payload, current=target, current_context=repaired_context: validate_specialist_workpaper(
                    payload,
                    context=current_context,
                    expected_agent_id=current,
                ),
                purpose="消费研究负责人的已接受反方反馈，只修正受影响判断并保留全部证据边界。",
                required_outputs=(
                    "revised_thesis",
                    "revised_sourced_claims",
                    "revised_counterarguments",
                    "revised_what_would_change",
                ),
                risk="repair must narrow or correct the judgment without inventing new authority",
                analysis_tokens=(4000 if resume_active_fragment else 12000),
                submission_tokens=8000,
                analysis_resume_checkpoint=(
                    downstream_analysis_checkpoint
                    if resume_active_fragment
                    else None
                ),
                analysis_resume_draft=(
                    downstream_analysis_checkpoint_draft
                    if resume_active_fragment
                    else None
                ),
                analysis_resume_original_messages=(
                    downstream_analysis_checkpoint_original_messages
                    if resume_active_fragment
                    else None
                ),
                analysis_profile_override=(
                    repair_analysis_profile
                    if role_scoped_repair_successor
                    else None
                ),
            )
            evaluation_contexts[target] = deepcopy(dict(repaired_context))
            counter_repairs += 1
            new_counter_repairs += 1
            if new_counter_repairs > authority["execution_limits"].get(
                "maximum_new_counter_challenge_repairs", 3
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_new_counter_repair_budget_exceeded"
                )

        evaluations: list[dict[str, Any]] = []
        def apply_evaluator_repairs(
            *, evaluation: Mapping[str, Any], evaluation_round: int
        ) -> list[str]:
            nonlocal evaluator_repairs
            unrepairable = [
                row
                for row in evaluation["findings"]
                if row["blocks_report"]
                and row["failure_owner"]
                in {"data_infrastructure_or_tool", "harness_control"}
            ]
            if unrepairable:
                return []
            by_target: dict[str, list[dict[str, Any]]] = {}
            maximum_targets = authority["execution_limits"][
                "maximum_evaluator_repairs"
            ]
            for finding in evaluation["findings"]:
                if not (
                    finding["blocks_report"]
                    and finding["failure_owner"]
                    in {
                        "agent_orchestration_and_role_design",
                        "model_judgment",
                    }
                ):
                    continue
                target = str(finding["target_agent_id"])
                if target not in by_target and len(by_target) >= maximum_targets:
                    continue
                by_target.setdefault(target, []).append(
                    _compile_evaluator_feedback_receipt(
                        target_session_id=state(target).session["session_id"],
                        finding=finding,
                    )
                )
            for target, receipts in by_target.items():
                prior = workpapers_by_agent[target]
                _checkpoint_and_resume_for_feedback(
                    state=state(target),
                    context=contexts[target],
                    prior_workpaper=prior,
                    feedback_receipts=receipts,
                    objective_digest=canonical_digest(objective_payload),
                    plan_digest=lead["lead_plan_digest"],
                )
                repaired_context = compile_specialist_context(
                    topology=topology,
                    agent_id=target,
                    research_input=materialization.research_input,
                    tool_execution_input=materialization.dynamic_research_input,
                    case_truth_packet=materialization.case_truth_packet,
                    plan_opinion=next(row for row in opinions if row["agent_id"] == target),
                    lead_plan=lead,
                    feedback_receipts=receipts,
                    prior_workpaper=prior,
                    context_scope="role_repair",
                )
                workpapers_by_agent[target] = execute_node(
                    agent_id=target,
                    node_suffix=f"EVALUATOR_REPAIR_R{evaluation_round}",
                    messages=compile_specialist_workpaper_messages(
                        context=repaired_context
                    ),
                    tool=specialist_workpaper_tool(
                        agent_id=target, context=repaired_context
                    ),
                    validator=lambda payload, current=target, current_context=repaired_context: validate_specialist_workpaper(
                        payload,
                        context=current_context,
                        expected_agent_id=current,
                    ),
                    purpose="消费独立评估反馈，局部修正事实、边界或角色冲突后重新提交底稿。",
                    required_outputs=(
                        "revised_thesis",
                        "revised_sourced_claims",
                        "revised_mechanism",
                        "revised_counterarguments",
                    ),
                    risk="evaluator repair must not hide an upstream data or Harness defect",
                    analysis_tokens=12000,
                    submission_tokens=8000,
                    analysis_profile_override=(
                        repair_analysis_profile
                        if role_scoped_repair_successor
                        else None
                    ),
                )
                evaluation_contexts[target] = deepcopy(dict(repaired_context))
                evaluator_repairs += 1
            return list(by_target)

        if hierarchical_evaluator:
            case_truth_model_view = compile_case_truth_model_view(
                materialization.case_truth_packet
            )
            current_workpapers = [
                workpapers_by_agent[agent_id]
                for agent_id in lead["ordered_agent_ids"]
            ]
            validated_role_evaluation_checkpoint = None
            if role_evaluation_checkpoint_raw is not None:
                if role_evaluation_checkpoint_terminal is None:
                    raise MultiAgentPreviewLiveError(
                        "multi_agent_preview_role_evaluation_checkpoint_"
                        "terminal_missing"
                    )
                predecessor_evaluation_checkpoint = None
                predecessor_evaluation_terminal = None
                validated_submission_replay = None
                if (
                    role_evaluation_checkpoint_raw.get("schema_version")
                    == ROLE_EVALUATION_PROGRESS_CHECKPOINT_CHAIN_SCHEMA_VERSION
                ):
                    predecessor_evaluation_checkpoint = _json(
                        _resolve(
                            str(
                                role_evaluation_checkpoint_raw[
                                    "predecessor_checkpoint_ref"
                                ]
                            )
                        )
                    )
                    predecessor_evaluation_terminal = _json(
                        _resolve(
                            str(
                                predecessor_evaluation_checkpoint[
                                    "source_terminal_result_ref"
                                ]
                            )
                        )
                    )
                    submission_replay_raw = _json(
                        _resolve(
                            str(
                                role_evaluation_checkpoint_raw[
                                    "submission_replay_ref"
                                ]
                            )
                        )
                    )
                    replay_agent_id = str(
                        submission_replay_raw["target_agent_id"]
                    )
                    replay_response_captures = [
                        _json(_resolve(str(row["response_capture_ref"])))
                        for row in submission_replay_raw[
                            "submission_attempts"
                        ]
                    ]
                    validated_submission_replay = (
                        validate_role_evaluation_submission_replay(
                            submission_replay_raw,
                            terminal_failure=(
                                role_evaluation_checkpoint_terminal
                            ),
                            workpaper=workpapers_by_agent[replay_agent_id],
                            context=evaluation_contexts[replay_agent_id],
                            response_captures=replay_response_captures,
                        )
                    )
                validated_role_evaluation_checkpoint = (
                    validate_role_evaluation_progress_checkpoint(
                        role_evaluation_checkpoint_raw,
                        terminal_failure=role_evaluation_checkpoint_terminal,
                        workpapers=[
                            workpapers_by_agent[agent_id]
                            for agent_id in SPECIALIST_AGENT_IDS
                        ],
                        contexts=evaluation_contexts,
                        predecessor_checkpoint=(
                            predecessor_evaluation_checkpoint
                        ),
                        predecessor_terminal_failure=(
                            predecessor_evaluation_terminal
                        ),
                        submission_replay=validated_submission_replay,
                    )
                )
                if not (
                    validated_role_evaluation_checkpoint[
                        "completed_agent_ids"
                    ]
                    == successor_frontier.get(
                        "completed_role_evaluation_agent_ids"
                    )
                    and validated_role_evaluation_checkpoint[
                        "checkpoint_digest"
                    ]
                    == successor_frontier.get(
                        "evaluation_progress_checkpoint_digest"
                    )
                ):
                    raise MultiAgentPreviewLiveError(
                        "multi_agent_preview_role_evaluation_checkpoint_"
                        "frontier_drift"
                    )
                evaluator_role_audit_reuses = int(
                    validated_role_evaluation_checkpoint[
                        "reused_role_evaluation_count"
                    ]
                )
            role_evaluations: dict[str, dict[str, Any]] = (
                {
                    str(agent_id): deepcopy(dict(evaluation))
                    for agent_id, evaluation in (
                        validated_role_evaluation_checkpoint[
                            "validated_role_evaluations"
                        ].items()
                    )
                }
                if validated_role_evaluation_checkpoint is not None
                else {}
            )
            for agent_id in lead["ordered_agent_ids"]:
                if agent_id in role_evaluations:
                    continue
                workpaper = workpapers_by_agent[agent_id]
                evaluator_agent_id = (
                    "EVAL::ROLE::" + agent_id.split("::")[-1]
                )
                rebind_preview_session_plan(
                    state(evaluator_agent_id), active_plan_ref=plan_ref
                )
                role_evaluations[agent_id] = execute_node(
                    agent_id=evaluator_agent_id,
                    node_suffix="CONTENT_AUDIT_R1",
                    messages=compile_role_evaluation_messages(
                        workpaper=workpaper,
                        case_truth_model_view=case_truth_model_view,
                        specialist_context=evaluation_contexts[agent_id],
                    ),
                    tool=evaluation_tool(
                        allowed_agent_ids=[agent_id],
                        allowed_refs=evaluation_allowed_refs([workpaper]),
                    ),
                    validator=lambda payload, current=workpaper: validate_role_evaluation(
                        payload, workpaper=current
                    ),
                    purpose="独立审查单一专业底稿的判断、经济机制、替代解释、最强反方和可观察改变条件，不代写研究。",
                    required_outputs=(
                        "role_findings",
                        "role_content_may_proceed",
                    ),
                    risk="a false role pass could preserve a material causal overreach; a false block could erase valid specialist gain",
                    analysis_tokens=(
                        ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING
                        if evaluator_analysis_profile is not None
                        else 12000
                    ),
                    submission_tokens=7000,
                    analysis_profile_override=(
                        evaluator_analysis_profile or repair_analysis_profile
                    ),
                )
                evaluator_role_audits += 1
            cross_evaluator_id = "EVAL::CROSS_ROLE"
            rebind_preview_session_plan(
                state(cross_evaluator_id), active_plan_ref=plan_ref
            )
            cross_role_evaluation = execute_node(
                agent_id=cross_evaluator_id,
                node_suffix="CONSISTENCY_AUDIT_R1",
                messages=compile_cross_role_evaluation_messages(
                    workpapers=current_workpapers,
                    role_evaluations=role_evaluations,
                ),
                tool=evaluation_tool(
                    allowed_agent_ids=lead["ordered_agent_ids"],
                    allowed_refs=evaluation_allowed_refs(
                        current_workpapers
                    ),
                ),
                validator=lambda payload, current=current_workpapers: validate_evaluation(
                    payload, workpapers=current
                ),
                purpose="在六份已完成角色审查的基础上，只检查跨角色矛盾、重复计算、口径冲突和综合边界。",
                required_outputs=(
                    "cross_role_findings",
                    "cross_role_conflicts",
                    "report_may_proceed",
                ),
                risk="a missed cross-role conflict could make individually plausible workpapers form a materially inconsistent report",
                analysis_tokens=(
                    CROSS_ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING
                    if evaluator_analysis_profile is not None
                    else 12000
                ),
                submission_tokens=7000,
                analysis_profile_override=(
                    evaluator_analysis_profile or repair_analysis_profile
                ),
            )
            evaluator_cross_role_audits += 1
            evaluation = merge_hierarchical_evaluations(
                workpapers=current_workpapers,
                role_evaluations=role_evaluations,
                cross_role_evaluation=cross_role_evaluation,
                local_findings=local_case_absence_findings(
                    workpapers=current_workpapers,
                    case_truth_model_view=case_truth_model_view,
                ),
            )
            evaluations.append(evaluation)
            if not evaluation["report_may_proceed"]:
                repaired_targets = apply_evaluator_repairs(
                    evaluation=evaluation, evaluation_round=1
                )
                if repaired_targets:
                    current_workpapers = [
                        workpapers_by_agent[agent_id]
                        for agent_id in lead["ordered_agent_ids"]
                    ]
                    for agent_id in repaired_targets:
                        workpaper = workpapers_by_agent[agent_id]
                        evaluator_agent_id = (
                            "EVAL::ROLE::" + agent_id.split("::")[-1]
                        )
                        role_evaluations[agent_id] = execute_node(
                            agent_id=evaluator_agent_id,
                            node_suffix="CONTENT_AUDIT_R2",
                            messages=compile_role_evaluation_messages(
                                workpaper=workpaper,
                                case_truth_model_view=case_truth_model_view,
                                specialist_context=evaluation_contexts[agent_id],
                            ),
                            tool=evaluation_tool(
                                allowed_agent_ids=[agent_id],
                                allowed_refs=evaluation_allowed_refs(
                                    [workpaper]
                                ),
                            ),
                            validator=lambda payload, current=workpaper: validate_role_evaluation(
                                payload, workpaper=current
                            ),
                            purpose="只复审消费 Evaluator finding 后发生变化的专业底稿，确认问题已收窄且没有新增越权事实。",
                            required_outputs=(
                                "revised_role_findings",
                                "revised_role_content_may_proceed",
                            ),
                            risk="an unaffected-role rerun or a permissive re-audit would hide whether targeted feedback actually improved the workpaper",
                            analysis_tokens=(
                                ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING
                                if evaluator_analysis_profile is not None
                                else 12000
                            ),
                            submission_tokens=7000,
                            analysis_profile_override=(
                                evaluator_analysis_profile
                                or repair_analysis_profile
                            ),
                        )
                        evaluator_role_reaudits += 1
                    current_workpapers = [
                        workpapers_by_agent[agent_id]
                        for agent_id in lead["ordered_agent_ids"]
                    ]
                    cross_role_evaluation = execute_node(
                        agent_id=cross_evaluator_id,
                        node_suffix="CONSISTENCY_AUDIT_R2",
                        messages=compile_cross_role_evaluation_messages(
                            workpapers=current_workpapers,
                            role_evaluations=role_evaluations,
                        ),
                        tool=evaluation_tool(
                            allowed_agent_ids=lead["ordered_agent_ids"],
                            allowed_refs=evaluation_allowed_refs(
                                current_workpapers
                            ),
                        ),
                        validator=lambda payload, current=current_workpapers: validate_evaluation(
                            payload, workpapers=current
                        ),
                        purpose="复核受影响角色修订后是否仍存在跨角色矛盾、重复计算、口径冲突或综合边界缺口。",
                        required_outputs=(
                            "rechecked_cross_role_findings",
                            "rechecked_cross_role_conflicts",
                            "report_may_proceed",
                        ),
                        risk="a false post-repair pass could publish an internally inconsistent synthesis",
                        analysis_tokens=(
                            CROSS_ROLE_EVALUATION_ANALYSIS_TOKEN_CEILING
                            if evaluator_analysis_profile is not None
                            else 12000
                        ),
                        submission_tokens=7000,
                        analysis_profile_override=(
                            evaluator_analysis_profile
                            or repair_analysis_profile
                        ),
                    )
                    evaluator_cross_role_audits += 1
                    evaluations.append(
                        merge_hierarchical_evaluations(
                            workpapers=current_workpapers,
                            role_evaluations=role_evaluations,
                            cross_role_evaluation=cross_role_evaluation,
                            local_findings=local_case_absence_findings(
                                workpapers=current_workpapers,
                                case_truth_model_view=case_truth_model_view,
                            ),
                        )
                    )
            if not (
                evaluator_role_audits
                <= authority["execution_limits"][
                    "maximum_initial_role_evaluation_nodes"
                ]
                and evaluator_role_audit_reuses
                == authority["execution_limits"].get(
                    "reused_role_evaluation_count", 0
                )
                and evaluator_role_audits + evaluator_role_audit_reuses
                == len(SPECIALIST_AGENT_IDS)
                and evaluator_role_reaudits
                <= authority["execution_limits"][
                    "maximum_affected_role_reevaluation_nodes"
                ]
                and evaluator_cross_role_audits
                <= authority["execution_limits"][
                    "maximum_cross_role_evaluation_nodes"
                ]
            ):
                raise MultiAgentPreviewLiveError(
                    "multi_agent_preview_hierarchical_evaluator_budget_exceeded"
                )
        else:
            evaluator_state = state("EVAL::L1_AND_CONTENT")
            rebind_preview_session_plan(
                evaluator_state, active_plan_ref=plan_ref
            )
            for evaluation_round in (1, 2):
                current_workpapers = [
                    workpapers_by_agent[agent_id]
                    for agent_id in lead["ordered_agent_ids"]
                ]
                model_evaluation = execute_node(
                    agent_id="EVAL::L1_AND_CONTENT",
                    node_suffix=f"EVALUATION_R{evaluation_round}",
                    messages=compile_evaluation_messages(
                        workpapers=current_workpapers,
                        case_truth_model_view=compile_case_truth_model_view(
                            materialization.case_truth_packet
                        ),
                        specialist_contexts=evaluation_contexts,
                    ),
                    tool=evaluation_tool(
                        allowed_refs=evaluation_allowed_refs(
                            current_workpapers
                        )
                    ),
                    validator=lambda payload, current=current_workpapers: validate_evaluation(
                        payload, workpapers=current
                    ),
                    purpose="独立检查事实、期间、引用、因果边界、角色冲突与最早责任层，不代写结论。",
                    required_outputs=(
                        "findings",
                        "cross_role_conflicts",
                        "report_may_proceed",
                    ),
                    risk="a false pass would publish materially wrong financial research; a false block would hide agent capability",
                    analysis_tokens=16000,
                    submission_tokens=7000,
                )
                local_findings = local_case_absence_findings(
                    workpapers=current_workpapers,
                    case_truth_model_view=compile_case_truth_model_view(
                        materialization.case_truth_packet
                    ),
                )
                evaluation = _merge_local_evaluation(
                    model_evaluation=model_evaluation,
                    local_findings=local_findings,
                    workpapers=current_workpapers,
                )
                evaluations.append(evaluation)
                if evaluation["report_may_proceed"] or evaluation_round == 2:
                    break
                if not apply_evaluator_repairs(
                    evaluation=evaluation,
                    evaluation_round=evaluation_round,
                ):
                    break

        final_evaluation = evaluations[-1]
        final_workpapers = [
            workpapers_by_agent[agent_id] for agent_id in lead["ordered_agent_ids"]
        ]
        report: dict[str, Any] | None = None
        if final_evaluation["report_may_proceed"]:
            writer_state = state(WRITER_AGENT_ID)
            rebind_preview_session_plan(writer_state, active_plan_ref=plan_ref)
            report = execute_node(
                agent_id=WRITER_AGENT_ID,
                node_suffix="REPORT_DRAFT",
                messages=compile_report_messages(
                    workpapers=final_workpapers,
                    evaluation=final_evaluation,
                ),
                tool=report_draft_tool(workpapers=final_workpapers),
                validator=lambda payload: validate_report_draft(
                    payload, workpapers=final_workpapers
                ),
                purpose="把已验收的多角色底稿编成可伸缩研报，不增加事实、数字、引用或因果关系。",
                required_outputs=(
                    "report_title",
                    "executive_thesis",
                    "sections",
                    "remaining_gaps",
                    "what_would_change",
                    "confidence_statement",
                ),
                risk="writer synthesis can reintroduce a false fact or erase material counterevidence",
                analysis_tokens=16000,
                submission_tokens=9000,
            )

        for agent_id in SPECIALIST_AGENT_IDS:
            _stop_role(
                state=state(agent_id),
                context=contexts[agent_id],
                evaluation=final_evaluation,
            )

        if generic_successor:
            completed_frontier_nodes = [
                row
                for row in successor_frontier["nodes"]
                if row["disposition"] in COMPLETED_DISPOSITIONS
            ]
            pending_frontier_nodes = [
                row
                for row in successor_frontier["nodes"]
                if row["disposition"] not in COMPLETED_DISPOSITIONS
            ]
            evaluator_boundary = (
                "Evaluation used deterministic full-case L1, six independent "
                "role-scoped content audits and one authority-light cross-role "
                "consistency audit; only affected roles could be repaired and "
                "re-audited. "
                if hierarchical_evaluator
                else (
                    "Evaluation used the historical claim-bound monolithic "
                    "Evaluator contract. "
                )
            )
            known_boundary_prefix = (
                "This is one provider-neutral compiled DELL Multi-Agent "
                "Preview successor over unchanged current local S1/S2 "
                "authority. Six specialist workpapers and the valid Lead "
                "challenge partition were reused from immutable checkpoints. "
                f"The compiled frontier reused {len(completed_frontier_nodes)} "
                "completed role repairs and authorized "
                f"{len(pending_frontier_nodes)} pending role repairs before "
                "evaluation. It did not rerun planning, initial workpapers, "
                "Lead coordination or any completed repair, and it permitted "
                "no analysis continuation. "
                + evaluator_boundary
            )
        elif repair_context_replacement:
            known_boundary_prefix = (
                "This is one DELL R15 role-scoped Supply-repair Multi-Agent "
                "Preview successor over unchanged current local S1/S2 "
                "authority. Six specialist workpapers, the valid R9 Lead "
                "challenge partition and the completed Demand and Cash "
                "repairs were revalidated from immutable captures. The new "
                "attempt began only at a fresh Supply repair with no analysis "
                "continuation and did not rerun planning, initial workpapers, "
                "Lead coordination, Demand or Cash. "
            )
        elif downstream_analysis_successor:
            known_boundary_prefix = (
                "This is one DELL R11-R10-downstream-repair-analysis-"
                "checkpoint Multi-Agent Preview successor over unchanged "
                "current local S1/S2 authority. Six specialist workpapers, "
                "the valid R9 Lead challenge partition and the completed "
                "R10 Demand repair were revalidated from immutable captures. "
                "The new attempt resumed the exact truncated Cash repair "
                "conversation once and did not rerun planning, initial "
                "workpapers, Lead coordination or the completed Demand repair. "
            )
        elif coordination_checkpoint_successor:
            known_boundary_prefix = (
                "This is one DELL R10-R9-Lead-coordination-checkpoint "
                "downstream-only Multi-Agent Preview successor over unchanged "
                "current local S1/S2 authority. Six specialist workpapers and "
                "the valid R9 Lead challenge partition were revalidated from "
                "immutable captures and reused without any planning, workpaper "
                "or Lead-coordination model rerun; the new attempt began only "
                "at the three accepted role-local repairs. "
            )
        elif specialist_analysis_successor:
            known_boundary_prefix = (
                "This is one DELL R8-Counterevidence-analysis-checkpoint "
                "downstream-only Multi-Agent Preview successor over unchanged "
                "current local S1/S2 authority. Five specialist workpapers and "
                "the truncated Counter analysis were revalidated from immutable "
                "captures; the exact original Counter conversation was resumed "
                "once without rerunning its initial analysis. "
            )
        elif workpaper_checkpoint_successor:
            known_boundary_prefix = (
                "This is one DELL R7-five-workpaper-checkpoint downstream-only "
                "Multi-Agent Preview successor over unchanged current local "
                "S1/S2 authority. Five specialist workpapers were revalidated "
                "from immutable captures and reused without a model rerun; the "
                "new attempt began only at Counterevidence. "
            )
        elif lead_checkpoint_successor:
            known_boundary_prefix = (
                "This is one DELL R6-validated-Lead-plan downstream-only "
                "Multi-Agent Preview successor over unchanged current local "
                "S1/S2 authority. Six specialist plans and the validated "
                "Research Lead plan were reused from immutable checkpoints; no "
                "new planning or Lead plan call was made. "
            )
        elif submission_successor:
            known_boundary_prefix = (
                "This is one DELL R5-completed-analysis strict-submission "
                "Multi-Agent Preview successor over unchanged current local "
                "S1/S2 authority. The R4 fragment and R5 continuation were "
                "reused from an immutable completion checkpoint with no new "
                "Research Lead analysis call. "
            )
        elif analysis_successor:
            known_boundary_prefix = (
                "This is one DELL R4-analysis-checkpoint feedback-and-"
                "continuation Multi-Agent Preview successor over unchanged "
                "current local S1/S2 authority. The incomplete Research Lead "
                "draft was preserved as non-business evidence and resumed once "
                "only for its missing outputs. "
            )
        else:
            known_boundary_prefix = (
                "This is one DELL R3-plan-checkpoint Multi-Agent Preview "
                "successor over unchanged current local S1/S2 authority. Six "
                "validated specialist plans were reused without paid reruns; "
                "all new nodes separated visible analysis from strict submission. "
            )

        full_body = {
            "schema_version": full_schema,
            "status": (
                "multi_agent_preview_report_compiled_content_assessment_pending"
                if report is not None
                else "multi_agent_preview_completed_report_blocked_by_evaluation"
            ),
            "recorded_at": _now(),
            "authority_ref": _relative(authority_path),
            "authority_sha256": _sha(authority_path),
            "implementation_commit": authority["implementation_commit"],
            "case_key": "DELL",
            "research_as_of": "2026-08-06",
            "predecessor_plan_checkpoint": {
                "ref": _relative(paths["predecessor_plan_checkpoint"]),
                "sha256": _sha(paths["predecessor_plan_checkpoint"]),
                "checkpoint_digest": plan_checkpoint["checkpoint_digest"],
                "predecessor_run_id": plan_checkpoint["predecessor_run_id"],
                "reused_specialist_plan_count": 6,
            },
            "successor_zero_call_proof": {
                "ref": _relative(paths["successor_zero_call_proof"]),
                "sha256": _sha(paths["successor_zero_call_proof"]),
                "result_digest": successor_zero["result_digest"],
            },
            **analysis_successor_bindings,
            **submission_successor_bindings,
            **lead_checkpoint_successor_bindings,
            **workpaper_checkpoint_successor_bindings,
            **specialist_analysis_successor_bindings,
            **coordination_checkpoint_successor_bindings,
            **downstream_analysis_successor_bindings,
            "planning_overlay": {
                "ref": _relative(paths["planning_overlay"]),
                "sha256": _sha(paths["planning_overlay"]),
                "maximum_proposed_atoms": 20,
                "maximum_evidence_requests": 12,
            },
            "opinions": opinions,
            "lead_plan": lead,
            "materialization_readiness": readiness,
            "initial_workpapers": initial_workpapers,
            "challenge_catalog": challenge_catalog,
            "lead_coordination": coordination,
            "final_workpapers": final_workpapers,
            "evaluations": evaluations,
            "report": report,
            "node_executions": node_records,
            "sessions": {
                agent_id: session_state.as_dict()
                for agent_id, session_state in sessions.items()
            },
            "execution": {
                "new_model_nodes": node_index,
                "reused_specialist_plan_count": 6,
                "new_specialist_plan_model_calls": 0,
                "lead_plan_checkpoint_reuses": (
                    1
                    if lead_checkpoint_successor
                    or workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else 0
                ),
                "new_lead_plan_model_calls": (
                    0
                    if lead_checkpoint_successor
                    or workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else sum(
                        1
                        for row in node_records
                        if row["node_id"].endswith("::LEAD_PLAN")
                    )
                ),
                "reused_workpaper_count": (
                    6
                    if coordination_resume
                    else (
                        5
                        if workpaper_checkpoint_successor
                        or specialist_analysis_successor
                        else 0
                    )
                ),
                "reused_lead_coordination_count": (
                    1 if coordination_resume else 0
                ),
                "new_lead_coordination_model_calls": sum(
                    1
                    for row in node_records
                    if row["node_id"].endswith("::COORDINATION_R1")
                ),
                "new_initial_workpaper_nodes": sum(
                    1
                    for row in node_records
                    if row["node_id"].endswith("::WORKPAPER_R1")
                ),
                "analysis_calls": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                ),
                "analysis_continuation_calls": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_continuation"
                ),
                "submission_attempts": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "submission"
                ),
                "provider_attempts": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation", "submission"}
                ),
                "analysis_checkpoint_reuses": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_checkpoint_reuse"
                ),
                "successor_attempts": sum(
                    int(row["successor_attempt_count"]) for row in node_records
                ),
                "counter_challenge_repairs": counter_repairs,
                "reused_completed_challenge_repair_count": len(
                    completed_downstream_repairs
                ),
                "new_counter_challenge_repairs": new_counter_repairs,
                "evaluation_strategy": (
                    successor_frontier.get("evaluation_strategy")
                    if generic_successor
                    else MONOLITHIC_EVALUATION_STRATEGY
                ),
                "evaluator_role_audits": evaluator_role_audits,
                "evaluator_role_audit_reuses": (
                    evaluator_role_audit_reuses
                ),
                "evaluator_role_reaudits": evaluator_role_reaudits,
                "evaluator_cross_role_audits": evaluator_cross_role_audits,
                "evaluator_repairs": evaluator_repairs,
                "evaluation_rounds": len(evaluations),
                "external_source_network_calls": 0,
                "candidate_promotions": 0,
                "product_publication": False,
                "private_reasoning_persisted": False,
                "analysis_drafts_business_promoted": False,
            },
            "acceptance": {
                "true_independent_agent_sessions_proven": True,
                "R3_specialist_plan_checkpoint_reused_without_rerun": True,
                **(
                    {
                        "R6_validated_lead_plan_checkpoint_reused_without_"
                        "lead_rerun": True
                    }
                    if lead_checkpoint_successor
                    or workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else {}
                ),
                **(
                    {
                        (
                            "R9_six_workpaper_checkpoint_reused_without_"
                            "workpaper_rerun"
                            if coordination_resume
                            else (
                                "R7_five_workpaper_checkpoint_reused_without_"
                                "workpaper_rerun"
                            )
                        ): (
                            len(workpapers_by_agent) == 6
                            if coordination_resume
                            else len(
                                workpaper_checkpoint[
                                    "revalidated_workpapers"
                                ]
                            )
                            == 5
                        )
                    }
                    if (
                        workpaper_checkpoint_successor
                        or specialist_analysis_successor
                        or coordination_resume
                    )
                    and workpaper_checkpoint is not None
                    else {}
                ),
                "analysis_submission_separation_proven": all(
                    "submission"
                    in {attempt.get("phase") for attempt in row["attempts"]}
                    and bool(
                        {attempt.get("phase") for attempt in row["attempts"]}
                        & {
                            "analysis",
                            "analysis_continuation",
                            "analysis_checkpoint_reuse",
                        }
                    )
                    for row in node_records
                ),
                "feedback_checkpoint_resume_proven": any(
                    bool(session_state.feedback_receipts)
                    and bool(session_state.resume_receipts)
                    for session_state in sessions.values()
                ),
                "workpaper_checkpoint_resume_proven": (
                    sum(
                        1
                        for agent_id in (
                            SPECIALIST_AGENT_IDS
                            if coordination_resume
                            else SPECIALIST_AGENT_IDS[:5]
                        )
                        if state(agent_id).resume_receipts
                    )
                    == (6 if coordination_resume else 5)
                    if workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else False
                ),
                **(
                    {
                        "R9_lead_coordination_checkpoint_reused_without_rerun": (
                            all(
                                not row["node_id"].endswith(
                                    "::COORDINATION_R1"
                                )
                                for row in node_records
                            )
                            and bool(
                                state(
                                    RESEARCH_LEAD_AGENT_ID
                                ).resume_receipts
                            )
                        )
                    }
                    if coordination_resume
                    else {}
                ),
                **(
                    {
                        "compiled_frontier_completed_repairs_reused_without_"
                        "rerun": (
                            len(completed_downstream_repairs)
                            == len(completed_frontier_nodes)
                            and all(
                                row["node_id"]
                                not in {
                                    frontier_row["node_id"]
                                    for frontier_row in completed_frontier_nodes
                                }
                                for row in node_records
                            )
                        ),
                        "compiled_frontier_analysis_continuation_forbidden_"
                        "and_absent": all(
                            attempt.get("phase") != "analysis_continuation"
                            for row in node_records
                            for attempt in row["attempts"]
                        ),
                        "compiled_frontier_pending_repairs_executed_once": all(
                            sum(
                                1
                                for row in node_records
                                if row["node_id"] == frontier_row["node_id"]
                            )
                            == 1
                            for frontier_row in pending_frontier_nodes
                        ),
                        "hierarchical_evaluation_topology_proven": (
                            not hierarchical_evaluator
                            or (
                                evaluator_role_audits
                                + evaluator_role_audit_reuses
                                == 6
                                and evaluator_role_reaudits <= 2
                                and 1 <= evaluator_cross_role_audits <= 2
                            )
                        ),
                        "completed_role_evaluations_reused_without_rerun": (
                            evaluator_role_audit_reuses
                            == authority["execution_limits"].get(
                                "reused_role_evaluation_count", 0
                            )
                            and all(
                                row["agent_id"]
                                not in {
                                    "EVAL::ROLE::"
                                    + agent_id.split("::")[-1]
                                    for agent_id in (
                                        successor_frontier.get(
                                            "completed_role_evaluation_agent_ids"
                                        )
                                        or []
                                    )
                                }
                                or not row["node_id"].endswith(
                                    "::CONTENT_AUDIT_R1"
                                )
                                for row in node_records
                            )
                        ),
                    }
                    if generic_successor
                    else (
                        {
                            "R15_completed_demand_and_cash_repairs_reused_"
                            "without_rerun": (
                                len(completed_downstream_repairs) == 2
                                and all(
                                    row["node_id"]
                                    not in {
                                        "AGENT::DEMAND_QUALITY::COUNTER_REPAIR",
                                        "AGENT::CASH_CONVERSION::COUNTER_REPAIR",
                                    }
                                    for row in node_records
                                )
                            ),
                            "R15_analysis_continuation_forbidden_and_absent": all(
                                attempt.get("phase")
                                != "analysis_continuation"
                                for row in node_records
                                for attempt in row["attempts"]
                            ),
                            "R15_fresh_supply_repair_started_once": sum(
                                1
                                for row in node_records
                                if row["node_id"]
                                == (
                                    "AGENT::SUPPLY_RELATIONSHIP::"
                                    "COUNTER_REPAIR"
                                )
                            )
                            == 1,
                        }
                        if repair_context_replacement
                        else {}
                    )
                ),
                **(
                    {
                        "R10_completed_demand_repair_reused_without_rerun": (
                            len(completed_downstream_repairs) == 1
                            and all(
                                not row["node_id"].endswith(
                                    "AGENT::DEMAND_QUALITY::COUNTER_REPAIR"
                                )
                                for row in node_records
                            )
                        ),
                        "R10_cash_repair_analysis_checkpoint_resumed_once": sum(
                            1
                            for row in node_records
                            if row["node_id"].endswith(
                                "AGENT::CASH_CONVERSION::COUNTER_REPAIR"
                            )
                            for attempt in row["attempts"]
                            if attempt.get("phase")
                            == "analysis_continuation"
                        )
                        == 1,
                        "R10_cash_repair_initial_analysis_not_rerun": all(
                            attempt.get("phase") != "analysis"
                            for row in node_records
                            if row["node_id"].endswith(
                                "AGENT::CASH_CONVERSION::COUNTER_REPAIR"
                            )
                            for attempt in row["attempts"]
                        ),
                    }
                    if downstream_analysis_successor
                    and not role_scoped_repair_successor
                    else {}
                ),
                **(
                    {
                        "R4_analysis_checkpoint_resumed_once": sum(
                            1
                            for row in node_records
                            for attempt in row["attempts"]
                            if attempt.get("phase")
                            == "analysis_continuation"
                        )
                        == 1
                    }
                    if analysis_successor
                    else {}
                ),
                **(
                    {
                        "R8_counterevidence_analysis_checkpoint_resumed_once": sum(
                            1
                            for row in node_records
                            for attempt in row["attempts"]
                            if attempt.get("phase")
                            == "analysis_continuation"
                        )
                        == 1,
                        "R8_counterevidence_initial_analysis_not_rerun": all(
                            attempt.get("phase") != "analysis"
                            for row in node_records
                            if row["node_id"].endswith(
                                "AGENT::COUNTEREVIDENCE::WORKPAPER_R1"
                            )
                            for attempt in row["attempts"]
                        ),
                    }
                    if specialist_analysis_successor
                    else {}
                ),
                **(
                    {
                        "R5_completed_analysis_checkpoint_reused_without_"
                        "analysis_rerun": sum(
                            1
                            for row in node_records
                            for attempt in row["attempts"]
                            if attempt.get("phase")
                            == "analysis_checkpoint_reuse"
                        )
                        == 1
                    }
                    if submission_successor
                    else {}
                ),
                "report_contract_valid": report is not None,
                "formal_eight_dimension_assessment_pending": report is not None,
                "S1_pass": False,
                "S3_pass": False,
                "qualified_human_acceptance": False,
                "release_ready": False,
            },
        }
        full = {**full_body, "full_result_digest": canonical_digest(full_body)}
        full_path = private_root / "full_result.json"
        _write_new(full_path, full)
        public_body = {
            "schema_version": public_schema,
            "status": full["status"],
            "recorded_at": full["recorded_at"],
            "authority_ref": full["authority_ref"],
            "authority_sha256": full["authority_sha256"],
            "implementation_commit": full["implementation_commit"],
            "case_key": "DELL",
            "research_as_of": "2026-08-06",
            "predecessor_plan_checkpoint": full[
                "predecessor_plan_checkpoint"
            ],
            "successor_zero_call_proof": full["successor_zero_call_proof"],
            **analysis_successor_bindings,
            **submission_successor_bindings,
            **lead_checkpoint_successor_bindings,
            **workpaper_checkpoint_successor_bindings,
            **specialist_analysis_successor_bindings,
            **coordination_checkpoint_successor_bindings,
            **downstream_analysis_successor_bindings,
            "planning_overlay": full["planning_overlay"],
            "role_inventory": {
                "declared_true_agent_ids": [
                    RESEARCH_LEAD_AGENT_ID,
                    *SPECIALIST_AGENT_IDS,
                    WRITER_AGENT_ID,
                ],
                "activated_true_agent_ids": [
                    agent_id
                    for agent_id in [
                        RESEARCH_LEAD_AGENT_ID,
                        *SPECIALIST_AGENT_IDS,
                        WRITER_AGENT_ID,
                    ]
                    if agent_id in sessions
                ],
                "evaluator_execution_ids": sorted(
                    agent_id
                    for agent_id in sessions
                    if agent_id.startswith("EVAL::")
                ),
                "tools_and_label_roles_remain_non_agents": True,
            },
            "materialization_readiness": readiness,
            "collaboration": {
                "independent_specialist_opinions": len(opinions),
                "independent_specialist_workpapers": len(final_workpapers),
                "cross_role_challenges": len(challenge_catalog),
                "accepted_challenges": len(
                    coordination["accepted_challenge_ids"]
                ),
                "feedback_checkpoint_resume_cycles": sum(
                    len(session_state.resume_receipts)
                    for session_state in sessions.values()
                ),
                "evaluation_rounds": len(evaluations),
                "blocking_findings": [
                    {
                        "finding_code": row["finding_code"],
                        "severity": row["severity"],
                        "target_agent_id": row["target_agent_id"],
                        "failure_owner": row["failure_owner"],
                        "explanation": row["explanation"],
                    }
                    for row in final_evaluation["findings"]
                    if row["blocks_report"]
                ],
            },
            "report_preview": report,
            "execution": full["execution"],
            "acceptance": full["acceptance"],
            "historical_comparison_ref": _relative(
                paths["historical_five_cell_assessment"]
            ),
            "full_result_ref": _relative(full_path),
            "full_result_sha256": _sha(full_path),
            "known_boundary": known_boundary_prefix
            + (
                "It does not qualify open-web research, S1, S3, generalization, "
                "qualified-human acceptance, Workbench publication or release."
            ),
        }
        public = {**public_body, "result_digest": canonical_digest(public_body)}
        _write_new(public_result_path, public)
        return public
    except Exception as exc:
        failure_code = str(getattr(exc, "code", "") or str(exc) or type(exc).__name__)
        terminal_attempts = [
            deepcopy(dict(row))
            for row in getattr(exc, "attempts", ())
        ]
        failure_body = {
            "schema_version": full_schema,
            "status": "multi_agent_preview_terminal_failure_preserved",
            "recorded_at": _now(),
            "authority_ref": _relative(authority_path),
            "implementation_commit": authority["implementation_commit"],
            "failure_code": failure_code,
            "failure_type": type(exc).__name__,
            "predecessor_plan_checkpoint": {
                "ref": _relative(paths["predecessor_plan_checkpoint"]),
                "sha256": _sha(paths["predecessor_plan_checkpoint"]),
                "checkpoint_digest": plan_checkpoint["checkpoint_digest"],
                "reused_specialist_plan_count": 6,
            },
            "successor_zero_call_proof": {
                "ref": _relative(paths["successor_zero_call_proof"]),
                "sha256": _sha(paths["successor_zero_call_proof"]),
                "result_digest": successor_zero["result_digest"],
            },
            **analysis_successor_bindings,
            **submission_successor_bindings,
            **lead_checkpoint_successor_bindings,
            **workpaper_checkpoint_successor_bindings,
            **specialist_analysis_successor_bindings,
            **coordination_checkpoint_successor_bindings,
            **downstream_analysis_successor_bindings,
            "planning_overlay": {
                "ref": _relative(paths["planning_overlay"]),
                "sha256": _sha(paths["planning_overlay"]),
                "maximum_proposed_atoms": 20,
                "maximum_evidence_requests": 12,
            },
            "terminal_node_attempts": terminal_attempts,
            "node_executions": node_records,
            "sessions": {
                agent_id: session_state.as_dict()
                for agent_id, session_state in sessions.items()
            },
            "execution": {
                "new_model_nodes_started": node_index,
                "reused_specialist_plan_count": 6,
                "new_specialist_plan_model_calls": 0,
                "lead_plan_checkpoint_reuses_preserved": (
                    1
                    if lead_checkpoint_successor
                    or workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else 0
                ),
                "new_lead_plan_model_calls_preserved": (
                    0
                    if lead_checkpoint_successor
                    or workpaper_checkpoint_successor
                    or specialist_analysis_successor
                    or coordination_resume
                    else sum(
                        1
                        for row in node_records
                        if row["node_id"].endswith("::LEAD_PLAN")
                    )
                ),
                "reused_workpaper_count": (
                    6
                    if coordination_resume
                    else (
                        5
                        if workpaper_checkpoint_successor
                        or specialist_analysis_successor
                        else 0
                    )
                ),
                "reused_lead_coordination_count": (
                    1 if coordination_resume else 0
                ),
                "new_lead_coordination_model_calls_preserved": sum(
                    1
                    for row in node_records
                    if row["node_id"].endswith("::COORDINATION_R1")
                ),
                "new_initial_workpaper_nodes": sum(
                    1
                    for row in node_records
                    if row["node_id"].endswith("::WORKPAPER_R1")
                ),
                "analysis_calls_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation"}
                ),
                "analysis_continuation_calls_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_continuation"
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase") == "analysis_continuation"
                ),
                "submission_attempts_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "submission"
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase") == "submission"
                ),
                "provider_attempts_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation", "submission"}
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase")
                    in {"analysis", "analysis_continuation", "submission"}
                ),
                "analysis_checkpoint_reuses_preserved": sum(
                    1
                    for row in node_records
                    for attempt in row["attempts"]
                    if attempt.get("phase") == "analysis_checkpoint_reuse"
                )
                + sum(
                    1
                    for attempt in terminal_attempts
                    if attempt.get("phase") == "analysis_checkpoint_reuse"
                ),
                "reused_completed_challenge_repair_count": len(
                    completed_downstream_repairs
                ),
                "new_counter_challenge_repairs_preserved": (
                    new_counter_repairs
                ),
                "evaluation_strategy": (
                    successor_frontier.get("evaluation_strategy")
                    if generic_successor
                    else MONOLITHIC_EVALUATION_STRATEGY
                ),
                "evaluator_role_audits_preserved": evaluator_role_audits,
                "evaluator_role_audit_reuses_preserved": (
                    evaluator_role_audit_reuses
                ),
                "evaluator_role_reaudits_preserved": evaluator_role_reaudits,
                "evaluator_cross_role_audits_preserved": (
                    evaluator_cross_role_audits
                ),
                "evaluator_repairs_preserved": evaluator_repairs,
                "external_source_network_calls": 0,
                "candidate_promotions": 0,
                "product_publication": False,
                "analysis_drafts_business_promoted": False,
            },
        }
        failure = {
            **failure_body,
            "full_result_digest": canonical_digest(failure_body),
        }
        _write_new(private_root / "terminal_failure.json", failure)
        public_body = {
            "schema_version": public_schema,
            "status": failure["status"],
            "recorded_at": failure["recorded_at"],
            "authority_ref": failure["authority_ref"],
            "implementation_commit": failure["implementation_commit"],
            "failure_code": failure_code,
            "predecessor_plan_checkpoint": failure[
                "predecessor_plan_checkpoint"
            ],
            "successor_zero_call_proof": failure[
                "successor_zero_call_proof"
            ],
            **analysis_successor_bindings,
            **submission_successor_bindings,
            **lead_checkpoint_successor_bindings,
            **workpaper_checkpoint_successor_bindings,
            **specialist_analysis_successor_bindings,
            **coordination_checkpoint_successor_bindings,
            **downstream_analysis_successor_bindings,
            "planning_overlay": failure["planning_overlay"],
            "execution": failure["execution"],
            "full_result_ref": _relative(private_root / "terminal_failure.json"),
            "acceptance": {
                "true_multi_agent_preview_completed": False,
                "S1_pass": False,
                "S3_pass": False,
                "qualified_human_acceptance": False,
                "release_ready": False,
            },
        }
        public = {**public_body, "result_digest": canonical_digest(public_body)}
        _write_new(public_result_path, public)
        return public


def _materialize_pre_execution_failure(
    authority_path: Path,
    *,
    failure_code: str,
    failure_type: str,
    failure_message: str,
) -> dict[str, Any]:
    authority = _json(authority_path)
    outputs = authority.get("outputs") or {}
    if set(outputs) != {
        "run_id",
        "capture_root_ref",
        "private_output_root_ref",
        "public_result_ref",
    }:
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_pre_execution_failure_output_shape_invalid"
        )
    capture_root = _resolve(str(outputs["capture_root_ref"]))
    private_root = _resolve(str(outputs["private_output_root_ref"]))
    public_result_path = _resolve(str(outputs["public_result_ref"]))
    capture_entries = list(capture_root.rglob("*")) if capture_root.is_dir() else []
    if not (
        capture_root.is_dir()
        and not capture_entries
        and not private_root.exists()
        and not public_result_path.exists()
    ):
        raise MultiAgentPreviewLiveError(
            "multi_agent_preview_pre_execution_failure_not_eligible"
        )
    full_schema, public_schema = _result_schemas_for_authority(
        str(authority.get("schema_version") or "")
    )
    recorded_at = _now()
    execution = {
        "failure_phase": "pre_execution_binding",
        "authority_validation_completed": True,
        "capture_root_created": True,
        "capture_entries_preserved": 0,
        "new_model_nodes_started": 0,
        "provider_attempts_preserved": 0,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
    }
    failure_body = {
        "schema_version": full_schema,
        "status": "multi_agent_preview_terminal_failure_preserved",
        "recorded_at": recorded_at,
        "authority_ref": _relative(authority_path),
        "authority_sha256": _sha(authority_path),
        "implementation_commit": authority.get("implementation_commit"),
        "failure_code": failure_code,
        "failure_type": failure_type,
        "failure_message": failure_message,
        "run_id": outputs["run_id"],
        "bound_input_count": len(authority.get("bound_inputs") or {}),
        "terminal_node_attempts": [],
        "node_executions": [],
        "sessions": {},
        "execution": execution,
    }
    failure = {
        **failure_body,
        "full_result_digest": canonical_digest(failure_body),
    }
    _write_new(private_root / "terminal_failure.json", failure)
    public_body = {
        "schema_version": public_schema,
        "status": failure["status"],
        "recorded_at": recorded_at,
        "authority_ref": failure["authority_ref"],
        "authority_sha256": failure["authority_sha256"],
        "implementation_commit": failure["implementation_commit"],
        "failure_code": failure_code,
        "failure_phase": execution["failure_phase"],
        "execution": execution,
        "full_result_ref": _relative(private_root / "terminal_failure.json"),
        "acceptance": {
            "true_multi_agent_preview_completed": False,
            "S1_pass": False,
            "S3_pass": False,
            "qualified_human_acceptance": False,
            "release_ready": False,
        },
    }
    public = {**public_body, "result_digest": canonical_digest(public_body)}
    _write_new(public_result_path, public)
    return public


def run(authority_path: Path) -> dict[str, Any]:
    try:
        return _run_authorized(authority_path)
    except Exception as exc:
        try:
            return _materialize_pre_execution_failure(
                authority_path,
                failure_code="multi_agent_preview_pre_execution_runtime_failure",
                failure_type=type(exc).__name__,
                failure_message=str(exc),
            )
        except MultiAgentPreviewLiveError:
            raise exc


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authority", required=True)
    args = parser.parse_args(argv)
    result = run(_resolve(args.authority))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"].startswith("multi_agent_preview_") and "failure" not in result["status"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
