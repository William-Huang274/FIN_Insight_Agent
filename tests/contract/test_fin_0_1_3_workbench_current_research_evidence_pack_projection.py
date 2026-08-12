from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from fastapi.testclient import TestClient
import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.research_evidence_pack_service import (
    ResearchEvidencePackPrincipal,
    ResearchEvidencePackService,
    ResearchEvidencePackServiceError,
)
from apps.workbench.backend.application.research_workspace_service import (
    ResearchWorkspacePrincipal,
    ResearchWorkspaceService,
    ResearchWorkspaceServiceError,
)
from sec_agent.runtime_resource_registry import load_runtime_resource_registry
from sec_agent.research.reviewed_evidence_pack import (
    REVIEWED_EVIDENCE_PACK_CONTRACT as CONTRACT_REF,
    REVIEWED_EVIDENCE_PACK_SCHEMA as PACK_SCHEMA,
    canonical_digest,
)


HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Case-Permissions": "current_product:read",
}


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _pack(case_key: str, source_text: str) -> dict[str, Any]:
    source_digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    material_ref = f"source_material_{case_key.lower()}"
    body = {
        "schema_version": PACK_SCHEMA,
        "contract_ref": CONTRACT_REF,
        "status": "local_evidence_pack_ready_with_declared_residual_gaps",
        "case_key": case_key,
        "candidate_manifest_digest": "a" * 64,
        "retrieval_result_digest": "b" * 64,
        "generalization_contract_digest": "c" * 64,
        "content_gate_basis": "reviewed_local_source",
        "evidence_items": [
            {
                "case_key": case_key,
                "target_id": f"{case_key}-target-1",
                "source_record_id": f"{case_key}-source-1",
                "source_material_ref": material_ref,
                "source_content_digest": source_digest,
                "object_type": "source_segment",
                "disposition": "accepted_direct_source_evidence",
                "evidence_role": "issuer_direct_source",
                "publication_date": "2026-07-01",
                "source_reporting_period_end": "2026-06-30",
                "research_as_of": "2026-08-06",
                "relationship_directions": ["subject_self_disclosure"],
                "slot_bindings": [
                    {
                        "slot_id": "demand_volume_quality",
                        "facet_ids": ["order_conversion"],
                        "qualification_id": f"{case_key.lower()}-demand",
                        "business_meaning_zh": f"{case_key} 的订单与收入转换可核查。",
                        "claim_boundary_zh": "不能据此推断未来需求或客户取消率。",
                    }
                ],
                "numeric_use_boundary": (
                    "Only source-visible exact values may be quoted."
                ),
                "causal_attribution_authorized": False,
                "writer_citable": True,
                "evidence_item_digest": "d" * 64,
            }
        ],
        "rejected_items": [],
        "residual_gaps": [
            {
                "gap_id": f"{case_key.lower()}-gap-customer-cancellation",
                "gap_code": "commercial_data_gap",
                "slot_id": "demand_volume_quality",
                "facet_id": "customer_cancellation_or_pushout",
                "attempted_lane_ids": ["issuer_disclosure"],
                "business_reason_zh": "现有披露没有客户取消率或延期分布。",
                "supplement_direction_zh": "定向补充客户、渠道与管理层问答。",
            }
        ],
        "source_materials": [
            {
                "material_ref": material_ref,
                "source_record_id": f"{case_key}-source-1",
                "evidence_owner_ticker": case_key,
                "source_tier": "issuer_primary",
                "source_type": "earnings_release",
                "source_url": f"https://example.test/{case_key.lower()}",
                "publication_date": "2026-07-01",
                "period_end": "2026-06-30",
                "license_scope": "public",
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
        "known_boundary": (
            "Reviewed local Evidence Pack only; not a complete investment report."
        ),
    }
    return {**body, "pack_payload_digest": canonical_digest(body)}


def _service(tmp_path: Path) -> ResearchEvidencePackService:
    object_root = tmp_path / "objects"
    object_root.mkdir()
    artifacts: dict[str, dict[str, Any]] = {}
    payload_digests: dict[str, str] = {}
    summaries = []
    source_text = (
        "Management reported that orders converted into recognized revenue during "
        "the quarter, while cancellation and delivery-cycle distributions were not "
        "disclosed. " * 8
    )
    for case_key in ("DELL", "MU", "NVDA"):
        pack = _pack(case_key, source_text)
        raw = _canonical_bytes(pack)
        digest = hashlib.sha256(raw).hexdigest()
        object_key = f"{case_key.lower()}/{digest}.json"
        target = object_root / object_key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        artifacts[case_key] = {
            "object_key": object_key,
            "digest": digest,
            "byte_size": len(raw),
            "media_type": "application/json",
            "artifact_type": "reviewed_local_evidence_pack_with_declared_gaps",
        }
        payload_digests[case_key] = pack["pack_payload_digest"]
        summaries.append(
            {
                "case_key": case_key,
                "status": "local_evidence_pack_ready_with_declared_residual_gaps",
                "accepted_evidence_items": 1,
                "direct_evidence_items": 1,
                "bounded_context_items": 0,
                "rejected_items": 0,
                "residual_gaps": 1,
                "source_materials": 1,
            }
        )
    result_body = {
        "schema_version": (
            "fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0"
        ),
        "contract_ref": CONTRACT_REF,
        "run_scope": "test",
        "recorded_at": "2026-08-11",
        "attempt_id": "test-zero-call-r1",
        "status": (
            "terminal_succeeded_six_case_local_evidence_packs_with_declared_gaps"
        ),
        "materialization_order": ["DELL", "MU", "NVDA"],
        "candidate_manifest_digest": "a" * 64,
        "retrieval_result_digest": "b" * 64,
        "pack_payload_digests": payload_digests,
        "case_summaries": summaries,
        "observed_counts": {
            "network_calls": 0,
            "provider_calls": 0,
            "model_calls": 0,
        },
        "stage_acceptance": {
            "complete_investment_report_claimed": False,
        },
        "known_boundary": "test boundary",
        "pack_artifacts": artifacts,
    }
    result = {**result_body, "result_digest": canonical_digest(result_body)}
    config = {
        "schema_version": (
            "fin_ia_current_research_evidence_pack_projection_config_v1_0"
        ),
        "status": "active_read_only_workbench_projection",
        "source_result_resource_id": (
            "application.result.current_research_local_evidence_packs"
        ),
        "private_object_root_relative": "unused-in-direct-construction",
        "published_case_keys": ["DELL", "MU", "NVDA"],
        "read_mode": "current",
        "read_permission": "current_product:read",
        "max_reviewed_source_excerpt_chars": 200,
        "surface_policy": {
            "reviewed_source_excerpt_exposure": (
                "authenticated_internal_review_only"
            ),
            "full_source_material_exposure": False,
            "raw_capture_exposure": False,
            "rejected_item_prompt_exposure": False,
            "automatic_evidence_promotion": False,
            "automatic_financial_truth_write": False,
            "model_provider_or_live_network_calls": 0,
            "residual_gaps_remain_visible": True,
        },
        "known_boundary": "safe Workbench projection",
    }
    return ResearchEvidencePackService(
        config=config,
        result=result,
        private_object_root=object_root,
    )


def _workspace_config(
    evidence_service: ResearchEvidencePackService,
) -> dict[str, Any]:
    principal = ResearchEvidencePackPrincipal(
        "current", frozenset({"current_product:read"})
    )
    subjects = {
        "DELL": {
            "entity_id": "sec_issuer_0001571996",
            "issuer_id": "0001571996",
            "legal_name": "Dell Technologies Inc.",
            "ticker": "DELL",
            "exchange": "NYSE",
            "as_of": "2026-08-06",
            "aliases": ["Dell Technologies", "Dell"],
        },
        "MU": {
            "entity_id": "sec_issuer_0000723125",
            "issuer_id": "0000723125",
            "legal_name": "Micron Technology, Inc.",
            "ticker": "MU",
            "exchange": "NASDAQ",
            "as_of": "2026-08-06",
            "aliases": ["Micron Technology", "Micron"],
        },
        "NVDA": {
            "entity_id": "sec_issuer_0001045810",
            "issuer_id": "0001045810",
            "legal_name": "NVIDIA Corporation",
            "ticker": "NVDA",
            "exchange": "NASDAQ",
            "as_of": "2026-08-06",
            "aliases": ["NVIDIA", "Nvidia"],
        },
    }
    cases = []
    for key in ("DELL", "MU", "NVDA"):
        pack = evidence_service.get_case(key, principal)
        cases.append(
            {
                "case_id": f"case_{key.lower()}_current",
                "case_version": 1,
                "case_key": key,
                "subject": subjects[key],
                "research_context": {
                    "research_as_of": "2026-08-06",
                    "language": "zh-CN",
                    "research_question": f"{key} current research question",
                },
                "evidence_pack_binding": {
                    "pack_case_key": key,
                    "pack_artifact_digest": pack["artifact_digest"],
                    "pack_payload_digest": pack["pack_payload_digest"],
                },
            }
        )
    return {
        "schema_version": "fin_ia_research_workspace_catalog_v1_0",
        "status": "active_read_only_research_workspace",
        "product_mode": "current",
        "read_permission": "current_product:read",
        "evidence_pack_result_digest": evidence_service.result_digest,
        "cases": cases,
        "surface_policy": {
            "primary_route": "/workspace",
            "available_surfaces": ["overview", "evidence", "retrieval"],
            "mutable_case_creation": False,
            "complete_investment_report_claimed": False,
            "model_or_network_calls": 0,
            "residual_gaps_remain_visible": True,
        },
        "known_boundary": "test identity-bound reviewed evidence only",
    }


def _all_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            key
            for item in value.values()
            for key in _all_keys(item)
        }
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_default_runtime_registry_registers_current_research_projection() -> None:
    registry = load_runtime_resource_registry(ROOT)
    assert registry.registry_id == (
        "FIN-0.1.3-CURRENT-PRODUCT-RUNTIME-RESOURCE-REGISTRY-R4"
    )
    assert set(registry.by_id()) == {
        "application.config.current_financial_research_kernel",
        "application.config.current_research_evidence_pack_projection",
        "application.config.current_research_workspace_catalog",
        "application.result.current_research_local_evidence_packs",
        "application.result.current_research_retrieval_snapshot",
        "application.result.current_s1c_ranking_comparison_projection",
    }
    assert registry.detector_python_refs == (
        "apps/workbench/backend/application/research_evidence_pack_service.py",
        "apps/workbench/backend/application/research_retrieval_service.py",
        "apps/workbench/backend/application/research_workspace_service.py",
    )
    assert all(
        "fin_0_1_2" not in row.repo_relative_path
        and "p36" not in row.repo_relative_path.lower()
        and "r53_r60" not in row.repo_relative_path
        for row in registry.resources
    )
    assert (
        "apps/workbench/backend/application/research_evidence_pack_service.py"
        in registry.detector_python_refs
    )


def test_workbench_api_exposes_reviewed_content_and_gaps_without_raw_material(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    app = create_app(
        store_path=tmp_path / "workbench.sqlite3",
        current_research_evidence_pack_service=service,
        workbench_runtime_mode="fixture",
    )
    client = TestClient(app)
    route_paths = {route.path for route in app.routes}
    assert {"/next", "/next/{frontend_path:path}"}.issubset(route_paths)

    listed = client.get(
        "/api/v1/current-research/evidence-packs", headers=HEADERS
    )
    assert listed.status_code == 200
    assert [row["case_key"] for row in listed.json()["items"]] == [
        "DELL",
        "MU",
        "NVDA",
    ]
    assert listed.json()["hard_boundaries"]["model_calls"] == 0

    response = client.get(
        "/api/v1/current-research/evidence-packs/dell", headers=HEADERS
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["case_key"] == "DELL"
    assert payload["summary"]["accepted_evidence_items"] == 1
    assert payload["evidence_items"][0]["slot_bindings"][0][
        "business_meaning_zh"
    ] == "DELL 的订单与收入转换可核查。"
    assert payload["residual_gaps"][0]["business_reason_zh"] == (
        "现有披露没有客户取消率或延期分布。"
    )
    source = payload["evidence_items"][0]["source"]
    assert len(source["reviewed_source_excerpt"]) == 200
    assert source["excerpt_truncated"] is True
    assert "source_text" not in _all_keys(payload)
    assert "object_key" not in _all_keys(payload)
    assert response.headers["etag"].startswith('"research-evidence-pack=')


def test_projection_fails_closed_on_permission_case_and_artifact_drift(
    tmp_path: Path,
) -> None:
    service = _service(tmp_path)
    with pytest.raises(ResearchEvidencePackServiceError) as denied:
        service.list_cases(
            ResearchEvidencePackPrincipal("current", frozenset())
        )
    assert denied.value.status_code == 403
    with pytest.raises(ResearchEvidencePackServiceError) as missing:
        service.get_case(
            "ORCL",
            ResearchEvidencePackPrincipal(
                "current", frozenset({"current_product:read"})
            ),
        )
    assert missing.value.status_code == 404

    object_path = next((tmp_path / "objects" / "dell").glob("*.json"))
    object_path.write_bytes(object_path.read_bytes() + b" ")
    with pytest.raises(ResearchEvidencePackServiceError) as drift:
        service.get_case(
            "DELL",
            ResearchEvidencePackPrincipal(
                "current", frozenset({"current_product:read"})
            ),
        )
    assert drift.value.error_code == (
        "current_research_evidence_pack_object_identity_drift"
    )
    assert drift.value.status_code == 503


def test_primary_workspace_binds_subject_case_and_evidence_pack(
    tmp_path: Path,
) -> None:
    evidence_service = _service(tmp_path)
    workspace_service = ResearchWorkspaceService(
        config=_workspace_config(evidence_service),
        evidence_packs=evidence_service,
    )
    app = create_app(
        store_path=tmp_path / "workbench.sqlite3",
        current_research_evidence_pack_service=evidence_service,
        research_workspace_service=workspace_service,
        workbench_runtime_mode="fixture",
    )
    client = TestClient(app)

    listed = client.get("/api/v1/research-cases", headers=HEADERS)
    assert listed.status_code == 200
    assert listed.json()["primary_route"] == "/workspace"
    assert [row["subject"]["legal_name"] for row in listed.json()["items"]] == [
        "Dell Technologies Inc.",
        "Micron Technology, Inc.",
        "NVIDIA Corporation",
    ]
    assert all(
        row["pack_binding"]["binding_state"]
        == "identity_and_digest_bound"
        for row in listed.json()["items"]
    )

    detail = client.get(
        "/api/v1/research-cases/case_dell_current", headers=HEADERS
    )
    assert detail.status_code == 200
    assert detail.json()["subject"]["issuer_id"] == "0001571996"
    assert detail.json()["available_surfaces"] == [
        "overview",
        "evidence",
        "retrieval",
    ]
    assert detail.json()["evidence_pack_uri"].endswith("/evidence")

    evidence = client.get(
        "/api/v1/research-cases/case_dell_current/evidence",
        headers=HEADERS,
    )
    assert evidence.status_code == 200
    payload = evidence.json()
    assert payload["case_key"] == payload["subject"]["ticker"] == "DELL"
    assert payload["research_context"]["research_as_of"] == "2026-08-06"
    assert payload["evidence_items"][0]["source"]["evidence_owner_ticker"] == "DELL"
    assert payload["residual_gaps"]
    assert {"/workspace", "/workspace/{frontend_path:path}"}.issubset(
        {route.path for route in app.routes}
    )


def test_primary_workspace_fails_closed_on_cross_case_binding(
    tmp_path: Path,
) -> None:
    evidence_service = _service(tmp_path)
    config = _workspace_config(evidence_service)
    config["cases"][0]["evidence_pack_binding"]["pack_artifact_digest"] = (
        config["cases"][1]["evidence_pack_binding"]["pack_artifact_digest"]
    )
    config["cases"][0]["evidence_pack_binding"]["pack_payload_digest"] = (
        config["cases"][1]["evidence_pack_binding"]["pack_payload_digest"]
    )
    with pytest.raises(ResearchWorkspaceServiceError) as failure:
        ResearchWorkspaceService(
            config=config,
            evidence_packs=evidence_service,
        )
    assert failure.value.error_code == (
        "research_workspace_case_pack_binding_drift"
    )
    assert failure.value.status_code == 503


def test_primary_workspace_denies_wrong_mode_permission_and_unknown_case(
    tmp_path: Path,
) -> None:
    evidence_service = _service(tmp_path)
    service = ResearchWorkspaceService(
        config=_workspace_config(evidence_service),
        evidence_packs=evidence_service,
    )
    with pytest.raises(ResearchWorkspaceServiceError) as denied:
        service.list_cases(ResearchWorkspacePrincipal("fixture", frozenset()))
    assert denied.value.status_code == 403
    with pytest.raises(ResearchWorkspaceServiceError) as missing:
        service.get_case(
            "case_orcl_current",
            ResearchWorkspacePrincipal(
                "current", frozenset({"current_product:read"})
            ),
        )
    assert missing.value.status_code == 404
