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
    compose_current_pack,
    validate_authority,
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
