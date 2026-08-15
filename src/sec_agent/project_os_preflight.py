from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any


CURRENT_PREFLIGHT_SCHEMA = "fin_ia_current_decision_bound_project_os_preflight_v1_0"
FIXED_PACK_SCOPE = (
    "one_separately_authorized_natural_fixed_pack_replacement_with_zero_retry"
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
    required_equal = {
        "case_key": "DELL",
        "cell_id": "CELL::value_capture",
        "run_scope_id": FIXED_PACK_SCOPE,
        "evidence_mode": "reviewed_fixed_pack_unit_test",
        "next_authorized_scope": (
            "one_DELL_value_capture_fixed_pack_claim_surface_Chat_replacement"
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
    if clean.get("status") != "engineering_pass_zero_call_claim_surface_authority":
        raise ValueError("project_os_clean_proof_status_invalid")
    acceptance = clean.get("acceptance") or {}
    if (
        acceptance.get("corrected_zero_call_judgment_passes") is not True
        or acceptance.get("zero_request_fixed_pack_loop_passes") is not True
        or acceptance.get("natural_replacement_live_proven") is not False
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
    if predecessor.get("failure_code") != (
        "finance_loop_judgment_invalid:research_consumer_thesis_atom_invalid"
    ):
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
    out_of_scope: list[str] = []
    for issue_id, row in sorted(ledger.items()):
        if row.get("full_chain_blocker") is not True:
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
    if "RC-S3-004-model_visible_judgment_contract_omits_enums_and_conflates_evidence_use" not in explicitly_allowed:
        raise ValueError("project_os_claim_surface_scope_allowance_missing")
    return {
        "blocking_issue_ids": blocked,
        "explicit_allow_issue_ids": explicitly_allowed,
        "out_of_scope_full_chain_blocker_count": len(out_of_scope),
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
        "known_boundary": (
            "This current-baseline preflight permits only the decision-bound DELL "
            "value_capture fixed-Pack Chat replacement. It is not exact-live authority, "
            "dynamic Agentic Research, five-cell acceptance, publication, or release."
        ),
    }
