from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any, Mapping, Sequence


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
    CASE_SUPPLEMENT_SUMMARY_SCHEMA_VERSION,
    SUPPLEMENT_SUMMARY_SET_SCHEMA_VERSION,
    build_capture_bound_pack_successor,
    compile_supplement_workbench_projection,
    validate_supplement_vertical_summary,
    validate_supplement_vertical_summary_set,
)
from sec_agent.research.reviewed_evidence_anchor import (  # noqa: E402
    compile_reviewed_evidence_anchor_catalog,
    load_reviewed_evidence_anchor_catalog,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    canonical_digest as reviewed_pack_digest,
    validate_reviewed_evidence_pack,
)
from sec_agent.runtime_resource_registry import (  # noqa: E402
    DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF,
)


RECORDED_AT = "2026-08-18"
RESULT_SCHEMA_VERSION = "fin_ia_s1_vs4_case_supplement_vertical_result_v1_0"
VS4_RESULT_RESOURCE_ID = "application.result.current_s1_vs4_supplement_vertical"
CURRENT_PACK_RESULT_RESOURCE_ID = "application.result.current_research_local_evidence_packs"
CURRENT_ANCHOR_RESOURCE_ID = "application.result.current_reviewed_claim_anchors"
CURRENT_WORKSPACE_RESOURCE_ID = "application.config.current_research_workspace_catalog"


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValueError(code)


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
    _require(isinstance(value, dict), f"vs4_case_json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            _require(
                isinstance(value, dict),
                f"vs4_case_jsonl_object_required:{path.name}:{line_number}",
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


def _verified(path: Path, expected_sha256: str, code: str) -> Path:
    _require(path.is_file() and sha256_file(path) == expected_sha256, code)
    return path


def _capture_resolver(reference: str) -> Path:
    raw = Path(reference)
    for candidate in (
        raw,
        ROOT / raw,
        ROOT / "data/workbench_private/source_intake" / raw,
        ROOT / "data/workbench_private" / raw,
    ):
        if candidate.is_file():
            return candidate.resolve()
    return (ROOT / raw).resolve()


def _pack_path(
    artifact: Mapping[str, Any], *, projection_config: Mapping[str, Any]
) -> Path:
    root_ref = str(
        artifact.get("private_object_root_relative")
        or projection_config.get("private_object_root_relative")
        or ""
    )
    object_key = str(artifact.get("object_key") or "")
    root = PurePosixPath(root_ref)
    key = PurePosixPath(object_key)
    _require(
        root_ref
        and object_key
        and not root.is_absolute()
        and not key.is_absolute()
        and ".." not in root.parts
        and ".." not in key.parts,
        "vs4_case_predecessor_object_path_invalid",
    )
    return ROOT.joinpath("data", "workbench_private", *root.parts, *key.parts)


def _load_bound_inputs(policy: Mapping[str, Any]) -> dict[str, Any]:
    bound = dict(policy.get("bound_inputs") or {})
    paths: dict[str, Path] = {}
    for key, code in (
        ("current_pack_result", "vs4_case_current_pack_result_drift"),
        ("projection_config", "vs4_case_projection_config_drift"),
        ("current_anchor_catalog", "vs4_case_anchor_catalog_drift"),
        ("current_workspace_catalog", "vs4_case_workspace_catalog_drift"),
        ("legacy_dell_summary", "vs4_case_legacy_dell_summary_drift"),
        ("candidate_ranking_summary", "vs4_case_ranking_summary_drift"),
        ("candidate_ranking_full", "vs4_case_ranking_full_drift"),
        ("compiled_objects", "vs4_case_compiled_objects_drift"),
        ("source_records", "vs4_case_source_records_drift"),
        ("parent_documents", "vs4_case_parent_documents_drift"),
    ):
        paths[key] = _verified(
            _resolve(str(bound.get(f"{key}_ref") or "")),
            str(bound.get(f"{key}_sha256") or ""),
            code,
        )
    return {"values": bound, "paths": paths}


def _validate_ranking_gate(
    summary: Mapping[str, Any], full: Mapping[str, Any], bound: Mapping[str, Any]
) -> None:
    metrics = dict(summary.get("summary") or {})
    rerankers = dict(metrics.get("rerankers") or {})
    shortlist = dict(rerankers.get("financial_evidence_shortlist_v1") or {})
    role = dict(metrics.get("evidence_role") or {})
    candidate_role = dict(metrics.get("candidate_pool_evidence_role") or {})
    cuda = dict(summary.get("execution") or {}).get("cuda_execution_receipt") or {}
    _require(
        summary.get("result_digest")
        == full.get("result_digest")
        == bound.get("candidate_ranking_result_digest")
        and metrics.get("positive_target_in_combined_union_rate") == 1.0
        and shortlist.get("positive_target_in_top_k_count")
        == shortlist.get("positive_atom_count")
        and shortlist.get("pairwise_accuracy") == 1.0
        and role.get("positive_compatible_rate") == 1.0
        and role.get("hard_negative_suppressed_or_abstained_rate") == 1.0
        and candidate_role.get("positive_compatible_rate") == 1.0
        and candidate_role.get("hard_negative_suppressed_or_abstained_rate")
        == 1.0
        and cuda.get("execution_device") == "cuda:0"
        and cuda.get("cpu_fallback_allowed") is False
        and cuda.get("embedding_precision") == "fp16"
        and cuda.get("reranker_precision") == "fp16",
        "vs4_case_ranking_cuda_or_business_gate_failed",
    )


def _ranking_reviews(
    *,
    case_key: str,
    ranking_rows: Sequence[Mapping[str, Any]],
    materialized_positive_ids: frozenset[str],
    materialized_hard_negative_ids: frozenset[str],
) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for atom in ranking_rows:
        if str(atom.get("case_key") or "").upper() != case_key:
            continue
        atom_id = str(atom.get("atom_id") or "")
        reviews: dict[str, str] = {}
        for row in dict(atom.get("evidence_role") or {}).get(
            "judged_label_rows"
        ) or ():
            eligibility = dict(row.get("eligibility") or {})
            if eligibility.get("eligible") is not True:
                continue
            judgement = str(row.get("judgement") or "")
            if judgement not in {"positive", "hard_negative"}:
                continue
            object_id = str(row.get("compiled_object_id") or "")
            if judgement == "positive" and object_id not in materialized_positive_ids:
                continue
            if (
                judgement == "hard_negative"
                and object_id not in materialized_hard_negative_ids
            ):
                continue
            _require(object_id and object_id not in reviews, "vs4_case_review_duplicate")
            reviews[object_id] = judgement
        _require(reviews, f"vs4_case_review_labels_missing:{atom_id}")
        output[atom_id] = reviews
    return output


def _compile_case_policy(
    *,
    case_key: str,
    case_config: Mapping[str, Any],
    ranking_rows: Sequence[Mapping[str, Any]],
    atom_by_id: Mapping[str, Any],
    kernel: Any,
    predecessor: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, tuple[str, ...]], dict[str, Any]]:
    reviews_by_atom = _ranking_reviews(
        case_key=case_key,
        ranking_rows=ranking_rows,
        materialized_positive_ids=frozenset(
            str(value) for value in case_config.get("promotion_object_ids") or ()
        ),
        materialized_hard_negative_ids=frozenset(
            str(value)
            for value in case_config.get("materialize_hard_negative_object_ids")
            or ()
        ),
    )
    expected_atoms = tuple(str(value) for value in case_config.get("atom_ids") or ())
    _require(
        expected_atoms and set(expected_atoms) == set(reviews_by_atom),
        "vs4_case_atom_set_drift",
    )
    specs = {
        str(key): dict(value)
        for key, value in dict(case_config.get("promotion_specs") or {}).items()
    }
    positive_occurrences: dict[str, list[str]] = {}
    for atom_id in expected_atoms:
        for object_id, judgement in reviews_by_atom[atom_id].items():
            if judgement == "positive":
                positive_occurrences.setdefault(object_id, []).append(atom_id)
    _require(
        set(specs) == set(positive_occurrences),
        "vs4_case_reviewed_positive_spec_set_drift",
    )

    lane_by_atom: dict[str, Any] = {}
    for atom_id in expected_atoms:
        atom = atom_by_id.get(atom_id)
        _require(atom is not None, f"vs4_case_query_atom_missing:{atom_id}")
        _request, lane_by_atom[atom_id] = compile_atom_lane(atom, kernel)

    add_owner = {
        object_id: atom_ids[0]
        for object_id, atom_ids in positive_occurrences.items()
    }
    relations: list[dict[str, Any]] = []
    for atom_id in expected_atoms:
        atom_config = dict(
            dict(case_config.get("coverage_statements") or {}).get(atom_id) or {}
        )
        direction = str(atom_config.get("relationship_direction") or "")
        _require(direction, f"vs4_case_relationship_direction_missing:{atom_id}")
        lane = lane_by_atom[atom_id]
        for object_id, judgement in sorted(reviews_by_atom[atom_id].items()):
            row: dict[str, Any] = {
                "atom_id": atom_id,
                "compiled_object_id": object_id,
                "judgement": judgement,
                "evidence_action": (
                    "reject_candidate"
                    if judgement == "hard_negative"
                    else (
                        "add_capture_bound_evidence"
                        if add_owner[object_id] == atom_id
                        else "reuse_reviewed_evidence"
                    )
                ),
                "slot_id": lane.slot_id,
                "facet_id": lane.facet_id,
                "relationship_direction": direction,
            }
            if judgement == "positive" and add_owner[object_id] == atom_id:
                spec = specs[object_id]
                slot_bindings = []
                for linked_atom_id in positive_occurrences[object_id]:
                    linked_lane = lane_by_atom[linked_atom_id]
                    slot_bindings.append(
                        {
                            "slot_id": linked_lane.slot_id,
                            "facet_ids": [linked_lane.facet_id],
                            "qualification_id": (
                                f"{case_key.lower()}-{object_id.split('::')[-1].lower()}-"
                                f"{linked_atom_id.lower()}"
                            ),
                            "business_meaning_zh": str(
                                spec.get("business_meaning_zh") or ""
                            ),
                            "claim_boundary_zh": str(
                                spec.get("claim_boundary_zh") or ""
                            ),
                        }
                    )
                row["evidence_spec"] = {
                    "disposition": spec.get("disposition"),
                    "relationship_directions": list(
                        spec.get("relationship_directions") or (direction,)
                    ),
                    "slot_bindings": slot_bindings,
                }
            relations.append(row)

    policy = {
        "policy_id": str(case_config.get("policy_id") or ""),
        "case_key": case_key,
        "research_as_of": str(case_config.get("research_as_of") or ""),
        "retire_evidence_item_digests": (
            [
                str(row.get("evidence_item_digest") or "")
                for row in predecessor.get("evidence_items") or ()
            ]
            if case_config.get("retire_all_predecessor_evidence") is True
            else list(case_config.get("retire_evidence_item_digests") or ())
        ),
        "review_relations": relations,
        "gap_updates": deepcopy(list(case_config.get("gap_updates") or ())),
        "gap_additions": deepcopy(
            list(case_config.get("gap_additions") or ())
        ),
        "successor_known_boundary": str(
            case_config.get("successor_known_boundary") or ""
        ),
    }
    ranked_by_atom = {
        str(row.get("atom_id") or ""): tuple(
            str(value) for value in row.get("candidate_union_ids") or ()
        )
        for row in ranking_rows
        if str(row.get("case_key") or "").upper() == case_key
    }
    return policy, ranked_by_atom, lane_by_atom


def _reviewed_relations(
    relations: Sequence[Mapping[str, Any]], atom_id: str
) -> dict[str, dict[str, Any]]:
    return {
        str(row["compiled_object_id"]): {
            "judgement": str(row["judgement"]),
            "label_authority": "post_ranking_capture_bound_business_review",
            "runtime_evidence_authority": False,
        }
        for row in relations
        if str(row.get("atom_id") or "") == atom_id
    }


def _case_summary(pack: Mapping[str, Any]) -> dict[str, Any]:
    evidence = [dict(row) for row in pack.get("evidence_items") or ()]
    direct = sum(
        row.get("disposition") == "accepted_direct_source_evidence"
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


def _materialize_case(
    *,
    case_key: str,
    case_config: Mapping[str, Any],
    predecessor: Mapping[str, Any],
    predecessor_path: Path,
    ranking: Mapping[str, Any],
    ranking_summary_path: Path,
    ranking_full_path: Path,
    atom_by_id: Mapping[str, Any],
    kernel: Any,
    objects_by_id: Mapping[str, Mapping[str, Any]],
    records_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    legacy_capture_attestations: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    policy, ranked_by_atom, lane_by_atom = _compile_case_policy(
        case_key=case_key,
        case_config=case_config,
        ranking_rows=list(ranking.get("atoms") or ()),
        atom_by_id=atom_by_id,
        kernel=kernel,
        predecessor=predecessor,
    )
    core = build_capture_bound_pack_successor(
        predecessor=predecessor,
        policy=policy,
        ranked_candidates_by_atom=ranked_by_atom,
        compiled_objects_by_id=objects_by_id,
        source_records_by_id=records_by_id,
        parent_documents_by_id=documents_by_id,
        capture_resolver=_capture_resolver,
        recorded_at=RECORDED_AT,
        legacy_capture_attestations_by_parent_id=legacy_capture_attestations,
    )
    successor = core["successor_pack"]
    proposition_rows: list[dict[str, Any]] = []
    relation_rows = list(policy["review_relations"])
    coverage = dict(case_config.get("coverage_statements") or {})
    for atom_id in case_config.get("atom_ids") or ():
        atom = atom_by_id[str(atom_id)]
        ledger = compile_object_candidate_decision_ledger(
            request=atom.request_payload,
            lane=lane_by_atom[str(atom_id)],
            ranked_object_ids=ranked_by_atom[str(atom_id)],
            objects_by_id=objects_by_id,
            reviewed_relations=_reviewed_relations(relation_rows, str(atom_id)),
            evidence_pack=successor,
            recorded_at=RECORDED_AT,
        )
        relations = _reviewed_relations(relation_rows, str(atom_id))
        positives = {
            object_id
            for object_id, row in relations.items()
            if row["judgement"] == "positive"
        }
        negatives = {
            object_id
            for object_id, row in relations.items()
            if row["judgement"] == "hard_negative"
        }
        accepted = set(ledger.get("accepted_compiled_object_ids") or ())
        negative_accepts = sorted(
            str(row["compiled_object_id"])
            for row in ledger.get("decisions") or ()
            if row.get("compiled_object_id") in negatives
            and row.get("decision_state") == "accepted"
        )
        statement = dict(coverage.get(str(atom_id)) or {})
        proposition_rows.append(
            {
                "atom_id": str(atom_id),
                "proposition_id": (
                    f"PROP::{canonical_digest({'case_key': case_key, 'atom_id': atom_id})[:24].upper()}"
                ),
                "slot_id": lane_by_atom[str(atom_id)].slot_id,
                "facet_id": lane_by_atom[str(atom_id)].facet_id,
                "coverage_state": str(statement.get("coverage_state") or ""),
                "known": list(statement.get("known") or ()),
                "unknown": list(statement.get("unknown") or ()),
                "positive_reviewed_object_count": len(positives),
                "positive_accepted_object_count": len(positives & accepted),
                "hard_negative_reviewed_object_count": len(negatives),
                "hard_negative_accepted_object_ids": negative_accepts,
                "candidate_decision_counts": ledger.get("decision_counts"),
                "accepted_compiled_object_ids": sorted(positives & accepted),
                "accepted_evidence_item_digests": sorted(
                    ledger.get("accepted_evidence_item_digests") or ()
                ),
                "proposition_ready": positives <= accepted and not negative_accepts,
                "candidate_text_promoted": False,
                "numeric_authority": False,
                "candidate_decision_ledger": ledger,
            }
        )
    all_ready = all(row["proposition_ready"] for row in proposition_rows)
    workbench = compile_supplement_workbench_projection(
        result=core,
        proposition_rows=[
            {key: value for key, value in row.items() if key != "candidate_decision_ledger"}
            for row in proposition_rows
        ],
    )
    body = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "vs4_case_capture_bound_supplement_vertical_materialized",
        "recorded_at": RECORDED_AT,
        "case_key": case_key,
        "slice_id": str(case_config.get("slice_id") or ""),
        "bound_inputs": {
            "predecessor_pack_ref": _relative(predecessor_path),
            "predecessor_pack_sha256": sha256_file(predecessor_path),
            "predecessor_pack_payload_digest": predecessor["pack_payload_digest"],
            "ranking_summary_ref": _relative(ranking_summary_path),
            "ranking_full_ref": _relative(ranking_full_path),
            "ranking_result_digest": ranking["result_digest"],
        },
        "coverage_delta": core["coverage_delta"],
        "proposition_rows": proposition_rows,
        "workbench_projection": workbench,
        "gate_results": {
            "all_registered_positive_objects_capture_bound": all_ready,
            "hard_negative_false_accept_count": sum(
                len(row["hard_negative_accepted_object_ids"])
                for row in proposition_rows
            ),
            "bound_ranking_hard_negatives_suppressed_or_abstained": True,
            "all_predecessor_broad_or_legacy_evidence_retired": (
                core["coverage_delta"]["retired_broad_or_legacy_evidence_count"]
                == core["coverage_delta"]["predecessor_evidence_count"]
            ),
            "gap_count_not_silently_reduced": (
                core["coverage_delta"]["predecessor_gap_count"]
                <= core["coverage_delta"]["successor_gap_count"]
                and core["coverage_delta"]["closed_gap_count"] == 0
            ),
            "case_vertical_integrated": all_ready,
        },
        "decision": {
            "case_status": (
                "bounded_capture_bound_supplement_ready" if all_ready else "gate_failed"
            ),
            "successor_pack_authorized": all_ready,
            "complete_s1_qualified": False,
            "runtime_route_promotion_authorized": False,
            "numeric_fact_authorized": False,
            "next_owning_work": (
                "Execute VS5 cross-case composite qualification."
                if all_ready
                else "Keep failure in VS4 and repair the earliest evidence or capture gate."
            ),
        },
        "business_findings": list(case_config.get("business_findings") or ()),
        "authority": {
            **dict(core["authority"]),
            "cuda_vector_execution_inherited_from_bound_ranking": True,
            "development_case_only": True,
            "complete_s1_qualified": False,
            "hidden_qualification_authorized": False,
        },
        "successor_pack": successor,
    }
    return {**body, "result_digest": canonical_digest(body)}, successor


def _compact_case(
    result: Mapping[str, Any], *, full_path: Path, pack_path: Path
) -> dict[str, Any]:
    return {
        "schema_version": CASE_SUPPLEMENT_SUMMARY_SCHEMA_VERSION,
        "status": "vs4_case_capture_bound_supplement_vertical_materialized",
        "recorded_at": result["recorded_at"],
        "case_key": result["case_key"],
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


def _compose_current_surfaces(
    *,
    current_result: Mapping[str, Any],
    anchor_payload: Mapping[str, Any],
    workspace: Mapping[str, Any],
    replacements: Mapping[str, tuple[Mapping[str, Any], Path, Mapping[str, Any]]],
    output_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    body = deepcopy(dict(current_result))
    current_digest = str(body.pop("result_digest", ""))
    _require(
        current_digest == reviewed_pack_digest(body),
        "vs4_case_current_result_digest_drift",
    )
    body["attempt_id"] = "20260818_s1_vs4_mu_nvda_capture_bound_current_successor"
    body["recorded_at"] = RECORDED_AT
    body["case_summaries"] = [
        (
            _case_summary(replacements[str(row["case_key"])][0])
            if str(row.get("case_key") or "") in replacements
            else deepcopy(dict(row))
        )
        for row in current_result.get("case_summaries") or ()
    ]
    body["pack_artifacts"] = deepcopy(dict(current_result["pack_artifacts"]))
    body["pack_payload_digests"] = deepcopy(
        dict(current_result["pack_payload_digests"])
    )
    evidence_delta = 0
    for case_key, (pack, pack_path, result) in replacements.items():
        expected_artifact = str(current_result["pack_artifacts"][case_key]["digest"])
        expected_payload = str(current_result["pack_payload_digests"][case_key])
        _require(
            result["bound_inputs"]["predecessor_pack_sha256"] == expected_artifact
            and result["bound_inputs"]["predecessor_pack_payload_digest"]
            == expected_payload,
            "vs4_case_current_predecessor_binding_drift",
        )
        body["pack_artifacts"][case_key] = {
            "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
            "byte_size": pack_path.stat().st_size,
            "digest": sha256_file(pack_path),
            "media_type": "application/json",
            "object_key": pack_path.relative_to(output_root).as_posix(),
            "private_object_root_relative": output_root.relative_to(
                _resolve("data/workbench_private")
            ).as_posix(),
        }
        body["pack_payload_digests"][case_key] = pack["pack_payload_digest"]
        evidence_delta += int(result["coverage_delta"]["successor_evidence_count"])
        evidence_delta -= int(result["coverage_delta"]["predecessor_evidence_count"])
    observed = deepcopy(dict(current_result["observed_counts"]))
    observed["evidence_items"] = int(observed["evidence_items"]) + evidence_delta
    body["observed_counts"] = observed
    body["current_composition_lineage"] = {
        "schema_version": "fin_ia_current_pack_composition_lineage_v1_2",
        "predecessor_result_digest": current_digest,
        "replacement_case_keys": sorted(replacements),
        "replacement_result_digests": {
            key: str(value[2]["result_digest"])
            for key, value in sorted(replacements.items())
        },
        "retained_case_keys": ["DELL", "ORCL", "ASML", "ANET"],
        "private_object_copy_performed": False,
        "promotion_kind": "multi_case_capture_bound_precision_successor",
    }
    body["known_boundary"] = (
        "Current composition exposes DELL, MU and NVDA capture-bound precision "
        "successors while retaining development holdout packs by digest. It does "
        "not prove open-web completeness, NumericFact authority, S1 qualification, "
        "research report quality or release."
    )
    stage = deepcopy(dict(current_result["stage_acceptance"]))
    stage["mu_capture_bound_supplement_promoted"] = True
    stage["nvda_capture_bound_supplement_promoted"] = True
    stage["mu_nvda_vs4_vertical_integrated"] = True
    stage["s1_product_acceptance"] = False
    body["stage_acceptance"] = stage
    composed_result = {**body, "result_digest": reviewed_pack_digest(body)}

    predecessor_anchor = load_reviewed_evidence_anchor_catalog(anchor_payload)
    replacement_keys = set(replacements)
    entries = [
        deepcopy(dict(row))
        for row in predecessor_anchor.entries
        if str(row["case_key"]) not in replacement_keys
    ]
    bindings = {
        key: deepcopy(dict(value))
        for key, value in predecessor_anchor.case_pack_bindings.items()
    }
    for case_key, (pack, pack_path, _result) in sorted(replacements.items()):
        sources = {
            str(row["material_ref"]): dict(row)
            for row in pack["source_materials"]
        }
        for item in pack["evidence_items"]:
            if str(item.get("object_type") or "") != "claim":
                continue
            source = sources[str(item["source_material_ref"])]
            text = str(source["source_text"])
            entries.append(
                {
                    "case_key": case_key,
                    "target_id": str(item["target_id"]),
                    "source_record_id": str(item["source_record_id"]),
                    "evidence_item_digest": str(item["evidence_item_digest"]),
                    "source_text_digest": str(source["source_text_digest"]),
                    "anchor_kind": "structured_claim_text",
                    "anchor_text": text,
                    "anchor_start": 0,
                    "anchor_end": len(text),
                    "anchor_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "review_status": "reviewed_exact_source_surface",
                }
            )
        bindings[case_key] = {
            "artifact_digest": sha256_file(pack_path),
            "pack_payload_digest": str(pack["pack_payload_digest"]),
        }
    anchor = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings=bindings,
        entries=entries,
        known_boundary=(
            "Anchors are exact source surfaces for current DELL, MU and NVDA claim "
            "Evidence. They grant no new Evidence, numeric or causal authority."
        ),
    )

    composed_workspace = deepcopy(dict(workspace))
    composed_workspace["evidence_pack_result_digest"] = composed_result[
        "result_digest"
    ]
    for row in composed_workspace["cases"]:
        case_key = str(row.get("case_key") or "")
        if case_key not in replacements:
            continue
        pack, pack_path, _result = replacements[case_key]
        row["evidence_pack_binding"] = {
            "pack_artifact_digest": sha256_file(pack_path),
            "pack_case_key": case_key,
            "pack_payload_digest": str(pack["pack_payload_digest"]),
        }
    composed_workspace["known_boundary"] = (
        "FIN 0.1.3 exposes three identity-bound capture-verified Evidence Pack "
        "successors. Dynamic case creation, complete S1 qualification, S2 NumericFact, "
        "model research, complete reports and release remain unavailable."
    )
    return composed_result, anchor, composed_workspace


def _update_registry(
    *, summary_path: Path, result_path: Path, anchor_path: Path, workspace_path: Path
) -> None:
    registry_path = _resolve(DEFAULT_RUNTIME_RESOURCE_REGISTRY_REF)
    registry = _read_json(registry_path)
    replacements = {
        VS4_RESULT_RESOURCE_ID: summary_path,
        CURRENT_PACK_RESULT_RESOURCE_ID: result_path,
        CURRENT_ANCHOR_RESOURCE_ID: anchor_path,
        CURRENT_WORKSPACE_RESOURCE_ID: workspace_path,
    }
    rows = [dict(row) for row in registry.get("resources") or ()]
    for row in rows:
        replacement = replacements.get(str(row.get("resource_id") or ""))
        if replacement is None:
            continue
        payload = replacement.read_bytes()
        row["repo_relative_path"] = _relative(replacement)
        row["sha256"] = hashlib.sha256(payload).hexdigest()
        row["bytes"] = len(payload)
        if row["resource_id"] == VS4_RESULT_RESOURCE_ID:
            row["classification"] = (
                "digest_bound_read_only_s1_case_supplement_summary_set"
            )
    registry["registry_id"] = "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R19"
    rows.sort(key=lambda row: str(row["resource_id"]))
    registry["resources"] = rows
    registry["resource_count"] = len(rows)
    registry["resource_bytes"] = sum(int(row["bytes"]) for row in rows)
    registry["resource_canonical_digest"] = canonical_json_digest(rows)
    _write_json(registry_path, registry)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Materialize capture-bound S1 VS4 successors for configured cases."
    )
    parser.add_argument(
        "--policy",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_vs4_mu_nvda_capture_bound_supplement_policy_v1_0.json"
        ),
    )
    parser.add_argument(
        "--full-output-root",
        default="data/workbench_private/fin_0_1_3_s1_vs4_case_supplement_vertical/v1_0",
    )
    parser.add_argument(
        "--summary-output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1_vs4_case_supplement_vertical_result_v1_0.json"
        ),
    )
    parser.add_argument(
        "--current-result-output",
        default="configs/runtime/fin_ia_current_research_evidence_pack_result_v1_3.json",
    )
    parser.add_argument(
        "--current-anchor-output",
        default=(
            "configs/runtime/"
            "fin_ia_0_1_3_current_reviewed_claim_anchor_catalog_v1_2.json"
        ),
    )
    parser.add_argument(
        "--current-workspace-output",
        default="configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_3.json",
    )
    parser.add_argument("--promote-current-product", action="store_true")
    parser.add_argument("--update-runtime-registry", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy_path = _resolve(args.policy)
    policy = _read_json(policy_path)
    loaded = _load_bound_inputs(policy)
    bound = loaded["values"]
    paths = loaded["paths"]
    current_result = _read_json(paths["current_pack_result"])
    _require(
        current_result.get("result_digest") == bound.get("current_pack_result_digest"),
        "vs4_case_current_pack_result_digest_drift",
    )
    projection_config = _read_json(paths["projection_config"])
    ranking_summary = _read_json(paths["candidate_ranking_summary"])
    ranking = _read_json(paths["candidate_ranking_full"])
    _validate_ranking_gate(ranking_summary, ranking, bound)
    objects = load_compiled_objects(_read_jsonl(paths["compiled_objects"]))
    objects_by_id = {str(row["compiled_object_id"]): row for row in objects}
    records = _read_jsonl(paths["source_records"])
    records_by_id = {str(row["evidence_id"]): row for row in records}
    documents = _read_jsonl(paths["parent_documents"])
    documents_by_id = {str(row["document_id"]): row for row in documents}
    query_atoms = load_query_atoms(
        _read_json(_resolve(str(ranking["bound_inputs"]["query_atom_eval_ref"])))
    )
    atom_by_id = {atom.atom_id: atom for atom in query_atoms}
    kernel = load_financial_research_kernel(
        _read_json(_resolve(str(ranking["bound_inputs"]["kernel_ref"])))
    )

    output_root = _resolve(args.full_output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict[str, Any]] = {}
    packs: dict[str, dict[str, Any]] = {}
    pack_paths: dict[str, Path] = {}
    case_summaries: dict[str, dict[str, Any]] = {}
    object_spec_library = {
        str(key): dict(value)
        for key, value in dict(policy.get("object_spec_library") or {}).items()
    }
    legacy_capture_attestations = {
        str(key): dict(value)
        for key, value in dict(
            policy.get("legacy_capture_attestations") or {}
        ).items()
    }
    for raw_key, raw_config in sorted(dict(policy.get("cases") or {}).items()):
        case_key = str(raw_key).upper()
        case_config = dict(raw_config)
        overrides = {
            str(key): dict(value)
            for key, value in dict(
                case_config.get("promotion_spec_overrides") or {}
            ).items()
        }
        case_config["promotion_specs"] = {
            object_id: {
                **dict(object_spec_library.get(object_id) or {}),
                **dict(overrides.get(object_id) or {}),
            }
            for object_id in case_config.get("promotion_object_ids") or ()
        }
        artifact = dict(current_result["pack_artifacts"][case_key])
        predecessor_path = _verified(
            _pack_path(artifact, projection_config=projection_config),
            str(case_config.get("predecessor_pack_sha256") or ""),
            f"vs4_case_predecessor_artifact_drift:{case_key}",
        )
        predecessor = _read_json(predecessor_path)
        validate_reviewed_evidence_pack(predecessor)
        _require(
            predecessor.get("pack_payload_digest")
            == case_config.get("predecessor_pack_payload_digest")
            == current_result["pack_payload_digests"][case_key],
            f"vs4_case_predecessor_payload_drift:{case_key}",
        )
        result, pack = _materialize_case(
            case_key=case_key,
            case_config=case_config,
            predecessor=predecessor,
            predecessor_path=predecessor_path,
            ranking=ranking,
            ranking_summary_path=paths["candidate_ranking_summary"],
            ranking_full_path=paths["candidate_ranking_full"],
            atom_by_id=atom_by_id,
            kernel=kernel,
            objects_by_id=objects_by_id,
            records_by_id=records_by_id,
            documents_by_id=documents_by_id,
            legacy_capture_attestations=legacy_capture_attestations,
        )
        pack_path = output_root / "packs" / case_key.lower() / (
            f"{pack['pack_payload_digest']}.json"
        )
        _write_json(pack_path, pack)
        full_path = output_root / case_key.lower() / (
            f"full_result_{result['result_digest']}.json"
        )
        _write_json(full_path, result)
        summary = _compact_case(result, full_path=full_path, pack_path=pack_path)
        validate_supplement_vertical_summary(summary)
        results[case_key] = result
        packs[case_key] = pack
        pack_paths[case_key] = pack_path
        case_summaries[case_key] = summary

    legacy_dell = validate_supplement_vertical_summary(
        _read_json(paths["legacy_dell_summary"])
    )
    set_body = {
        "schema_version": SUPPLEMENT_SUMMARY_SET_SCHEMA_VERSION,
        "status": "vs4_case_supplement_summary_set_ready",
        "recorded_at": RECORDED_AT,
        "case_summaries": {"DELL": legacy_dell, **case_summaries},
        "decision": {
            "vs4_case_keys_integrated": sorted(case_summaries),
            "all_case_successors_authorized": all(
                value["decision"]["successor_pack_authorized"] is True
                for value in case_summaries.values()
            ),
            "complete_s1_qualified": False,
            "next_owning_work": "Execute VS5 composite qualification.",
        },
    }
    summary_set = {
        **set_body,
        "summary_set_digest": canonical_digest(set_body),
    }
    # Validate the exact serialized shape before it can be registered. The
    # legacy DELL member is normalized above so runtime re-validation is
    # idempotent and cannot invalidate the digest-bound summary set.
    validate_supplement_vertical_summary_set(summary_set)
    summary_path = _resolve(args.summary_output)
    _write_json(summary_path, summary_set)

    current_paths: tuple[Path | None, Path | None, Path | None] = (None, None, None)
    if args.promote_current_product:
        _require(
            summary_set["decision"]["all_case_successors_authorized"] is True,
            "vs4_case_current_product_promotion_not_authorized",
        )
        replacements = {
            key: (packs[key], pack_paths[key], results[key])
            for key in sorted(results)
        }
        composed = _compose_current_surfaces(
            current_result=current_result,
            anchor_payload=_read_json(paths["current_anchor_catalog"]),
            workspace=_read_json(paths["current_workspace_catalog"]),
            replacements=replacements,
            output_root=output_root,
        )
        current_paths = (
            _resolve(args.current_result_output),
            _resolve(args.current_anchor_output),
            _resolve(args.current_workspace_output),
        )
        for path, value in zip(current_paths, composed, strict=True):
            _write_json(path, value)
    if args.update_runtime_registry:
        _require(all(path is not None for path in current_paths), "vs4_case_registry_without_promotion")
        _update_registry(
            summary_path=summary_path,
            result_path=current_paths[0],
            anchor_path=current_paths[1],
            workspace_path=current_paths[2],
        )
    print(
        json.dumps(
            {
                key: {
                    "coverage_delta": results[key]["coverage_delta"],
                    "gate_results": results[key]["gate_results"],
                    "decision": results[key]["decision"],
                }
                for key in sorted(results)
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
