from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/releases/point02_p02_4_vertical_contract_increment_v1_0.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def test_increment_binds_exact_p02_0_v1_1_contracts() -> None:
    contract = _load(CONTRACT)
    for binding in contract["base_contracts"]:
        path = ROOT / binding["path"]
        assert path.exists()
        assert binding["canonical_digest"] == _canonical_digest(_load(path))


def test_increment_is_a_bounded_product_delta_not_a_new_gate() -> None:
    contract = _load(CONTRACT)
    assert contract["execution_point"] == "P02.4"
    assert contract["authority"] == "fixture_shadow_internal_development_only"
    assert len(contract["fixed_cells"]) == 3
    assert {row["cell_key"] for row in contract["fixed_cells"]} == {
        "demand_reality",
        "value_profit_capture",
        "bottleneck_counterevidence",
    }
    assert "does_not_create_a_gate_or_package_family" in contract["non_authority"]
    assert "does_not_reopen_P02_0" in contract["non_authority"]
    assert "does_not_admit_FIN_0_1_release_or_production" in contract["non_authority"]


def test_increment_closes_revision_projection_and_checkpoint_gap() -> None:
    contract = _load(CONTRACT)
    delta = contract["canonical_delta"]
    assert {row["command_id"] for row in delta["commands"]} == {
        "CompileDecisionSurfaceCommand",
        "ReviseDecisionSurfaceCommand",
        "PlanningCheckpointDecisionCommand",
    }
    assert "PlanningCheckpointVersion" in {row["model"] for row in delta["models"]}
    assert delta["persistence"]["runtime_boundary"] == "RuntimeFacade"
    assert delta["persistence"]["store_registration"] == {
        "object_tables_add": "canonical_planning_checkpoint_versions",
        "case_scoped_tables_add": "canonical_planning_checkpoint_versions",
        "parent_binding": "PlanningCheckpointVersion.contract_version_id must reference the exact DecisionSurfaceContractVersion.contract_version_id in the same Case",
    }
    assert set(delta["persistence"]["must_not_require"]) >= {
        "canonical_work_units",
        "canonical_attempts",
        "work_unit_id",
        "attempt_id",
    }
    assert set(contract["api_delta"]["cell_view_required"]) >= {
        "decision_question",
        "what_would_change",
        "evidence_slots",
    }
    assert set(contract["api_delta"]["evidence_slot_view_required"]) >= {
        "evidence_role",
        "source_policy_ref",
        "required",
    }
    schemas = contract["api_delta"]["wire_schemas"]
    assert schemas["CompileDecisionSurfaceCommand"]["fixed_values"] == {
        "compiler_policy_ref": "fixture:p36-three-cell-v1",
        "pack_selection_ref": "fixture:p36-ai-infrastructure-v1",
    }
    assert schemas["ReviseDecisionSurfaceCommand"]["changes_item"] == {
        "required": ["cell_id", "what_would_change"],
        "optional": ["stop_rule"],
        "minimum_items": 1,
    }
    assert schemas["PlanningCheckpointDecisionCommand"]["decision_values"] == ["accept", "return"]


def test_fixed_cells_have_exact_product_content_and_two_required_slots_each() -> None:
    cells = _load(CONTRACT)["fixed_cells"]
    for cell in cells:
        assert cell["decision_question"].strip()
        assert cell["stop_rule"].strip()
        assert cell["what_would_change"].strip()
        assert len(cell["evidence_slots"]) == 2
        assert {slot["evidence_role"] for slot in cell["evidence_slots"]} == set(cell["required_evidence_roles"])
        assert all(slot["required"] for slot in cell["evidence_slots"])


def test_increment_preserves_immutable_plan_and_checkpoint_semantics() -> None:
    states = _load(CONTRACT)["state_machine"]
    assert states == {
        "compile": "new_contract_version_plus_awaiting_review_checkpoint",
        "revise": "new_contract_version_plus_awaiting_review_checkpoint",
        "accept": "same_contract_version_plus_accepted_checkpoint",
        "return": "same_contract_version_plus_returned_checkpoint",
        "stale_command": "version_conflict_without_write",
    }
