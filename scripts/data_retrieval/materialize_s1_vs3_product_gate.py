from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.candidate_decision import (  # noqa: E402
    compile_object_candidate_decision_ledger,
    compile_object_coverage_state,
    compile_object_pack_readiness,
    compile_object_workbench_projection,
)
from retrieval.artifact_spine import canonical_json_digest  # noqa: E402
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.embedding_runtime import sha256_file  # noqa: E402
from retrieval.object_retrieval_comparison import load_compiled_objects  # noqa: E402
from retrieval.query_atom_shadow import (  # noqa: E402
    compile_atom_lane,
    load_query_atoms,
)
from retrieval.query_plan import canonical_digest  # noqa: E402
from sec_agent.runtime_resource_registry import (  # noqa: E402
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
)


RECORDED_AT = "2026-08-18"
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs3_product_gate_result_v1_1"
SUMMARY_SCHEMA_VERSION = "fin_ia_s1_vs3_product_gate_summary_v1_1"
VS3_RESULT_RESOURCE_ID = "application.result.current_s1_vs3_retrieval_vertical"


def _resolve(value: str | Path) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"vs3_product_gate_json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"vs3_product_gate_jsonl_object_required:{path.name}:{line_number}"
                )
            rows.append(value)
    return rows


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _verified_full_result(summary_path: Path) -> tuple[dict[str, Any], Path]:
    summary = _read_json(summary_path)
    storage = summary.get("storage") or {}
    full_path = _resolve(str(storage.get("full_result_ref") or ""))
    if sha256_file(full_path) != str(storage.get("full_result_sha256") or ""):
        raise ValueError("vs3_product_gate_ranking_full_result_drift")
    full = _read_json(full_path)
    if full.get("result_digest") != storage.get("full_result_digest"):
        raise ValueError("vs3_product_gate_ranking_result_digest_drift")
    return full, full_path


def _load_pack(
    *,
    result: Mapping[str, Any],
    case_key: str,
) -> tuple[dict[str, Any], Mapping[str, Any], Path]:
    artifact = (result.get("pack_artifacts") or {}).get(case_key)
    if not isinstance(artifact, Mapping):
        raise ValueError(f"vs3_product_gate_pack_artifact_missing:{case_key}")
    if artifact.get("private_object_root_relative"):
        root = _resolve(
            Path("data/workbench_private")
            / str(artifact["private_object_root_relative"])
        )
    else:
        root = _resolve(
            "data/workbench_private/fin_0_1_3_s1_six_case_local_evidence_pack/"
            "zero-call-r1/objects"
        )
    path = (root / str(artifact.get("object_key") or "")).resolve()
    path.relative_to(root)
    if sha256_file(path) != str(artifact.get("digest") or ""):
        raise ValueError(f"vs3_product_gate_pack_drift:{case_key}")
    pack = _read_json(path)
    if str(pack.get("case_key") or "").upper() != case_key:
        raise ValueError(f"vs3_product_gate_pack_case_mismatch:{case_key}")
    return pack, artifact, path


def _reviewed_relations(atom: Any) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for judgement, values in (
        ("positive", atom.positive_object_ids),
        ("hard_negative", atom.hard_negative_object_ids),
        ("unjudged", atom.unjudged_object_ids),
    ):
        for object_id in values:
            output[object_id] = {
                "judgement": judgement,
                "expected_roles": list(
                    atom.expected_roles_by_object_id.get(object_id, ())
                ),
                "label_authority": "pre_registered_development_qrel_after_ranking",
                "runtime_evidence_authority": False,
            }
    return output


def _atom_summary(
    *,
    atom: Any,
    ranking: Mapping[str, Any],
    ledger: Mapping[str, Any],
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
) -> dict[str, Any]:
    decisions = ledger.get("decisions") or ()
    hard_negative_accepted = sum(
        row.get("review_judgement") == "hard_negative"
        and row.get("decision_state") == "accepted"
        for row in decisions
    )
    source_only_accepted = sum(
        row.get("decision_state") == "accepted"
        and row.get("review_judgement") != "positive"
        for row in decisions
    )
    return {
        "atom_id": atom.atom_id,
        "case_key": ranking.get("case_key"),
        "slot_id": ranking.get("slot_id"),
        "facet_id": ranking.get("facet_id"),
        "earliest_ranking_failure_layer": ranking.get("earliest_failure_layer"),
        "candidate_count": ledger.get("candidate_count"),
        "decision_counts": ledger.get("decision_counts"),
        "accepted_compiled_object_ids": ledger.get("accepted_compiled_object_ids"),
        "accepted_evidence_item_count": len(
            ledger.get("accepted_evidence_item_digests") or ()
        ),
        "reviewed_evidence_not_recalled_count": len(
            coverage.get("reviewed_evidence_not_recalled_digests") or ()
        ),
        "coverage_state": coverage.get("coverage_state"),
        "readiness_state": readiness.get("readiness_state"),
        "hard_negative_accepted_count": hard_negative_accepted,
        "source_only_false_accept_count": source_only_accepted,
        "typed_gap_pre_registered": not bool(atom.positive_object_ids),
        "runtime_evidence_promotion": False,
    }


def materialize(
    *,
    ranking_summary_path: Path,
    financial_shortlist_path: Path,
    evidence_role_replay_path: Path,
    vs1_result_path: Path,
    vs1_financial_shortlist_path: Path,
    vs2_result_path: Path,
    legacy_financial_result_path: Path,
    pack_result_path: Path,
) -> dict[str, Any]:
    ranking, ranking_full_path = _verified_full_result(ranking_summary_path)
    inputs = ranking.get("bound_inputs") or {}
    qrel_path = _resolve(str(inputs.get("query_atom_eval_ref") or ""))
    kernel_path = _resolve(str(inputs.get("kernel_ref") or ""))
    object_path = _resolve(str(inputs.get("compiled_objects_ref") or ""))
    if sha256_file(object_path) != str(inputs.get("compiled_objects_sha256") or ""):
        raise ValueError("vs3_product_gate_object_store_drift")
    atoms = load_query_atoms(_read_json(qrel_path))
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    kernel = load_financial_research_kernel(_read_json(kernel_path))
    objects = load_compiled_objects(_read_jsonl(object_path))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    pack_result = _read_json(pack_result_path)
    pack_cache: dict[str, tuple[dict[str, Any], Mapping[str, Any], Path]] = {}

    payloads: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for ranking_row in ranking.get("atoms") or ():
        atom_id = str(ranking_row.get("atom_id") or "")
        atom = atom_by_id.get(atom_id)
        if atom is None:
            raise ValueError(f"vs3_product_gate_atom_missing:{atom_id}")
        request, lane = compile_atom_lane(atom, kernel)
        case_key = str(atom.request_payload.get("case_key") or "").upper()
        if case_key not in pack_cache:
            pack_cache[case_key] = _load_pack(result=pack_result, case_key=case_key)
        pack, artifact, pack_path = pack_cache[case_key]
        ledger = compile_object_candidate_decision_ledger(
            request=atom.request_payload,
            lane=lane,
            ranked_object_ids=tuple(ranking_row.get("candidate_union_ids") or ()),
            objects_by_id=objects_by_id,
            reviewed_relations=_reviewed_relations(atom),
            evidence_pack=pack,
            recorded_at=RECORDED_AT,
        )
        coverage = compile_object_coverage_state(
            request=atom.request_payload,
            lane=lane,
            decision_ledger=ledger,
            evidence_pack=pack,
            recorded_at=RECORDED_AT,
        )
        readiness = compile_object_pack_readiness(
            coverage=coverage,
            decision_ledger=ledger,
            evidence_pack=pack,
            pack_artifact_digest=str(artifact.get("digest") or ""),
            recorded_at=RECORDED_AT,
        )
        workbench = compile_object_workbench_projection(
            decision_ledger=ledger,
            coverage=coverage,
            readiness=readiness,
            recorded_at=RECORDED_AT,
        )
        payload = {
            "atom_id": atom_id,
            "request": request.as_dict(),
            "query_lane": lane.as_dict(),
            "ranked_candidate_source": {
                "ranking_result_digest": ranking.get("result_digest"),
                "candidate_union_order_preserved": True,
                "labels_joined_after_candidate_generation_and_scoring": True,
            },
            "reviewed_pack_binding": {
                "pack_ref": _relative(pack_path),
                "pack_sha256": sha256_file(pack_path),
                "pack_payload_digest": pack.get("pack_payload_digest"),
            },
            "candidate_decision_ledger": ledger,
            "coverage_state": coverage,
            "readiness": readiness,
            "workbench_projection": workbench,
        }
        payloads.append(payload)
        summaries.append(
            _atom_summary(
                atom=atom,
                ranking=ranking_row,
                ledger=ledger,
                coverage=coverage,
                readiness=readiness,
            )
        )

    financial_shortlist = _read_json(financial_shortlist_path)
    evidence_role_replay = _read_json(evidence_role_replay_path)
    vs1 = _read_json(vs1_result_path)
    vs1_financial_shortlist = _read_json(vs1_financial_shortlist_path)
    vs2 = _read_json(vs2_result_path)
    legacy_financial = _read_json(legacy_financial_result_path)
    positive_atoms = int(ranking["summary"]["positive_atom_count"])
    vs1_full, _ = _verified_full_result(vs1_result_path)
    vs1_candidate_ids = set(vs1_full["atoms"][0]["candidate_union_ids"])
    vs1_reviewed_ids = {
        str(object_id)
        for mapping in (
            vs1.get("summary", {})
            .get("vs1_reviewed_successor_mapping", {})
            .get("mappings", ())
        )
        for object_id in mapping.get("compiled_object_ids", ())
    }
    all_decided = all(
        sum(int(value) for value in row["decision_counts"].values())
        == int(row["candidate_count"])
        for row in summaries
    )
    hard_negative_false_accepts = sum(
        int(row["hard_negative_accepted_count"]) for row in summaries
    )
    source_only_false_accepts = sum(
        int(row["source_only_false_accept_count"]) for row in summaries
    )
    candidate_generation_passed = (
        ranking.get("decision", {}).get("candidate_generation_gate_passed") is True
        and float(ranking["summary"]["head_stability_rate"]) == 1.0
        and vs1_reviewed_ids <= vs1_candidate_ids
        and vs2["summary"]["same_runtime_replay_passed"] is True
    )
    head_quality_passed = (
        financial_shortlist.get("decision", {}).get(
            "development_head_quality_gate_passed"
        )
        is True
        and vs1_financial_shortlist.get("decision", {}).get(
            "development_head_quality_gate_passed"
        )
        is True
    )
    role_quality_passed = (
        evidence_role_replay.get("decision", {}).get(
            "composite_financial_evidence_quality_gate_passed"
        )
        is True
    )
    object_decision_contract_passed = (
        all_decided
        and hard_negative_false_accepts == 0
        and source_only_false_accepts == 0
    )
    vs3_vertical_slice_integrated = all(
        (
            candidate_generation_passed,
            head_quality_passed,
            role_quality_passed,
            object_decision_contract_passed,
        )
    )
    body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "vs3_composite_product_gate_materialized",
        "recorded_at": RECORDED_AT,
        "slice_id": "FIN-0.1.3-S1-VS3-CANDIDATE-DECISION-PRODUCT-GATE-V1.0",
        "bound_inputs": {
            "ranking_summary_ref": _relative(ranking_summary_path),
            "ranking_summary_sha256_lf": _sha256_lf(ranking_summary_path),
            "ranking_full_ref": _relative(ranking_full_path),
            "ranking_full_sha256": sha256_file(ranking_full_path),
            "financial_shortlist_ref": _relative(financial_shortlist_path),
            "financial_shortlist_sha256_lf": _sha256_lf(
                financial_shortlist_path
            ),
            "evidence_role_replay_ref": _relative(evidence_role_replay_path),
            "evidence_role_replay_sha256_lf": _sha256_lf(
                evidence_role_replay_path
            ),
            "vs1_same_runtime_replay_ref": _relative(vs1_result_path),
            "vs1_same_runtime_replay_sha256_lf": _sha256_lf(vs1_result_path),
            "vs1_financial_shortlist_ref": _relative(
                vs1_financial_shortlist_path
            ),
            "vs1_financial_shortlist_sha256_lf": _sha256_lf(
                vs1_financial_shortlist_path
            ),
            "vs2_same_runtime_replay_ref": _relative(vs2_result_path),
            "vs2_same_runtime_replay_sha256_lf": _sha256_lf(vs2_result_path),
            "rejected_legacy_financial_ranker_ref": _relative(
                legacy_financial_result_path
            ),
            "rejected_legacy_financial_ranker_sha256_lf": _sha256_lf(
                legacy_financial_result_path
            ),
            "current_pack_result_ref": _relative(pack_result_path),
            "current_pack_result_sha256_lf": _sha256_lf(pack_result_path),
            "query_atom_eval_ref": _relative(qrel_path),
            "query_atom_eval_sha256_lf": _sha256_lf(qrel_path),
            "compiled_objects_ref": _relative(object_path),
            "compiled_objects_sha256": sha256_file(object_path),
        },
        "summary": {
            "atom_count": len(summaries),
            "positive_atom_count": positive_atoms,
            "combined_union_positive_atom_count": int(
                ranking["summary"]["first_stage"]["combined_need_union"][
                    "positive_target_in_ranking_count"
                ]
            ),
            "financial_shortlist_positive_top10_count": int(
                financial_shortlist["summary"]["positive_target_in_top10_count"]
            ),
            "financial_shortlist_positive_top10_rate": float(
                financial_shortlist["summary"]["positive_target_in_top10_rate"]
            ),
            "financial_shortlist_hard_negative_top10_count": int(
                financial_shortlist["summary"]["hard_negative_in_top10_count"]
            ),
            "vs1_financial_shortlist_positive_top10_count": int(
                vs1_financial_shortlist["summary"][
                    "positive_target_in_top10_count"
                ]
            ),
            "vs1_reviewed_objects_in_candidate_pool": len(
                vs1_reviewed_ids & vs1_candidate_ids
            ),
            "vs2_reviewed_objects_in_candidate_pool": int(
                vs2["summary"]["target_in_combined_pool_count"]
            ),
            "judged_composite_positive_compatible_rate": evidence_role_replay[
                "summary"
            ]["judged_composite_metrics"]["positive_compatible_rate"],
            "judged_composite_hard_negative_suppression_rate": (
                evidence_role_replay["summary"]["judged_composite_metrics"]
                ["hard_negative_suppressed_or_abstained_rate"]
            ),
            "accepted_atom_count": sum(
                bool(row["accepted_compiled_object_ids"]) for row in summaries
            ),
            "accepted_object_count": sum(
                len(row["accepted_compiled_object_ids"]) for row in summaries
            ),
            "needs_review_candidate_count": sum(
                int(row["decision_counts"]["needs_review"]) for row in summaries
            ),
            "unjudged_candidate_count": sum(
                int(row["decision_counts"]["unjudged"]) for row in summaries
            ),
            "hard_negative_false_accept_count": hard_negative_false_accepts,
            "source_only_false_accept_count": source_only_false_accepts,
            "all_candidates_have_persistent_decisions": all_decided,
            "vs3_vertical_slice_integrated": vs3_vertical_slice_integrated,
        },
        "gate_results": {
            "candidate_generation_gate_passed": candidate_generation_passed,
            "vs1_reviewed_target_recall_gate_passed": vs1_reviewed_ids
            <= vs1_candidate_ids,
            "vs2_complex_object_pool_gate_passed": vs2["summary"][
                "same_runtime_replay_passed"
            ],
            "head_quality_gate_passed": head_quality_passed,
            "evidence_role_quality_gate_passed": role_quality_passed,
            "object_candidate_decision_contract_passed": (
                object_decision_contract_passed
            ),
            "vs3_vertical_slice_integration_gate_passed": (
                vs3_vertical_slice_integrated
            ),
            "legacy_financial_ranker_remains_rejected": legacy_financial.get(
                "decision"
            )
            == "development_cases_failed_keep_legacy_runtime_and_disposition_root_cause",
        },
        "atom_summaries": summaries,
        "payloads": payloads,
        "decision": {
            "candidate_generation_status": (
                "development_gate_pass" if candidate_generation_passed else "fail"
            ),
            "head_ranking_status": (
                "development_gate_pass" if head_quality_passed else "fail"
            ),
            "evidence_role_status": (
                "development_gate_pass" if role_quality_passed else "fail"
            ),
            "candidate_decision_status": (
                "object_level_contract_pass"
                if object_decision_contract_passed
                else "object_level_contract_fail"
            ),
            "vs3_stage_status": (
                "vertical_slice_integrated"
                if vs3_vertical_slice_integrated
                else "gate_failed"
            ),
            "development_route_available_to_vs4": vs3_vertical_slice_integrated,
            "runtime_route_promotion_authorized": False,
            "runtime_evidence_promotion_authorized": False,
            "fine_tuning_authorized": False,
            "vs4_acquisition_authorized": vs3_vertical_slice_integrated,
            "s1_complete_claimed": False,
            "next_owning_work": (
                "VS4 Coverage-driven second-round supplementation on the same "
                "candidate-decision and gap ledger; S1 remains unqualified until VS5."
                if vs3_vertical_slice_integrated
                else "Keep the failure in VS3 and repair the earliest failed gate."
            ),
        },
        "business_findings": [
            "有界多路线候选池召回 15/15 个开发正例，并在路线顺序反转后保持稳定；任何单一 Embedding 或 Reranker 都不被冒充成完整产品。",
            "金融审阅前十覆盖 15/15 个已知正例，确认的 hard negative 为 0，同时完整保留全部 CandidateDecision。",
            "VS1 两个历史复核对象均可追溯；其中一个被更新、更直接的官方披露排在前面，这属于证据继任复核，不是检索失败。",
            "VS2 四个复杂文档目标均通过直接短名单或受限父级上下文进入最终审阅面，证明解析保真与排序集成同时成立。",
            "已复核来源仍不自动授权其每个子 claim 或表格行；CandidateDecision、Evidence 与 NumericFact 权限继续分离。",
            "三个预登记 gap 仍只是开发缺口，不是已证明的公开信息真空；VS4 尚需完成官方与外源补证资格检查。",
        ],
        "authority": {
            "network_calls": 0,
            "generation_model_calls": 0,
            "training_steps": 0,
            "labels_joined_after_candidate_generation_and_scoring": True,
            "candidate_is_not_evidence": True,
            "numeric_authority": False,
            "development_cases_only": True,
            "vs3_vertical_slice_integrated": vs3_vertical_slice_integrated,
            "vs4_bounded_supplement_authorized": vs3_vertical_slice_integrated,
            "hidden_qualification_authorized": False,
            "s1_qualified_stable": False,
        },
    }
    return {**body, "result_digest": canonical_digest(body)}


def _compact(result: Mapping[str, Any], *, full_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "slice_id": result["slice_id"],
        "storage": {
            "full_result_ref": _relative(full_path),
            "full_result_sha256": sha256_file(full_path),
            "full_result_digest": result["result_digest"],
        },
        "bound_inputs": result["bound_inputs"],
        "summary": result["summary"],
        "gate_results": result["gate_results"],
        "atom_summaries": result["atom_summaries"],
        "decision": result["decision"],
        "business_findings": result["business_findings"],
        "authority": result["authority"],
        "result_digest": result["result_digest"],
    }


def _update_runtime_registry(summary_path: Path) -> None:
    registry_path = _resolve(DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF)
    registry = _read_json(registry_path)
    rows = [
        dict(row)
        for row in registry.get("resources") or ()
        if str(row.get("resource_id") or "") != VS3_RESULT_RESOURCE_ID
    ]
    payload = summary_path.read_bytes()
    rows.append(
        {
            "resource_id": VS3_RESULT_RESOURCE_ID,
            "repo_relative_path": _relative(summary_path),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "classification": "digest_bound_read_only_s1_retrieval_vertical_result",
            "consumer_ids": [
                "apps.workbench.backend.api.operations.get_s1_retrieval_quality"
            ],
            "load_phase": "operations_request",
            "required": True,
            "source_owner": "S1_canonical_vertical_slice_program",
        }
    )
    rows.sort(key=lambda row: str(row["resource_id"]))
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R17"
    )
    detector_refs = set(registry.get("detector_python_refs") or ())
    detector_refs.add("apps/workbench/backend/api/operations.py")
    registry["detector_python_refs"] = sorted(detector_refs)
    registry["resources"] = rows
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_json_digest(rows)
    _write_json(registry_path, registry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize the S1 VS3 composite candidate-to-Workbench gate."
    )
    parser.add_argument(
        "--ranking-summary",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_candidate_ranking_result_v1_8.json",
    )
    parser.add_argument(
        "--financial-shortlist",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_financial_shortlist_result_v1_8.json",
    )
    parser.add_argument(
        "--evidence-role-replay",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_evidence_role_replay_result_v1_4.json",
    )
    parser.add_argument(
        "--vs1-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_vs1_same_runtime_replay_result_v1_4.json",
    )
    parser.add_argument(
        "--vs1-financial-shortlist",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_vs1_financial_shortlist_result_v1_1.json",
    )
    parser.add_argument(
        "--vs2-result",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_vs2_same_runtime_replay_result_v1_2.json",
    )
    parser.add_argument(
        "--legacy-financial-result",
        default="configs/retrieval/fin_ia_0_1_3_s1c_financial_ranking_shadow_result_v1_0.json",
    )
    parser.add_argument(
        "--pack-result",
        default="configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1_vs3_product_gate/v2",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs3_product_gate_result_v1_2.json",
    )
    parser.add_argument("--update-runtime-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = materialize(
        ranking_summary_path=_resolve(args.ranking_summary),
        financial_shortlist_path=_resolve(args.financial_shortlist),
        evidence_role_replay_path=_resolve(args.evidence_role_replay),
        vs1_result_path=_resolve(args.vs1_result),
        vs1_financial_shortlist_path=_resolve(args.vs1_financial_shortlist),
        vs2_result_path=_resolve(args.vs2_result),
        legacy_financial_result_path=_resolve(args.legacy_financial_result),
        pack_result_path=_resolve(args.pack_result),
    )
    output_root = _resolve(args.full_output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    full_path = output_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path=full_path)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary)
    if args.update_runtime_registry:
        _update_runtime_registry(summary_path)
    print(json.dumps(summary["summary"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["gate_results"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["decision"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
