"""P33 no-paid fixture for the enterprise RAG/data pipeline contract.

P14 already proves a data-ingestion/retrieval control plane.  P33-1.1 makes
the L3 ``enterprise_rag_data_pipeline`` contract directly auditable: every
promoted evidence row used by the fixture must trace back to raw source,
parser execution, parsed chunk/table object, retrieval index, and authority.
Parser failures must become typed gaps instead of being mislabeled as public
source absence.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from sec_agent.r53_r60_data_ingestion_retrieval_control_plane import (
    NEGATIVE_AUTHORITY_ID,
    NEGATIVE_RAW_DOC_ID,
    build_p14_gate,
    data_ingestion_retrieval_control_plane_schema_contract,
    default_p14_paths,
)
from sec_agent.r53_r60_research_to_quant_lab import row_to_dict, rows_to_dicts
from sec_agent.r53_r60_runtime_task_spine import json_dumps, json_loads, rel_path, utc_now_iso, write_json


SCHEMA_VERSION = "fin_insight_p33_enterprise_rag_data_pipeline_fixture_v0_1"
CONTRACT_ID = "l3_enterprise_rag_data_pipeline_contract_v0_1"
RELEASE_DECISION_PASS = "P33_1_1_L4_scope_pass_enterprise_rag_data_pipeline_fixture"
RELEASE_DECISION_BLOCKED = "P33_1_1_blocked_enterprise_rag_data_pipeline_fixture"


@dataclass(frozen=True)
class P33EnterpriseRagFixturePaths:
    manifest_path: Path
    report_path: Path


def default_p33_enterprise_rag_fixture_paths(root: Path) -> P33EnterpriseRagFixturePaths:
    return P33EnterpriseRagFixturePaths(
        manifest_path=root / "data" / "manifests" / "p33_enterprise_rag_data_pipeline_fixture_v0_1.json",
        report_path=root
        / "docs"
        / "internal"
        / "vnext_20260610"
        / "p33_enterprise_rag_data_pipeline_fixture_report.zh-CN.md",
    )


def build_p33_enterprise_rag_data_pipeline_fixture(
    root: Path,
    *,
    rebuild_p14: bool = True,
    write_outputs: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    paths = default_p33_enterprise_rag_fixture_paths(root)
    if rebuild_p14:
        p14_summary = build_p14_gate(root)
    else:
        p14_summary_path = default_p14_paths(root).summary_path
        p14_summary = json_loads(p14_summary_path.read_text(encoding="utf-8"), {}) if p14_summary_path.exists() else {}

    manifest = collect_enterprise_rag_fixture_manifest(root, p14_summary=p14_summary)
    if write_outputs:
        write_json(paths.manifest_path, manifest)
        paths.report_path.parent.mkdir(parents=True, exist_ok=True)
        paths.report_path.write_text(render_enterprise_rag_fixture_report(manifest), encoding="utf-8")
    return manifest


def collect_enterprise_rag_fixture_manifest(root: Path, *, p14_summary: Mapping[str, Any]) -> dict[str, Any]:
    paths = default_p14_paths(root)
    if not paths.db_path.exists():
        raise FileNotFoundError(f"P14 runtime DB is missing: {paths.db_path}")

    generated_at = utc_now_iso()
    with sqlite3.connect(str(paths.db_path)) as conn:
        conn.row_factory = sqlite3.Row
        evidence_rows = _collect_promoted_evidence_rows(conn)
        typed_gap = _collect_typed_parser_gap(conn)
        index_rows = rows_to_dicts(
            conn.execute(
                """
                select index_refresh_id, index_name, index_type, authority_mapping_ids_json,
                       parser_run_ids_json, lineage_complete, refresh_status, payload_json
                from index_refresh_records_p14
                order by index_refresh_id
                """
            ).fetchall()
        )
        gate_rows = rows_to_dicts(
            conn.execute(
                """
                select gate_id, gate_group, status, pass_level, detail_json
                from data_plane_gate_results_p14
                order by gate_id
                """
            ).fetchall()
        )
        quality_probe_rows = rows_to_dicts(
            conn.execute(
                """
                select intent_id, expected_source_role, expected_authority_mode, candidate_found,
                       selected_for_context, gap_if_missing, status
                from retrieval_quality_probe_records_p14
                order by intent_id, expected_source_role
                """
            ).fetchall()
        )

    acceptance_gates = evaluate_enterprise_rag_fixture_gates(
        p14_summary=p14_summary,
        evidence_rows=evidence_rows,
        typed_gap=typed_gap,
        index_rows=index_rows,
        gate_rows=gate_rows,
        quality_probe_rows=quality_probe_rows,
    )
    fail_count = len([row for row in acceptance_gates if row["status"] != "pass"])
    status = "pass" if fail_count == 0 else "fail"
    fixture_paths = default_p33_enterprise_rag_fixture_paths(root)
    p14_paths = default_p14_paths(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "contract_id": CONTRACT_ID,
        "status": status,
        "release_decision": RELEASE_DECISION_PASS if status == "pass" else RELEASE_DECISION_BLOCKED,
        "closeout_level": "L4_scope_pass" if status == "pass" else "blocked",
        "promotion_recommendation": "active_registry_ready_runtime_alignment_only" if status == "pass" else "deferred_pending_repair",
        "promotion_scope": "data_pipeline_initial",
        "absorbed_contract_ids": [CONTRACT_ID],
        "artifacts": [
            {
                "artifact_type": "p33_enterprise_rag_data_pipeline_fixture",
                "contract_aligned_plan": {
                    "absorbed_contract_ids": [CONTRACT_ID],
                    "used_case_contract_ids": [CONTRACT_ID],
                },
            }
        ],
        "source_fixture_refs": {
            "p14_summary": rel_path(p14_paths.summary_path, root),
            "p14_runtime_db": rel_path(p14_paths.db_path, root),
            "p14_gate_rows": rel_path(p14_paths.gate_rows_path, root),
            "p33_manifest": rel_path(fixture_paths.manifest_path, root),
            "p33_report": rel_path(fixture_paths.report_path, root),
        },
        "input_contract_required_fields": [
            "source_id",
            "source_role",
            "raw_artifact_ref",
            "parser_profile",
            "chunk_or_table_policy",
            "index_target",
            "authority_policy",
        ],
        "output_contract_required_fields": [
            "ingestion_run_id",
            "parser_execution_id",
            "chunk_or_table_artifact_ref",
            "retrieval_index_ref",
            "lineage_ref",
            "quality_probe_result",
            "typed_gap_if_failed",
        ],
        "evidence_rows": evidence_rows,
        "typed_parser_gap": typed_gap,
        "index_refresh_rows": [_compact_index_row(row) for row in index_rows],
        "quality_probe_rows": quality_probe_rows,
        "acceptance_gates": acceptance_gates,
        "gate_fail_count": fail_count,
        "runtime_entry_policy": (
            "Runtime alignment only: may align DataIngestionContract, ParserExecutionContract, "
            "RetrievalIndexRegistry, RoutePolicyMatrix, RetrievalAudit and StorageAndLineageContract. "
            "It does not by itself prove broad crawler coverage, paid-model memo quality or production p95/p99."
        ),
        "do_not_promote": [
            "generic_vector_hit_over_exact_source",
            "parser_failure_hidden_as_source_absent",
            "raw_snapshot_as_fact_authority",
        ],
        "rollback_gate": [
            "promoted_evidence_without_raw_parser_chunk_index_authority_lineage",
            "refresh_status_invisible",
            "milvus_or_generic_vector_used_as_exact_authority",
        ],
    }


def _collect_promoted_evidence_rows(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = rows_to_dicts(
        conn.execute(
            """
            select
                auth.authority_mapping_id,
                auth.authority_mode,
                auth.claim_scope,
                auth.can_enter_claim_card,
                auth.can_enter_context,
                auth.can_enter_exact_value_ledger,
                obj.parsed_object_id,
                obj.object_type,
                obj.issuer_id,
                obj.ticker,
                obj.product_family,
                obj.metric_or_signal,
                obj.period_or_version,
                obj.citation_ref,
                parser.parser_run_id,
                parser.parser_name,
                parser.parser_version,
                parser.status as parser_status,
                raw.raw_document_id,
                raw.object_uri as raw_artifact_ref,
                raw.document_kind,
                raw.ingestion_job_id,
                source.source_snapshot_id,
                source.source_role,
                source.source_modality,
                source.refresh_policy,
                source.authority_boundary
            from authority_mapping_records_p14 auth
            join parsed_object_records_p14 obj on obj.parsed_object_id = auth.parsed_object_id
            join parser_runs_p14 parser on parser.parser_run_id = obj.parser_run_id
            join raw_source_documents_p14 raw on raw.raw_document_id = obj.raw_document_id
            join source_snapshot_registry_p14 source on source.source_snapshot_id = raw.source_snapshot_id
            where auth.status = 'accepted'
            order by auth.authority_mapping_id
            """
        ).fetchall()
    )
    index_rows = rows_to_dicts(
        conn.execute(
            """
            select index_refresh_id, index_name, index_type, authority_mapping_ids_json,
                   parser_run_ids_json, lineage_complete, refresh_status, payload_json
            from index_refresh_records_p14
            order by index_type, index_refresh_id
            """
        ).fetchall()
    )
    lineage_edges = rows_to_dicts(
        conn.execute(
            """
            select lineage_edge_id, from_ref, to_ref, edge_type, lineage_status
            from ingestion_lineage_edges_p14
            """
        ).fetchall()
    )
    output: list[dict[str, Any]] = []
    for row in rows:
        index_refs = _index_refs_for_authority(str(row["authority_mapping_id"]), index_rows)
        preferred_index = _preferred_index(index_refs)
        lineage_checks = _lineage_checks_for_row(row, preferred_index, lineage_edges)
        output.append(
            {
                "evidence_row_ref": f"authority_mapping_records_p14:{row['authority_mapping_id']}",
                "ingestion_run_id": row["ingestion_job_id"],
                "source_id": row["source_snapshot_id"],
                "source_role": row["source_role"],
                "source_modality": row["source_modality"],
                "raw_artifact_ref": row["raw_artifact_ref"],
                "parser_profile": f"{row['parser_name']}:{row['parser_version']}",
                "parser_execution_id": row["parser_run_id"],
                "parser_status": row["parser_status"],
                "chunk_or_table_policy": _chunk_or_table_policy(str(row["object_type"])),
                "chunk_or_table_artifact_ref": f"parsed_object_records_p14:{row['parsed_object_id']}",
                "retrieval_index_ref": preferred_index.get("index_refresh_id", ""),
                "retrieval_index_type": preferred_index.get("index_type", ""),
                "lineage_ref": f"p14_lineage_chain:{row['authority_mapping_id']}:{preferred_index.get('index_refresh_id', '')}",
                "quality_probe_result": _quality_probe_result(str(row["object_type"]), str(row["source_role"]), str(row["authority_mode"])),
                "authority_policy": row["authority_mode"],
                "authority_boundary": row["authority_boundary"],
                "claim_scope": row["claim_scope"],
                "can_enter_claim_card": bool(row["can_enter_claim_card"]),
                "can_enter_context": bool(row["can_enter_context"]),
                "can_enter_exact_value_ledger": bool(row["can_enter_exact_value_ledger"]),
                "issuer": row["issuer_id"],
                "ticker": row["ticker"],
                "product_family": row["product_family"],
                "metric_or_signal": row["metric_or_signal"],
                "period_or_version": row["period_or_version"],
                "citation_ref": row["citation_ref"],
                "typed_gap_if_failed": None,
                "lineage_checks": lineage_checks,
            }
        )
    return output


def _collect_typed_parser_gap(conn: sqlite3.Connection) -> dict[str, Any]:
    raw_doc = row_to_dict(
        conn.execute("select * from raw_source_documents_p14 where raw_document_id = ?", (NEGATIVE_RAW_DOC_ID,)).fetchone()
    )
    fetch_attempt = row_to_dict(
        conn.execute("select * from fetch_attempts_p14 where raw_document_id = ?", (NEGATIVE_RAW_DOC_ID,)).fetchone()
    )
    parser_gap = row_to_dict(
        conn.execute("select * from parser_runs_p14 where raw_document_id = ?", (NEGATIVE_RAW_DOC_ID,)).fetchone()
    )
    blocked_authority = row_to_dict(
        conn.execute(
            "select * from authority_mapping_records_p14 where authority_mapping_id = ?",
            (NEGATIVE_AUTHORITY_ID,),
        ).fetchone()
    )
    return {
        "raw_document_ref": f"raw_source_documents_p14:{NEGATIVE_RAW_DOC_ID}",
        "raw_artifact_ref": raw_doc.get("object_uri", ""),
        "fetch_attempt_ref": f"fetch_attempts_p14:{fetch_attempt.get('fetch_attempt_id', '')}",
        "parser_execution_id": parser_gap.get("parser_run_id", ""),
        "parser_status": parser_gap.get("status", ""),
        "typed_gap_if_failed": {
            "gap_type": "parser_gap",
            "reason": fetch_attempt.get("blocked_reason") or blocked_authority.get("blocked_reason") or "parser_missing",
            "source_absent": False,
            "public_source_absent": False,
            "next_action": "add source-specific parser before evidence/context promotion",
        },
        "blocked_authority_ref": f"authority_mapping_records_p14:{blocked_authority.get('authority_mapping_id', '')}",
        "blocked_authority_status": blocked_authority.get("status", ""),
        "can_enter_context": bool(blocked_authority.get("can_enter_context")),
        "can_enter_claim_card": bool(blocked_authority.get("can_enter_claim_card")),
    }


def evaluate_enterprise_rag_fixture_gates(
    *,
    p14_summary: Mapping[str, Any],
    evidence_rows: list[dict[str, Any]],
    typed_gap: Mapping[str, Any],
    index_rows: list[dict[str, Any]],
    gate_rows: list[dict[str, Any]],
    quality_probe_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    generated_at = utc_now_iso()

    def gate(gate_id: str, status: bool, detail: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "gate_id": gate_id,
            "status": "pass" if status else "fail",
            "pass_level": "L4_scope_pass" if status else "blocked",
            "detail": dict(detail),
            "generated_at": generated_at,
        }

    required_fields = {
        "source_id",
        "source_role",
        "raw_artifact_ref",
        "parser_profile",
        "chunk_or_table_artifact_ref",
        "retrieval_index_ref",
        "lineage_ref",
        "authority_policy",
        "quality_probe_result",
    }
    complete_rows = [row for row in evidence_rows if required_fields.issubset(row) and all(row.get(field) for field in required_fields)]
    lineage_complete = [
        row
        for row in evidence_rows
        if all(bool(row.get("lineage_checks", {}).get(key)) for key in ("source_to_raw", "raw_to_parser", "parser_to_object", "object_to_authority", "authority_to_index"))
    ]
    milvus_rows = [row for row in index_rows if row.get("index_type") == "milvus_semantic"]
    milvus_boundary_ok = bool(milvus_rows) and all(json_loads(str(row.get("payload_json") or "{}"), {}).get("milvus_not_exact_authority") is True for row in milvus_rows)
    refresh_bad = [row for row in index_rows if not row.get("refresh_status") or int(row.get("lineage_complete") or 0) != 1]
    typed_gap_payload = typed_gap.get("typed_gap_if_failed") if isinstance(typed_gap.get("typed_gap_if_failed"), Mapping) else {}
    p14_gate_fail = [row for row in gate_rows if row.get("status") != "pass"]
    quality_fail = [row for row in quality_probe_rows if row.get("status") != "pass"]
    return [
        gate(
            "p33_enterprise_rag_p14_control_plane_pass",
            p14_summary.get("status") == "pass"
            and p14_summary.get("release_decision") == "P14_L4_scope_pass_data_ingestion_retrieval_control_plane_ready"
            and not p14_gate_fail,
            {
                "p14_status": p14_summary.get("status"),
                "p14_release_decision": p14_summary.get("release_decision"),
                "p14_gate_fail_count": len(p14_gate_fail),
            },
        ),
        gate(
            "p33_promoted_evidence_traces_to_raw_parser_chunk_index_authority",
            bool(evidence_rows) and len(complete_rows) == len(evidence_rows) and len(lineage_complete) == len(evidence_rows),
            {
                "evidence_row_count": len(evidence_rows),
                "complete_required_field_count": len(complete_rows),
                "complete_lineage_count": len(lineage_complete),
            },
        ),
        gate(
            "p33_parser_failure_is_typed_not_source_absent",
            typed_gap_payload.get("gap_type") == "parser_gap"
            and typed_gap_payload.get("source_absent") is False
            and typed_gap_payload.get("public_source_absent") is False
            and typed_gap.get("parser_status") == "parser_gap_blocked"
            and not typed_gap.get("can_enter_context")
            and not typed_gap.get("can_enter_claim_card"),
            {
                "parser_status": typed_gap.get("parser_status"),
                "typed_gap": dict(typed_gap_payload),
                "can_enter_context": typed_gap.get("can_enter_context"),
                "can_enter_claim_card": typed_gap.get("can_enter_claim_card"),
            },
        ),
        gate(
            "p33_generic_vector_hit_cannot_override_exact_first_authority",
            milvus_boundary_ok
            and all(row.get("authority_policy") for row in evidence_rows)
            and all(row.get("retrieval_index_type") != "milvus_semantic" or row.get("authority_policy") != "exact_company_fact_authority" for row in evidence_rows),
            {
                "milvus_index_count": len(milvus_rows),
                "milvus_boundary_ok": milvus_boundary_ok,
                "milvus_selected_exact_authority_count": len(
                    [
                        row
                        for row in evidence_rows
                        if row.get("retrieval_index_type") == "milvus_semantic"
                        and row.get("authority_policy") == "exact_company_fact_authority"
                    ]
                ),
            },
        ),
        gate(
            "p33_refresh_status_and_quality_probe_visible",
            not refresh_bad and bool(quality_probe_rows) and not quality_fail,
            {
                "index_refresh_count": len(index_rows),
                "refresh_bad_count": len(refresh_bad),
                "quality_probe_count": len(quality_probe_rows),
                "quality_fail_count": len(quality_fail),
            },
        ),
    ]


def render_enterprise_rag_fixture_report(manifest: Mapping[str, Any]) -> str:
    lines = [
        "# P33-1.1 Enterprise RAG / Data Pipeline Fixture",
        "",
        f"- Contract: `{manifest.get('contract_id')}`",
        f"- Status: `{manifest.get('status')}`",
        f"- Release decision: `{manifest.get('release_decision')}`",
        f"- Closeout level: `{manifest.get('closeout_level')}`",
        f"- Promotion recommendation: `{manifest.get('promotion_recommendation')}`",
        "",
        "## Scope",
        "",
        "本 fixture 证明 P32 的 enterprise RAG/data pipeline 合同在 P14 控制面上可被机器验证：promoted evidence row 必须能追到 raw source、parser、parsed object、index、authority；parser 失败必须成为 typed parser gap，而不是 public_source_absent。",
        "",
        "## Gates",
        "",
    ]
    for gate in manifest.get("acceptance_gates") or []:
        lines.append(f"- `{gate['gate_id']}`: `{gate['status']}`")
    lines.extend(
        [
            "",
            "## Evidence Rows",
            "",
            f"- Promoted evidence rows checked: `{len(manifest.get('evidence_rows') or [])}`",
            f"- Index refresh rows checked: `{len(manifest.get('index_refresh_rows') or [])}`",
            f"- Quality probe rows checked: `{len(manifest.get('quality_probe_rows') or [])}`",
            "",
            "## Typed Parser Gap",
            "",
            f"- Parser status: `{(manifest.get('typed_parser_gap') or {}).get('parser_status', '')}`",
            f"- Gap: `{json_dumps((manifest.get('typed_parser_gap') or {}).get('typed_gap_if_failed') or {})}`",
            "",
            "## Boundary",
            "",
            "- 该结果只证明 data-pipeline runtime alignment，不证明 broad crawler coverage、paid-model memo quality 或生产 p95/p99 SLA。",
            "- Milvus / vector hit 仍是 semantic recall，不允许覆盖 exact-first authority。",
            "",
        ]
    )
    return "\n".join(lines)


def _index_refs_for_authority(authority_mapping_id: str, index_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for row in index_rows:
        authority_ids = json_loads(str(row.get("authority_mapping_ids_json") or "[]"), [])
        if authority_mapping_id in authority_ids:
            refs.append(row)
    return refs


def _preferred_index(index_refs: list[dict[str, Any]]) -> dict[str, Any]:
    priority = {"sql_exact": 0, "object_bm25": 1, "bm25": 2, "graph": 3, "milvus_semantic": 4}
    if not index_refs:
        return {}
    return sorted(index_refs, key=lambda row: priority.get(str(row.get("index_type")), 99))[0]


def _lineage_checks_for_row(row: Mapping[str, Any], preferred_index: Mapping[str, Any], lineage_edges: list[dict[str, Any]]) -> dict[str, bool]:
    checks = {
        "source_to_raw": _edge_exists(
            lineage_edges,
            f"source_snapshot:{row['source_snapshot_id']}",
            f"raw_document:{row['raw_document_id']}",
            "snapshot_to_raw",
        ),
        "raw_to_parser": _edge_exists(
            lineage_edges,
            f"raw_document:{row['raw_document_id']}",
            f"parser_run:{row['parser_run_id']}",
            "raw_to_parser",
        ),
        "parser_to_object": _edge_exists(
            lineage_edges,
            f"parser_run:{row['parser_run_id']}",
            f"parsed_object:{row['parsed_object_id']}",
            "parser_to_object",
        ),
        "object_to_authority": _edge_exists(
            lineage_edges,
            f"parsed_object:{row['parsed_object_id']}",
            f"authority_mapping:{row['authority_mapping_id']}",
            "object_to_authority",
        ),
        "authority_to_index": _edge_exists(
            lineage_edges,
            f"authority_mapping:{row['authority_mapping_id']}",
            f"index_refresh:{preferred_index.get('index_refresh_id', '')}",
            "authority_to_index",
        ),
    }
    return checks


def _edge_exists(lineage_edges: list[dict[str, Any]], from_ref: str, to_ref: str, edge_type: str) -> bool:
    return any(
        row.get("from_ref") == from_ref
        and row.get("to_ref") == to_ref
        and row.get("edge_type") == edge_type
        and row.get("lineage_status") == "complete"
        for row in lineage_edges
    )


def _chunk_or_table_policy(object_type: str) -> str:
    if object_type == "financial_statement_metric":
        return "parsed_table_metric_object_preserve_value_unit_period_citation"
    if object_type == "product_spec_architecture":
        return "parsed_product_spec_slot_preserve_version_and_citation"
    if object_type == "customer_deployment_event":
        return "parsed_event_signal_preserve_counterparty_context_and_citation"
    return "parsed_context_row_preserve_source_ref"


def _quality_probe_result(object_type: str, source_role: str, authority_mode: str) -> str:
    if object_type == "financial_statement_metric":
        return "quality_probe:exact_financial_metric:pass"
    if object_type == "product_spec_architecture":
        return "quality_probe:product_spec_architecture:pass"
    if object_type == "customer_deployment_event":
        return "quality_probe:customer_deployment_adoption:pass"
    if source_role == "macro_context":
        return "quality_probe:macro_context_only:context"
    return f"quality_probe:{authority_mode}:pass"


def _compact_index_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "index_refresh_id": row.get("index_refresh_id"),
        "index_name": row.get("index_name"),
        "index_type": row.get("index_type"),
        "lineage_complete": bool(row.get("lineage_complete")),
        "refresh_status": row.get("refresh_status"),
        "milvus_not_exact_authority": bool(json_loads(str(row.get("payload_json") or "{}"), {}).get("milvus_not_exact_authority")),
    }
