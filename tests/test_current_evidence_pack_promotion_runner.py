from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.data_retrieval.run_current_evidence_pack_promotion import (  # noqa: E402
    CurrentEvidencePackPromotionError,
    _compose_anchor_catalog,
    _compose_runtime_registry,
    compose_current_pack,
    compose_current_pack_set,
    validate_authority,
    validate_pack_set_authority,
)
from sec_agent.research.reviewed_evidence_anchor import (  # noqa: E402
    compile_reviewed_evidence_anchor_catalog,
    load_reviewed_evidence_anchor_catalog,
)
from sec_agent.research.reviewed_evidence_pack import (  # noqa: E402
    REVIEWED_EVIDENCE_PACK_CONTRACT,
    REVIEWED_EVIDENCE_PACK_SCHEMA,
    canonical_digest,
)


RUNNER_REF = (
    "scripts/data_retrieval/run_current_evidence_pack_promotion.py"
)
PRIVATE_ROOT = "fin_0_1_3_s1d_dell_official_pdf_successor/zero-call-r1"
PACK_KEY = "objects/current/dell.json"


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _successor_pack() -> dict[str, Any]:
    source_text = "Dell management reported demand, backlog and margin evidence."
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    body = {
        "schema_version": REVIEWED_EVIDENCE_PACK_SCHEMA,
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "status": "local_evidence_pack_ready_with_declared_residual_gaps",
        "case_key": "DELL",
        "candidate_manifest_digest": "a" * 64,
        "retrieval_result_digest": "b" * 64,
        "generalization_contract_digest": "c" * 64,
        "content_gate_basis": "reviewed_local_source",
        "evidence_items": [
            {
                "case_key": "DELL",
                "target_id": "dell-target-current",
                "source_record_id": "dell-source-current",
                "source_material_ref": "dell-source-material-current",
                "source_content_digest": source_digest,
                "object_type": "source_segment",
                "disposition": "accepted_direct_source_evidence",
                "evidence_role": "issuer_direct_source",
                "publication_date": "2026-05-28",
                "source_reporting_period_end": "2026-05-01",
                "research_as_of": "2026-08-06",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [
                    {
                        "slot_id": "demand_volume_quality",
                        "facet_ids": ["ai_backlog"],
                        "qualification_id": "dell-demand-current",
                        "business_meaning_zh": "AI 订单与积压可核查。",
                        "claim_boundary_zh": "不证明取消率或积压转化速度。",
                    }
                ],
                "numeric_use_boundary": "Narrative evidence only.",
                "causal_attribution_authorized": False,
                "writer_citable": True,
                "evidence_item_digest": "d" * 64,
            }
        ],
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": "dell-gap-pull-forward",
                "gap_code": "commercial_data_gap",
                "slot_id": "demand_volume_quality",
                "facet_id": "pull_forward_or_digestion",
                "attempted_lane_ids": ["issuer_disclosure"],
                "business_reason_zh": "没有量化提前采购与后续消化。",
                "supplement_direction_zh": "继续追踪客户与渠道证据。",
            }
        ],
        "source_materials": [
            {
                "material_ref": "dell-source-material-current",
                "source_record_id": "dell-source-current",
                "evidence_owner_ticker": "DELL",
                "source_tier": "official_hosted_management_call_transcript",
                "source_type": "earnings_call_transcript",
                "source_url": "https://investors.delltechnologies.com/current",
                "publication_date": "2026-05-28",
                "period_end": "2026-05-01",
                "license_scope": "private_research_use",
                "redistributable": False,
                "source_text": source_text,
                "source_text_digest": source_digest,
            }
        ],
        "observed_counts": {
            "accepted_evidence_items": 1,
            "direct_evidence_items": 1,
            "bounded_context_items": 0,
            "rejected_items": 0,
            "residual_gaps": 1,
            "source_materials": 1,
        },
        "consumer_contract": {
            "writer_may_consume_only_writer_citable_items": True,
            "context_items_must_preserve_claim_boundary": True,
            "rejected_items_must_not_enter_prompt": True,
            "residual_gaps_must_remain_visible": True,
            "exact_numeric_surface_must_be_source_visible_or_typed": True,
            "derived_numeric_claim_requires_deterministic_program": True,
            "model_may_not_change_identity_period_currency_unit_or_relationship_direction": True,
        },
        "known_boundary": "Fixture successor only.",
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def _fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    repo = tmp_path / "repo"
    pack = _successor_pack()
    pack_ref = f"data/workbench_private/{PRIVATE_ROOT}/{PACK_KEY}"
    pack_path = repo / pack_ref
    _write_json(pack_path, pack)

    predecessor_body = {
        "schema_version": "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0",
        "contract_ref": REVIEWED_EVIDENCE_PACK_CONTRACT,
        "run_scope": "fixture",
        "recorded_at": "2026-08-10",
        "attempt_id": "fixture-predecessor",
        "status": "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps",
        "materialization_order": ["DELL", "MU", "NVDA", "ORCL", "ASML", "ANET"],
        "candidate_manifest_digest": "a" * 64,
        "retrieval_result_digest": "b" * 64,
        "pack_payload_digests": {
            key: hashlib.sha256(key.encode()).hexdigest()
            for key in ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
        },
        "case_summaries": [
            {
                "case_key": key,
                "status": "local_evidence_pack_ready_with_declared_residual_gaps",
                "accepted_evidence_items": 2,
                "direct_evidence_items": 2,
                "bounded_context_items": 0,
                "rejected_items": 0,
                "residual_gaps": 2,
                "source_materials": 2,
            }
            for key in ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
        ],
        "observed_counts": {
            "evidence_items": 12,
            "rejected_items": 0,
            "residual_gaps": 12,
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
        },
        "stage_acceptance": {"complete_investment_report_claimed": False},
        "known_boundary": "fixture predecessor",
        "pack_artifacts": {
            key: {
                "object_key": f"{key.lower()}.json",
                "digest": hashlib.sha256(key.encode()).hexdigest(),
                "byte_size": 1,
                "media_type": "application/json",
                "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
            }
            for key in ("DELL", "MU", "NVDA", "ORCL", "ASML", "ANET")
        },
    }
    predecessor = {
        **predecessor_body,
        "result_digest": canonical_digest(predecessor_body),
    }
    predecessor_ref = "configs/runtime/predecessor.json"
    _write_json(repo / predecessor_ref, predecessor)

    workspace = {
        "schema_version": "fin_ia_research_workspace_catalog_v1_0",
        "evidence_pack_result_digest": predecessor["result_digest"],
        "cases": [
            {
                "case_key": key,
                "evidence_pack_binding": {
                    "pack_case_key": key,
                    "pack_artifact_digest": predecessor["pack_artifacts"][key]["digest"],
                    "pack_payload_digest": predecessor["pack_payload_digests"][key],
                },
            }
            for key in ("DELL", "MU", "NVDA")
        ],
    }
    workspace_ref = "configs/runtime/workspace.json"
    _write_json(repo / workspace_ref, workspace)

    successor_body = {
        "schema_version": "fin_ia_s1d_official_pdf_successor_result_v1_0",
        "status": "dell_official_pdf_successor_candidate_ready_current_pointer_unchanged",
        "successor_pack": {
            "private_object_key": PACK_KEY,
            "artifact_sha256": _sha(pack_path),
            "pack_payload_digest": pack["pack_payload_digest"],
        },
        "remaining_boundaries": {
            "core_research_ready": True,
            "S1_product_acceptance": False,
        },
    }
    successor = {
        **successor_body,
        "result_digest": canonical_digest(successor_body),
    }
    successor_ref = "configs/retrieval/successor_result.json"
    _write_json(repo / successor_ref, successor)
    proof_ref = "configs/retrieval/proof.json"
    _write_json(
        repo / proof_ref,
        {
            "schema_version": (
                "fin_ia_current_evidence_pack_promotion_zero_call_proof_v1_0"
            ),
            "status": "pass",
            "current_pointer_mutated": False,
            "private_object_copy_performed": False,
            "model_calls": 0,
            "network_calls": 0,
            "mutation_results": [
                "successor_digest_drift_rejected",
                "budget_expansion_rejected",
                "private_root_escape_rejected",
                "retained_case_partition_drift_rejected",
            ],
        },
    )
    runner_path = repo / RUNNER_REF
    runner_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / RUNNER_REF, runner_path)
    registry_ref = "configs/runtime/registry.json"
    registry = {
        "schema_version": "fin_ia_0_1_3_runtime_resource_registry_v1_0",
        "registry_id": "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R10",
        "status": "tracked_typed_runtime_resource_authority",
        "policy": {},
        "detector_python_refs": [],
        "resource_count": 2,
        "resource_bytes": 2,
        "resource_canonical_digest": "0" * 64,
        "resources": [
            {
                "resource_id": "application.config.current_research_workspace_catalog",
                "repo_relative_path": workspace_ref,
                "sha256": _sha(repo / workspace_ref),
                "bytes": (repo / workspace_ref).stat().st_size,
                "classification": "application_runtime_config",
                "consumer_ids": ["fixture"],
                "load_phase": "fixture",
                "required": True,
                "source_owner": "fixture",
            },
            {
                "resource_id": "application.result.current_research_local_evidence_packs",
                "repo_relative_path": predecessor_ref,
                "sha256": _sha(repo / predecessor_ref),
                "bytes": (repo / predecessor_ref).stat().st_size,
                "classification": "digest_bound_read_only_product_result",
                "consumer_ids": ["fixture"],
                "load_phase": "fixture",
                "required": True,
                "source_owner": "fixture",
            },
        ],
    }
    _write_json(repo / registry_ref, registry)

    authority = {
        "schema_version": "fin_ia_current_evidence_pack_promotion_authority_v1_0",
        "authority_id": "fixture-current-pack-promotion-r1",
        "recorded_at": "2026-08-13",
        "status": "fresh_zero_call_current_pack_promotion_authorized",
        "clean_implementation": {
            "branch": "codex/test",
            "git_commit": "a" * 40,
            "working_tree_required_clean_before_execution": True,
            "pushed_head_required": True,
        },
        "bound_inputs": {
            "predecessor_result_ref": predecessor_ref,
            "predecessor_result_sha256": _sha(repo / predecessor_ref),
            "predecessor_workspace_ref": workspace_ref,
            "predecessor_workspace_sha256": _sha(repo / workspace_ref),
            "successor_result_ref": successor_ref,
            "successor_result_sha256": _sha(repo / successor_ref),
            "successor_pack_ref": pack_ref,
            "successor_pack_sha256": _sha(pack_path),
            "zero_call_proof_ref": proof_ref,
            "zero_call_proof_sha256": _sha(repo / proof_ref),
            "runner_ref": RUNNER_REF,
            "runner_sha256": _sha(runner_path),
            "runtime_registry_ref": registry_ref,
            "runtime_registry_sha256": _sha(repo / registry_ref),
        },
        "replacement_contract": {
            "case_key": "DELL",
            "retained_case_keys": ["MU", "NVDA", "ORCL", "ASML", "ANET"],
            "private_object_root_relative": PRIVATE_ROOT,
        },
        "execution_budget": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "current_pointer_mutation": "replace_registered_result_and_workspace_once",
            "private_object_copy": "forbidden",
            "raw_source_publication": "forbidden",
        },
        "output_contract": {
            "result_id": "fixture-result",
            "composed_result_ref": "configs/runtime/composed.json",
            "composed_workspace_ref": "configs/runtime/workspace-composed.json",
            "public_execution_result_ref": "configs/retrieval/execution.json",
            "runtime_registry_ref": registry_ref,
            "runtime_registry_id": "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R11",
        },
    }
    authority_ref = repo / "configs/retrieval/authority.json"
    _write_json(authority_ref, authority)
    return repo, authority_ref, authority


def test_current_pack_composition_replaces_only_dell(tmp_path: Path) -> None:
    repo, authority_path, authority = _fixture(tmp_path)
    validated = validate_authority(authority, repository_root=repo)

    result, workspace, execution = compose_current_pack(
        validated,
        authority_path=authority_path,
        repository_root=repo,
    )

    assert result["schema_version"] == "fin_ia_current_research_evidence_pack_result_v1_1"
    assert result["case_summaries"][0]["accepted_evidence_items"] == 1
    assert result["case_summaries"][1]["accepted_evidence_items"] == 2
    assert result["pack_artifacts"]["DELL"]["private_object_root_relative"] == PRIVATE_ROOT
    assert "private_object_root_relative" not in result["pack_artifacts"]["MU"]
    assert workspace["cases"][0]["evidence_pack_binding"]["pack_payload_digest"] == result["pack_payload_digests"]["DELL"]
    assert execution["before_after"] == {
        "evidence_items": [2, 1],
        "residual_gaps": [2, 1],
    }
    assert execution["execution"]["private_object_copy_performed"] is False

    registry = _compose_runtime_registry(
        json.loads((repo / authority["bound_inputs"]["runtime_registry_ref"]).read_text(encoding="utf-8")),
        repository_root=repo,
        result_ref=authority["output_contract"]["composed_result_ref"],
        result_payload=result,
        workspace_ref=authority["output_contract"]["composed_workspace_ref"],
        workspace_payload=workspace,
        registry_id=authority["output_contract"]["runtime_registry_id"],
    )
    assert registry["registry_id"].endswith("R11")
    assert registry["resource_count"] == 2
    assert registry["resource_canonical_digest"] == canonical_digest(
        registry["resources"]
    )


@pytest.mark.parametrize("mutation", ["digest", "budget", "root", "retained"])
def test_current_pack_promotion_authority_mutations_fail_closed(
    tmp_path: Path, mutation: str
) -> None:
    repo, _, authority = _fixture(tmp_path)
    mutated = deepcopy(authority)
    if mutation == "digest":
        mutated["bound_inputs"]["successor_pack_sha256"] = "0" * 64
    elif mutation == "budget":
        mutated["execution_budget"]["model_calls"] = 1
    elif mutation == "root":
        mutated["replacement_contract"]["private_object_root_relative"] = "../private"
    else:
        mutated["replacement_contract"]["retained_case_keys"] = ["MU"]

    with pytest.raises(CurrentEvidencePackPromotionError):
        validate_authority(mutated, repository_root=repo)


def _pack_for_case(case_key: str) -> dict[str, Any]:
    pack = deepcopy(_successor_pack())
    source_text = f"{case_key} management reported current demand and supply evidence."
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    pack["case_key"] = case_key
    item = pack["evidence_items"][0]
    item.update(
        {
            "case_key": case_key,
            "target_id": f"{case_key}-target-current",
            "source_record_id": f"{case_key}-source-current",
            "source_material_ref": f"{case_key}-material-current",
            "source_content_digest": source_digest,
            "object_type": "claim",
            "evidence_item_digest": hashlib.sha256(
                f"{case_key}-evidence".encode()
            ).hexdigest(),
        }
    )
    pack["source_materials"][0].update(
        {
            "material_ref": f"{case_key}-material-current",
            "source_record_id": f"{case_key}-source-current",
            "evidence_owner_ticker": case_key,
            "source_text": source_text,
            "source_text_digest": source_digest,
        }
    )
    pack["residual_gaps"][0]["gap_id"] = f"{case_key}-gap-current"
    pack.pop("pack_payload_digest")
    pack["pack_payload_digest"] = canonical_digest(pack)
    return pack


def _pack_set_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, Any]]:
    repo, _legacy_authority_path, legacy = _fixture(tmp_path)
    predecessor_result_ref = legacy["bound_inputs"]["predecessor_result_ref"]
    predecessor_workspace_ref = legacy["bound_inputs"]["predecessor_workspace_ref"]

    anchor = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings={
            key: {
                "artifact_digest": hashlib.sha256(f"{key}-a".encode()).hexdigest(),
                "pack_payload_digest": hashlib.sha256(
                    f"{key}-p".encode()
                ).hexdigest(),
            }
            for key in ("DELL", "MU", "NVDA")
        },
        entries=[
            {
                "case_key": "DELL",
                "target_id": "old-target",
                "source_record_id": "old-source",
                "evidence_item_digest": "1" * 64,
                "source_text_digest": "2" * 64,
                "anchor_kind": "structured_claim_text",
                "anchor_text": "Old reviewed source surface for the DELL fixture.",
                "anchor_start": 0,
                "anchor_end": 49,
                "anchor_digest": hashlib.sha256(
                    "Old reviewed source surface for the DELL fixture.".encode()
                ).hexdigest(),
                "review_status": "reviewed_exact_source_surface",
            }
        ],
        known_boundary="fixture",
    )
    anchor_ref = "configs/runtime/anchor.json"
    _write_json(repo / anchor_ref, anchor)

    policy = {
        "schema_version": "fin_ia_s1_current_runtime_binding_policy_v1_2",
        "status": "current_product_binding_policy",
        "policy_id": "fixture-policy-old",
        "assets": {
            "current_evidence_pack_result": {"ref": predecessor_result_ref},
            "current_reviewed_anchor_catalog": {"ref": anchor_ref},
            "dell_product_readiness": {"ref": "old-dell.json"},
            "mu_product_readiness": {"ref": "old-mu.json"},
            "nvda_product_readiness": {"ref": "old-nvda.json"},
        },
    }
    policy_ref = "configs/retrieval/binding-policy.json"
    _write_json(repo / policy_ref, policy)

    replacements: list[dict[str, Any]] = []
    for case_key in ("DELL", "MU", "NVDA"):
        pack = _pack_for_case(case_key)
        pack_ref = f"data/workbench_private/successors/{case_key.lower()}/pack.json"
        _write_json(repo / pack_ref, pack)
        predecessor = json.loads(
            (repo / predecessor_result_ref).read_text(encoding="utf-8")
        )["pack_payload_digests"][case_key]
        successor_body = {
            "schema_version": (
                "fin_ia_s1_product_evidence_successor_public_result_v1_2"
            ),
            "status": "proposition_bound_evidence_successor_materialized",
            "case_key": case_key,
            "predecessor_pack_payload_digest": predecessor,
            "successor_pack_payload_digest": pack["pack_payload_digest"],
            "private_pack_ref": pack_ref,
            "private_pack_sha256": _sha(repo / pack_ref),
            "authority": {
                "accepted_claims_capture_bound": True,
                "accepted_evidence_proposition_bound": True,
                "candidate_is_not_evidence": True,
                "generation_model_calls": 0,
                "network_calls": 0,
                "metric_row_promoted_as_narrative_evidence": False,
                "numeric_fact_authority": False,
                "qualified_human_review": False,
                "S1_qualification_claimed": False,
                "product_publication": False,
            },
        }
        successor = {
            **successor_body,
            "result_digest": canonical_digest(successor_body),
        }
        successor_ref = f"configs/retrieval/{case_key.lower()}-successor.json"
        _write_json(repo / successor_ref, successor)

        readiness_full_ref = f"data/workbench_private/{case_key.lower()}-full.json"
        _write_json(repo / readiness_full_ref, {"case_key": case_key})
        readiness_body = {
            "schema_version": "fin_ia_s1_current_product_readiness_result_v1_1",
            "status": "current_product_pack_readiness_materialized",
            "case_key": case_key,
            "readiness_state": "blocked_by_evidence_admission",
            "full_result_ref": readiness_full_ref,
            "full_result_sha256": _sha(repo / readiness_full_ref),
            "authority": {
                "candidate_is_not_evidence": True,
                "public_information_gap_authority": False,
                "S1_qualification_claimed": False,
            },
        }
        readiness = {
            **readiness_body,
            "result_digest": canonical_digest(readiness_body),
        }
        readiness_ref = f"configs/retrieval/{case_key.lower()}-readiness.json"
        _write_json(repo / readiness_ref, readiness)
        replacements.append(
            {
                "case_key": case_key,
                "successor_result_chain": [
                    {
                        "result_ref": successor_ref,
                        "result_sha256": _sha(repo / successor_ref),
                    }
                ],
                "readiness_result_ref": readiness_ref,
                "readiness_result_sha256": _sha(repo / readiness_ref),
            }
        )

    proof_ref = "configs/retrieval/pack-set-proof.json"
    _write_json(
        repo / proof_ref,
        {
            "schema_version": (
                "fin_ia_current_evidence_pack_set_promotion_zero_call_proof_v2_0"
            ),
            "status": "pass",
            "current_pointer_mutated": False,
            "private_object_copy_performed": False,
            "model_calls": 0,
            "network_calls": 0,
            "mutation_results": [
                "successor_chain_drift_rejected",
                "readiness_digest_drift_rejected",
                "retained_case_partition_drift_rejected",
                "long_claim_without_reviewed_anchor_rejected",
                "budget_expansion_rejected",
            ],
        },
    )
    registry_ref = legacy["bound_inputs"]["runtime_registry_ref"]
    registry = json.loads((repo / registry_ref).read_text(encoding="utf-8"))
    registry["registry_id"] = (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R25"
    )
    _write_json(repo / registry_ref, registry)
    authority = {
        "schema_version": (
            "fin_ia_current_evidence_pack_set_promotion_authority_v2_0"
        ),
        "authority_id": "fixture-current-pack-set-r1",
        "recorded_at": "2026-08-19",
        "status": "fresh_zero_call_current_pack_set_promotion_authorized",
        "clean_implementation": {
            "branch": "codex/test",
            "git_commit": "a" * 40,
            "working_tree_required_clean_before_execution": True,
            "pushed_head_required": True,
        },
        "predecessor_contract": {
            "current_result_ref": predecessor_result_ref,
            "current_result_sha256": _sha(repo / predecessor_result_ref),
            "current_workspace_ref": predecessor_workspace_ref,
            "current_workspace_sha256": _sha(repo / predecessor_workspace_ref),
            "current_anchor_catalog_ref": anchor_ref,
            "current_anchor_catalog_sha256": _sha(repo / anchor_ref),
            "current_binding_policy_ref": policy_ref,
            "current_binding_policy_sha256": _sha(repo / policy_ref),
            "runtime_registry_ref": registry_ref,
            "runtime_registry_sha256": _sha(repo / registry_ref),
            "zero_call_proof_ref": proof_ref,
            "zero_call_proof_sha256": _sha(repo / proof_ref),
            "runner_ref": RUNNER_REF,
            "runner_sha256": _sha(repo / RUNNER_REF),
        },
        "replacement_chains": replacements,
        "retained_case_keys": ["ORCL", "ASML", "ANET"],
        "execution_budget": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
            "retries": 0,
            "current_pointer_mutation": (
                "replace_registered_pack_anchor_workspace_readiness_and_binding_once"
            ),
            "private_object_copy": "forbidden",
            "raw_source_publication": "forbidden",
        },
        "output_contract": {
            "result_id": "fixture-pack-set-result",
            "composed_result_ref": "configs/runtime/current-pack-v2.json",
            "composed_workspace_ref": "configs/runtime/workspace-v2.json",
            "composed_anchor_catalog_ref": "configs/runtime/anchor-v2.json",
            "binding_policy_ref": "configs/retrieval/binding-policy-v2.json",
            "binding_receipt_ref": "configs/runtime/binding-receipt-v2.json",
            "public_execution_result_ref": "configs/retrieval/promotion-v2.json",
            "runtime_registry_ref": registry_ref,
            "runtime_registry_id": (
                "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R26"
            ),
            "binding_policy_id": "fixture-policy-v2",
        },
    }
    authority_path = repo / "configs/retrieval/pack-set-authority.json"
    _write_json(authority_path, authority)
    return repo, authority_path, authority


def test_current_pack_set_composes_three_cases_and_exact_anchors(
    tmp_path: Path,
) -> None:
    repo, authority_path, authority = _pack_set_fixture(tmp_path)
    validated = validate_pack_set_authority(authority, repository_root=repo)

    result, workspace, anchors, policy, execution = compose_current_pack_set(
        validated,
        authority_path=authority_path,
        repository_root=repo,
    )

    assert [row["accepted_evidence_items"] for row in result["case_summaries"][:3]] == [1, 1, 1]
    assert result["stage_acceptance"][
        "three_case_proposition_bound_evidence_successors_promoted"
    ] is True
    assert result["stage_acceptance"]["s1_product_acceptance"] is False
    assert len({row["evidence_pack_binding"]["pack_payload_digest"] for row in workspace["cases"]}) == 3
    loaded = load_reviewed_evidence_anchor_catalog(anchors)
    assert {row["case_key"] for row in loaded.entries} == {"DELL", "MU", "NVDA"}
    assert policy["policy_id"] == "fixture-policy-v2"
    assert policy["assets"]["mu_product_readiness"]["ref"].endswith(
        "mu-readiness.json"
    )
    assert execution["remaining_boundaries"]["S1_product_acceptance"] is False


def test_current_pack_set_can_replace_one_case_without_replaying_others(
    tmp_path: Path,
) -> None:
    repo, authority_path, authority = _pack_set_fixture(tmp_path)
    predecessor = json.loads(
        (
            repo
            / authority["predecessor_contract"]["current_result_ref"]
        ).read_text(encoding="utf-8")
    )
    prior_mu = predecessor["pack_payload_digests"]["MU"]
    prior_nvda = predecessor["pack_payload_digests"]["NVDA"]
    authority["replacement_chains"] = [authority["replacement_chains"][0]]
    authority["retained_case_keys"] = ["MU", "NVDA", "ORCL", "ASML", "ANET"]

    validated = validate_pack_set_authority(authority, repository_root=repo)
    result, workspace, _anchors, policy, execution = compose_current_pack_set(
        validated,
        authority_path=authority_path,
        repository_root=repo,
    )

    assert result["pack_payload_digests"]["MU"] == prior_mu
    assert result["pack_payload_digests"]["NVDA"] == prior_nvda
    assert result["current_composition_lineage"]["replacement_case_keys"] == [
        "DELL"
    ]
    assert result["current_composition_lineage"]["promotion_kind"] == (
        "subset_proposition_bound_evidence_successor"
    )
    assert execution["status"] == "current_pack_subset_promoted"
    assert policy["assets"]["dell_product_readiness"]["ref"].endswith(
        "dell-readiness.json"
    )
    assert policy["assets"]["mu_product_readiness"]["ref"] == "old-mu.json"
    assert [row["case_key"] for row in workspace["cases"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]


def test_current_pack_set_rejects_broken_successor_chain(tmp_path: Path) -> None:
    repo, _authority_path, authority = _pack_set_fixture(tmp_path)
    mutated = deepcopy(authority)
    result_ref = mutated["replacement_chains"][0]["successor_result_chain"][0][
        "result_ref"
    ]
    successor = json.loads((repo / result_ref).read_text(encoding="utf-8"))
    body = deepcopy(successor)
    body.pop("result_digest")
    body["predecessor_pack_payload_digest"] = "0" * 64
    successor = {**body, "result_digest": canonical_digest(body)}
    _write_json(repo / result_ref, successor)
    mutated["replacement_chains"][0]["successor_result_chain"][0][
        "result_sha256"
    ] = _sha(repo / result_ref)

    with pytest.raises(
        CurrentEvidencePackPromotionError,
        match="current_pack_set_successor_link_invalid:DELL",
    ):
        validate_pack_set_authority(mutated, repository_root=repo)


def test_current_pack_set_rejects_long_claim_without_reviewed_anchor(
    tmp_path: Path,
) -> None:
    repo, _authority_path, authority = _pack_set_fixture(tmp_path)
    predecessor = authority["predecessor_contract"]
    anchor = load_reviewed_evidence_anchor_catalog(
        json.loads(
            (repo / predecessor["current_anchor_catalog_ref"]).read_text(
                encoding="utf-8"
            )
        )
    )
    pack = _pack_for_case("DELL")
    long_text = "reviewed financial evidence " * 80
    digest = hashlib.sha256(long_text.encode()).hexdigest()
    pack["source_materials"][0]["source_text"] = long_text
    pack["source_materials"][0]["source_text_digest"] = digest
    pack["evidence_items"][0]["source_content_digest"] = digest
    pack.pop("pack_payload_digest")
    pack["pack_payload_digest"] = canonical_digest(pack)
    pack_path = repo / "data/workbench_private/long/pack.json"
    _write_json(pack_path, pack)

    with pytest.raises(
        CurrentEvidencePackPromotionError,
        match="current_pack_set_explicit_anchor_required:DELL",
    ):
        _compose_anchor_catalog(
            predecessor_anchor=anchor,
            replacements={"DELL": (pack, pack_path, {}, {})},
        )


def test_current_pack_set_accepts_digest_bound_reviewed_anchor_for_long_claim(
    tmp_path: Path,
) -> None:
    repo, _authority_path, authority = _pack_set_fixture(tmp_path)
    predecessor = authority["predecessor_contract"]
    predecessor_anchor = load_reviewed_evidence_anchor_catalog(
        json.loads(
            (repo / predecessor["current_anchor_catalog_ref"]).read_text(
                encoding="utf-8"
            )
        )
    )
    pack = _pack_for_case("DELL")
    anchor_text = "reviewed financial evidence " * 10
    long_text = f"prefix surface. {anchor_text}" + ("long tail " * 180)
    source_digest = hashlib.sha256(long_text.encode()).hexdigest()
    pack["source_materials"][0]["source_text"] = long_text
    pack["source_materials"][0]["source_text_digest"] = source_digest
    pack["evidence_items"][0]["source_content_digest"] = source_digest
    pack.pop("pack_payload_digest")
    pack["pack_payload_digest"] = canonical_digest(pack)
    pack_path = repo / "data/workbench_private/long-reviewed/pack.json"
    _write_json(pack_path, pack)

    item = pack["evidence_items"][0]
    material = pack["source_materials"][0]
    start = long_text.index(anchor_text)
    retained_entries = [
        dict(row)
        for row in predecessor_anchor.entries
        if row["case_key"] != "DELL"
    ]
    successor_payload = compile_reviewed_evidence_anchor_catalog(
        case_pack_bindings={
            **dict(predecessor_anchor.case_pack_bindings),
            "DELL": {
                "artifact_digest": _sha(pack_path),
                "pack_payload_digest": pack["pack_payload_digest"],
            },
        },
        entries=[
            *retained_entries,
            {
                "case_key": "DELL",
                "target_id": item["target_id"],
                "source_record_id": item["source_record_id"],
                "evidence_item_digest": item["evidence_item_digest"],
                "source_text_digest": material["source_text_digest"],
                "anchor_kind": "reviewed_current_document_passage",
                "anchor_text": anchor_text,
                "anchor_start": start,
                "anchor_end": start + len(anchor_text),
                "anchor_digest": hashlib.sha256(anchor_text.encode()).hexdigest(),
                "review_status": "reviewed_exact_source_surface",
            },
        ],
        known_boundary="reviewed long-claim fixture",
    )
    successor_anchor = load_reviewed_evidence_anchor_catalog(successor_payload)

    composed = _compose_anchor_catalog(
        predecessor_anchor=predecessor_anchor,
        replacements={"DELL": (pack, pack_path, {}, {})},
        reviewed_anchor_successors={"DELL": successor_anchor},
    )
    loaded = load_reviewed_evidence_anchor_catalog(composed)

    dell_rows = [row for row in loaded.entries if row["case_key"] == "DELL"]
    assert len(dell_rows) == 1
    assert dell_rows[0]["anchor_text"] == anchor_text
    assert len(dell_rows[0]["anchor_text"]) < len(long_text)
