from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys

import pytest
from fastapi.testclient import TestClient


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from apps.workbench.backend.app import create_app
from apps.workbench.backend.application.case_service import CaseService
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (
    CurrentProductProjectionService,
)
from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_review_control import (
    CurrentProductReviewControlService,
    CurrentReviewControlError,
    CurrentReviewControlPrincipal,
    CurrentReturnForRepairDraft,
)
from sec_agent.canonical_runtime.models import canonical_digest


ACTOR = "t06_internal_operator"
READ_PRINCIPAL = CurrentReviewControlPrincipal(
    mode="current",
    actor_id=ACTOR,
    permissions=frozenset({"current_product:read"}),
)
WRITE_PRINCIPAL = CurrentReviewControlPrincipal(
    mode="current",
    actor_id=ACTOR,
    permissions=frozenset(
        {"current_product:read", "current_product:request_repair"}
    ),
)
API_HEADERS = {
    "X-Fin-Product-Mode": "current",
    "X-Fin-Current-Actor": ACTOR,
    "X-Fin-Case-Permissions": (
        "current_product:read,current_product:request_repair"
    ),
}


def _services(tmp_path: Path) -> tuple[
    CurrentProductProjectionService, CurrentProductReviewControlService, Path
]:
    projection = CurrentProductProjectionService.from_repository(REPO_ROOT)
    db_path = tmp_path / "review-control.sqlite"
    review = CurrentProductReviewControlService.from_repository(
        REPO_ROOT, projection, db_path
    )
    review._clock = lambda: "2026-08-05T23:00:00+00:00"
    return projection, review, db_path


def _draft(
    projection: CurrentProductProjectionService,
    case_key: str = "NVDA",
    surface: str = "report",
    *,
    reason_code: str = "delivery_clarity",
    key: str = "return-report-r1",
) -> CurrentReturnForRepairDraft:
    case = projection.get_case(
        case_key,
        principal=_projection_principal(),
    )
    target = projection.get_surface(
        case_key,
        surface,
        principal=_projection_principal(),
    )
    return CurrentReturnForRepairDraft(
        expected_manifest_digest=projection.manifest_digest,
        expected_case_projection_digest=case["case_projection_digest"],
        target_surface=surface,
        expected_target_view_digest=target["view_digest"],
        target_ref=f"surface:{surface}",
        reason_code=reason_code,
        reviewer_note="交付表述需要明确区分已报告事实与判断边界。",
        actor_ref=ACTOR,
        idempotency_key=key,
    )


def _projection_principal():
    from apps.workbench.backend.application.fin_0_1_2_s4_t06_current_product_projection import (
        CurrentProductPrincipal,
    )

    return CurrentProductPrincipal(
        mode="current", permissions=frozenset({"current_product:read"})
    )


def test_empty_replay_is_ready_for_T07_without_claiming_review(
    tmp_path: Path,
) -> None:
    projection, review, _ = _services(tmp_path)

    state = review.get_state("NVDA", READ_PRINCIPAL)

    assert state["event_count"] == 0
    assert state["return_requests"] == []
    assert state["replay_integrity"] == "pass"
    assert state["manifest_digest"] == projection.manifest_digest
    assert state["T07_handoff"]["status"] == "ready_for_qualified_review"
    assert state["T07_handoff"]["qualified_review_executed"] is False
    assert state["T07_handoff"]["NVDA_R3_executed"] is False
    assert state["hard_boundaries"]["qualified_human_review"] is False


def test_return_request_is_exact_typed_idempotent_and_replays_after_restart(
    tmp_path: Path,
) -> None:
    projection, review, db_path = _services(tmp_path)
    report_before = projection.get_surface(
        "NVDA", "report", _projection_principal()
    )
    draft = _draft(projection)

    first = review.request_return_for_repair(
        "NVDA", draft, WRITE_PRINCIPAL
    )
    reused = review.request_return_for_repair(
        "NVDA", draft, WRITE_PRINCIPAL
    )
    restarted = CurrentProductReviewControlService.from_repository(
        REPO_ROOT, projection, db_path
    ).get_state("NVDA", READ_PRINCIPAL)
    report_after = projection.get_surface(
        "NVDA", "report", _projection_principal()
    )

    assert reused == first == restarted
    assert first["event_count"] == 1
    request = first["return_requests"][0]
    assert request["action_type"] == "return_for_repair"
    assert request["target_surface"] == "report"
    assert request["reason_code"] == "delivery_clarity"
    assert request["repair_owner"] == "writer"
    assert request["requested_resolution"] == "delivery_rerender_and_verify"
    assert request["qualified_human_review"] is False
    assert request["automatic_repair_execution"] is False
    assert (
        first["T07_handoff"]["status"]
        == "repair_required_before_qualified_review"
    )
    assert first["T07_handoff"]["open_return_request_ids"] == [
        request["request_id"]
    ]
    assert report_after == report_before


def test_permission_identity_digest_surface_and_idempotency_mutations_fail_closed(
    tmp_path: Path,
) -> None:
    projection, review, _ = _services(tmp_path)
    draft = _draft(projection)

    with pytest.raises(
        CurrentReviewControlError,
        match="current_product_request_repair_permission_required",
    ):
        review.request_return_for_repair("NVDA", draft, READ_PRINCIPAL)

    wrong_actor = CurrentReviewControlPrincipal(
        mode="current",
        actor_id="somebody_else",
        permissions=WRITE_PRINCIPAL.permissions,
    )
    with pytest.raises(
        CurrentReviewControlError, match="current_review_actor_scope_mismatch"
    ):
        review.request_return_for_repair("NVDA", draft, wrong_actor)

    with pytest.raises(
        CurrentReviewControlError, match="current_review_manifest_digest_stale"
    ):
        review.request_return_for_repair(
            "NVDA",
            CurrentReturnForRepairDraft(
                **{**draft.__dict__, "expected_manifest_digest": "0" * 64}
            ),
            WRITE_PRINCIPAL,
        )

    with pytest.raises(
        CurrentReviewControlError,
        match="current_review_reason_surface_mismatch",
    ):
        review.request_return_for_repair(
            "NVDA",
            _draft(
                projection,
                surface="numeric",
                reason_code="delivery_clarity",
                key="bad-surface",
            ),
            WRITE_PRINCIPAL,
        )

    review.request_return_for_repair("NVDA", draft, WRITE_PRINCIPAL)
    changed_payload = CurrentReturnForRepairDraft(
        **{**draft.__dict__, "reviewer_note": "同一个 key 不能改变请求正文。"}
    )
    with pytest.raises(
        CurrentReviewControlError,
        match="current_review_idempotency_conflict",
    ):
        review.request_return_for_repair(
            "NVDA", changed_payload, WRITE_PRINCIPAL
        )


def test_hash_chain_and_cross_case_tampering_fail_replay(tmp_path: Path) -> None:
    projection, review, db_path = _services(tmp_path)
    review.request_return_for_repair(
        "NVDA", _draft(projection), WRITE_PRINCIPAL
    )
    with sqlite3.connect(db_path) as conn:
        payload = json.loads(
            conn.execute(
                "SELECT payload_json FROM current_product_review_events"
            ).fetchone()[0]
        )
        payload["case_key"] = "MU"
        conn.execute(
            "UPDATE current_product_review_events SET payload_json = ?",
            (json.dumps(payload, ensure_ascii=False, sort_keys=True),),
        )

    with pytest.raises(
        CurrentReviewControlError, match="current_review_event_chain_invalid"
    ):
        review.get_state("NVDA", READ_PRINCIPAL)


def test_three_case_review_replay_is_isolated_and_restart_safe(
    tmp_path: Path,
) -> None:
    projection, review, db_path = _services(tmp_path)
    requests = {
        "DELL": _draft(
            projection,
            "DELL",
            "evidence",
            reason_code="missing_authority",
            key="dell-evidence-r1",
        ),
        "MU": _draft(
            projection,
            "MU",
            "numeric",
            reason_code="numeric_scope_or_unit",
            key="mu-numeric-r1",
        ),
        "NVDA": _draft(
            projection,
            "NVDA",
            "workpaper",
            reason_code="unsupported_inference",
            key="nvda-workpaper-r1",
        ),
    }
    for case_key, draft in requests.items():
        review.request_return_for_repair(
            case_key, draft, WRITE_PRINCIPAL
        )

    restarted = CurrentProductReviewControlService.from_repository(
        REPO_ROOT, projection, db_path
    )
    states = {
        case_key: restarted.get_state(case_key, READ_PRINCIPAL)
        for case_key in requests
    }

    assert {state["event_count"] for state in states.values()} == {1}
    assert {
        case_key: state["return_requests"][0]["case_key"]
        for case_key, state in states.items()
    } == {"DELL": "DELL", "MU": "MU", "NVDA": "NVDA"}
    assert len({state["replay_digest"] for state in states.values()}) == 3
    assert all(
        state["T07_handoff"]["status"]
        == "repair_required_before_qualified_review"
        for state in states.values()
    )


def test_current_review_control_API_registers_static_paths_before_surface_route(
    tmp_path: Path,
) -> None:
    projection, review, _ = _services(tmp_path)
    app = create_app(
        tmp_path / "workbench.sqlite",
        p02_case_service=CaseService.for_fixture_root(
            tmp_path / "canonical", repo_root=REPO_ROOT
        ),
        current_product_projection_service=projection,
        current_product_review_control_service=review,
        workbench_runtime_mode="fixture",
    )
    case = projection.get_case("NVDA", _projection_principal())
    report = projection.get_surface(
        "NVDA", "report", _projection_principal()
    )
    command = {
        "expected_manifest_digest": projection.manifest_digest,
        "expected_case_projection_digest": case["case_projection_digest"],
        "target_surface": "report",
        "expected_target_view_digest": report["view_digest"],
        "target_ref": "surface:report",
        "reason_code": "delivery_clarity",
        "reviewer_note": "请将判断边界在最终交付中单列。",
        "actor_ref": ACTOR,
        "idempotency_key": "api-return-report-r1",
    }

    with TestClient(app) as client:
        initial = client.get(
            "/api/v1/current-product/cases/NVDA/review-control",
            headers=API_HEADERS,
        )
        created = client.post(
            "/api/v1/current-product/cases/NVDA/return-requests",
            headers=API_HEADERS,
            json=command,
        )
        denied = client.post(
            "/api/v1/current-product/cases/NVDA/return-requests",
            headers={
                **API_HEADERS,
                "X-Fin-Case-Permissions": "current_product:read",
            },
            json={**command, "idempotency_key": "denied"},
        )

    assert initial.status_code == 200
    assert initial.json()["event_count"] == 0
    assert created.status_code == 202
    assert created.json()["event_count"] == 1
    assert created.headers["etag"].startswith('"review-replay=')
    assert denied.status_code == 403
    assert (
        denied.json()["detail"]["reason"]
        == "current_product_request_repair_permission_required"
    )


def test_T06_C_successor_record_preserves_predecessor_without_freezing_future_code() -> None:
    output = REPO_ROOT / (
        "configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_"
        "and_t07_handoff_zero_call_implementation_v1_0.json"
    )
    predecessor_path = REPO_ROOT / (
        "configs/releases/fin_ia_0_1_2_s4_t06_b_current_frontend_runtime_"
        "isolation_and_browser_zero_call_implementation_v1_0.json"
    )
    stored = json.loads(output.read_text(encoding="utf-8"))
    predecessor = json.loads(predecessor_path.read_text(encoding="utf-8"))

    assert stored["record_digest"] == canonical_digest(
        {key: value for key, value in stored.items() if key != "record_digest"}
    )
    assert (
        stored["predecessor"]["T06_B_record_digest"]
        == predecessor["record_digest"]
    )
    assert stored["predecessor"]["historical_records_preserved_not_rewritten"] is True
    assert stored["acceptance_boundary"]["qualified_human_review"] is False
    assert stored["acceptance_boundary"]["NVDA_R3"] is False
    for binding in stored["code_and_test_bindings"]:
        assert len(binding["sha256"]) == 64
        assert binding["bytes"] > 0
        assert (REPO_ROOT / binding["ref"]).exists()
