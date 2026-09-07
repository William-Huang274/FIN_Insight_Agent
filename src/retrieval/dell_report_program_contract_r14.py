from __future__ import annotations

from typing import Any, Mapping

from .dell_report_r14_common import (
    require,
    require_sha256,
    validate_result_digest,
)


RUNNER_VERSION = "R14_zero_call_graph_runner_v1"
FULL_PROGRAM_RECEIPT_SCHEMA = "fin_ia_dell_03B_R14_full_program_receipt_v1_0"


def validate_full_program_receipt_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_full_program_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "runner_version",
            "manifest_result_digest",
            "source_compiled_input_counts",
            "logical_decision_count",
            "package_root",
            "event_root",
            "binding_root",
            "coverage_root",
            "family_root",
            "rank_root",
            "route_root",
            "transformation_root",
            "candidate_ceiling",
            "family_count",
            "rank_summary",
            "route_summary",
            "transformation_count",
            "model_provider_calls",
            "result_digest",
        },
        "R14_full_program_receipt_keyset_invalid",
    )
    for field in (
        "manifest_result_digest",
        "package_root",
        "event_root",
        "binding_root",
        "coverage_root",
        "family_root",
        "rank_root",
        "route_root",
        "transformation_root",
    ):
        require_sha256(value.get(field), field=f"full_program_{field}")
    counts = value.get("source_compiled_input_counts")
    require(
        value.get("schema_version") == FULL_PROGRAM_RECEIPT_SCHEMA
        and value.get("runner_version") == RUNNER_VERSION
        and isinstance(counts, dict)
        and set(counts) == {"source", "compiled"}
        and all(type(count) is int and count >= 0 for count in counts.values())
        and all(
            type(value.get(field)) is int and value[field] >= 0
            for field in (
                "logical_decision_count",
                "candidate_ceiling",
                "family_count",
                "transformation_count",
            )
        )
        and isinstance(value.get("rank_summary"), list)
        and isinstance(value.get("route_summary"), list)
        and value.get("model_provider_calls") == 0,
        "R14_full_program_receipt_semantics_invalid",
    )


__all__ = [
    "FULL_PROGRAM_RECEIPT_SCHEMA",
    "RUNNER_VERSION",
    "validate_full_program_receipt_r14",
]
