from __future__ import annotations

from typing import Any, Mapping

from .dell_report_r14_common import (
    canonical_json_bytes,
    domain_rows_digest,
    require,
    require_sha256,
    validate_result_digest,
    with_result_digest,
)
from .dell_report_program_contract_r14 import validate_full_program_receipt_r14


DELTA_RECEIPT_SCHEMA = "fin_ia_dell_03B_R13_to_R14_delta_receipt_v1_0"


def build_r13_to_r14_delta_receipt_r14(
    *,
    program_receipt: Mapping[str, Any],
    r13_result_digest: str,
    r13_summary: Mapping[str, Any],
    explanations: Mapping[str, str],
) -> dict[str, Any]:
    validate_full_program_receipt_r14(program_receipt)
    require_sha256(r13_result_digest, field="r13_delta_result")
    require(
        set(r13_summary) == {"family_count", "candidate_ceiling", "rank_summary", "route_summary"}
        and type(r13_summary.get("family_count")) is int
        and type(r13_summary.get("candidate_ceiling")) is int
        and isinstance(r13_summary.get("rank_summary"), list)
        and isinstance(r13_summary.get("route_summary"), list),
        "R14_delta_r13_summary_invalid",
    )
    current = {
        "family_count": program_receipt["family_count"],
        "candidate_ceiling": program_receipt["candidate_ceiling"],
        "rank_summary": program_receipt["rank_summary"],
        "route_summary": program_receipt["route_summary"],
    }
    rows: list[dict[str, Any]] = []
    for dimension in sorted(current):
        before = r13_summary[dimension]
        after = current[dimension]
        changed = before != after
        explanation = str(explanations.get(dimension) or "").strip()
        require(not changed or bool(explanation), f"R14_delta_unexplained:{dimension}")
        rows.append(
            {
                "dimension": dimension,
                "r13_digest": domain_rows_digest(
                    b"FIN_IA_R14_DELTA_BEFORE_V1\0",
                    (canonical_json_bytes(before),),
                ),
                "r14_digest": domain_rows_digest(
                    b"FIN_IA_R14_DELTA_AFTER_V1\0",
                    (canonical_json_bytes(after),),
                ),
                "changed": changed,
                "explanation": explanation if changed else "UNCHANGED",
            }
        )
    return with_result_digest(
        {
            "schema_version": DELTA_RECEIPT_SCHEMA,
            "r13_result_digest": r13_result_digest,
            "r14_program_receipt_result_digest": program_receipt["result_digest"],
            "dimension_rows": rows,
            "dimension_root": domain_rows_digest(
                b"FIN_IA_R14_R13_DELTA_V1\0",
                (canonical_json_bytes(row) for row in rows),
            ),
            "unexplained_delta_count": 0,
            "status": "PASS_ALL_DELTAS_EXPLAINED",
        }
    )


def validate_r13_to_r14_delta_receipt_r14(value: Mapping[str, Any]) -> None:
    validate_result_digest(value, code="R14_delta_receipt")
    require(
        set(value)
        == {
            "schema_version",
            "r13_result_digest",
            "r14_program_receipt_result_digest",
            "dimension_rows",
            "dimension_root",
            "unexplained_delta_count",
            "status",
            "result_digest",
        },
        "R14_delta_receipt_keyset_invalid",
    )
    for field in (
        "r13_result_digest",
        "r14_program_receipt_result_digest",
        "dimension_root",
    ):
        require_sha256(value.get(field), field=f"delta_{field}")
    rows = list(value.get("dimension_rows") or ())
    require(
        value.get("schema_version") == DELTA_RECEIPT_SCHEMA
        and [row.get("dimension") for row in rows]
        == ["candidate_ceiling", "family_count", "rank_summary", "route_summary"]
        and all(
            isinstance(row, dict)
            and set(row)
            == {"dimension", "r13_digest", "r14_digest", "changed", "explanation"}
            and type(row.get("changed")) is bool
            and isinstance(row.get("explanation"), str)
            and bool(row["explanation"])
            for row in rows
        ),
        "R14_delta_receipt_rows_invalid",
    )
    for row in rows:
        require_sha256(row["r13_digest"], field="delta_before")
        require_sha256(row["r14_digest"], field="delta_after")
        require(
            (row["changed"] and row["explanation"] != "UNCHANGED")
            or (not row["changed"] and row["explanation"] == "UNCHANGED"),
            "R14_delta_receipt_explanation_invalid",
        )
    require(
        value.get("dimension_root")
        == domain_rows_digest(
            b"FIN_IA_R14_R13_DELTA_V1\0",
            (canonical_json_bytes(row) for row in rows),
        )
        and value.get("unexplained_delta_count") == 0
        and value.get("status") == "PASS_ALL_DELTAS_EXPLAINED",
        "R14_delta_receipt_status_invalid",
    )


__all__ = [
    "DELTA_RECEIPT_SCHEMA",
    "build_r13_to_r14_delta_receipt_r14",
    "validate_r13_to_r14_delta_receipt_r14",
]
