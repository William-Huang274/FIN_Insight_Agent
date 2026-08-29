from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence

from .dell_report_r14_common import (
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_sha256,
    validate_result_digest,
    with_result_digest,
)
from .dell_report_transaction_r14 import (
    TransactionDurabilityCapabilityR14,
    validate_transaction_durability_capability_r14,
)


RESOURCE_RECEIPT_SCHEMA = "fin_ia_dell_03B_R14_resource_gate_receipt_v1_0"
PERFORMANCE_RECEIPT_SCHEMA = "fin_ia_dell_03B_R14_performance_receipt_v1_0"
FORMAL_FREE_FLOOR_BYTES = 512 * 1024 * 1024
SAFETY_FLOOR_BYTES = 128 * 1024 * 1024
FROZEN_WARNING_LIMIT_MS = 600_000
FROZEN_HARD_LIMIT_MS = 1_800_000
FROZEN_HARD_MEMORY_LIMIT_BYTES = 4 * 1024**3


def build_performance_receipt_r14(
    *,
    source_input_count: int,
    compiled_input_count: int,
    logical_decision_count: int,
    elapsed_ms: int,
    peak_memory_bytes: int,
    warning_limit_ms: int,
    hard_limit_ms: int,
    hard_memory_limit_bytes: int,
) -> dict[str, Any]:
    values = (
        source_input_count,
        compiled_input_count,
        logical_decision_count,
        elapsed_ms,
        peak_memory_bytes,
        warning_limit_ms,
        hard_limit_ms,
        hard_memory_limit_bytes,
    )
    require(
        all(type(value) is int and value >= 0 for value in values)
        and warning_limit_ms <= hard_limit_ms
        and hard_limit_ms > 0
        and hard_memory_limit_bytes > 0,
        "R14_performance_measurement_invalid",
    )
    status = (
        "FAIL_HARD_LIMIT"
        if elapsed_ms > hard_limit_ms or peak_memory_bytes > hard_memory_limit_bytes
        else "PASS_WITH_WARNING"
        if elapsed_ms > warning_limit_ms
        else "PASS"
    )
    return with_result_digest(
        {
            "schema_version": PERFORMANCE_RECEIPT_SCHEMA,
            "source_input_count": source_input_count,
            "compiled_input_count": compiled_input_count,
            "logical_decision_count": logical_decision_count,
            "elapsed_ms": elapsed_ms,
            "peak_memory_bytes": peak_memory_bytes,
            "warning_limit_ms": warning_limit_ms,
            "hard_limit_ms": hard_limit_ms,
            "hard_memory_limit_bytes": hard_memory_limit_bytes,
            "status": status,
            "model_provider_calls": 0,
        }
    )


def validate_performance_receipt_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_performance_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "source_input_count",
            "compiled_input_count",
            "logical_decision_count",
            "elapsed_ms",
            "peak_memory_bytes",
            "warning_limit_ms",
            "hard_limit_ms",
            "hard_memory_limit_bytes",
            "status",
            "model_provider_calls",
            "result_digest",
        },
        "R14_performance_receipt_keyset_invalid",
    )
    rebuilt = build_performance_receipt_r14(
        source_input_count=value.get("source_input_count"),
        compiled_input_count=value.get("compiled_input_count"),
        logical_decision_count=value.get("logical_decision_count"),
        elapsed_ms=value.get("elapsed_ms"),
        peak_memory_bytes=value.get("peak_memory_bytes"),
        warning_limit_ms=value.get("warning_limit_ms"),
        hard_limit_ms=value.get("hard_limit_ms"),
        hard_memory_limit_bytes=value.get("hard_memory_limit_bytes"),
    )
    require(rebuilt == dict(value), "R14_performance_receipt_recomputation_failed")


def build_resource_gate_receipt_r14(
    *,
    attempt_root: Path,
    planned_artifacts: Sequence[Mapping[str, Any]],
    durability_capability: TransactionDurabilityCapabilityR14,
    implementation_commit: str,
    implementation_tree: str,
    population_manifest_result_digest: str,
    program_receipt_result_digest: str,
    performance_receipt_result_digest: str,
    serializer_scratch_bytes: int,
    raw_capture_or_copy_bytes: int,
    replay_temp_bytes: int,
    failure_receipt_bytes: int,
    runtime_drift_bytes: int,
    safety_bytes: int = SAFETY_FLOOR_BYTES,
) -> dict[str, Any]:
    import re

    require(
        bool(re.fullmatch(r"[0-9a-f]{40}", implementation_commit))
        and bool(re.fullmatch(r"[0-9a-f]{40}", implementation_tree)),
        "R14_resource_implementation_identity_invalid",
    )
    for field, value in (
        ("population_manifest", population_manifest_result_digest),
        ("program_receipt", program_receipt_result_digest),
        ("performance_receipt", performance_receipt_result_digest),
    ):
        require_sha256(value, field=f"resource_{field}")
    capability = validate_transaction_durability_capability_r14(
        durability_capability, attempt_root=attempt_root
    )
    rows: list[dict[str, Any]] = []
    for raw in planned_artifacts:
        row = dict(raw)
        require(
            set(row) == {"relative_path", "exact_bytes", "sha256", "semantic_root"}
            and isinstance(row.get("relative_path"), str)
            and bool(row["relative_path"])
            and type(row.get("exact_bytes")) is int
            and row["exact_bytes"] >= 0,
            "R14_resource_planned_artifact_invalid",
        )
        require_sha256(row.get("sha256"), field="resource_artifact_sha256")
        require_sha256(row.get("semantic_root"), field="resource_artifact_root")
        rows.append(row)
    require(
        [row["relative_path"] for row in rows]
        == sorted({row["relative_path"] for row in rows})
        and bool(rows),
        "R14_resource_artifact_pathset_invalid",
    )
    components = {
        "serializer_scratch_bytes": serializer_scratch_bytes,
        "raw_capture_or_copy_bytes": raw_capture_or_copy_bytes,
        "replay_temp_bytes": replay_temp_bytes,
        "failure_receipt_bytes": failure_receipt_bytes,
        "runtime_drift_bytes": runtime_drift_bytes,
        "safety_bytes": safety_bytes,
    }
    require(
        all(type(value) is int and value >= 0 for value in components.values())
        and safety_bytes >= SAFETY_FLOOR_BYTES,
        "R14_resource_component_invalid",
    )
    stage_bytes = sum(row["exact_bytes"] for row in rows)
    publish_duplicate_bytes = 0
    required = max(
        FORMAL_FREE_FLOOR_BYTES,
        stage_bytes + publish_duplicate_bytes + sum(components.values()),
    )
    free_now = int(shutil.disk_usage(attempt_root).free)
    status = "PASS" if free_now >= required else "FAIL_INSUFFICIENT_FREE_BYTES"
    return with_result_digest(
        {
            "schema_version": RESOURCE_RECEIPT_SCHEMA,
            "implementation_commit": implementation_commit,
            "implementation_tree": implementation_tree,
            "population_manifest_result_digest": population_manifest_result_digest,
            "program_receipt_result_digest": program_receipt_result_digest,
            "performance_receipt_result_digest": performance_receipt_result_digest,
            "attempt_root": str(Path(attempt_root).resolve(strict=True)),
            "durability_backend": capability["backend"],
            "durability_probe_receipt_digest": capability["probe_receipt_digest"],
            "planned_artifact_root": domain_rows_digest(
                b"FIN_IA_R14_RESOURCE_ARTIFACTS_V1\0",
                (canonical_json_bytes(row) for row in rows),
            ),
            "planned_artifact_count": len(rows),
            "stage_bytes": stage_bytes,
            "publish_duplicate_bytes": publish_duplicate_bytes,
            **components,
            "formal_floor_bytes": FORMAL_FREE_FLOOR_BYTES,
            "required_free_bytes": required,
            "observed_free_bytes": free_now,
            "shortfall_bytes": max(0, required - free_now),
            "status": status,
        }
    )


def validate_resource_gate_receipt_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_resource_gate_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "implementation_commit",
            "implementation_tree",
            "population_manifest_result_digest",
            "program_receipt_result_digest",
            "performance_receipt_result_digest",
            "attempt_root",
            "durability_backend",
            "durability_probe_receipt_digest",
            "planned_artifact_root",
            "planned_artifact_count",
            "stage_bytes",
            "publish_duplicate_bytes",
            "serializer_scratch_bytes",
            "raw_capture_or_copy_bytes",
            "replay_temp_bytes",
            "failure_receipt_bytes",
            "runtime_drift_bytes",
            "safety_bytes",
            "formal_floor_bytes",
            "required_free_bytes",
            "observed_free_bytes",
            "shortfall_bytes",
            "status",
            "result_digest",
        },
        "R14_resource_gate_receipt_keyset_invalid",
    )
    for field in (
        "population_manifest_result_digest",
        "program_receipt_result_digest",
        "performance_receipt_result_digest",
        "durability_probe_receipt_digest",
        "planned_artifact_root",
    ):
        require_sha256(value.get(field), field=f"resource_{field}")
    integer_fields = (
        "planned_artifact_count",
        "stage_bytes",
        "publish_duplicate_bytes",
        "serializer_scratch_bytes",
        "raw_capture_or_copy_bytes",
        "replay_temp_bytes",
        "failure_receipt_bytes",
        "runtime_drift_bytes",
        "safety_bytes",
        "formal_floor_bytes",
        "required_free_bytes",
        "observed_free_bytes",
        "shortfall_bytes",
    )
    require(
        value.get("schema_version") == RESOURCE_RECEIPT_SCHEMA
        and bool(__import__("re").fullmatch(r"[0-9a-f]{40}", str(value.get("implementation_commit") or "")))
        and bool(__import__("re").fullmatch(r"[0-9a-f]{40}", str(value.get("implementation_tree") or "")))
        and value.get("durability_backend")
        == "Windows_MoveFileExW_WRITE_THROUGH_no_replace"
        and all(type(value.get(field)) is int and value[field] >= 0 for field in integer_fields)
        and value.get("publish_duplicate_bytes") == 0
        and value.get("formal_floor_bytes") == FORMAL_FREE_FLOOR_BYTES
        and value.get("safety_bytes", 0) >= SAFETY_FLOOR_BYTES,
        "R14_resource_gate_receipt_semantics_invalid",
    )
    recomputed_required = max(
        FORMAL_FREE_FLOOR_BYTES,
        int(value["stage_bytes"])
        + int(value["publish_duplicate_bytes"])
        + sum(
            int(value[field])
            for field in (
                "serializer_scratch_bytes",
                "raw_capture_or_copy_bytes",
                "replay_temp_bytes",
                "failure_receipt_bytes",
                "runtime_drift_bytes",
                "safety_bytes",
            )
        ),
    )
    shortfall = max(0, recomputed_required - int(value["observed_free_bytes"]))
    status = "PASS" if shortfall == 0 else "FAIL_INSUFFICIENT_FREE_BYTES"
    require(
        value.get("required_free_bytes") == recomputed_required
        and value.get("shortfall_bytes") == shortfall
        and value.get("status") == status,
        "R14_resource_gate_receipt_recomputation_failed",
    )


__all__ = [
    "FORMAL_FREE_FLOOR_BYTES",
    "FROZEN_HARD_LIMIT_MS",
    "FROZEN_HARD_MEMORY_LIMIT_BYTES",
    "FROZEN_WARNING_LIMIT_MS",
    "PERFORMANCE_RECEIPT_SCHEMA",
    "RESOURCE_RECEIPT_SCHEMA",
    "SAFETY_FLOOR_BYTES",
    "build_performance_receipt_r14",
    "build_resource_gate_receipt_r14",
    "validate_performance_receipt_r14",
    "validate_resource_gate_receipt_r14",
]
