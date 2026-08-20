from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any

from sec_agent.canonical_runtime import canonical_digest
from sec_agent.research.material_scope_canary import (
    MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_CONTRACT_REPAIR_RUN_SCOPE,
    MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_SCHEMA,
    MATERIAL_SCOPE_SUCCESSOR_RUN_SCOPE,
    validate_material_scope_canary_authority,
)
from sec_agent.research.multi_agent_preview import (
    SPECIALIST_AGENT_IDS,
    load_multi_agent_role_topology,
    validate_analysis_completion_checkpoint,
    validate_analysis_fragment_checkpoint,
    validate_downstream_repair_progress_checkpoint,
    validate_downstream_repair_progress_checkpoint_v2,
    validate_lead_plan_checkpoint,
    validate_specialist_plan_checkpoint,
)
from sec_agent.providers import load_chat_completion_profile


CURRENT_PREFLIGHT_SCHEMA = "fin_ia_current_decision_bound_project_os_preflight_v1_0"
FIXED_PACK_SCOPE = (
    "one_separately_authorized_natural_fixed_pack_replacement_with_zero_retry"
)
MICRO_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_micro_judgment_live_scope_decision_v1_0"
)
MICRO_FIXED_PACK_DECISION_STATUS = (
    "micro_judgment_formal_zero_call_pass_"
    "canonical_live_gate_required_one_chat_successor_authorized"
)
FULL_FRAGMENT_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_live_scope_decision_v1_0"
)
FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_surface_"
    "live_scope_decision_v1_1"
)
FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_relation_role_"
    "live_scope_decision_v1_2"
)
FULL_FRAGMENT_CLAIM_LOCAL_BOUNDARY_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_claim_local_boundary_"
    "live_scope_decision_v1_3"
)
FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_causal_polarity_"
    "live_scope_decision_v1_4"
)
FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_full_fragment_judgment_wwc_route_identifier_"
    "live_scope_decision_v1_5"
)
FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_failed_fragment_submission_successor_"
    "live_scope_decision_v1_6"
)
FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_STATUS = (
    "failed_fragment_zero_call_pass_one_non_thinking_submission_"
    "successor_authorized"
)
FRAGMENT_VALIDATION_REPAIR_DECISION_SCHEMA = (
    "fin_ia_s3_fixed_pack_fragment_validation_repair_"
    "live_scope_decision_v1_8"
)
FRAGMENT_VALIDATION_REPAIR_DECISION_STATUS = (
    "zero_call_pass_one_validation_repair_authorized"
)
FRAGMENT_VALIDATION_REPAIR_SCOPE = (
    "one_fresh_same_fragment_repair_after_clean_gate"
)
DYNAMIC_SINGLE_CELL_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_live_scope_decision_v1_0"
)
DYNAMIC_SINGLE_CELL_DECISION_STATUS = (
    "approved_one_honest_DELL_SEC_only_dynamic_single_cell"
)
DYNAMIC_SINGLE_CELL_SCOPE = (
    "one_honest_DELL_SEC_only_dynamic_single_cell"
)
DYNAMIC_FIVE_CELL_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_exact_once"
)
DYNAMIC_FIVE_CELL_SCOPE = "one_DELL_dynamic_five_cell_exact_once"
MULTI_AGENT_PREVIEW_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_0"
)
MULTI_AGENT_PREVIEW_DECISION_STATUS = (
    "approved_one_clean_authorized_DELL_multi_agent_preview"
)
MULTI_AGENT_PREVIEW_SCOPE = "one_clean_authorized_DELL_multi_agent_preview"
MULTI_AGENT_PREVIEW_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_1"
)
MULTI_AGENT_PREVIEW_SUCCESSOR_DECISION_STATUS = (
    "R2_thinking_tool_choice_failure_preserved_one_profile_"
    "compatibility_successor_authorized"
)
MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_2"
)
MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS = (
    "R3_six_specialist_plans_preserved_one_analysis_submission_"
    "checkpoint_successor_authorized"
)
MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R3_plan_checkpoint_successor"
)
MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_3"
)
MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS = (
    "R4_visible_analysis_length_failure_preserved_one_checkpoint_feedback_"
    "continuation_successor_authorized"
)
MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R4_analysis_checkpoint_successor"
)
MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_4"
)
MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_STATUS = (
    "R5_semantically_complete_analysis_preserved_one_strict_submission_"
    "checkpoint_successor_authorized"
)
MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R5_completed_analysis_submission_successor"
)
MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_5"
)
MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_STATUS = (
    "R6_lead_contract_failure_preserved_one_validated_plan_checkpoint_"
    "downstream_successor_authorized"
)
MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R6_Lead_checkpoint_downstream_successor"
)
MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_6"
)
MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_STATUS = (
    "R7_five_workpapers_preserved_one_remaining_workpaper_"
    "downstream_successor_authorized"
)
MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R7_five_workpaper_checkpoint_downstream_successor"
)
MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_7"
)
MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_STATUS = (
    "R8_counterevidence_analysis_length_failure_preserved_one_checkpoint_"
    "continuation_downstream_successor_authorized"
)
MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R8_counterevidence_analysis_checkpoint_"
    "downstream_successor"
)
MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_8"
)
MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_STATUS = (
    "R9_lead_coordination_capacity_failure_preserved_six_workpapers_and_"
    "coordination_checkpoint_downstream_successor_authorized"
)
MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R9_lead_coordination_checkpoint_downstream_successor"
)
MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_9"
)
MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_STATUS = (
    "R10_downstream_analysis_length_failure_preserved_completed_repair_and_"
    "fragment_checkpoint_successor_authorized"
)
MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R10_downstream_repair_analysis_checkpoint_successor"
)
MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dell_multi_agent_preview_live_scope_decision_v1_10"
)
MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_STATUS = (
    "R14_supply_reasoning_only_failure_preserved_two_repairs_and_role_scoped_"
    "fresh_successor_authorized"
)
MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE = (
    "one_clean_authorized_R15_role_scoped_supply_repair_successor"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_remaining_twelve_nodes_exact_once"
)
DYNAMIC_FIVE_CELL_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_successor_remaining_twelve_nodes"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_partial_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_failed_three_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_partial_successor_failed_three_plus_synthesis"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_node_successor_live_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_two_submissions_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_node_successor_two_submissions_plus_synthesis"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_claim_surface_successor_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
)
DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_claim_surface_successor_exact_once"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_scope_decision_v1_1"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_exact_once"
)
DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_cell_scoped_claim_contract_"
    "successor_exact_once"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
    "successor_scope_decision_v1_0"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_STATUS = (
    "approved_one_DELL_dynamic_five_cell_value_submission_"
    "repair_plus_synthesis_exact_once"
)
DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_SCOPE = (
    "one_DELL_dynamic_five_cell_value_submission_repair_plus_synthesis"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_0 = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_0"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_0 = (
    "dynamic_R1_preserved_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1 = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_1"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_1 = (
    "dynamic_R1_historical_binding_pass_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
    "live_scope_decision_v1_2"
)
DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS = (
    "dynamic_R1_authority_contract_pass_one_counter_analysis_submission_"
    "successor_authorized"
)
DYNAMIC_COUNTER_SUCCESSOR_SCOPE = (
    "one_dynamic_counter_WWC_failed_node_successor_after_clean_zero_call_gate"
)
DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA = (
    "fin_ia_s3_dynamic_single_cell_temporal_fragment_repair_"
    "live_scope_decision_v1_0"
)
DYNAMIC_TEMPORAL_REPAIR_DECISION_STATUS = (
    "dynamic_temporal_authority_zero_call_pass_one_counter_repair_authorized"
)
DYNAMIC_TEMPORAL_REPAIR_SCOPE = (
    "one_DELL_dynamic_counter_temporal_fragment_repair_after_clean_zero_call_gate"
)
FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS = (
    "full_fragment_zero_call_pass_one_fresh_chat_judgment_authorized"
)
REQUIRED_PROJECT_OS_REFS = (
    "docs/project_os/current_context_pack.zh-CN.md",
    "docs/project_os/senior_assistant_collaboration_policy.zh-CN.md",
    "docs/project_os/root_cause_issue_ledger.jsonl",
    "docs/project_os/capability_status_ledger.jsonl",
    "docs/project_os/full_chain_preflight_checklist.json",
    "docs/project_os/full_chain_run_policy.zh-CN.md",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git_blob_sha256(*, root: Path, commit: str, ref: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", str(commit or "").lower()):
        raise ValueError("project_os_historical_commit_invalid")
    _repo_path(root, ref)
    completed = subprocess.run(
        ["git", "show", f"{commit}:{ref}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise ValueError("project_os_historical_blob_missing")
    return hashlib.sha256(completed.stdout).hexdigest()


def _git_latest_commit_for_ref(*, root: Path, ref: str) -> str:
    _repo_path(root, ref)
    completed = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--", ref],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    commit = completed.stdout.strip().lower()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("project_os_historical_ref_commit_missing")
    return commit


def _repo_path(root: Path, ref: str) -> Path:
    if not ref or Path(ref).is_absolute():
        raise ValueError(f"project_os_ref_not_repo_relative:{ref}")
    path = (root / ref).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError(f"project_os_ref_missing:{ref}")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"project_os_json_object_required:{path.as_posix()}")
    return value


def _latest_jsonl_rows(path: Path, key: str) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"project_os_jsonl_invalid:{path.as_posix()}:{line_number}"
            ) from exc
        if not isinstance(row, dict) or not row.get(key):
            raise ValueError(
                f"project_os_jsonl_key_missing:{path.as_posix()}:{line_number}:{key}"
            )
        latest[str(row[key])] = row
    if not latest:
        raise ValueError(f"project_os_jsonl_empty:{path.as_posix()}")
    return latest


def _validate_artifact_binding(
    *,
    root: Path,
    decision: Mapping[str, Any],
    ref_field: str,
    sha_field: str,
    digest_field: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    ref = str(decision.get(ref_field) or "")
    path = _repo_path(root, ref)
    actual_sha = _sha256(path)
    expected_sha = str(decision.get(sha_field) or "")
    if actual_sha != expected_sha:
        raise ValueError(f"project_os_artifact_sha_drift:{ref_field}:{ref}")
    payload = _load_json(path)
    if digest_field is not None:
        expected_digest = str(decision.get(digest_field) or "")
        if str(payload.get("result_digest") or "") != expected_digest:
            raise ValueError(f"project_os_artifact_result_digest_drift:{ref_field}:{ref}")
    return path, payload


def _validate_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    if decision.get("schema_version") in {
        MULTI_AGENT_PREVIEW_DECISION_SCHEMA,
        MULTI_AGENT_PREVIEW_SUCCESSOR_DECISION_SCHEMA,
    }:
        return validate_multi_agent_preview_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_plan_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_analysis_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_submission_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_lead_checkpoint_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_specialist_analysis_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
    ):
        return validate_multi_agent_preview_downstream_analysis_successor_scope_decision(
            root=root, decision=decision
        )
    if decision.get("schema_version") in {
        MATERIAL_SCOPE_CANARY_AUTHORITY_SCHEMA,
        MATERIAL_SCOPE_CONTRACT_REPAIR_AUTHORITY_SCHEMA,
        MATERIAL_SCOPE_SUCCESSOR_AUTHORITY_SCHEMA,
    }:
        return _validate_material_scope_canary_decision(
            root=root, decision=decision
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_value_repair_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") in {
        DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_SCHEMA,
        DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA,
    }:
        return _validate_dynamic_five_cell_claim_surface_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_node_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_partial_successor_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_dynamic_five_cell_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_FIVE_CELL_DECISION_SCHEMA:
        return _validate_dynamic_five_cell_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA:
        return _validate_dynamic_temporal_repair_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        in {
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_0,
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1,
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA,
        }
    ):
        return _validate_dynamic_counter_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == DYNAMIC_SINGLE_CELL_DECISION_SCHEMA:
        return _validate_dynamic_single_cell_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") == FRAGMENT_VALIDATION_REPAIR_DECISION_SCHEMA:
        return _validate_fragment_validation_repair_decision(
            root=root,
            decision=decision,
        )
    if (
        decision.get("schema_version")
        == FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_SCHEMA
    ):
        return _validate_failed_fragment_submission_successor_decision(
            root=root,
            decision=decision,
        )
    if decision.get("schema_version") in {
        FULL_FRAGMENT_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA,
        FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA,
    }:
        return _validate_full_fragment_fixed_pack_decision(
            root=root, decision=decision
        )
    if decision.get("schema_version") in {
        FULL_FRAGMENT_CLAIM_LOCAL_BOUNDARY_DECISION_SCHEMA,
        FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA,
    }:
        return _validate_claim_local_boundary_fixed_pack_decision(
            root=root, decision=decision
        )
    if decision.get("schema_version") == MICRO_FIXED_PACK_DECISION_SCHEMA:
        return _validate_micro_fixed_pack_decision(
            root=root, decision=decision
        )
    alias_status = (
        "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
        "one_chat_successor_authorized"
    )
    alias_mode = decision.get("status") == alias_status
    required_equal = {
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_claim_relation_alias_Chat_successor"
            if alias_mode
            else "one_DELL_value_capture_fixed_pack_claim_surface_Chat_replacement"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_decision_field_invalid:{field}")
    if "authorized" not in str(decision.get("status") or ""):
        raise ValueError("project_os_decision_not_authorized")

    required_true = (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
    )
    required_false = (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
    )
    for field in required_true:
        if decision.get(field) is not True:
            raise ValueError(f"project_os_decision_true_required:{field}")
    for field in required_false:
        if decision.get(field) is not False:
            raise ValueError(f"project_os_decision_false_required:{field}")
    if alias_mode:
        if decision.get("same_evidence_pack_and_provider_profile") is not True:
            raise ValueError(
                "project_os_decision_true_required:"
                "same_evidence_pack_and_provider_profile"
            )
        if decision.get("reasoning_or_token_limit_increase") is not False:
            raise ValueError(
                "project_os_decision_false_required:"
                "reasoning_or_token_limit_increase"
            )

    numeric_equal = {
        "maximum_model_calls": 3,
        "maximum_provider_transport_attempts": 3,
        "maximum_completion_tokens_per_call": 16000,
        "maximum_total_completion_tokens": 48000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_decision_budget_invalid:{field}")

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    acceptance = clean.get("acceptance") or {}
    legacy_clean_valid = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_surface_authority"
        and acceptance.get("corrected_zero_call_judgment_passes") is True
        and acceptance.get("zero_request_fixed_pack_loop_passes") is True
        and acceptance.get("natural_replacement_live_proven") is False
    )
    alias_clean_valid = (
        clean.get("status")
        == "engineering_pass_zero_call_claim_relation_alias_capacity"
        and acceptance.get(
            "relation_alias_selection_and_local_expansion_pass"
        )
        is True
        and acceptance.get("capacity_reduction_pass") is True
        and acceptance.get("fake_loop_and_mutation_pass") is True
        and acceptance.get("natural_replacement_live_proven") is False
    )
    if (alias_mode and not alias_clean_valid) or (
        not alias_mode and not legacy_clean_valid
    ):
        raise ValueError("project_os_clean_proof_acceptance_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    if predecessor.get("status") != "terminal_failed_no_retry":
        raise ValueError("project_os_predecessor_status_invalid")
    expected_failure = (
        "model_gateway_reasoning_budget_exhausted"
        if alias_mode
        else "finance_loop_judgment_invalid:research_consumer_thesis_atom_invalid"
    )
    if predecessor.get("failure_code") != expected_failure:
        raise ValueError("project_os_predecessor_failure_code_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_profile_ref",
        sha_field="provider_profile_sha256",
    )
    if (
        profile.get("wire_api") != "openai_compatible_chat_completions"
        or profile.get("model") != "deepseek-v4-pro"
        or (profile.get("authority") or {}).get("retry_count") != 0
    ):
        raise ValueError("project_os_provider_profile_invalid")
    if (profile.get("request_defaults") or {}).get("max_tokens") != decision.get(
        "maximum_completion_tokens_per_call"
    ):
        raise ValueError("project_os_provider_profile_budget_drift")

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    if (
        health.get("status") != "completed_contract_valid_content_assessment_pending"
        or (health.get("execution") or {}).get("retries") != 0
        or not health.get("provider_steps")
    ):
        raise ValueError("project_os_provider_health_evidence_invalid")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": len(health["provider_steps"]),
        "claim_relation_alias_capacity_successor": alias_mode,
        "micro_judgment_successor": False,
    }


def validate_multi_agent_preview_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    successor = (
        decision.get("schema_version")
        == MULTI_AGENT_PREVIEW_SUCCESSOR_DECISION_SCHEMA
    )
    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "topology_ref",
        "topology_sha256",
        "objective_ref",
        "objective_sha256",
        "zero_call_proof_ref",
        "zero_call_proof_sha256",
        "provider_profile_ref",
        "provider_profile_sha256",
        "historical_five_cell_assessment_ref",
        "historical_five_cell_assessment_sha256",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if successor:
        expected_fields.update(
            {
                "predecessor_authority_ref",
                "predecessor_authority_sha256",
                "predecessor_result_ref",
                "predecessor_result_sha256",
                "transport_fix_scope",
                "unchanged_research_inputs_required",
            }
        )
    if set(decision) != expected_fields:
        raise ValueError("project_os_multi_agent_decision_shape_invalid")

    required_equal = {
        "status": (
            MULTI_AGENT_PREVIEW_SUCCESSOR_DECISION_STATUS
            if successor
            else MULTI_AGENT_PREVIEW_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_transport_successor_"
            "live_attempt"
            if successor
            else "one_bounded_DELL_multi_agent_preview_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_multi_agent_decision_field_invalid:{field}"
            )

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_multi_agent_decision_true_required:{field}"
            )

    if successor:
        if decision.get("unchanged_research_inputs_required") is not True:
            raise ValueError(
                "project_os_multi_agent_successor_unchanged_inputs_required"
            )
        if decision.get("transport_fix_scope") != (
            "omit_unsupported_tool_choice_in_thinking_mode_via_"
            "provider_profile_capability"
        ):
            raise ValueError(
                "project_os_multi_agent_successor_transport_scope_invalid"
            )
        _, predecessor_authority = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="predecessor_authority_ref",
            sha_field="predecessor_authority_sha256",
        )
        _, predecessor_result = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="predecessor_result_ref",
            sha_field="predecessor_result_sha256",
        )
        predecessor_execution = predecessor_result.get("execution") or {}
        predecessor_acceptance = predecessor_result.get("acceptance") or {}
        if not (
            predecessor_authority.get("schema_version")
            == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_1"
            and predecessor_authority.get("status")
            == "approved_for_one_bounded_preview_after_project_os_preflight"
            and predecessor_result.get("status")
            == "multi_agent_preview_terminal_failure_preserved"
            and predecessor_result.get("failure_code")
            == "model_gateway_http_error:400"
            and predecessor_execution.get("model_nodes_started") == 1
            and predecessor_execution.get("provider_attempts_preserved") == 2
            and predecessor_acceptance.get(
                "true_multi_agent_preview_completed"
            )
            is False
        ):
            raise ValueError(
                "project_os_multi_agent_successor_predecessor_invalid"
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_multi_agent_decision_false_required:{field}"
            )

    _, topology = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="topology_ref",
        sha_field="topology_sha256",
    )
    preview_agents = topology.get("preview_agents") or ()
    specialist_count = sum(
        1
        for row in preview_agents
        if isinstance(row, Mapping)
        and row.get("preview_state") == "true_agent"
        and row.get("cell_id")
    )
    if not (
        topology.get("status")
        == "preview_topology_audited_not_product_qualified"
        and topology.get("case_key") == "DELL"
        and specialist_count == 6
        and len(topology.get("evaluators") or ()) >= 5
    ):
        raise ValueError("project_os_multi_agent_topology_invalid")

    _, objective = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="objective_ref",
        sha_field="objective_sha256",
    )
    if not (
        objective.get("case_key") == "DELL"
        and objective.get("task_type") == "company_deep_dive"
        and len(objective.get("required_slot_ids") or ()) == 7
        and objective.get("gap_policy") == "return_typed_gap"
    ):
        raise ValueError("project_os_multi_agent_objective_invalid")

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_proof_ref",
        sha_field="zero_call_proof_sha256",
    )
    zero_claims = zero.get("claims") or {}
    if not (
        zero.get("status") == "zero_call_topology_and_current_tool_spine_pass"
        and zero.get("case_key") == "DELL"
        and zero.get("independent_specialist_opinion_count") == 6
        and zero.get("blocking_empty_role_ids") == []
        and zero_claims.get("model_calls") == 0
        and zero_claims.get("network_calls") == 0
        and zero_claims.get("S1_pass") is False
        and zero_claims.get("S3_pass") is False
        and zero_claims.get("true_multi_agent_live_proven") is False
    ):
        raise ValueError("project_os_multi_agent_zero_call_proof_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_profile_ref",
        sha_field="provider_profile_sha256",
    )
    profile_authority = profile.get("authority") or {}
    if not (
        profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("model") == "deepseek-v4-pro"
        and profile_authority.get("retry_count") == 0
        and profile_authority.get("capture_model_visible_request") is True
        and profile_authority.get("capture_assistant_output") is True
        and profile_authority.get("provider_private_reasoning_capture_forbidden")
        is True
        and (
            not successor
            or (
                profile.get("schema_version")
                == "fin_ia_agent_transport_profile_v1_1"
                and profile_authority.get("thinking_tool_choice_supported")
                is False
                and profile_authority.get(
                    "thinking_tool_continuation_requires_reasoning_content"
                )
                is True
                and profile_authority.get(
                    "thinking_tool_continuation_requires_assistant_content"
                )
                is True
            )
        )
    ):
        raise ValueError("project_os_multi_agent_provider_profile_invalid")

    _, historical = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="historical_five_cell_assessment_ref",
        sha_field="historical_five_cell_assessment_sha256",
    )
    historical_execution = historical.get("execution") or {}
    if not (
        historical.get("case_key") == "DELL"
        and "not_accepted" in str(historical.get("status") or "")
        and historical_execution.get("new_model_calls", 0) > 0
        and (historical.get("hard_gate_assessment") or {}).get("overall_L1_L2")
        == "fail"
    ):
        raise ValueError("project_os_multi_agent_historical_boundary_invalid")

    expected_limits = {
        "maximum_model_nodes": 22,
        "maximum_successor_attempts_per_node": 1,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError("project_os_multi_agent_execution_limits_invalid")
    expected_budget_policy = {
        "task_specific_basis_required_per_model_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError("project_os_multi_agent_token_budget_policy_invalid")

    return {
        "clean_proof_status": zero["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": historical_execution["new_model_calls"],
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": successor,
        "run_scope_id": decision["run_scope_id"],
        "specialist_agent_count": specialist_count,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_plan_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate the R3-plan-checkpoint successor without rerunning specialists."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "topology_ref",
        "topology_sha256",
        "objective_ref",
        "objective_sha256",
        "zero_call_proof_ref",
        "zero_call_proof_sha256",
        "successor_zero_call_proof_ref",
        "successor_zero_call_proof_sha256",
        "successor_zero_call_proof_result_digest",
        "planning_overlay_ref",
        "planning_overlay_sha256",
        "analysis_profile_ref",
        "analysis_profile_sha256",
        "submission_profile_ref",
        "submission_profile_sha256",
        "historical_five_cell_assessment_ref",
        "historical_five_cell_assessment_sha256",
        "predecessor_authority_ref",
        "predecessor_authority_sha256",
        "predecessor_result_ref",
        "predecessor_result_sha256",
        "predecessor_plan_checkpoint_ref",
        "predecessor_plan_checkpoint_sha256",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_plan_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA,
        "status": MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R3_plan_checkpoint_"
            "successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_plan_successor_field_invalid:"
                + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_plan_successor_true_required:"
                + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_plan_successor_false_required:"
                + field
            )

    _, topology = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="topology_ref",
        sha_field="topology_sha256",
    )
    preview_agents = topology.get("preview_agents") or []
    if not (
        topology.get("status")
        == "preview_topology_audited_not_product_qualified"
        and topology.get("case_key") == "DELL"
        and sum(
            1
            for row in preview_agents
            if isinstance(row, Mapping)
            and row.get("agent_id") in SPECIALIST_AGENT_IDS
            and row.get("preview_state") == "true_agent"
        )
        == len(SPECIALIST_AGENT_IDS)
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_topology_invalid"
        )
    _, objective = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="objective_ref",
        sha_field="objective_sha256",
    )
    if not (
        objective.get("case_key") == "DELL"
        and objective.get("task_type") == "company_deep_dive"
        and len(objective.get("required_slot_ids") or []) == 7
        and objective.get("gap_policy") == "return_typed_gap"
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_objective_invalid"
        )
    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_proof_ref",
        sha_field="zero_call_proof_sha256",
    )
    zero_claims = zero.get("claims") or {}
    if not (
        zero.get("status") == "zero_call_topology_and_current_tool_spine_pass"
        and zero.get("independent_specialist_opinion_count") == 6
        and zero.get("blocking_empty_role_ids") == []
        and zero_claims.get("model_calls") == 0
        and zero_claims.get("network_calls") == 0
        and zero_claims.get("S1_pass") is False
        and zero_claims.get("S3_pass") is False
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_zero_proof_invalid"
        )

    _, successor_zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="successor_zero_call_proof_ref",
        sha_field="successor_zero_call_proof_sha256",
        digest_field="successor_zero_call_proof_result_digest",
    )
    successor_bindings = successor_zero.get("bindings") or {}
    checkpoint_resume = successor_zero.get("checkpoint_resume") or {}
    two_phase = successor_zero.get("two_phase_projection") or {}
    readiness = successor_zero.get("materialization_readiness") or {}
    controlled = readiness.get("controlled_plan_summary") or {}
    execution_projection = successor_zero.get("execution_budget_projection") or {}
    negative_mutations = successor_zero.get("negative_mutations") or {}
    successor_claims = successor_zero.get("claims") or {}
    role_readiness = readiness.get("role_readiness") or []
    if not (
        successor_zero.get("schema_version")
        == (
            "fin_ia_s3_dell_multi_agent_preview_"
            "R4_plan_successor_zero_call_result_v1_0"
        )
        and successor_zero.get("status")
        == "R3_plan_checkpoint_successor_zero_call_pass"
        and successor_zero.get("case_key") == "DELL"
        and successor_bindings.get("topology_ref")
        == decision["topology_ref"]
        and successor_bindings.get("topology_sha256")
        == decision["topology_sha256"]
        and successor_bindings.get("objective_ref")
        == decision["objective_ref"]
        and successor_bindings.get("objective_sha256")
        == decision["objective_sha256"]
        and successor_bindings.get("plan_checkpoint_ref")
        == decision["predecessor_plan_checkpoint_ref"]
        and successor_bindings.get("plan_checkpoint_sha256")
        == decision["predecessor_plan_checkpoint_sha256"]
        and checkpoint_resume.get("reused_specialist_plan_count") == 6
        and checkpoint_resume.get("new_specialist_plan_model_calls") == 0
        and checkpoint_resume.get("lead_start_node")
        == "AGENT::RESEARCH_LEAD::LEAD_PLAN"
        and set(checkpoint_resume.get("reused_agent_ids") or [])
        == set(SPECIALIST_AGENT_IDS)
        and two_phase.get("analysis_message_count") == 2
        and two_phase.get("submission_message_count") == 2
        and two_phase.get("analysis_has_original_role_context") is True
        and two_phase.get("submission_contains_analysis_draft") is True
        and two_phase.get("submission_excludes_original_context_sentinel")
        is True
        and two_phase.get("analysis_draft_business_promotion") is False
        and readiness.get("blocking_empty_role_ids") == []
        and readiness.get("compiled_evidence_request_count") == 12
        and controlled.get("proposed_atom_count") == 13
        and controlled.get("selected_atom_count") == 12
        and controlled.get("deferred_atom_count") == 1
        and controlled.get("execution_request_budget") == 12
        and controlled.get("evidence_request_count") == 12
        and controlled.get("compiled_lane_count") == 12
        and controlled.get("nonempty_lane_count") == 12
        and controlled.get("hybrid_selected_candidate_count") == 192
        and controlled.get("typed_fact_request_count") == 44
        and controlled.get("typed_fact_resolved_count") == 27
        and controlled.get("typed_fact_gap_count") == 17
        and controlled.get("typed_fact_conflict_count") == 0
        and controlled.get("numeric_fact_count") == 87
        and controlled.get("model_calls") == 0
        and controlled.get("network_calls") == 0
        and len(role_readiness) == 6
        and {
            str(row.get("agent_id") or "")
            for row in role_readiness
            if isinstance(row, Mapping)
        }
        == set(SPECIALIST_AGENT_IDS)
        and all(
            int(row.get("reviewed_evidence_visible") or 0)
            + int(row.get("numeric_facts_visible") or 0)
            > 0
            and int(row.get("tool_execution_receipts_visible") or 0) == 2
            for row in role_readiness
            if isinstance(row, Mapping)
        )
        and execution_projection
        == {
            "maximum_new_model_nodes": 16,
            "lead_nodes": 2,
            "specialist_workpaper_nodes": 6,
            "maximum_counter_repair_nodes": 3,
            "maximum_evaluator_nodes": 2,
            "maximum_evaluator_repair_nodes": 2,
            "conditional_writer_nodes": 1,
            "maximum_analysis_calls_per_node": 1,
            "maximum_submission_attempts_per_node": 2,
        }
        and negative_mutations
        == {
            "missing_specialist_plan_rejected": True,
            "checkpoint_digest_mutation_rejected": True,
            "original_context_not_copied_to_submission": True,
        }
        and successor_claims
        == {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_live_completed": False,
        }
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_current_proof_invalid"
        )

    _, planning_overlay = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="planning_overlay_ref",
        sha_field="planning_overlay_sha256",
    )
    if not (
        set(planning_overlay)
        == {
            "schema_version",
            "status",
            "base_policy_resource_id",
            "max_proposed_atoms_override",
            "max_evidence_requests_must_remain",
            "selection_strategy_must_remain",
            "authority",
            "reason",
        }
        and planning_overlay.get("schema_version")
        == "fin_ia_multi_agent_preview_planning_overlay_v1_0"
        and planning_overlay.get("status")
        == "provider_neutral_preview_proposal_execution_budget_separation"
        and planning_overlay.get("base_policy_resource_id")
        == "application.config.current_research_planning_policy"
        and planning_overlay.get("max_proposed_atoms_override") == 20
        and planning_overlay.get("max_evidence_requests_must_remain") == 12
        and planning_overlay.get("selection_strategy_must_remain")
        == "required_slot_first_then_provider_neutral_facet_priority"
        and planning_overlay.get("authority")
        == {
            "changes_research_evidence_or_numeric_authority": False,
            "changes_execution_request_budget": False,
            "records_deferred_atoms": True,
            "provider_or_model_specific": False,
            "product_pointer_promotion": False,
        }
        and str(planning_overlay.get("reason") or "").strip()
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_planning_overlay_invalid"
        )

    _, analysis_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_profile_ref",
        sha_field="analysis_profile_sha256",
    )
    analysis_defaults = analysis_profile.get("request_defaults") or {}
    analysis_authority = analysis_profile.get("authority") or {}
    if not (
        analysis_profile.get("schema_version")
        == "fin_ia_chat_completion_provider_profile_v1_0"
        and analysis_profile.get("provider_id") == "deepseek"
        and analysis_profile.get("model") == "deepseek-v4-pro"
        and analysis_profile.get("base_url") == "https://api.deepseek.com"
        and analysis_profile.get("endpoint") == "/chat/completions"
        and analysis_defaults.get("stream") is False
        and analysis_defaults.get("thinking") == {"type": "enabled"}
        and analysis_defaults.get("reasoning_effort") == "max"
        and analysis_defaults.get("max_tokens") == 16000
        and analysis_authority.get("retry_count") == 0
        and analysis_authority.get(
            "provider_private_reasoning_capture_forbidden"
        )
        is True
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_analysis_profile_invalid"
        )
    _, submission_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    submission_defaults = submission_profile.get("request_defaults") or {}
    submission_authority = submission_profile.get("authority") or {}
    if not (
        submission_profile.get("schema_version")
        == "fin_ia_chat_completion_provider_profile_v1_0"
        and submission_profile.get("provider_id") == "deepseek"
        and submission_profile.get("model") == "deepseek-v4-pro"
        and submission_profile.get("base_url") == "https://api.deepseek.com"
        and submission_profile.get("endpoint") == "/chat/completions"
        and submission_defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and submission_authority.get("retry_count") == 0
        and submission_authority.get(
            "provider_private_reasoning_capture_forbidden"
        )
        is True
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_submission_profile_invalid"
        )

    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_authority_ref",
        sha_field="predecessor_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_result_ref",
        sha_field="predecessor_result_sha256",
    )
    _, checkpoint = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_plan_checkpoint_ref",
        sha_field="predecessor_plan_checkpoint_sha256",
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_2"
        and predecessor_authority.get("status")
        == (
            "approved_for_one_transport_compatibility_successor_"
            "after_project_os_preflight"
        )
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and predecessor_execution.get("model_nodes_started") == 7
        and predecessor_execution.get("provider_attempts_preserved") == 11
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_predecessor_invalid"
        )
    validated_checkpoint = validate_specialist_plan_checkpoint(
        checkpoint, topology=topology
    )
    if not (
        validated_checkpoint["predecessor_authority_ref"]
        == decision["predecessor_authority_ref"]
        and validated_checkpoint["predecessor_authority_sha256"]
        == decision["predecessor_authority_sha256"]
        and validated_checkpoint["predecessor_result_ref"]
        == decision["predecessor_result_ref"]
        and validated_checkpoint["predecessor_result_sha256"]
        == decision["predecessor_result_sha256"]
        and validated_checkpoint["predecessor_result_digest"]
        == predecessor_result.get("result_digest")
        and validated_checkpoint["reused_specialist_plan_count"] == 6
        and successor_bindings.get("plan_checkpoint_digest")
        == validated_checkpoint["checkpoint_digest"]
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_checkpoint_binding_invalid"
        )

    _, historical = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="historical_five_cell_assessment_ref",
        sha_field="historical_five_cell_assessment_sha256",
    )
    historical_execution = historical.get("execution") or {}
    if not (
        historical.get("case_key") == "DELL"
        and "not_accepted" in str(historical.get("status") or "")
        and historical_execution.get("new_model_calls", 0) > 0
        and (historical.get("hard_gate_assessment") or {}).get("overall_L1_L2")
        == "fail"
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_historical_invalid"
        )
    expected_constraints = {
        "reuse_exactly_six_R3_specialist_plans": True,
        "rerun_successful_specialist_plans": False,
        "analysis_submission_separation_required": True,
        "analysis_draft_business_promotion_forbidden": True,
        "research_inputs_unchanged": True,
        "maximum_proposed_atoms": 20,
        "maximum_evidence_requests": 12,
        "deferred_atoms_receipt_required": True,
        "planning_overlay_product_promotion_forbidden": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_plan_successor_constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 16,
        "maximum_analysis_calls_per_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_plan_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "analysis_and_submission_bases_separate": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_plan_successor_budget_policy_invalid"
        )
    return {
        "clean_proof_status": zero["status"],
        "successor_zero_call_proof_status": successor_zero["status"],
        "provider_id": analysis_profile["provider_id"],
        "provider_model": analysis_profile["model"],
        "api_key_env": analysis_profile["api_key_env"],
        "recent_provider_steps": historical_execution["new_model_calls"],
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "maximum_proposed_atoms": 20,
        "maximum_evidence_requests": 12,
        "proved_proposed_atom_count": 13,
        "proved_selected_atom_count": 12,
        "proved_deferred_atom_count": 1,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_analysis_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one R4 partial-analysis checkpoint continuation successor."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "analysis_fragment_checkpoint_required",
        "semantic_completion_receipt_required",
        "one_continuation_only",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "analysis_checkpoint_ref",
        "analysis_checkpoint_sha256",
        "analysis_checkpoint_digest",
        "analysis_successor_zero_call_proof_ref",
        "analysis_successor_zero_call_proof_sha256",
        "analysis_successor_zero_call_proof_result_digest",
        "analysis_continuation_profile_ref",
        "analysis_continuation_profile_sha256",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_analysis_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_SCHEMA,
        "status": MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R4_analysis_checkpoint_"
            "successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_analysis_successor_field_invalid:"
                + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "analysis_fragment_checkpoint_required",
        "semantic_completion_receipt_required",
        "one_continuation_only",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_analysis_successor_true_required:"
                + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_analysis_successor_false_required:"
                + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_plan_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    if not (
        predecessor_scope.get("schema_version")
        == MULTI_AGENT_PREVIEW_PLAN_SUCCESSOR_DECISION_SCHEMA
        and predecessor_projection.get(
            "multi_agent_preview_plan_checkpoint_successor"
        )
        is True
    ):
        raise ValueError(
            "project_os_multi_agent_analysis_successor_predecessor_scope_invalid"
        )

    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    predecessor_scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    if not (
        predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_3"
        and predecessor_scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and predecessor_scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and predecessor_execution.get("analysis_calls_preserved") == 1
        and predecessor_execution.get("submission_attempts_preserved") == 0
        and predecessor_execution.get("new_specialist_plan_model_calls") == 0
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_analysis_successor_predecessor_invalid"
        )

    _, raw_checkpoint = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_checkpoint_ref",
        sha_field="analysis_checkpoint_sha256",
    )
    checkpoint = validate_analysis_fragment_checkpoint(raw_checkpoint)
    if not (
        checkpoint["checkpoint_digest"]
        == decision["analysis_checkpoint_digest"]
        and checkpoint["source_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and checkpoint["source_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and checkpoint["source_public_result_ref"]
        == decision["predecessor_live_result_ref"]
        and checkpoint["source_public_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and checkpoint["source_public_result_digest"]
        == predecessor_result.get("result_digest")
        and checkpoint["node_id"] == "AGENT::RESEARCH_LEAD::LEAD_PLAN"
        and checkpoint["completed_required_outputs"]
        == ["accepted_agent_ids", "accepted_facets"]
        and checkpoint["partial_required_outputs"]
        == ["coordination_questions"]
        and checkpoint["missing_required_outputs"]
        == ["expected_information_boundaries", "stop_conditions"]
        and checkpoint["continuation_policy"]["maximum_continuation_calls"]
        == 1
    ):
        raise ValueError(
            "project_os_multi_agent_analysis_successor_checkpoint_invalid"
        )
    for ref_field, sha_field in (
        ("request_capture_ref", "request_capture_sha256"),
        ("response_capture_ref", "response_capture_sha256"),
    ):
        capture_path = _repo_path(root, str(checkpoint[ref_field]))
        if _sha256(capture_path) != checkpoint[sha_field]:
            raise ValueError(
                "project_os_multi_agent_analysis_successor_capture_drift:"
                + ref_field
            )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_successor_zero_call_proof_ref",
        sha_field="analysis_successor_zero_call_proof_sha256",
        digest_field="analysis_successor_zero_call_proof_result_digest",
    )
    proof_bindings = proof.get("bindings") or {}
    checkpoint_projection = proof.get("checkpoint_projection") or {}
    runtime_projection = proof.get("runtime_projection") or {}
    negative = proof.get("negative_mutations") or {}
    claims = proof.get("claims") or {}
    if not (
        proof.get("status")
        == "R4_visible_analysis_checkpoint_successor_zero_call_pass"
        and proof.get("case_key") == "DELL"
        and proof_bindings.get("analysis_checkpoint_ref")
        == decision["analysis_checkpoint_ref"]
        and proof_bindings.get("analysis_checkpoint_digest")
        == decision["analysis_checkpoint_digest"]
        and proof_bindings.get("R4_authority_ref")
        == decision["predecessor_live_authority_ref"]
        and proof_bindings.get("R4_authority_sha256")
        == decision["predecessor_live_authority_sha256"]
        and proof_bindings.get("R4_public_result_ref")
        == decision["predecessor_live_result_ref"]
        and proof_bindings.get("R4_public_result_sha256")
        == decision["predecessor_live_result_sha256"]
        and proof_bindings.get("continuation_profile_ref")
        == decision["analysis_continuation_profile_ref"]
        and proof_bindings.get("continuation_profile_sha256")
        == decision["analysis_continuation_profile_sha256"]
        and checkpoint_projection.get("maximum_continuation_calls") == 1
        and checkpoint_projection.get(
            "partial_draft_content_persisted_in_public_artifact"
        )
        is False
        and runtime_projection.get("attempt_phases")
        == ["analysis_continuation", "submission"]
        and runtime_projection.get("continuation_calls") == 1
        and runtime_projection.get("submission_calls") == 1
        and runtime_projection.get("validated_lead_plan") is True
        and runtime_projection.get("checkpoint_event_present") is True
        and runtime_projection.get("feedback_event_present") is True
        and runtime_projection.get("resume_event_present") is True
        and runtime_projection.get("original_full_context_resent") is False
        and runtime_projection.get("merged_draft_reached_submission") is True
        and negative.get("checkpoint_digest_mutation_rejected") is True
        and negative.get("semantic_incompletion_rejected_before_submission")
        is True
        and negative.get("semantic_incompletion_continuation_call_count") == 1
        and negative.get("public_checkpoint_excludes_partial_draft") is True
        and negative.get(
            "continuation_messages_require_all_remaining_outputs"
        )
        is True
        and claims
        == {
            "model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "specialist_plan_reruns": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_live_completed": False,
        }
    ):
        raise ValueError(
            "project_os_multi_agent_analysis_successor_proof_invalid"
        )

    continuation_profile_path, continuation_profile_payload = (
        _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="analysis_continuation_profile_ref",
            sha_field="analysis_continuation_profile_sha256",
        )
    )
    del continuation_profile_path
    continuation_profile = load_chat_completion_profile(
        continuation_profile_payload
    )
    if not (
        continuation_profile.provider_id == "deepseek"
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
        raise ValueError(
            "project_os_multi_agent_analysis_successor_profile_invalid"
        )

    expected_constraints = {
        "reuse_R4_visible_partial_analysis": True,
        "partial_analysis_business_promotion_forbidden": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "rerun_successful_specialist_plans": False,
        "continue_only_checkpoint_partial_and_missing_outputs": True,
        "semantic_completion_required_before_submission": True,
        "maximum_analysis_continuations": 1,
        "analysis_submission_separation_required": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_analysis_successor_constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 16,
        "maximum_resumed_lead_analysis_continuations": 1,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_analysis_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "analysis_continuation_basis_is_separate": True,
        "submission_basis_is_separate": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_analysis_successor_budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": continuation_profile.provider_id,
        "provider_model": continuation_profile.model,
        "api_key_env": continuation_profile.api_key_env,
        "recent_provider_steps": 1,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": True,
        "multi_agent_preview_analysis_checkpoint_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_ANALYSIS_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "maximum_analysis_continuations": 1,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_submission_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one R5 completed-analysis checkpoint submission successor."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "completed_analysis_checkpoint_required",
        "new_lead_analysis_forbidden",
        "strict_submission_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "analysis_completion_checkpoint_ref",
        "analysis_completion_checkpoint_sha256",
        "analysis_completion_checkpoint_digest",
        "submission_successor_zero_call_proof_ref",
        "submission_successor_zero_call_proof_sha256",
        "submission_successor_zero_call_proof_result_digest",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_submission_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_SCHEMA,
        "status": MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R5_completed_analysis_"
            "submission_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_submission_successor_field_invalid:"
                + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "completed_analysis_checkpoint_required",
        "new_lead_analysis_forbidden",
        "strict_submission_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_submission_successor_true_required:"
                + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_submission_successor_false_required:"
                + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_analysis_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    predecessor_scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    if not (
        predecessor_projection.get(
            "multi_agent_preview_analysis_checkpoint_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_4"
        and predecessor_scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and predecessor_scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_analysis_continuation_semantically_incomplete"
        and predecessor_execution.get("analysis_continuation_calls_preserved")
        == 1
        and predecessor_execution.get("submission_attempts_preserved") == 0
        and predecessor_execution.get("new_specialist_plan_model_calls") == 0
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_submission_successor_predecessor_invalid"
        )

    completion_path, raw_completion = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_completion_checkpoint_ref",
        sha_field="analysis_completion_checkpoint_sha256",
    )
    del completion_path
    completion = validate_analysis_completion_checkpoint(raw_completion)
    if not (
        completion["checkpoint_digest"]
        == decision["analysis_completion_checkpoint_digest"]
        and completion["source_continuation_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and completion["source_continuation_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and completion["source_continuation_result_ref"]
        == decision["predecessor_live_result_ref"]
        and completion["source_continuation_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and completion["source_continuation_result_digest"]
        == predecessor_result.get("result_digest")
        and completion["node_id"] == "AGENT::RESEARCH_LEAD::LEAD_PLAN"
        and completion["required_outputs"]
        == [
            "accepted_agent_ids",
            "accepted_facets",
            "coordination_questions",
            "expected_information_boundaries",
            "stop_conditions",
        ]
        and completion["continuation_completed_outputs"]
        == [
            "coordination_questions",
            "expected_information_boundaries",
            "stop_conditions",
        ]
    ):
        raise ValueError(
            "project_os_multi_agent_submission_successor_checkpoint_invalid"
        )
    for ref_field, sha_field in (
        ("fragment_checkpoint_ref", "fragment_checkpoint_sha256"),
        (
            "continuation_request_capture_ref",
            "continuation_request_capture_sha256",
        ),
        (
            "continuation_response_capture_ref",
            "continuation_response_capture_sha256",
        ),
    ):
        artifact_path = _repo_path(root, str(completion[ref_field]))
        if _sha256(artifact_path) != completion[sha_field]:
            raise ValueError(
                "project_os_multi_agent_submission_successor_capture_drift:"
                + ref_field
            )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_successor_zero_call_proof_ref",
        sha_field="submission_successor_zero_call_proof_sha256",
        digest_field="submission_successor_zero_call_proof_result_digest",
    )
    projection = proof.get("runtime_projection") or {}
    replay = proof.get("replay_projection") or {}
    bindings = proof.get("bindings") or {}
    negative = proof.get("negative_mutations") or {}
    claims = proof.get("claims") or {}
    if not (
        proof.get("status")
        == "R5_completed_analysis_submission_successor_zero_call_pass"
        and proof.get("case_key") == "DELL"
        and bindings.get("completion_checkpoint_ref")
        == decision["analysis_completion_checkpoint_ref"]
        and bindings.get("completion_checkpoint_digest")
        == decision["analysis_completion_checkpoint_digest"]
        and bindings.get("R5_authority_ref")
        == decision["predecessor_live_authority_ref"]
        and bindings.get("R5_authority_sha256")
        == decision["predecessor_live_authority_sha256"]
        and bindings.get("R5_public_result_ref")
        == decision["predecessor_live_result_ref"]
        and bindings.get("R5_public_result_sha256")
        == decision["predecessor_live_result_sha256"]
        and replay.get("analysis_or_continuation_rerun") is False
        and replay.get("continuation_semantically_complete_under_corrected_contract")
        is True
        and projection.get("attempt_phases")
        == ["analysis_checkpoint_reuse", "submission"]
        and projection.get("provider_attempt_count") == 1
        and projection.get("analysis_checkpoint_reuse_count") == 1
        and projection.get("submission_calls") == 1
        and projection.get("validated_lead_plan") is True
        and projection.get("merged_draft_reached_submission") is True
        and projection.get("analysis_context_digest_preserved") is True
        and bool(negative)
        and all(value is True for value in negative.values())
        and claims
        == {
            "new_analysis_model_calls": 0,
            "new_submission_model_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "specialist_plan_reruns": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_live_completed": False,
        }
    ):
        raise ValueError(
            "project_os_multi_agent_submission_successor_proof_invalid"
        )

    expected_constraints = {
        "reuse_R4_fragment_and_R5_continuation": True,
        "analysis_fragments_business_promotion_forbidden": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "rerun_successful_specialist_plans": False,
        "rerun_lead_analysis_or_continuation": False,
        "strict_lead_submission_only": True,
        "analysis_submission_separation_required": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_submission_successor_constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 16,
        "maximum_new_lead_analysis_calls": 0,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_submission_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "source_analysis_basis_must_remain_bound": True,
        "new_lead_analysis_budget_forbidden": True,
        "submission_basis_is_separate": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_submission_successor_budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 1,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": True,
        "multi_agent_preview_analysis_checkpoint_successor": True,
        "multi_agent_preview_submission_checkpoint_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_SUBMISSION_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "maximum_new_lead_analysis_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_lead_checkpoint_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one downstream-only successor from the R6 Lead checkpoint."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "new_lead_plan_model_calls_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "topology_ref",
        "topology_sha256",
        "specialist_plan_checkpoint_ref",
        "specialist_plan_checkpoint_sha256",
        "specialist_plan_checkpoint_digest",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "lead_plan_checkpoint_digest",
        "lead_checkpoint_successor_zero_call_proof_ref",
        "lead_checkpoint_successor_zero_call_proof_sha256",
        "lead_checkpoint_successor_zero_call_proof_result_digest",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R6_validated_Lead_plan_"
            "downstream_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_lead_checkpoint_successor_field_invalid:"
                + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "new_lead_plan_model_calls_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_lead_checkpoint_successor_true_required:"
                + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_lead_checkpoint_successor_false_required:"
                + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_submission_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    predecessor_scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_projection.get(
            "multi_agent_preview_submission_checkpoint_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_5"
        and predecessor_scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and predecessor_scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_lead_coordination_questions_invalid"
        and predecessor_execution.get("new_model_nodes_started") == 1
        and predecessor_execution.get("analysis_calls_preserved") == 0
        and predecessor_execution.get("analysis_checkpoint_reuses_preserved")
        == 1
        and predecessor_execution.get("submission_attempts_preserved") == 2
        and predecessor_execution.get("new_specialist_plan_model_calls") == 0
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_predecessor_invalid"
        )

    topology_path = _repo_path(root, str(decision["topology_ref"]))
    if _sha256(topology_path) != decision["topology_sha256"]:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_topology_drift"
        )
    topology = load_multi_agent_role_topology(_load_json(topology_path))
    specialist_path, raw_specialist = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="specialist_plan_checkpoint_ref",
        sha_field="specialist_plan_checkpoint_sha256",
    )
    del specialist_path
    specialist = validate_specialist_plan_checkpoint(
        raw_specialist, topology=topology
    )
    if specialist["checkpoint_digest"] != decision[
        "specialist_plan_checkpoint_digest"
    ]:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_specialist_drift"
        )
    lead_path, raw_lead = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="lead_plan_checkpoint_ref",
        sha_field="lead_plan_checkpoint_sha256",
    )
    del lead_path
    lead = validate_lead_plan_checkpoint(
        raw_lead,
        opinions=specialist["specialist_plans"],
        topology=topology,
    )
    if not (
        lead["checkpoint_digest"] == decision["lead_plan_checkpoint_digest"]
        and lead["specialist_plan_checkpoint_ref"]
        == decision["specialist_plan_checkpoint_ref"]
        and lead["specialist_plan_checkpoint_sha256"]
        == decision["specialist_plan_checkpoint_sha256"]
        and lead["specialist_plan_checkpoint_digest"]
        == decision["specialist_plan_checkpoint_digest"]
        and lead["source_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and lead["source_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and lead["source_public_result_ref"]
        == decision["predecessor_live_result_ref"]
        and lead["source_public_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and lead["source_public_result_digest"]
        == predecessor_result.get("result_digest")
        and lead["source_failure_code"]
        == predecessor_result.get("failure_code")
    ):
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_checkpoint_invalid"
        )
    for ref_field, sha_field in (
        ("request_capture_ref", "request_capture_sha256"),
        ("response_capture_ref", "response_capture_sha256"),
    ):
        artifact_path = _repo_path(root, str(lead[ref_field]))
        if _sha256(artifact_path) != lead[sha_field]:
            raise ValueError(
                "project_os_multi_agent_lead_checkpoint_successor_capture_drift:"
                + ref_field
            )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="lead_checkpoint_successor_zero_call_proof_ref",
        sha_field="lead_checkpoint_successor_zero_call_proof_sha256",
        digest_field=(
            "lead_checkpoint_successor_zero_call_proof_result_digest"
        ),
    )
    readiness = proof.get("materialization_readiness") or {}
    claims = proof.get("claims") or {}
    if not (
        proof.get("status")
        == (
            "R6_validated_lead_plan_checkpoint_downstream_successor_"
            "zero_call_pass"
        )
        and proof.get("case_key") == "DELL"
        and proof.get("specialist_plan_checkpoint_digest")
        == specialist["checkpoint_digest"]
        and proof.get("lead_plan_checkpoint_digest")
        == lead["checkpoint_digest"]
        and proof.get("lead_plan_digest")
        == lead["lead_plan"]["lead_plan_digest"]
        and proof.get("reused_specialist_plan_count") == 6
        and proof.get("reused_lead_plan_count") == 1
        and proof.get("maximum_new_model_nodes") == 15
        and readiness.get("blocking_empty_role_ids") == []
        and claims
        == {
            "new_specialist_plan_model_calls": 0,
            "new_lead_analysis_calls": 0,
            "new_lead_submission_calls": 0,
            "network_calls": 0,
            "paid_tool_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
            "true_multi_agent_preview_completed": False,
        }
    ):
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_proof_invalid"
        )

    expected_constraints = {
        "R6_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "rerun_successful_specialist_plans": False,
        "rerun_lead_analysis_continuation_or_submission": False,
        "downstream_execution_starts_at_specialist_workpapers": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 15,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_successor_budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 0,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": False,
        "multi_agent_preview_analysis_checkpoint_successor": False,
        "multi_agent_preview_submission_checkpoint_successor": False,
        "multi_agent_preview_lead_checkpoint_downstream_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_LEAD_CHECKPOINT_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one R7 successor that resumes after five workpapers."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "workpaper_checkpoint_required",
        "new_lead_plan_model_calls_forbidden",
        "completed_workpaper_reruns_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "topology_ref",
        "topology_sha256",
        "specialist_plan_checkpoint_ref",
        "specialist_plan_checkpoint_sha256",
        "specialist_plan_checkpoint_digest",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "lead_plan_checkpoint_digest",
        "workpaper_checkpoint_ref",
        "workpaper_checkpoint_sha256",
        "workpaper_checkpoint_digest",
        "workpaper_checkpoint_successor_zero_call_proof_ref",
        "workpaper_checkpoint_successor_zero_call_proof_sha256",
        "workpaper_checkpoint_successor_zero_call_proof_result_digest",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": (
            MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": (
            MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE
        ),
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R7_five_workpaper_"
            "checkpoint_downstream_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_workpaper_checkpoint_successor_"
                "field_invalid:" + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "workpaper_checkpoint_required",
        "new_lead_plan_model_calls_forbidden",
        "completed_workpaper_reruns_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_workpaper_checkpoint_successor_"
                "true_required:" + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_workpaper_checkpoint_successor_"
                "false_required:" + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_lead_checkpoint_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_projection.get(
            "multi_agent_preview_lead_checkpoint_downstream_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_6"
        and scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_workpaper_ref_out_of_scope"
        and predecessor_execution.get("new_model_nodes_started") == 5
        and predecessor_execution.get("analysis_calls_preserved") == 5
        and predecessor_execution.get("submission_attempts_preserved") == 6
        and predecessor_execution.get("provider_attempts_preserved") == 11
        and predecessor_execution.get("external_source_network_calls") == 0
        and predecessor_execution.get("candidate_promotions") == 0
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "predecessor_invalid"
        )

    topology_path = _repo_path(root, str(decision["topology_ref"]))
    if _sha256(topology_path) != decision["topology_sha256"]:
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "topology_drift"
        )
    topology = load_multi_agent_role_topology(_load_json(topology_path))
    _, raw_specialist = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="specialist_plan_checkpoint_ref",
        sha_field="specialist_plan_checkpoint_sha256",
    )
    specialist = validate_specialist_plan_checkpoint(
        raw_specialist, topology=topology
    )
    _, raw_lead = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="lead_plan_checkpoint_ref",
        sha_field="lead_plan_checkpoint_sha256",
    )
    lead = validate_lead_plan_checkpoint(
        raw_lead,
        opinions=specialist["specialist_plans"],
        topology=topology,
    )
    if not (
        specialist["checkpoint_digest"]
        == decision["specialist_plan_checkpoint_digest"]
        and lead["checkpoint_digest"]
        == decision["lead_plan_checkpoint_digest"]
    ):
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "planning_checkpoint_drift"
        )

    _, workpaper = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="workpaper_checkpoint_ref",
        sha_field="workpaper_checkpoint_sha256",
    )
    terminal_path = _repo_path(
        root, str(workpaper.get("source_terminal_result_ref") or "")
    )
    terminal = _load_json(terminal_path)
    terminal_body = dict(terminal)
    terminal_digest = str(terminal_body.pop("full_result_digest", ""))
    checkpoint_body = dict(workpaper)
    checkpoint_digest = str(checkpoint_body.pop("checkpoint_digest", ""))
    if not (
        checkpoint_digest == decision["workpaper_checkpoint_digest"]
        and checkpoint_digest == canonical_digest(checkpoint_body)
        and workpaper.get("status")
        == "five_R7_specialist_workpapers_valid_for_downstream_resume"
        and workpaper.get("case_key") == "DELL"
        and workpaper.get("source_authority_ref")
        == decision["predecessor_live_authority_ref"]
        and workpaper.get("source_authority_sha256")
        == decision["predecessor_live_authority_sha256"]
        and workpaper.get("source_public_result_ref")
        == decision["predecessor_live_result_ref"]
        and workpaper.get("source_public_result_sha256")
        == decision["predecessor_live_result_sha256"]
        and workpaper.get("source_public_result_digest")
        == predecessor_result.get("result_digest")
        and workpaper.get("source_terminal_result_ref")
        == predecessor_result.get("full_result_ref")
        and _sha256(terminal_path)
        == workpaper.get("source_terminal_result_sha256")
        and terminal_digest == canonical_digest(terminal_body)
        and terminal_digest == workpaper.get("source_terminal_result_digest")
        and workpaper.get("completed_agent_ids")
        == list(SPECIALIST_AGENT_IDS[:5])
        and workpaper.get("pending_agent_ids")
        == [SPECIALIST_AGENT_IDS[5]]
        and workpaper.get("reused_workpaper_count") == 5
        and len(workpaper.get("source_receipts") or ()) == 5
        and set(workpaper.get("workpaper_digests") or {})
        == set(SPECIALIST_AGENT_IDS[:5])
        and workpaper.get("claims")
        == {
            "new_model_calls": 0,
            "new_network_calls": 0,
            "candidate_promotions": 0,
            "S1_pass": False,
            "S3_pass": False,
        }
    ):
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "checkpoint_invalid"
        )
    _, successor_proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="workpaper_checkpoint_successor_zero_call_proof_ref",
        sha_field="workpaper_checkpoint_successor_zero_call_proof_sha256",
        digest_field=(
            "workpaper_checkpoint_successor_zero_call_proof_result_digest"
        ),
    )
    if not (
        successor_proof.get("status")
        == "R7_five_workpaper_checkpoint_downstream_successor_zero_call_pass"
        and successor_proof.get("workpaper_checkpoint_digest")
        == checkpoint_digest
        and successor_proof.get("reused_workpaper_count") == 5
        and successor_proof.get("pending_agent_ids")
        == [SPECIALIST_AGENT_IDS[5]]
        and successor_proof.get("maximum_new_model_nodes") == 10
        and (successor_proof.get("materialization_readiness") or {}).get(
            "blocking_empty_role_ids"
        )
        == []
        and (successor_proof.get("claims") or {}).get(
            "new_completed_workpaper_model_calls"
        )
        == 0
    ):
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "zero_call_proof_invalid"
        )

    expected_constraints = {
        "R7_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "reuse_exactly_five_validated_R7_workpapers": True,
        "rerun_completed_workpapers": False,
        "downstream_execution_starts_at_counterevidence_workpaper": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 10,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 1,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 5,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "reused_workpapers_have_no_new_token_budget": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_successor_"
            "budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": successor_proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 0,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": False,
        "multi_agent_preview_analysis_checkpoint_successor": False,
        "multi_agent_preview_submission_checkpoint_successor": False,
        "multi_agent_preview_lead_checkpoint_downstream_successor": False,
        "multi_agent_preview_workpaper_checkpoint_downstream_successor": True,
        "run_scope_id": (
            MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE
        ),
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 5,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_specialist_analysis_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one R9 successor from the truncated Counter analysis."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "workpaper_checkpoint_required",
        "specialist_analysis_checkpoint_required",
        "original_analysis_conversation_replay_required",
        "new_lead_plan_model_calls_forbidden",
        "completed_workpaper_reruns_forbidden",
        "counterevidence_initial_analysis_rerun_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "topology_ref",
        "topology_sha256",
        "specialist_plan_checkpoint_ref",
        "specialist_plan_checkpoint_sha256",
        "specialist_plan_checkpoint_digest",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "lead_plan_checkpoint_digest",
        "workpaper_checkpoint_ref",
        "workpaper_checkpoint_sha256",
        "workpaper_checkpoint_digest",
        "specialist_analysis_checkpoint_ref",
        "specialist_analysis_checkpoint_sha256",
        "specialist_analysis_checkpoint_digest",
        "specialist_analysis_successor_zero_call_proof_ref",
        "specialist_analysis_successor_zero_call_proof_sha256",
        "specialist_analysis_successor_zero_call_proof_result_digest",
        "analysis_continuation_profile_ref",
        "analysis_continuation_profile_sha256",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": (
            MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_"
            "no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R8_counterevidence_"
            "analysis_checkpoint_downstream_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_specialist_analysis_successor_"
                "field_invalid:" + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "lead_coordination_feedback_required",
        "checkpoint_resume_required",
        "lead_plan_checkpoint_required",
        "workpaper_checkpoint_required",
        "specialist_analysis_checkpoint_required",
        "original_analysis_conversation_replay_required",
        "new_lead_plan_model_calls_forbidden",
        "completed_workpaper_reruns_forbidden",
        "counterevidence_initial_analysis_rerun_forbidden",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_specialist_analysis_successor_"
                "true_required:" + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_specialist_analysis_successor_"
                "false_required:" + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_workpaper_checkpoint_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    predecessor_execution = predecessor_result.get("execution") or {}
    predecessor_acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_projection.get(
            "multi_agent_preview_workpaper_checkpoint_downstream_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_7"
        and scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and predecessor_execution.get("new_model_nodes_started") == 1
        and predecessor_execution.get("analysis_calls_preserved") == 1
        and predecessor_execution.get("analysis_continuation_calls_preserved")
        == 0
        and predecessor_execution.get("submission_attempts_preserved") == 0
        and predecessor_execution.get("provider_attempts_preserved") == 1
        and predecessor_execution.get("reused_workpaper_count") == 5
        and predecessor_execution.get("new_initial_workpaper_nodes") == 0
        and predecessor_execution.get("external_source_network_calls") == 0
        and predecessor_execution.get("candidate_promotions") == 0
        and predecessor_acceptance.get("true_multi_agent_preview_completed")
        is False
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "predecessor_invalid"
        )

    topology_path = _repo_path(root, str(decision["topology_ref"]))
    if _sha256(topology_path) != decision["topology_sha256"]:
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "topology_drift"
        )
    topology = load_multi_agent_role_topology(_load_json(topology_path))
    _, raw_specialist = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="specialist_plan_checkpoint_ref",
        sha_field="specialist_plan_checkpoint_sha256",
    )
    specialist = validate_specialist_plan_checkpoint(
        raw_specialist, topology=topology
    )
    _, raw_lead = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="lead_plan_checkpoint_ref",
        sha_field="lead_plan_checkpoint_sha256",
    )
    lead = validate_lead_plan_checkpoint(
        raw_lead,
        opinions=specialist["specialist_plans"],
        topology=topology,
    )
    _, workpaper = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="workpaper_checkpoint_ref",
        sha_field="workpaper_checkpoint_sha256",
    )
    if not (
        specialist["checkpoint_digest"]
        == decision["specialist_plan_checkpoint_digest"]
        and lead["checkpoint_digest"]
        == decision["lead_plan_checkpoint_digest"]
        and workpaper.get("checkpoint_digest")
        == decision["workpaper_checkpoint_digest"]
        and workpaper.get("completed_agent_ids")
        == list(SPECIALIST_AGENT_IDS[:5])
        and workpaper.get("pending_agent_ids") == [SPECIALIST_AGENT_IDS[5]]
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "planning_or_workpaper_checkpoint_drift"
        )

    _, raw_analysis_checkpoint = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="specialist_analysis_checkpoint_ref",
        sha_field="specialist_analysis_checkpoint_sha256",
    )
    analysis_checkpoint = validate_analysis_fragment_checkpoint(
        raw_analysis_checkpoint
    )
    if not (
        analysis_checkpoint["checkpoint_digest"]
        == decision["specialist_analysis_checkpoint_digest"]
        and analysis_checkpoint["run_id"]
        == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R8_20260820"
        and analysis_checkpoint["node_id"]
        == "AGENT::COUNTEREVIDENCE::WORKPAPER_R1"
        and analysis_checkpoint["source_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and analysis_checkpoint["source_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and analysis_checkpoint["source_public_result_ref"]
        == decision["predecessor_live_result_ref"]
        and analysis_checkpoint["source_public_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and analysis_checkpoint["source_public_result_digest"]
        == predecessor_result.get("result_digest")
        and analysis_checkpoint["finish_reason"] == "length"
        and analysis_checkpoint["partial_draft_character_count"] == 918
        and analysis_checkpoint["completed_required_outputs"] == []
        and analysis_checkpoint["partial_required_outputs"] == ["thesis"]
        and analysis_checkpoint["continuation_policy"][
            "maximum_continuation_calls"
        ]
        == 1
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "analysis_checkpoint_invalid"
        )
    for ref_field, sha_field in (
        ("request_capture_ref", "request_capture_sha256"),
        ("response_capture_ref", "response_capture_sha256"),
    ):
        artifact_path = _repo_path(root, str(analysis_checkpoint[ref_field]))
        if _sha256(artifact_path) != analysis_checkpoint[sha_field]:
            raise ValueError(
                "project_os_multi_agent_specialist_analysis_successor_"
                "capture_drift:" + ref_field
            )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="specialist_analysis_successor_zero_call_proof_ref",
        sha_field="specialist_analysis_successor_zero_call_proof_sha256",
        digest_field=(
            "specialist_analysis_successor_zero_call_proof_result_digest"
        ),
    )
    summary = proof.get("materialization_summary") or {}
    if not (
        proof.get("status")
        == (
            "R8_counterevidence_analysis_checkpoint_downstream_successor_"
            "zero_call_pass"
        )
        and proof.get("analysis_fragment_checkpoint_digest")
        == analysis_checkpoint["checkpoint_digest"]
        and proof.get("workpaper_checkpoint_digest")
        == workpaper.get("checkpoint_digest")
        and proof.get("reused_workpaper_count") == 5
        and proof.get("pending_agent_ids") == [SPECIALIST_AGENT_IDS[5]]
        and proof.get("maximum_analysis_continuation_calls") == 1
        and proof.get("new_initial_counterevidence_analysis_calls") == 0
        and proof.get("maximum_new_model_nodes") == 10
        and summary.get("blocking_empty_role_ids") == []
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "zero_call_proof_invalid"
        )

    _, continuation_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_continuation_profile_ref",
        sha_field="analysis_continuation_profile_sha256",
    )
    defaults = continuation_profile.get("request_defaults") or {}
    if not (
        continuation_profile.get("provider_id") == "deepseek"
        and continuation_profile.get("model") == "deepseek-v4-pro"
        and continuation_profile.get("base_url") == "https://api.deepseek.com"
        and continuation_profile.get("endpoint") == "/chat/completions"
        and defaults
        == {
            "max_tokens": 4000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "low",
        }
        and (continuation_profile.get("authority") or {}).get("retry_count")
        == 0
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "profile_invalid"
        )

    expected_constraints = {
        "R8_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "reuse_exactly_five_validated_R7_workpapers": True,
        "resume_exactly_one_R8_counterevidence_analysis_fragment": True,
        "replay_original_counterevidence_analysis_conversation": True,
        "rerun_completed_workpapers": False,
        "rerun_initial_counterevidence_analysis": False,
        "downstream_execution_starts_at_counterevidence_analysis_continuation": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 10,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 0,
        "maximum_resumed_specialist_analysis_continuations": 1,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 5,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "reused_workpapers_have_no_new_token_budget": True,
        "counterevidence_continuation_basis_is_task_specific": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_successor_"
            "budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 1,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": False,
        "multi_agent_preview_analysis_checkpoint_successor": False,
        "multi_agent_preview_submission_checkpoint_successor": False,
        "multi_agent_preview_lead_checkpoint_downstream_successor": False,
        "multi_agent_preview_workpaper_checkpoint_downstream_successor": False,
        "multi_agent_preview_specialist_analysis_checkpoint_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 5,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one downstream resume after the natural R9 Lead decision."""

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_workpaper_reruns_forbidden",
        "accepted_challenge_repair_entry_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "workpaper_checkpoint_ref",
        "workpaper_checkpoint_sha256",
        "lead_coordination_checkpoint_ref",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "coordination_checkpoint_successor_zero_call_proof_ref",
        "coordination_checkpoint_successor_zero_call_proof_sha256",
        "coordination_checkpoint_successor_zero_call_proof_result_digest",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": (
            MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": (
            MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE
        ),
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R9_lead_coordination_"
            "checkpoint_downstream_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_coordination_checkpoint_successor_"
                "field_invalid:" + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_workpaper_reruns_forbidden",
        "accepted_challenge_repair_entry_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_coordination_checkpoint_successor_"
                "true_required:" + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_coordination_checkpoint_successor_"
                "false_required:" + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_specialist_analysis_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    execution = predecessor_result.get("execution") or {}
    acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_projection.get(
            "multi_agent_preview_specialist_analysis_checkpoint_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_8"
        and scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_lead_coordination_identity_invalid"
        and execution.get("new_model_nodes_started") == 2
        and execution.get("analysis_calls_preserved") == 2
        and execution.get("analysis_continuation_calls_preserved") == 1
        and execution.get("submission_attempts_preserved") == 3
        and execution.get("provider_attempts_preserved") == 5
        and execution.get("reused_workpaper_count") == 5
        and execution.get("new_initial_workpaper_nodes") == 1
        and execution.get("external_source_network_calls") == 0
        and execution.get("candidate_promotions") == 0
        and acceptance.get("true_multi_agent_preview_completed") is False
    ):
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "predecessor_invalid"
        )
    predecessor_lead = predecessor_scope.get("lead_plan_checkpoint_ref")
    predecessor_workpapers = predecessor_scope.get("workpaper_checkpoint_ref")
    for ref_field, sha_field, expected_ref in (
        (
            "lead_plan_checkpoint_ref",
            "lead_plan_checkpoint_sha256",
            predecessor_lead,
        ),
        (
            "workpaper_checkpoint_ref",
            "workpaper_checkpoint_sha256",
            predecessor_workpapers,
        ),
    ):
        bound_path, _ = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        if bound_path.relative_to(root).as_posix() != expected_ref:
            raise ValueError(
                "project_os_multi_agent_coordination_checkpoint_successor_"
                "inherited_checkpoint_drift:" + ref_field
            )

    checkpoint_path, checkpoint = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="lead_coordination_checkpoint_ref",
        sha_field="lead_coordination_checkpoint_sha256",
    )
    checkpoint_body = {
        key: value
        for key, value in checkpoint.items()
        if key != "checkpoint_digest"
    }
    if not (
        checkpoint.get("checkpoint_digest")
        == decision["lead_coordination_checkpoint_digest"]
        == canonical_digest(checkpoint_body)
        and checkpoint.get("status")
        == "six_workpapers_and_R9_lead_coordination_valid_for_downstream_resume"
        and checkpoint.get("source_authority_ref")
        == decision["predecessor_live_authority_ref"]
        and checkpoint.get("source_authority_sha256")
        == decision["predecessor_live_authority_sha256"]
        and checkpoint.get("source_public_result_ref")
        == decision["predecessor_live_result_ref"]
        and checkpoint.get("source_public_result_sha256")
        == decision["predecessor_live_result_sha256"]
        and checkpoint.get("source_public_result_digest")
        == predecessor_result.get("result_digest")
        and checkpoint.get("reused_workpaper_count") == 6
        and checkpoint.get("completed_agent_ids")
        == list(SPECIALIST_AGENT_IDS)
        and len(checkpoint.get("accepted_challenge_ids") or ()) == 3
        and len(checkpoint.get("deferred_challenge_ids") or ()) == 1
        and (checkpoint.get("resume_policy") or {}).get(
            "lead_coordination_rerun_forbidden"
        )
        is True
    ):
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "checkpoint_invalid"
        )
    terminal_path = _repo_path(
        root, str(checkpoint["source_terminal_result_ref"])
    )
    terminal = _load_json(terminal_path)
    terminal_body = {
        key: value
        for key, value in terminal.items()
        if key != "full_result_digest"
    }
    if not (
        _sha256(terminal_path) == checkpoint["source_terminal_result_sha256"]
        and terminal.get("full_result_digest")
        == checkpoint["source_terminal_result_digest"]
        == canonical_digest(terminal_body)
        and terminal.get("failure_code")
        == "multi_agent_lead_coordination_identity_invalid"
    ):
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "terminal_drift"
        )
    lead_receipt = (checkpoint.get("source_receipts") or {}).get(
        "lead_coordination"
    ) or {}
    for ref_field, sha_field in (
        ("request_capture_ref", "request_capture_sha256"),
        ("response_capture_ref", "response_capture_sha256"),
    ):
        capture_path = _repo_path(root, str(lead_receipt.get(ref_field) or ""))
        if _sha256(capture_path) != lead_receipt.get(sha_field):
            raise ValueError(
                "project_os_multi_agent_coordination_checkpoint_successor_"
                "capture_drift:" + ref_field
            )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="coordination_checkpoint_successor_zero_call_proof_ref",
        sha_field="coordination_checkpoint_successor_zero_call_proof_sha256",
        digest_field=(
            "coordination_checkpoint_successor_zero_call_proof_result_digest"
        ),
    )
    if not (
        proof.get("status")
        == (
            "R9_six_workpapers_and_lead_coordination_checkpoint_"
            "downstream_successor_zero_call_pass"
        )
        and proof.get("lead_coordination_checkpoint_digest")
        == checkpoint["checkpoint_digest"]
        and proof.get("reused_workpaper_count") == 6
        and proof.get("reused_lead_coordination_count") == 1
        and proof.get("maximum_new_model_nodes") == 8
        and (proof.get("coordination_contract_capacity_audit") or {}).get(
            "compiled_rationale_maximum_characters"
        )
        == 2200
        and (proof.get("coordination_contract_capacity_audit") or {}).get(
            "rationale_character_count"
        )
        == 1799
        and (proof.get("materialization_summary") or {}).get(
            "blocking_empty_role_ids"
        )
        == []
    ):
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "zero_call_proof_invalid"
        )

    expected_constraints = {
        "R9_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "reuse_exactly_six_validated_workpapers": True,
        "reuse_exactly_one_R9_lead_coordination_decision": True,
        "rerun_any_completed_workpaper": False,
        "rerun_lead_coordination": False,
        "downstream_execution_starts_at_three_accepted_challenge_repairs": True,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 8,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 0,
        "maximum_new_lead_coordination_model_calls": 0,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "reused_workpapers_have_no_new_token_budget": True,
        "reused_coordination_has_no_new_token_budget": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_successor_"
            "budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 5,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": False,
        "multi_agent_preview_analysis_checkpoint_successor": False,
        "multi_agent_preview_submission_checkpoint_successor": False,
        "multi_agent_preview_lead_checkpoint_downstream_successor": False,
        "multi_agent_preview_workpaper_checkpoint_downstream_successor": False,
        "multi_agent_preview_specialist_analysis_checkpoint_successor": False,
        "multi_agent_preview_coordination_checkpoint_successor": True,
        "run_scope_id": (
            MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE
        ),
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
        "checkpoint_ref": checkpoint_path.relative_to(root).as_posix(),
    }


def validate_multi_agent_preview_downstream_analysis_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one generic downstream repair-fragment successor.

    The contract is intentionally about ordered repair progress rather than a
    Cash-specific workaround. Any completed repair must be recovered from an
    immutable validated payload, while the first pending repair may resume one
    capture-bound analysis fragment exactly once.
    """

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_initial_workpaper_reruns_forbidden",
        "completed_repair_reruns_forbidden",
        "active_fragment_continuation_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "workpaper_checkpoint_ref",
        "workpaper_checkpoint_sha256",
        "lead_coordination_checkpoint_ref",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "downstream_repair_progress_checkpoint_ref",
        "downstream_repair_progress_checkpoint_sha256",
        "downstream_repair_progress_checkpoint_digest",
        "downstream_analysis_fragment_checkpoint_ref",
        "downstream_analysis_fragment_checkpoint_sha256",
        "downstream_analysis_fragment_checkpoint_digest",
        "downstream_analysis_successor_zero_call_proof_ref",
        "downstream_analysis_successor_zero_call_proof_sha256",
        "downstream_analysis_successor_zero_call_proof_result_digest",
        "analysis_continuation_profile_ref",
        "analysis_continuation_profile_sha256",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": (
            MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R10_downstream_analysis_"
            "checkpoint_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_downstream_analysis_successor_"
                "field_invalid:" + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_initial_workpaper_reruns_forbidden",
        "completed_repair_reruns_forbidden",
        "active_fragment_continuation_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_downstream_analysis_successor_"
                "true_required:" + field
            )
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_downstream_analysis_successor_"
                "false_required:" + field
            )

    _, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_coordination_checkpoint_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    _, predecessor_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_authority_ref",
        sha_field="predecessor_live_authority_sha256",
    )
    _, predecessor_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_live_result_ref",
        sha_field="predecessor_live_result_sha256",
    )
    scope_binding = (
        predecessor_authority.get("bound_inputs", {}).get(
            "project_os_scope_decision"
        )
        or {}
    )
    execution = predecessor_result.get("execution") or {}
    acceptance = predecessor_result.get("acceptance") or {}
    if not (
        predecessor_projection.get(
            "multi_agent_preview_coordination_checkpoint_successor"
        )
        is True
        and predecessor_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_9"
        and scope_binding.get("ref")
        == decision["predecessor_scope_decision_ref"]
        and scope_binding.get("sha256")
        == decision["predecessor_scope_decision_sha256"]
        and predecessor_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and predecessor_result.get("authority_ref")
        == decision["predecessor_live_authority_ref"]
        and predecessor_result.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and execution.get("new_model_nodes_started") == 2
        and execution.get("analysis_calls_preserved") == 2
        and execution.get("analysis_continuation_calls_preserved") == 0
        and execution.get("submission_attempts_preserved") == 1
        and execution.get("provider_attempts_preserved") == 3
        and execution.get("reused_workpaper_count") == 6
        and execution.get("reused_lead_coordination_count") == 1
        and execution.get("external_source_network_calls") == 0
        and execution.get("candidate_promotions") == 0
        and acceptance.get("true_multi_agent_preview_completed") is False
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "predecessor_invalid"
        )

    inherited_artifacts: dict[str, Mapping[str, Any]] = {}
    for ref_field, sha_field, expected_ref in (
        (
            "lead_plan_checkpoint_ref",
            "lead_plan_checkpoint_sha256",
            predecessor_scope.get("lead_plan_checkpoint_ref"),
        ),
        (
            "workpaper_checkpoint_ref",
            "workpaper_checkpoint_sha256",
            predecessor_scope.get("workpaper_checkpoint_ref"),
        ),
        (
            "lead_coordination_checkpoint_ref",
            "lead_coordination_checkpoint_sha256",
            predecessor_scope.get("lead_coordination_checkpoint_ref"),
        ),
    ):
        bound_path, bound_artifact = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        inherited_artifacts[ref_field] = bound_artifact
        if bound_path.relative_to(root).as_posix() != expected_ref:
            raise ValueError(
                "project_os_multi_agent_downstream_analysis_successor_"
                "inherited_checkpoint_drift:" + ref_field
            )
    if (
        decision["lead_coordination_checkpoint_digest"]
        != predecessor_scope.get("lead_coordination_checkpoint_digest")
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "coordination_digest_drift"
        )

    _, progress_raw = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="downstream_repair_progress_checkpoint_ref",
        sha_field="downstream_repair_progress_checkpoint_sha256",
    )
    progress = validate_downstream_repair_progress_checkpoint(progress_raw)
    _, fragment_raw = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="downstream_analysis_fragment_checkpoint_ref",
        sha_field="downstream_analysis_fragment_checkpoint_sha256",
    )
    fragment = validate_analysis_fragment_checkpoint(fragment_raw)
    if not (
        progress["checkpoint_digest"]
        == decision["downstream_repair_progress_checkpoint_digest"]
        and fragment["checkpoint_digest"]
        == decision["downstream_analysis_fragment_checkpoint_digest"]
        and progress["source_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and progress["source_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and progress["source_public_result_ref"]
        == decision["predecessor_live_result_ref"]
        and progress["source_public_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and progress["source_public_result_digest"]
        == predecessor_result.get("result_digest")
        and progress["source_terminal_result_ref"]
        == predecessor_result.get("full_result_ref")
        and progress["lead_coordination_checkpoint_ref"]
        == decision["lead_coordination_checkpoint_ref"]
        and progress["lead_coordination_checkpoint_sha256"]
        == decision["lead_coordination_checkpoint_sha256"]
        and progress["lead_coordination_checkpoint_digest"]
        == decision["lead_coordination_checkpoint_digest"]
        and progress["active_analysis_fragment_checkpoint_ref"]
        == decision["downstream_analysis_fragment_checkpoint_ref"]
        and progress["active_analysis_fragment_checkpoint_sha256"]
        == decision["downstream_analysis_fragment_checkpoint_sha256"]
        and progress["active_analysis_fragment_checkpoint_digest"]
        == fragment["checkpoint_digest"]
        and progress["accepted_challenge_ids"]
        == inherited_artifacts["lead_coordination_checkpoint_ref"].get(
            "accepted_challenge_ids"
        )
        and fragment["run_id"] == progress["source_run_id"]
        and fragment["source_authority_ref"]
        == decision["predecessor_live_authority_ref"]
        and fragment["source_authority_sha256"]
        == decision["predecessor_live_authority_sha256"]
        and fragment["source_public_result_ref"]
        == decision["predecessor_live_result_ref"]
        and fragment["source_public_result_sha256"]
        == decision["predecessor_live_result_sha256"]
        and fragment["source_public_result_digest"]
        == predecessor_result.get("result_digest")
        and len(progress["accepted_challenge_ids"]) == 3
        and len(progress["completed_challenge_repairs"]) == 1
        and len(progress["pending_challenge_ids"]) == 2
        and fragment["node_id"]
        == "AGENT::CASH_CONVERSION::COUNTER_REPAIR"
        and fragment["required_outputs"]
        == [
            "revised_thesis",
            "revised_sourced_claims",
            "revised_counterarguments",
            "revised_what_would_change",
        ]
        and fragment["completed_required_outputs"] == []
        and fragment["partial_required_outputs"] == ["revised_thesis"]
        and fragment["missing_required_outputs"]
        == [
            "revised_sourced_claims",
            "revised_counterarguments",
            "revised_what_would_change",
        ]
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "checkpoint_invalid"
        )

    terminal_path = _repo_path(root, progress["source_terminal_result_ref"])
    terminal = _load_json(terminal_path)
    terminal_body = {
        key: value for key, value in terminal.items() if key != "full_result_digest"
    }
    completed_node = (terminal.get("node_executions") or [None])[0] or {}
    terminal_attempt = (terminal.get("terminal_node_attempts") or [None])[0] or {}
    completed_receipt = progress["completed_challenge_repairs"][0]
    if not (
        _sha256(terminal_path) == progress["source_terminal_result_sha256"]
        and terminal.get("full_result_digest")
        == progress["source_terminal_result_digest"]
        == canonical_digest(terminal_body)
        and terminal.get("failure_code")
        == "multi_agent_preview_analysis_finish_reason_invalid:length"
        and len(terminal.get("node_executions") or ()) == 1
        and len(terminal.get("terminal_node_attempts") or ()) == 1
        and completed_node.get("node_id") == completed_receipt["node_id"]
        and (completed_node.get("validated_payload") or {}).get(
            "workpaper_digest"
        )
        == completed_receipt["workpaper_digest"]
        and terminal_attempt.get("attempt_id")
        == (
            f"{progress['source_run_id']}-"
            f"{fragment['node_id'].replace('::', '-')}-"
            "ANALYSIS-ATTEMPT-01"
        )
        and terminal_attempt.get("finish_reason") == "length"
        and terminal_attempt.get("request_digest") == fragment["request_digest"]
        and terminal_attempt.get("response_digest")
        == fragment["response_digest"]
        and terminal_attempt.get("analysis_draft_digest")
        == fragment["partial_draft_digest"]
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "terminal_drift"
        )
    for ref_field, sha_field in (
        ("request_capture_ref", "request_capture_sha256"),
        ("response_capture_ref", "response_capture_sha256"),
    ):
        capture_path = _repo_path(root, fragment[ref_field])
        if _sha256(capture_path) != fragment[sha_field]:
            raise ValueError(
                "project_os_multi_agent_downstream_analysis_successor_"
                "capture_drift:" + ref_field
            )

    _, continuation_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_continuation_profile_ref",
        sha_field="analysis_continuation_profile_sha256",
    )
    if not (
        continuation_profile.get("provider_id") == "deepseek"
        and continuation_profile.get("model") == "deepseek-v4-pro"
        and continuation_profile.get("base_url") == "https://api.deepseek.com"
        and continuation_profile.get("endpoint") == "/chat/completions"
        and continuation_profile.get("request_defaults")
        == {
            "max_tokens": 4000,
            "stream": False,
            "thinking": {"type": "enabled"},
            "reasoning_effort": "low",
        }
        and (continuation_profile.get("authority") or {}).get("retry_count")
        == 0
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "profile_invalid"
        )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="downstream_analysis_successor_zero_call_proof_ref",
        sha_field="downstream_analysis_successor_zero_call_proof_sha256",
        digest_field="downstream_analysis_successor_zero_call_proof_result_digest",
    )
    if not (
        proof.get("status")
        == "R10_downstream_repair_analysis_checkpoint_successor_zero_call_pass"
        and proof.get("downstream_repair_progress_checkpoint_digest")
        == progress["checkpoint_digest"]
        and proof.get("analysis_fragment_checkpoint_digest")
        == fragment["checkpoint_digest"]
        and proof.get("reused_completed_challenge_repair_count") == 1
        and proof.get("pending_challenge_repair_count") == 2
        and proof.get("maximum_analysis_continuation_calls") == 1
        and proof.get("maximum_new_model_nodes") == 7
        and (proof.get("mutation_results") or {}).get(
            "completed_repair_digest_mutation_rejected"
        )
        is True
        and (proof.get("mutation_results") or {}).get(
            "analysis_capture_mutation_rejected"
        )
        is True
        and (proof.get("mutation_results") or {}).get(
            "challenge_order_mutation_rejected"
        )
        is True
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "zero_call_proof_invalid"
        )

    expected_constraints = {
        "R10_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "reuse_exactly_six_initial_workpapers": True,
        "reuse_exactly_one_R9_lead_coordination_decision": True,
        "reuse_exactly_one_completed_R10_challenge_repair": True,
        "resume_exactly_one_active_analysis_fragment": True,
        "rerun_completed_challenge_repair": False,
        "rerun_lead_coordination": False,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 7,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 0,
        "maximum_new_lead_coordination_model_calls": 0,
        "maximum_resumed_downstream_analysis_continuations": 1,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "reused_completed_challenge_repair_count": 1,
        "maximum_new_counter_challenge_repairs": 2,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "reused_workpapers_have_no_new_token_budget": True,
        "reused_coordination_has_no_new_token_budget": True,
        "reused_completed_repair_has_no_new_token_budget": True,
        "continuation_basis_is_separate_for_active_fragment": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_successor_"
            "budget_policy_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": proof["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 3,
        "multi_agent_preview": True,
        "multi_agent_preview_transport_successor": False,
        "multi_agent_preview_plan_checkpoint_successor": False,
        "multi_agent_preview_analysis_checkpoint_successor": False,
        "multi_agent_preview_submission_checkpoint_successor": False,
        "multi_agent_preview_lead_checkpoint_downstream_successor": False,
        "multi_agent_preview_workpaper_checkpoint_downstream_successor": False,
        "multi_agent_preview_specialist_analysis_checkpoint_successor": False,
        "multi_agent_preview_coordination_checkpoint_successor": False,
        "multi_agent_preview_downstream_analysis_checkpoint_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "reused_completed_challenge_repair_count": 1,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def validate_multi_agent_preview_repair_context_successor_scope_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    """Validate one fresh role-scoped successor after a reasoning-only failure.

    The predecessor R10 scope remains immutable lineage.  This decision adds
    only the R14 failure disposition, a V2 progress checkpoint with two
    completed repairs, and a provider-specific task profile for one fresh
    Supply repair.  It does not broaden research inputs or product authority.
    """

    expected_fields = {
        "schema_version",
        "status",
        "case_key",
        "cell_id",
        "run_scope_id",
        "evidence_mode",
        "next_authorized_scope",
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_initial_workpaper_reruns_forbidden",
        "completed_repair_reruns_forbidden",
        "active_fragment_continuation_required",
        "fresh_role_scoped_pending_repair_required",
        "task_specific_repair_profile_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
        "predecessor_scope_decision_ref",
        "predecessor_scope_decision_sha256",
        "predecessor_live_authority_ref",
        "predecessor_live_authority_sha256",
        "predecessor_live_result_ref",
        "predecessor_live_result_sha256",
        "lead_plan_checkpoint_ref",
        "lead_plan_checkpoint_sha256",
        "workpaper_checkpoint_ref",
        "workpaper_checkpoint_sha256",
        "lead_coordination_checkpoint_ref",
        "lead_coordination_checkpoint_sha256",
        "lead_coordination_checkpoint_digest",
        "downstream_repair_progress_checkpoint_ref",
        "downstream_repair_progress_checkpoint_sha256",
        "downstream_repair_progress_checkpoint_digest",
        "downstream_analysis_fragment_checkpoint_ref",
        "downstream_analysis_fragment_checkpoint_sha256",
        "downstream_analysis_fragment_checkpoint_digest",
        "downstream_analysis_successor_zero_call_proof_ref",
        "downstream_analysis_successor_zero_call_proof_sha256",
        "downstream_analysis_successor_zero_call_proof_result_digest",
        "analysis_continuation_profile_ref",
        "analysis_continuation_profile_sha256",
        "failed_repair_authority_ref",
        "failed_repair_authority_sha256",
        "failed_repair_result_ref",
        "failed_repair_result_sha256",
        "repair_context_failure_disposition_ref",
        "repair_context_failure_disposition_sha256",
        "repair_context_failure_disposition_result_digest",
        "downstream_repair_progress_checkpoint_v2_ref",
        "downstream_repair_progress_checkpoint_v2_sha256",
        "downstream_repair_progress_checkpoint_v2_digest",
        "repair_analysis_profile_ref",
        "repair_analysis_profile_sha256",
        "successor_constraints",
        "execution_limits",
        "token_budget_basis_policy",
        "authority_statement",
    }
    if set(decision) != expected_fields:
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_shape_invalid"
        )
    required_equal = {
        "schema_version": (
            MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_SCHEMA
        ),
        "status": (
            MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "MULTI_AGENT_PREVIEW",
        "run_scope_id": MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "current_reviewed_Evidence_plus_current_S2_no_candidate_promotion"
        ),
        "next_authorized_scope": (
            "one_bounded_DELL_multi_agent_preview_R15_role_scoped_supply_"
            "repair_successor_live_attempt"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_multi_agent_repair_context_successor_field_invalid:"
                + field
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "independent_specialist_sessions_required",
        "checkpoint_resume_required",
        "lead_coordination_checkpoint_required",
        "lead_coordination_rerun_forbidden",
        "all_initial_workpaper_reruns_forbidden",
        "completed_repair_reruns_forbidden",
        "fresh_role_scoped_pending_repair_required",
        "task_specific_repair_profile_required",
        "downstream_only_execution_required",
        "conditional_writer_required",
        "evaluation_rounds_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_multi_agent_repair_context_successor_true_required:"
                + field
            )
    for field in (
        "active_fragment_continuation_required",
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "qualified_human_acceptance_authorized",
        "S1_acceptance_authorized",
        "S3_acceptance_authorized",
        "generalization_claim_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_multi_agent_repair_context_successor_false_required:"
                + field
            )

    predecessor_scope_path, predecessor_scope = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_scope_decision_ref",
        sha_field="predecessor_scope_decision_sha256",
    )
    predecessor_projection = (
        validate_multi_agent_preview_downstream_analysis_successor_scope_decision(
            root=root, decision=predecessor_scope
        )
    )
    if (
        predecessor_scope_path.relative_to(root).as_posix()
        != "configs/research/evals/fin_ia_0_1_3_s3_dell_multi_agent_preview_live_scope_decision_v1_9.json"
    ):
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_predecessor_invalid"
        )

    for ref_field, sha_field, inherited_field in (
        (
            "predecessor_live_authority_ref",
            "predecessor_live_authority_sha256",
            "predecessor_live_authority_ref",
        ),
        (
            "predecessor_live_result_ref",
            "predecessor_live_result_sha256",
            "predecessor_live_result_ref",
        ),
        (
            "lead_plan_checkpoint_ref",
            "lead_plan_checkpoint_sha256",
            "lead_plan_checkpoint_ref",
        ),
        (
            "workpaper_checkpoint_ref",
            "workpaper_checkpoint_sha256",
            "workpaper_checkpoint_ref",
        ),
        (
            "lead_coordination_checkpoint_ref",
            "lead_coordination_checkpoint_sha256",
            "lead_coordination_checkpoint_ref",
        ),
        (
            "downstream_repair_progress_checkpoint_ref",
            "downstream_repair_progress_checkpoint_sha256",
            "downstream_repair_progress_checkpoint_ref",
        ),
        (
            "downstream_analysis_fragment_checkpoint_ref",
            "downstream_analysis_fragment_checkpoint_sha256",
            "downstream_analysis_fragment_checkpoint_ref",
        ),
        (
            "downstream_analysis_successor_zero_call_proof_ref",
            "downstream_analysis_successor_zero_call_proof_sha256",
            "downstream_analysis_successor_zero_call_proof_ref",
        ),
        (
            "analysis_continuation_profile_ref",
            "analysis_continuation_profile_sha256",
            "analysis_continuation_profile_ref",
        ),
    ):
        bound_path, _ = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        if bound_path.relative_to(root).as_posix() != predecessor_scope.get(
            inherited_field
        ):
            raise ValueError(
                "project_os_multi_agent_repair_context_successor_lineage_drift:"
                + ref_field
            )
    for digest_field in (
        "lead_coordination_checkpoint_digest",
        "downstream_repair_progress_checkpoint_digest",
        "downstream_analysis_fragment_checkpoint_digest",
        "downstream_analysis_successor_zero_call_proof_result_digest",
    ):
        if decision.get(digest_field) != predecessor_scope.get(digest_field):
            raise ValueError(
                "project_os_multi_agent_repair_context_successor_digest_drift:"
                + digest_field
            )

    _, failed_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_repair_authority_ref",
        sha_field="failed_repair_authority_sha256",
    )
    _, failed_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_repair_result_ref",
        sha_field="failed_repair_result_sha256",
    )
    execution = failed_result.get("execution") or {}
    if not (
        failed_authority.get("schema_version")
        == "fin_ia_s3_dell_multi_agent_preview_live_authority_v1_13"
        and failed_authority.get("outputs", {}).get("run_id")
        == "FIN_0_1_3_S3_DELL_MULTI_AGENT_PREVIEW_R14_20260820"
        and failed_authority.get("outputs", {}).get("public_result_ref")
        == decision["failed_repair_result_ref"]
        and failed_result.get("authority_ref")
        == decision["failed_repair_authority_ref"]
        and failed_result.get("status")
        == "multi_agent_preview_terminal_failure_preserved"
        and failed_result.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and execution.get("new_model_nodes_started") == 2
        and execution.get("reused_completed_challenge_repair_count") == 1
        and execution.get("new_counter_challenge_repairs_preserved") == 1
        and execution.get("external_source_network_calls") == 0
        and execution.get("candidate_promotions") == 0
    ):
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_failure_invalid"
        )

    _, disposition = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="repair_context_failure_disposition_ref",
        sha_field="repair_context_failure_disposition_sha256",
        digest_field="repair_context_failure_disposition_result_digest",
    )
    _, progress_raw = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="downstream_repair_progress_checkpoint_v2_ref",
        sha_field="downstream_repair_progress_checkpoint_v2_sha256",
    )
    progress = validate_downstream_repair_progress_checkpoint_v2(progress_raw)
    _, repair_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="repair_analysis_profile_ref",
        sha_field="repair_analysis_profile_sha256",
    )
    if not (
        disposition.get("status")
        == "R14_role_repair_context_and_task_profile_root_cause_replay_pass"
        and disposition.get("failed_authority_ref")
        == decision["failed_repair_authority_ref"]
        and disposition.get("failed_public_result_ref")
        == decision["failed_repair_result_ref"]
        and progress["checkpoint_digest"]
        == decision["downstream_repair_progress_checkpoint_v2_digest"]
        and progress["source_authority_ref"]
        == decision["failed_repair_authority_ref"]
        and progress["source_public_result_ref"]
        == decision["failed_repair_result_ref"]
        and progress["source_public_result_digest"]
        == failed_result.get("result_digest")
        and progress["repair_context_policy_digest"]
        == disposition.get("result_digest")
        and len(progress["completed_challenge_repairs"]) == 2
        and len(progress["pending_challenge_repairs"]) == 1
        and progress["pending_challenge_repairs"][0]["target_agent_id"]
        == "AGENT::SUPPLY_RELATIONSHIP"
        and progress["resume_policy"]["maximum_analysis_continuation_calls"]
        == 0
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
        and (repair_profile.get("authority") or {}).get("retry_count") == 0
    ):
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_artifact_invalid"
        )

    expected_constraints = {
        "R14_terminal_failure_remains_immutable": True,
        "reuse_exactly_six_R3_specialist_plans": True,
        "reuse_exactly_one_validated_R6_lead_plan": True,
        "reuse_exactly_six_initial_workpapers": True,
        "reuse_exactly_one_R9_lead_coordination_decision": True,
        "reuse_exactly_two_completed_challenge_repairs": True,
        "begin_exactly_one_fresh_supply_repair": True,
        "resume_analysis_fragment": False,
        "rerun_completed_challenge_repair": False,
        "rerun_lead_coordination": False,
        "research_inputs_unchanged": True,
    }
    if decision.get("successor_constraints") != expected_constraints:
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_constraints_invalid"
        )
    expected_limits = {
        "maximum_new_model_nodes": 6,
        "maximum_new_lead_plan_model_calls": 0,
        "maximum_new_initial_workpaper_nodes": 0,
        "maximum_new_lead_coordination_model_calls": 0,
        "maximum_resumed_downstream_analysis_continuations": 0,
        "maximum_new_analysis_calls_per_other_node": 1,
        "maximum_submission_attempts_per_node": 2,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "reused_completed_challenge_repair_count": 2,
        "maximum_new_counter_challenge_repairs": 1,
        "maximum_counter_challenge_repairs": 3,
        "maximum_evaluator_repairs": 2,
        "maximum_evaluation_rounds": 2,
        "external_source_network_calls": 0,
        "candidate_promotions": 0,
        "product_publication": False,
        "qualified_human_acceptance": False,
    }
    if decision.get("execution_limits") != expected_limits:
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_limits_invalid"
        )
    expected_budget_policy = {
        "task_specific_basis_required_per_paid_phase": True,
        "reused_lead_has_no_new_token_budget": True,
        "reused_workpapers_have_no_new_token_budget": True,
        "reused_coordination_has_no_new_token_budget": True,
        "reused_completed_repairs_have_no_new_token_budget": True,
        "fresh_supply_analysis_basis_is_separate": True,
        "analysis_basis_is_separate_per_downstream_node": True,
        "submission_basis_is_separate_per_downstream_node": True,
        "input_scale_and_reference_count_required": True,
        "required_outputs_and_schema_burden_required": True,
        "materiality_and_quality_risk_required": True,
        "comparable_run_evidence_required": True,
        "reasoning_profile_required": True,
        "stop_and_truncation_behavior_required": True,
        "cost_and_latency_are_secondary_constraints": True,
    }
    if decision.get("token_budget_basis_policy") != expected_budget_policy:
        raise ValueError(
            "project_os_multi_agent_repair_context_successor_budget_invalid"
        )
    return {
        "clean_proof_status": predecessor_projection["clean_proof_status"],
        "successor_zero_call_proof_status": disposition["status"],
        "provider_id": predecessor_projection["provider_id"],
        "provider_model": predecessor_projection["provider_model"],
        "api_key_env": predecessor_projection["api_key_env"],
        "recent_provider_steps": 4,
        "multi_agent_preview": True,
        "multi_agent_preview_downstream_analysis_checkpoint_successor": False,
        "multi_agent_preview_repair_context_successor": True,
        "run_scope_id": MULTI_AGENT_PREVIEW_REPAIR_CONTEXT_SUCCESSOR_SCOPE,
        "specialist_agent_count": 6,
        "reused_specialist_plan_count": 6,
        "reused_lead_plan_count": 1,
        "reused_workpaper_count": 6,
        "reused_lead_coordination_count": 1,
        "reused_completed_challenge_repair_count": 2,
        "maximum_new_lead_plan_model_calls": 0,
        "execution_limits": dict(expected_limits),
        "token_budget_basis_policy": dict(expected_budget_policy),
    }


def _validate_material_scope_canary_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    bound = validate_material_scope_canary_authority(decision, root=root)
    input_payload = bound["input"]
    diagnostic = input_payload.get("product_diagnostic") or {}
    if not (
        input_payload.get("case_key") == "DELL"
        and len(input_payload.get("required_request_ids") or ()) == 8
        and diagnostic.get("selected_atom_count") == 8
        and diagnostic.get("deferred_atom_count") == 2
        and diagnostic.get("material_scope_required_request_count") == 8
        and diagnostic.get("material_scope_ready_request_count") == 0
        and diagnostic.get("network_calls") == 0
        and diagnostic.get("model_calls") == 0
    ):
        raise ValueError("project_os_material_scope_canary_input_invalid")
    defaults = bound["profile"].request_defaults
    node_profile = {
        "max_tokens": defaults["max_tokens"],
        "response_format": defaults["response_format"],
        "thinking": defaults["thinking"],
    }
    if "reasoning_effort" in defaults:
        node_profile["reasoning_effort"] = defaults["reasoning_effort"]
    return {
        "clean_proof_status": input_payload["status"],
        "provider_id": bound["profile"].provider_id,
        "provider_model": bound["profile"].model,
        "api_key_env": bound["api_key_env"],
        "recent_provider_steps": 0,
        "natural_material_scope_canary": True,
        "material_scope_nonthinking_successor": bound[
            "nonthinking_successor"
        ],
        "material_scope_contract_repair_successor": bound[
            "contract_repair_successor"
        ],
        "run_scope_id": decision["run_scope_id"],
        "node_profiles": {"material_scope": node_profile},
    }


def _validate_dynamic_single_cell_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": DYNAMIC_SINGLE_CELL_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_SINGLE_CELL_SCOPE,
        "evidence_mode": "current_reviewed_pack_request_scoped_reselection",
        "next_authorized_scope": (
            "one_DELL_value_capture_dynamic_single_cell_chat_live"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_decision_field_invalid:{field}"
            )

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "natural_planner_required",
        "current_S1_S2_execution_required",
        "candidate_promotion_forbidden",
        "transcript_prefeed_forbidden",
        "same_current_product_pointer_required",
        "immutable_zero_call_predecessor_required",
        "S1_RC_S1_019_remains_open",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_dynamic_decision_true_required:{field}"
            )
    for field in (
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_dynamic_decision_false_required:{field}"
            )

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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_dynamic_decision_budget_invalid")

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    zero_acceptance = zero.get("stage_acceptance") or {}
    if not (
        zero.get("schema_version")
        == "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_2"
        and zero.get("status")
        == "zero_call_dynamic_truth_spine_engineering_pass"
        and zero_acceptance.get(
            "dynamic_dell_terminal_deliverable_compiled"
        )
        is True
        and zero_acceptance.get("natural_model_planner_executed") is False
        and zero_acceptance.get("natural_model_judgment_executed") is False
    ):
        raise ValueError("project_os_dynamic_zero_call_predecessor_invalid")

    profile_specs = (
        (
            "planner_profile_ref",
            "planner_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
            {"type": "json_object"},
        ),
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
            None,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
            None,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for ref_field, sha_field, thinking, reasoning, tokens, response_format in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        common_valid = (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and "temperature" not in defaults
            and "top_p" not in defaults
        )
        reasoning_valid = (
            defaults.get("reasoning_effort") == reasoning
            if reasoning is not None
            else "reasoning_effort" not in defaults
        )
        response_format_valid = (
            defaults.get("response_format") == response_format
            if response_format is not None
            else "response_format" not in defaults
        )
        if not (common_valid and reasoning_valid and response_format_valid):
            raise ValueError(
                f"project_os_dynamic_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    repair_submission = health.get("repair_submission") or {}
    if not (
        health.get("status")
        == (
            "completed_failed_fragment_validation_repair_contract_valid_"
            "content_assessment_pending"
        )
        and (health.get("execution") or {}).get("retries") == 0
        and repair_submission.get("attempted") is True
        and repair_submission.get("finish_reason") == "tool_calls"
        and repair_submission.get("tool_call_count") == 1
    ):
        raise ValueError("project_os_dynamic_provider_health_invalid")

    return {
        "clean_proof_status": zero["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_single_cell_successor": True,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": DYNAMIC_FIVE_CELL_SCOPE,
        "evidence_mode": (
            "current_reviewed_pack_request_scoped_reselection_with_typed_gaps"
        ),
        "next_authorized_scope": "one_DELL_dynamic_five_cell_chat_exact_once",
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_decision_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError("project_os_five_cell_required_cells_invalid")

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "natural_planner_required",
        "current_S1_S2_execution_required",
        "candidate_promotion_forbidden",
        "transcript_prefeed_forbidden",
        "same_current_product_pointer_required",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "immutable_zero_call_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_decision_true_required:{field}"
            )
    for field in (
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_decision_false_required:{field}"
            )

    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_decision_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="runner_zero_call_result_ref",
        sha_field="runner_zero_call_result_sha256",
        digest_field="runner_zero_call_result_digest",
    )
    proof_acceptance = proof.get("acceptance") or {}
    replay = proof.get("current_S1_S2_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_runner_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_stable_five_cell_runner"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 59
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("case_key") == "DELL"
        and replay.get("requested_evidence_count") == 8
        and replay.get("candidate_promotions") == 0
        and tuple(replay.get("research_context_cells") or ()) == required_cells
        and proof_acceptance.get("stale_objective_binding_fails_closed") is True
        and proof_acceptance.get("success_path_exact_thirteen_calls") is True
        and proof_acceptance.get("cell_failure_does_not_hide_later_cells")
        is True
        and proof_acceptance.get("synthesis_requires_all_five_cells") is True
        and proof_acceptance.get("public_result_redacts_model_content") is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError("project_os_five_cell_runner_proof_invalid")
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "dynamic_runtime",
        "five_cell_runtime",
        "current_consumer",
        "runner_tests",
        "runtime_tests",
        "consumer_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError("project_os_five_cell_runner_proof_bindings_invalid")
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_runner_proof_bindings_invalid"
            )
        path = _repo_path(root, str(row.get("ref") or ""))
        if _sha256(path) != str(row.get("sha256") or ""):
            raise ValueError(
                f"project_os_five_cell_runner_source_drift:{name}"
            )

    _, context = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="five_cell_context_result_ref",
        sha_field="five_cell_context_result_sha256",
        digest_field="five_cell_context_result_digest",
    )
    if not (
        context.get("status")
        == "engineering_pass_zero_call_current_consumer_contract_successor"
        and (context.get("acceptance") or {}).get(
            "all_five_cells_have_role_method_pack"
        )
        is True
        and (context.get("acceptance") or {}).get(
            "all_graph_context_compiled_from_current_case"
        )
        is True
        and (context.get("acceptance") or {}).get("natural_model_quality_proven")
        is False
    ):
        raise ValueError("project_os_five_cell_context_predecessor_invalid")

    _, single = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="dynamic_single_cell_assessment_ref",
        sha_field="dynamic_single_cell_assessment_sha256",
    )
    if not (
        single.get("status")
        == (
            "dynamic_single_cell_L1_and_applicable_content_pass_"
            "S1_sync_then_five_cell"
        )
        and (single.get("acceptance") or {}).get("dynamic_single_cell_L1") is True
        and (single.get("acceptance") or {}).get(
            "DELL_value_capture_dynamic_single_cell_accepted"
        )
        is True
        and (single.get("acceptance") or {}).get("five_cell_live_authorized")
        is False
    ):
        raise ValueError("project_os_five_cell_single_cell_predecessor_invalid")

    profile_specs = (
        (
            "planner_profile_ref",
            "planner_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
            {"type": "json_object"},
        ),
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
            None,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
            None,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for (
        ref_field,
        sha_field,
        thinking,
        reasoning,
        tokens,
        response_format,
    ) in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and (
                defaults.get("response_format") == response_format
                if response_format is not None
                else "response_format" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": DYNAMIC_FIVE_CELL_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R1_planner_current_S1_S2_prefix_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_remaining_twelve_nodes_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_successor_decision_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError(
            "project_os_five_cell_successor_required_cells_invalid"
        )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "same_current_product_pointer_required",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "immutable_R1_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_successor_false_required:{field}"
            )
    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_successor_decision_budget_invalid"
        )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="successor_runner_zero_call_result_ref",
        sha_field="successor_runner_zero_call_result_sha256",
        digest_field="successor_runner_zero_call_result_digest",
    )
    proof_acceptance = proof.get("acceptance") or {}
    replay = proof.get("successor_fake_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_runner_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_stable_successor_remaining_twelve_nodes"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 65
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 12
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_planner_calls") == 1
        and replay.get("reused_predecessor_current_S1_S2") is True
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_contract_valid") is True
        and proof_acceptance.get("R1_preserved") is True
        and proof_acceptance.get("only_remaining_twelve_nodes_authorized")
        is True
        and proof_acceptance.get("natural_model_quality_proven") is False
        and proof_acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError(
            "project_os_five_cell_successor_runner_proof_invalid"
        )
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "project_os_preflight",
        "current_consumer",
        "consumer_policy",
        "runner_tests",
        "project_os_tests",
        "consumer_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError(
            "project_os_five_cell_successor_proof_bindings_invalid"
        )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_successor_proof_bindings_invalid"
            )
        path = _repo_path(root, str(row.get("ref") or ""))
        if _sha256(path) != str(row.get("sha256") or ""):
            raise ValueError(
                f"project_os_five_cell_successor_source_drift:{name}"
            )

    _, capacity = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="capacity_successor_result_ref",
        sha_field="capacity_successor_result_sha256",
        digest_field="capacity_successor_result_digest",
    )
    if not (
        capacity.get("status")
        == "engineering_pass_zero_call_R1_capacity_contract_successor"
        and (capacity.get("acceptance") or {}).get("R1_preserved") is True
        and (capacity.get("acceptance") or {}).get(
            "value_capture_five_metrics_two_periods_equal_ten"
        )
        is True
        and (capacity.get("acceptance") or {}).get(
            "successor_live_authorized"
        )
        is False
    ):
        raise ValueError(
            "project_os_five_cell_successor_capacity_proof_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    if not (
        predecessor_public.get("status")
        == "terminal_failed_or_partial_no_retry"
        and predecessor_private.get("status")
        == "terminal_failed_or_partial_no_retry"
        and (predecessor_private.get("orchestration_failure") or {}).get(
            "failure_code"
        )
        == "research_consumer_cell_capacity_exceeded"
        and (predecessor_private.get("execution") or {}).get(
            "model_calls_attempted"
        )
        == 1
        and (predecessor_private.get("execution") or {}).get(
            "cell_analysis_calls_attempted"
        )
        == 0
    ):
        raise ValueError(
            "project_os_five_cell_successor_R1_predecessor_invalid"
        )

    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "high",
            8000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    profiles: dict[str, dict[str, Any]] = {}
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_partial_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = required_cells[:2]
    remaining_cells = required_cells[2:]
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "FAILED_THREE_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_PARTIAL_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R2_prefix_two_valid_cells_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_failed_three_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_partial_successor_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("remaining_cell_ids") or ())
        == remaining_cells
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_cells_invalid"
        )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R2_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_partial_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_partial_successor_false_required:{field}"
            )
    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_partial_successor_budget_invalid"
        )

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="partial_successor_zero_call_result_ref",
        sha_field="partial_successor_zero_call_result_sha256",
        digest_field="partial_successor_zero_call_result_digest",
    )
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("partial_successor_fake_replay") or {}
    compact = proof.get("compact_analysis_projection") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_compact_analysis_partial_resume"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 70
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 8
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_cell_judgments") == 2
        and replay.get("cell_analysis_calls_attempted") == 3
        and replay.get("cell_submission_calls_attempted") == 3
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_contract_valid") is True
        and compact.get("cell_count") == 5
        and compact.get("all_authority_ref_sets_preserved") is True
        and compact.get("submission_schema_removed") is True
        and compact.get("dynamic_transport_diagnostics_removed") is True
        and min(compact.get("character_reduction_percent") or [0]) >= 15
        and acceptance.get("R2_preserved") is True
        and acceptance.get("two_valid_cells_reused_not_rerun") is True
        and acceptance.get("only_three_failed_cells_executed") is True
        and acceptance.get("compact_analysis_projection_lossless") is True
        and acceptance.get("fresh_model_calls_equal_eight") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("partial_successor_live_authorized") is False
        and acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_proof_invalid"
        )
    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "five_cell_runtime",
        "project_os_preflight",
        "runner_tests",
        "runtime_tests",
        "project_os_tests",
        "consumer_policy",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError(
            "project_os_five_cell_partial_successor_bindings_invalid"
        )
    implementation_commit = str(proof.get("implementation_commit") or "")
    proof_commit = _git_latest_commit_for_ref(
        root=root,
        ref=str(decision.get("partial_successor_zero_call_result_ref") or ""),
    )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_partial_successor_bindings_invalid"
            )
        ref = str(row.get("ref") or "")
        _repo_path(root, ref)
        expected_sha = str(row.get("sha256") or "")
        if not any(
            _git_blob_sha256(root=root, commit=commit, ref=ref) == expected_sha
            for commit in {implementation_commit, proof_commit}
        ):
            raise ValueError(
                f"project_os_five_cell_partial_successor_source_drift:{name}"
            )

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_result_ref",
        sha_field="predecessor_result_sha256",
        digest_field="predecessor_result_digest",
    )
    cells = predecessor.get("cells") or []
    if not (
        predecessor.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_successor_live_result_v1_0"
        and predecessor.get("status") == "terminal_failed_or_partial_no_retry"
        and (predecessor.get("execution") or {}).get(
            "cell_judgments_accepted"
        )
        == 2
        and len(cells) == 5
        and [row.get("cell_id") for row in cells] == list(required_cells)
        and all(cells[index].get("validated_cell_digest") for index in (0, 1))
        and all(not cells[index].get("failure_code") for index in (0, 1))
        and [cells[index].get("failure_code") for index in (2, 3, 4)]
        == [
            "model_gateway_reasoning_budget_exhausted",
            "five_cell_live_cell_analysis_length_stop",
            "model_gateway_reasoning_budget_exhausted",
        ]
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_predecessor_invalid"
        )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_failure_assessment_ref",
        sha_field="predecessor_failure_assessment_sha256",
    )
    if not (
        predecessor_assessment.get("status")
        == "terminal_partial_two_of_five_contract_valid_three_analysis_budget_exhausted"
        and predecessor_assessment.get("result_digest")
        == predecessor.get("result_digest")
        and tuple(
            (predecessor_assessment.get("successor_disposition") or {}).get(
                "remaining_cell_ids"
            )
            or ()
        )
        == remaining_cells
    ):
        raise ValueError(
            "project_os_five_cell_partial_successor_assessment_invalid"
        )

    profiles: dict[str, Any] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_partial_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 3,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_node_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::cash_conversion",
    )
    resubmission_cells = (
        "CELL::value_capture",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "TWO_SUBMISSIONS_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_NODE_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_dynamic_R3_three_valid_cells_two_analysis_drafts_no_new_evidence"
        ),
        "next_authorized_scope": (
            "one_DELL_dynamic_five_cell_two_submissions_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_node_successor_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("resubmission_cell_ids") or ())
        == resubmission_cells
    ):
        raise ValueError("project_os_five_cell_node_successor_cells_invalid")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "reuse_predecessor_analysis_drafts",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R3_predecessor_required",
        "positive_product_profit_attribution_requires_authoritative_bridge",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_node_successor_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "rerun_cell_analysis",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_node_successor_false_required:{field}"
            )
    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_node_successor_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="node_successor_zero_call_result_ref",
        sha_field="node_successor_zero_call_result_sha256",
        digest_field="node_successor_zero_call_result_digest",
    )
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("node_successor_fake_replay") or {}
    capture = proof.get("R3_capture_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_node_successor_zero_call_result_v1_0"
        and proof.get("status")
        == "engineering_pass_zero_call_R3_node_successor_strict_resubmission"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 100
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 4
        and replay.get("planner_calls_attempted") == 0
        and replay.get("current_S1_S2_executions") == 0
        and replay.get("reused_predecessor_cell_judgments") == 3
        and replay.get("reused_predecessor_analysis_drafts") == 2
        and replay.get("cell_analysis_calls_attempted") == 0
        and replay.get("cell_submission_calls_attempted") == 2
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_analysis_calls_attempted") == 1
        and replay.get("synthesis_submission_calls_attempted") == 1
        and replay.get("strict_projected_submission_tools") == 3
        and replay.get("synthesis_contract_valid") is True
        and capture.get("analysis_capture_count") == 2
        and capture.get("all_request_response_digests_match") is True
        and capture.get("all_response_bodies_complete") is True
        and capture.get("all_saved_analysis_content_matches") is True
        and acceptance.get("R3_preserved") is True
        and acceptance.get("three_valid_judgments_reused_not_rerun") is True
        and acceptance.get(
            "two_analysis_drafts_capture_verified_and_reused"
        )
        is True
        and acceptance.get("only_two_cell_submissions_executed") is True
        and acceptance.get(
            "strict_projection_applied_to_all_three_submission_tools"
        )
        is True
        and acceptance.get("fresh_model_calls_equal_four") is True
        and acceptance.get("synthesis_requires_all_five_cells") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("node_successor_live_authorized") is False
        and acceptance.get("product_publication_authorized") is False
    ):
        raise ValueError("project_os_five_cell_node_successor_proof_invalid")

    source_bindings = proof.get("source_bindings") or {}
    required_binding_names = {
        "runner",
        "five_cell_runtime",
        "strict_projection",
        "project_os_preflight",
        "runner_tests",
        "runtime_tests",
        "projection_tests",
    }
    if set(source_bindings) != required_binding_names:
        raise ValueError("project_os_five_cell_node_successor_bindings_invalid")
    implementation_commit = str(proof.get("implementation_commit") or "")
    proof_commit = _git_latest_commit_for_ref(
        root=root,
        ref=str(decision.get("node_successor_zero_call_result_ref") or ""),
    )
    for name, row in source_bindings.items():
        if not isinstance(row, Mapping):
            raise ValueError(
                "project_os_five_cell_node_successor_bindings_invalid"
            )
        ref = str(row.get("ref") or "")
        _repo_path(root, ref)
        expected_sha = str(row.get("sha256") or "")
        if not any(
            _git_blob_sha256(root=root, commit=commit, ref=ref) == expected_sha
            for commit in {implementation_commit, proof_commit}
        ):
            raise ValueError(
                f"project_os_five_cell_node_successor_source_drift:{name}"
            )

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_result_ref",
        sha_field="predecessor_result_sha256",
        digest_field="predecessor_result_digest",
    )
    cells = predecessor.get("cells") or []
    expected_valid = {0, 1, 3}
    if not (
        predecessor.get("schema_version")
        == "fin_ia_s3_dynamic_five_cell_partial_successor_live_result_v1_0"
        and predecessor.get("status") == "terminal_failed_or_partial_no_retry"
        and (predecessor.get("execution") or {}).get(
            "cell_judgments_accepted"
        )
        == 3
        and len(cells) == 5
        and [row.get("cell_id") for row in cells] == list(required_cells)
        and all(cells[index].get("validated_cell_digest") for index in expected_valid)
        and all(not cells[index].get("failure_code") for index in expected_valid)
        and cells[2].get("failure_code")
        == "research_consumer_mechanism_atom_invalid"
        and cells[4].get("failure_code")
        == "research_consumer_thesis_atom_invalid"
    ):
        raise ValueError(
            "project_os_five_cell_node_successor_predecessor_invalid"
        )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_failure_assessment_ref",
        sha_field="predecessor_failure_assessment_sha256",
    )
    if not (
        predecessor_assessment.get("status")
        == "terminal_partial_three_of_five_contract_valid_two_strict_submission_surface_rejected"
        and predecessor_assessment.get("result_digest")
        == predecessor.get("result_digest")
    ):
        raise ValueError(
            "project_os_five_cell_node_successor_assessment_invalid"
        )
    _, strict_canary = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="strict_canary_result_ref",
        sha_field="strict_canary_result_sha256",
        digest_field="strict_canary_result_digest",
    )
    if not (
        strict_canary.get("status")
        == "completed_deepseek_beta_strict_pattern_qualified"
        and (strict_canary.get("acceptance") or {}).get(
            "deepseek_beta_endpoint_accepted_schema"
        )
        is True
        and (strict_canary.get("execution") or {}).get("retries") == 0
    ):
        raise ValueError("project_os_five_cell_node_successor_canary_invalid")

    profiles: dict[str, Any] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            "https://api.deepseek.com",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            "https://api.deepseek.com/beta",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, base_url, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == base_url
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_five_cell_node_successor_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "base_url": base_url,
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_five_cell_claim_surface_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    cell_scoped_successor = (
        decision.get("schema_version")
        == DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_SCHEMA
    )
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    required_equal = {
        "status": (
            DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_DECISION_STATUS
            if cell_scoped_successor
            else DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_DECISION_STATUS
        ),
        "case_key": "DELL",
        "cell_id": "ALL_FIVE_RESEARCH_CELLS",
        "run_scope_id": (
            DYNAMIC_FIVE_CELL_CELL_SCOPED_CLAIM_SUCCESSOR_SCOPE
            if cell_scoped_successor
            else DYNAMIC_FIVE_CELL_CLAIM_SURFACE_SUCCESSOR_SCOPE
        ),
        "evidence_mode": (
            (
                "immutable_R4_planner_and_current_S1_S2_with_reviewed_exact_"
                "claim_anchor_period_bound_historical_relation_and_cell_"
                "scoped_submission_contract"
            )
            if cell_scoped_successor
            else (
                "immutable_R4_planner_and_current_S1_S2_with_reviewed_exact_"
                "claim_anchor_and_period_bound_historical_relation"
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_claim_surface_successor_field_invalid:{field}"
            )
    if tuple(decision.get("required_cell_ids") or ()) != required_cells:
        raise ValueError(
            "project_os_five_cell_claim_surface_successor_cells_invalid"
        )
    for field in (
        "reuse_predecessor_planner_and_controlled_plan",
        "rerun_all_five_analysis_and_submission_nodes",
        "same_current_product_pointer_required",
        "reviewed_exact_source_anchor_required",
        "historical_relation_is_period_bound_and_issuer_attributed",
        "historical_relation_is_not_current_quarter_causality",
        "continue_after_cell_failure",
        "synthesis_requires_all_cells",
        "chat_live_authorized",
        "credential_presence_required",
        *(
            (
                "cell_scoped_claim_contract_required",
                "typed_unexpected_exception_terminal_required",
                "failed_attempt_authority_consumed",
                "failed_attempt_reuse_forbidden",
            )
            if cell_scoped_successor
            else ()
        ),
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_true_required:"
                + field
            )
    for field in (
        "reuse_predecessor_cell_analysis_or_judgments",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_false_required:"
                + field
            )
    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_five_cell_claim_surface_successor_budget_invalid"
        )
    if cell_scoped_successor:
        if decision.get("failed_attempt_run_id") != (
            "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R5"
        ):
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_failed_attempt_invalid"
            )
        _zero_path, zero_result = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="cell_scoped_zero_call_result_ref",
            sha_field="cell_scoped_zero_call_result_sha256",
            digest_field="cell_scoped_zero_call_result_digest",
        )
        _failed_path, failed_result = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="failed_attempt_result_ref",
            sha_field="failed_attempt_result_sha256",
            digest_field="failed_attempt_result_digest",
        )
        assessment_ref = str(
            decision.get("failed_attempt_failure_assessment_ref") or ""
        )
        assessment_path = _repo_path(root, assessment_ref)
        assessment = _load_json(assessment_path)
        if not (
            _sha256(assessment_path)
            == decision.get("failed_attempt_failure_assessment_sha256")
            and assessment.get("assessment_digest")
            == decision.get("failed_attempt_failure_assessment_digest")
            and zero_result.get("status")
            == (
                "formal_zero_call_engineering_pass_"
                "fresh_live_scope_decision_pending"
            )
            and (zero_result.get("contract_proof") or {}).get(
                "nonqualified_messages_omit_claim_contracts_and_relation_aliases"
            )
            is True
            and (zero_result.get("contract_proof") or {}).get(
                "unexpected_project_exception_materializes_terminal_result"
            )
            is True
            and failed_result.get("run_id")
            == "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R5"
            and failed_result.get("status")
            == "terminal_unexpected_project_exception_preserved_no_retry"
            and (assessment.get("disposition") or {}).get(
                "R5_authority_consumed"
            )
            is True
            and (assessment.get("disposition") or {}).get(
                "R5_rerun_forbidden"
            )
            is True
        ):
            raise ValueError(
                "project_os_five_cell_claim_surface_successor_repair_artifact_invalid"
            )
    return {
        "clean_proof_status": "engineering_pass_scope_bound_zero_call_regression",
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 0,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": False,
        "dynamic_five_cell_claim_surface_successor": True,
        "dynamic_five_cell_cell_scoped_claim_contract_successor": (
            cell_scoped_successor
        ),
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {},
    }


def _validate_dynamic_five_cell_value_repair_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::value_capture",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    reused_cells = (
        "CELL::demand_quality",
        "CELL::operating_performance",
        "CELL::cash_conversion",
        "CELL::counterevidence",
    )
    resubmission_cells = ("CELL::value_capture",)
    required_equal = {
        "status": DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "VALUE_SUBMISSION_REPAIR_PLUS_SYNTHESIS",
        "run_scope_id": DYNAMIC_FIVE_CELL_VALUE_REPAIR_SUCCESSOR_SCOPE,
        "evidence_mode": (
            "immutable_R6_four_valid_cells_value_analysis_and_current_S1_S2"
        ),
        "next_authorized_scope": (
            "one_DELL_value_submission_repair_plus_synthesis_chat_exact_once"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_five_cell_value_repair_field_invalid:{field}"
            )
    if not (
        tuple(decision.get("required_cell_ids") or ()) == required_cells
        and tuple(decision.get("reused_cell_ids") or ()) == reused_cells
        and tuple(decision.get("resubmission_cell_ids") or ())
        == resubmission_cells
    ):
        raise ValueError("project_os_five_cell_value_repair_cells_invalid")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "reuse_predecessor_planner",
        "reuse_predecessor_current_S1_S2",
        "reuse_predecessor_valid_cells",
        "reuse_predecessor_value_analysis",
        "reuse_rejected_value_call_only_as_typed_feedback",
        "same_current_product_pointer_required",
        "synthesis_requires_all_cells",
        "immutable_R6_predecessor_required",
        "relation_endpoints_bind_locally",
        "structured_financial_support_is_valid_support_channel",
        "narrative_date_number_ref_gate_unchanged",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_five_cell_value_repair_true_required:{field}"
            )
    for field in (
        "rerun_planner",
        "rerun_current_S1_S2",
        "rerun_valid_cells",
        "rerun_cell_analysis",
        "harness_rewrites_model_judgment",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "candidate_promotion_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
        "heterogeneous_generalization_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_five_cell_value_repair_false_required:{field}"
            )
    expected_budget = {
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_five_cell_value_repair_budget_invalid")

    _, proof = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="value_repair_zero_call_result_ref",
        sha_field="value_repair_zero_call_result_sha256",
        digest_field="value_repair_zero_call_result_digest",
    )
    _, failed_result = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_attempt_result_ref",
        sha_field="failed_attempt_result_sha256",
        digest_field="failed_attempt_result_digest",
    )
    assessment_ref = str(decision.get("failed_attempt_failure_assessment_ref") or "")
    assessment_path = _repo_path(root, assessment_ref)
    assessment = _load_json(assessment_path)
    acceptance = proof.get("acceptance") or {}
    replay = proof.get("successor_fake_replay") or {}
    capture = proof.get("R6_capture_replay") or {}
    test_runs = proof.get("independent_test_processes") or []
    if not (
        proof.get("schema_version")
        == (
            "fin_ia_s3_dynamic_five_cell_value_submission_repair_"
            "successor_zero_call_result_v1_0"
        )
        and proof.get("status")
        == "engineering_pass_zero_call_R6_value_repair_plus_synthesis_successor"
        and isinstance(test_runs, list)
        and len(test_runs) == 2
        and all(
            isinstance(row, Mapping)
            and row.get("status") == "passed"
            and int(row.get("passed_tests") or 0) >= 100
            and row.get("model_calls") == 0
            and row.get("provider_calls") == 0
            and row.get("network_calls") == 0
            for row in test_runs
        )
        and replay.get("fresh_model_calls_attempted") == 3
        and replay.get("reused_predecessor_cell_judgments") == 4
        and replay.get("reused_predecessor_analysis_drafts") == 1
        and replay.get("cell_submission_calls_attempted") == 1
        and replay.get("cell_judgments_accepted") == 5
        and replay.get("synthesis_analysis_calls_attempted") == 1
        and replay.get("synthesis_submission_calls_attempted") == 1
        and replay.get("synthesis_contract_valid") is True
        and capture.get("analysis_capture_count") == 1
        and capture.get("all_request_response_digests_match") is True
        and capture.get("all_response_bodies_complete") is True
        and capture.get("saved_analysis_content_matches") is True
        and capture.get("rejected_submission_digest_matches") is True
        and capture.get("rejected_submission_replays_to_typed_failure")
        == "research_consumer_thesis_atom_invalid"
        and acceptance.get("R6_preserved") is True
        and acceptance.get("four_valid_judgments_reused_not_rerun") is True
        and acceptance.get("value_analysis_capture_verified_and_reused") is True
        and acceptance.get("rejected_value_submission_not_promoted") is True
        and acceptance.get("relation_endpoints_bind_locally") is True
        and acceptance.get("structured_financial_support_recognized") is True
        and acceptance.get("only_one_typed_value_repair_submission") is True
        and acceptance.get("synthesis_requires_all_five_cells") is True
        and acceptance.get("natural_model_quality_proven") is False
        and acceptance.get("successor_live_authorized") is False
        and failed_result.get("status")
        == "terminal_failed_or_partial_no_retry"
        and failed_result.get("result_digest")
        == decision.get("failed_attempt_result_digest")
        and _sha256(assessment_path)
        == decision.get("failed_attempt_failure_assessment_sha256")
        and assessment.get("assessment_digest")
        == decision.get("failed_attempt_failure_assessment_digest")
        and assessment.get("run_id") == "FIN013-S3-DELL-DYNAMIC-FIVE-CELL-R6"
        and (assessment.get("disposition") or {}).get("R6_authority_consumed")
        is True
        and (assessment.get("disposition") or {}).get("R6_rerun_forbidden")
        is True
    ):
        raise ValueError("project_os_five_cell_value_repair_proof_invalid")
    return {
        "clean_proof_status": proof["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 10,
        "dynamic_five_cell_successor": False,
        "dynamic_five_cell_remaining_nodes_successor": False,
        "dynamic_five_cell_partial_successor": False,
        "dynamic_five_cell_node_successor": False,
        "dynamic_five_cell_claim_surface_successor": False,
        "dynamic_five_cell_cell_scoped_claim_contract_successor": False,
        "dynamic_five_cell_value_repair_successor": True,
        "dynamic_single_cell_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {},
    }


def _validate_dynamic_counter_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    decision_schema = decision.get("schema_version")
    historical_binding = decision_schema in {
        DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA_V1_1,
        DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA,
    }
    authority_contract_v1_2 = (
        decision_schema == DYNAMIC_COUNTER_SUCCESSOR_DECISION_SCHEMA
    )
    required_equal = {
        "status": (
            DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS
            if authority_contract_v1_2
            else (
                DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_1
                if historical_binding
                else DYNAMIC_COUNTER_SUCCESSOR_DECISION_STATUS_V1_0
            )
        ),
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_COUNTER_SUCCESSOR_SCOPE,
        "evidence_mode": "immutable_dynamic_R1_prefix_no_new_evidence",
        "next_authorized_scope": (
            "one_DELL_dynamic_counter_WWC_analysis_submission_successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_counter_decision_field_invalid:{field}"
            )

    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "immutable_successful_prefix_reuse_required",
        "failed_node_only_required",
        "max_thinking_analysis_required",
        "non_thinking_submission_required",
        "predecessor_R1_remains_failed",
        "same_current_product_pointer_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_dynamic_counter_decision_true_required:{field}"
            )
    if historical_binding:
        for field in (
            "historical_git_blob_validation_required",
            "current_runtime_policies_directly_bound",
            "obsolete_v1_0_identity_reuse_forbidden",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_dynamic_counter_decision_true_required:"
                    f"{field}"
                )
    if authority_contract_v1_2:
        for field in (
            "real_authority_fixture_shape_required",
            "obsolete_v1_1_identity_reuse_forbidden",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_dynamic_counter_decision_true_required:"
                    f"{field}"
                )
    for field in (
        "planner_rerun_authorized",
        "current_S1_S2_rerun_authorized",
        "thesis_or_mechanism_rerun_authorized",
        "new_evidence_authorized",
        "candidate_promotion_authorized",
        "contract_relaxation_authorized",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "automatic_second_analysis_retry_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_dynamic_counter_decision_false_required:{field}"
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
    if decision.get("execution_budget") != expected_budget:
        raise ValueError("project_os_dynamic_counter_decision_budget_invalid")

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    zero_acceptance = zero.get("acceptance") or {}
    replay = zero.get("replay_observation") or {}
    expected_zero_schema = (
        "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
        "zero_call_result_"
        + (
            "v1_2"
            if authority_contract_v1_2
            else ("v1_1" if historical_binding else "v1_0")
        )
    )
    expected_zero_status = (
        "zero_call_failed_counter_successor_authority_contract_engineering_pass"
        if authority_contract_v1_2
        else (
            "zero_call_failed_counter_successor_historical_binding_"
            "engineering_pass"
            if historical_binding
            else "zero_call_failed_counter_successor_engineering_pass"
        )
    )
    if not (
        zero.get("schema_version") == expected_zero_schema
        and zero.get("status") == expected_zero_status
        and zero_acceptance.get("immutable_successful_prefix_reused") is True
        and zero_acceptance.get("failed_counter_context_recompiled_exactly")
        is True
        and zero_acceptance.get("failed_counter_messages_recompiled_exactly")
        is True
        and zero_acceptance.get("new_evidence_or_candidate_promotion") is False
        and zero_acceptance.get("natural_successor_executed") is False
        and replay.get("successful_predecessor_model_nodes_reused") == 5
        and replay.get("failed_analysis_step_absent") is True
        and replay.get("failed_submission_step_absent") is True
        and replay.get("failed_validated_fragment_absent") is True
        and all(
            value == 0 for value in (zero.get("observed_calls") or {}).values()
        )
    ):
        raise ValueError("project_os_dynamic_counter_zero_call_invalid")
    if historical_binding and not (
        zero_acceptance.get(
            "historical_authority_validated_from_immutable_git_commit"
        )
        is True
        and zero_acceptance.get("current_runtime_policies_directly_bound")
        is True
        and (
            zero_acceptance.get("obsolete_v1_0_identity_reuse_forbidden")
            is True
            if not authority_contract_v1_2
            else zero_acceptance.get(
                "obsolete_v1_0_and_v1_1_identity_reuse_forbidden"
            )
            is True
        )
    ):
        raise ValueError(
            "project_os_dynamic_counter_historical_acceptance_invalid"
        )
    if authority_contract_v1_2 and zero_acceptance.get(
        "real_authority_fixture_shape_validated"
    ) is not True:
        raise ValueError(
            "project_os_dynamic_counter_authority_contract_acceptance_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    predecessor_execution = predecessor_public.get("execution") or {}
    if not (
        predecessor_public.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_result_v1_0"
        and predecessor_public.get("status") == "terminal_failed_no_retry"
        and predecessor_public.get("failure_code")
        == "model_gateway_generation_budget_exhausted"
        and predecessor_public.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and predecessor_execution.get("model_calls_attempted") == 6
        and predecessor_execution.get("fragment_tool_calls_accepted") == 2
    ):
        raise ValueError("project_os_dynamic_counter_predecessor_public_invalid")

    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    failed_rows = [
        row
        for row in predecessor_private.get("fragment_steps") or ()
        if row.get("fragment_tool")
        == "submit_research_counterargument_and_wwc"
    ]
    if not (
        predecessor_private.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_full_v1_0"
        and predecessor_private.get("status") == "terminal_failed_no_retry"
        and predecessor_private.get("full_result_digest")
        == decision.get("predecessor_private_result_digest")
        and set(predecessor_private.get("accepted_fragments") or {})
        == {"submit_research_thesis", "submit_research_mechanism"}
        and len(failed_rows) == 1
        and not failed_rows[0].get("analysis_step")
        and not failed_rows[0].get("submission_step")
        and not failed_rows[0].get("validated_fragment")
    ):
        raise ValueError("project_os_dynamic_counter_predecessor_private_invalid")

    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failure_assessment_ref",
        sha_field="failure_assessment_sha256",
    )
    disposition = assessment.get("successor_disposition") or {}
    if not (
        assessment.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_live_failure_assessment_v1_0"
        and assessment.get("status")
        == "terminal_failed_counter_WWC_analysis_generation_budget_exhausted"
        and disposition.get("preserve_R1") is True
        and disposition.get("maximum_fresh_model_calls") == 2
        and disposition.get("rerun_natural_planner") is False
        and disposition.get("rerun_current_S1_S2") is False
        and disposition.get("rerun_thesis_or_mechanism") is False
        and disposition.get("retry_count") == 0
        and disposition.get("new_evidence_or_authority") is False
        and disposition.get("contract_relaxation") is False
    ):
        raise ValueError("project_os_dynamic_counter_assessment_invalid")

    runner_path = _repo_path(root, str(decision.get("runner_ref") or ""))
    runner_digest = (
        _git_blob_sha256(
            root=root,
            commit=str(decision.get("implementation_commit") or ""),
            ref=str(decision.get("runner_ref") or ""),
        )
        if authority_contract_v1_2
        else _sha256(runner_path)
    )
    if runner_digest != str(decision.get("runner_sha256") or ""):
        raise ValueError("project_os_dynamic_counter_runner_drift")

    if historical_binding:
        _, obsolete_authority = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="obsolete_entry_authority_ref",
            sha_field="obsolete_entry_authority_sha256",
        )
        _, obsolete_failure = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="obsolete_entry_failure_ref",
            sha_field="obsolete_entry_failure_sha256",
        )
        _, predecessor_authority = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="predecessor_authority_ref",
            sha_field="predecessor_authority_sha256",
        )
        if not (
            obsolete_authority.get("schema_version")
            == (
                "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
                "authority_v1_0"
            )
            and obsolete_failure.get("status")
            == "entry_failed_zero_model_calls_historical_runner_current_path_drift"
            and sum((obsolete_failure.get("observed_calls") or {}).values()) == 0
            and predecessor_authority.get("schema_version")
            == "fin_ia_s3_dynamic_single_cell_live_authority_v1_0"
            and predecessor_authority.get("implementation_commit")
            == "ba02a24b3d01bdb70898e8ca09e442c50a09562f"
        ):
            raise ValueError(
                "project_os_dynamic_counter_historical_binding_invalid"
            )
        if authority_contract_v1_2:
            _, obsolete_authority_v1_1 = _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field="obsolete_entry_authority_v1_1_ref",
                sha_field="obsolete_entry_authority_v1_1_sha256",
            )
            _, obsolete_failure_v1_1 = _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field="obsolete_entry_failure_v1_1_ref",
                sha_field="obsolete_entry_failure_v1_1_sha256",
            )
            if not (
                obsolete_authority_v1_1.get("schema_version")
                == (
                    "fin_ia_s3_dynamic_single_cell_failed_counter_successor_"
                    "authority_v1_1"
                )
                and obsolete_failure_v1_1.get("status")
                == "entry_failed_zero_model_calls_current_policy_required_set_omission"
                and sum(
                    (obsolete_failure_v1_1.get("observed_calls") or {}).values()
                )
                == 0
            ):
                raise ValueError(
                    "project_os_dynamic_counter_authority_contract_history_invalid"
                )
        for ref_field, sha_field in (
            ("loop_policy_ref", "loop_policy_sha256"),
            ("dynamic_micro_policy_ref", "dynamic_micro_policy_sha256"),
        ):
            _validate_artifact_binding(
                root=root,
                decision=decision,
                ref_field=ref_field,
                sha_field=sha_field,
            )

    profiles: dict[str, dict[str, Any]] = {}
    profile_specs = (
        (
            "analysis_profile_ref",
            "analysis_profile_sha256",
            {"type": "enabled"},
            "max",
            16000,
        ),
        (
            "submission_profile_ref",
            "submission_profile_sha256",
            {"type": "disabled"},
            None,
            2000,
        ),
    )
    for ref_field, sha_field, thinking, reasoning, tokens in profile_specs:
        _, profile = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field=ref_field,
            sha_field=sha_field,
        )
        defaults = profile.get("request_defaults") or {}
        if not (
            profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("base_url") == "https://api.deepseek.com"
            and profile.get("endpoint") == "/chat/completions"
            and (profile.get("authority") or {}).get("retry_count") == 0
            and defaults.get("stream") is False
            and defaults.get("thinking") == thinking
            and defaults.get("max_tokens") == tokens
            and (
                defaults.get("reasoning_effort") == reasoning
                if reasoning is not None
                else "reasoning_effort" not in defaults
            )
            and "response_format" not in defaults
            and "temperature" not in defaults
            and "top_p" not in defaults
        ):
            raise ValueError(
                f"project_os_dynamic_counter_provider_profile_invalid:{ref_field}"
            )
        profiles[ref_field] = {
            "thinking": thinking,
            "reasoning_effort": reasoning,
            "max_tokens": tokens,
        }

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    repair_submission = health.get("repair_submission") or {}
    if not (
        health.get("status")
        == (
            "completed_failed_fragment_validation_repair_contract_valid_"
            "content_assessment_pending"
        )
        and (health.get("execution") or {}).get("retries") == 0
        and repair_submission.get("attempted") is True
        and repair_submission.get("finish_reason") == "tool_calls"
        and repair_submission.get("tool_call_count") == 1
    ):
        raise ValueError("project_os_dynamic_counter_provider_health_invalid")

    return {
        "clean_proof_status": zero["status"],
        "predecessor_status": predecessor_public["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_counter_successor": True,
        "historical_binding_version": (
            "v1_2"
            if authority_contract_v1_2
            else ("v1_1_obsolete" if historical_binding else "v1_0_obsolete")
        ),
        "micro_judgment_successor": False,
        "node_profiles": profiles,
    }


def _validate_dynamic_temporal_repair_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "schema_version": DYNAMIC_TEMPORAL_REPAIR_DECISION_SCHEMA,
        "status": DYNAMIC_TEMPORAL_REPAIR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": DYNAMIC_TEMPORAL_REPAIR_SCOPE,
        "evidence_mode": "immutable_dynamic_R3_same_evidence_no_new_evidence",
        "next_authorized_scope": (
            "one_non_thinking_counter_temporal_repair_submission"
        ),
        "terminal_failure_code": (
            "finance_loop_micro_temporal_relation_unbound"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_dynamic_temporal_repair_field_invalid:{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "temporal_authority_required",
        "immutable_successful_nodes_reuse_required",
        "rejected_fragment_preserved_as_failure_evidence",
        "same_current_product_pointer_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_dynamic_temporal_repair_true_required:"
                f"{field}"
            )
    for field in (
        "planner_rerun_authorized",
        "current_S1_S2_rerun_authorized",
        "thesis_or_mechanism_rerun_authorized",
        "counter_analysis_rerun_authorized",
        "new_evidence_authorized",
        "candidate_promotion_authorized",
        "contract_relaxation_authorized",
        "automatic_second_repair_authorized",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "external_source_network_authorized",
        "five_cell_authorized",
        "product_publication_authorized",
        "S3_acceptance_authorized",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_dynamic_temporal_repair_false_required:"
                f"{field}"
            )
    expected_budget = {
        "successful_predecessor_model_nodes_reused": 6,
        "rejected_predecessor_submission_reused_as_business_truth": False,
        "maximum_fresh_model_calls": 1,
        "maximum_transport_attempts": 1,
        "maximum_counter_repair_submission_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
        "external_source_network_calls": 0,
        "protocol_switches": 0,
        "current_product_pointer_mutations": 0,
    }
    if decision.get("execution_budget") != expected_budget:
        raise ValueError(
            "project_os_dynamic_temporal_repair_budget_invalid"
        )

    _, zero = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="zero_call_result_ref",
        sha_field="zero_call_result_sha256",
        digest_field="zero_call_result_digest",
    )
    if not (
        zero.get("schema_version")
        == "fin_ia_s3_dynamic_truth_spine_zero_call_result_v1_3"
        and zero.get("status")
        == "zero_call_dynamic_truth_spine_engineering_pass"
        and (zero.get("stage_acceptance") or {}).get(
            "unbound_cross_item_temporal_relation_fails_closed"
        )
        is True
        and (zero.get("observed_counts") or {}).get("model_calls") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_zero_call_invalid"
        )

    _, predecessor_public = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_public_result_ref",
        sha_field="predecessor_public_result_sha256",
        digest_field="predecessor_public_result_digest",
    )
    _, predecessor_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_private_result_ref",
        sha_field="predecessor_private_result_sha256",
    )
    _, base_private = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="base_predecessor_private_result_ref",
        sha_field="base_predecessor_private_result_sha256",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="content_assessment_ref",
        sha_field="content_assessment_sha256",
    )
    if not (
        predecessor_public.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_result_v1_1"
        and predecessor_public.get("status")
        == "completed_dynamic_counter_successor_contract_valid_content_assessment_pending"
        and predecessor_private.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_full_v1_1"
        and predecessor_private.get("status")
        == "completed_dynamic_counter_successor_contract_valid_content_assessment_pending"
        and predecessor_private.get("full_result_digest")
        == decision.get("predecessor_private_result_digest")
        and base_private.get("full_result_digest")
        == decision.get("base_predecessor_private_result_digest")
        and predecessor_private.get("predecessor_private_result_digest")
        == base_private.get("full_result_digest")
        and assessment.get("schema_version")
        == "fin_ia_s3_dynamic_single_cell_failed_counter_successor_content_assessment_v1_0"
        and assessment.get("status")
        == "dynamic_single_cell_contract_pass_L1_fail_temporal_relation_overreach_repair_required"
        and (assessment.get("root_cause") or {}).get("issue_id")
        == "RC-S3-028-dynamic-narrative-temporal-relation-unbound"
        and (assessment.get("disposition") or {}).get(
            "maximum_future_model_calls_after_zero_call_proof"
        )
        == 1
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_predecessor_invalid"
        )

    for ref_field, sha_field in (
        ("runner_ref", "runner_sha256"),
        ("bounded_loop_ref", "bounded_loop_sha256"),
    ):
        if _sha256(_repo_path(root, str(decision.get(ref_field) or ""))) != str(
            decision.get(sha_field) or ""
        ):
            raise ValueError(
                f"project_os_dynamic_temporal_repair_runtime_drift:{ref_field}"
            )
    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("base_url") == "https://api.deepseek.com"
        and profile.get("endpoint") == "/chat/completions"
        and defaults.get("stream") is False
        and defaults.get("thinking") == {"type": "disabled"}
        and defaults.get("max_tokens") == 2000
        and "reasoning_effort" not in defaults
        and (profile.get("authority") or {}).get("retry_count") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_profile_invalid"
        )
    predecessor_submission = predecessor_public.get("submission") or {}
    if not (
        predecessor_submission.get("finish_reason") == "tool_calls"
        and (predecessor_public.get("execution") or {}).get("retries") == 0
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_provider_health_invalid"
        )
    return {
        "clean_proof_status": zero["status"],
        "predecessor_status": predecessor_public["status"],
        "provider_id": "deepseek",
        "provider_model": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
        "recent_provider_steps": 1,
        "dynamic_temporal_repair_successor": True,
        "dynamic_counter_successor": False,
        "micro_judgment_successor": False,
        "node_profiles": {
            "submission_profile_ref": {
                "thinking": {"type": "disabled"},
                "reasoning_effort": None,
                "max_tokens": 2000,
            }
        },
    }


def _validate_failed_fragment_submission_successor_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": FAILED_FRAGMENT_SUBMISSION_SUCCESSOR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R6_failed_counter_submission_"
            "successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_submission_successor_decision_field_invalid:"
                f"{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "immutable_successful_prefix_reused",
        "immutable_counter_analysis_reused",
        "failed_node_only_execution_required",
        "non_thinking_submission_required",
        "reasoning_effort_omitted_required",
        "terminal_contract_parity_required",
        "clock_derived_authority_timestamp_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_submission_successor_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "successful_predecessor_nodes_rerun",
        "analysis_node_rerun",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_submission_successor_decision_false_required:"
                f"{field}"
            )
    numeric_equal = {
        "successful_predecessor_model_calls_reused": 5,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_submission_successor_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    replay = (clean.get("normalized_proof") or {}).get(
        "saved_r6_non_thinking_submission_successor_replay"
    ) or {}
    if not (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and (clean.get("acceptance") or {}).get(
            "saved_r6_submission_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and replay.get("successful_predecessor_model_calls_reused") == 5
        and replay.get("fresh_model_calls_in_successor") == 1
        and replay.get("reasoning_effort_omitted") is True
        and replay.get("fake_only_not_business_promotion") is True
        and replay.get("harness_generated_research_judgment") is False
    ):
        raise ValueError("project_os_submission_successor_clean_proof_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_result_ref",
        sha_field="immutable_failed_result_sha256",
        digest_field="immutable_failed_result_digest",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_result_assessment_ref",
        sha_field="failed_result_assessment_sha256",
    )
    if not (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and failed.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("model_calls_attempted") == 6
        and (failed.get("execution") or {}).get("tool_calls_accepted") == 2
        and (failed.get("execution") or {}).get("retries") == 0
        and (assessment.get("root_cause") or {}).get("owner_layer")
        == "S3_replaceable_DeepSeek_contract_submission_profile"
    ):
        raise ValueError("project_os_submission_successor_failed_R6_invalid")

    _, fixture = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_successor_fixture_ref",
        sha_field="submission_successor_fixture_sha256",
    )
    if not (
        fixture.get("source_result_sha256")
        == decision.get("immutable_failed_result_sha256")
        and fixture.get("source_result_digest")
        == decision.get("immutable_failed_result_digest")
        and fixture.get("failed_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and set(fixture.get("accepted_fragments") or {})
        == {"submit_research_thesis", "submit_research_mechanism"}
        and bool(str(fixture.get("counter_analysis_content") or ""))
        and fixture.get("private_reasoning_persisted") is False
        and fixture.get("manual_fragment_or_tool_payload_constructed") is False
    ):
        raise ValueError("project_os_submission_successor_fixture_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and (profile.get("authority") or {}).get("retry_count") == 0
        and defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and "reasoning_effort" not in defaults
    ):
        raise ValueError("project_os_submission_successor_profile_invalid")
    return {
        "clean_proof_status": clean["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": 6,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": False,
        "failed_fragment_submission_successor": True,
        "successful_predecessor_model_calls_reused": 5,
        "fresh_model_calls_authorized": 1,
        "node_profiles": {
            "contract_submission": {
                "thinking": "disabled",
                "reasoning_effort": "omitted",
                "max_tokens": defaults["max_tokens"],
            }
        },
    }


def _validate_fragment_validation_repair_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": FRAGMENT_VALIDATION_REPAIR_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "failed_fragment_tool": "submit_research_counterargument_and_wwc",
        "terminal_failure_code": "claim_surface_narrative_relation_conflict",
        "run_scope_id": FRAGMENT_VALIDATION_REPAIR_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_R7_failed_counter_validation_repair"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_validation_repair_decision_field_invalid:"
                f"{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "immutable_successful_prefix_reused",
        "rejected_fragment_preserved",
        "failed_node_only_execution_required",
        "typed_validation_feedback_required",
        "non_thinking_submission_required",
        "terminal_contract_parity_required",
        "clock_derived_authority_timestamp_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_validation_repair_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "successful_predecessor_nodes_rerun",
        "analysis_node_rerun",
        "causal_guard_relaxation",
        "manual_text_rewrite",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_validation_repair_decision_false_required:"
                f"{field}"
            )
    numeric_equal = {
        "successful_predecessor_model_calls_reused": 6,
        "maximum_fresh_model_calls": 1,
        "maximum_provider_transport_attempts": 1,
        "maximum_tool_calls": 1,
        "maximum_submission_completion_tokens": 2000,
        "maximum_repair_turns": 1,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_validation_repair_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    replay = (clean.get("normalized_proof") or {}).get(
        "saved_r7_validation_repair_successor_replay"
    ) or {}
    if not (
        clean.get("status") == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and (clean.get("acceptance") or {}).get(
            "saved_r7_validation_repair_successor_replay_pass"
        )
        is True
        and replay.get("predecessor_failure_code")
        == "claim_surface_narrative_relation_conflict"
        and replay.get("successful_predecessor_model_calls_reused") == 6
        and replay.get("fresh_model_calls_in_repair_successor") == 1
        and replay.get("maximum_repair_turns") == 1
        and replay.get("typed_tool_feedback_sequence") is True
        and replay.get("local_causal_guard_preserved") is True
        and replay.get("rejected_fragment_promoted_to_business_truth") is False
        and replay.get("harness_generated_research_judgment") is False
    ):
        raise ValueError("project_os_validation_repair_clean_proof_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_result_ref",
        sha_field="immutable_failed_result_sha256",
        digest_field="immutable_failed_result_digest",
    )
    _, assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_result_assessment_ref",
        sha_field="failed_result_assessment_sha256",
    )
    if not (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == "claim_surface_narrative_relation_conflict"
        and failed.get("failed_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("fresh_model_calls_attempted") == 1
        and (failed.get("execution") or {}).get(
            "successful_predecessor_model_calls_reused"
        )
        == 5
        and (failed.get("execution") or {}).get("retries") == 0
        and (assessment.get("root_cause") or {}).get("financial_L1_observed")
        is True
        and (assessment.get("root_cause") or {}).get(
            "local_validator_false_positive"
        )
        is False
    ):
        raise ValueError("project_os_validation_repair_failed_R7_invalid")

    _, fixture = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="rejected_fragment_fixture_ref",
        sha_field="rejected_fragment_fixture_sha256",
    )
    if not (
        fixture.get("source_result_sha256")
        == decision.get("immutable_failed_result_sha256")
        and fixture.get("source_result_digest")
        == decision.get("immutable_failed_result_digest")
        and fixture.get("fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and fixture.get("rejected_fragment_digest")
        == replay.get("rejected_fragment_digest")
    ):
        raise ValueError("project_os_validation_repair_fixture_invalid")

    _, profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    defaults = profile.get("request_defaults") or {}
    if not (
        profile.get("wire_api") == "openai_compatible_chat_completions"
        and profile.get("provider_id") == "deepseek"
        and profile.get("model") == "deepseek-v4-pro"
        and (profile.get("authority") or {}).get("retry_count") == 0
        and defaults
        == {
            "max_tokens": 2000,
            "stream": False,
            "thinking": {"type": "disabled"},
        }
        and "reasoning_effort" not in defaults
    ):
        raise ValueError("project_os_validation_repair_profile_invalid")
    return {
        "clean_proof_status": clean["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": profile["provider_id"],
        "provider_model": profile["model"],
        "api_key_env": profile["api_key_env"],
        "recent_provider_steps": 1,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": False,
        "failed_fragment_submission_successor": False,
        "fragment_validation_repair_successor": True,
        "successful_predecessor_model_calls_reused": 6,
        "fresh_model_calls_authorized": 1,
        "maximum_repair_turns": 1,
        "node_profiles": {
            "contract_submission_repair": {
                "thinking": "disabled",
                "reasoning_effort": "omitted",
                "max_tokens": defaults["max_tokens"],
            }
        },
    }


def _validate_claim_local_boundary_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    route_identifier_successor = (
        decision.get("schema_version")
        == FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA
    )
    causal_polarity_successor = decision.get("schema_version") in {
        FULL_FRAGMENT_CAUSAL_POLARITY_DECISION_SCHEMA,
        FULL_FRAGMENT_WWC_ROUTE_IDENTIFIER_DECISION_SCHEMA,
    }
    required_equal = {
        "status": FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_clean_synced_exact_once_DELL_value_capture_full_three_"
            "fragment_analysis_submission_Chat_"
            + (
                "R6"
                if route_identifier_successor
                else ("R5" if causal_polarity_successor else "R4")
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_claim_local_decision_field_invalid:"
                f"{field}"
            )
    true_fields = [
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "terminal_contract_parity_required",
        "fragment_surface_contract_parity_required",
        "claim_local_evidence_roles_required",
        "deterministic_report_evidence_summary_required",
        "global_support_laundering_forbidden",
        "typed_bridge_gap_boundary_required",
        "typed_same_scope_counter_boundary_required",
        "clock_derived_authority_timestamp_required",
    ]
    true_fields.extend(
        (
            "saved_R3_regression_replay_required",
            "saved_R4_causal_polarity_replay_required",
            "clause_scoped_causal_guard_required",
            "negated_or_unsupported_causal_surface_allowed",
            "ambiguous_single_character_cjk_term_forbidden",
            "positive_cross_scope_causal_surface_fail_closed",
        )
        if causal_polarity_successor
        else ("saved_R3_replay_required",)
    )
    if route_identifier_successor:
        true_fields.extend(
            (
                "saved_R5_route_identifier_replay_required",
                "registered_document_identifier_only_in_wwc_route_required",
                "unregistered_or_financial_numeric_surface_fail_closed",
                "document_identifier_in_narrative_fail_closed",
            )
        )
    for field in true_fields:
        if decision.get(field) is not True:
            raise ValueError(
                "project_os_claim_local_decision_true_required:"
                f"{field}"
            )
    for field in (
        "historical_failure_promoted",
        "immutable_thesis_predecessor_reused",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "heterogeneous_generalization_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                "project_os_claim_local_decision_false_required:"
                f"{field}"
            )
    numeric_equal = {
        "maximum_model_calls": 6,
        "maximum_provider_transport_attempts": 6,
        "maximum_tool_calls": 3,
        "maximum_analysis_completion_tokens_per_call": 8000,
        "maximum_submission_completion_tokens_per_call": 2000,
        "maximum_total_completion_tokens": 30000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                "project_os_claim_local_decision_budget_invalid:"
                f"{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    normalized_proof = clean.get("normalized_proof") or {}
    replay = normalized_proof.get(
        "saved_r3_claim_local_boundary_replay"
    ) or {}
    r4_replay = normalized_proof.get("saved_r4_causal_polarity_replay") or {}
    r5_replay = normalized_proof.get(
        "saved_r5_wwc_route_identifier_replay"
    ) or {}
    clean_acceptance = clean.get("acceptance") or {}
    common_clean_valid = (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and clean_acceptance.get("saved_r3_terminal_replay_pass") is True
        and clean_acceptance.get("natural_model_submission_proven") is False
        and replay.get("claim_local_roles_preserved") is True
        and replay.get("report_level_summary_deterministic") is True
        and set(replay.get("boundary_authority_sources") or ())
        == {
            "typed_bridge_gap_relation",
            "typed_same_scope_counter_relation",
        }
        and (replay.get("mutation_failure_codes") or {}).get(
            "global_support_laundering"
        )
        == "claim_surface_required_authority_missing"
        and (replay.get("mutation_failure_codes") or {}).get(
            "typed_boundary_removed"
        )
        == "claim_authority_multi_driver_boundary_missing"
    )
    causal_clean_valid = (
        r4_replay.get("predecessor_failure_code")
        == "claim_surface_narrative_relation_conflict"
        and r4_replay.get("judgment_status") == "bounded_support"
        and r4_replay.get("inference_authority") == "bounded_inference"
        and r4_replay.get("claim_scope") == "multi_scope"
        and r4_replay.get("financial_scope") == "multi_scope_financial"
        and r4_replay.get("causal_bridge_authority")
        == "multi_driver_context_only"
        and r4_replay.get("clause_scoped_guard") is True
        and r4_replay.get("negated_or_unsupported_causal_surface_pass")
        is True
        and r4_replay.get(
            "single_character_cjk_substring_not_authoritative"
        )
        is True
        and r4_replay.get("positive_cross_scope_causal_surface_fail_closed")
        is True
        and set(r4_replay.get("boundary_authority_sources") or ())
        == {
            "typed_bridge_gap_relation",
            "typed_same_scope_counter_relation",
        }
        and r4_replay.get("model_narratives_preserved_exactly") is True
        and r4_replay.get("harness_generated_research_judgment") is False
        and (r4_replay.get("mutation_failure_codes") or {}).get(
            "positive_cross_scope_causal_zh"
        )
        == "claim_surface_narrative_relation_conflict"
        and (r4_replay.get("mutation_failure_codes") or {}).get(
            "positive_cross_scope_causal_en"
        )
        == "claim_surface_narrative_relation_conflict"
    )
    route_identifier_clean_valid = (
        not route_identifier_successor
        or (
            clean_acceptance.get("saved_r5_terminal_replay_pass") is True
            and r5_replay.get("predecessor_failure_code")
            == "research_consumer_wwc_evidence_route_invalid"
            and r5_replay.get("qualified_document_identifier") == "10-Q"
            and r5_replay.get("qualified_route_preserved_exactly") is True
            and r5_replay.get("field_scoped_numeric_surface_guard") is True
            and r5_replay.get("unregistered_numeric_surface_fail_closed")
            is True
            and r5_replay.get("model_narratives_preserved_exactly") is True
            and r5_replay.get("harness_generated_research_judgment") is False
            and set((r5_replay.get("mutation_failure_codes") or {}))
            == {
                "percentage_after_qualified_identifier",
                "year_after_qualified_identifier",
                "unknown_digit_identifier",
                "url_with_qualified_identifier",
                "document_identifier_in_narrative",
            }
        )
    )
    if not (
        common_clean_valid
        and (not causal_polarity_successor or causal_clean_valid)
        and route_identifier_clean_valid
    ):
        raise ValueError("project_os_claim_local_clean_proof_invalid")

    _, disposition = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="scope_disposition_ref",
        sha_field="scope_disposition_sha256",
    )
    if not (
        disposition.get("status")
        == (
            "approved_fresh_full_three_fragment_analysis_submission_Chat_"
            + (
                "R6"
                if route_identifier_successor
                else ("R5" if causal_polarity_successor else "R4")
            )
        )
        and disposition.get("decision_digest")
        == decision.get("scope_disposition_decision_digest")
        and (disposition.get("execution_budget") or {}).get(
            "maximum_model_calls"
        )
        == 6
        and disposition.get("claim_local_evidence_roles_required") is True
        and disposition.get("typed_bridge_gap_boundary_required") is True
        and disposition.get("typed_same_scope_counter_boundary_required")
        is True
        and disposition.get("prior_failed_attempt_reused") is False
        and disposition.get("dynamic_agentic_research_authorized") is False
        and (
            not causal_polarity_successor
            or (
                disposition.get("clause_scoped_causal_guard_required")
                is True
                and disposition.get(
                    "negated_or_unsupported_causal_surface_allowed"
                )
                is True
                and disposition.get(
                    "ambiguous_single_character_cjk_term_forbidden"
                )
                is True
                and disposition.get(
                    "positive_cross_scope_causal_surface_fail_closed"
                )
                is True
            )
        )
        and (
            not route_identifier_successor
            or (
                disposition.get(
                    "registered_document_identifier_only_in_wwc_route_required"
                )
                is True
                and disposition.get(
                    "unregistered_or_financial_numeric_surface_fail_closed"
                )
                is True
                and disposition.get(
                    "document_identifier_in_narrative_fail_closed"
                )
                is True
            )
        )
    ):
        raise ValueError("project_os_claim_local_disposition_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_assessment_ref",
        sha_field="predecessor_assessment_sha256",
    )
    if not (
        predecessor.get("status")
        == "completed_fragment_contract_valid_content_assessment_pending"
        and predecessor_assessment.get("status")
        == "single_thesis_L1_pass_content_materially_improved_two_hypotheses_qualified_no_automatic_expansion"
        and decision.get("immutable_thesis_predecessor_reused") is False
    ):
        raise ValueError("project_os_claim_local_predecessor_invalid")

    _, failed = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_failed_full_fragment_result_ref",
        sha_field="immutable_failed_full_fragment_result_sha256",
        digest_field="immutable_failed_full_fragment_result_digest",
    )
    _, failed_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="failed_full_fragment_assessment_ref",
        sha_field="failed_full_fragment_assessment_sha256",
    )
    failed_valid = (
        failed.get("status") == "terminal_failed_no_retry"
        and failed.get("failure_code")
        == (
            "research_consumer_wwc_evidence_route_invalid"
            if route_identifier_successor
            else (
                "claim_surface_narrative_relation_conflict"
                if causal_polarity_successor
                else "finance_loop_micro_evidence_role_conflict"
            )
        )
        and failed.get("failure_fragment_tool")
        == "submit_research_counterargument_and_wwc"
        and (failed.get("execution") or {}).get("model_calls_attempted") == 6
        and (failed.get("execution") or {}).get("tool_calls_accepted") == 3
        and (failed.get("execution") or {}).get("retries") == 0
        and failed_assessment.get("status")
        == (
            "terminal_contract_failure_wwc_document_identifier_numeric_"
            "surface_false_positive_new_attempt_required"
            if route_identifier_successor
            else (
                "terminal_contract_failure_clause_and_negation_blind_lexical_"
                "guard_false_positive_new_attempt_required"
                if causal_polarity_successor
                else "terminal_contract_failure_claim_local_evidence_role_and_"
                "typed_boundary_aggregation_defect_new_attempt_required"
            )
        )
        and (failed_assessment.get("disposition") or {}).get(
            "immutable_R4_preserved"
            if causal_polarity_successor and not route_identifier_successor
            else (
                "immutable_R5_preserved"
                if route_identifier_successor
                else "immutable_R3_preserved"
            )
        )
        is True
    )
    if not failed_valid:
        raise ValueError("project_os_claim_local_failed_R3_invalid")

    _, analysis_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_profile_ref",
        sha_field="analysis_profile_sha256",
    )
    _, submission_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    for profile in (analysis_profile, submission_profile):
        if not (
            profile.get("wire_api")
            == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_claim_local_profile_invalid")
    analysis_defaults = analysis_profile.get("request_defaults") or {}
    submission_defaults = submission_profile.get("request_defaults") or {}
    if not (
        analysis_defaults.get("reasoning_effort") == "high"
        and analysis_defaults.get("max_tokens") == 8000
        and submission_defaults.get("reasoning_effort") == "low"
        and submission_defaults.get("max_tokens") == 2000
    ):
        raise ValueError("project_os_claim_local_profile_budget_drift")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "prior_failed_full_fragment_status": failed["status"],
        "provider_id": analysis_profile["provider_id"],
        "provider_model": analysis_profile["model"],
        "api_key_env": analysis_profile["api_key_env"],
        "recent_provider_steps": 6,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": True,
        "relation_role_successor": False,
        "claim_local_boundary_successor": True,
        "causal_polarity_successor": causal_polarity_successor,
        "wwc_route_identifier_successor": route_identifier_successor,
        "node_profiles": {
            "fragment_analysis": {
                "reasoning_effort": analysis_defaults["reasoning_effort"],
                "max_tokens": analysis_defaults["max_tokens"],
            },
            "contract_submission": {
                "reasoning_effort": submission_defaults[
                    "reasoning_effort"
                ],
                "max_tokens": submission_defaults["max_tokens"],
            },
        },
    }


def _validate_full_fragment_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    surface_successor = (
        decision.get("schema_version")
        in {
            FULL_FRAGMENT_SURFACE_FIXED_PACK_DECISION_SCHEMA,
            FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA,
        }
    )
    relation_role_successor = (
        decision.get("schema_version")
        == FULL_FRAGMENT_RELATION_ROLE_FIXED_PACK_DECISION_SCHEMA
    )
    required_equal = {
        "status": FULL_FRAGMENT_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            (
                "one_clean_synced_exact_once_DELL_value_capture_full_three_"
                "fragment_analysis_submission_Chat_R3"
            )
            if relation_role_successor
            else (
                "one_clean_synced_exact_once_DELL_value_capture_full_three_"
                "fragment_analysis_submission_Chat_live"
            )
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_full_fragment_decision_field_invalid:{field}"
            )
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "same_evidence_pack",
        "terminal_contract_parity_required",
    ):
        if decision.get(field) is not True:
            raise ValueError(
                f"project_os_full_fragment_decision_true_required:{field}"
            )
    if surface_successor:
        for field in (
            "fragment_surface_contract_parity_required",
            "saved_R1_replay_required",
            "final_QF_surface_rendering_required",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_full_fragment_decision_true_required:"
                    f"{field}"
                )
    if relation_role_successor:
        for field in (
            "relation_support_set_v1_2_required",
            "saved_R2_replay_required",
            "fragment_local_disposition_required",
            "clock_derived_authority_timestamp_required",
        ):
            if decision.get(field) is not True:
                raise ValueError(
                    "project_os_full_fragment_decision_true_required:"
                    f"{field}"
                )
    for field in (
        "historical_failure_promoted",
        "immutable_thesis_predecessor_reused",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(
                f"project_os_full_fragment_decision_false_required:{field}"
            )
    numeric_equal = {
        "maximum_model_calls": 6,
        "maximum_provider_transport_attempts": 6,
        "maximum_tool_calls": 3,
        "maximum_analysis_completion_tokens_per_call": 8000,
        "maximum_submission_completion_tokens_per_call": 2000,
        "maximum_total_completion_tokens": 30000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(
                f"project_os_full_fragment_decision_budget_invalid:{field}"
            )

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    expected_clean_status = (
        "zero_call_relation_support_and_fragment_local_disposition_pass"
        if relation_role_successor
        else "zero_call_full_fragment_sequence_and_terminal_judgment_pass_predecessor_not_reusable"
    )
    if not (
        clean.get("status") == expected_clean_status
        and (
            clean.get("fresh_process_results_byte_equivalent") is True
            if relation_role_successor
            else (clean.get("fresh_process") or {}).get("byte_equivalent")
            is True
        )
        and (clean.get("immutable_predecessor") or {}).get(
            "reuse_in_full_judgment_authorized"
        )
        is False
        and (
            (
                (clean.get("terminal_compilation") or {}).get(
                    "harness_generated_research_judgment"
                )
                is False
            )
            if relation_role_successor
            else (clean.get("full_fake_sequence") or {})
            .get("terminal_judgment", {})
            .get("harness_generated_research_judgment")
            is False
        )
        and (
            not surface_successor
            or (
                (
                    relation_role_successor
                    or (clean.get("surface_contract") or {}).get(
                        "saved_R1_replay_failure"
                    )
                    == "finance_loop_micro_narrative_invalid"
                )
                and (clean.get("surface_contract") or {}).get(
                    "final_deliverable_QF_surface_preserved"
                )
                is True
            )
        )
        and (
            not relation_role_successor
            or (
                (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_thesis_replay_pass"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_mechanism_replay_pass"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "saved_R2_context_role_preserved"
                )
                is True
                and (clean.get("relation_role_contract") or {}).get(
                    "context_only_required_support_mutation_failure"
                )
                == "finance_loop_micro_required_authority_missing"
                and (clean.get("terminal_compilation") or {}).get(
                    "judgment_status"
                )
                == "bounded_support"
                and (clean.get("terminal_compilation") or {}).get(
                    "inference_authority"
                )
                == "bounded_inference"
            )
        )
    ):
        raise ValueError("project_os_full_fragment_clean_proof_invalid")

    _, disposition = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="scope_disposition_ref",
        sha_field="scope_disposition_sha256",
    )
    expected_disposition_status = (
        "approved_fresh_full_three_fragment_analysis_submission_Chat_R3"
        if relation_role_successor
        else "approved_fresh_full_three_fragment_analysis_submission_Chat_live"
    )
    if not (
        disposition.get("status") == expected_disposition_status
        and disposition.get("execution_budget", {}).get(
            "maximum_model_calls"
        )
        == 6
        and disposition.get("dynamic_agentic_research_authorized") is False
        and (
            not surface_successor
            or (
                (
                    relation_role_successor
                    or disposition.get("surface_contract_v1_1_required")
                    is True
                )
                and disposition.get("prior_failed_attempt_reused") is False
            )
        )
        and (
            not relation_role_successor
            or disposition.get("relation_support_set_v1_2_required") is True
        )
    ):
        raise ValueError("project_os_full_fragment_disposition_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    _, predecessor_assessment = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="predecessor_assessment_ref",
        sha_field="predecessor_assessment_sha256",
    )
    if not (
        predecessor.get("status")
        == "completed_fragment_contract_valid_content_assessment_pending"
        and (predecessor.get("execution") or {}).get("retries") == 0
        and predecessor_assessment.get("status")
        == "single_thesis_L1_pass_content_materially_improved_two_hypotheses_qualified_no_automatic_expansion"
        and decision.get("immutable_thesis_predecessor_reused") is False
    ):
        raise ValueError("project_os_full_fragment_predecessor_invalid")

    prior_failed_status = ""
    if surface_successor:
        _, prior_failed = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="immutable_failed_full_fragment_result_ref",
            sha_field="immutable_failed_full_fragment_result_sha256",
            digest_field="immutable_failed_full_fragment_result_digest",
        )
        _, prior_failed_assessment = _validate_artifact_binding(
            root=root,
            decision=decision,
            ref_field="failed_full_fragment_assessment_ref",
            sha_field="failed_full_fragment_assessment_sha256",
        )
        expected_failure_code = (
            "finance_loop_micro_required_authority_missing"
            if relation_role_successor
            else "finance_loop_micro_narrative_invalid"
        )
        expected_failure_fragment = (
            "submit_research_mechanism"
            if relation_role_successor
            else "submit_research_thesis"
        )
        expected_assessment_status = (
            "terminal_contract_failure_relation_evidence_role_and_"
            "fragment_disposition_compilation_defect_new_attempt_required"
            if relation_role_successor
            else "terminal_contract_failure_project_surface_projection_"
            "defect_new_attempt_required"
        )
        expected_preserved_field = (
            "immutable_R2_preserved"
            if relation_role_successor
            else "same_attempt_retry_forbidden"
        )
        if not (
            prior_failed.get("status") == "terminal_failed_no_retry"
            and prior_failed.get("failure_code") == expected_failure_code
            and prior_failed.get("failure_fragment_tool")
            == expected_failure_fragment
            and (prior_failed.get("execution") or {}).get("retries") == 0
            and prior_failed_assessment.get("status")
            == expected_assessment_status
            and (prior_failed_assessment.get("disposition") or {}).get(
                expected_preserved_field
            )
            is True
        ):
            raise ValueError(
                "project_os_full_fragment_failed_predecessor_invalid"
            )
        prior_failed_status = str(prior_failed["status"])

    _, analysis_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="analysis_profile_ref",
        sha_field="analysis_profile_sha256",
    )
    _, submission_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="submission_profile_ref",
        sha_field="submission_profile_sha256",
    )
    for profile in (analysis_profile, submission_profile):
        if not (
            profile.get("wire_api") == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_full_fragment_provider_profile_invalid")
    analysis_defaults = analysis_profile.get("request_defaults") or {}
    submission_defaults = submission_profile.get("request_defaults") or {}
    if not (
        analysis_defaults.get("reasoning_effort") == "high"
        and analysis_defaults.get("max_tokens")
        == decision.get("maximum_analysis_completion_tokens_per_call")
        and submission_defaults.get("reasoning_effort") == "low"
        and submission_defaults.get("max_tokens")
        == decision.get("maximum_submission_completion_tokens_per_call")
    ):
        raise ValueError("project_os_full_fragment_provider_profile_budget_drift")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "prior_failed_full_fragment_status": prior_failed_status,
        "provider_id": analysis_profile["provider_id"],
        "provider_model": analysis_profile["model"],
        "api_key_env": analysis_profile["api_key_env"],
        "recent_provider_steps": 2,
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": False,
        "full_fragment_judgment_successor": True,
        "relation_role_successor": relation_role_successor,
        "node_profiles": {
            "fragment_analysis": {
                "reasoning_effort": analysis_defaults["reasoning_effort"],
                "max_tokens": analysis_defaults["max_tokens"],
            },
            "contract_submission": {
                "reasoning_effort": submission_defaults["reasoning_effort"],
                "max_tokens": submission_defaults["max_tokens"],
            },
        },
    }


def _validate_micro_fixed_pack_decision(
    *, root: Path, decision: Mapping[str, Any]
) -> dict[str, Any]:
    required_equal = {
        "status": MICRO_FIXED_PACK_DECISION_STATUS,
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_micro_judgment_Chat_successor"
        ),
    }
    for field, expected in required_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_micro_decision_field_invalid:{field}")
    for field in (
        "replacement_is_new_attempt_not_retry",
        "chat_live_authorized",
        "credential_presence_required",
        "canonical_live_gate_required",
        "same_evidence_pack",
    ):
        if decision.get(field) is not True:
            raise ValueError(f"project_os_micro_decision_true_required:{field}")
    for field in (
        "historical_failure_promoted",
        "responses_live_authorized",
        "anthropic_live_authorized",
        "dynamic_layer_two_authorized",
        "five_cell_live_authorized",
        "product_publication_authorized",
        "reasoning_or_token_limit_increase",
    ):
        if decision.get(field) is not False:
            raise ValueError(f"project_os_micro_decision_false_required:{field}")
    numeric_equal = {
        "maximum_model_calls": 4,
        "maximum_provider_transport_attempts": 4,
        "maximum_tool_calls": 5,
        "maximum_read_completion_tokens": 2000,
        "maximum_judgment_completion_tokens_per_call": 8000,
        "maximum_total_completion_tokens": 26000,
        "maximum_evidence_requests": 0,
        "retries": 0,
        "fallbacks": 0,
    }
    for field, expected in numeric_equal.items():
        if decision.get(field) != expected:
            raise ValueError(f"project_os_micro_decision_budget_invalid:{field}")

    _, clean = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="clean_zero_call_result_ref",
        sha_field="clean_zero_call_result_sha256",
        digest_field="clean_zero_call_result_digest",
    )
    clean_acceptance = clean.get("acceptance") or {}
    if not (
        clean.get("status")
        == "zero_call_micro_judgment_fresh_process_proof_pass"
        and clean.get("fresh_process_results_byte_equivalent") is True
        and clean_acceptance.get("natural_model_submission_proven") is False
        and clean_acceptance.get("fixed_pack_layer_one_accepted") is False
        and clean_acceptance.get("dynamic_agentic_research_authorized") is False
    ):
        raise ValueError("project_os_micro_clean_proof_acceptance_invalid")

    _, proof_authority = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_zero_call_authority_ref",
        sha_field="micro_zero_call_authority_sha256",
    )
    if (
        proof_authority.get("authority_id")
        != decision.get("formal_zero_call_authority_id")
        or proof_authority.get("status")
        != "fresh_zero_network_zero_model_bounded_finance_loop_proof_authorized"
    ):
        raise ValueError("project_os_micro_proof_authority_invalid")

    _, predecessor = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="immutable_predecessor_result_ref",
        sha_field="immutable_predecessor_result_sha256",
        digest_field="immutable_predecessor_result_digest",
    )
    if not (
        predecessor.get("status") == "terminal_failed_no_retry"
        and predecessor.get("failure_code")
        == "model_gateway_reasoning_budget_exhausted"
        and (predecessor.get("execution") or {}).get("retries") == 0
        and (predecessor.get("execution") or {}).get("fallbacks") == 0
    ):
        raise ValueError("project_os_micro_predecessor_invalid")

    _, capacity = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="prior_capacity_assessment_ref",
        sha_field="prior_capacity_assessment_sha256",
    )
    if not (
        capacity.get("status")
        == (
            "terminal_capacity_failure_preserved_"
            "monolithic_judgment_successor_required"
        )
        and capacity.get("result_digest") == predecessor.get("result_digest")
        and (capacity.get("acceptance") or {}).get(
            "fixed_pack_layer_one_accepted"
        )
        is False
    ):
        raise ValueError("project_os_micro_capacity_assessment_invalid")

    _, read_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_read_profile_ref",
        sha_field="micro_read_profile_sha256",
    )
    _, judgment_profile = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="micro_judgment_profile_ref",
        sha_field="micro_judgment_profile_sha256",
    )
    for profile in (read_profile, judgment_profile):
        if not (
            profile.get("wire_api") == "openai_compatible_chat_completions"
            and profile.get("provider_id") == "deepseek"
            and profile.get("model") == "deepseek-v4-pro"
            and (profile.get("authority") or {}).get("retry_count") == 0
        ):
            raise ValueError("project_os_micro_provider_profile_invalid")
    read_defaults = read_profile.get("request_defaults") or {}
    judgment_defaults = judgment_profile.get("request_defaults") or {}
    if not (
        read_defaults.get("reasoning_effort") == "low"
        and read_defaults.get("max_tokens")
        == decision.get("maximum_read_completion_tokens")
        and judgment_defaults.get("reasoning_effort") == "high"
        and judgment_defaults.get("max_tokens")
        == decision.get("maximum_judgment_completion_tokens_per_call")
    ):
        raise ValueError("project_os_micro_provider_profile_budget_drift")

    _, health = _validate_artifact_binding(
        root=root,
        decision=decision,
        ref_field="provider_health_evidence_ref",
        sha_field="provider_health_evidence_sha256",
        digest_field="provider_health_evidence_result_digest",
    )
    if not (
        health.get("status")
        == "completed_contract_valid_content_assessment_pending"
        and (health.get("execution") or {}).get("retries") == 0
        and health.get("provider_steps")
    ):
        raise ValueError("project_os_provider_health_evidence_invalid")
    return {
        "clean_proof_status": clean["status"],
        "predecessor_status": predecessor["status"],
        "capacity_assessment_status": capacity["status"],
        "provider_id": read_profile["provider_id"],
        "provider_model": read_profile["model"],
        "api_key_env": read_profile["api_key_env"],
        "recent_provider_steps": len(health["provider_steps"]),
        "claim_relation_alias_capacity_successor": False,
        "micro_judgment_successor": True,
        "node_profiles": {
            "tool_routing": {
                "reasoning_effort": read_defaults["reasoning_effort"],
                "max_tokens": read_defaults["max_tokens"],
            },
            "bounded_financial_judgment": {
                "reasoning_effort": judgment_defaults["reasoning_effort"],
                "max_tokens": judgment_defaults["max_tokens"],
            },
        },
    }


def _scope_blocker_projection(
    *, root: Path, run_scope_id: str
) -> dict[str, Any]:
    ledger = _latest_jsonl_rows(
        _repo_path(root, "docs/project_os/root_cause_issue_ledger.jsonl"),
        "issue_id",
    )
    blocked: list[str] = []
    explicitly_allowed: list[str] = []
    closed_preconditions: list[str] = []
    out_of_scope: list[str] = []
    for issue_id, row in sorted(ledger.items()):
        if row.get("full_chain_blocker") is not True:
            if (
                issue_id
                == "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
                and str(row.get("status") or "").startswith("closed_")
                and bool(row.get("current_evidence_refs"))
                and bool(str(row.get("verification_result") or ""))
            ):
                closed_preconditions.append(issue_id)
            continue
        blocking = {str(value) for value in row.get("blocking_run_scopes") or ()}
        allowed = {str(value) for value in row.get("allowed_run_scopes") or ()}
        if run_scope_id in allowed:
            explicitly_allowed.append(issue_id)
            continue
        if "*" in blocking or run_scope_id in blocking or (not blocking and not allowed):
            blocked.append(issue_id)
        else:
            out_of_scope.append(issue_id)
    if blocked:
        raise ValueError("project_os_scope_blocked:" + ",".join(blocked))
    required_claim_surface_issue = (
        "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use"
    )
    if (
        required_claim_surface_issue not in explicitly_allowed
        and required_claim_surface_issue not in closed_preconditions
    ):
        raise ValueError("project_os_claim_surface_scope_allowance_missing")
    return {
        "blocking_issue_ids": blocked,
        "explicit_allow_issue_ids": explicitly_allowed,
        "closed_precondition_issue_ids": closed_preconditions,
        "out_of_scope_full_chain_blocker_count": len(out_of_scope),
    }


def _issue_explicitly_allows(
    *, root: Path, issue_id: str, allowed_scope: str
) -> bool:
    ledger = _latest_jsonl_rows(
        _repo_path(root, "docs/project_os/root_cause_issue_ledger.jsonl"),
        "issue_id",
    )
    issue = ledger.get(issue_id) or {}
    return allowed_scope in {
        str(value) for value in issue.get("allowed_run_scopes") or ()
    }


def _repository_projection(root: Path) -> dict[str, Any]:
    def git(*args: str) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    head = git("rev-parse", "HEAD")
    upstream = git("rev-parse", "@{upstream}")
    porcelain = git("status", "--porcelain")
    if head != upstream:
        raise ValueError("project_os_repository_not_synced")
    if porcelain:
        raise ValueError("project_os_repository_not_clean")
    return {"head": head, "upstream": upstream, "clean": True, "synced": True}


def build_preflight(
    *,
    root: Path,
    decision_ref: str,
    environment: Mapping[str, str] | None = None,
    check_repository: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    project_os_digests: dict[str, str] = {}
    for ref in REQUIRED_PROJECT_OS_REFS:
        path = _repo_path(root, ref)
        if path.suffix == ".json":
            _load_json(path)
        elif path.suffix == ".jsonl":
            key = "issue_id" if "root_cause" in ref else "capability_id"
            _latest_jsonl_rows(path, key)
        elif not path.read_text(encoding="utf-8").strip():
            raise ValueError(f"project_os_document_empty:{ref}")
        project_os_digests[ref] = _sha256(path)

    decision_path = _repo_path(root, decision_ref)
    decision = _load_json(decision_path)
    decision_projection = _validate_fixed_pack_decision(root=root, decision=decision)
    scope_projection = _scope_blocker_projection(
        root=root, run_scope_id=str(decision["run_scope_id"])
    )
    if (
        decision_projection.get("multi_agent_preview") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-002-old-five-cell-workflow-lacked-independent-role-"
                "coordination-and-feedback-loop"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_preview_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_plan_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-003-multi-agent-node-couples-max-thinking-analysis-"
                "and-strict-contract-submission"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_plan_successor_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_analysis_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-005-agent-analysis-one-shot-has-no-fragment-"
                "checkpoint-feedback-or-continuation"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_analysis_successor_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_submission_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-006-analysis-continuation-validator-conflates-"
                "partial-and-missing-fields"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_submission_successor_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_lead_checkpoint_downstream_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-007-lead-plan-cardinality-schema-validator-and-"
                "feedback-drift"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_lead_checkpoint_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_workpaper_checkpoint_downstream_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-008-empty-reference-placeholder-schema-validator-"
                "and-nested-feedback-drift"
            ),
            allowed_scope=(
                MULTI_AGENT_PREVIEW_WORKPAPER_CHECKPOINT_SUCCESSOR_SCOPE
            ),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_workpaper_checkpoint_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_specialist_analysis_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-009-counterevidence-analysis-exhausts-reasoning-"
                "budget-without-context-continuity"
            ),
            allowed_scope=(
                MULTI_AGENT_PREVIEW_SPECIALIST_ANALYSIS_SUCCESSOR_SCOPE
            ),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_specialist_analysis_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_coordination_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-010-lead-coordination-rationale-capacity-and-"
                "error-classification-drift"
            ),
            allowed_scope=(
                MULTI_AGENT_PREVIEW_COORDINATION_CHECKPOINT_SUCCESSOR_SCOPE
            ),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_coordination_checkpoint_scope_allowance_missing"
        )
    if (
        decision_projection.get(
            "multi_agent_preview_downstream_analysis_checkpoint_successor"
        )
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-AR-011-downstream-repair-analysis-length-lacks-general-"
                "checkpoint-resume"
            ),
            allowed_scope=(
                MULTI_AGENT_PREVIEW_DOWNSTREAM_ANALYSIS_SUCCESSOR_SCOPE
            ),
        )
    ):
        raise ValueError(
            "project_os_multi_agent_downstream_analysis_scope_allowance_missing"
        )
    if (
        decision_projection.get("natural_material_scope_canary") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S1-024-generic-query-facets-and-shortlist-fusion-drop-"
                "proposition-materiality-and-temporal-pairs"
            ),
            allowed_scope=str(decision_projection["run_scope_id"]),
        )
    ):
        raise ValueError(
            "project_os_material_scope_canary_scope_allowance_missing"
        )
    if (
        decision_projection.get("material_scope_nonthinking_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S1-026-material-scope-max-thinking-exhausts-visible-"
                "contract-budget"
            ),
            allowed_scope=MATERIAL_SCOPE_SUCCESSOR_RUN_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_material_scope_successor_scope_allowance_missing"
        )
    if (
        decision_projection.get("material_scope_contract_repair_successor")
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S1-027-material-scope-model-visible-contract-omits-"
                "validator-vocabulary-and-shape"
            ),
            allowed_scope=MATERIAL_SCOPE_CONTRACT_REPAIR_RUN_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_material_scope_contract_repair_scope_allowance_missing"
        )
    if (
        decision.get("status")
        == (
            "fixed_pack_claim_relation_alias_capacity_zero_call_pass_"
            "one_chat_successor_authorized"
        )
        and "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget"
        not in scope_projection["explicit_allow_issue_ids"]
    ):
        raise ValueError("project_os_claim_relation_alias_scope_allowance_missing")
    if (
        decision_projection.get("micro_judgment_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence"
            ),
            allowed_scope=(
                "one_exact_once_natural_fixed_pack_micro_successor_after_all_gates"
            ),
        )
    ):
        raise ValueError("project_os_micro_judgment_scope_allowance_missing")
    if (
        decision_projection.get("full_fragment_judgment_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence"
            ),
            allowed_scope=(
                "one_full_fixed_pack_new_attempt_after_engineering_and_"
                "authority_gates"
            ),
        )
    ):
        raise ValueError("project_os_full_fragment_scope_allowance_missing")
    if (
        decision_projection.get("failed_fragment_submission_successor")
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-022-contract-submission-thinking-profile-semantic-"
                "mismatch"
            ),
            allowed_scope=FIXED_PACK_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_failed_fragment_submission_scope_allowance_missing"
        )
    if (
        decision_projection.get("fragment_validation_repair_successor")
        is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-023-model-counterargument-positive-causal-overreach-"
                "and-missing-bounded-validation-repair"
            ),
            allowed_scope=FRAGMENT_VALIDATION_REPAIR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_fragment_validation_repair_scope_allowance_missing"
        )
    if (
        decision_projection.get("dynamic_counter_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-025-dynamic-counter-WWC-analysis-high-thinking-"
                "nonconvergence"
            ),
            allowed_scope=DYNAMIC_COUNTER_SUCCESSOR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_dynamic_counter_scope_allowance_missing"
        )
    if (
        decision_projection.get("dynamic_temporal_repair_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-028-dynamic-narrative-temporal-relation-unbound"
            ),
            allowed_scope=DYNAMIC_TEMPORAL_REPAIR_SCOPE,
        )
    ):
        raise ValueError(
            "project_os_dynamic_temporal_repair_scope_allowance_missing"
        )
    if decision_projection.get("dynamic_five_cell_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_remaining_nodes_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-031-five-cell-route-metric-bundle-and-consumer-capacity-contract-mismatch",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_remaining_nodes_scope_allowance_missing"
            )
    if decision_projection.get("dynamic_five_cell_partial_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-032-five-cell-analysis-view-duplication-and-shared-reasoning-output-budget",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_partial_scope_allowance_missing"
            )
    if decision_projection.get("dynamic_five_cell_node_successor") is True:
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_node_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_value_repair_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
            "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
            "RC-S3-036-global-claim-authority-contract-leaks-value-relations-into-nonqualified-cells",
            "RC-S3-037-value-numeric-relation-endpoint-redundancy-and-structured-support-not-recognized",
        }
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_value_repair_scope_allowance_missing"
            )
    if (
        decision_projection.get("dynamic_five_cell_claim_surface_successor")
        is True
    ):
        required_allowances = {
            "RC-S2-004-product-operating-metric-and-profit-bridge-authority-missing",
            "RC-S3-014-claim-surface-model-view-contract-density-exhausts-reasoning-budget",
            "RC-S3-015-monolithic-final-judgment-max-thinking-nonconvergence",
            "RC-S3-033-strict-tool-semantic-surface-predicate-not-encoded-in-server-schema",
            "RC-S3-035-reviewed-claim-exact-source-hidden-by-prefix-projection",
        }
        if decision_projection.get(
            "dynamic_five_cell_cell_scoped_claim_contract_successor"
        ) is True:
            required_allowances.add(
                "RC-S3-036-global-claim-authority-contract-leaks-value-"
                "relations-into-nonqualified-cells"
            )
        actual_allowances = set(scope_projection["explicit_allow_issue_ids"])
        if not required_allowances.issubset(actual_allowances):
            raise ValueError(
                "project_os_dynamic_five_cell_claim_surface_scope_allowance_missing"
            )
    if (
        decision_projection.get("relation_role_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-018-relation-required-support-and-fragment-status-"
                "coupling"
            ),
            allowed_scope="one_new_R3_after_clean_synced_proof",
        )
    ):
        raise ValueError(
            "project_os_full_fragment_relation_role_scope_allowance_missing"
        )
    if (
        decision_projection.get("causal_polarity_successor") is True
        and not _issue_explicitly_allows(
            root=root,
            issue_id=(
                "RC-S3-020-clause-and-negation-blind-causal-lexical-guard-"
                "false-positive"
            ),
            allowed_scope="one_fresh_R5_after_clean_synced_proof_and_preflight",
        )
    ):
        raise ValueError(
            "project_os_full_fragment_causal_polarity_scope_allowance_missing"
        )

    env = os.environ if environment is None else environment
    api_key_env = str(decision_projection["api_key_env"])
    credential_present = bool(str(env.get(api_key_env) or "").strip())
    if decision.get("credential_presence_required") is True and not credential_present:
        raise ValueError(f"project_os_provider_credential_missing:{api_key_env}")

    repository = _repository_projection(root) if check_repository else {
        "head": "not_checked",
        "upstream": "not_checked",
        "clean": "not_checked",
        "synced": "not_checked",
    }
    if decision_projection.get("multi_agent_preview") is True:
        if decision_projection.get(
            "multi_agent_preview_downstream_analysis_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R10 as a terminal "
                "Agent Runtime/context-continuity failure. It revalidates six "
                "initial workpapers, the R9 Lead coordination decision and "
                "the completed R10 Demand repair from immutable captures. It "
                "forbids rerunning them and permits exactly one low-reasoning "
                "continuation of the active Cash repair fragment before the "
                "remaining Supply repair, bounded evaluation, local evaluator "
                "repairs and conditional Writer. It forbids changing research "
                "inputs, external source network access, candidate promotion, "
                "S1 or S3 acceptance, heterogeneous generalization, qualified-"
                "human self-acceptance, Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_coordination_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R9 as a terminal "
                "Harness contract-capacity failure. It revalidates six "
                "capture-bound specialist workpapers and the natural Lead "
                "coordination partition without any new model call. It "
                "forbids rerunning those nodes and permits only the three "
                "accepted role-local repairs, followed by at most two "
                "independent evaluation rounds, two evaluator repairs and a "
                "conditional Writer. It forbids changing research inputs, "
                "external source network access, candidate promotion, S1 or "
                "S3 acceptance, heterogeneous generalization, qualified-human "
                "self-acceptance, Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_specialist_analysis_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R8 as a terminal "
                "Agent Runtime/context-continuity failure. It revalidates five "
                "capture-bound specialist workpapers and the 918-character "
                "Counterevidence analysis fragment without any new call. It "
                "permits exactly one low-reasoning continuation over the exact "
                "original Counter conversation, forbids rerunning the initial "
                "analysis, then permits the unchanged bounded downstream "
                "coordination, feedback, evaluation and conditional Writer. "
                "It forbids changing research inputs, external source network "
                "access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-acceptance, "
                "Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_workpaper_checkpoint_downstream_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R7 as a terminal "
                "Harness failure and revalidates five capture-bound specialist "
                "workpapers without any new model call. It forbids rerunning "
                "those five roles and permits only the pending Counterevidence "
                "workpaper, followed by bounded Lead coordination, targeted "
                "feedback/checkpoint repair, independent evaluation and a "
                "conditional Writer. It forbids changing research inputs, "
                "external source network access, candidate promotion, S1 or S3 "
                "acceptance, heterogeneous generalization, qualified-human "
                "self-acceptance, Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_lead_checkpoint_downstream_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R6 as a terminal "
                "Harness failure and reuses six specialist plans plus one "
                "capture-bound, newly validated Research Lead plan. It permits "
                "no new specialist planning, Lead analysis, continuation or "
                "Lead plan submission; the fresh attempt begins at six role "
                "workpapers, followed by bounded Lead coordination, feedback/"
                "checkpoint repair, independent evaluation and a conditional "
                "Writer. It forbids changing research inputs, external source "
                "network access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-acceptance, "
                "Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_submission_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves the complete "
                "R4 fragment plus R5 continuation as one non-authoritative, "
                "capture-bound analysis checkpoint and permits no new "
                "Research Lead analysis or continuation. It authorizes only "
                "the separate non-thinking strict Lead submission before the "
                "unchanged bounded downstream preview. The six R3 specialist "
                "plans are reused without rerun. It forbids promoting analysis "
                "drafts, changing research inputs, external source network "
                "access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-acceptance, "
                "Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_analysis_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves the R4 visible "
                "Research Lead partial analysis as a non-authoritative, "
                "capture-bound checkpoint and permits exactly one low-reasoning "
                "continuation of only its partial and missing outputs. A local "
                "semantic completion receipt must pass before the merged draft "
                "can enter the separate non-thinking strict submission. The six "
                "R3 specialist plans are reused without rerun. It forbids a "
                "second continuation, new facts or research authority, external "
                "source network access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-acceptance, "
                "Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_plan_checkpoint_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves the six valid "
                "R3 specialist plan opinions as one immutable checkpoint "
                "and permits only one fresh DELL Multi-Agent Preview "
                "successor starting at Research Lead. Every new logical "
                "node must separate visible financial analysis from a "
                "non-thinking strict contract submission and record a "
                "task-specific TokenBudgetBasis for each phase. It forbids "
                "rerunning the successful specialists, promoting analysis "
                "drafts, changing research inputs, external source network "
                "access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-"
                "acceptance, Workbench publication or release."
            )
        elif decision_projection.get(
            "multi_agent_preview_transport_successor"
        ) is True:
            known_boundary = (
                "This current-baseline preflight preserves R2 as a failed "
                "DeepSeek V4 thinking-tool transport attempt and permits "
                "only one fresh DELL Multi-Agent Preview successor. The "
                "research topology, objective, Evidence, S2 authority and "
                "execution limits remain unchanged; only the provider "
                "profile may omit the unsupported thinking-mode tool_choice "
                "parameter. It permits no external source network access, "
                "candidate promotion, S1 or S3 acceptance, heterogeneous "
                "generalization, qualified-human self-acceptance, Workbench "
                "publication or release."
            )
        else:
            known_boundary = (
                "This current-baseline preflight permits only one clean, "
                "decision-bound DELL diagnostic Multi-Agent Preview over "
                "current reviewed Evidence and current S2 NumericFact "
                "authority. It requires six independent specialist sessions, "
                "Research Lead coordination, typed feedback, checkpoint/"
                "resume, bounded local repairs, independent evaluation and a "
                "conditional Writer. It permits no external source network "
                "access, candidate promotion, S1 or S3 acceptance, "
                "heterogeneous generalization, qualified-human self-"
                "acceptance, Workbench publication or release."
            )
    elif (
        decision_projection.get("material_scope_contract_repair_successor")
        is True
    ):
        known_boundary = (
            "This current-baseline preflight permits only one exact-once "
            "candidate-blind DELL material-scope contract-repair R3 over a "
            "fresh message digest. It preserves R1 and R2 as failed, keeps "
            "the non-thinking provider profile, and changes only the "
            "provider-neutral model-visible shape, enums and binding rules. "
            "It permits no retrieval, candidate, qrel, reference, hidden, "
            "Evidence, NumericFact, publication, S1 acceptance, COST R3 or "
            "full-chain authority."
        )
    elif decision_projection.get("material_scope_nonthinking_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one exact-once "
            "candidate-blind DELL non-thinking successor over the unchanged "
            "eight request-visible scopes. It preserves R1 as failed, changes "
            "only the provider submission profile, and permits no retrieval, "
            "candidate, qrel, reference, hidden, Evidence, NumericFact, "
            "publication, S1 acceptance, COST R3 or full-chain authority."
        )
    elif decision_projection.get("natural_material_scope_canary") is True:
        known_boundary = (
            "This current-baseline preflight permits only one exact-once "
            "candidate-blind DELL natural material-scope call over eight "
            "request-visible scopes. It permits no retrieval, candidate, "
            "qrel, reference, hidden, Evidence, NumericFact, publication, "
            "S1 acceptance, COST R3 or full-chain authority."
        )
    elif decision_projection.get(
        "dynamic_five_cell_value_repair_successor"
    ) is True:
        known_boundary = (
            "This current-baseline preflight permits only one fresh "
            "decision-bound DELL Value submission repair plus synthesis. It "
            "preserves R6 as failed, reuses its four valid judgments and "
            "capture-verified Value analysis, permits one typed Value repair "
            "submission and synthesis only after all five cells validate, "
            "and forbids new Evidence, Harness-authored judgment, publication, "
            "S3 acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get(
        "dynamic_five_cell_cell_scoped_claim_contract_successor"
    ) is True:
        known_boundary = (
            "This current-baseline preflight permits only one fresh "
            "decision-bound DELL dynamic five-cell cell-scoped claim-contract "
            "successor. It preserves R5 as a consumed project failure, reuses "
            "only the immutable R4 planner and current S1/S2 result, reruns "
            "all five analyses and submissions plus synthesis, and forbids "
            "R5 reuse, new Evidence, cross-cell claim authority, publication, "
            "S3 acceptance, heterogeneous generalization or release."
        )
    elif (
        decision_projection.get("dynamic_five_cell_claim_surface_successor")
        is True
    ):
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell claim-surface successor. It reuses only "
            "the immutable R4 planner and current S1/S2 result, reruns all "
            "five analyses and submissions plus synthesis, exposes one "
            "reviewed period-bound issuer attribution, and forbids new "
            "Evidence, current-period causal promotion, publication, S3 "
            "acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get("dynamic_five_cell_node_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell node successor. It reuses the immutable "
            "R3 planner, current S1/S2, three valid judgments and two "
            "capture-verified analysis drafts; permits only two strict Beta "
            "submissions plus synthesis after all five judgments validate; "
            "and forbids analysis reruns, new Evidence, publication, S3 "
            "acceptance, heterogeneous generalization or release."
        )
    elif decision_projection.get("dynamic_five_cell_partial_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell partial successor. It reuses the immutable "
            "R2 planner, current S1/S2 and two valid cell judgments, permits "
            "only three failed cell analyses/submissions plus synthesis after "
            "all five judgments validate, and forbids valid-node reruns, new "
            "Evidence, publication, S3 acceptance, heterogeneous "
            "generalization or release."
        )
    elif (
        decision_projection.get("dynamic_five_cell_remaining_nodes_successor")
        is True
    ):
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell successor over the remaining twelve Chat "
            "nodes. It reuses the immutable successful R1 planner and current "
            "S1/S2 prefix, permits five cell analyses, five strict submissions "
            "and synthesis only after five valid judgments, and forbids prefix "
            "reruns, publication, S3 acceptance, heterogeneous generalization "
            "or release."
        )
    elif decision_projection.get("dynamic_five_cell_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic five-cell Chat run. It requires natural planning, "
            "current S1/S2 execution, all five cell attempts, and synthesis "
            "only after five valid judgments. Missing product-profit bridge "
            "authority must remain a typed gap. It does not authorize "
            "publication, S3 acceptance, heterogeneous generalization, or "
            "release."
        )
    elif decision_projection.get("dynamic_temporal_repair_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL dynamic counter temporal-validation repair submission. It "
            "reuses six successful model nodes, preserves the rejected R3 "
            "submission as failure evidence, and does not authorize new "
            "evidence, upstream reruns, a second repair, five-cell execution, "
            "publication, S3 acceptance, or release."
        )
    elif decision_projection.get("dynamic_counter_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "failed-node successor for DELL dynamic value_capture counter/WWC. "
            "It reuses five immutable successful model nodes and permits one "
            "max-thinking analysis plus one non-thinking strict submission. "
            "It does not authorize new evidence, another analysis retry, "
            "five-cell execution, publication, S3 acceptance, or release."
        )
    elif decision_projection.get("dynamic_single_cell_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "DELL SEC-only dynamic value_capture single-cell Chat run. It "
            "requires natural planning and current S1/S2 execution, forbids "
            "candidate promotion and transcript prefeed, and does not authorize "
            "five-cell acceptance, publication, or release."
        )
    elif decision_projection.get("fragment_validation_repair_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "R7 failed counter/WWC validation-repair submission. It reuses "
            "six immutable successful model calls, preserves the rejected "
            "fragment and causal guard, and does not authorize another repair, "
            "dynamic Agentic Research, five-cell acceptance, publication, or "
            "release."
        )
    elif decision_projection.get("failed_fragment_submission_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only one decision-bound "
            "R6 failed counter/WWC contract-submission successor. It reuses "
            "five immutable successful model calls and does not authorize "
            "analysis reruns, dynamic Agentic Research, five-cell acceptance, "
            "publication, or release."
        )
    elif decision_projection.get("full_fragment_judgment_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture full three-fragment fixed-Pack Chat successor. "
            "It is not exact-live authority, dynamic Agentic Research, "
            "five-cell acceptance, publication, or release."
        )
    elif decision_projection.get("micro_judgment_successor") is True:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture fixed-Pack micro-judgment Chat successor. It "
            "is not exact-live authority, natural submission proof, dynamic "
            "Agentic Research, five-cell acceptance, publication, or release."
        )
    else:
        known_boundary = (
            "This current-baseline preflight permits only the decision-bound "
            "DELL value_capture fixed-Pack Chat replacement. It is not exact-"
            "live authority, dynamic Agentic Research, five-cell acceptance, "
            "publication, or release."
        )
    return {
        "schema_version": CURRENT_PREFLIGHT_SCHEMA,
        "status": "pass_current_decision_bound_preflight",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "decision_ref": decision_ref,
        "decision_sha256": _sha256(decision_path),
        "run_scope_id": decision["run_scope_id"],
        "case_key": decision["case_key"],
        "cell_id": decision["cell_id"],
        "checks": {
            "project_os_documents_available_and_parseable": True,
            "immutable_clean_proof_and_failure_bindings_valid": True,
            "root_cause_scope_allowed": True,
            "token_and_call_budget_bounded": True,
            "provider_profile_and_recent_complete_capture_valid": True,
            "provider_credential_present_value_unread": credential_present,
            "real_evidence_mode": decision["evidence_mode"],
            "repository_clean_and_synced": repository["clean"] is True,
        },
        "decision_projection": decision_projection,
        "scope_projection": scope_projection,
        "repository": repository,
        "project_os_document_digests": project_os_digests,
        "network_calls": 0,
        "model_calls": 0,
        "provider_calls": 0,
        "credential_value_persisted": False,
        "known_boundary": known_boundary,
    }
