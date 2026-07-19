from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m6_3_5_positive_sec_document_pilot_design_lint.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_3_5_positive_sec_document_pilot_design_lint", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _design() -> dict[str, object]:
    return json.loads(
        (ROOT / "configs/engineering_handoff/point01_m6_3_5_positive_sec_document_pilot_design_v1_0.json").read_text(encoding="utf-8")
    )


def test_positive_sec_document_pilot_design_has_an_immutable_external_decision_boundary() -> None:
    result = MODULE.build_result(_design())
    assert result["status"] == "pass"
    assert result["design_status"] == "immutable_runtime_contract_external_total_reviewer_decision_required"
    assert result["external_call_count"] == 0
    assert result["parser_execution_count"] == 0
    assert result["evidence_promotion_count"] == 0


def test_positive_sec_document_pilot_design_rejects_reuse_of_consumed_metadata_receipt() -> None:
    design = _design()
    design["authorization"]["prior_m6_2_one_shot_receipt"] = "reusable"
    assert "prior_receipt_reuse_not_denied" in MODULE.validate_design(design)


def test_positive_sec_document_pilot_design_rejects_parser_promotion_or_writer_citation() -> None:
    design = _design()
    design["artifact_boundary"]["evidence_promotion"] = "allowed"
    design["artifact_boundary"]["writer_citable"] = True
    errors = MODULE.validate_design(design)
    assert "artifact_boundary_invalid:evidence_promotion" in errors
    assert "downstream_consumer_boundary_invalid" in errors


def test_positive_sec_document_pilot_design_rejects_search_or_retry_expansion() -> None:
    design = _design()
    design["source_boundary"]["web_search"] = "allowed"
    design["source_boundary"]["max_retry_calls"] = 1
    errors = MODULE.validate_design(design)
    assert "discovery_execution_not_denied" in errors
    assert "call_budget_invalid:max_retry_calls" in errors


def test_positive_sec_document_pilot_design_rejects_runtime_use_of_reviewer_blind_oracle() -> None:
    design = _design()
    design["target_document"]["reviewer_blind_oracle"]["allowed_runtime_use"] = True
    assert "reviewer_blind_oracle_boundary_invalid" in MODULE.validate_design(design)


def test_positive_sec_document_pilot_design_rejects_mutable_receipt_registration_policy() -> None:
    design = _design()
    design["authorization"]["receipt_registration"] = "authorized"
    assert "receipt_registration_external_decision_boundary_invalid" in MODULE.validate_design(design)


def test_positive_sec_document_pilot_design_requires_incident_transport_isolation() -> None:
    design = _design()
    design["incident_remediation_isolation"]["default_transport"] = "requests_session_default"
    assert "incident_isolation_invalid:default_transport" in MODULE.validate_design(design)
