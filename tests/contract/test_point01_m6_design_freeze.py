from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m6_0_design_lint.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_0_design_lint", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _manifest() -> dict[str, object]:
    return json.loads((ROOT / "configs/engineering_handoff/point01_m6_0_migration_design_freeze_manifest_v1_0.json").read_text(encoding="utf-8"))


def test_m6_design_freeze_passes_without_runtime_admission() -> None:
    result = MODULE.build_result(_manifest())
    assert result["status"] == "pass"
    assert result["runtime_implementation_count"] == 0
    assert result["authority_boundary"]["provider_execution"] == "not_admitted"
    assert "does not implement M6.1" in result["boundary"]


def test_m6_design_freeze_rejects_cross_owner_evidence_request_write() -> None:
    manifest = _manifest()
    evidence_request = next(row for row in manifest["artifact_catalog"] if row["artifact"] == "EvidenceRequest")
    evidence_request["write_owner"] = "M6.6_evidence_gate_owner"
    assert "artifact_owner_invalid:EvidenceRequest" in MODULE.validate_manifest(manifest)


def test_m6_design_freeze_rejects_m6_1_implementation_claim() -> None:
    manifest = _manifest()
    m6_1 = next(row for row in manifest["children"] if row["point_id"] == "M6.1")
    m6_1["status"] = "implemented"
    assert "implementation_not_denied:M6.1" in MODULE.validate_manifest(manifest)


def test_m6_design_freeze_rejects_unbounded_repair_feedback() -> None:
    manifest = _manifest()
    repair_edge = next(row for row in manifest["dataflow"] if row["from"] == "RepairTicket" and row["to"] == "ToolSelectionPlan")
    repair_edge["required_controls"] = ["origin_evidence_request_ref"]
    assert "repair_loop_not_bounded" in MODULE.validate_manifest(manifest)
