from __future__ import annotations

import argparse
from copy import deepcopy
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

from retrieval.artifact_spine import canonical_json_digest  # noqa: E402
from retrieval.candidate_decision import (  # noqa: E402
    compile_object_candidate_decision_ledger,
)
from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.embedding_runtime import sha256_file  # noqa: E402
from retrieval.object_retrieval_comparison import load_compiled_objects  # noqa: E402
from retrieval.query_atom_shadow import compile_atom_lane, load_query_atoms  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.supplement_vertical import (  # noqa: E402
    build_capture_bound_pack_successor,
    compile_supplement_workbench_projection,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest as reviewed_pack_digest,
    validate_reviewed_evidence_pack,
)
from sec_agent.research.reviewed_evidence_anchor import (  # noqa: E402
    compile_reviewed_evidence_anchor_catalog,
    load_reviewed_evidence_anchor_catalog,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
)


RECORDED_AT = "2026-08-18"
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs4_dell_supplement_vertical_result_v1_0"
SUMMARY_SCHEMA_VERSION = "fin_ia_s1_vs4_dell_supplement_vertical_summary_v1_0"
VS4_RESULT_RESOURCE_ID = "application.result.current_s1_vs4_supplement_vertical"
CURRENT_PACK_RESULT_RESOURCE_ID = "application.result.current_research_local_evidence_packs"
CURRENT_ANCHOR_RESOURCE_ID = "application.result.current_reviewed_claim_anchors"
CURRENT_WORKSPACE_RESOURCE_ID = "application.config.current_research_workspace_catalog"
PREDECESSOR_CURRENT_PACK_REF = Path(
    "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_1.json"
)
PREDECESSOR_ANCHOR_CATALOG_REF = Path(
    "configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_0.json"
)
PREDECESSOR_WORKSPACE_CATALOG_REF = Path(
    "configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_1.json"
)


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
        raise ValueError(f"vs4_supplement_json_object_required:{path.name}")
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
                    f"vs4_supplement_jsonl_object_required:{path.name}:{line_number}"
                )
            rows.append(value)
    return rows


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _verified(path: Path, expected_sha256: str, code: str) -> Path:
    if sha256_file(path) != expected_sha256:
        raise ValueError(code)
    return path


def _capture_resolver(reference: str) -> Path:
    raw = Path(reference)
    candidates = (
        raw,
        ROOT / raw,
        ROOT / "data/workbench_private/source_intake" / raw,
        ROOT / "data/workbench_private" / raw,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return (ROOT / raw).resolve()


def _reviewed_relations(
    policy: Mapping[str, Any], atom_id: str
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for row in policy.get("review_relations") or ():
        if str(row.get("atom_id") or "") != atom_id:
            continue
        object_id = str(row.get("compiled_object_id") or "")
        output[object_id] = {
            "judgement": str(row.get("judgement") or ""),
            "label_authority": "post_ranking_capture_bound_owner_review",
            "runtime_evidence_authority": False,
        }
    return output


def _coverage_state(atom_id: str) -> tuple[str, list[str], list[str]]:
    if atom_id == "S1_VS4_DELL_WORKING_CAPITAL":
        return (
            "qualitative_mechanism_and_direction_established_quantification_gap_remains",
            [
                "Dell 披露 AI 动态提高库存、应收和应付。",
                "Dell 披露大额 AI 订单会占用更多营运资金并带来取消、延迟和过时库存风险。",
            ],
            [
                "AI 产品级营运资金金额、周转天数桥和各科目具体增量仍未披露。"
            ],
        )
    if atom_id == "S1_VS4_DELL_ISSUER_COUNTER":
        return (
            "issuer_counterevidence_established",
            [
                "强订单可能伴随竞争定价、营运资金占用、订单取消和库存风险。"
            ],
            ["风险发生概率和已实现损失金额未披露。"],
        )
    if atom_id == "S1_VS4_DELL_UPSTREAM_COUNTER":
        return (
            "ecosystem_supply_counterevidence_established_subject_allocation_gap_remains",
            [
                "TSMC 管理层确认封装产能紧张、瓶颈工具和测试设备短缺。"
            ],
            ["这些行业约束与 Dell 的具体分配、产品映射和释放时点未被证明。"],
        )
    raise ValueError(f"vs4_supplement_coverage_atom_unknown:{atom_id}")


def materialize(*, policy_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    policy = _read_json(policy_path)
    bound = policy.get("bound_inputs") or {}
    predecessor_path = _verified(
        _resolve(str(bound.get("predecessor_pack_ref") or "")),
        str(bound.get("predecessor_pack_sha256") or ""),
        "vs4_supplement_predecessor_pack_drift",
    )
    predecessor = _read_json(predecessor_path)
    validate_reviewed_evidence_pack(predecessor)
    if predecessor.get("pack_payload_digest") != bound.get(
        "predecessor_pack_payload_digest"
    ):
        raise ValueError("vs4_supplement_predecessor_payload_drift")

    ranking_summary_path = _resolve(
        str(bound.get("candidate_ranking_summary_ref") or "")
    )
    ranking_summary = _read_json(ranking_summary_path)
    ranking_full_path = _verified(
        _resolve(str(bound.get("candidate_ranking_full_ref") or "")),
        str(bound.get("candidate_ranking_full_sha256") or ""),
        "vs4_supplement_ranking_full_drift",
    )
    ranking = _read_json(ranking_full_path)
    if not (
        ranking.get("result_digest") == bound.get("candidate_ranking_result_digest")
        == ranking_summary.get("result_digest")
        and ranking.get("summary", {}).get("positive_target_in_combined_union_rate")
        == 1.0
        and ranking.get("summary", {})
        .get("evidence_role", {})
        .get("positive_compatible_rate")
        == 1.0
        and ranking.get("summary", {})
        .get("evidence_role", {})
        .get("hard_negative_suppressed_or_abstained_rate")
        == 1.0
    ):
        raise ValueError("vs4_supplement_ranking_or_role_gate_failed")

    object_path = _verified(
        _resolve(str(bound.get("compiled_objects_ref") or "")),
        str(bound.get("compiled_objects_sha256") or ""),
        "vs4_supplement_object_store_drift",
    )
    record_path = _verified(
        _resolve(str(bound.get("source_records_ref") or "")),
        str(bound.get("source_records_sha256") or ""),
        "vs4_supplement_source_record_store_drift",
    )
    document_path = _verified(
        _resolve(str(bound.get("parent_documents_ref") or "")),
        str(bound.get("parent_documents_sha256") or ""),
        "vs4_supplement_parent_document_store_drift",
    )
    objects = load_compiled_objects(_read_jsonl(object_path))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    source_records = _read_jsonl(record_path)
    source_records_by_id = {str(row["evidence_id"]): row for row in source_records}
    parent_documents = _read_jsonl(document_path)
    parent_documents_by_id = {
        str(row["document_id"]): row for row in parent_documents
    }
    ranking_by_atom = {
        str(row.get("atom_id") or ""): row for row in ranking.get("atoms") or ()
    }
    ranked_candidates_by_atom = {
        atom_id: tuple(str(value) for value in row.get("candidate_union_ids") or ())
        for atom_id, row in ranking_by_atom.items()
    }
    core = build_capture_bound_pack_successor(
        predecessor=predecessor,
        policy=policy,
        ranked_candidates_by_atom=ranked_candidates_by_atom,
        compiled_objects_by_id=objects_by_id,
        source_records_by_id=source_records_by_id,
        parent_documents_by_id=parent_documents_by_id,
        capture_resolver=_capture_resolver,
        recorded_at=RECORDED_AT,
    )
    successor_pack = core["successor_pack"]

    query_atom_path = _resolve(str(ranking["bound_inputs"]["query_atom_eval_ref"]))
    kernel_path = _resolve(str(ranking["bound_inputs"]["kernel_ref"]))
    atoms = load_query_atoms(_read_json(query_atom_path))
    atom_by_id = {atom.atom_id: atom for atom in atoms}
    kernel = load_financial_research_kernel(_read_json(kernel_path))
    proposition_rows: list[dict[str, Any]] = []
    for atom_id in sorted(ranking_by_atom):
        atom = atom_by_id[atom_id]
        _request, lane = compile_atom_lane(atom, kernel)
        ledger = compile_object_candidate_decision_ledger(
            request=atom.request_payload,
            lane=lane,
            ranked_object_ids=ranked_candidates_by_atom[atom_id],
            objects_by_id=objects_by_id,
            reviewed_relations=_reviewed_relations(policy, atom_id),
            evidence_pack=successor_pack,
            recorded_at=RECORDED_AT,
        )
        relations = _reviewed_relations(policy, atom_id)
        positive_ids = {
            object_id
            for object_id, row in relations.items()
            if row["judgement"] == "positive"
        }
        hard_negative_ids = {
            object_id
            for object_id, row in relations.items()
            if row["judgement"] == "hard_negative"
        }
        accepted_ids = set(ledger.get("accepted_compiled_object_ids") or ())
        decisions = ledger.get("decisions") or ()
        hard_negative_accepted = [
            row["compiled_object_id"]
            for row in decisions
            if row.get("compiled_object_id") in hard_negative_ids
            and row.get("decision_state") == "accepted"
        ]
        state, known, unknown = _coverage_state(atom_id)
        proposition_ready = positive_ids <= accepted_ids and not hard_negative_accepted
        proposition_rows.append(
            {
                "atom_id": atom_id,
                "proposition_id": f"PROP::{canonical_digest({'atom_id': atom_id})[:24].upper()}",
                "slot_id": lane.slot_id,
                "facet_id": lane.facet_id,
                "coverage_state": state,
                "known": known,
                "unknown": unknown,
                "positive_reviewed_object_count": len(positive_ids),
                "positive_accepted_object_count": len(positive_ids & accepted_ids),
                "hard_negative_reviewed_object_count": len(hard_negative_ids),
                "hard_negative_accepted_object_ids": hard_negative_accepted,
                "candidate_decision_counts": ledger.get("decision_counts"),
                "accepted_compiled_object_ids": sorted(positive_ids & accepted_ids),
                "accepted_evidence_item_digests": sorted(
                    ledger.get("accepted_evidence_item_digests") or ()
                ),
                "proposition_ready": proposition_ready,
                "candidate_text_promoted": False,
                "numeric_authority": False,
                "candidate_decision_ledger": ledger,
            }
        )
    all_propositions_ready = all(row["proposition_ready"] for row in proposition_rows)
    workbench = compile_supplement_workbench_projection(
        result=core,
        proposition_rows=[
            {key: value for key, value in row.items() if key != "candidate_decision_ledger"}
            for row in proposition_rows
        ],
    )
    body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "vs4_dell_capture_bound_supplement_vertical_materialized",
        "recorded_at": RECORDED_AT,
        "slice_id": "FIN-0.1.3-S1-VS4-DELL-COVERAGE-DRIVEN-SUPPLEMENT-V1.0",
        "bound_inputs": {
            "policy_ref": _relative(policy_path),
            "policy_sha256_lf": _sha256_lf(policy_path),
            "predecessor_pack_ref": _relative(predecessor_path),
            "predecessor_pack_sha256": sha256_file(predecessor_path),
            "predecessor_pack_payload_digest": str(
                predecessor["pack_payload_digest"]
            ),
            "ranking_summary_ref": _relative(ranking_summary_path),
            "ranking_summary_sha256_lf": _sha256_lf(ranking_summary_path),
            "ranking_full_ref": _relative(ranking_full_path),
            "ranking_full_sha256": sha256_file(ranking_full_path),
            "compiled_objects_ref": _relative(object_path),
            "compiled_objects_sha256": sha256_file(object_path),
            "source_records_ref": _relative(record_path),
            "source_records_sha256": sha256_file(record_path),
            "parent_documents_ref": _relative(document_path),
            "parent_documents_sha256": sha256_file(document_path),
        },
        "core_result_digest": core["result_digest"],
        "coverage_delta": core["coverage_delta"],
        "capture_receipts": core["capture_receipts"],
        "review_receipts": core["review_receipts"],
        "gap_change_receipts": core["gap_change_receipts"],
        "proposition_rows": proposition_rows,
        "workbench_projection": workbench,
        "gate_results": {
            "candidate_generation_and_role_gate_passed": True,
            "all_reviewed_objects_capture_bound": True,
            "all_positive_objects_bound_to_successor_evidence": all_propositions_ready,
            "hard_negative_false_accept_count": sum(
                len(row["hard_negative_accepted_object_ids"])
                for row in proposition_rows
            ),
            "broad_or_legacy_evidence_replaced": (
                core["coverage_delta"]["retired_broad_or_legacy_evidence_count"]
                == 3
            ),
            "working_capital_gap_narrowed_not_closed": (
                core["coverage_delta"]["narrowed_gap_count"] == 1
                and core["coverage_delta"]["closed_gap_count"] == 0
            ),
            "vs4_dell_vertical_integrated": all_propositions_ready,
        },
        "decision": {
            "vs4_dell_status": (
                "bounded_capture_bound_supplement_ready"
                if all_propositions_ready
                else "gate_failed"
            ),
            "successor_pack_authorized": all_propositions_ready,
            "complete_s1_qualified": False,
            "runtime_route_promotion_authorized": False,
            "numeric_fact_authorized": False,
            "next_owning_work": (
                "Run equivalent natural Coverage-driven paths for MU and NVDA, then execute VS5 composite qualification."
                if all_propositions_ready
                else "Keep the failure in VS4 and repair the earliest failed evidence or capture gate."
            ),
        },
        "business_findings": [
            "Dell 自身已明确披露 AI 动态提高库存、应收和应付；旧系统把这一事实误留在营运资金 gap 外。",
            "Dell 的风险披露已能直接反驳“强订单必然高质量兑现”：大单会占用营运资金，并暴露于定价、延迟、取消和过时库存风险。",
            "TSMC 管理层确认封装产能紧张、瓶颈工具和测试设备短缺；这能支持行业供给反方，但不能证明 Dell 的分配量或释放时点。",
            "三条旧宽 chunk/整页证据被五条精确 claim 继任，分析师提问和同页无关句不再获得管理层事实权限。",
            "营运资金缺口只被窄化为产品级金额和归属桥未披露，未被静默删除或冒充所有公开信息均不存在。",
        ],
        "authority": {
            **dict(core["authority"]),
            "cuda_vector_execution_inherited_from_bound_ranking": True,
            "development_case_only": True,
            "complete_s1_qualified": False,
            "hidden_qualification_authorized": False,
        },
        "successor_pack": successor_pack,
    }
    return {**body, "result_digest": canonical_digest(body)}, successor_pack


def _compact(
    result: Mapping[str, Any],
    *,
    full_path: Path,
    pack_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "status": result["status"],
        "recorded_at": result["recorded_at"],
        "slice_id": result["slice_id"],
        "storage": {
            "full_result_ref": _relative(full_path),
            "full_result_sha256": sha256_file(full_path),
            "full_result_digest": result["result_digest"],
            "successor_pack_ref": _relative(pack_path),
            "successor_pack_sha256": sha256_file(pack_path),
            "successor_pack_payload_digest": result["successor_pack"][
                "pack_payload_digest"
            ],
        },
        "bound_inputs": result["bound_inputs"],
        "coverage_delta": result["coverage_delta"],
        "proposition_rows": [
            {key: value for key, value in row.items() if key != "candidate_decision_ledger"}
            for row in result["proposition_rows"]
        ],
        "workbench_projection": result["workbench_projection"],
        "gate_results": result["gate_results"],
        "decision": result["decision"],
        "business_findings": result["business_findings"],
        "authority": result["authority"],
        "result_digest": result["result_digest"],
    }


def _case_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    evidence = [dict(row) for row in pack.get("evidence_items") or ()]
    direct = sum(
        str(row.get("disposition") or "") == "accepted_direct_source_evidence"
        for row in evidence
    )
    return {
        "accepted_evidence_items": len(evidence),
        "bounded_context_items": len(evidence) - direct,
        "case_key": str(pack["case_key"]),
        "direct_evidence_items": direct,
        "rejected_items": len(pack.get("rejected_items") or ()),
        "residual_gaps": len(pack.get("residual_gaps") or ()),
        "source_materials": len(pack.get("source_materials") or ()),
        "status": str(pack["status"]),
    }


def _compose_current_product_surfaces(
    *,
    result: Mapping[str, Any],
    successor_pack: Mapping[str, Any],
    pack_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    predecessor_result = _read_json(_resolve(PREDECESSOR_CURRENT_PACK_REF))
    predecessor_anchor_payload = _read_json(
        _resolve(PREDECESSOR_ANCHOR_CATALOG_REF)
    )
    predecessor_workspace = _read_json(
        _resolve(PREDECESSOR_WORKSPACE_CATALOG_REF)
    )
    predecessor_anchor = load_reviewed_evidence_anchor_catalog(
        predecessor_anchor_payload
    )
    validate_reviewed_evidence_pack(successor_pack)
    predecessor_result_body = deepcopy(predecessor_result)
    predecessor_result_digest = str(
        predecessor_result_body.pop("result_digest", "")
    )
    if not (
        predecessor_result_digest == reviewed_pack_digest(predecessor_result_body)
        and predecessor_result.get("pack_payload_digests", {}).get("DELL")
        == result["bound_inputs"].get("predecessor_pack_payload_digest")
        and predecessor_result.get("pack_artifacts", {})
        .get("DELL", {})
        .get("digest")
        == result["bound_inputs"].get("predecessor_pack_sha256")
    ):
        raise ValueError("vs4_current_product_predecessor_binding_drift")

    private_root = _resolve("data/workbench_private")
    output_root = pack_path.parents[2]
    private_root_relative = output_root.relative_to(private_root).as_posix()
    object_key = pack_path.relative_to(output_root).as_posix()
    artifact_digest = sha256_file(pack_path)
    pack_payload_digest = str(successor_pack["pack_payload_digest"])

    current_body = deepcopy(predecessor_result)
    current_body.pop("result_digest", None)
    current_body["attempt_id"] = (
        "20260818_s1_vs4_dell_capture_bound_current_product_successor"
    )
    current_body["recorded_at"] = RECORDED_AT
    current_body["candidate_manifest_digest"] = str(
        successor_pack["candidate_manifest_digest"]
    )
    current_body["retrieval_result_digest"] = str(
        successor_pack["retrieval_result_digest"]
    )
    current_body["case_summaries"] = [
        _case_summary(successor_pack)
        if str(row.get("case_key") or "") == "DELL"
        else deepcopy(dict(row))
        for row in predecessor_result["case_summaries"]
    ]
    current_body["pack_artifacts"] = deepcopy(
        dict(predecessor_result["pack_artifacts"])
    )
    current_body["pack_artifacts"]["DELL"] = {
        "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
        "byte_size": pack_path.stat().st_size,
        "digest": artifact_digest,
        "media_type": "application/json",
        "object_key": object_key,
        "private_object_root_relative": private_root_relative,
    }
    current_body["pack_payload_digests"] = deepcopy(
        dict(predecessor_result["pack_payload_digests"])
    )
    current_body["pack_payload_digests"]["DELL"] = pack_payload_digest
    observed = deepcopy(dict(predecessor_result["observed_counts"]))
    observed["evidence_items"] = int(observed["evidence_items"]) + int(
        result["coverage_delta"]["successor_evidence_count"]
        - result["coverage_delta"]["predecessor_evidence_count"]
    )
    current_body["observed_counts"] = observed
    current_body["current_composition_lineage"] = {
        "schema_version": "fin_ia_current_pack_composition_lineage_v1_1",
        "predecessor_result_digest": predecessor_result_digest,
        "successor_result_digest": str(result["result_digest"]),
        "successor_pack_artifact_sha256": artifact_digest,
        "successor_pack_payload_digest": pack_payload_digest,
        "replacement_case_key": "DELL",
        "retained_case_keys": ["MU", "NVDA", "ORCL", "ASML", "ANET"],
        "private_object_copy_performed": False,
        "promotion_kind": "capture_bound_precision_and_coverage_successor",
    }
    current_body["known_boundary"] = (
        "Current composition exposes the DELL VS4 capture-bound precision successor "
        "while retaining MU, NVDA and development holdout packs by digest. It proves "
        "one bounded current-product supplement vertical, not open-web completeness, "
        "NumericFact authority, S1 qualification, report quality or release."
    )
    stage = deepcopy(dict(predecessor_result["stage_acceptance"]))
    stage["dell_capture_bound_supplement_promoted"] = True
    stage["dell_vs4_vertical_integrated"] = True
    stage["s1_product_acceptance"] = False
    current_body["stage_acceptance"] = stage
    current_result = {
        **current_body,
        "result_digest": reviewed_pack_digest(current_body),
    }

    successor_claims = {
        str(row["target_id"]): dict(row)
        for row in successor_pack["evidence_items"]
        if str(row.get("object_type") or "") == "claim"
    }
    retained_entries = [
        deepcopy(dict(row))
        for row in predecessor_anchor.entries
        if str(row["case_key"]) != "DELL"
        or str(row["target_id"]) in successor_claims
    ]
    retained_keys = {
        (str(row["case_key"]), str(row["target_id"]))
        for row in retained_entries
    }
    source_by_ref = {
        str(row["material_ref"]): dict(row)
        for row in successor_pack["source_materials"]
    }
    for target_id, item in successor_claims.items():
        if ("DELL", target_id) in retained_keys:
            continue
        source = source_by_ref[str(item["source_material_ref"])]
        anchor_text = str(source["source_text"])
        retained_entries.append(
            {
                "case_key": "DELL",
                "target_id": target_id,
                "source_record_id": str(item["source_record_id"]),
                "evidence_item_digest": str(item["evidence_item_digest"]),
                "source_text_digest": str(source["source_text_digest"]),
                "anchor_kind": "structured_claim_text",
                "anchor_text": anchor_text,
                "anchor_start": 0,
                "anchor_end": len(anchor_text),
                "anchor_digest": hashlib.sha256(
                    anchor_text.encode("utf-8")
                ).hexdigest(),
                "review_status": "reviewed_exact_source_surface",
            }
        )
    bindings = {
        key: deepcopy(dict(value))
        for key, value in predecessor_anchor.case_pack_bindings.items()
    }
    bindings["DELL"] = {
        "artifact_digest": artifact_digest,
        "pack_payload_digest": pack_payload_digest,
    }
    current_anchor = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings=bindings,
        entries=retained_entries,
        known_boundary=(
            "Anchors are verbatim surfaces for current DELL, MU and NVDA reviewed "
            "claim Evidence. The five DELL VS4 additions are exact capture-bound claim "
            "surfaces; anchors do not grant new Evidence, numeric or causal authority."
        ),
    )

    current_workspace = deepcopy(predecessor_workspace)
    current_workspace["evidence_pack_result_digest"] = current_result[
        "result_digest"
    ]
    for row in current_workspace["cases"]:
        if str(row.get("case_key") or "") != "DELL":
            continue
        row["evidence_pack_binding"] = {
            "pack_artifact_digest": artifact_digest,
            "pack_case_key": "DELL",
            "pack_payload_digest": pack_payload_digest,
        }
    current_workspace["known_boundary"] = (
        "FIN 0.1.3 exposes three identity-bound reviewed Evidence Packs. DELL now "
        "uses the capture-bound VS4 precision successor; MU and NVDA retain their "
        "predecessor packs. Dynamic case creation, S1 qualification, model research, "
        "complete reports and release remain unavailable."
    )
    return current_result, current_anchor, current_workspace


def _update_runtime_registry(
    summary_path: Path,
    *,
    current_result_path: Path | None = None,
    current_anchor_path: Path | None = None,
    current_workspace_path: Path | None = None,
) -> None:
    registry_path = _resolve(DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF)
    registry = _read_json(registry_path)
    rows = [
        dict(row)
        for row in registry.get("resources") or ()
        if str(row.get("resource_id") or "") != VS4_RESULT_RESOURCE_ID
    ]
    payload = summary_path.read_bytes()
    rows.append(
        {
            "resource_id": VS4_RESULT_RESOURCE_ID,
            "repo_relative_path": _relative(summary_path),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "classification": "digest_bound_read_only_s1_supplement_vertical_result",
            "consumer_ids": [
                "apps.workbench.backend.api.operations.get_s1_supplement_quality",
                "apps.workbench.research_evidence_pack_service.ResearchEvidencePackService.from_runtime_paths",
                "apps.workbench.research_retrieval_service.ResearchRetrievalService.from_runtime_paths",
            ],
            "load_phase": "application_service_initialization_and_operations_request",
            "required": True,
            "source_owner": "S1_canonical_vertical_slice_program",
        }
    )
    replacements = {
        CURRENT_PACK_RESULT_RESOURCE_ID: current_result_path,
        CURRENT_ANCHOR_RESOURCE_ID: current_anchor_path,
        CURRENT_WORKSPACE_RESOURCE_ID: current_workspace_path,
    }
    if any(path is not None for path in replacements.values()):
        if not all(path is not None for path in replacements.values()):
            raise ValueError("vs4_current_product_registry_paths_incomplete")
        for row in rows:
            replacement = replacements.get(str(row["resource_id"]))
            if replacement is None:
                continue
            payload = replacement.read_bytes()
            row["repo_relative_path"] = _relative(replacement)
            row["sha256"] = hashlib.sha256(payload).hexdigest()
            row["bytes"] = len(payload)
    rows.sort(key=lambda row: str(row["resource_id"]))
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R18"
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
        description="Materialize the S1 VS4 DELL Coverage-driven supplement vertical."
    )
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs4_dell_capture_bound_supplement_policy_v1_0.json",
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1_vs4_dell_supplement_vertical/v1_0",
    )
    parser.add_argument(
        "--summary-output",
        default="configs/retrieval/fin_ia_0_1_3_s1_vs4_dell_supplement_vertical_result_v1_0.json",
    )
    parser.add_argument(
        "--current-result-output",
        default="configs/runtime/fin_ia_current_research_evidence_pack_result_v1_2.json",
    )
    parser.add_argument(
        "--current-anchor-output",
        default="configs/runtime/fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_1.json",
    )
    parser.add_argument(
        "--current-workspace-output",
        default="configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_2.json",
    )
    parser.add_argument("--promote-current-product", action="store_true")
    parser.add_argument("--update-runtime-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result, successor_pack = materialize(policy_path=_resolve(args.policy))
    output_root = _resolve(args.full_output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    pack_digest = str(successor_pack["pack_payload_digest"])
    pack_path = output_root / "packs" / "dell" / f"{pack_digest}.json"
    _write_json(pack_path, successor_pack)
    full_path = output_root / f"full_result_{result['result_digest']}.json"
    _write_json(full_path, result)
    summary = _compact(result, full_path=full_path, pack_path=pack_path)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary)
    current_paths: tuple[Path | None, Path | None, Path | None] = (
        None,
        None,
        None,
    )
    if args.promote_current_product:
        if not (
            summary["decision"]["successor_pack_authorized"] is True
            and summary["gate_results"]["vs4_dell_vertical_integrated"] is True
        ):
            raise ValueError("vs4_current_product_promotion_not_authorized")
        current_result, current_anchor, current_workspace = (
            _compose_current_product_surfaces(
                result=result,
                successor_pack=successor_pack,
                pack_path=pack_path,
            )
        )
        current_paths = (
            _resolve(args.current_result_output),
            _resolve(args.current_anchor_output),
            _resolve(args.current_workspace_output),
        )
        _write_json(current_paths[0], current_result)
        _write_json(current_paths[1], current_anchor)
        _write_json(current_paths[2], current_workspace)
    if args.update_runtime_registry:
        _update_runtime_registry(
            summary_path,
            current_result_path=current_paths[0],
            current_anchor_path=current_paths[1],
            current_workspace_path=current_paths[2],
        )
    print(json.dumps(summary["coverage_delta"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["gate_results"], ensure_ascii=False, indent=2))
    print(json.dumps(summary["decision"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
