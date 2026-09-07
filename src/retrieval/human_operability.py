from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable, Mapping

from .evaluation_assets import (
    load_evaluation_program_manifest,
    validate_evaluation_program,
)
from .query_plan import canonical_digest


PROGRAM_SCHEMA_VERSION = "fin_ia_s1_human_operability_and_blind_gate_program_v1_0"
RESULT_SCHEMA_VERSION = "fin_ia_s1_human_operability_preflight_result_v1_0"
SOURCE_ASSET_RECONCILIATION_SCHEMA_VERSION = (
    "fin_ia_s1_source_asset_reconciliation_v1_0"
)


class HumanOperabilityError(ValueError):
    """Raised when S1 human-operability evidence is missing or drifts."""


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise HumanOperabilityError(code)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanOperabilityError(f"human_operability_json_unreadable:{path}") from exc
    _require(isinstance(value, dict), "human_operability_json_object_required")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bound_json(repo_root: Path, binding: Mapping[str, Any]) -> dict[str, Any]:
    ref = str(binding.get("ref") or "")
    expected = str(binding.get("sha256") or "")
    _require(ref and not Path(ref).is_absolute(), "human_operability_ref_invalid")
    path = repo_root / ref
    _require(path.is_file(), f"human_operability_bound_file_missing:{ref}")
    _require(_sha256(path) == expected, f"human_operability_bound_digest_drift:{ref}")
    return _read_json(path)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                _require(
                    isinstance(value, dict),
                    f"human_operability_jsonl_object_required:{path}:{line_number}",
                )
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise HumanOperabilityError(
            f"human_operability_jsonl_unreadable:{path}"
        ) from exc
    return rows


def _iso_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _source_asset_document_key(row: Mapping[str, Any]) -> str:
    metadata = row.get("metadata")
    if isinstance(metadata, Mapping):
        parent = str(metadata.get("parent_document_id") or "").strip()
        if parent:
            return parent
    for field in ("source_url", "local_path", "evidence_id"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return canonical_digest(dict(row))


def reconcile_source_asset_coverage(
    *,
    source_truth: Mapping[str, Any],
    source_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Distinguish missing source assets from failures after source capture.

    Candidate coverage and source acquisition are different seams.  If a current,
    identity-bound official document is already represented in the canonical
    source-object snapshot, downloading the same filing again cannot repair a
    parser, query, ranking, role or Evidence-admission failure.
    """

    projection = source_truth.get("product_projection")
    _require(
        isinstance(projection, Mapping),
        "human_operability_source_truth_projection_missing",
    )
    raw_requests = projection.get("request_results")
    _require(
        isinstance(raw_requests, list) and raw_requests,
        "human_operability_source_truth_requests_missing",
    )
    normalized_records = [dict(row) for row in source_records]
    request_rows: list[dict[str, Any]] = []
    missing_request_count = 0
    pending_requirement_count = 0
    source_present_requirement_count = 0
    for raw_request in raw_requests:
        _require(
            isinstance(raw_request, Mapping),
            "human_operability_source_truth_request_invalid",
        )
        request = dict(raw_request.get("request") or {})
        truth = dict(raw_request.get("source_route_execution_truth") or {})
        request_id = str(request.get("request_id") or "")
        start = _iso_date((request.get("period") or {}).get("start_date"))
        end = _iso_date(
            (request.get("period") or {}).get("end_date")
            or request.get("research_as_of")
        )
        _require(
            request_id and end is not None,
            "human_operability_source_request_period_invalid",
        )
        requirements: list[dict[str, Any]] = []
        for raw_requirement in truth.get("requirements") or ():
            _require(
                isinstance(raw_requirement, Mapping),
                "human_operability_source_requirement_invalid",
            )
            if raw_requirement.get("candidate_coverage_state") != "incomplete":
                continue
            owner = str(
                raw_requirement.get("evidence_owner_ticker") or ""
            ).upper()
            source_types = {
                str(item).upper()
                for item in raw_requirement.get("source_types") or ()
            }
            matched: dict[str, dict[str, Any]] = {}
            for record in normalized_records:
                published = _iso_date(record.get("publication_date"))
                if (
                    str(record.get("ticker") or "").upper() != owner
                    or str(record.get("source_type") or "").upper()
                    not in source_types
                    or published is None
                    or published > end
                    or (start is not None and published < start)
                ):
                    continue
                key = _source_asset_document_key(record)
                current = matched.get(key)
                candidate = {
                    "source_type": str(record.get("source_type") or "").upper(),
                    "publication_date": published.isoformat(),
                    "source_tier": record.get("source_tier"),
                }
                if current is None or candidate["publication_date"] > current[
                    "publication_date"
                ]:
                    matched[key] = candidate
            documents = sorted(
                matched.values(),
                key=lambda row: (row["publication_date"], row["source_type"]),
                reverse=True,
            )
            asset_present = bool(documents)
            if asset_present:
                source_present_requirement_count += 1
                state = "current_official_source_asset_present"
                earliest_owner = "S1_object_query_recall_ranking"
                next_action = (
                    "不要重复下载同一官方文件；回查对象化、query facets、候选召回、"
                    "金融排序和 Evidence Role，必要时对已捕获原文作人工非披露裁决。"
                )
            else:
                pending_requirement_count += 1
                state = "official_source_asset_acquisition_required"
                earliest_owner = "S1_source_route_execution"
                next_action = (
                    "执行与披露主体、期间和来源类型绑定的官方来源路线；原始响应先保存，"
                    "失败时保留传输或解析终态，不能直接声明公开资料不存在。"
                )
            requirements.append(
                {
                    "requirement_id": raw_requirement.get("requirement_id"),
                    "evidence_owner_ticker": owner,
                    "required_source_role": raw_requirement.get(
                        "required_source_role"
                    ),
                    "source_types": sorted(source_types),
                    "period_start": start.isoformat() if start else None,
                    "period_end": end.isoformat(),
                    "source_asset_state": state,
                    "matched_document_count": len(documents),
                    "matched_source_types": sorted(
                        {row["source_type"] for row in documents}
                    ),
                    "latest_publication_date": (
                        documents[0]["publication_date"] if documents else None
                    ),
                    "earliest_owner": earliest_owner,
                    "operator_action_zh": next_action,
                }
            )
        acquisition_required = any(
            row["source_asset_state"]
            == "official_source_asset_acquisition_required"
            for row in requirements
        )
        if acquisition_required:
            missing_request_count += 1
        request_rows.append(
            {
                "request_id": request_id,
                "business_question_zh": request.get("business_question_zh"),
                "official_source_acquisition_required": acquisition_required,
                "candidate_coverage_incomplete_requirement_count": len(
                    requirements
                ),
                "requirements": requirements,
            }
        )
    body = {
        "schema_version": SOURCE_ASSET_RECONCILIATION_SCHEMA_VERSION,
        "status": "source_assets_reconciled_without_network_or_model",
        "case_key": projection.get("case_key"),
        "request_count": len(request_rows),
        "official_source_acquisition_required_request_count": missing_request_count,
        "official_source_acquisition_required_requirement_count": (
            pending_requirement_count
        ),
        "current_official_source_asset_present_requirement_count": (
            source_present_requirement_count
        ),
        "requests": request_rows,
        "authority": {
            "source_asset_is_evidence": False,
            "candidate_is_evidence": False,
            "public_information_gap_authority": False,
            "network_calls": 0,
            "model_calls": 0,
        },
    }
    return {**body, "reconciliation_digest": canonical_digest(body)}


def _operator_disposition(
    row: Mapping[str, Any],
    *,
    source_asset_reconciliation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = str(row.get("readiness_state") or "")
    route = dict(
        row.get("source_route_execution_truth")
        or row.get("route_execution_state")
        or {}
    )
    if state == "blocked_by_candidate_coverage":
        if source_asset_reconciliation and not source_asset_reconciliation.get(
            "official_source_acquisition_required"
        ):
            owner = "S1_object_query_recall_ranking"
            failure = "source_present_candidate_coverage_failure"
            action = (
                "当前期间的官方来源已在本地对象快照中；不要重复下载，改查 parser/对象化、"
                "query facets、召回、排序与 Evidence Role。"
            )
        elif (
            route.get("source_supplement_route_required") is True
            and route.get("official_or_external_supplement_route_exhausted") is not True
        ):
            owner = "S1_source_route_execution"
            failure = "route_not_executed"
            action = "执行已允许的官方路线并保存 capture-bound terminal receipt；失败也必须保留传输/解析原因。"
        else:
            owner = "S1_object_query_recall_ranking"
            failure = "candidate_not_recalled"
            action = "按对象、公司、期间、来源角色、关系方向和 material requirement 回查召回与排序。"
    elif state == "blocked_by_evidence_admission":
        owner = "S1_evidence_gate"
        failure = "candidate_not_admitted"
        action = "由合格评审者作 accept/reject/needs-review；排名或相似度不能自动晋升 Evidence。"
    elif state == "blocked_by_local_data_materialization":
        owner = "S1_parser_object_store"
        failure = "parser_or_object_failure"
        action = "回查 capture、OCR/parser、表格/claim/context 对象化和当前 snapshot 绑定。"
    elif state == "blocked_by_retrieval_quality":
        owner = "S1_index_query_recall_ranking"
        failure = "index_or_query_failure"
        action = "在冻结请求下检查索引、query facets、候选 union、重排与 Evidence Role。"
    elif state == "blocked_by_source_access":
        owner = "S1_source_transport"
        failure = "source_transport_failure"
        action = "保存原始失败 capture 与 terminal receipt，验证等价官方路径或人工官方上传。"
    elif state == "partial_with_material_gaps":
        owner = "S1_gap_eligibility"
        failure = "gap_not_yet_eligible_as_public_boundary"
        action = "读取 GapEligibilityReceipt；先关闭未执行路线、候选和 admission blockers，再裁决信息边界。"
    elif state == "blocked_by_numeric_or_bridge_authority":
        owner = "S2_numeric_fact"
        failure = "numeric_fact_or_bridge_authority"
        action = "用 SQL/NumericFact 处理同公司、期间、单位和口径；文本检索不承担精确数值权威。"
    elif state == "ready_for_current_scope":
        owner = "none"
        failure = "none"
        action = "当前请求可供下游消费；仍不等于整个 Case、S1 或发布通过。"
    else:
        owner = "S1_contract_control"
        failure = "unclassified_s1_state"
        action = "停止并修复 typed readiness 合同，不允许模型猜测下一步。"
    return {
        "earliest_owner": owner,
        "failure_class": failure,
        "operator_action_zh": action,
    }


def _validate_receipt_digest(value: Mapping[str, Any], code: str) -> None:
    digest = str(value.get("receipt_digest") or "")
    unsigned = {key: item for key, item in value.items() if key != "receipt_digest"}
    _require(digest == canonical_digest(unsigned), code)


def validate_qualified_human_evidence_receipts(
    *,
    program: Mapping[str, Any],
    receipts: list[Mapping[str, Any]],
    valid_candidate_bindings: Mapping[
        tuple[str, str, str, str], Mapping[str, str]
    ],
) -> dict[str, Any]:
    contract = dict(
        (program.get("external_authority_gates") or {}).get(
            "qualified_human_evidence_admission"
        )
        or {}
    )
    required = set(contract.get("required_receipt_fields") or ()) | {
        "requirement_id"
    }
    seen: set[tuple[str, str, str, str]] = set()
    decisions: dict[str, int] = {"accepted": 0, "rejected": 0, "needs_review": 0}
    for raw in receipts:
        value = dict(raw)
        _require(required.issubset(value), "human_evidence_receipt_fields_missing")
        binding = (
            str(value.get("case_key") or "").upper(),
            str(value.get("request_id") or ""),
            str(value.get("requirement_id") or ""),
            str(value.get("candidate_or_evidence_ref") or ""),
        )
        expected = valid_candidate_bindings.get(binding)
        _require(
            expected is not None,
            "human_evidence_receipt_candidate_binding_invalid",
        )
        _require(binding not in seen, "human_evidence_receipt_duplicate")
        seen.add(binding)
        _require(
            str(value.get("candidate_admission_item_digest") or "")
            == expected.get("candidate_admission_item_digest")
            and str(value.get("source_lineage_digest") or "")
            == expected.get("source_lineage_digest"),
            "human_evidence_receipt_lineage_digest_invalid",
        )
        decision = str(value.get("decision") or "")
        _require(decision in decisions, "human_evidence_receipt_decision_invalid")
        bindings = dict(value.get("source_period_role_and_proposition_binding") or {})
        required_bindings = {
            "case_identity_bound",
            "source_bound",
            "period_bound",
            "evidence_role_bound",
            "proposition_bound",
        }
        _require(
            required_bindings.issubset(bindings),
            "human_evidence_receipt_authority_binding_missing",
        )
        if decision == "accepted":
            _require(
                all(bindings[key] is True for key in required_bindings),
                "human_evidence_acceptance_binding_invalid",
            )
        _validate_receipt_digest(value, "human_evidence_receipt_digest_invalid")
        decisions[decision] += 1
    expected_count = len(valid_candidate_bindings)
    coverage_complete = len(seen) == expected_count
    gate_complete = coverage_complete and decisions["needs_review"] == 0
    return {
        "receipt_count": len(receipts),
        "unique_candidate_binding_count": len(seen),
        "expected_candidate_binding_count": expected_count,
        "unreviewed_candidate_binding_count": expected_count - len(seen),
        "decision_counts": decisions,
        "all_receipts_valid": True,
        "all_candidate_bindings_reviewed": coverage_complete,
        "admission_gate_state": "complete" if gate_complete else "pending",
        "current_readiness_must_be_rematerialized_after_decisions": True,
    }


def validate_external_blind_qualification_receipt(
    *,
    program: Mapping[str, Any],
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    contract = dict(
        (program.get("external_authority_gates") or {}).get(
            "replacement_blind_qualification"
        )
        or {}
    )
    value = dict(receipt)
    required = set(contract.get("required_receipt_fields") or ())
    _require(required.issubset(value), "blind_receipt_fields_missing")
    cases = {str(item).upper() for item in value.get("case_keys") or ()}
    forbidden = {
        str(item).upper()
        for item in contract.get("observed_or_disclosed_cases_forbidden") or ()
    }
    _require(cases and not (cases & forbidden), "blind_receipt_case_overlap_invalid")
    _require(
        len(cases) >= int(contract.get("minimum_case_count") or 0),
        "blind_receipt_case_count_insufficient",
    )
    _require(
        value.get("label_store_outside_repo") is True
        and value.get("label_store_git_tracked") is False,
        "blind_receipt_label_isolation_invalid",
    )
    _require(
        value.get("runtime_read_reference_before_candidate_freeze") is False,
        "blind_receipt_runtime_label_leak",
    )
    overlap = dict(value.get("case_overlap_check") or {})
    _require(
        overlap.get("overlap_count") == 0 and overlap.get("passed") is True,
        "blind_receipt_overlap_check_invalid",
    )
    hard_gates = dict(value.get("hard_gate_results") or {})
    required_dimensions = set(contract.get("required_case_design_dimensions") or ())
    dimensions = dict(value.get("case_design_coverage") or {})
    _require(
        required_dimensions
        and required_dimensions.issubset(dimensions)
        and all(dimensions[key] is True for key in required_dimensions),
        "blind_receipt_case_design_incomplete",
    )
    required_hard_gates = set(contract.get("required_hard_gates") or ())
    _require(
        required_hard_gates
        and required_hard_gates.issubset(hard_gates)
        and all(hard_gates[key] is True for key in required_hard_gates),
        "blind_receipt_hard_gate_failed",
    )
    metrics = value.get("aggregate_metric_results")
    failure_examples = value.get("business_failure_examples")
    _require(
        isinstance(metrics, Mapping)
        and bool(metrics)
        and isinstance(failure_examples, list),
        "blind_receipt_quality_evidence_missing",
    )
    _validate_receipt_digest(value, "blind_receipt_digest_invalid")
    return {
        "external_program_id": value["external_program_id"],
        "case_count": len(cases),
        "case_keys_digest": canonical_digest(sorted(cases)),
        "hard_gate_count": len(hard_gates),
        "status": "external_blind_receipt_validated",
        "receipt_digest": value["receipt_digest"],
    }


def compile_human_operability_preflight(
    *,
    repo_root: str | Path,
    program: Mapping[str, Any],
    recorded_at: str,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    _require(
        program.get("schema_version") == PROGRAM_SCHEMA_VERSION,
        "human_operability_program_schema_invalid",
    )
    _require(
        program.get("status") == "active_preflight_external_authority_pending",
        "human_operability_program_status_invalid",
    )
    evaluation_binding = dict(program.get("evaluation_program") or {})
    evaluation_payload = _bound_json(root, evaluation_binding)
    evaluation_path = root / str(evaluation_binding["ref"])
    evaluation_manifest = load_evaluation_program_manifest(evaluation_path)
    evaluation_summary = validate_evaluation_program(
        repo_root=root, manifest=evaluation_manifest
    )
    _require(
        evaluation_payload.get("program_id") == evaluation_manifest.program_id,
        "human_operability_evaluation_program_drift",
    )

    cases = []
    all_actionable = True
    all_zero_generation = True
    remaining_source_requests = 0
    evidence_admission_requests = 0
    evidence_admission_requirements = 0
    public_gap_eligible_requests = 0
    for binding in program.get("development_case_readiness") or ():
        readiness = _bound_json(root, dict(binding))
        case_key = str(readiness.get("case_key") or "").upper()
        _require(
            case_key == str(binding.get("case_key") or "").upper(),
            "human_operability_case_binding_mismatch",
        )
        full_ref = str(readiness.get("full_result_ref") or "")
        full_path = root / full_ref
        _require(full_path.is_file(), "human_operability_private_full_result_missing")
        _require(
            _sha256(full_path) == readiness.get("full_result_sha256"),
            "human_operability_private_full_result_digest_drift",
        )
        full = _read_json(full_path)
        pack_readiness = dict(full.get("pack_readiness") or {})
        pending_requirements_by_request = {
            str(request.get("request_id") or ""): [
                str(requirement.get("requirement_id") or "")
                for requirement in request.get("requirements") or ()
                if requirement.get("readiness_state")
                == "blocked_by_evidence_admission"
            ]
            for request in pack_readiness.get("requests") or ()
        }
        source_binding = dict((full.get("source_bindings") or {}).get("candidate_replay") or {})
        source_ref = str(source_binding.get("ref") or "")
        source_path = root / source_ref
        _require(source_path.is_file(), "human_operability_source_truth_missing")
        _require(
            _sha256(source_path) == source_binding.get("sha256"),
            "human_operability_source_truth_digest_drift",
        )
        source_truth = _read_json(source_path)
        record_binding = dict(
            (full.get("source_bindings") or {}).get("current_source_records")
            or {}
        )
        record_ref = str(record_binding.get("ref") or "")
        record_path = root / record_ref
        _require(
            record_path.is_file(),
            "human_operability_current_source_records_missing",
        )
        _require(
            _sha256(record_path) == record_binding.get("sha256"),
            "human_operability_current_source_records_digest_drift",
        )
        source_asset_reconciliation = reconcile_source_asset_coverage(
            source_truth=source_truth,
            source_records=_read_jsonl(record_path),
        )
        source_by_request = {
            str(item.get("request_id") or ""): item
            for item in source_asset_reconciliation["requests"]
        }
        execution = dict(source_truth.get("execution_summary") or {})
        zero_generation = execution.get("model_calls") == 0
        all_zero_generation = all_zero_generation and zero_generation

        request_rows = []
        for raw in readiness.get("requests") or ():
            row = dict(raw)
            question = str(row.get("business_question_zh") or "").strip()
            route = dict(row.get("source_route_execution_truth") or {})
            source_reconciliation = source_by_request.get(
                str(row.get("request_id") or ""), {}
            )
            disposition = _operator_disposition(
                row,
                source_asset_reconciliation=source_reconciliation,
            )
            actionable = bool(
                question
                and row.get("request_id")
                and row.get("slot_id")
                and row.get("facet_id")
                and disposition["operator_action_zh"]
                and route.get("source_route_execution_truth_bound") is True
            )
            all_actionable = all_actionable and actionable
            if source_reconciliation.get(
                "official_source_acquisition_required"
            ) is True:
                remaining_source_requests += 1
            pending_requirement_ids = pending_requirements_by_request.get(
                str(row.get("request_id") or ""), []
            )
            if pending_requirement_ids:
                evidence_admission_requests += 1
            evidence_admission_requirements += len(pending_requirement_ids)
            if route.get("public_information_gap_eligible") is True:
                public_gap_eligible_requests += 1
            request_rows.append(
                {
                    "request_id": row.get("request_id"),
                    "slot_id": row.get("slot_id"),
                    "facet_id": row.get("facet_id"),
                    "business_question_zh": question,
                    "readiness_state": row.get("readiness_state"),
                    "candidate_decision_counts": row.get("candidate_decision_counts"),
                    "pending_evidence_admission_requirement_ids": pending_requirement_ids,
                    "numeric_authority_state": row.get("numeric_authority_state"),
                    "route_execution_state_counts": route.get(
                        "source_route_execution_state_counts"
                    ),
                    "source_asset_reconciliation": source_reconciliation,
                    "public_information_gap_eligible": route.get(
                        "public_information_gap_eligible", False
                    ),
                    "operator_actionable": actionable,
                    **disposition,
                }
            )
        cases.append(
            {
                "case_key": case_key,
                "readiness_state": readiness.get("readiness_state"),
                "request_count": len(request_rows),
                "zero_generation_model_source_truth_replay": zero_generation,
                "source_asset_reconciliation_digest": (
                    source_asset_reconciliation["reconciliation_digest"]
                ),
                "requests": request_rows,
            }
        )

    external = dict(program.get("external_authority_gates") or {})
    human_gate = dict(external.get("qualified_human_evidence_admission") or {})
    blind_gate = dict(external.get("replacement_blind_qualification") or {})
    gate_states = {
        "ai_free_human_operability": (
            "engineering_pass" if all_actionable and all_zero_generation else "failed"
        ),
        "remaining_official_source_execution": (
            "pass" if remaining_source_requests == 0 else "pending"
        ),
        "evidence_admission": (
            "pass"
            if evidence_admission_requests == 0
            and human_gate.get("state") == "complete"
            else "pending_qualified_human"
        ),
        "replacement_blind_qualification": (
            "pass" if blind_gate.get("state") == "complete" else "pending_external"
        ),
    }
    qualified = all(value in {"pass", "engineering_pass"} for value in gate_states.values())
    unsigned = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": (
            "S1_qualified_stable"
            if qualified
            else "human_operability_engineering_ready_external_gates_open"
            if remaining_source_requests == 0
            else "human_operability_engineering_ready_external_and_source_gates_open"
        ),
        "recorded_at": recorded_at,
        "program_id": program.get("program_id"),
        "evaluation_program_summary": evaluation_summary,
        "gate_states": gate_states,
        "summary": {
            "development_case_count": len(cases),
            "request_count": sum(row["request_count"] for row in cases),
            "remaining_source_request_count": remaining_source_requests,
            "evidence_admission_request_count": evidence_admission_requests,
            "evidence_admission_requirement_count": evidence_admission_requirements,
            "public_information_gap_eligible_request_count": public_gap_eligible_requests,
            "generation_model_calls": 0 if all_zero_generation else "unverified",
        },
        "cases": cases,
        "external_authority": {
            "qualified_human_evidence_admission": human_gate.get("state"),
            "replacement_blind_qualification": blind_gate.get("state"),
            "disclosed_regression_cases_cannot_support_blind_claim": True,
        },
        "authority": {
            "candidate_is_evidence": False,
            "numeric_fact_authority": False,
            "public_information_gap_authority": False,
            "S1_qualified_stable": qualified,
            "product_or_release_authority": False,
        },
    }
    return {**unsigned, "result_digest": canonical_digest(unsigned)}


def load_human_operability_program(path: str | Path) -> dict[str, Any]:
    return _read_json(Path(path))


__all__ = [
    "HumanOperabilityError",
    "PROGRAM_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "SOURCE_ASSET_RECONCILIATION_SCHEMA_VERSION",
    "compile_human_operability_preflight",
    "load_human_operability_program",
    "reconcile_source_asset_coverage",
    "validate_external_blind_qualification_receipt",
    "validate_qualified_human_evidence_receipts",
]
