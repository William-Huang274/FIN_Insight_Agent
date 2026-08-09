from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import StrictModel, canonical_digest
from sec_agent.financial_research_core_unchanged_transfer import (
    load_core_unchanged_transfer_policy,
)
from sec_agent.financial_research_held_out_candidate_generation import (
    load_held_out_candidate_generation_policy,
)
from sec_agent.financial_research_source_object_vertical import (
    load_amended_financial_source_object_vertical_policy,
    normalized_sha256,
)


POLICY_SCHEMA = "fin_ia_0_1_3_s1_financial_candidate_bundle_v2_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_financial_candidate_bundle_v2_result_v1_0"
RUN_SCOPE = "S1_FINANCIAL_CANDIDATE_BUNDLE_V2_SUCCESSOR"
EXPECTED_CASE_KEYS = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")


class FinancialCandidateBundleV2Error(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class LockedBundleArtifact(StrictModel):
    artifact_id: str
    path: str
    normalized_sha256: str
    role: str


class BundleCaseInput(StrictModel):
    case_key: str
    policy_kind: str
    policy_ref: str
    policy_sha256: str
    result_ref: str
    result_sha256: str
    reporting_currency: str
    reporting_currency_authority: str


class FinancialCandidateBundleV2Policy(StrictModel):
    schema_version: str
    contract_ref: str
    run_scope: str
    recorded_at: str
    attempt_id: str
    locked_artifacts: tuple[LockedBundleArtifact, ...]
    case_inputs: tuple[BundleCaseInput, ...]
    typed_gap_codes: tuple[str, ...]
    hard_boundaries: dict[str, Any]


class TableSemanticPath(StrictModel):
    table_id: str
    table_header: str
    row_label: str
    column_label: str
    cell_key: str
    context_digest: str


class CurrencyUnitAuthority(StrictModel):
    expected_currency: str
    source_currency: str
    child_currency: str
    scale: str
    canonical_unit: str
    provenance: tuple[str, ...]
    status: str


class FinancialCandidateBundleV2(StrictModel):
    bundle_id: str
    case_key: str
    lane_id: str
    slot_id: str
    evidence_owner_entity_key: str
    evidence_owner_ticker: str
    relationship_direction: str
    asset_id: str
    target_id: str
    source_record_id: str
    object_type: str
    source_locator: str
    source_content_digest: str
    child_content_digest: str
    parent_child_lineage: str
    section: str
    subsection: str
    publication_date: str
    source_reporting_period_end: str
    research_as_of: str
    table_path: TableSemanticPath | None = None
    currency_unit_authority: CurrencyUnitAuthority | None = None
    candidate_state: str = "bundle_candidate_only_not_evidence"


def load_candidate_bundle_v2_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> FinancialCandidateBundleV2Policy:
    root = Path(repo_root).resolve()
    try:
        policy = FinancialCandidateBundleV2Policy.model_validate(
            json.loads(Path(path).read_text(encoding="utf-8"))
        )
    except Exception as exc:
        raise FinancialCandidateBundleV2Error("bundle_v2_policy_shape_invalid") from exc
    if policy.schema_version != POLICY_SCHEMA or policy.run_scope != RUN_SCOPE:
        raise FinancialCandidateBundleV2Error("bundle_v2_policy_identity_invalid")
    if tuple(row.case_key for row in policy.case_inputs) != EXPECTED_CASE_KEYS:
        raise FinancialCandidateBundleV2Error("bundle_v2_case_order_invalid")
    if len({row.artifact_id for row in policy.locked_artifacts}) != len(
        policy.locked_artifacts
    ):
        raise FinancialCandidateBundleV2Error("bundle_v2_locked_identity_invalid")
    for row in policy.locked_artifacts:
        if normalized_sha256(_resolve(root, row.path)) != row.normalized_sha256:
            raise FinancialCandidateBundleV2Error("bundle_v2_locked_digest_mismatch")
    for case in policy.case_inputs:
        if case.policy_kind not in {
            "dell_amended_vertical",
            "known_case_transfer",
            "held_out_candidate",
        }:
            raise FinancialCandidateBundleV2Error("bundle_v2_policy_kind_invalid")
        if normalized_sha256(_resolve(root, case.policy_ref)) != case.policy_sha256:
            raise FinancialCandidateBundleV2Error("bundle_v2_case_policy_digest_mismatch")
        if normalized_sha256(_resolve(root, case.result_ref)) != case.result_sha256:
            raise FinancialCandidateBundleV2Error("bundle_v2_case_result_digest_mismatch")
        if not re.fullmatch(r"[A-Z]{3}", case.reporting_currency):
            raise FinancialCandidateBundleV2Error("bundle_v2_reporting_currency_invalid")
    required_gaps = {
        "source_absent_gap",
        "retrieval_quality_gap",
        "object_context_gap",
    }
    if not required_gaps.issubset(policy.typed_gap_codes):
        raise FinancialCandidateBundleV2Error("bundle_v2_gap_taxonomy_incomplete")
    _validate_zero_call_boundary(policy.hard_boundaries)
    return policy


def execute_candidate_bundle_v2_reproof(
    *,
    policy: FinancialCandidateBundleV2Policy,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    locked_before = _locked_digest_map(policy, root=root)
    case_results = [
        _execute_case(case, repo_root=root) for case in policy.case_inputs
    ]
    locked_after = _locked_digest_map(policy, root=root)
    all_terminal = all(row["stage_acceptance"]["all_candidates_terminal"] for row in case_results)
    identity_clean = all(row["stage_acceptance"]["identity_clean"] for row in case_results)
    unsafe_numeric_admitted = sum(
        row["observed_counts"]["unsafe_numeric_bundle_admissions"] for row in case_results
    )
    status = (
        "bundle_v2_engineering_pass_fail_closed_current_sources_pending"
        if locked_before == locked_after
        and all_terminal
        and identity_clean
        and unsafe_numeric_admitted == 0
        else "bundle_v2_engineering_blocked"
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
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "embedding": 0,
            "rerank": 0,
            "evidence_promotion": 0,
            "local_parent_reads": sum(
                row["observed_counts"]["parent_records_loaded"] for row in case_results
            ),
            "local_object_reads": sum(
                row["observed_counts"]["child_records_loaded"] for row in case_results
            ),
        },
        "stage_acceptance": {
            "candidate_bundle_v2_engineering": status.startswith("bundle_v2_engineering_pass"),
            "currency_unit_conflicts_fail_closed": unsafe_numeric_admitted == 0,
            "six_case_projection_terminal": all_terminal,
            "held_out_product_generalization": False,
            "current_source_coverage": False,
            "sparse_dense_rebuild_admitted": False,
            "external_residual_supplement_admitted": False,
            "model_research_admitted": False,
        },
        "decision_zh": (
            "v2 已把旧候选投影成 child＋parent＋table path 组合，并把币种、数值单元或父子语境不安全的对象拒绝为 typed gap。"
            "这证明结构可以 fail closed；三案当前期官方资料仍缺，因此尚不能进入 sparse／dense 重建。"
        ),
        "known_boundary": (
            "This is a versioned, read-only projection over immutable v1 results. It does not rewrite "
            "historical objects, correct rejected metrics, ingest current sources, build an index, "
            "promote Evidence, call a model or accept a report."
        ),
    }
    return {**body, "result_digest": canonical_digest(body)}


def validate_candidate_bundle_v2_result(payload: Mapping[str, Any]) -> None:
    body = dict(payload)
    digest = str(body.pop("result_digest", ""))
    if body.get("schema_version") != RESULT_SCHEMA or canonical_digest(body) != digest:
        raise FinancialCandidateBundleV2Error("bundle_v2_result_digest_invalid")
    case_results = list(body.get("case_results") or [])
    if tuple(row.get("case_key") for row in case_results) != EXPECTED_CASE_KEYS:
        raise FinancialCandidateBundleV2Error("bundle_v2_result_case_order_invalid")
    for row in case_results:
        counts = dict(row.get("observed_counts") or {})
        if int(counts.get("bundle_projected", -1)) + int(
            counts.get("rejected_typed_gap", -1)
        ) != int(counts.get("candidate_rows", -2)):
            raise FinancialCandidateBundleV2Error("bundle_v2_result_terminal_count_invalid")
        if int(counts.get("unsafe_numeric_bundle_admissions", -1)) != 0:
            raise FinancialCandidateBundleV2Error("bundle_v2_result_unsafe_numeric_admission")
    if body.get("stage_acceptance", {}).get("sparse_dense_rebuild_admitted") is not False:
        raise FinancialCandidateBundleV2Error("bundle_v2_result_rebuild_boundary_invalid")


def project_candidate_bundle_v2(
    *,
    case_key: str,
    research_as_of: str,
    reporting_currency: str,
    reporting_currency_authority: str,
    lane: Mapping[str, Any],
    candidate: Mapping[str, Any],
    parent: Mapping[str, Any] | None,
    child: Mapping[str, Any] | None,
) -> dict[str, Any]:
    codes: list[str] = []
    source_record_id = str(candidate.get("source_record_id") or "")
    target_id = str(candidate.get("target_id") or "")
    expected_ticker = str(lane.get("evidence_owner_ticker") or "")
    if parent is None:
        codes.append("bound_parent_source_record_missing")
    else:
        parent_id = str(parent.get("evidence_id") or parent.get("source_evidence_id") or "")
        if parent_id != source_record_id:
            codes.append("parent_source_identity_mismatch")
        if str(parent.get("ticker") or "") != expected_ticker:
            codes.append("parent_source_ticker_mismatch")

    object_type = str(candidate.get("object_type") or "source_segment")
    child_required = target_id != source_record_id or object_type in {"metric", "claim", "table"}
    if child_required:
        if child is None:
            codes.append("child_object_missing")
        else:
            if str(child.get("object_id") or "") != target_id:
                codes.append("child_object_identity_mismatch")
            if str(child.get("source_evidence_id") or "") != source_record_id:
                codes.append("parent_child_lineage_mismatch")
            if str(child.get("ticker") or "") != expected_ticker:
                codes.append("child_object_ticker_mismatch")

    table_path: TableSemanticPath | None = None
    unit_authority: CurrencyUnitAuthority | None = None
    if object_type == "metric" and parent is not None and child is not None:
        raw_value = str(child.get("raw_value") or "")
        row_label = str(child.get("row_label") or child.get("metric_name") or "")
        column_label = str(child.get("column_label") or "")
        if not _strict_numeric_cell(raw_value, child.get("value")):
            codes.append("numeric_cell_parse_invalid")
        table = _find_parent_table_context(
            str(parent.get("text") or ""),
            row_label=row_label,
            raw_value=raw_value,
            expected_table_id=str(child.get("metadata", {}).get("source_table_id") or ""),
        )
        if not row_label or not column_label or table is None:
            codes.append("table_semantic_path_missing")
        else:
            expected_cell_key = str(
                child.get("metadata", {}).get("table_cell_key")
                or child.get("metadata", {}).get("cell_key")
                or ""
            )
            computed_source_cell_key = _source_cell_key(row_label, column_label)
            table_path = TableSemanticPath(
                table_id=table["table_id"],
                table_header=table["header"],
                row_label=row_label,
                column_label=column_label,
                cell_key=expected_cell_key or _cell_key(row_label, column_label),
                context_digest=hashlib.sha256(table["text"].encode("utf-8")).hexdigest(),
            )
            if expected_cell_key and expected_cell_key != computed_source_cell_key:
                codes.append("table_cell_key_mismatch")
            unit_authority, unit_codes = _reconcile_currency_unit(
                table_text=table["text"],
                child_unit=str(child.get("unit") or ""),
                expected_currency=reporting_currency,
                expected_currency_authority=reporting_currency_authority,
            )
            codes.extend(unit_codes)

    codes = list(dict.fromkeys(codes))
    if codes:
        gap_code = (
            "object_context_gap"
            if any(
                code in {
                    "bound_parent_source_record_missing",
                    "parent_source_identity_mismatch",
                    "child_object_missing",
                    "child_object_identity_mismatch",
                    "parent_child_lineage_mismatch",
                    "table_semantic_path_missing",
                    "table_cell_key_mismatch",
                    "currency_unit_conflict",
                    "currency_unit_authority_missing",
                    "numeric_cell_parse_invalid",
                }
                for code in codes
            )
            else "retrieval_quality_gap"
        )
        return {
            "terminal_state": "rejected_typed_gap",
            "gap_code": gap_code,
            "finding_codes": codes,
            "lane_id": str(lane.get("lane_id") or ""),
            "slot_id": str(lane.get("slot_id") or ""),
            "target_id": target_id,
            "source_record_id": source_record_id,
            "candidate_state": "candidate_only_not_evidence",
        }

    assert parent is not None
    child_digest = canonical_digest(child) if child is not None else ""
    source_digest = hashlib.sha256(str(parent.get("text") or "").encode("utf-8")).hexdigest()
    bundle_body = {
        "case_key": case_key,
        "lane_id": str(lane.get("lane_id") or ""),
        "slot_id": str(lane.get("slot_id") or ""),
        "evidence_owner_entity_key": str(lane.get("evidence_owner_entity_key") or ""),
        "evidence_owner_ticker": expected_ticker,
        "relationship_direction": str(lane.get("relationship_direction") or ""),
        "asset_id": str(candidate.get("asset_id") or lane.get("asset_id") or ""),
        "target_id": target_id,
        "source_record_id": source_record_id,
        "object_type": object_type,
        "source_locator": str(
            parent.get("source_url")
            or candidate.get("source_locator")
            or source_record_id
        ),
        "source_content_digest": source_digest,
        "child_content_digest": child_digest,
        "parent_child_lineage": (
            f"source:{source_record_id}:sha256:{source_digest}"
            + (f"/child:{target_id}:sha256:{child_digest}" if child is not None else "")
        ),
        "section": str((child or parent).get("section") or parent.get("section") or ""),
        "subsection": str((child or parent).get("subsection") or parent.get("subsection") or ""),
        "publication_date": str(parent.get("publication_date") or parent.get("published_at") or ""),
        "source_reporting_period_end": str(parent.get("period_end") or ""),
        "research_as_of": research_as_of,
        "table_path": None if table_path is None else table_path.model_dump(mode="json"),
        "currency_unit_authority": (
            None if unit_authority is None else unit_authority.model_dump(mode="json")
        ),
        "candidate_state": "bundle_candidate_only_not_evidence",
    }
    bundle_id = "financial_candidate_bundle_v2_" + canonical_digest(bundle_body)[:24]
    bundle = FinancialCandidateBundleV2(bundle_id=bundle_id, **bundle_body)
    return {
        "terminal_state": "bundle_projected",
        "gap_code": None,
        "finding_codes": [],
        "bundle": bundle.model_dump(mode="json"),
    }


def _execute_case(case: BundleCaseInput, *, repo_root: Path) -> dict[str, Any]:
    lanes, assets, research_as_of, current_source_available = _load_case_inputs(
        case, repo_root=repo_root
    )
    candidates = [
        (lane, {**candidate, "asset_id": candidate.get("asset_id") or lane.get("asset_id")})
        for lane in lanes
        for candidate in lane.get("candidates", [])
    ]
    parent_requests: dict[Path, set[str]] = defaultdict(set)
    object_requests: dict[tuple[Path, str], set[str]] = defaultdict(set)
    candidate_paths: dict[tuple[str, str], tuple[Path, Path | None]] = {}
    for lane, candidate in candidates:
        asset = assets[str(candidate.get("asset_id") or lane.get("asset_id") or "")]
        source_path = _resolve(repo_root, str(asset["source_records_ref"]))
        object_path = _resolve(repo_root, str(asset["index_ref"]))
        source_id = str(candidate.get("source_record_id") or "")
        target_id = str(candidate.get("target_id") or "")
        parent_requests[source_path].add(source_id)
        child_path: Path | None = None
        if str(asset["retriever_kind"]) == "object_bm25":
            child_path = object_path
            object_requests[(object_path, str(candidate.get("ticker") or ""))].add(target_id)
        candidate_paths[(str(lane["lane_id"]), target_id)] = (source_path, child_path)

    parents = _load_parent_records(parent_requests)
    children = _load_object_records(object_requests)
    projections: list[dict[str, Any]] = []
    for lane, candidate in candidates:
        key = (str(lane["lane_id"]), str(candidate.get("target_id") or ""))
        source_path, child_path = candidate_paths[key]
        parent = parents.get((source_path, str(candidate.get("source_record_id") or "")))
        child = None
        if child_path is not None:
            child = children.get((child_path, str(candidate.get("target_id") or "")))
        projections.append(
            project_candidate_bundle_v2(
                case_key=case.case_key,
                research_as_of=research_as_of,
                reporting_currency=case.reporting_currency,
                reporting_currency_authority=case.reporting_currency_authority,
                lane=lane,
                candidate=candidate,
                parent=parent,
                child=child,
            )
        )

    terminal_counts = Counter(row["terminal_state"] for row in projections)
    finding_counts = Counter(
        code for row in projections for code in row.get("finding_codes", [])
    )
    gap_counts = Counter(
        str(row["gap_code"]) for row in projections if row.get("gap_code")
    )
    wrong_identity = sum(
        count
        for code, count in finding_counts.items()
        if code in {
            "parent_source_ticker_mismatch",
            "child_object_ticker_mismatch",
            "parent_source_identity_mismatch",
            "child_object_identity_mismatch",
        }
    )
    unsafe_numeric_admissions = sum(
        1
        for row in projections
        if row["terminal_state"] == "bundle_projected"
        and row.get("bundle", {}).get("object_type") == "metric"
        and row.get("bundle", {}).get("currency_unit_authority", {}).get("status")
        not in {"source_and_child_consistent", "non_monetary_dimension_preserved"}
    )
    public_projections = [_public_projection(row) for row in projections]
    body = {
        "case_key": case.case_key,
        "reporting_currency": case.reporting_currency,
        "reporting_currency_authority": case.reporting_currency_authority,
        "research_as_of": research_as_of,
        "source_currentness_status": (
            "current_period_candidate_observed"
            if current_source_available
            else "source_absent_gap"
        ),
        "candidate_projections": public_projections,
        "finding_counts": dict(sorted(finding_counts.items())),
        "typed_gap_counts": dict(sorted(gap_counts.items())),
        "observed_counts": {
            "query_lanes": len(lanes),
            "candidate_rows": len(candidates),
            "bundle_projected": terminal_counts["bundle_projected"],
            "rejected_typed_gap": terminal_counts["rejected_typed_gap"],
            "parent_records_loaded": len(parents),
            "child_records_loaded": len(children),
            "unsafe_numeric_bundle_admissions": unsafe_numeric_admissions,
        },
        "stage_acceptance": {
            "all_candidates_terminal": sum(terminal_counts.values()) == len(candidates),
            "identity_clean": wrong_identity == 0,
            "unsafe_numeric_admission_absent": unsafe_numeric_admissions == 0,
            "current_source_available": current_source_available,
            "product_case_complete": False,
        },
    }
    return {**body, "case_result_digest": canonical_digest(body)}


def _load_case_inputs(
    case: BundleCaseInput,
    *,
    repo_root: Path,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str, bool]:
    result_payload = json.loads(_resolve(repo_root, case.result_ref).read_text(encoding="utf-8"))
    if case.policy_kind == "dell_amended_vertical":
        vertical, _contract, compiled, _amendment = load_amended_financial_source_object_vertical_policy(
            _resolve(repo_root, case.policy_ref), repo_root=repo_root
        )
        case_payload = result_payload
        assets = {row.asset_id: row.model_dump(mode="json") for row in vertical.assets}
        research_as_of = compiled.as_of_date
        current_source = True
    elif case.policy_kind == "known_case_transfer":
        transfer = load_core_unchanged_transfer_policy(
            _resolve(repo_root, case.policy_ref), repo_root=repo_root
        )
        definition = next(row for row in transfer.case_policies if row.case_key == case.case_key)
        assets = {row.asset_id: row.model_dump(mode="json") for row in definition.assets}
        case_payload = result_payload
        first_period = next(
            (
                str(row.get("period_binding", {}).get("research_as_of_date") or "")
                for row in case_payload.get("candidate_qualifications", [])
                if row.get("period_binding")
            ),
            "",
        )
        research_as_of = first_period
        current_source = True
    else:
        heldout, _selection, extended = load_held_out_candidate_generation_policy(
            _resolve(repo_root, case.policy_ref), repo_root=repo_root
        )
        plan = next(row for row in heldout.case_plans if row.case_key == case.case_key)
        assets = {row.asset_id: row.model_dump(mode="json") for row in plan.assets}
        case_payload = next(
            row for row in result_payload["case_results"] if row["case_key"] == case.case_key
        )
        selected = next(
            row for row in _selection.selections if row.profile.case_key == case.case_key
        )
        research_as_of = selected.profile.as_of_date
        current_source = bool(case_payload["stage_acceptance"]["current_period_source_available"])
    lanes = [dict(row) for row in case_payload["query_lane_results"]]
    return lanes, assets, research_as_of, current_source


def _load_parent_records(
    requests: Mapping[Path, set[str]],
) -> dict[tuple[Path, str], dict[str, Any]]:
    found: dict[tuple[Path, str], dict[str, Any]] = {}
    for path, wanted in requests.items():
        remaining = set(wanted)
        evidence_id_pattern = re.compile(r'"evidence_id"\s*:\s*"([^"]+)"')
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not remaining:
                    break
                match = evidence_id_pattern.search(line)
                if match is None or match.group(1) not in remaining:
                    continue
                row = json.loads(line)
                source_id = str(row.get("evidence_id") or "")
                if source_id in remaining:
                    found[(path, source_id)] = row
                    remaining.remove(source_id)
    return found


def _load_object_records(
    requests: Mapping[tuple[Path, str], set[str]],
) -> dict[tuple[Path, str], dict[str, Any]]:
    found: dict[tuple[Path, str], dict[str, Any]] = {}
    for (index_path, ticker), wanted in requests.items():
        sqlite_path = index_path / "records.sqlite"
        if not sqlite_path.is_file():
            raise FinancialCandidateBundleV2Error("bundle_v2_object_store_missing")
        con = sqlite3.connect(f"file:{sqlite_path.as_posix()}?mode=ro", uri=True)
        try:
            ordered = sorted(wanted)
            for start in range(0, len(ordered), 400):
                batch = ordered[start : start + 400]
                placeholders = ",".join("?" for _ in batch)
                rows = con.execute(
                    "SELECT object_id, record_json FROM object_records "
                    f"WHERE ticker = ? AND object_id IN ({placeholders})",
                    [ticker, *batch],
                ).fetchall()
                for object_id, record_json in rows:
                    found[(index_path, str(object_id))] = json.loads(record_json)
        finally:
            con.close()
    return found


def _find_parent_table_context(
    text: str,
    *,
    row_label: str,
    raw_value: str,
    expected_table_id: str = "",
) -> dict[str, str] | None:
    if not text or not row_label:
        return None
    blocks = []
    pattern = re.compile(
        r"\[TABLE_START id=(?P<id>[^\s\]]+)[^\]]*\](?P<body>.*?)\[TABLE_END\]",
        re.IGNORECASE | re.DOTALL,
    )
    row_norm = _normalise(row_label)
    raw_norm = _normalise(raw_value)
    for match in pattern.finditer(text):
        if expected_table_id and match.group("id") != expected_table_id:
            continue
        body = " ".join(match.group("body").split())
        body_norm = _normalise(body)
        score = 0
        if row_norm and row_norm in body_norm:
            score += 3
        if raw_norm and raw_norm in body_norm:
            score += 2
        if score:
            blocks.append((score, match.group("id"), body))
    if not blocks:
        return None
    blocks.sort(key=lambda row: (-row[0], row[1]))
    best = blocks[0]
    header = " | ".join(best[2].split("|")[:8])[:500]
    return {"table_id": best[1], "header": header, "text": best[2]}


def _reconcile_currency_unit(
    *,
    table_text: str,
    child_unit: str,
    expected_currency: str,
    expected_currency_authority: str,
) -> tuple[CurrencyUnitAuthority | None, list[str]]:
    source_codes = _currency_codes(table_text)
    source_currency = next(iter(source_codes)) if len(source_codes) == 1 else ""
    child_currency = _currency_from_unit(child_unit)
    scale = _scale_from_unit_or_text(child_unit, table_text)
    normalized_unit = child_unit.strip().casefold()
    if normalized_unit in {"count", "percent"}:
        return (
            CurrencyUnitAuthority(
                expected_currency=expected_currency,
                source_currency=source_currency,
                child_currency="",
                scale="",
                canonical_unit=normalized_unit,
                provenance=(
                    expected_currency_authority,
                    "parent_table_marker" if source_currency else "parent_table_no_currency_marker",
                    "child_non_monetary_unit",
                ),
                status="non_monetary_dimension_preserved",
            ),
            [],
        )
    if normalized_unit == "per_share" or normalized_unit.endswith("_per_share"):
        codes: list[str] = []
        if child_currency and child_currency != expected_currency:
            codes.append("currency_unit_conflict")
        if source_currency and source_currency != expected_currency:
            codes.append("currency_unit_conflict")
        if source_currency and child_currency and source_currency != child_currency:
            codes.append("currency_unit_conflict")
        codes = list(dict.fromkeys(codes))
        if codes:
            return None, codes
        canonical_currency = child_currency or source_currency or expected_currency
        return (
            CurrencyUnitAuthority(
                expected_currency=expected_currency,
                source_currency=source_currency,
                child_currency=child_currency,
                scale="per_share",
                canonical_unit=f"{canonical_currency.lower()}_per_share",
                provenance=(expected_currency_authority, "parent_table_marker", "child_per_share_unit"),
                status="source_and_child_consistent",
            ),
            [],
        )
    codes: list[str] = []
    if len(source_codes) != 1 or not source_currency:
        codes.append("currency_unit_authority_missing")
    if source_currency and source_currency != expected_currency:
        codes.append("currency_unit_conflict")
    if child_currency and source_currency and child_currency != source_currency:
        codes.append("currency_unit_conflict")
    if child_currency and child_currency != expected_currency:
        codes.append("currency_unit_conflict")
    codes = list(dict.fromkeys(codes))
    if codes:
        return None, codes
    canonical_unit = expected_currency.lower() + (f"_{scale}" if scale else "")
    return (
        CurrencyUnitAuthority(
            expected_currency=expected_currency,
            source_currency=source_currency,
            child_currency=child_currency,
            scale=scale,
            canonical_unit=canonical_unit,
            provenance=(expected_currency_authority, "parent_table_marker", "child_metric_unit"),
            status="source_and_child_consistent",
        ),
        [],
    )


def _currency_codes(text: str) -> set[str]:
    lower = text.casefold()
    pairs = {
        "EUR": ("€", " eur", "euro"),
        "USD": ("$", " usd", "u.s. dollar", "us dollar"),
        "GBP": ("£", " gbp", "pound sterling"),
        "CHF": (" chf", "swiss franc"),
        "CNY": (" cny", " rmb", "renminbi"),
        "JPY": (" jpy", "yen"),
        "TWD": (" twd", "nt$", "new taiwan dollar"),
        "KRW": ("₩", " krw", "won"),
    }
    return {
        code for code, markers in pairs.items() if any(marker in lower for marker in markers)
    }


def _currency_from_unit(unit: str) -> str:
    match = re.match(r"(?i)^(usd|eur|gbp|chf|cny|jpy|twd|krw)(?:_|$)", unit.strip())
    return match.group(1).upper() if match else ""


def _scale_from_unit_or_text(unit: str, text: str) -> str:
    lower_unit = unit.casefold()
    lower_text = text.casefold()
    for scale in ("billions", "millions", "thousands"):
        if scale in lower_unit or f"in {scale}" in lower_text:
            return scale
    return ""


def _strict_numeric_cell(raw_value: str, value: Any) -> bool:
    if value is None:
        return False
    raw = " ".join(raw_value.split())
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


def _public_projection(row: Mapping[str, Any]) -> dict[str, Any]:
    if row["terminal_state"] != "bundle_projected":
        return dict(row)
    bundle = dict(row["bundle"])
    return {
        "terminal_state": row["terminal_state"],
        "gap_code": None,
        "finding_codes": [],
        "bundle": bundle,
    }


def _validate_zero_call_boundary(boundary: Mapping[str, Any]) -> None:
    for key in ("network", "provider", "model", "embedding", "rerank", "evidence_promotion"):
        if int(boundary.get(key, -1)) != 0:
            raise FinancialCandidateBundleV2Error("bundle_v2_zero_call_boundary_invalid")
    if (
        boundary.get("historical_results_immutable") is not True
        or boundary.get("ticker_specific_branch_allowed") is not False
        or boundary.get("unsafe_unit_override_allowed") is not False
        or boundary.get("sparse_dense_rebuild_allowed") is not False
    ):
        raise FinancialCandidateBundleV2Error("bundle_v2_authority_boundary_invalid")


def _locked_digest_map(
    policy: FinancialCandidateBundleV2Policy,
    *,
    root: Path,
) -> dict[str, str]:
    return {
        row.artifact_id: normalized_sha256(_resolve(root, row.path))
        for row in policy.locked_artifacts
    }


def _normalise(value: str) -> str:
    return " ".join(value.casefold().split())


def _cell_key(row_label: str, column_label: str) -> str:
    raw = f"{_normalise(row_label)}::{_normalise(column_label)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _source_cell_key(row_label: str, column_label: str) -> str:
    def safe(value: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return cleaned[:80] or "cell"

    return f"{safe(row_label)}__{safe(column_label)}"


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


__all__ = [
    "FinancialCandidateBundleV2",
    "FinancialCandidateBundleV2Error",
    "FinancialCandidateBundleV2Policy",
    "POLICY_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "execute_candidate_bundle_v2_reproof",
    "load_candidate_bundle_v2_policy",
    "project_candidate_bundle_v2",
    "validate_candidate_bundle_v2_result",
]
