from __future__ import annotations

import base64
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from evidence.schema import EvidenceObject
from evidence.structured_extractor import extract_structured_objects
from evidence.structured_objects import ClaimObject, MetricObject, TableObject
from ingestion.parse_sec_filing import extract_sec_html_text_content
from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore
from sec_agent.financial_research_candidate_bundle_v2 import (
    project_candidate_bundle_v2,
)
from sec_agent.financial_research_source_object_vertical import normalized_sha256


POLICY_SCHEMA = "fin_ia_0_1_3_s1_three_held_out_current_source_reparse_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_three_held_out_current_source_reparse_result_v1_0"
RUN_SCOPE = "S1_THREE_HELD_OUT_CURRENT_SOURCE_TABLE_PRESERVING_REPARSE_AND_OBJECT_MIGRATION"
EXPECTED_CASE_KEYS = ("ORCL", "ASML", "ANET")
PRIVATE_NAMESPACE = "fin-0.1.3/s1-three-held-out-current-source-reparse"


class CurrentSourceReparseError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedReparseArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class CurrentSourceBinding(StrictModel):
    case_key: str
    subject_entity_key: str
    ticker: str
    company_name: str
    industry_pack_ref: str
    source_result_artifact_id: str
    source_result_selector: str
    source_type: str
    source_tier: str
    evidence_type: str
    fiscal_year: int
    fiscal_period: str
    reporting_period_end: str
    publication_date: str
    research_as_of: str
    reporting_currency: str
    reporting_currency_authority: str


class CurrentSourceReparsePolicy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    attempt_id: str
    locked_artifacts: tuple[LockedReparseArtifact, ...]
    source_bindings: tuple[CurrentSourceBinding, ...]
    candidate_ceiling_per_slot: int
    minimum_admitted_table_metrics_per_case: int
    minimum_projected_bundles_per_case: int
    minimum_projected_slots_per_case: int
    required_mutations: tuple[str, ...]
    hard_boundaries: dict[str, Any]


def load_current_source_reparse_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> CurrentSourceReparsePolicy:
    root = Path(repo_root).resolve()
    try:
        policy = CurrentSourceReparsePolicy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise CurrentSourceReparseError("current_source_reparse_policy_shape_invalid") from exc
    if policy.schema_version != POLICY_SCHEMA or policy.run_scope != RUN_SCOPE:
        raise CurrentSourceReparseError("current_source_reparse_policy_identity_invalid")
    if tuple(row.case_key for row in policy.source_bindings) != EXPECTED_CASE_KEYS:
        raise CurrentSourceReparseError("current_source_reparse_case_order_invalid")
    if len({row.artifact_id for row in policy.locked_artifacts}) != len(policy.locked_artifacts):
        raise CurrentSourceReparseError("current_source_reparse_locked_identity_invalid")
    locked_ids = {row.artifact_id for row in policy.locked_artifacts}
    for row in policy.locked_artifacts:
        if normalized_sha256(_resolve(root, row.path)) != row.normalized_sha256:
            raise CurrentSourceReparseError("current_source_reparse_locked_digest_mismatch")
    for binding in policy.source_bindings:
        if binding.source_result_artifact_id not in locked_ids:
            raise CurrentSourceReparseError("current_source_reparse_source_result_unlocked")
        if binding.source_result_selector not in {
            "held_out_case_source",
            "selected_detailed_source",
        }:
            raise CurrentSourceReparseError("current_source_reparse_selector_invalid")
        if not re.fullmatch(r"[A-Z]{3}", binding.reporting_currency):
            raise CurrentSourceReparseError("current_source_reparse_currency_invalid")
        if binding.ticker != binding.case_key:
            raise CurrentSourceReparseError("current_source_reparse_case_ticker_mismatch")
    if (
        policy.candidate_ceiling_per_slot < 1
        or policy.minimum_admitted_table_metrics_per_case < 1
        or policy.minimum_projected_bundles_per_case < 1
        or policy.minimum_projected_slots_per_case < 1
    ):
        raise CurrentSourceReparseError("current_source_reparse_threshold_invalid")
    required_mutations = {
        "directory_mime_mismatch_html_signature",
        "pdf_layout_gap_fail_closed",
        "table_id_mismatch",
        "table_cell_key_mismatch",
        "currency_conflict",
        "malformed_numeric_cell",
        "cross_case_identity",
        "header_and_contact_numeric_noise",
        "table_context_does_not_route_metric",
    }
    if not required_mutations.issubset(policy.required_mutations):
        raise CurrentSourceReparseError("current_source_reparse_mutations_incomplete")
    _validate_hard_boundaries(policy.hard_boundaries)
    return policy


def classify_captured_document(
    *,
    final_url: str,
    actual_content_type: str,
    body: bytes,
    directory_declared_type: str = "",
) -> dict[str, Any]:
    suffix = Path(urlparse(final_url).path).suffix.casefold()
    actual = actual_content_type.split(";", 1)[0].strip().casefold()
    declared = directory_declared_type.split(";", 1)[0].strip().casefold()
    stripped = body.lstrip()
    signature = (
        "pdf"
        if stripped.startswith(b"%PDF-")
        else "html"
        if stripped[:256].lower().startswith((b"<!doctype html", b"<html"))
        or b"<html" in stripped[:1024].lower()
        else "json"
        if stripped.startswith((b"{", b"["))
        else "unknown"
    )
    if signature == "pdf" or actual == "application/pdf" or suffix == ".pdf":
        parser_family = "pdf"
    elif signature == "html" or actual in {"text/html", "application/xhtml+xml"} or suffix in {".htm", ".html"}:
        parser_family = "html_table_preserving"
    elif signature == "json" or "json" in actual:
        parser_family = "json"
    else:
        parser_family = "unsupported"
    findings: list[str] = []
    if declared and actual and declared != actual:
        findings.append("directory_mime_differs_from_actual_response_mime")
    if declared and parser_family == "html_table_preserving" and "html" not in declared:
        findings.append("directory_mime_is_advisory_not_parser_authority")
    if actual and signature != "unknown" and signature not in actual and not (
        signature == "html" and actual == "application/xhtml+xml"
    ):
        findings.append("response_mime_differs_from_body_signature")
    terminal_state = (
        "parser_ready"
        if parser_family == "html_table_preserving"
        else "typed_parser_capability_gap"
    )
    gap_code = (
        None
        if terminal_state == "parser_ready"
        else "pdf_layout_preserving_table_adapter_pending"
        if parser_family == "pdf"
        else "captured_document_format_not_supported"
    )
    return {
        "parser_family": parser_family,
        "terminal_state": terminal_state,
        "gap_code": gap_code,
        "suffix": suffix,
        "actual_content_type": actual,
        "directory_declared_type": declared,
        "body_signature": signature,
        "finding_codes": findings,
    }


def execute_current_source_reparse(
    *,
    policy: CurrentSourceReparsePolicy,
    repo_root: str | Path,
    runtime_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    runtime = Path(runtime_root).resolve()
    locked_before = _locked_digest_map(policy, root=root)
    artifacts = {row.artifact_id: row for row in policy.locked_artifacts}
    store = FileCanonicalObjectStore(runtime / "objects")
    case_results: list[dict[str, Any]] = []
    mutation_contexts: dict[str, dict[str, Any]] = {}
    for binding in policy.source_bindings:
        source_artifact = artifacts[binding.source_result_artifact_id]
        public_result = json.loads(_resolve(root, source_artifact.path).read_text(encoding="utf-8"))
        descriptor = _source_descriptor(binding, public_result)
        capture = _load_and_verify_response_capture(
            repo_root=root,
            public_result=public_result,
            descriptor=descriptor,
        )
        route = classify_captured_document(
            final_url=str(capture["final_url"]),
            actual_content_type=str((capture.get("headers") or {}).get("content-type") or ""),
            body=capture["body"],
            directory_declared_type=str(descriptor.get("directory_declared_type") or ""),
        )
        case_result, mutation_context = _execute_case_reparse(
            policy=policy,
            binding=binding,
            descriptor=descriptor,
            capture=capture,
            route=route,
            store=store,
        )
        case_results.append(case_result)
        mutation_contexts[binding.case_key] = mutation_context

    mutation_results = _run_mutations(mutation_contexts)
    locked_after = _locked_digest_map(policy, root=root)
    all_case_object_pass = all(
        row["stage_acceptance"]["source_object_migration"] for row in case_results
    )
    mutations_pass = all(row["passed"] for row in mutation_results)
    status = (
        "source_object_migration_pass_index_rebuild_admitted"
        if locked_before == locked_after and all_case_object_pass and mutations_pass
        else "source_object_migration_blocked"
    )
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": policy.contract_ref,
        "run_scope": policy.run_scope,
        "recorded_at": policy.recorded_at,
        "attempt_id": policy.attempt_id,
        "status": status,
        "locked_artifacts_before": locked_before,
        "locked_artifacts_after": locked_after,
        "case_results": case_results,
        "mutation_results": mutation_results,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "stage_acceptance": {
            "capture_integrity": all(row["stage_acceptance"]["capture_integrity"] for row in case_results),
            "table_preserving_reparse": all(row["stage_acceptance"]["table_preserving_reparse"] for row in case_results),
            "three_case_source_object_migration": all_case_object_pass,
            "candidate_bundle_v2_current_source_projection": all(
                row["stage_acceptance"]["candidate_bundle_v2"] for row in case_results
            ),
            "mutation_gate": mutations_pass,
            "held_out_product_generalization": False,
            "sparse_dense_rebuild_admitted": status.startswith("source_object_migration_pass"),
            "external_residual_supplement_admitted": False,
            "model_research_admitted": False,
        },
        "decision_zh": (
            "ORCL、ASML、ANET 已使用同一张表保真解析、对象准入和 CandidateBundleV2 合同完成迁移。"
            "缺少 table／row／column／period／unit 的对象被保留为 typed reject，不会进入待重建索引。"
            "这只准入下一步 sparse／dense 重建，不代表 Evidence Pack、外源补源、DeepSeek 研究或最终产品验收通过。"
        ),
        "known_boundary": (
            "All source bytes were read from immutable capture-first stores. Output objects and bundles remain "
            "candidate-only audit material; no network, model, embedding, rerank, Evidence promotion or index build occurred."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_current_source_reparse_result(payload: Mapping[str, Any]) -> None:
    body = dict(payload)
    digest = str(body.pop("result_digest", ""))
    if body.get("schema_version") != RESULT_SCHEMA or canonical_digest(body) != digest:
        raise CurrentSourceReparseError("current_source_reparse_result_digest_invalid")
    case_results = list(body.get("case_results") or [])
    if tuple(row.get("case_key") for row in case_results) != EXPECTED_CASE_KEYS:
        raise CurrentSourceReparseError("current_source_reparse_result_case_order_invalid")
    if any(int(value) != 0 for value in dict(body.get("observed_calls") or {}).values()):
        raise CurrentSourceReparseError("current_source_reparse_result_call_boundary_invalid")
    for row in case_results:
        counts = dict(row.get("observed_counts") or {})
        if int(counts.get("admitted_table_metrics", -1)) + int(
            counts.get("rejected_table_metrics", -1)
        ) != int(counts.get("raw_table_metrics", -2)):
            raise CurrentSourceReparseError("current_source_reparse_metric_terminal_count_invalid")
        if int(counts.get("unsafe_numeric_bundle_admissions", -1)) != 0:
            raise CurrentSourceReparseError("current_source_reparse_unsafe_bundle_admission")
    acceptance = dict(body.get("stage_acceptance") or {})
    if acceptance.get("held_out_product_generalization") is not False:
        raise CurrentSourceReparseError("current_source_reparse_product_boundary_invalid")
    admitted = body.get("status") == "source_object_migration_pass_index_rebuild_admitted"
    if bool(acceptance.get("sparse_dense_rebuild_admitted")) != admitted:
        raise CurrentSourceReparseError("current_source_reparse_index_admission_invalid")


def _execute_case_reparse(
    *,
    policy: CurrentSourceReparsePolicy,
    binding: CurrentSourceBinding,
    descriptor: Mapping[str, Any],
    capture: Mapping[str, Any],
    route: Mapping[str, Any],
    store: FileCanonicalObjectStore,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if route["terminal_state"] != "parser_ready":
        raise CurrentSourceReparseError(
            f"current_source_reparse_parser_gap:{binding.case_key}:{route['gap_code']}"
        )
    try:
        html = capture["body"].decode("utf-8", errors="ignore")
        text = extract_sec_html_text_content(html)
    except Exception as exc:
        raise CurrentSourceReparseError(
            f"current_source_reparse_html_failed:{binding.case_key}"
        ) from exc
    if "[TABLE_START" not in text or "[TABLE_END]" not in text:
        raise CurrentSourceReparseError(
            f"current_source_reparse_table_structure_absent:{binding.case_key}"
        )
    source_id = (
        f"CURRENT_SOURCE::{binding.case_key}::{binding.source_type}::"
        f"{binding.reporting_period_end}::{capture['body_sha256'][:16]}"
    )
    parent = EvidenceObject(
        evidence_id=source_id,
        source_type=binding.source_type,
        source_tier=binding.source_tier,
        ticker=binding.ticker,
        company=binding.company_name,
        fiscal_year=binding.fiscal_year,
        period_end=binding.reporting_period_end,
        fiscal_period=binding.fiscal_period,
        publication_date=binding.publication_date,
        evidence_type=binding.evidence_type,
        text=text,
        source_url=str(capture["final_url"]),
        metadata={
            "form_type": binding.source_type,
            "reporting_currency": binding.reporting_currency,
            "reporting_currency_authority": binding.reporting_currency_authority,
            "industry_pack_ref": binding.industry_pack_ref,
            "response_capture_ref": descriptor["response_capture_ref"],
            "response_capture_digest": descriptor["response_capture_digest"],
            "body_sha256": capture["body_sha256"],
            "parser_family": route["parser_family"],
            "candidate_only_not_evidence": True,
        },
    )
    extracted = extract_structured_objects(parent)
    tables_by_object = {table.object_id: table for table in extracted.tables}
    admitted_metrics: list[MetricObject] = []
    rejected_metrics: list[dict[str, Any]] = []
    for metric in extracted.metrics:
        if metric.extraction_method != "table_row_heuristic":
            continue
        codes = _metric_admission_codes(metric, tables_by_object=tables_by_object)
        if codes:
            rejected_metrics.append(
                {
                    "object_id": metric.object_id,
                    "row_label": metric.row_label,
                    "column_label": metric.column_label,
                    "raw_value": metric.raw_value,
                    "finding_codes": codes,
                    "terminal_state": "rejected_typed_gap",
                }
            )
        else:
            admitted_metrics.append(metric)

    selected_objects = _select_bundle_candidates(
        binding=binding,
        metrics=admitted_metrics,
        claims=extracted.claims,
        ceiling_per_slot=policy.candidate_ceiling_per_slot,
    )
    parent_payload = parent.model_dump(mode="json")
    projections: list[dict[str, Any]] = []
    projection_inputs: list[dict[str, Any]] = []
    for slot_id, child in selected_objects:
        lane = _lane(binding, slot_id=slot_id)
        child_payload = child.model_dump(mode="json")
        candidate = {
            "asset_id": "current_financial_objects",
            "target_id": child_payload["object_id"],
            "source_record_id": source_id,
            "object_type": child_payload["object_type"],
            "ticker": binding.ticker,
        }
        projection = project_candidate_bundle_v2(
            case_key=binding.case_key,
            research_as_of=binding.research_as_of,
            reporting_currency=binding.reporting_currency,
            reporting_currency_authority=binding.reporting_currency_authority,
            lane=lane,
            candidate=candidate,
            parent=parent_payload,
            child=child_payload,
        )
        projections.append(projection)
        projection_inputs.append(
            {
                "slot_id": slot_id,
                "lane": lane,
                "candidate": candidate,
                "child": child_payload,
            }
        )
    projected = [row for row in projections if row["terminal_state"] == "bundle_projected"]
    projection_rejects = [row for row in projections if row["terminal_state"] != "bundle_projected"]
    unsafe_admissions = sum(
        1
        for row in projected
        if row.get("bundle", {}).get("object_type") == "metric"
        and row.get("bundle", {}).get("currency_unit_authority", {}).get("status")
        not in {"source_and_child_consistent", "non_monetary_dimension_preserved"}
    )
    projected_slots = sorted(
        {str(row["bundle"]["slot_id"]) for row in projected if row.get("bundle")}
    )
    finding_counts = Counter(
        code for row in rejected_metrics for code in row["finding_codes"]
    )
    finding_counts.update(
        code for row in projection_rejects for code in row.get("finding_codes", [])
    )
    private_artifacts = {
        "parent": store.put_json(
            parent_payload,
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/parent",
            artifact_type="current_source_parent_candidate_not_evidence",
        ),
        "tables": store.put_json(
            [row.model_dump(mode="json") for row in extracted.tables],
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/tables",
            artifact_type="current_source_table_candidates_not_evidence",
        ),
        "admitted_metrics": store.put_json(
            [row.model_dump(mode="json") for row in admitted_metrics],
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/admitted-metrics",
            artifact_type="current_source_metric_candidates_not_evidence",
        ),
        "metric_rejects": store.put_json(
            rejected_metrics,
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/metric-rejects",
            artifact_type="current_source_metric_typed_rejects",
        ),
        "claims": store.put_json(
            [row.model_dump(mode="json") for row in extracted.claims],
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/claims",
            artifact_type="current_source_claim_candidates_not_evidence",
        ),
        "candidate_bundles": store.put_json(
            projections,
            namespace=f"{PRIVATE_NAMESPACE}/{binding.case_key.lower()}/bundles",
            artifact_type="current_source_candidate_bundle_v2_not_evidence",
        ),
    }
    source_object_pass = (
        len(extracted.tables) > 0
        and len(admitted_metrics) >= policy.minimum_admitted_table_metrics_per_case
        and len(projected) >= policy.minimum_projected_bundles_per_case
        and len(projected_slots) >= policy.minimum_projected_slots_per_case
        and unsafe_admissions == 0
    )
    example_by_slot: dict[str, dict[str, Any]] = {}
    for row in projected:
        slot_id = str(row["bundle"]["slot_id"])
        example_by_slot.setdefault(slot_id, row)
    child_by_target = {
        str(row["candidate"]["target_id"]): row["child"]
        for row in projection_inputs
    }
    public_examples = []
    for _, row in sorted(example_by_slot.items()):
        child = child_by_target[str(row["bundle"]["target_id"])]
        object_summary = (
            {
                "metric_name": child.get("metric_name"),
                "row_label": child.get("row_label"),
                "column_label": child.get("column_label"),
                "raw_value": child.get("raw_value"),
                "value": child.get("value"),
                "unit": child.get("unit"),
                "period": child.get("period"),
            }
            if child.get("object_type") == "metric"
            else {
                "claim_type": child.get("claim_type"),
                "claim_text": str(child.get("claim_text") or "")[:320],
            }
        )
        public_examples.append({
            "bundle_id": row["bundle"]["bundle_id"],
            "slot_id": row["bundle"]["slot_id"],
            "object_type": row["bundle"]["object_type"],
            "object_summary": object_summary,
            "table_path": row["bundle"].get("table_path"),
            "currency_unit_authority": row["bundle"].get("currency_unit_authority"),
            "candidate_state": row["bundle"]["candidate_state"],
        })
    result = {
        "case_key": binding.case_key,
        "source_identity": {
            "subject_entity_key": binding.subject_entity_key,
            "ticker": binding.ticker,
            "form_type": binding.source_type,
            "publication_date": binding.publication_date,
            "reporting_period_end": binding.reporting_period_end,
            "reporting_currency": binding.reporting_currency,
            "source_url": str(capture["final_url"]),
            "body_sha256": capture["body_sha256"],
        },
        "parser_route": route,
        "finding_counts": dict(sorted(finding_counts.items())),
        "projected_slot_ids": projected_slots,
        "public_bundle_examples": public_examples,
        "private_artifacts": private_artifacts,
        "observed_counts": {
            "source_bytes": int(capture["body_bytes"]),
            "table_preserved_text_chars": len(text),
            "tables": len(extracted.tables),
            "all_metrics": len(extracted.metrics),
            "raw_table_metrics": len(admitted_metrics) + len(rejected_metrics),
            "admitted_table_metrics": len(admitted_metrics),
            "rejected_table_metrics": len(rejected_metrics),
            "claims": len(extracted.claims),
            "bundle_candidates_selected": len(selected_objects),
            "bundle_projected": len(projected),
            "bundle_rejected": len(projection_rejects),
            "unsafe_numeric_bundle_admissions": unsafe_admissions,
            "projected_slots": len(projected_slots),
        },
        "stage_acceptance": {
            "capture_integrity": True,
            "table_preserving_reparse": len(extracted.tables) > 0,
            "candidate_bundle_v2": len(projected) >= policy.minimum_projected_bundles_per_case,
            "source_object_migration": source_object_pass,
        },
        "candidate_state": "source_objects_and_bundles_not_evidence",
    }
    mutation_context = {
        "binding": binding,
        "parent": parent_payload,
        "projection_inputs": projection_inputs,
        "route": route,
    }
    return result, mutation_context


def _source_descriptor(
    binding: CurrentSourceBinding,
    public_result: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_ref = str(
        (public_result.get("public_private_separation") or {}).get("runtime_root_ref")
        or ""
    )
    if not runtime_ref:
        raise CurrentSourceReparseError("current_source_reparse_runtime_ref_missing")
    if binding.source_result_selector == "held_out_case_source":
        rows = [
            row
            for row in public_result.get("source_results") or []
            if str(row.get("case_key") or "") == binding.case_key
        ]
        if len(rows) != 1 or rows[0].get("status") != "captured_parsed_current_markers_pass":
            raise CurrentSourceReparseError("current_source_reparse_bound_source_missing")
        source = dict(rows[0].get("source") or {})
        if str(source.get("form_type") or "") != binding.source_type:
            raise CurrentSourceReparseError("current_source_reparse_form_type_mismatch")
        return {
            "runtime_root_ref": runtime_ref,
            "response_capture_ref": str(source["response_capture_ref"]),
            "response_capture_digest": str(source["response_capture_digest"]),
            "expected_final_url": str(source["selected_url"]),
            "directory_declared_type": "",
        }
    selected = dict(public_result.get("selected_detailed_source") or {})
    candidate = dict(selected.get("candidate") or {})
    if not selected or not candidate:
        raise CurrentSourceReparseError("current_source_reparse_detailed_source_missing")
    return {
        "runtime_root_ref": runtime_ref,
        "response_capture_ref": str(selected["response_capture_ref"]),
        "response_capture_digest": str(selected["response_capture_digest"]),
        "expected_final_url": str(candidate["url"]),
        "directory_declared_type": str(candidate.get("type") or ""),
    }


def _load_and_verify_response_capture(
    *,
    repo_root: Path,
    public_result: Mapping[str, Any],
    descriptor: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_ref = Path(str(descriptor["runtime_root_ref"]))
    if runtime_ref.is_absolute() or ".." in runtime_ref.parts:
        raise CurrentSourceReparseError("current_source_reparse_runtime_ref_nonportable")
    object_key = Path(PurePosixPath(str(descriptor["response_capture_ref"])))
    if object_key.is_absolute() or ".." in object_key.parts:
        raise CurrentSourceReparseError("current_source_reparse_capture_ref_nonportable")
    object_root = (repo_root / runtime_ref / "objects").resolve()
    capture_path = (object_root / object_key).resolve()
    try:
        capture_path.relative_to(object_root)
    except ValueError as exc:
        raise CurrentSourceReparseError("current_source_reparse_capture_escape") from exc
    data = capture_path.read_bytes()
    expected_digest = str(descriptor["response_capture_digest"])
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise CurrentSourceReparseError("current_source_reparse_capture_digest_mismatch")
    capture = json.loads(data)
    if (
        canonical_digest(capture) != expected_digest
        or capture.get("capture_kind") != "source_response"
        or capture.get("capture_before_parse") is not True
        or capture.get("credential_cookie_authorization_present") is not False
        or int(capture.get("status_code") or 0) != 200
        or str(capture.get("final_url") or "") != str(descriptor["expected_final_url"])
    ):
        raise CurrentSourceReparseError("current_source_reparse_capture_contract_invalid")
    body = base64.b64decode(str(capture.get("body_base64") or ""), validate=True)
    if (
        len(body) != int(capture.get("body_bytes") or -1)
        or hashlib.sha256(body).hexdigest() != str(capture.get("body_sha256") or "")
    ):
        raise CurrentSourceReparseError("current_source_reparse_body_digest_mismatch")
    return {**capture, "body": body}


def _metric_admission_codes(
    metric: MetricObject,
    *,
    tables_by_object: Mapping[str, TableObject],
) -> list[str]:
    codes: list[str] = []
    table_object_id = str(metric.table_object_id or metric.metadata.get("table_object_id") or "")
    table = tables_by_object.get(table_object_id)
    if table is None:
        codes.append("bound_table_object_missing")
    if not metric.row_label or not metric.column_label:
        codes.append("table_row_or_column_label_missing")
    if not metric.period:
        codes.append("table_cell_period_missing")
    if not metric.unit:
        codes.append("table_cell_unit_missing")
    if not _strict_numeric_cell(metric.raw_value, metric.value):
        codes.append("numeric_cell_parse_invalid")
    source_table_id = str(metric.metadata.get("source_table_id") or "")
    source_cell_key = str(metric.metadata.get("table_cell_key") or "")
    if not source_table_id or not source_cell_key:
        codes.append("table_coordinate_lineage_missing")
    if table is not None:
        if source_table_id != table.table_id:
            codes.append("table_id_mismatch")
        matching = [
            cell
            for cell in table.cells
            if str(cell.get("cell_key") or "") == source_cell_key
            and str(cell.get("row_label") or "") == str(metric.row_label or "")
            and str(cell.get("column_label") or "") == str(metric.column_label or "")
            and str(cell.get("raw_value") or "") == metric.raw_value
        ]
        if len(matching) != 1:
            codes.append("table_cell_lineage_mismatch")
    row_label = str(metric.row_label or "").strip().casefold()
    if re.fullmatch(r"item\s+\d+[a-z]?\.?", row_label) or any(
        marker in row_label
        for marker in (
            "financial statements for",
            "statements of operations",
            "statements of cash flows",
            "balance sheets as of",
            "figures in millions",
        )
    ):
        codes.append("navigation_or_table_title_numeric_noise")
    return list(dict.fromkeys(codes))


def _select_bundle_candidates(
    *,
    binding: CurrentSourceBinding,
    metrics: Sequence[MetricObject],
    claims: Sequence[ClaimObject],
    ceiling_per_slot: int,
) -> list[tuple[str, MetricObject | ClaimObject]]:
    by_slot: dict[str, list[MetricObject | ClaimObject]] = defaultdict(list)
    for row in [*metrics, *claims]:
        slot_id = _slot_for_object(row)
        if slot_id:
            by_slot[slot_id].append(row)
    selected: list[tuple[str, MetricObject | ClaimObject]] = []
    for slot_id in sorted(by_slot):
        rows = sorted(
            by_slot[slot_id],
            key=lambda row: (
                _current_period_rank(binding, row),
                0 if row.object_type == "metric" else 1,
                row.object_id,
            ),
        )
        selected.extend((slot_id, row) for row in rows[:ceiling_per_slot])
    return selected


def _current_period_rank(
    binding: CurrentSourceBinding,
    row: MetricObject | ClaimObject,
) -> int:
    if row.object_type != "metric":
        return 4
    column_label = str(row.column_label or "").casefold()
    cell_period = str(row.period or "").casefold()
    year = str(binding.fiscal_year)
    fiscal_period = binding.fiscal_period.casefold()
    if binding.reporting_period_end.casefold() in column_label:
        return 0
    if year in column_label and fiscal_period and fiscal_period in column_label:
        return 0
    if fiscal_period and fiscal_period in column_label:
        return 1
    if year in column_label or cell_period == year:
        return 2
    if year in cell_period:
        return 2
    return 3


def classify_financial_object_slot(row: MetricObject | ClaimObject) -> str | None:
    """Classify one source object without borrowing unrelated table context."""
    if row.object_type == "claim":
        claim_type = str(row.claim_type)
        return {
            "demand": "demand_volume_quality",
            "revenue_visibility": "demand_volume_quality",
            "capex": "capacity_inputs_execution",
            "cost_pressure": "pricing_mix_value_capture",
            "risk": "counterevidence_and_what_would_change",
            "strategy": "operating_performance",
            "accounting_policy": "operating_performance",
            "business_context": "relationship_attribution",
        }.get(claim_type)

    # A table title or active group can be copied into ``metric_name`` by the
    # generic extractor.  It is useful retrieval context, but it is not enough
    # authority to decide what the individual numeric row means.  Routing is
    # therefore based on the row's own label only.  Unclassified rows remain
    # candidate objects; they are not forced into a superficially full pack.
    text = " ".join(str(row.row_label or "").casefold().split())
    routes = (
        (
            "cash_conversion_balance_sheet",
            (
                "cash",
                "inventory",
                "accounts receivable",
                "accounts payable",
                "working capital",
                "marketable securities",
                "proceeds from maturities",
            ),
        ),
        (
            "capital_allocation_and_valuation",
            (
                "notes payable",
                "borrowings",
                "debt",
                "senior notes",
                "interest rate",
                "discount rate",
                "maturit",
                " due ",
                "customer relationships",
            ),
        ),
        ("demand_volume_quality", ("bookings", "backlog", "remaining performance obligations", " rpo ", "orders")),
        (
            "pricing_mix_value_capture",
            (
                "gross margin",
                "operating margin",
                "per share",
                "systems sold",
                "units sold",
                "product mix",
                "service mix",
                "% of total revenue",
                "percent of total revenue",
                "average selling price",
            ),
        ),
        (
            "capacity_inputs_execution",
            (
                "capital expenditure",
                "property, plant and equipment",
                "property and equipment",
                "construction-in-process",
                "capacity",
                "equipment",
                "data center",
                "buildings and improvements",
                "land",
            ),
        ),
        ("regulatory_policy_exposure", ("export", "regulatory", "china", "license restriction")),
        ("relationship_attribution", ("customer", "supplier", "concentration")),
        ("counterevidence_and_what_would_change", ("risk", "adverse", "uncertain", "decline")),
        ("operating_performance", ("revenue", "net sales", "sales", "net income", "operating income", "gross profit", "profit")),
    )
    for slot_id, markers in routes:
        if any(marker in text for marker in markers):
            return slot_id
    return None


def _slot_for_object(row: MetricObject | ClaimObject) -> str | None:
    return classify_financial_object_slot(row)


def _lane(binding: CurrentSourceBinding, *, slot_id: str) -> dict[str, Any]:
    return {
        "lane_id": f"{binding.case_key.lower()}_current_source_{slot_id}",
        "slot_id": slot_id,
        "asset_id": "current_financial_objects",
        "evidence_owner_entity_key": binding.subject_entity_key,
        "evidence_owner_ticker": binding.ticker,
        "relationship_direction": "subject_self_disclosure",
    }


def _run_mutations(contexts: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    asml = contexts["ASML"]
    binding: CurrentSourceBinding = asml["binding"]
    metric_inputs = [
        row for row in asml["projection_inputs"] if row["child"]["object_type"] == "metric"
    ]
    if not metric_inputs:
        raise CurrentSourceReparseError("current_source_reparse_mutation_metric_missing")
    monetary = next(
        (
            row
            for row in metric_inputs
            if str(row["child"].get("unit") or "").startswith("eur_")
            and not str(row["child"].get("unit") or "").endswith("_per_share")
        ),
        metric_inputs[0],
    )

    def project(child: Mapping[str, Any], *, parent: Mapping[str, Any] | None = None) -> dict[str, Any]:
        return project_candidate_bundle_v2(
            case_key=binding.case_key,
            research_as_of=binding.research_as_of,
            reporting_currency=binding.reporting_currency,
            reporting_currency_authority=binding.reporting_currency_authority,
            lane=monetary["lane"],
            candidate=monetary["candidate"],
            parent=parent or asml["parent"],
            child=child,
        )

    wrong_table = json.loads(json.dumps(monetary["child"]))
    wrong_table.setdefault("metadata", {})["source_table_id"] = "wrong-table"
    wrong_cell = json.loads(json.dumps(monetary["child"]))
    wrong_cell.setdefault("metadata", {})["table_cell_key"] = "wrong-cell"
    wrong_currency = json.loads(json.dumps(monetary["child"]))
    wrong_currency["unit"] = "usd_millions"
    malformed = json.loads(json.dumps(monetary["child"]))
    malformed["raw_value"] = "Q2 2026: EUR 9,326 and 8,767"
    malformed["value"] = 2026.0
    wrong_parent = json.loads(json.dumps(asml["parent"]))
    wrong_parent["ticker"] = "OTHER"

    mime_route = classify_captured_document(
        final_url="https://issuer.example/exhibit.htm",
        actual_content_type="text/html",
        directory_declared_type="text.gif",
        body=b"<html><body><table><tr><td>Revenue</td><td>1</td></tr></table></body></html>",
    )
    pdf_route = classify_captured_document(
        final_url="https://issuer.example/results.pdf",
        actual_content_type="application/pdf",
        directory_declared_type="application/pdf",
        body=b"%PDF-1.7\nfixture",
    )
    noise_text = extract_sec_html_text_content(
        "<html><body>"
        "<table><tr><td>Financial Statements for Q2 2026</td><td>5</td></tr></table>"
        "<table><tr><td>Investor Relations</td><td>+31 40 268 3000</td></tr></table>"
        "</body></html>"
    )
    noise_parent = EvidenceObject(
        evidence_id="MUTATION_NOISE",
        source_type="6-K",
        ticker="FIX",
        fiscal_year=2026,
        period_end="2026-06-30",
        fiscal_period="Q2",
        evidence_type="company_authored_disclosure",
        text=noise_text,
        metadata={"form_type": "6-K", "reporting_currency": "EUR"},
    )
    noise_extraction = extract_structured_objects(noise_parent)
    checks = {
        "directory_mime_mismatch_html_signature": (
            mime_route["terminal_state"] == "parser_ready"
            and "directory_mime_is_advisory_not_parser_authority" in mime_route["finding_codes"]
        ),
        "pdf_layout_gap_fail_closed": (
            pdf_route["terminal_state"] == "typed_parser_capability_gap"
            and pdf_route["gap_code"] == "pdf_layout_preserving_table_adapter_pending"
        ),
        "table_id_mismatch": (
            project(wrong_table)["terminal_state"] == "rejected_typed_gap"
            and "table_semantic_path_missing" in project(wrong_table)["finding_codes"]
        ),
        "table_cell_key_mismatch": (
            project(wrong_cell)["terminal_state"] == "rejected_typed_gap"
            and "table_cell_key_mismatch" in project(wrong_cell)["finding_codes"]
        ),
        "currency_conflict": (
            project(wrong_currency)["terminal_state"] == "rejected_typed_gap"
            and "currency_unit_conflict" in project(wrong_currency)["finding_codes"]
        ),
        "malformed_numeric_cell": (
            project(malformed)["terminal_state"] == "rejected_typed_gap"
            and "numeric_cell_parse_invalid" in project(malformed)["finding_codes"]
        ),
        "cross_case_identity": (
            project(monetary["child"], parent=wrong_parent)["terminal_state"]
            == "rejected_typed_gap"
            and "parent_source_ticker_mismatch"
            in project(monetary["child"], parent=wrong_parent)["finding_codes"]
        ),
        "header_and_contact_numeric_noise": (
            sum(
                row.extraction_method == "table_row_heuristic"
                for row in noise_extraction.metrics
            )
            == 0
        ),
        "table_context_does_not_route_metric": (
            classify_financial_object_slot(
                MetricObject(
                    object_id="MUTATION_TABLE_CONTEXT",
                    source_evidence_id="MUTATION_PARENT",
                    ticker="FIX",
                    metric_name="Risk factors | Cash and cash equivalents | Other borrowings",
                    raw_value="42",
                    value=42.0,
                    unit="usd_millions",
                    row_label="Deferred tax assets",
                    column_label="2026",
                    context="Risk factors and cash flows",
                    extraction_method="table_row_heuristic",
                )
            )
            is None
        ),
    }
    return [
        {"mutation_id": mutation_id, "passed": bool(passed)}
        for mutation_id, passed in sorted(checks.items())
    ]


def _strict_numeric_cell(raw_value: str, value: Any) -> bool:
    if value is None:
        return False
    raw = " ".join(str(raw_value or "").split())
    if re.search(r"[A-Za-z]{2,}", raw):
        return False
    numbers = re.findall(r"(?<!\d)(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", raw)
    if len(numbers) != 1:
        return False
    parsed = float(numbers[0].replace(",", ""))
    if "(" in raw and ")" in raw:
        parsed = -parsed
    try:
        return abs(parsed - float(value)) < 1e-6
    except (TypeError, ValueError):
        return False


def _validate_hard_boundaries(boundary: Mapping[str, Any]) -> None:
    for key in ("network", "provider", "model", "embedding", "rerank", "evidence_promotion"):
        if int(boundary.get(key, -1)) != 0:
            raise CurrentSourceReparseError("current_source_reparse_zero_call_boundary_invalid")
    if (
        boundary.get("source_captures_immutable") is not True
        or boundary.get("ticker_specific_parser_branch_allowed") is not False
        or boundary.get("directory_mime_is_parser_authority") is not False
        or boundary.get("index_build_allowed_during_reparse") is not False
        or boundary.get("unsafe_object_coercion_allowed") is not False
    ):
        raise CurrentSourceReparseError("current_source_reparse_authority_boundary_invalid")


def _locked_digest_map(
    policy: CurrentSourceReparsePolicy,
    *,
    root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(root, row.path))
        for row in policy.locked_artifacts
    }


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


__all__ = [
    "CurrentSourceReparseError",
    "CurrentSourceReparsePolicy",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "classify_financial_object_slot",
    "classify_captured_document",
    "execute_current_source_reparse",
    "load_current_source_reparse_policy",
    "validate_current_source_reparse_result",
]
