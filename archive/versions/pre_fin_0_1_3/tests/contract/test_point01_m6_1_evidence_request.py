from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from sec_agent.canonical_runtime.evidence_request import EvidenceRequestCompileError, EvidenceRequestCompileOverrides, EvidenceRequestCompiler


pytestmark = pytest.mark.fast_contract


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m6_1_evidence_request_fixture.py"
SPEC = importlib.util.spec_from_file_location("point01_m6_1_fixture", RUNNER_PATH)
assert SPEC and SPEC.loader
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def test_exact_cell_slot_request_is_replayable_and_numeric_bound() -> None:
    compiler = EvidenceRequestCompiler(RUNNER._policy())
    contract, cell, slot = RUNNER.planning_models(sector="ai_semis")
    first = compiler.compile(
        contract=contract,
        cell=cell,
        slot=slot,
        overrides=EvidenceRequestCompileOverrides(product_intent=("accelerator",)),
    )
    second = compiler.compile(
        contract=contract,
        cell=cell,
        slot=slot,
        overrides=EvidenceRequestCompileOverrides(product_intent=("accelerator",)),
    )
    assert first.request.request_digest == second.request.request_digest
    assert first.request.compiled_from_refs == (contract.contract_version_id, cell.cell_version_id, slot.slot_version_id, "point01-m6-1-evidence-request-policy-v1")
    assert first.request.accepted_evidence_role == "numeric_fact"
    assert first.request.numeric_binding_requirements == ("row_label", "unit", "period", "source_coordinate")
    assert first.external_call_count == 0
    assert first.store_write_count == 0


def test_compiler_rejects_parent_policy_and_requester_bypass() -> None:
    compiler = EvidenceRequestCompiler(RUNNER._policy())
    contract, cell, slot = RUNNER.planning_models(sector="banks")
    with pytest.raises(EvidenceRequestCompileError, match="slot_parent_cell_version_mismatch"):
        compiler.compile(contract=contract, cell=cell, slot=slot.model_copy(update={"cell_version_id": "wrong:v1"}))
    with pytest.raises(EvidenceRequestCompileError, match="required_forbidden_substitution_missing:relationship_graph_only"):
        compiler.compile(contract=contract, cell=cell, slot=slot.model_copy(update={"forbidden_substitutions": ()}))
    with pytest.raises(EvidenceRequestCompileError, match="requester_role_must_match_cell_owner"):
        compiler.compile(
            contract=contract,
            cell=cell,
            slot=slot,
            overrides=EvidenceRequestCompileOverrides(requester_role="memo_writer"),
        )


def test_relationship_request_is_context_only_not_numeric_or_promotion() -> None:
    compiler = EvidenceRequestCompiler(RUNNER._policy())
    contract, cell, slot = RUNNER.planning_models(
        sector="relationship",
        evidence_role="relationship_signal",
        source_policy_ref="relationship_graph_only",
        acceptance_role="bounded_context_only",
        forbidden_substitutions=("issuer_metric_substitute",),
        metric_scope=(),
    )
    request = compiler.compile(contract=contract, cell=cell, slot=slot).request
    assert request.accepted_evidence_role == "context"
    assert request.numeric_binding_requirements == ()
    assert request.execution_admission == "not_admitted"
    assert request.preferred_routes == ("relationship_graph_metadata_route",)


def test_cross_owner_review_records_user_scoped_authorization_without_false_independence_claim() -> None:
    review = json.loads((ROOT / "configs/engineering_handoff/point01_m6_1_cross_owner_design_review_v1_0.json").read_text(encoding="utf-8"))
    assert review["status"] == "user_confirmed_structured_cross_owner_review_accepted_for_m6_1"
    assert review["independent_human_or_multi_person_signoff"] is False
    assert review["user_confirmation"]["decision"] == "approve_m6_1_deterministic_cell_slot_request_compiler_only"
    assert len(review["reviewer_lenses"]) == 5


def test_m6_1_fixture_runner_is_multisector_replayable_and_execution_free(tmp_path: Path) -> None:
    output = tmp_path / "m6_1_fixture.json"
    completed = subprocess.run([sys.executable, str(RUNNER_PATH), "--output", str(output)], cwd=ROOT, text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["status"] == "pass"
    assert result["checks"]["four_sector_positive_corpus"] is True
    assert result["checks"]["lineage_and_policy_negatives"] is True
    assert result["authority_boundary"]["external_tool_execution"] is False
