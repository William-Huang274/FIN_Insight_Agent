from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .model_identity import (
    local_cross_encoder_model_identity_v3,
    local_embedding_model_identity_v3,
)
from .query_plan import canonical_digest


PROGRAM_SCHEMA_VERSION = "fin_ia_s1_large_model_challenger_program_v1_2"
PROGRAM_STATUS = (
    "preregistered_development_challenger_gate_revalidated_identity_v3"
)
IDENTITY_CONTRACT_VERSION = "local_model_identity_v3"
APPROVED_PROGRAM_DIGEST = (
    "7192ef8cc94b62300f7dbe966656e64398a66668d7a2c27cf6bfc37fa81a9dac"
)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_LEGACY_PROGRAM_STATUSES = {
    "fin_ia_s1_large_model_challenger_program_v1_0": (
        "preregistered_development_challenger"
    ),
    "fin_ia_s1_large_model_challenger_program_v1_1": (
        "preregistered_development_challenger_identity_v3_required"
    ),
}
_IDENTITY_SCHEMAS = {
    "embedding": "local_embedding_model_identity_v3",
    "reranker": "local_cross_encoder_model_identity_v3",
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _is_lower_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(character in "0123456789abcdef" for character in value)
    )


def _validate_current_program_isolation(program: Mapping[str, Any]) -> None:
    if program.get("program_id") != "FIN-0.1.3-S1-LARGE-MODEL-CHALLENGER-R3":
        raise ValueError("large_model_challenger_program_id_invalid")
    split = program.get("split_and_leakage_policy")
    if not isinstance(split, Mapping) or not (
        split.get("allowed_case_keys") == ["DELL", "MU", "NVDA"]
        and split.get("forbidden_case_keys") == ["COST"]
        and split.get(
            "historical_forbidden_case_diagnostics_as_execution_input_allowed"
        )
        is False
        and split.get("hidden_frozen_holdout_reference_loading_forbidden") is True
        and split.get("temporal_qualification_execution_forbidden") is True
        and split.get("known_answer_url_or_object_id_query_injection_forbidden")
        is True
        and split.get("development_results_cannot_be_relabelled_as_blind") is True
    ):
        raise ValueError("large_model_challenger_split_contract_invalid")

    inputs = program.get("bound_development_inputs")
    if not isinstance(inputs, list) or len(inputs) != 5:
        raise ValueError("large_model_challenger_development_inputs_invalid")
    allowed_cases = {"DELL", "MU", "NVDA"}
    observed_cases: set[str] = set()
    observed_paths: set[str] = set()
    for item in inputs:
        if not isinstance(item, Mapping):
            raise ValueError("large_model_challenger_development_inputs_invalid")
        raw_path = item.get("path")
        expected_sha = item.get("sha256")
        case_inventory = item.get("case_inventory")
        if (
            not isinstance(raw_path, str)
            or not isinstance(expected_sha, str)
            or not isinstance(case_inventory, list)
            or not case_inventory
        ):
            raise ValueError("large_model_challenger_development_inputs_invalid")
        relative = PurePosixPath(raw_path)
        if (
            relative.is_absolute()
            or "\\" in raw_path
            or relative.as_posix() != raw_path
            or ".." in relative.parts
            or raw_path in observed_paths
        ):
            raise ValueError("large_model_challenger_development_input_path_invalid")
        observed_paths.add(raw_path)
        inventory = {str(value) for value in case_inventory}
        if inventory - allowed_cases or "COST" in inventory:
            raise ValueError("large_model_challenger_development_case_inventory_invalid")
        observed_cases.update(inventory)
        path = (_REPO_ROOT / Path(*relative.parts)).resolve()
        if not path.is_relative_to(_REPO_ROOT) or not path.is_file():
            raise ValueError(
                f"large_model_challenger_development_input_missing:{raw_path}"
            )
        if _sha256_file(path) != expected_sha:
            raise ValueError(
                f"large_model_challenger_development_input_digest_mismatch:{raw_path}"
            )
    if observed_cases != allowed_cases:
        raise ValueError("large_model_challenger_development_case_inventory_invalid")
    mixed_eval = (
        "configs/retrieval/"
        "fin_ia_0_1_3_s1c_financial_role_eval_set_v1_1.json"
    )
    projection = (
        "configs/retrieval/"
        "fin_ia_0_1_3_s1_large_model_dev_only_role_eval_v1_0.json"
    )
    if mixed_eval in observed_paths or projection not in observed_paths:
        raise ValueError("large_model_challenger_holdout_input_isolation_invalid")
    projection_value = json.loads((_REPO_ROOT / projection).read_text(encoding="utf-8"))
    if not (
        projection_value.get("status") == "development_only_projection_ready"
        and projection_value.get("case_inventory") == ["DELL", "MU", "NVDA"]
        and projection_value.get("query_count") == 18
        and projection_value.get("selection_contract", {}).get(
            "holdout_rows_copied"
        )
        is False
        and projection_value.get("selection_contract", {}).get(
            "heldout_pack_bindings_copied"
        )
        is False
    ):
        raise ValueError("large_model_challenger_dev_projection_invalid")
    excluded = program.get("excluded_execution_inputs")
    if not isinstance(excluded, list) or not any(
        isinstance(item, Mapping) and item.get("path") == mixed_eval
        for item in excluded
    ):
        raise ValueError("large_model_challenger_holdout_exclusion_missing")
    if canonical_digest(program) != APPROVED_PROGRAM_DIGEST:
        raise ValueError("large_model_challenger_approved_program_digest_mismatch")


def _execution_profile(program: Mapping[str, Any]) -> Mapping[str, Any]:
    profile = program.get("execution_profile")
    if not isinstance(profile, Mapping):
        raise ValueError("large_model_challenger_execution_profile_invalid")
    if not (
        profile.get("device") == "cuda"
        and profile.get("precision") == "fp16"
        and profile.get("cpu_model_fallback_allowed") is False
        and profile.get("quantized_qualification_allowed") is False
    ):
        raise ValueError("large_model_challenger_execution_contract_invalid")
    return profile


def _resource_blockers(
    profile: Mapping[str, Any],
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
) -> list[str]:
    required_total = int(profile["minimum_total_memory_bytes"])
    required_free = int(profile["minimum_free_memory_bytes_before_load"])
    required_storage = int(profile["minimum_free_storage_bytes_before_download"])
    blockers: list[str] = []
    if hardware.get("cuda_available") is not True:
        blockers.append("cuda_unavailable")
    else:
        if int(hardware.get("total_memory_bytes") or 0) < required_total:
            blockers.append("gpu_total_memory_below_preregistered_profile")
        if int(hardware.get("free_memory_bytes") or 0) < required_free:
            blockers.append("gpu_free_memory_below_preregistered_profile")
    if int(storage.get("free_bytes") or 0) < required_storage:
        blockers.append("storage_free_bytes_below_preregistered_profile")
    return blockers


def _required_model_keys(profile: Mapping[str, Any]) -> tuple[str, ...]:
    keys = tuple(profile.get("required_model_keys") or ())
    if not keys or any(not isinstance(key, str) or not key for key in keys):
        raise ValueError("large_model_challenger_required_models_missing")
    if len(keys) != len(set(keys)):
        raise ValueError("large_model_challenger_required_models_duplicated")
    return keys


def _candidate_by_key(
    program: Mapping[str, Any], model_key: str
) -> Mapping[str, Any]:
    candidates = program.get("candidates")
    if not isinstance(candidates, Mapping):
        raise ValueError("large_model_challenger_candidates_invalid")
    matches = [
        candidate
        for candidate in candidates.values()
        if isinstance(candidate, Mapping)
        and candidate.get("model_key") == model_key
    ]
    if len(matches) != 1:
        raise ValueError(
            f"large_model_challenger_candidate_key_invalid:{model_key}"
        )
    return matches[0]


def _validate_current_identity_contract(program: Mapping[str, Any]) -> None:
    contract = program.get("artifact_identity_contract")
    if not isinstance(contract, Mapping) or not (
        contract.get("identity_contract_version") == IDENTITY_CONTRACT_VERSION
        and contract.get("acquisition_manifest_required") is True
        and contract.get("expected_model_id_must_match_manifest") is True
        and contract.get("immutable_resolved_revision_required") is True
        and contract.get("exact_recursive_file_closure_required") is True
        and contract.get("remote_code_and_nested_configs_bound") is True
        and contract.get("extra_or_missing_files_fail_closed") is True
        and contract.get("gate_revalidates_local_files") is True
        and contract.get("caller_supplied_status_is_authority") is False
        and contract.get("local_manifest_proves_upstream_origin") is False
        and contract.get("separate_acquisition_receipt_required") is True
        and contract.get("owner_approved_resolved_revision_required") is True
    ):
        raise ValueError("large_model_challenger_identity_contract_invalid")


def _revalidate_artifact(
    program: Mapping[str, Any],
    model_key: str,
    supplied: Mapping[str, Any],
) -> tuple[dict[str, Any], str | None]:
    candidate = _candidate_by_key(program, model_key)
    model_id = candidate.get("model_id")
    kind = candidate.get("artifact_kind")
    required_schema = candidate.get("required_identity_schema")
    if (
        not isinstance(model_id, str)
        or kind not in _IDENTITY_SCHEMAS
        or required_schema != _IDENTITY_SCHEMAS[kind]
    ):
        raise ValueError(
            f"large_model_challenger_candidate_identity_contract_invalid:{model_key}"
        )

    raw_dir = supplied.get("local_dir")
    if not isinstance(raw_dir, str) or not raw_dir.strip():
        return (
            {
                "status": "locator_missing",
                "model_id": model_id,
                "caller_claimed_status": supplied.get("status"),
                "gate_revalidated_from_local_files": False,
            },
            f"model_artifact_locator_missing:{model_key}",
        )
    model_dir = Path(raw_dir)
    if not model_dir.is_absolute():
        return (
            {
                "status": "locator_invalid",
                "local_dir": raw_dir,
                "model_id": model_id,
                "caller_claimed_status": supplied.get("status"),
                "gate_revalidated_from_local_files": False,
            },
            f"model_artifact_locator_not_absolute:{model_key}",
        )
    if not model_dir.is_dir():
        return (
            {
                "status": "absent",
                "local_dir": str(model_dir),
                "model_id": model_id,
                "caller_claimed_status": supplied.get("status"),
                "gate_revalidated_from_local_files": False,
            },
            f"model_artifact_absent:{model_key}",
        )
    try:
        identity = (
            local_embedding_model_identity_v3(model_dir, model_id)
            if kind == "embedding"
            else local_cross_encoder_model_identity_v3(
                model_dir, model_id=model_id
            )
        )
    except (OSError, ValueError) as exc:
        return (
            {
                "status": "identity_invalid",
                "local_dir": str(model_dir),
                "model_id": model_id,
                "caller_claimed_status": supplied.get("status"),
                "identity_error": str(exc),
                "gate_revalidated_from_local_files": False,
            },
            (
                "model_artifact_identity_revalidation_failed:"
                f"{model_key}:{exc}"
            ),
        )
    if identity.get("identity_schema") != required_schema:
        raise ValueError(
            f"large_model_challenger_identity_schema_mismatch:{model_key}"
        )
    validated = {
        "status": "identity_bound_v3",
        "local_dir": str(model_dir.resolve()),
        "model_id": model_id,
        "identity_schema": identity["identity_schema"],
        "resolved_revision": identity["resolved_revision"],
        "model_digest": identity["model_digest"],
        "identity_receipt_digest": canonical_digest(identity),
        "artifact_closure": identity["artifact_closure"],
        "bound_file_count": len(identity["files"]),
        "caller_claimed_status": supplied.get("status"),
        "gate_revalidated_from_local_files": True,
        "upstream_origin_attested_by_local_manifest": False,
    }
    approved_revision = candidate.get("approved_resolved_revision")
    if not _is_lower_hex(approved_revision, 40):
        return (
            {
                **validated,
                "status": "identity_bound_v3_revision_approval_pending",
                "acquisition_receipt_revalidated": False,
            },
            f"model_artifact_upstream_revision_not_owner_approved:{model_key}",
        )
    if identity["resolved_revision"] != approved_revision:
        return (
            {
                **validated,
                "status": "identity_revision_mismatch",
                "approved_resolved_revision": approved_revision,
                "acquisition_receipt_revalidated": False,
            },
            f"model_artifact_approved_revision_mismatch:{model_key}",
        )
    receipt_ref = candidate.get("approved_acquisition_receipt_ref")
    receipt_sha = candidate.get("approved_acquisition_receipt_sha256")
    receipt_digest = candidate.get("approved_acquisition_receipt_digest")
    if not (
        isinstance(receipt_ref, str)
        and _is_lower_hex(receipt_sha, 64)
        and _is_lower_hex(receipt_digest, 64)
    ):
        return (
            {
                **validated,
                "status": "acquisition_receipt_approval_pending",
                "approved_resolved_revision": approved_revision,
                "acquisition_receipt_revalidated": False,
            },
            f"model_artifact_acquisition_receipt_not_approved:{model_key}",
        )
    relative = PurePosixPath(receipt_ref)
    if (
        relative.is_absolute()
        or "\\" in receipt_ref
        or relative.as_posix() != receipt_ref
        or ".." in relative.parts
    ):
        raise ValueError(
            f"large_model_challenger_acquisition_receipt_path_invalid:{model_key}"
        )
    receipt_path = (_REPO_ROOT / Path(*relative.parts)).resolve()
    if (
        not receipt_path.is_relative_to(_REPO_ROOT)
        or not receipt_path.is_file()
        or _sha256_file(receipt_path) != receipt_sha
    ):
        return (
            {
                **validated,
                "status": "acquisition_receipt_invalid",
                "approved_resolved_revision": approved_revision,
                "acquisition_receipt_revalidated": False,
            },
            f"model_artifact_acquisition_receipt_invalid:{model_key}",
        )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    unsigned_receipt = {
        key: value for key, value in receipt.items() if key != "receipt_digest"
    }
    if not (
        receipt.get("schema_version")
        == "fin_ia_local_model_acquisition_receipt_v1_0"
        and receipt.get("status") == "snapshot_download_acquisition_succeeded"
        and receipt.get("model_id") == model_id
        and receipt.get("hub_returned_commit") == approved_revision
        and receipt.get("acquisition_tool")
        == "huggingface_hub.snapshot_download"
        and receipt.get("model_digest") == identity["model_digest"]
        and receipt.get("receipt_digest") == receipt_digest
        and canonical_digest(unsigned_receipt) == receipt_digest
    ):
        return (
            {
                **validated,
                "status": "acquisition_receipt_invalid",
                "approved_resolved_revision": approved_revision,
                "acquisition_receipt_revalidated": False,
            },
            f"model_artifact_acquisition_receipt_invalid:{model_key}",
        )
    return (
        {
            **validated,
            "approved_resolved_revision": approved_revision,
            "acquisition_receipt_ref": receipt_ref,
            "acquisition_receipt_sha256": receipt_sha,
            "acquisition_receipt_digest": receipt_digest,
            "acquisition_receipt_revalidated": True,
        },
        None,
    )


def _base_result(
    profile: Mapping[str, Any],
    *,
    status: str,
    next_action: str,
    resource_blockers: list[str],
    artifact_blockers: list[str],
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
    model_artifacts: Mapping[str, Mapping[str, Any]],
    historical_replay_only: bool,
) -> dict[str, Any]:
    return {
        "status": status,
        "resource_blockers": resource_blockers,
        "artifact_blockers": artifact_blockers,
        "hardware": dict(hardware),
        "storage": dict(storage),
        "model_artifacts": {
            key: dict(value) for key, value in sorted(model_artifacts.items())
        },
        "required_profile": {
            "device": "cuda",
            "precision": "fp16",
            "minimum_total_memory_bytes": int(
                profile["minimum_total_memory_bytes"]
            ),
            "minimum_free_memory_bytes_before_load": int(
                profile["minimum_free_memory_bytes_before_load"]
            ),
            "minimum_free_storage_bytes_before_download": int(
                profile["minimum_free_storage_bytes_before_download"]
            ),
            "cpu_model_fallback_allowed": False,
            "quantized_qualification_allowed": False,
        },
        "historical_replay_only": historical_replay_only,
        "decision": {
            "development_execution_authorized_by_this_preflight": False,
            "model_download_authorized_by_this_preflight": False,
            "runtime_promotion_authorized": False,
            "hidden_or_temporal_qualification_authorized": False,
            "evidence_or_numeric_authority_granted": False,
            "next_action": next_action,
        },
        "calls": {"network": 0, "provider": 0, "model": 0},
    }


def _evaluate_legacy_replay(
    program: Mapping[str, Any],
    *,
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
    model_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    schema = str(program.get("schema_version"))
    if program.get("status") != _LEGACY_PROGRAM_STATUSES[schema]:
        raise ValueError("large_model_challenger_program_status_invalid")
    profile = _execution_profile(program)
    resource_blockers = _resource_blockers(profile, hardware, storage)
    required_status = (
        "identity_bound" if schema.endswith("v1_0") else "identity_bound_v3"
    )
    artifact_blockers = []
    for key in _required_model_keys(profile):
        artifact_status = model_artifacts.get(key, {}).get("status")
        if artifact_status == required_status:
            continue
        artifact_blockers.append(
            f"model_artifact_absent:{key}"
            if artifact_status in {None, "absent"}
            else (
                f"model_artifact_not_{required_status}:"
                f"{key}:{artifact_status}"
            )
        )
    if resource_blockers:
        status = "resource_blocked_before_download"
        next_action = (
            "move_the_frozen_profile_to_a_suitable_cuda_host_then_use_the_"
            "current_identity_gate"
        )
    elif artifact_blockers:
        status = "model_artifacts_missing_download_not_authorized_by_preflight"
        next_action = "use_the_current_program_before_any_model_materialization"
    else:
        status = "historical_identity_contract_not_authorized_for_new_attempt"
        artifact_blockers.append(
            f"historical_program_cannot_authorize_new_attempt:{schema}"
        )
        next_action = "repeat_preflight_under_the_current_program"
    return _base_result(
        profile,
        status=status,
        next_action=next_action,
        resource_blockers=resource_blockers,
        artifact_blockers=artifact_blockers,
        hardware=hardware,
        storage=storage,
        model_artifacts=model_artifacts,
        historical_replay_only=True,
    )


def evaluate_large_model_resource_gate(
    program: Mapping[str, Any],
    *,
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
    model_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    schema = program.get("schema_version")
    if schema in _LEGACY_PROGRAM_STATUSES:
        return _evaluate_legacy_replay(
            program,
            hardware=hardware,
            storage=storage,
            model_artifacts=model_artifacts,
        )
    if schema != PROGRAM_SCHEMA_VERSION:
        raise ValueError("large_model_challenger_program_schema_invalid")
    if program.get("status") != PROGRAM_STATUS:
        raise ValueError("large_model_challenger_program_status_invalid")
    _validate_current_identity_contract(program)
    _validate_current_program_isolation(program)
    profile = _execution_profile(program)
    resource_blockers = _resource_blockers(profile, hardware, storage)
    validated_artifacts: dict[str, dict[str, Any]] = {}
    artifact_blockers: list[str] = []
    for key in _required_model_keys(profile):
        supplied = model_artifacts.get(key, {})
        if not isinstance(supplied, Mapping):
            supplied = {}
        validated, blocker = _revalidate_artifact(program, key, supplied)
        validated_artifacts[key] = validated
        if blocker is not None:
            artifact_blockers.append(blocker)

    if resource_blockers:
        status = "resource_blocked_before_download"
        next_action = (
            "move_the_frozen_profile_to_a_suitable_cuda_host_then_repeat_preflight"
        )
    elif artifact_blockers:
        status = "model_artifacts_missing_download_not_authorized_by_preflight"
        next_action = "materialize_models_under_a_separate_recorded_attempt"
    else:
        status = "eligible_for_preregistered_development_attempt"
        next_action = (
            "open_a_new_model_run_attempt_and_execute_candidate_ceiling_first"
        )

    return _base_result(
        profile,
        status=status,
        next_action=next_action,
        resource_blockers=resource_blockers,
        artifact_blockers=artifact_blockers,
        hardware=hardware,
        storage=storage,
        model_artifacts=validated_artifacts,
        historical_replay_only=False,
    )


__all__ = [
    "APPROVED_PROGRAM_DIGEST",
    "IDENTITY_CONTRACT_VERSION",
    "PROGRAM_SCHEMA_VERSION",
    "PROGRAM_STATUS",
    "evaluate_large_model_resource_gate",
]
