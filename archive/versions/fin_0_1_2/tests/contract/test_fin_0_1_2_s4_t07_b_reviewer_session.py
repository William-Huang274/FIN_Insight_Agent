from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
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
    CurrentProductReviewerPacketService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t07_reviewer_session import (
    CurrentProductReviewerSessionService,
    QualifiedReviewDecisionDraft,
    ReviewerSessionError,
)
from scripts.releases.materialize_fin_ia_0_1_2_s4_t07_b_reviewer_session_contract import (
    DEFAULT_OUTPUT,
    build_contract,
    validate_contract,
)
from sec_agent.runtime_resource_registry import read_registered_runtime_json


TOKEN = "finrvw_" + "T" * 48
START = datetime(2026, 8, 5, 16, 0, 0, tzinfo=timezone.utc)


def _services(tmp_path: Path):
    now = [START]
    db_path = tmp_path / "workbench.sqlite"
    projection = CurrentProductProjectionService.from_repository(ROOT)
    control = CurrentProductReviewControlService.from_repository(
        ROOT, projection, db_path
    )
    packet = CurrentProductReviewerPacketService.from_repository(
        ROOT, projection, control
    )
    session = CurrentProductReviewerSessionService.from_repository(
        ROOT,
        packet,
        db_path,
        clock=lambda: now[0],
        credential_factory=lambda: TOKEN,
    )
    return now, db_path, projection, control, packet, session


def _issue(service: CurrentProductReviewerSessionService):
    return service.issue_session(
        admin_actor_ref="local_security_admin",
        reviewer_ref="FIN_OWNER_A",
        reviewer_role="qualified_product_owner",
        ttl_seconds=3600,
    )


def test_contract_is_reproducible_registered_and_keeps_real_action_false() -> None:
    stored = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert build_contract() == stored
    validate_contract(stored)
    assert read_registered_runtime_json(
        ROOT,
        "fin_0_1_2.s4.t07_b.reviewer_session_contract",
        registry_ref=(
            "configs/runtime/fin_ia_0_1_2_s4_t07_b_reviewer_session_"
            "runtime_resource_registry_v1_0.json"
        ),
    ) == stored
    assert stored["authority"]["selected_security_option"] == "A"
    assert stored["authority"]["real_session_issuance_executed"] is False
    assert stored["authority"]["T07_C_real_human_action_executed"] is False


def test_offline_issuance_is_allowlisted_digest_only_and_exact_bound(
    tmp_path: Path,
) -> None:
    _, db_path, _, _, _, service = _services(tmp_path)
    issued = _issue(service)
    assert issued.credential == TOKEN
    assert issued.reviewer_ref == "FIN_OWNER_A"
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT credential_digest, manifest_digest, handoff_digest, packet_digest FROM t07_reviewer_sessions"
        ).fetchall()
        all_text = "\n".join(
            str(value)
            for row in conn.execute(
                "SELECT payload_json FROM t07_reviewer_security_events"
            ).fetchall()
            for value in row
        )
    assert len(rows) == 1
    assert len(rows[0][0]) == 64
    assert all(len(value) == 64 for value in rows[0])
    assert TOKEN not in db_path.read_bytes().decode("latin-1")
    assert TOKEN not in all_text
    with pytest.raises(ReviewerSessionError, match="offline_admin_required"):
        service.issue_session(
            admin_actor_ref="browser_user",
            reviewer_ref="FIN_OWNER_A",
            reviewer_role="qualified_product_owner",
            ttl_seconds=3600,
        )


def test_authentication_rejects_unknown_expired_revoked_and_scope_drift(
    tmp_path: Path,
) -> None:
    now, db_path, _, _, _, service = _services(tmp_path)
    issued = _issue(service)
    authenticated = service.authenticate(TOKEN, expected_case_key="NVDA")
    assert authenticated.reviewer_ref == "FIN_OWNER_A"
    with pytest.raises(ReviewerSessionError, match="authentication_failed"):
        service.authenticate("finrvw_" + "X" * 48, expected_case_key="NVDA")
    with pytest.raises(ReviewerSessionError, match="authentication_failed"):
        service.authenticate(TOKEN, expected_case_key="MU")
    now[0] = START + timedelta(hours=2)
    with pytest.raises(ReviewerSessionError, match="authentication_failed"):
        service.authenticate(TOKEN, expected_case_key="NVDA")
    now[0] = START
    service.revoke_session(
        admin_actor_ref="local_security_admin", session_id=issued.session_id
    )
    with pytest.raises(ReviewerSessionError, match="authentication_failed"):
        service.authenticate(TOKEN, expected_case_key="NVDA")
    assert TOKEN not in db_path.read_bytes().decode("latin-1")


def test_accept_decision_is_authenticated_idempotent_and_bounded_r3(
    tmp_path: Path,
) -> None:
    _, _, _, _, _, service = _services(tmp_path)
    _issue(service)
    draft = QualifiedReviewDecisionDraft(
        action="accept_exact_version",
        reviewer_note="临时测试库中的合格审核接受；不代表真实产品验收。",
        idempotency_key="accept-r1",
    )
    state = service.record_decision(TOKEN, draft)
    assert state["decision"]["authenticated_reviewer_identity"] is True
    assert state["acceptance"] == {
        "authenticated_reviewer_identity": True,
        "qualified_human_review": True,
        "NVDA_R3": True,
        "release_qualified": False,
    }
    repeated = service.record_decision(TOKEN, draft)
    assert repeated["decision"]["decision_id"] == state["decision"]["decision_id"]
    with pytest.raises(ReviewerSessionError, match="terminal_decision_exists"):
        service.record_decision(
            TOKEN,
            QualifiedReviewDecisionDraft(
                action="accept_exact_version",
                reviewer_note="second terminal",
                idempotency_key="accept-r2",
            ),
        )


def test_return_requires_exact_surface_reason_and_does_not_establish_r3(
    tmp_path: Path,
) -> None:
    _, _, _, _, packet, service = _services(tmp_path)
    _issue(service)
    view_digest = packet.get_packet(
        "NVDA",
        CurrentProductPrincipal(
            mode="current", permissions=frozenset({"current_product:read"})
        ),
    )["exact_binding"]["view_digests"]["report"]
    with pytest.raises(ReviewerSessionError, match="return_scope_invalid"):
        service.record_decision(
            TOKEN,
            QualifiedReviewDecisionDraft(
                action="return_for_repair",
                reviewer_note="return",
                idempotency_key="return-bad",
            ),
        )
    state = service.record_decision(
        TOKEN,
        QualifiedReviewDecisionDraft(
            action="return_for_repair",
            reviewer_note="最终交付仍需更清晰地标注判断边界。",
            idempotency_key="return-good",
            target_surface="report",
            expected_target_view_digest=view_digest,
            reason_code="delivery_clarity",
        ),
    )
    assert state["acceptance"]["qualified_human_review"] is True
    assert state["acceptance"]["NVDA_R3"] is False


def test_api_has_no_public_issuance_and_requires_bearer(tmp_path: Path) -> None:
    _, db_path, projection, control, packet, service = _services(tmp_path)
    _issue(service)
    app = create_app(
        db_path,
        p02_case_service=CaseService.unavailable("fixture_not_in_T07_B"),
        current_product_projection_service=projection,
        current_product_review_control_service=control,
        current_product_reviewer_packet_service=packet,
        current_product_reviewer_session_service=service,
    )
    with TestClient(app) as client:
        assert client.get(
            "/api/v1/current-product/cases/NVDA/qualified-review"
        ).status_code == 401
        response = client.get(
            "/api/v1/current-product/cases/NVDA/qualified-review",
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        assert response.status_code == 200, response.text
        paths = client.get("/openapi.json").json()["paths"]
        assert not any("issue" in path and "review" in path for path in paths)


def test_event_chain_mutation_fails_closed(tmp_path: Path) -> None:
    _, db_path, _, _, _, service = _services(tmp_path)
    _issue(service)
    service.authenticate(TOKEN, expected_case_key="NVDA")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE t07_reviewer_security_events SET payload_json = ? WHERE event_sequence = 1",
            ('{"mutated":true}',),
        )
    with pytest.raises(ReviewerSessionError, match="event_chain_invalid"):
        service.get_review_state(TOKEN)
