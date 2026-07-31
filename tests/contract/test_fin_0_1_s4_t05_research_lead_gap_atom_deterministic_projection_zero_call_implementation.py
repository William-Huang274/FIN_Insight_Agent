from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
R7_BINDING_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_dell_r7_profile_v2_versioned_"
    "case_runtime_binding_and_create_app_preflight_minimum_zero_call_"
    "implementation_v1_0.json"
)
NUMERIC_IDENTITY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t05_case_local_numeric_atom_"
    "deterministic_rendering_and_delivery_identity_minimum_zero_call_"
    "implementation_v1_0.json"
)
FACT_PRESENCE_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
    "local_materialization_minimum_zero_call_implementation_v1_0.json"
)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3ResearchLeadV3ContractError,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation import (
    _CompactV5FullFakeProvider,
    _surface_and_capacity,
    _v5_admission,
)
from test_fin_0_1_s3_t09_specialist_v7_contract_convergence import (
    _semantic_only_mutation,
)


IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_"
    "minimum_zero_call_implementation_v1_0.json"
)
LATEST_RUNTIME_IMPLEMENTATION = (
    ROOT
    / "configs/releases/"
    "fin_ia_0_1_s4_t05_specialist_wwc_judgment_atom_deterministic_"
    "task_assembly_minimum_zero_call_implementation_v1_0.json"
)


def _v6_admission(input_pack: Any) -> Any:
    return _v5_admission(input_pack).model_copy(
        update={
            "admission_id": "fixture-s4-t05-research-lead-v6-gap-atoms",
            "execution_mode": "fixture_only_research_lead_v6_gap_atoms",
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
            ),
        }
    )


def _profile_lineage_valid_input_pack(cells: list[dict[str, Any]]) -> Any:
    input_pack = _input_pack(cells)
    lineage = {
        key: {
            "version_ref": f"fixture:{key}:v1",
            "digest": canonical_digest(("fixture", key)),
        }
        for key in (
            "T02_runtime_plan",
            "T03_evidence_route_plan",
            "T04_financial_pack",
            "T05_graph_pack",
            "T06_judgment_contract",
            "T07_presentation_contract",
        )
    }
    return input_pack.model_copy(update={"lineage": lineage})


def _atom(
    ordinal: int,
    *,
    claims: list[str],
    tasks: list[str],
) -> dict[str, Any]:
    return {
        "statement": f"gap atom {ordinal}",
        "claim_ids": claims,
        "what_would_change_task_ids": tasks,
    }


def _segment(atoms: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cross_cell_dependencies": [
            {
                "statement": "dependency",
                "claim_ids": ["C001"],
            }
        ],
        "conflict_adjudications": [],
        "variant_view": {
            "statement": "variant",
            "claim_ids": ["C001"],
            "what_would_change_task_ids": [],
        },
        "remaining_gap_atoms": atoms,
    }


def _ranked_atoms() -> list[dict[str, Any]]:
    return [
        _atom(1, claims=["C003"], tasks=[]),
        _atom(2, claims=["C001"], tasks=["W001"]),
        _atom(3, claims=["C002"], tasks=["W002"]),
        _atom(4, claims=["C003"], tasks=["W003"]),
        _atom(
            5,
            claims=["C001", "C002", "C003"],
            tasks=["W001"],
        ),
        _atom(6, claims=["C001", "C002", "C003"], tasks=[]),
        _atom(7, claims=["C003"], tasks=["W001"]),
        _atom(8, claims=["C001"], tasks=[]),
    ]


class _GapAtomV6FullFakeProvider(_CompactV5FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if request["node_id"] != "research_lead":
            return response
        output = json.loads(str(response["content"]))
        base = output.pop("remaining_gaps")[0]
        output["remaining_gap_atoms"] = [
            {
                **deepcopy(base),
                "statement": f"{base['statement']} #{ordinal}",
            }
            for ordinal in range(1, 9)
        ]
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def test_v6_registry_and_request_are_versioned_without_mutating_v5() -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    payload = {
        "input_digest": "fixture",
        "lead_contract": {"fixture": True},
        "specialist_outputs": specialists,
        "scoped_identity_surface": surface,
    }
    _, v5_before, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
        payload,
        heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        capacity=capacity,
    )
    v5_digest = canonical_digest(v5_before)
    _, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v6_request(
            payload,
            heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )
    )
    _, v5_after, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
        payload,
        heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        capacity=capacity,
    )

    assert canonical_digest(v5_after) == v5_digest
    assert request["research_lead_transport_ref"].endswith(":v6")
    assert "remaining_gap_atoms" in request["required_output_schema"]
    assert "remaining_gaps" not in request["required_output_schema"]
    assert (
        request["output_constraints"][
            "remaining_gap_atoms_independent_semantic_maximum"
        ]
        is None
    )
    assert request["output_constraints"]["canonical_remaining_gaps_maximum"] == 4
    assert binding["gap_atom_projection_policy_ref"] == (
        S3_RESEARCH_LEAD_GAP_ATOM_PROJECTION_POLICY.policy_ref
    )
    v5 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
    )
    v6 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF
    )
    assert v5.gap_atom_deterministic_projection is False
    assert v6.gap_atom_deterministic_projection is True


def test_v6_validates_all_atoms_then_projects_deterministic_top_four() -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    for specialist, status in zip(
        specialists,
        ("fact_supported", "hypothesis", "cannot_infer"),
        strict=True,
    ):
        specialist["judgment_layer"][0]["epistemic_status"] = status
    segment = _segment(_ranked_atoms())

    output, findings = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v6_output(
            segment,
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )
    )
    repeated, repeated_findings = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v6_output(
            deepcopy(segment),
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )
    )

    assert canonical_digest(repeated) == canonical_digest(output)
    assert repeated_findings == findings
    assert len(output["remaining_gaps"]) == 4
    assert all(
        row["what_would_change_task_ids"]
        for row in output["remaining_gaps"]
    )
    finding = findings[0]
    assert finding["candidate_count"] == 8
    assert finding["selected_count"] == 4
    assert finding["overflow_count"] == 4
    assert 5 in finding["selected_candidate_ordinals"]
    assert finding["acceptance_layer"] == "L2_recoverable_protocol"
    assert finding["terminal"] is False
    assert "statement" not in json.dumps(finding, ensure_ascii=False)


@pytest.mark.parametrize("count", (1, 4))
def test_v6_one_to_four_atoms_preserve_the_existing_success_path(
    count: int,
) -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    output, findings = (
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v6_output(
            _segment(_ranked_atoms()[:count]),
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )
    )
    assert len(output["remaining_gaps"]) == count
    assert findings == []


@pytest.mark.parametrize(
    "mutation",
    (
        lambda atom: atom.update({"claim_ids": ["C999"]}),
        lambda atom: atom.pop("statement"),
    ),
)
def test_v6_invalid_overflow_atom_fails_before_projection(
    mutation: Any,
) -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    atoms = _ranked_atoms()
    mutation(atoms[7])
    with pytest.raises(S3ResearchLeadV3ContractError):
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v6_output(
            _segment(atoms),
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )


def test_v5_five_gap_rows_remain_a_hard_cardinality_failure() -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    segment = _segment(_ranked_atoms()[:5])
    segment["remaining_gaps"] = segment.pop("remaining_gap_atoms")
    with pytest.raises(
        S3ResearchLeadV3ContractError,
        match="cardinality_above_maximum",
    ):
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v5_output(
            segment,
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )


def test_v6_full_fake_path_persists_l2_finding_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _profile_lineage_valid_input_pack(cells)
    admission = _v6_admission(input_pack)
    fake = _GapAtomV6FullFakeProvider(
        specialists,
        mutation=_semantic_only_mutation,
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")

    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={"research_run_id": "fixture-s4-t05-v6-gap-atoms"},
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    artifacts = {
        artifact.artifact_type: artifact.payload
        for artifact in result.artifacts
    }
    manifest_findings = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "recoverable_protocol_findings"
    ]
    judgment = artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE]
    assert judgment["recoverable_protocol_findings"] == manifest_findings
    assert len(judgment["cross_cell_lead"]["remaining_gaps"]) == 4
    assert manifest_findings[0]["node_id"] == "research_lead"
    assert manifest_findings[0]["candidate_count"] == 8
    assert manifest_findings[0]["overflow_count"] == 4


def test_zero_call_implementation_record_binds_current_code_and_next_gate() -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    latest = json.loads(
        NUMERIC_IDENTITY_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    current = json.loads(
        FACT_PRESENCE_IMPLEMENTATION.read_text(encoding="utf-8")
    )
    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["next_action"] == (
        "S4-T05-DELL-RESEARCH-LEAD-GAP-ATOM-DETERMINISTIC-"
        "PROJECTION-FRESH-AGENT-PROOF-DECISION"
    )
    assert implementation["fixture_proof"][
        "full_fake_provider_callbacks"
    ] == 12
    assert implementation["fixture_proof"][
        "full_fake_provider_logical_artifacts"
    ] == 9
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        current_sha256 = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if current_sha256 != expected_sha256:
            if relative_path in current[
                "historical_exact_binding_supersession"
            ]["allowed_changed_paths"]:
                assert current["exact_code_bindings"][
                    relative_path
                ] == current_sha256
            else:
                assert relative_path in latest[
                    "historical_exact_binding_supersession"
                ]["allowed_changed_paths"]
                assert latest["exact_code_bindings"][
                    relative_path
                ] == current_sha256
