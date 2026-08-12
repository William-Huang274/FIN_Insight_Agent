from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from sec_agent.runtime_resource_registry import (
    RuntimeResourceRegistryError,
    load_runtime_resource_registry,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "configs"
    / "runtime"
    / "fin_ia_0_1_3_clean_baseline_runtime_resource_registry_v1_0.json"
)


def test_current_registry_is_exactly_the_current_product_resources() -> None:
    registry = load_runtime_resource_registry(ROOT)

    assert registry.registry_id == (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R8"
    )
    assert [row.repo_relative_path for row in registry.resources] == [
        "configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json",
        "configs/retrieval/fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_0.json",
        "configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_current_research_evidence_pack_projection_v1_0.json",
        "configs/research/fin_ia_0_1_3_s3_research_planning_policy_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_0.json",
        "configs/runtime/fin_ia_current_research_evidence_pack_result_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json",
        "configs/runtime/fin_ia_0_1_3_s1c_ranking_workbench_projection_v1_0.json",
    ]
    assert all("archive/" not in row.repo_relative_path for row in registry.resources)


def test_current_registry_fails_closed_on_digest_mutation(tmp_path: Path) -> None:
    fixture_root = _copy_registry_fixture(tmp_path)
    fixture_registry = fixture_root / REGISTRY.relative_to(ROOT)
    payload = json.loads(fixture_registry.read_text(encoding="utf-8"))
    payload["resources"][0]["sha256"] = "0" * 64
    fixture_registry.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeResourceRegistryError):
        load_runtime_resource_registry(fixture_root)


def test_current_registry_fails_closed_on_unregistered_resource(tmp_path: Path) -> None:
    fixture_root = _copy_registry_fixture(tmp_path)
    fixture_registry = fixture_root / REGISTRY.relative_to(ROOT)
    payload = json.loads(fixture_registry.read_text(encoding="utf-8"))
    payload["resources"].append(dict(payload["resources"][0]))
    payload["resource_count"] += 1
    fixture_registry.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(RuntimeResourceRegistryError):
        load_runtime_resource_registry(fixture_root)


def _copy_registry_fixture(tmp_path: Path) -> Path:
    fixture_root = tmp_path / "repo"
    paths = [
        REGISTRY.relative_to(ROOT),
        Path("apps/workbench/backend/application/research_evidence_pack_service.py"),
        Path("apps/workbench/backend/application/research_workspace_service.py"),
        Path("apps/workbench/backend/application/research_retrieval_service.py"),
        Path("configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json"),
        Path("configs/retrieval/fin_ia_0_1_3_s1c_hybrid_candidate_runtime_policy_v1_0.json"),
        Path("configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json"),
        Path("configs/runtime/fin_ia_0_1_3_current_research_evidence_pack_projection_v1_0.json"),
        Path("configs/research/fin_ia_0_1_3_s3_research_planning_policy_v1_0.json"),
        Path("configs/runtime/fin_ia_0_1_3_research_workspace_catalog_v1_0.json"),
        Path("configs/runtime/fin_ia_current_research_evidence_pack_result_v1_0.json"),
        Path("configs/runtime/fin_ia_0_1_3_current_retrieval_snapshot_v1_0.json"),
        Path("configs/runtime/fin_ia_0_1_3_s1c_ranking_workbench_projection_v1_0.json"),
    ]
    for relative in paths:
        target = fixture_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    return fixture_root
