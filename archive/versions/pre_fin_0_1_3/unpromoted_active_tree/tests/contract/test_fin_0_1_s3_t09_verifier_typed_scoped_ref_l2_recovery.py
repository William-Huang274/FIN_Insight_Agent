from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    DeepSeekS3ThreeCellNodeExecutor,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ScopedIdentityContractError,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    CellScopedResearchIdentityPolicy,
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)


def _findings(ref: dict[str, str]) -> list[dict[str, Any]]:
    rows = [
        {
            "layer": layer,
            "status": "pass",
            "issue_codes": [],
            "artifact_or_claim_refs": [],
            "repair_owner": None,
        }
        for layer in S3_FOUR_LAYER_VERIFIER_LAYERS
    ]
    rows[1] = {
        "layer": S3_FOUR_LAYER_VERIFIER_LAYERS[1],
        "status": "review_required",
        "issue_codes": ["unresolved_cross_cell_conflict"],
        "artifact_or_claim_refs": [ref],
        "repair_owner": "research_lead",
    }
    return rows


def _validate(
    findings: list[dict[str, Any]],
    specialists: list[dict[str, Any]],
    surface: dict[str, Any],
) -> None:
    lead_digest = canonical_digest({"lead": "fixture"})
    writer_digest = canonical_digest({"writer": "fixture"})
    S3ThreeCellBoundedAgentExecutor._validate_verifier_output(
        {
            "findings": findings,
            "bound_lead_digest": lead_digest,
            "bound_writer_digest": writer_digest,
            "decision": "repair",
        },
        lead_digest,
        writer_digest,
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        specialist_outputs=specialists,
        scoped_identity_surface=surface,
    )


def test_verifier_request_uses_shared_typed_claim_ref_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        S3ThreeCellBoundedAgentExecutor,
        "_validate_owner_grade_verifier_input",
        staticmethod(lambda payload: None),
    )
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-verifier-typed-ref-request",
        execution_mode="zero_call_verifier_typed_ref_request",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    )
    system, request, _ = DeepSeekS3ThreeCellNodeExecutor._node_request(
        "verifier",
        {},
        admission,
    )

    assert request["required_output_schema"]["findings"][0][
        "artifact_or_claim_refs"
    ] == [CellScopedResearchIdentityPolicy.wire_schema("claim")]
    assert request["output_constraints"]["exact_ref_contract_ref"] == (
        S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF
    )
    assert request["output_constraints"][
        "artifact_or_claim_refs_current_supported_kind"
    ] == "claim"
    assert "deterministic-owned" in system
    assert "company-total" in system


def test_verifier_accepts_known_typed_scoped_claim_refs() -> None:
    _, by_cell = _shared_local_id_specialists()
    specialists = list(by_cell.values())
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    first = specialists[0]
    ref = CellScopedResearchIdentityPolicy.ref(
        "claim",
        str(first["program_cell_id"]),
        str(first["judgment_layer"][0]["claim_id"]),
    ).to_payload()

    _validate(_findings(ref), specialists, surface)


def test_verifier_rejects_raw_unknown_and_duplicate_refs_without_guessing() -> None:
    _, by_cell = _shared_local_id_specialists()
    specialists = list(by_cell.values())
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    first = specialists[0]
    ref = CellScopedResearchIdentityPolicy.ref(
        "claim",
        str(first["program_cell_id"]),
        str(first["judgment_layer"][0]["claim_id"]),
    ).to_payload()

    raw = _findings(ref)
    raw[1]["artifact_or_claim_refs"] = ["claim-local-001"]
    with pytest.raises(
        S3ScopedIdentityContractError,
        match="raw_local_id_cross_cell_ambiguous",
    ):
        _validate(raw, specialists, surface)

    unknown = _findings(ref)
    unknown[1]["artifact_or_claim_refs"] = [
        {
            "identity_kind": "claim",
            "program_cell_id": "unknown-cell",
            "local_id": "claim-local-001",
        }
    ]
    with pytest.raises(S3ScopedIdentityContractError, match="unknown_scoped_ref"):
        _validate(unknown, specialists, surface)

    duplicate = _findings(ref)
    duplicate[1]["artifact_or_claim_refs"] = [
        deepcopy(ref),
        deepcopy(ref),
    ]
    with pytest.raises(
        S3ScopedIdentityContractError,
        match="scoped_ref_duplicate",
    ):
        _validate(duplicate, specialists, surface)


def test_zero_call_disposition_records_l1_and_l3_separately() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/"
            "fin_ia_0_1_s3_t09_verifier_typed_scoped_ref_l2_recovery_"
            "and_l1_semantic_findings_disposition_v1_0.json"
        ).read_text(encoding="utf-8")
    )

    assert result["L2_recovery"]["typed_ref_contract_converged"] is True
    assert result["L1_review"]["hard_integrity_violation_confirmed"] is False
    assert result["L1_review"]["quality_findings_carried_forward"] == [
        "unresolved_cross_cell_conflict",
        "unattributed_company_total_margins",
    ]
    assert result["historical_terminal_truth"]["artifact_count"] == 0
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-LAYERED-VERIFIER-TYPED-REF-AND-FINDING-DISPOSITION-"
        "FRESH-AGENT-PROOF-DECISION"
    )
