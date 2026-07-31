from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    BoundedResearchProfile,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
    research_lead_transport_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_DEEPSEEK_BETA_BASE_URL,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
    S3ScopedIdentityContractError,
    S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.bounded_agent_identity_policies import (
    CellScopedResearchIdentityPolicy,
    CompactScopedReferenceAliasTable,
    S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
    ScopedIdentityViolation,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _ScopedV4FullFakeProvider,
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_owner_grade_semantic_actionability_zero_call_repair import (
    _input_pack,
)
from test_fin_0_1_s3_t09_specialist_v7_contract_convergence import (
    _semantic_only_mutation,
)


def _v5_admission(input_pack: Any) -> S3ThreeCellBoundedAgentAdmission:
    return S3ThreeCellBoundedAgentAdmission(
        admission_id="fixture-s3-t09-research-lead-v5",
        output_contract_ref=S3_THREE_CELL_BOUNDED_AGENT_OUTPUT_CONTRACT_V4_REF,
        execution_enabled=True,
        execution_mode="fixture_only_research_lead_v5",
        research_profile_ref=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2_REF,
        case_id=input_pack.case_id,
        case_version=input_pack.case_version,
        as_of=input_pack.as_of,
        input_digest=input_pack.input_digest,
        provider="deepseek",
        model="deepseek-v4-pro",
        model_ref="deepseek:deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
        base_url=BOUNDED_DEEPSEEK_BETA_BASE_URL,
        transport_ref=S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
        research_lead_transport_ref=S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
        memo_writer_transport_ref=S3_OWNER_GRADE_MEMO_WRITER_TRANSPORT_V3_REF,
        scoped_identity_contract_ref=S3_CELL_SCOPED_RESEARCH_IDENTITY_CONTRACT_REF,
        provider_output_capture_policy_ref=S3_PROVIDER_OUTPUT_CAPTURE_POLICY_REF,
        max_semantic_model_calls=12,
        max_provider_calls=12,
        max_network_calls=12,
        max_total_cost_usd=0.10,
        specialist_max_output_tokens=4200,
        lead_max_output_tokens=1800,
        writer_max_output_tokens=1400,
        verifier_max_output_tokens=1000,
    )


def _surface_and_capacity() -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    CompactScopedReferenceAliasTable,
    list[dict[str, Any]],
    dict[str, Any],
]:
    _, by_cell = _shared_local_id_specialists()
    specialists = list(by_cell.values())
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    table = S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
        specialists,
        surface,
    )
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    )
    capacity = (
        DeepSeekS3ThreeCellNodeExecutor
        ._research_lead_v5_capacity_envelope(
            alias_table=table,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        )
    )
    return specialists, surface, table, heads, capacity


def _maximum_reference_capacity() -> dict[str, Any]:
    _, by_cell = _shared_local_id_specialists()
    specialists = list(by_cell.values())
    for specialist in specialists:
        second_claim = deepcopy(specialist["judgment_layer"][0])
        second_claim["claim_id"] = "claim-local-002"
        specialist["judgment_layer"].append(second_claim)
        for ordinal in (2, 3):
            task = deepcopy(specialist["what_would_change"][0])
            task["task_id"] = f"wwc-local-{ordinal:03d}"
            specialist["what_would_change"].append(task)
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    table = S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
        specialists,
        surface,
    )
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
    )
    return (
        DeepSeekS3ThreeCellNodeExecutor
        ._research_lead_v5_capacity_envelope(
            alias_table=table,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        )
    )


def _compact_provider_segment(
    typed_output: Mapping[str, Any],
    alias_rows: list[Mapping[str, str]],
) -> dict[str, Any]:
    by_ref = {
        (
            str(row["identity_kind"]),
            str(row["program_cell_id"]),
            str(row["local_id"]),
        ): str(row["alias"])
        for row in alias_rows
    }

    def alias(value: Mapping[str, Any]) -> str:
        return by_ref[
            (
                str(value["identity_kind"]),
                str(value["program_cell_id"]),
                str(value["local_id"]),
            )
        ]

    output = deepcopy(typed_output)
    for row in output["cross_cell_dependencies"]:
        row.pop("dependency_id")
        row["claim_ids"] = [alias(value) for value in row["claim_ids"]]
    for row in output["conflict_adjudications"]:
        row.pop("adjudication_id")
        row["involved_claim_ids"] = [
            alias(value) for value in row["involved_claim_ids"]
        ]
    output["variant_view"]["claim_ids"] = [
        alias(value) for value in output["variant_view"]["claim_ids"]
    ]
    output["variant_view"]["what_would_change_task_ids"] = [
        alias(value)
        for value in output["variant_view"]["what_would_change_task_ids"]
    ]
    for row in output["remaining_gaps"]:
        row.pop("gap_id")
        row["claim_ids"] = [alias(value) for value in row["claim_ids"]]
        row["what_would_change_task_ids"] = [
            alias(value) for value in row["what_would_change_task_ids"]
        ]
    return output


class _CompactV5FullFakeProvider(_ScopedV4FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        response = dict(super().__call__(**kwargs))
        if request["node_id"] != "research_lead":
            return response
        typed = json.loads(str(response["content"]))
        rows = request["analysis_input"][
            "compact_scoped_reference_alias_table"
        ]["rows"]
        response["content"] = json.dumps(
            _compact_provider_segment(typed, rows),
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def test_lead_capability_registry_converges_v1_through_v5() -> None:
    v4 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V4_REF
    )
    v5 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
    )
    assert v4.typed_scoped_identity is True
    assert v4.compact_scoped_alias_wire is False
    assert (
        v5.compact_scoped_alias_wire,
        v5.local_row_ids,
        v5.dual_capacity,
    ) == (True, True, True)


def test_compact_alias_table_is_deterministic_closed_and_not_authority() -> None:
    specialists, surface, table, _, _ = _surface_and_capacity()
    repeated = CompactScopedReferenceAliasTable.from_surface(surface)
    assert repeated == table
    assert [row.alias for row in table.rows] == [
        "C001",
        "C002",
        "C003",
        "W001",
        "W002",
        "W003",
    ]
    assert all(
        row.ref.program_cell_id
        == specialists[index % len(specialists)]["program_cell_id"]
        for index, row in enumerate(table.rows)
    )
    assert set(table.to_prompt_payload()) == {
        "alias_contract_ref",
        "rows",
    }


@pytest.mark.parametrize(
    ("value", "kind", "subtype"),
    (
        ("C999", "claim", "unknown_scoped_ref"),
        ("W001", "claim", "scoped_ref_mismatch"),
        (" C001", "claim", "scoped_ref_mismatch"),
        ("c001", "claim", "scoped_ref_mismatch"),
        ("claim-local-001", "claim", "unknown_scoped_ref"),
    ),
)
def test_compact_alias_rejects_unknown_wrong_kind_and_normalized_values(
    value: str,
    kind: str,
    subtype: str,
) -> None:
    _, _, table, _, _ = _surface_and_capacity()
    violation = table.expand(value, expected_kind=kind)
    assert violation == ScopedIdentityViolation(
        identity_kind=kind,
        failure_subtype=subtype,
        failing_item_count=1,
    )


def test_v5_request_uses_aliases_once_and_preserves_v4_request() -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    payload = {
        "input_digest": "fixture-input",
        "lead_contract": {"fixture": True},
        "specialist_outputs": specialists,
        "scoped_identity_surface": surface,
    }
    _, v4_before, _ = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v4_request(
            payload,
            heads,
        )
    )
    v4_digest = canonical_digest(v4_before)
    _, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
            payload,
            heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )
    )
    _, v4_after, _ = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v4_request(
            payload,
            heads,
        )
    )
    assert canonical_digest(v4_after) == v4_digest
    assert "scoped_identity_surface" not in request["analysis_input"]
    assert len(
        request["analysis_input"][
            "compact_scoped_reference_alias_table"
        ]["rows"]
    ) == 6
    assert "dependency_id" not in (
        request["required_output_schema"]["cross_cell_dependencies"][0]
    )
    assert request["output_constraints"]["claim_alias_list_maximum"] == 3
    assert binding["compact_alias_table_digest"]


def test_v5_local_expansion_adds_row_ids_and_restores_typed_refs() -> None:
    specialists, surface, table, heads, capacity = _surface_and_capacity()
    alias_rows = table.to_prompt_payload()["rows"]
    typed = {
        "cross_cell_dependencies": [
            {
                "dependency_id": "provider-id",
                "statement": "dependency",
                "claim_ids": [
                    row.ref.to_payload()
                    for row in table.rows
                    if row.ref.identity_kind == "claim"
                ],
            }
        ],
        "conflict_adjudications": [],
        "variant_view": {
            "statement": "variant",
            "claim_ids": [table.rows[0].ref.to_payload()],
            "what_would_change_task_ids": [],
        },
        "remaining_gaps": [
            {
                "gap_id": "provider-id",
                "statement": "gap",
                "claim_ids": [table.rows[0].ref.to_payload()],
                "what_would_change_task_ids": [],
            }
        ],
    }
    segment = _compact_provider_segment(typed, alias_rows)
    output = DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v5_output(
        segment,
        specialists,
        surface,
        cell_heads=heads,
        research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        capacity=capacity,
    )
    assert output["cross_cell_dependencies"][0]["dependency_id"] == (
        "research_lead:dependency:001"
    )
    assert output["remaining_gaps"][0]["gap_id"] == (
        "research_lead:gap:001"
    )
    assert output["variant_view"]["claim_ids"][0] == (
        table.rows[0].ref.to_payload()
    )
    assert "C001" not in json.dumps(output, ensure_ascii=False)


def test_v5_duplicate_alias_fails_before_canonical_assembly() -> None:
    specialists, surface, _, heads, capacity = _surface_and_capacity()
    segment = {
        "cross_cell_dependencies": [
            {
                "statement": "dependency",
                "claim_ids": ["C001", "C001"],
            }
        ],
        "conflict_adjudications": [],
        "variant_view": {
            "statement": "variant",
            "claim_ids": ["C001"],
            "what_would_change_task_ids": [],
        },
        "remaining_gaps": [
            {
                "statement": "gap",
                "claim_ids": ["C001"],
                "what_would_change_task_ids": [],
            }
        ],
    }
    with pytest.raises(
        S3ScopedIdentityContractError,
        match="scoped_ref_duplicate",
    ):
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v5_output(
            segment,
            specialists,
            surface,
            cell_heads=heads,
            research_profile=S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
            capacity=capacity,
        )


def test_maximum_combined_capacity_fixture_closes_all_three_envelopes() -> None:
    _, _, _, _, capacity = _surface_and_capacity()
    assert capacity == {
        "capacity_formula_ref": (
            "fin01.s3.research_lead_local_capacity."
            "exact_surface_maximum_valid_shape:v1"
        ),
        "exact_claim_alias_count": 3,
        "exact_what_would_change_alias_count": 3,
        "maximum_provider_segment_utf8_bytes": 4440,
        "maximum_canonical_alias_segment_utf8_bytes": 4866,
        "maximum_local_expanded_canonical_utf8_bytes": 12253,
    }
    assert canonical_digest(capacity) == (
        "f207e92024c9a4e109ec3ddb7665c3e396d965250726705ab43de635d6ce1bc3"
    )


def test_maximum_specialist_reference_cardinality_is_profile_closed() -> None:
    capacity = _maximum_reference_capacity()
    assert capacity == {
        "capacity_formula_ref": (
            "fin01.s3.research_lead_local_capacity."
            "exact_surface_maximum_valid_shape:v1"
        ),
        "exact_claim_alias_count": 6,
        "exact_what_would_change_alias_count": 9,
        "maximum_provider_segment_utf8_bytes": 4881,
        "maximum_canonical_alias_segment_utf8_bytes": 5307,
        "maximum_local_expanded_canonical_utf8_bytes": 19210,
    }
    assert canonical_digest(capacity) == (
        "2fff37072e7af7e4a825931eb8c639c344704285708828e3a60a9ccd4d9da02b"
    )


def test_minimum_reference_cardinality_is_profile_closed() -> None:
    specialists = [
        {
            "program_cell_id": "single-cell",
            "terminal_class": "bounded",
            "fact_layer": [],
            "judgment_layer": [
                {"claim_id": "claim-1", "epistemic_status": "hypothesis"}
            ],
            "what_would_change": [
                {"task_id": "task-1", "claim_id": "claim-1"}
            ],
        }
    ]
    surface = CellScopedResearchIdentityPolicy.derive_surface(specialists)
    assert isinstance(surface, dict)
    table = CompactScopedReferenceAliasTable.from_surface(surface)
    assert isinstance(table, CompactScopedReferenceAliasTable)
    profile = replace(
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        profile_ref="fixture.research_profile.minimum:v2",
        company="MIN",
        program_cell_ids=("single-cell",),
        maximum_cell_count=1,
    )
    digests = {"single-cell": canonical_digest(specialists[0])}
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=profile,
    )
    capacity = (
        DeepSeekS3ThreeCellNodeExecutor
        ._research_lead_v5_capacity_envelope(
            alias_table=table,
            cell_heads=heads,
            research_profile=profile,
        )
    )
    assert capacity["exact_claim_alias_count"] == 1
    assert capacity["exact_what_would_change_alias_count"] == 1
    assert canonical_digest(capacity) == (
        "ae3963f35f8eb3f9624f143f8c6f0e7897b51a3b56ab5f8e6ddaa45d64c41d7a"
    )


@pytest.mark.parametrize(
    "updates",
    (
        {
            "research_lead_provider_raw_max_utf8_bytes": 4439,
            "research_lead_canonical_alias_max_utf8_bytes": 4439,
        },
        {"research_lead_canonical_alias_max_utf8_bytes": 4865},
        {"research_lead_local_expanded_hard_max_utf8_bytes": 12252},
    ),
)
def test_adversarial_capacity_profile_fails_closed(
    updates: dict[str, int],
) -> None:
    _, _, table, heads, _ = _surface_and_capacity()
    profile = replace(
        S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V2,
        **updates,
    )
    with pytest.raises(
        ValueError,
        match="profile_capacity_not_closed",
    ):
        (
            DeepSeekS3ThreeCellNodeExecutor
            ._research_lead_v5_capacity_envelope(
                alias_table=table,
                cell_heads=heads,
                research_profile=profile,
            )
        )


def test_non_nvda_different_period_and_reference_counts_generalize() -> None:
    specialists = [
        {
            "program_cell_id": "amd-margin",
            "terminal_class": "bounded",
            "period": "FY2027-Q1-53W",
            "fact_layer": [],
            "judgment_layer": [
                {"claim_id": "claim-a", "epistemic_status": "hypothesis"},
                {"claim_id": "claim-b", "epistemic_status": "cannot_infer"},
            ],
            "what_would_change": [
                {"task_id": "task-a", "claim_id": "claim-a"},
            ],
        },
        {
            "program_cell_id": "amd-supply",
            "terminal_class": "bounded",
            "period": "FY2027-Q1-53W",
            "fact_layer": [],
            "judgment_layer": [
                {"claim_id": "claim-c", "epistemic_status": "bounded_inference"},
            ],
            "what_would_change": [
                {"task_id": "task-b", "claim_id": "claim-c"},
                {"task_id": "task-c", "claim_id": "claim-c"},
            ],
        },
    ]
    surface = CellScopedResearchIdentityPolicy.derive_surface(specialists)
    assert isinstance(surface, dict)
    table = CompactScopedReferenceAliasTable.from_surface(surface)
    assert isinstance(table, CompactScopedReferenceAliasTable)
    profile = BoundedResearchProfile(
        profile_ref="fixture.research_profile.amd_two_cell:v2",
        company="AMD",
        program_cell_ids=("amd-margin", "amd-supply"),
        maximum_cell_count=2,
        maximum_narrative_characters=200,
        specialist_segment_max_utf8_bytes=4096,
        specialist_assembly_max_utf8_bytes=6144,
        specialist_segment_token_budgets=(("segment", 700),),
        owner_grade_stage_token_budgets=(("lead", 800),),
        owner_grade_lead_v2_stage_token_budgets=(("lead", 1000),),
        owner_grade_aggregate_output_tokens=800,
        owner_grade_lead_v2_aggregate_output_tokens=1000,
        research_lead_provider_raw_max_utf8_bytes=8192,
        research_lead_canonical_alias_max_utf8_bytes=6000,
        research_lead_local_expanded_hard_max_utf8_bytes=32768,
        research_lead_aggregate_narrative_max_characters=2000,
        research_lead_local_capacity_formula_ref=(
            "fin01.s3.research_lead_local_capacity."
            "exact_surface_maximum_valid_shape:v1"
        ),
    )
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=profile,
    )
    capacity = (
        DeepSeekS3ThreeCellNodeExecutor
        ._research_lead_v5_capacity_envelope(
            alias_table=table,
            cell_heads=heads,
            research_profile=profile,
        )
    )
    assert capacity["exact_claim_alias_count"] == 3
    assert capacity["exact_what_would_change_alias_count"] == 3
    assert {row.alias for row in table.rows} == {
        "C001",
        "C002",
        "C003",
        "W001",
        "W002",
        "W003",
    }


def test_v5_full_fake_provider_expands_before_writer_verifier_and_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cells, specialists = _shared_local_id_specialists()
    input_pack = _input_pack(cells)
    admission = _v5_admission(input_pack)
    fake = _CompactV5FullFakeProvider(
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
        run_identity={
            "research_run_id": "fixture-run-research-lead-v5",
            "attempt_id": "fixture-attempt-research-lead-v5",
        },
    )

    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    judgment = next(
        row.payload
        for row in result.artifacts
        if row.artifact_type == BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE
    )
    report = next(
        row.payload["report"]
        for row in result.artifacts
        if row.artifact_type == BOUNDED_AGENT_REPORT_ARTIFACT_TYPE
    )
    assert "C001" not in json.dumps(judgment, ensure_ascii=False)
    assert "W001" not in json.dumps(report, ensure_ascii=False)
    assert all(
        set(ref) == {"identity_kind", "program_cell_id", "local_id"}
        for ref in judgment["cross_cell_lead"]["variant_view"]["claim_ids"]
    )


def test_zero_call_result_and_next_authority_are_frozen() -> None:
    result = json.loads(
        (
            ROOT
            / "configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation_v1_0.json"
        ).read_text(encoding="utf-8")
    )
    backlog = json.loads(
        (
            ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
        ).read_text(encoding="utf-8")
    )
    assert result["status"].startswith("pass_zero_call_")
    assert set(result["observed_counts"].values()) == {0}
    assert result["next_action"] == (
        "S3-T09-OWNER-GRADE-RESEARCH-LEAD-V5-FRESH-AGENT-PROOF-DECISION"
    )
    assert backlog["next_action"][
        "research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation_authorized"
    ] is True
    assert backlog["next_action"][
        "research_lead_v5_fresh_agent_proof_decision_authorized"
    ] is True
    assert backlog["next_action"][
        "S3_T09_research_lead_v5_fresh_agent_proof_decision_ref"
    ] == (
        "configs/releases/fin_ia_0_1_s3_t09_research_lead_v5_"
        "fresh_agent_proof_decision_v1_0.json"
    )
    assert backlog["next_action"]["agent_execution_authorized"] is False
