from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (
    CurrentProductPrincipal,
    CurrentProductProjectionService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_review_control import (
    CurrentProductReviewControlService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_packet import (
    CurrentProductReviewerPacketError,
    CurrentProductReviewerPacketService,
    validate_current_product_reviewer_packet_contract,
)
DEFAULT_OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t07_a_nvda_exact_reviewer_packet_"
    "contract_v1_0.json"
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.runtime_resource_registry import read_registered_runtime_json


PRINCIPAL = CurrentProductPrincipal(
    mode="current", permissions=frozenset({"current_product:read"})
)
HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Case-Permissions": "current_product:read",
}


def _services(tmp_path: Path):
    projection = CurrentProductProjectionService.from_repository(ROOT)
    review = CurrentProductReviewControlService.from_repository(
        ROOT, projection, tmp_path / "review.sqlite"
    )
    packet = CurrentProductReviewerPacketService.from_repository(
        ROOT, projection, review
    )
    return projection, review, packet


def test_contract_is_registered_self_consistent_and_records_option_a() -> None:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    registered = read_registered_runtime_json(
        ROOT,
        "fin_0_1_2.s4.t07_a.nvda_reviewer_packet_contract",
        registry_ref=(
            "configs/runtime/fin_ia_0_1_2_s4_t07_a_nvda_reviewer_packet_"
            "runtime_resource_registry_v1_0.json"
        ),
    )
    assert registered == stored
    assert canonical_digest(
        {key: value for key, value in stored.items() if key != "contract_digest"}
    ) == stored["contract_digest"]
    assert ".codex_runtime" not in json.dumps(stored, ensure_ascii=False)
    assert stored["authority"]["user_security_scope_choice"] == "A"
    assert stored["authority"]["T07_C_human_action_authorized_for_automation"] is False


def test_packet_exposes_exact_review_material_and_missing_lead_content(
    tmp_path: Path,
) -> None:
    _, _, service = _services(tmp_path)
    packet = service.get_packet("NVDA", PRINCIPAL)
    assert packet["status"] == "ready_for_authenticated_qualified_human_review"
    assert packet["packet_digest"] == canonical_digest(
        {key: value for key, value in packet.items() if key != "packet_digest"}
    )
    assert packet["review_burden"] == {
        "evidence_rows": 15,
        "numeric_rows": 3,
        "research_cells": 3,
        "claims": 6,
        "what_would_change_items": 9,
        "typed_product_gaps": 3,
        "cross_cell_dependencies": 1,
        "unresolved_conflicts": 2,
        "lead_remaining_gaps": 4,
        "checklist_items": 5,
        "measured_human_review_duration_seconds": None,
    }
    lead = packet["sections"]["cross_cell_lead"]
    assert len(lead["cross_cell_dependencies"]) == 1
    assert len(lead["conflict_adjudications"]) == 2
    assert len(lead["remaining_gaps"]) == 4
    assert all(row["review_status"] == "pending_human_review" for row in packet["review_checklist"])
    assert packet["decision_boundary"] == {
        "authenticated_reviewer_session_required": True,
        "authenticated_reviewer_session_established": False,
        "qualified_human_review_executed": False,
        "review_decision": None,
        "NVDA_R3": False,
    }


def test_packet_is_nvda_only_read_only_and_blocks_open_return_request(
    tmp_path: Path,
) -> None:
    projection, review, service = _services(tmp_path)
    with pytest.raises(CurrentProductReviewerPacketError, match="only_available"):
        service.get_packet("DELL", PRINCIPAL)
    with pytest.raises(CurrentProductReviewerPacketError, match="read_permission"):
        service.get_packet(
            "NVDA", CurrentProductPrincipal(mode="current", permissions=frozenset())
        )
    # The existing review-control suite proves append/replay. Here we inject a
    # fail-closed handoff to prove the packet cannot conceal an open repair.
    original = review.get_state
    def blocked(case_key, principal):
        state = original(case_key, principal)
        state["T07_handoff"]["status"] = "blocked_open_return_requests"
        state["T07_handoff"]["open_return_request_ids"] = ["return-1"]
        return state
    review.get_state = blocked  # type: ignore[method-assign]
    with pytest.raises(CurrentProductReviewerPacketError, match="handoff_not_ready"):
        service.get_packet("NVDA", PRINCIPAL)
    assert projection.manifest_digest


def test_contract_mutation_and_secret_surface_fail_closed() -> None:
    contract = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    mutated = deepcopy(contract)
    mutated["safe_cross_cell_lead"]["provider_output"] = "forbidden"
    mutated["exact_binding"]["cross_cell_lead_digest"] = canonical_digest(
        mutated["safe_cross_cell_lead"]
    )
    mutated["contract_digest"] = canonical_digest(
        {key: value for key, value in mutated.items() if key != "contract_digest"}
    )
    with pytest.raises(Exception, match="forbidden_reviewer_surface"):
        validate_current_product_reviewer_packet_contract(mutated)


def test_api_returns_packet_without_creating_human_acceptance(tmp_path: Path) -> None:
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=CaseService.unavailable("fixture_not_in_T07_A"),
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/current-product/cases/NVDA/reviewer-packet",
            headers=HEADERS,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert response.headers["etag"] == f'"review-packet={body["packet_digest"]}"'
        assert body["decision_boundary"]["qualified_human_review_executed"] is False
        assert client.get(
            "/api/v1/current-product/cases/DELL/reviewer-packet",
            headers=HEADERS,
        ).status_code == 404
