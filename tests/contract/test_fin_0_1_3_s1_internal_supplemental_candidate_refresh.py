from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.s1_internal_supplemental_assets import (  # noqa: E402
    load_internal_supplemental_candidate_refresh_policy,
    load_validated_supplemental_asset_manifest,
)


POLICY_PATH = ROOT / (
    "configs/runtime/fin_ia_0_1_3_s1_internal_"
    "supplemental_candidate_refresh_policy_v1_0.json"
)


def test_refresh_policy_binds_base_manifest_and_forbids_ranking() -> None:
    policy = load_internal_supplemental_candidate_refresh_policy(
        POLICY_PATH, repo_root=ROOT
    )
    assert len(policy["federated_asset_members"]["internal_bm25"]) == 2
    assert len(policy["federated_asset_members"]["internal_object_bm25"]) == 2
    assert policy["hard_boundaries"]["cross_asset_raw_score_comparison"] is False
    assert policy["hard_boundaries"]["BGE_fusion_rerank_admitted"] is False


def test_manifest_revalidates_all_private_files_without_promoting_evidence() -> None:
    policy = load_internal_supplemental_candidate_refresh_policy(
        POLICY_PATH, repo_root=ROOT
    )
    manifest = load_validated_supplemental_asset_manifest(
        ROOT / policy["immutable_inputs"]["supplemental_asset_manifest_ref"],
        repo_root=ROOT,
    )
    assert manifest["record_counts"]["source_documents"] == 3
    assert manifest["record_counts"]["bm25_records"] == 292
    assert manifest["observed_calls"]["embedding"] == 0
    assert manifest["stage_boundary"]["candidate_ceiling_proven"] is False
