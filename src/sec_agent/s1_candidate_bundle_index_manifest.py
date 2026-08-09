from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.object_store import FileCanonicalObjectStore


POLICY_SCHEMA = "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_policy_v1_0"
RESULT_SCHEMA = "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_proof_v1_0"
PRIVATE_MANIFEST_SCHEMA = "fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_private_manifest_v1_0"
RUN_SCOPE = "S1_IMMUTABLE_SUPPLEMENTAL_DENSE_INDEX_REPLACEMENT_BUILD"
EXPECTED_CASE_KEYS = ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
KNOWN_CASE_KEYS = ("DELL", "MU", "NVDA")
HELD_OUT_CASE_KEYS = ("ORCL", "ASML", "ANET")
ATTEMPT_PREDECESSOR_FAILURE_REFS = {
    "20260810_s1_six_case_candidate_bundle_sparse_dense_manifest_zero_call_r3": (
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r1_failure_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r2_failure_v1_0.json",
    ),
    "20260810_s1_six_case_candidate_bundle_sparse_dense_manifest_zero_call_r4": (
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r1_failure_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r2_failure_v1_0.json",
        "configs/releases/fin_ia_0_1_3_s1_candidate_bundle_sparse_dense_manifest_zero_call_r3_business_audit_failure_v1_0.json",
    ),
}
EXPECTED_MUTATIONS = (
    "duplicate_candidate_identity",
    "missing_bundle_binding",
    "source_digest_drift",
    "child_digest_drift",
    "metric_table_path_missing",
    "metric_currency_authority_missing",
    "metric_period_missing",
    "metric_period_role_missing",
    "metric_unit_mismatch",
    "cross_case_identity",
    "future_publication",
    "automatic_narrative_infiltration",
    "vector_text_drift",
    "sparse_partial_insert",
    "dense_partial_insert",
)


class CandidateBundleIndexManifestError(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise CandidateBundleIndexManifestError(code)


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    _require(isinstance(value, dict), "candidate_bundle_index_json_object_required")
    return value


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _plain_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalise_text(value: str, *, limit: int = 2200) -> str:
    return " ".join(value.split())[:limit]


def _artifact_map(policy: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = [dict(item) for item in policy.get("locked_artifacts") or []]
    return {str(item.get("artifact_id") or ""): item for item in rows}


def _has_forbidden_selection_input(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(
            "qrel" in str(key).casefold()
            or "gold" in str(key).casefold()
            or _has_forbidden_selection_input(item)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_has_forbidden_selection_input(item) for item in value)
    return False


def load_candidate_bundle_index_policy(
    path: str | Path,
    *,
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    policy = _read_json(Path(path))
    _require(
        policy.get("schema_version") == POLICY_SCHEMA
        and policy.get("result_schema") == RESULT_SCHEMA
        and policy.get("run_scope") == RUN_SCOPE
        and policy.get("contract_ref")
        == "fin_0_1_3.S1.candidate_bundle_sparse_dense_manifest:v1",
        "candidate_bundle_index_policy_identity_invalid",
    )
    artifacts = _artifact_map(policy)
    _require(
        len(artifacts) == len(policy.get("locked_artifacts") or [])
        and set(artifacts)
        == {
            "dell_policy",
            "known_transfer_policy",
            "dell_result",
            "mu_result",
            "nvda_result",
            "bundle_v2_result",
            "held_out_reparse_result",
            "held_out_clean_proof",
            "ubuntu_milvus_canary",
        },
        "candidate_bundle_index_locked_artifact_set_invalid",
    )
    for artifact in artifacts.values():
        target = _resolve(root, str(artifact.get("path") or ""))
        _require(
            target.is_file()
            and _normalized_sha256(target)
            == str(artifact.get("normalized_sha256") or ""),
            "candidate_bundle_index_locked_artifact_digest_mismatch",
        )
    attempt_id = str(policy.get("attempt_id") or "")
    _require(
        attempt_id in ATTEMPT_PREDECESSOR_FAILURE_REFS
        and tuple(policy.get("predecessor_failure_refs") or ())
        == ATTEMPT_PREDECESSOR_FAILURE_REFS[attempt_id],
        "candidate_bundle_index_attempt_lineage_invalid",
    )
    held_out_result = _read_json(
        _resolve(root, str(artifacts["held_out_reparse_result"]["path"]))
    )
    held_out_proof = _read_json(
        _resolve(root, str(artifacts["held_out_clean_proof"]["path"]))
    )
    held_out_result_path = str(artifacts["held_out_reparse_result"]["path"])
    proof_source_bindings = dict(held_out_proof.get("source_bindings") or {})
    proof_acceptance = dict(held_out_proof.get("stage_acceptance") or {})
    _require(
        held_out_proof.get("source_result_ref") == held_out_result_path
        and held_out_proof.get("source_result_digest")
        == held_out_result.get("result_digest")
        and proof_source_bindings.get(held_out_result_path)
        == artifacts["held_out_reparse_result"]["normalized_sha256"]
        and proof_acceptance.get("clean_independent_reproof") is True
        and proof_acceptance.get(
            "candidate_bundle_only_sparse_dense_manifest_rebaseline_admitted"
        )
        is True,
        "candidate_bundle_index_held_out_clean_proof_binding_invalid",
    )
    private_inputs = dict(policy.get("private_object_inputs") or {})
    result_attempt_match = re.search(
        r"successor_(r\d+)_result_v1_0\.json$",
        held_out_result_path,
    )
    _require(
        result_attempt_match is not None
        and str(private_inputs.get("held_out_reparse_runtime_root_ref") or "").endswith(
            "/zero-call-" + result_attempt_match.group(1)
        )
        and private_inputs.get("objects_are_digest_bound_by_public_reparse_result")
        is True
        and private_inputs.get("raw_source_text_may_enter_public_proof") is False,
        "candidate_bundle_index_private_input_binding_invalid",
    )
    selection = dict(policy.get("selection_contract") or {})
    expected_counts = dict(selection.get("expected_primary_specs_by_case") or {})
    _require(
        tuple(expected_counts) == EXPECTED_CASE_KEYS
        and sum(int(value) for value in expected_counts.values())
        == int(selection.get("expected_primary_spec_count") or 0)
        and selection.get("known_cases_require_reviewed_qualification") is True
        and selection.get("held_out_metrics_require_complete_table_authority") is True
        and selection.get("held_out_metrics_require_period_role") is True
        and selection.get("automatic_narrative_claims_enter_primary_index") is False
        and int(selection.get("expected_narrative_review_queue_count") or 0) >= 1
        and _has_forbidden_selection_input(policy) is False,
        "candidate_bundle_index_selection_contract_invalid",
    )
    index = dict(policy.get("index_contract") or {})
    _require(
        index.get("shared_manifest_for_sparse_and_dense") is True
        and index.get("sparse_kind") == "object_bm25"
        and index.get("dense_kind") == "bge_m3_milvus"
        and int(index.get("embedding_dimension") or 0) == 1024
        and int(index.get("fake_batch_size") or 0) > 0
        and index.get("historical_indexes_read_only") is True,
        "candidate_bundle_index_backend_contract_invalid",
    )
    platform = dict(policy.get("future_real_build_platform") or {})
    _require(
        platform.get("required_os") == "linux"
        and platform.get("required_distribution") == "Ubuntu-22.04"
        and platform.get("windows_milvus_lite_eligible") is False
        and platform.get("real_build_authorized") is False
        and str(platform.get("private_target_prefix") or "").startswith(
            "/home/william/.cache/fin_insight/"
        ),
        "candidate_bundle_index_platform_contract_invalid",
    )
    hard = dict(policy.get("hard_boundaries") or {})
    for key in (
        "network",
        "provider",
        "model",
        "document_fetch",
        "real_embedding",
        "milvus_read",
        "milvus_write",
        "rerank",
        "evidence_promotion",
    ):
        _require(
            int(hard.get(key, -1)) == 0,
            "candidate_bundle_index_zero_call_boundary_invalid",
        )
    _require(
        hard.get("may_write_real_sparse_index") is False
        and hard.get("may_write_real_dense_index") is False
        and hard.get("may_promote_candidate_to_evidence") is False
        and hard.get("may_call_deepseek") is False,
        "candidate_bundle_index_authority_boundary_invalid",
    )
    _require(
        tuple(policy.get("required_mutations") or ()) == EXPECTED_MUTATIONS,
        "candidate_bundle_index_mutation_contract_invalid",
    )
    return policy


def _case_result(result: Mapping[str, Any], case_key: str) -> dict[str, Any]:
    matches = [
        dict(item)
        for item in result.get("case_results") or []
        if str(item.get("case_key") or "") == case_key
    ]
    _require(len(matches) == 1, "candidate_bundle_index_case_result_missing")
    return matches[0]


def _finalize_spec(body: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(body)
    return {**payload, "spec_digest": canonical_digest(payload)}


def _known_case_specs(
    *,
    case_key: str,
    result: Mapping[str, Any],
    bundle_case_result: Mapping[str, Any],
) -> list[dict[str, Any]]:
    lane_candidates: dict[tuple[str, str], dict[str, Any]] = {}
    for lane in result.get("query_lane_results") or []:
        lane_id = str(lane.get("lane_id") or "")
        for candidate in lane.get("candidates") or []:
            lane_candidates[(lane_id, str(candidate.get("target_id") or ""))] = dict(
                candidate
            )
    bundle_index: dict[tuple[str, str], dict[str, Any]] = {}
    for projection in bundle_case_result.get("candidate_projections") or []:
        if projection.get("terminal_state") != "bundle_projected":
            continue
        bundle = dict(projection.get("bundle") or {})
        bundle_index[(str(bundle.get("lane_id") or ""), str(bundle.get("target_id") or ""))] = bundle

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for qualification in result.get("candidate_qualifications") or []:
        _require(
            qualification.get("qualification_status") == "qualified"
            and qualification.get("candidate_state") == "candidate_only_not_evidence",
            "candidate_bundle_index_unqualified_known_candidate",
        )
        lane_id = str(qualification.get("lane_id") or "")
        target_id = str(qualification.get("target_id") or "")
        candidate = lane_candidates.get((lane_id, target_id))
        bundle = bundle_index.get((lane_id, target_id))
        _require(
            candidate is not None and bundle is not None,
            "candidate_bundle_index_known_candidate_binding_missing",
        )
        grouped[target_id].append(
            {
                "qualification": dict(qualification),
                "candidate": candidate,
                "bundle": bundle,
            }
        )

    specs: list[dict[str, Any]] = []
    for target_id in sorted(grouped):
        rows = grouped[target_id]
        bundles = [row["bundle"] for row in rows]
        invariant_fields = (
            "case_key",
            "target_id",
            "source_record_id",
            "object_type",
            "source_locator",
            "source_content_digest",
            "child_content_digest",
            "parent_child_lineage",
            "publication_date",
            "source_reporting_period_end",
            "research_as_of",
        )
        for field in invariant_fields:
            _require(
                len({json.dumps(item.get(field), sort_keys=True) for item in bundles}) == 1,
                "candidate_bundle_index_known_bundle_invariant_mismatch",
            )
        anchor = bundles[0]
        previews = {
            _normalise_text(str(row["candidate"].get("preview") or ""), limit=2200)
            for row in rows
        }
        previews.discard("")
        _require(bool(previews), "candidate_bundle_index_known_preview_missing")
        source_text = max(previews, key=lambda item: (len(item), item))
        slot_ids = sorted(
            {str(row["qualification"].get("slot_id") or "") for row in rows}
        )
        facet_ids = sorted(
            {
                str(facet)
                for row in rows
                for facet in row["qualification"].get("facet_ids") or []
            }
        )
        bundle_bindings = sorted(
            (
                {
                    "bundle_id": str(row["bundle"].get("bundle_id") or ""),
                    "lane_id": str(row["bundle"].get("lane_id") or ""),
                    "slot_id": str(row["bundle"].get("slot_id") or ""),
                    "qualification_id": str(
                        row["qualification"].get("qualification_id") or ""
                    ),
                    "candidate_id": str(
                        row["qualification"].get("candidate_id") or ""
                    ),
                }
                for row in rows
            ),
            key=lambda item: (
                item["bundle_id"],
                item["qualification_id"],
            ),
        )
        vector_text = (
            f"case={case_key} | slots={','.join(slot_ids)} | "
            f"facets={','.join(facet_ids)} | object={anchor['object_type']} | "
            f"period_end={anchor['source_reporting_period_end']}\n{source_text}"
        )
        vector_id = "cbidx_" + canonical_digest(
            {
                "case_key": case_key,
                "target_id": target_id,
                "bundle_ids": [item["bundle_id"] for item in bundle_bindings],
            }
        )[:32]
        body = {
            "vector_id": vector_id,
            "canonical_candidate_identity": f"{case_key}::{target_id}",
            "case_key": case_key,
            "ticker": case_key,
            "evidence_owner_ticker": str(
                anchor.get("evidence_owner_ticker") or ""
            ),
            "target_id": target_id,
            "source_record_id": str(anchor.get("source_record_id") or ""),
            "object_type": str(anchor.get("object_type") or ""),
            "quality_tier": "reviewed_financial_candidate",
            "selection_basis": "reviewed_candidate_qualification",
            "candidate_state": "bundle_candidate_only_not_evidence",
            "bundle_bindings": bundle_bindings,
            "slot_ids": slot_ids,
            "facet_ids": facet_ids,
            "relationship_directions": sorted(
                {str(item.get("relationship_direction") or "") for item in bundles}
            ),
            "source_locator": str(anchor.get("source_locator") or ""),
            "publication_date": str(anchor.get("publication_date") or ""),
            "source_reporting_period_end": str(
                anchor.get("source_reporting_period_end") or ""
            ),
            "research_as_of": str(anchor.get("research_as_of") or ""),
            "source_content_digest": str(anchor.get("source_content_digest") or ""),
            "child_content_digest": str(anchor.get("child_content_digest") or ""),
            "parent_child_lineage": str(anchor.get("parent_child_lineage") or ""),
            "table_path": anchor.get("table_path"),
            "currency_unit_authority": anchor.get("currency_unit_authority"),
            "render_source": "qualified_candidate_preview_not_annotation",
            "index_lanes": ["object_bm25", "bge_m3_milvus"],
            "vector_text": vector_text,
            "vector_text_sha256": _plain_sha256(vector_text),
        }
        specs.append(_finalize_spec(body))
    return specs


def _load_private_case_objects(
    *,
    store: FileCanonicalObjectStore,
    case_result: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    private = dict(case_result.get("private_artifacts") or {})
    parent_ref = dict(private.get("parent") or {})
    metrics_ref = dict(private.get("admitted_metrics") or {})
    bundles_ref = dict(private.get("candidate_bundles") or {})
    parent = store.get_json(
        str(parent_ref.get("object_key") or ""),
        expected_digest=str(parent_ref.get("digest") or ""),
    )
    metrics = store.get_json(
        str(metrics_ref.get("object_key") or ""),
        expected_digest=str(metrics_ref.get("digest") or ""),
    )
    bundles = store.get_json(
        str(bundles_ref.get("object_key") or ""),
        expected_digest=str(bundles_ref.get("digest") or ""),
    )
    _require(
        isinstance(parent, dict) and isinstance(metrics, list) and isinstance(bundles, list),
        "candidate_bundle_index_private_object_shape_invalid",
    )
    return parent, [dict(item) for item in metrics], [dict(item) for item in bundles]


def _held_out_specs(
    *,
    case_result: Mapping[str, Any],
    store: FileCanonicalObjectStore,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    case_key = str(case_result.get("case_key") or "")
    source_identity = dict(case_result.get("source_identity") or {})
    parent, metrics, projections = _load_private_case_objects(
        store=store, case_result=case_result
    )
    metric_index = {str(item.get("object_id") or ""): item for item in metrics}
    source_digest = _plain_sha256(str(parent.get("text") or ""))
    specs: list[dict[str, Any]] = []
    quarantine: list[dict[str, Any]] = []
    for projection in projections:
        if projection.get("terminal_state") != "bundle_projected":
            continue
        bundle = dict(projection.get("bundle") or {})
        object_type = str(bundle.get("object_type") or "")
        if object_type == "claim":
            quarantine.append(
                {
                    "case_key": case_key,
                    "bundle_id": str(bundle.get("bundle_id") or ""),
                    "target_id": str(bundle.get("target_id") or ""),
                    "slot_id": str(bundle.get("slot_id") or ""),
                    "object_type": "claim",
                    "disposition": "narrative_review_required_not_indexed",
                    "reason_code": "automatic_narrative_claim_quality_unproven",
                    "candidate_state": "bundle_candidate_only_not_evidence",
                }
            )
            continue
        _require(object_type == "metric", "candidate_bundle_index_held_out_type_invalid")
        child = metric_index.get(str(bundle.get("target_id") or ""))
        _require(
            child is not None
            and canonical_digest(child) == str(bundle.get("child_content_digest") or "")
            and source_digest == str(bundle.get("source_content_digest") or ""),
            "candidate_bundle_index_held_out_content_binding_invalid",
        )
        table_path = dict(bundle.get("table_path") or {})
        unit_authority = dict(bundle.get("currency_unit_authority") or {})
        source_text = _normalise_text(
            " | ".join(
                (
                    str(child.get("metric_name") or child.get("row_label") or ""),
                    f"row={table_path.get('row_label') or ''}",
                    f"column={table_path.get('column_label') or ''}",
                    f"value={child.get('raw_value') or ''}",
                    f"period={child.get('period') or ''}",
                    f"unit={child.get('unit') or ''}",
                    f"table={table_path.get('table_header') or ''}",
                )
            ),
            limit=2200,
        )
        vector_text = (
            f"case={case_key} | slot={bundle.get('slot_id') or ''} | object=metric | "
            f"period_end={bundle.get('source_reporting_period_end') or ''}\n{source_text}"
        )
        vector_id = "cbidx_" + canonical_digest(
            {
                "case_key": case_key,
                "target_id": bundle.get("target_id"),
                "bundle_id": bundle.get("bundle_id"),
            }
        )[:32]
        body = {
            "vector_id": vector_id,
            "canonical_candidate_identity": f"{case_key}::{bundle.get('target_id') or ''}",
            "case_key": case_key,
            "ticker": case_key,
            "evidence_owner_ticker": str(
                bundle.get("evidence_owner_ticker") or ""
            ),
            "target_id": str(bundle.get("target_id") or ""),
            "source_record_id": str(bundle.get("source_record_id") or ""),
            "object_type": "metric",
            "quality_tier": "strict_structured_metric_candidate",
            "selection_basis": "strict_structured_metric_policy",
            "candidate_state": "bundle_candidate_only_not_evidence",
            "bundle_bindings": [
                {
                    "bundle_id": str(bundle.get("bundle_id") or ""),
                    "lane_id": str(bundle.get("lane_id") or ""),
                    "slot_id": str(bundle.get("slot_id") or ""),
                    "qualification_id": "",
                    "candidate_id": "",
                }
            ],
            "slot_ids": [str(bundle.get("slot_id") or "")],
            "facet_ids": [],
            "relationship_directions": [
                str(bundle.get("relationship_direction") or "")
            ],
            "source_locator": str(bundle.get("source_locator") or ""),
            "publication_date": str(bundle.get("publication_date") or ""),
            "source_reporting_period_end": str(
                bundle.get("source_reporting_period_end") or ""
            ),
            "research_as_of": str(bundle.get("research_as_of") or ""),
            "source_content_digest": str(bundle.get("source_content_digest") or ""),
            "child_content_digest": str(bundle.get("child_content_digest") or ""),
            "parent_child_lineage": str(bundle.get("parent_child_lineage") or ""),
            "table_path": table_path,
            "currency_unit_authority": unit_authority,
            "metric_period": str(child.get("period") or ""),
            "metric_period_role": str(child.get("period_role") or ""),
            "metric_unit": str(child.get("unit") or ""),
            "source_type": str(source_identity.get("form_type") or ""),
            "render_source": "table_row_column_metric_object",
            "index_lanes": ["object_bm25", "bge_m3_milvus"],
            "vector_text": vector_text,
            "vector_text_sha256": _plain_sha256(vector_text),
        }
        specs.append(_finalize_spec(body))
    return specs, quarantine


def validate_candidate_bundle_index_specs(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
) -> None:
    selection = dict(policy.get("selection_contract") or {})
    expected = int(selection.get("expected_primary_spec_count") or 0)
    expected_by_case = {
        str(key): int(value)
        for key, value in dict(selection.get("expected_primary_specs_by_case") or {}).items()
    }
    vector_ids = [str(item.get("vector_id") or "") for item in specs]
    identities = [str(item.get("canonical_candidate_identity") or "") for item in specs]
    _require(
        len(specs) == expected
        and len(set(vector_ids)) == expected
        and len(set(identities)) == expected
        and all(vector_ids)
        and all(identities),
        "candidate_bundle_index_identity_or_count_invalid",
    )
    actual_by_case = Counter(str(item.get("case_key") or "") for item in specs)
    _require(
        dict(actual_by_case) == expected_by_case,
        "candidate_bundle_index_case_count_invalid",
    )
    for item in specs:
        body = dict(item)
        supplied_digest = str(body.pop("spec_digest", ""))
        _require(
            supplied_digest == canonical_digest(body),
            "candidate_bundle_index_spec_digest_invalid",
        )
        case_key = str(item.get("case_key") or "")
        ticker = str(item.get("ticker") or "")
        selection_basis = str(item.get("selection_basis") or "")
        object_type = str(item.get("object_type") or "")
        bundle_bindings = list(item.get("bundle_bindings") or [])
        _require(
            case_key in EXPECTED_CASE_KEYS
            and ticker == case_key
            and str(item.get("canonical_candidate_identity") or "").startswith(
                f"{case_key}::"
            )
            and str(item.get("evidence_owner_ticker") or "")
            and item.get("candidate_state") == "bundle_candidate_only_not_evidence"
            and item.get("index_lanes") == ["object_bm25", "bge_m3_milvus"]
            and bundle_bindings
            and all(str(row.get("bundle_id") or "") for row in bundle_bindings),
            "candidate_bundle_index_case_or_bundle_binding_invalid",
        )
        if case_key in KNOWN_CASE_KEYS:
            _require(
                selection_basis == "reviewed_candidate_qualification"
                and item.get("quality_tier") == "reviewed_financial_candidate"
                and all(
                    str(row.get("qualification_id") or "")
                    and str(row.get("candidate_id") or "")
                    for row in bundle_bindings
                ),
                "candidate_bundle_index_known_selection_invalid",
            )
        else:
            _require(
                selection_basis == "strict_structured_metric_policy"
                and item.get("quality_tier") == "strict_structured_metric_candidate"
                and object_type == "metric",
                "candidate_bundle_index_automatic_narrative_admission_forbidden",
            )
        source_digest = str(item.get("source_content_digest") or "")
        child_digest = str(item.get("child_content_digest") or "")
        lineage = str(item.get("parent_child_lineage") or "")
        _require(
            len(source_digest) == 64
            and f"sha256:{source_digest}" in lineage
            and (not child_digest or f"sha256:{child_digest}" in lineage),
            "candidate_bundle_index_source_or_child_lineage_invalid",
        )
        try:
            publication = date.fromisoformat(str(item.get("publication_date") or ""))
            research_as_of = date.fromisoformat(str(item.get("research_as_of") or ""))
            period_end = date.fromisoformat(
                str(item.get("source_reporting_period_end") or "")
            )
        except ValueError as exc:
            raise CandidateBundleIndexManifestError(
                "candidate_bundle_index_temporal_binding_invalid"
            ) from exc
        _require(
            publication <= research_as_of and period_end <= research_as_of,
            "candidate_bundle_index_temporal_binding_invalid",
        )
        if object_type == "metric":
            table_path = dict(item.get("table_path") or {})
            authority = dict(item.get("currency_unit_authority") or {})
            metric_period = str(item.get("metric_period") or "")
            metric_period_role = str(item.get("metric_period_role") or "")
            metric_unit = str(item.get("metric_unit") or "")
            _require(
                all(
                    str(table_path.get(key) or "")
                    for key in (
                        "table_id",
                        "row_label",
                        "column_label",
                        "cell_key",
                        "context_digest",
                    )
                )
                and authority.get("status")
                in {"source_and_child_consistent", "non_monetary_dimension_preserved"}
                and str(authority.get("canonical_unit") or ""),
                "candidate_bundle_index_metric_authority_invalid",
            )
            _require(
                metric_period
                and (
                    metric_period in str(table_path.get("column_label") or "")
                    or metric_period
                    == str(item.get("source_reporting_period_end") or "")[:4]
                ),
                "candidate_bundle_index_metric_period_invalid",
            )
            _require(
                metric_period_role
                in {"instant", "qtd", "ytd", "annual", "ttm"},
                "candidate_bundle_index_metric_period_role_invalid",
            )
            _require(
                metric_unit
                and metric_unit == str(authority.get("canonical_unit") or ""),
                "candidate_bundle_index_metric_unit_invalid",
            )
        vector_text = str(item.get("vector_text") or "")
        _require(
            bool(vector_text)
            and len(vector_text) <= 2600
            and str(item.get("vector_text_sha256") or "")
            == _plain_sha256(vector_text),
            "candidate_bundle_index_vector_text_invalid",
        )


class _FakeIndexWriter:
    def __init__(self, *, partial: bool = False) -> None:
        self.partial = partial
        self.rows: dict[str, str] = {}

    def insert(self, rows: Sequence[Mapping[str, Any]]) -> int:
        acknowledged = max(0, len(rows) - 1) if self.partial else len(rows)
        for row in rows[:acknowledged]:
            self.rows[str(row["vector_id"])] = str(row["spec_digest"])
        return acknowledged


def execute_fake_sparse_dense_build(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
    sparse_partial: bool = False,
    dense_partial: bool = False,
) -> dict[str, Any]:
    validate_candidate_bundle_index_specs(specs, policy=policy)
    batch_size = int(policy["index_contract"]["fake_batch_size"])
    sparse = _FakeIndexWriter(partial=sparse_partial)
    dense = _FakeIndexWriter(partial=dense_partial)
    batches = 0
    for offset in range(0, len(specs), batch_size):
        batch = list(specs[offset : offset + batch_size])
        _require(
            sparse.insert(batch) == len(batch),
            "candidate_bundle_index_sparse_partial_insert",
        )
        _require(
            dense.insert(batch) == len(batch),
            "candidate_bundle_index_dense_partial_insert",
        )
        batches += 1
    _require(
        len(sparse.rows) == len(specs) and len(dense.rows) == len(specs),
        "candidate_bundle_index_fake_terminal_count_invalid",
    )
    return {
        "batch_count_each": batches,
        "sparse_inserted_specs": len(sparse.rows),
        "dense_inserted_specs": len(dense.rows),
        "fake_embedding_vectors": len(dense.rows),
        "fake_embedding_dimension": int(policy["index_contract"]["embedding_dimension"]),
        "terminal_count_each": len(specs),
    }


def _caught_code(action: Any) -> str:
    try:
        action()
    except CandidateBundleIndexManifestError as exc:
        return exc.code
    return "did_not_fail_closed"


def _redigest(spec: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(spec)
    body.pop("spec_digest", None)
    return _finalize_spec(body)


def _run_mutation_proof(
    specs: Sequence[Mapping[str, Any]],
    *,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    metric_index = next(
        index for index, item in enumerate(specs) if item.get("object_type") == "metric"
    )
    held_out_index = next(
        index for index, item in enumerate(specs) if item.get("case_key") in HELD_OUT_CASE_KEYS
    )

    def semantic_mutation(index: int, **changes: Any) -> list[dict[str, Any]]:
        mutated = [dict(item) for item in specs]
        changed = {**mutated[index], **changes}
        mutated[index] = _redigest(changed)
        return mutated

    source_drift = deepcopy(specs[0])
    source_drift["source_content_digest"] = "0" * 64
    source_drift = _redigest(source_drift)
    source_rows = [dict(item) for item in specs]
    source_rows[0] = source_drift

    child_target = next(
        index for index, item in enumerate(specs) if item.get("child_content_digest")
    )
    child_drift = deepcopy(specs[child_target])
    child_drift["child_content_digest"] = "1" * 64
    child_drift = _redigest(child_drift)
    child_rows = [dict(item) for item in specs]
    child_rows[child_target] = child_drift

    cross = deepcopy(specs[held_out_index])
    cross["case_key"] = "DELL"
    cross = _redigest(cross)
    cross_rows = [dict(item) for item in specs]
    cross_rows[held_out_index] = cross

    future = deepcopy(specs[0])
    future["publication_date"] = "2099-01-01"
    future = _redigest(future)
    future_rows = [dict(item) for item in specs]
    future_rows[0] = future

    narrative = deepcopy(specs[held_out_index])
    narrative["object_type"] = "claim"
    narrative["selection_basis"] = "automatic_narrative_claim"
    narrative["table_path"] = None
    narrative["currency_unit_authority"] = None
    narrative = _redigest(narrative)
    narrative_rows = [dict(item) for item in specs]
    narrative_rows[held_out_index] = narrative

    missing_bundle = deepcopy(specs[0])
    missing_bundle["bundle_bindings"] = []
    missing_bundle = _redigest(missing_bundle)
    missing_bundle_rows = [dict(item) for item in specs]
    missing_bundle_rows[0] = missing_bundle

    text_drift = [dict(item) for item in specs]
    text_drift[0] = {**text_drift[0], "vector_text": text_drift[0]["vector_text"] + " drift"}

    scenarios = {
        "duplicate_candidate_identity": lambda: validate_candidate_bundle_index_specs(
            [*specs, dict(specs[0])], policy=policy
        ),
        "missing_bundle_binding": lambda: validate_candidate_bundle_index_specs(
            missing_bundle_rows, policy=policy
        ),
        "source_digest_drift": lambda: validate_candidate_bundle_index_specs(
            source_rows, policy=policy
        ),
        "child_digest_drift": lambda: validate_candidate_bundle_index_specs(
            child_rows, policy=policy
        ),
        "metric_table_path_missing": lambda: validate_candidate_bundle_index_specs(
            semantic_mutation(metric_index, table_path=None), policy=policy
        ),
        "metric_currency_authority_missing": lambda: validate_candidate_bundle_index_specs(
            semantic_mutation(metric_index, currency_unit_authority=None), policy=policy
        ),
        "metric_period_missing": lambda: validate_candidate_bundle_index_specs(
            semantic_mutation(metric_index, metric_period=""), policy=policy
        ),
        "metric_period_role_missing": lambda: validate_candidate_bundle_index_specs(
            semantic_mutation(metric_index, metric_period_role=""), policy=policy
        ),
        "metric_unit_mismatch": lambda: validate_candidate_bundle_index_specs(
            semantic_mutation(metric_index, metric_unit="wrong_unit"), policy=policy
        ),
        "cross_case_identity": lambda: validate_candidate_bundle_index_specs(
            cross_rows, policy=policy
        ),
        "future_publication": lambda: validate_candidate_bundle_index_specs(
            future_rows, policy=policy
        ),
        "automatic_narrative_infiltration": lambda: validate_candidate_bundle_index_specs(
            narrative_rows, policy=policy
        ),
        "vector_text_drift": lambda: validate_candidate_bundle_index_specs(
            text_drift, policy=policy
        ),
        "sparse_partial_insert": lambda: execute_fake_sparse_dense_build(
            specs, policy=policy, sparse_partial=True
        ),
        "dense_partial_insert": lambda: execute_fake_sparse_dense_build(
            specs, policy=policy, dense_partial=True
        ),
    }
    rows = [
        {
            "scenario": name,
            "observed_code": _caught_code(action),
        }
        for name, action in scenarios.items()
    ]
    return {
        "scenario_count": len(rows),
        "rows": rows,
        "all_failed_closed": all(
            row["observed_code"] != "did_not_fail_closed" for row in rows
        ),
    }


def compile_candidate_bundle_index_manifest(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    source_runtime_root: str | Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    root = Path(repo_root).resolve()
    artifacts = _artifact_map(policy)
    bundle_result = _read_json(_resolve(root, artifacts["bundle_v2_result"]["path"]))
    specs: list[dict[str, Any]] = []
    for case_key, artifact_id in zip(
        KNOWN_CASE_KEYS,
        ("dell_result", "mu_result", "nvda_result"),
        strict=True,
    ):
        result = _read_json(_resolve(root, artifacts[artifact_id]["path"]))
        _require(
            result.get("case_key") == case_key,
            "candidate_bundle_index_known_case_result_identity_invalid",
        )
        specs.extend(
            _known_case_specs(
                case_key=case_key,
                result=result,
                bundle_case_result=_case_result(bundle_result, case_key),
            )
        )

    held_out_result = _read_json(
        _resolve(root, artifacts["held_out_reparse_result"]["path"])
    )
    source_root = (
        Path(source_runtime_root).resolve()
        if source_runtime_root is not None
        else _resolve(
            root,
            str(policy["private_object_inputs"]["held_out_reparse_runtime_root_ref"]),
        ).resolve()
    )
    store = FileCanonicalObjectStore(source_root / "objects")
    quarantine: list[dict[str, Any]] = []
    for case_key in HELD_OUT_CASE_KEYS:
        case_specs, case_quarantine = _held_out_specs(
            case_result=_case_result(held_out_result, case_key),
            store=store,
        )
        specs.extend(case_specs)
        quarantine.extend(case_quarantine)
    specs.sort(key=lambda item: (str(item["case_key"]), str(item["vector_id"])))
    quarantine.sort(
        key=lambda item: (
            str(item["case_key"]),
            str(item["bundle_id"]),
        )
    )
    validate_candidate_bundle_index_specs(specs, policy=policy)
    _require(
        len(quarantine)
        == int(
            policy["selection_contract"]["expected_narrative_review_queue_count"]
        )
        and all(
            item["disposition"] == "narrative_review_required_not_indexed"
            for item in quarantine
        ),
        "candidate_bundle_index_narrative_quarantine_invalid",
    )
    summary = {
        "primary_spec_count": len(specs),
        "primary_specs_by_case": dict(
            Counter(str(item["case_key"]) for item in specs)
        ),
        "primary_specs_by_quality_tier": dict(
            Counter(str(item["quality_tier"]) for item in specs)
        ),
        "primary_specs_by_object_type": dict(
            Counter(str(item["object_type"]) for item in specs)
        ),
        "narrative_review_queue_count": len(quarantine),
        "narrative_review_queue_by_case": dict(
            Counter(str(item["case_key"]) for item in quarantine)
        ),
        "qrels_or_gold_selection_inputs": 0,
        "manifest_spec_digest": canonical_digest(specs),
        "quarantine_digest": canonical_digest(quarantine),
    }
    return specs, quarantine, summary


def materialize_candidate_bundle_index_zero_call_proof(
    *,
    policy: Mapping[str, Any],
    repo_root: str | Path,
    output_runtime_root: str | Path,
    source_runtime_root: str | Path | None = None,
) -> dict[str, Any]:
    specs, quarantine, summary = compile_candidate_bundle_index_manifest(
        policy=policy,
        repo_root=repo_root,
        source_runtime_root=source_runtime_root,
    )
    private_body = {
        "schema_version": PRIVATE_MANIFEST_SCHEMA,
        "contract_ref": policy["contract_ref"],
        "candidate_state": "candidate_only_not_evidence",
        "specs": specs,
        "narrative_review_queue": quarantine,
        "summary": summary,
    }
    private_manifest = {
        **private_body,
        "manifest_digest": canonical_digest(private_body),
    }
    output_store = FileCanonicalObjectStore(Path(output_runtime_root).resolve() / "objects")
    manifest_ref = output_store.put_json(
        private_manifest,
        namespace="fin-0.1.3/s1-candidate-bundle-sparse-dense-manifest/v1",
        artifact_type="candidate_bundle_sparse_dense_private_manifest_not_evidence",
    )
    fake_build = execute_fake_sparse_dense_build(specs, policy=policy)
    mutation_proof = _run_mutation_proof(specs, policy=policy)
    _require(
        mutation_proof["all_failed_closed"] is True,
        "candidate_bundle_index_mutation_proof_failed",
    )
    public_examples = [
        {
            "case_key": item["case_key"],
            "vector_id": item["vector_id"],
            "target_id": item["target_id"],
            "object_type": item["object_type"],
            "quality_tier": item["quality_tier"],
            "selection_basis": item["selection_basis"],
            "slot_ids": item["slot_ids"],
            "bundle_ids": [
                row["bundle_id"] for row in item["bundle_bindings"]
            ],
            "source_locator": item["source_locator"],
            "source_reporting_period_end": item["source_reporting_period_end"],
            "vector_text_sha256": item["vector_text_sha256"],
            "candidate_state": item["candidate_state"],
        }
        for item in [
            next(spec for spec in specs if spec["case_key"] == case_key)
            for case_key in EXPECTED_CASE_KEYS
        ]
    ]
    body = {
        "schema_version": RESULT_SCHEMA,
        "contract_ref": policy["contract_ref"],
        "run_scope": RUN_SCOPE,
        "recorded_at": policy["recorded_at"],
        "attempt_id": policy["attempt_id"],
        "status": "terminal_succeeded_zero_call_candidate_bundle_index_manifest",
        "selection_summary": summary,
        "private_manifest": {
            **manifest_ref,
            "manifest_digest": private_manifest["manifest_digest"],
        },
        "public_examples": public_examples,
        "fake_build": fake_build,
        "mutation_proof": mutation_proof,
        "observed_calls": {
            "network": 0,
            "provider": 0,
            "model": 0,
            "document_fetch": 0,
            "real_embedding": 0,
            "milvus_read": 0,
            "milvus_write": 0,
            "rerank": 0,
            "evidence_promotion": 0,
        },
        "execution_gate": {
            "candidate_bundle_only_manifest": True,
            "sparse_fake_build": True,
            "dense_fake_build": True,
            "clean_independent_reproof_required": True,
            "ubuntu_real_build_authorized": False,
            "ranking_authorized": False,
        },
        "stage_acceptance": {
            "six_case_manifest_engineering": True,
            "automatic_narrative_claims_excluded": True,
            "held_out_narrative_quality": False,
            "physical_sparse_index": False,
            "physical_dense_index": False,
            "retrieval_quality": False,
            "evidence_pack": False,
            "external_residual_supplement": False,
            "deepseek_research": False,
            "release": False,
        },
        "decision_zh": (
            "六案主索引清单已重定基为 93 个选定 CandidateBundle：DELL/MU/NVDA 只取人工资格化目标，"
            "ORCL/ASML/ANET 只取带完整表格、期间和币种单元血缘的结构化 metric。"
            "19 条自动叙事 claim 进入复核队列而非主索引。当前只完成零调用 fake sparse/dense，"
            "真实 Ubuntu BGE/Milvus 构建仍需 clean independent proof 和独立 authority。"
        ),
        "known_boundary": (
            "This result proves a qrels-free CandidateBundle-only manifest and fake sparse/dense "
            "terminalization. It does not create a physical index, prove ranking, promote Evidence, "
            "close external coverage, call DeepSeek, establish held-out narrative quality or accept release."
        ),
    }
    return {**body, "proof_digest": canonical_digest(body)}


def validate_candidate_bundle_index_zero_call_proof(
    payload: Mapping[str, Any],
) -> None:
    body = dict(payload)
    supplied_digest = str(body.pop("proof_digest", ""))
    summary = dict(body.get("selection_summary") or {})
    calls = dict(body.get("observed_calls") or {})
    gate = dict(body.get("execution_gate") or {})
    _require(
        supplied_digest == canonical_digest(body)
        and body.get("schema_version") == RESULT_SCHEMA
        and body.get("status")
        == "terminal_succeeded_zero_call_candidate_bundle_index_manifest"
        and int(summary.get("primary_spec_count") or 0) == 93
        and int(summary.get("narrative_review_queue_count") or 0) == 19
        and int(summary.get("qrels_or_gold_selection_inputs", -1)) == 0
        and all(int(value) == 0 for value in calls.values())
        and gate.get("candidate_bundle_only_manifest") is True
        and gate.get("sparse_fake_build") is True
        and gate.get("dense_fake_build") is True
        and gate.get("ubuntu_real_build_authorized") is False
        and body.get("mutation_proof", {}).get("all_failed_closed") is True,
        "candidate_bundle_index_zero_call_proof_invalid",
    )


__all__ = [
    "CandidateBundleIndexManifestError",
    "POLICY_SCHEMA",
    "PRIVATE_MANIFEST_SCHEMA",
    "RESULT_SCHEMA",
    "RUN_SCOPE",
    "compile_candidate_bundle_index_manifest",
    "execute_fake_sparse_dense_build",
    "load_candidate_bundle_index_policy",
    "materialize_candidate_bundle_index_zero_call_proof",
    "validate_candidate_bundle_index_specs",
    "validate_candidate_bundle_index_zero_call_proof",
]
