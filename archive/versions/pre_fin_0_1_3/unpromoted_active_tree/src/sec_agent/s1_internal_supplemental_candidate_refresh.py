from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from retrieval.bm25_retriever import BM25Retriever
from retrieval.object_bm25_retriever import ObjectBM25Retriever
from sec_agent.s1_internal_candidate_ceiling import (
    canonical_observation_digest,
    execute_internal_candidate_inventory,
    load_bound_integration_proof,
    load_internal_candidate_ceiling_policy,
)
from sec_agent.s1_internal_supplemental_assets import (
    FederatedReadOnlyRetriever,
    load_validated_supplemental_asset_manifest,
)


OBSERVATION_SCHEMA = (
    "fin_ia_0_1_3_s1_internal_candidate_inventory_observation_v1_4"
)


def execute_internal_supplemental_candidate_refresh(
    *, policy: Mapping[str, Any], repo_root: str | Path
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    inputs = dict(policy["immutable_inputs"])
    base_policy = load_internal_candidate_ceiling_policy(
        root / str(inputs["base_candidate_policy_ref"]), repo_root=root
    )
    proof = load_bound_integration_proof(base_policy, repo_root=root)
    manifest_items = list(inputs.get("supplemental_asset_manifests") or [])
    if manifest_items:
        manifests = {
            str(item["asset_key"]): load_validated_supplemental_asset_manifest(
                root / str(item["ref"]), repo_root=root
            )
            for item in manifest_items
        }
    else:
        manifests = {
            "supplemental": load_validated_supplemental_asset_manifest(
                root / str(inputs["supplemental_asset_manifest_ref"]),
                repo_root=root,
            )
        }
    assets = dict(base_policy["local_assets"])
    members = dict(policy["federated_asset_members"])

    bm25_members = list(members["internal_bm25"])
    object_members = list(members["internal_object_bm25"])

    def _bm25_path(source: str) -> Path:
        if source == "base_candidate_policy.bm25_index_dir":
            return root / str(assets["bm25_index_dir"])
        parts = source.split(".")
        if len(parts) == 3 and parts[0] == "supplemental_asset_manifests":
            return root / str(manifests[parts[1]]["bm25_index_ref"])
        if source == "supplemental_asset_manifest.bm25_index_ref":
            return root / str(manifests["supplemental"]["bm25_index_ref"])
        raise ValueError(f"unsupported internal BM25 member source: {source}")

    def _object_path(source: str) -> Path:
        if source == "base_candidate_policy.object_bm25_index_dir":
            return root / str(assets["object_bm25_index_dir"])
        parts = source.split(".")
        if len(parts) == 3 and parts[0] == "supplemental_asset_manifests":
            return root / str(manifests[parts[1]]["object_bm25_index_ref"])
        if source == "supplemental_asset_manifest.object_bm25_index_ref":
            return root / str(manifests["supplemental"]["object_bm25_index_ref"])
        raise ValueError(f"unsupported internal ObjectBM25 member source: {source}")

    def bm25_factory(_unused_path: str | Path) -> FederatedReadOnlyRetriever:
        return FederatedReadOnlyRetriever(
            [
                (
                    str(item["asset_id"]),
                    BM25Retriever(_bm25_path(str(item["source"]))),
                )
                for item in bm25_members
            ]
        )

    def object_factory(_unused_path: str | Path) -> FederatedReadOnlyRetriever:
        return FederatedReadOnlyRetriever(
            [
                (
                    str(item["asset_id"]),
                    ObjectBM25Retriever(_object_path(str(item["source"]))),
                )
                for item in object_members
            ]
        )

    effective_policy = {
        **base_policy,
        "observation_schema": str(
            policy.get("observation_schema") or OBSERVATION_SCHEMA
        ),
        "contract_ref": str(policy["contract_ref"]),
    }
    result = execute_internal_candidate_inventory(
        policy=effective_policy,
        integration_proof=proof,
        repo_root=root,
        bm25_factory=bm25_factory,
        object_bm25_factory=object_factory,
    )
    body = dict(result)
    body.pop("result_digest", None)
    lineage_fields = (
        {
            "supplemental_asset_manifest_digests": {
                key: str(value["manifest_digest"])
                for key, value in manifests.items()
            },
            "source_acquisition_result_digests": {
                key: str(value["source_acquisition_result_digest"])
                for key, value in manifests.items()
            },
        }
        if manifest_items
        else {
            "supplemental_asset_manifest_digest": str(
                manifests["supplemental"]["manifest_digest"]
            ),
            "source_acquisition_result_digest": str(
                manifests["supplemental"]["source_acquisition_result_digest"]
            ),
        }
    )
    body.update(
        {
            "status": (
                "completed_supplemental_federated_candidate_inventory_"
                "qrels_pending"
            ),
            "base_candidate_policy_ref": str(
                inputs["base_candidate_policy_ref"]
            ),
            **lineage_fields,
            "federated_asset_members": members,
            "candidate_ceiling_proven": False,
            "BGE_fusion_rerank_admitted": False,
            "known_boundary": (
                "This observation round-robins immutable historical and current "
                "supplemental sparse assets without comparing raw cross-index scores. "
                "Captured document segments remain candidates, not adjudicated claims "
                "or Evidence. Qrels are loaded only after candidate generation; BGE, "
                "fusion and reranking remain blocked."
            ),
        }
    )
    qualification = dict(body["resource_qualification"])
    if manifest_items:
        qualification["supplemental_assets"] = {
            "status": "qualified",
            "members": {
                key: {
                    "manifest_digest": str(value["manifest_digest"]),
                    "record_counts": dict(value["record_counts"]),
                    "private_file_count": len(value["private_file_inventory"]),
                }
                for key, value in manifests.items()
            },
        }
    else:
        manifest = manifests["supplemental"]
        qualification["supplemental_assets"] = {
            "status": "qualified",
            "manifest_digest": str(manifest["manifest_digest"]),
            "record_counts": dict(manifest["record_counts"]),
            "private_file_count": len(manifest["private_file_inventory"]),
        }
    qualification["federation"] = {
        "status": "qualified_round_robin_no_cross_score_comparison",
        "members": members,
    }
    body["resource_qualification"] = qualification
    return {**body, "result_digest": canonical_observation_digest(body)}


__all__ = [
    "OBSERVATION_SCHEMA",
    "execute_internal_supplemental_candidate_refresh",
]
