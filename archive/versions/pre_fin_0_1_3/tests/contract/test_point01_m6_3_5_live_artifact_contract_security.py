from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.m6_pilot_global_approval import M6GlobalOneShotApprovalReceipt


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SANITIZER_PATH = ROOT / "scripts/engineering/run_point01_m6_3_5_restricted_live_artifact_sanitization.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_live_artifact_sanitizer", SANITIZER_PATH)
assert SPEC and SPEC.loader
SANITIZER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SANITIZER)


def _receipt_payload() -> dict[str, object]:
    return {
        "tenant_id": "global",
        "project_id": "point01",
        "case_id": None,
        "actor_snapshot_ref": "reviewer-william-003",
        "permission_snapshot_ref": "reviewer-permission",
        "policy_config_refs": ("point01-test",),
        "correlation_id": "point01-test-approval",
        "current_status": "active",
        "approval_id": "approval-point01-test",
        "approval_version": 1,
        "state_version": 1,
        "approval_state": "active",
        "approval_nonce": "nonce-" + "x" * 32,
        "scope_digest": "a" * 64,
        "package_ref": "point01-test-package",
        "package_digest": "b" * 64,
        "package_manifest_digest": "c" * 64,
        "reviewer_name": "william",
        "reviewer_employee_id": "003",
        "reviewer_role": "total_reviewer",
        "expires_at": "2026-07-13T13:40:55Z",
        "authority_store_identity": "d" * 64,
    }


def _restricted_original(raw_nonce: str) -> dict[str, object]:
    receipt = {
        "content_digest": "0" * 64,
        "global_approval_id": "approval-point01-v4",
        "global_approval_nonce": raw_nonce,
        "global_approval_receipt_digest": "1" * 64,
        "global_approval_store_identity": "2" * 64,
        "invocation_id": "sec_document_invocation_colliding_legacy_v4",
        "invocation_state": "succeeded",
        "downstream_status": "positive_chain_persisted",
        "request_id": "evidence_request_test",
        "request_digest": "3" * 64,
        "tool_selection_plan_id": "tool_selection_plan_test",
        "tool_selection_plan_digest": "4" * 64,
        "retry_call_count": 0,
        "fallback_call_count": 0,
        "source_document": {
            "document_content_sha256": "5" * 64,
            "response_status_code": 200,
            "raw_document_persisted": False,
        },
    }
    return {
        "status": "pass",
        "execution_status": "positive_chain_persisted",
        "external_call_count": 1,
        "tool_invocation_count": 1,
        "approval_package": {
            "package_ref": "point01-v4-package",
            "package_digest": "6" * 64,
            "manifest_digest": "7" * 64,
        },
        "receipt": receipt,
        "candidate": {
            "content_digest": "8" * 64,
            "candidate_id": "candidate-test",
            "promotion_status": "unpromoted",
            "writer_citable": False,
            "domain_judgment_eligible": False,
            "source_document_sha256": "5" * 64,
            "source_url": "https://www.sec.gov/Archives/edgar/data/1045810/test.htm",
            "table_coordinate": "table[21]/row[3]",
            "table_heading_normalized": "CONSOLIDATED STATEMENTS OF INCOME",
            "unit_caption_normalized": "In millions, except per share data",
            "row_label_normalized": "Revenue",
            "normalized_period": "2025-01-26",
            "financial_statement_role": "consolidated_primary_financial_statement",
        },
        "parser": {
            "content_digest": "9" * 64,
            "parser_candidate_id": "parser-test",
            "promotion_status": "unpromoted",
            "table_coordinate": "table[21]/row[3]",
            "parsed_table_digest": "a" * 64,
            "parse_status": "parsed_unpromoted",
        },
        "fact": {
            "content_digest": "b" * 64,
            "normalized_fact_id": "fact-test",
            "promotion_status": "unpromoted",
            "normalized_value": "130497",
            "unit": "USD_millions",
            "scale_multiplier": 1000000,
            "period": "2025-01-26",
            "source_coordinate": "table[21]/row[3]",
        },
        "trace": {
            "content_digest": "c" * 64,
            "numeric_trace_id": "trace-test",
            "promotion_status": "unpromoted",
            "writer_citable": False,
            "input_digest": "d" * 64,
            "output_value": "130497",
            "program_steps": ["html_table_parse"],
        },
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | set().union(*(_all_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_all_keys(item) for item in value)) if value else set()
    return set()


def test_new_authority_receipt_persists_only_nonce_sha256() -> None:
    receipt = M6GlobalOneShotApprovalReceipt.create(**_receipt_payload())
    serialized = receipt.model_dump(mode="json")

    assert "approval_nonce" not in serialized
    assert len(serialized["approval_nonce_sha256"]) == 64
    assert "nonce-" not in json.dumps(serialized, sort_keys=True)


def test_sanitized_projection_separates_terminal_authorization_and_replaces_legacy_identity(tmp_path: Path) -> None:
    raw_nonce = "restricted-" + "secret" * 8
    original_path = tmp_path / "restricted-v4.json"
    original_path.write_text(json.dumps(_restricted_original(raw_nonce)), encoding="utf-8")
    policy = json.loads((ROOT / "configs/engineering_handoff/point01_m6_3_5_restricted_live_artifact_policy_v1_0.json").read_text(encoding="utf-8"))

    projection = SANITIZER.build_projection(
        original=json.loads(original_path.read_text(encoding="utf-8")),
        original_path=original_path,
        policy=policy,
    )
    rendered = json.dumps(projection, sort_keys=True)
    execution_id = projection["lineage"]["execution_instance_id"]

    assert projection["result_version"] == "finsight_point01_m6_3_5_live_terminal_audit_projection_v1_0"
    assert projection["execution_state"] == "approved_single_live_pilot_succeeded"
    assert "authority_boundary" not in projection
    assert projection["package_authority_boundary"]["live_send_requires_separate_exact_receipt"] is True
    assert projection["execution_authorization_snapshot"]["live_send_authorized_by_exact_receipt"] is True
    assert projection["execution_authorization_snapshot"]["receipt_state"] == "consumed"
    assert execution_id != "sec_document_invocation_colliding_legacy_v4"
    assert raw_nonce not in rendered
    assert "global_approval_nonce" not in _all_keys(projection)
    assert projection["downstream_firewall"]["writer_citable"] is False
    for value in projection["unpromoted_lineage"].values():
        assert value["execution_instance_id"] == execution_id
        assert value["superseding_receipt_version_ref"] == projection["lineage"]["receipt_version_ref"]
        assert value["promotion_status"] == "unpromoted"
