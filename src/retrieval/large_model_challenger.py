from __future__ import annotations

from typing import Any, Mapping


PROGRAM_SCHEMA_VERSION = "fin_ia_s1_large_model_challenger_program_v1_0"


def evaluate_large_model_resource_gate(
    program: Mapping[str, Any],
    *,
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
    model_artifacts: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    if program.get("schema_version") != PROGRAM_SCHEMA_VERSION:
        raise ValueError("large_model_challenger_program_schema_invalid")
    if program.get("status") != "preregistered_development_challenger":
        raise ValueError("large_model_challenger_program_status_invalid")
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

    required_total = int(profile["minimum_total_memory_bytes"])
    required_free = int(profile["minimum_free_memory_bytes_before_load"])
    required_storage = int(profile["minimum_free_storage_bytes_before_download"])
    resource_blockers: list[str] = []
    if hardware.get("cuda_available") is not True:
        resource_blockers.append("cuda_unavailable")
    else:
        if int(hardware.get("total_memory_bytes") or 0) < required_total:
            resource_blockers.append(
                "gpu_total_memory_below_preregistered_profile"
            )
        if int(hardware.get("free_memory_bytes") or 0) < required_free:
            resource_blockers.append(
                "gpu_free_memory_below_preregistered_profile"
            )
    if int(storage.get("free_bytes") or 0) < required_storage:
        resource_blockers.append("storage_free_bytes_below_preregistered_profile")

    required_model_keys = tuple(profile.get("required_model_keys") or ())
    if not required_model_keys:
        raise ValueError("large_model_challenger_required_models_missing")
    artifact_blockers: list[str] = []
    for key in required_model_keys:
        artifact_status = model_artifacts.get(key, {}).get("status")
        if artifact_status == "identity_bound":
            continue
        artifact_blockers.append(
            f"model_artifact_absent:{key}"
            if artifact_status in {None, "absent"}
            else f"model_artifact_not_identity_bound:{key}:{artifact_status}"
        )

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
        next_action = "open_a_new_model_run_attempt_and_execute_candidate_ceiling_first"

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
            "minimum_total_memory_bytes": required_total,
            "minimum_free_memory_bytes_before_load": required_free,
            "minimum_free_storage_bytes_before_download": required_storage,
            "cpu_model_fallback_allowed": False,
            "quantized_qualification_allowed": False,
        },
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


__all__ = ["PROGRAM_SCHEMA_VERSION", "evaluate_large_model_resource_gate"]
