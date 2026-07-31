from __future__ import annotations

from copy import deepcopy
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
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from apps.workbench.backend.application.fact_candidate_pool_planner import (
    FACT_CANDIDATE_POOL_PLAN_REF,
    FACT_CANDIDATE_POOL_PROFILE_REF,
    FactCandidatePoolPlanner,
    FactCandidatePoolPlannerError,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    _compiled_runtime,
)


PROFILE_SET = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_fact_candidate_pool_profiles_v1_0.json"
)


def _single_slot_profile(
    *,
    research_profile_ref: str = "fin01.s4.research_profile.fixture:v1",
    program_cell_id: str = "fixture_cell",
    minimum_coverage: int = 0,
) -> dict[str, Any]:
    return {
        "profile_contract_ref": FACT_CANDIDATE_POOL_PROFILE_REF,
        "research_profile_ref": research_profile_ref,
        "program_cell_id": program_cell_id,
        "coverage_slots": [
            {
                "coverage_slot_id": "fixture_coverage",
                "coverage_slot_priority": 10,
                "eligible_support_kinds": ["Evidence"],
                "eligible_semantic_roles": ["fixture_role"],
                "authority_preference": ["Evidence", "Numeric"],
                "scope_preference": [
                    "issuer_exact",
                    "company_total",
                    "segment",
                    "product",
                    "unknown",
                ],
                "minimum_coverage": minimum_coverage,
                "maximum_selected_from_slot": 6,
            }
        ],
        "audit_only_rules": [],
    }


def _planner(
    profile: Mapping[str, Any] | None = None,
) -> FactCandidatePoolPlanner:
    payload = dict(profile or _single_slot_profile())
    return FactCandidatePoolPlanner(
        research_profile_ref=str(payload["research_profile_ref"]),
        program_cell_id=str(payload["program_cell_id"]),
        profile_payload=payload,
        profile_set_digest="f" * 64,
    )


def _catalog_row(ordinal: int, *, role: str = "fixture_role") -> dict[str, str]:
    row = {
        "alias": f"E{ordinal:03d}",
        "authority_ref": f"fixture-authority-{ordinal:03d}",
        "statement": f"fixture statement {ordinal:03d}",
        "boundary": f"fixture boundary {ordinal:03d}",
        "role": role,
        "support_kind": "Evidence",
        "authority_kind": "Evidence",
        "scope_kind": "issuer_exact",
    }
    row["canonical_support_digest"] = canonical_digest(row)
    return row


def _adapted_cell(
    ticker: str,
    cell_index: int,
) -> tuple[Any, Any, Mapping[str, Any]]:
    input_pack, admission, _ = _compiled_runtime(ticker)
    cell = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
        input_pack.cell_inputs[cell_index],
        policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    )
    return input_pack, admission, cell


@pytest.mark.parametrize(
    ("catalog_count", "visible_count"),
    ((1, 1), (3, 3), (6, 6), (7, 6), (22, 6)),
)
def test_catalog_cardinality_is_bounded_before_provider(
    catalog_count: int,
    visible_count: int,
) -> None:
    plan = _planner().plan(
        [_catalog_row(ordinal) for ordinal in range(1, catalog_count + 1)]
    )
    assert plan.contract_ref == FACT_CANDIDATE_POOL_PLAN_REF
    assert plan.eligible_support_count == catalog_count
    assert plan.candidate_pool_count == visible_count
    assert plan.omitted_eligible_support_count == (
        catalog_count - visible_count
    )
    if catalog_count <= 6:
        assert {row["alias"] for row in plan.candidate_rows} == {
            f"E{ordinal:03d}"
            for ordinal in range(1, catalog_count + 1)
        }


def test_zero_catalog_fails_closed_before_provider() -> None:
    with pytest.raises(
        FactCandidatePoolPlannerError,
        match="s4_fact_candidate_pool_empty",
    ) as exc_info:
        _planner().plan([])
    assert exc_info.value.telemetry["provider_calls"] == 0
    assert exc_info.value.telemetry["raw_fact_text_persisted"] is False
    assert exc_info.value.telemetry["raw_numeric_value_persisted"] is False


def test_catalog_permutation_has_identical_pool_and_digest() -> None:
    rows = [_catalog_row(ordinal) for ordinal in range(1, 23)]
    forward = _planner().plan(rows)
    reverse = _planner().plan(list(reversed(rows)))
    assert forward.candidate_pool_digest == reverse.candidate_pool_digest
    assert forward.eligible_catalog_digest == reverse.eligible_catalog_digest
    assert forward.candidate_rows == reverse.candidate_rows


def test_unknown_and_overlapping_semantic_roles_fail_closed() -> None:
    with pytest.raises(
        FactCandidatePoolPlannerError,
        match="unmapped_semantic_role",
    ):
        _planner().plan([_catalog_row(1, role="unknown_material_role")])

    profile = _single_slot_profile()
    duplicate_slot = deepcopy(profile["coverage_slots"][0])
    duplicate_slot["coverage_slot_id"] = "overlapping_coverage"
    duplicate_slot["coverage_slot_priority"] = 20
    profile["coverage_slots"].append(duplicate_slot)
    with pytest.raises(
        FactCandidatePoolPlannerError,
        match="overlapping_slot_mapping",
    ):
        _planner(profile).plan([_catalog_row(1)])


def test_profile_scope_minimum_and_registry_digest_fail_closed(
    tmp_path: Path,
) -> None:
    mismatched = _single_slot_profile(
        research_profile_ref="fin01.s4.research_profile.other:v1"
    )
    with pytest.raises(
        FactCandidatePoolPlannerError,
        match="profile_scope_mismatch",
    ):
        FactCandidatePoolPlanner(
            research_profile_ref="fin01.s4.research_profile.fixture:v1",
            program_cell_id="fixture_cell",
            profile_payload=mismatched,
            profile_set_digest="f" * 64,
        )

    minimum_over_capacity = _single_slot_profile(minimum_coverage=4)
    second = deepcopy(minimum_over_capacity["coverage_slots"][0])
    second["coverage_slot_id"] = "second_slot"
    second["eligible_semantic_roles"] = ["second_role"]
    minimum_over_capacity["coverage_slots"].append(second)
    with pytest.raises(
        FactCandidatePoolPlannerError,
        match="minimum_over_capacity",
    ):
        _planner(minimum_over_capacity)

    registry = json.loads(PROFILE_SET.read_text(encoding="utf-8"))
    registry["profile_set_digest"] = "0" * 64
    invalid_registry = tmp_path / "invalid_profile_set.json"
    invalid_registry.write_text(
        json.dumps(registry, ensure_ascii=False),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="profile_set_digest_mismatch",
    ):
        FactCandidatePoolPlanner.from_registry(
            research_profile_ref=(
                "fin01.s4.research_profile.mu_hbm_three_cell:v1"
            ),
            program_cell_id="value_and_profit_capture",
            registry_path=invalid_registry,
        )


def test_mu_value_cell_exposes_six_of_twenty_two_and_accepts_all_six() -> None:
    input_pack, admission, cell = _adapted_cell("MU", 1)
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
        contract_ref=str(admission.judgment_atom_compiled_contract_ref),
        research_profile_ref=str(admission.research_profile_ref),
    )
    contract = compiler.model_visible_contract(
        "facts_explanation_and_terminal"
    )
    plan = compiler.fact_candidate_pool_plan()
    assert plan is not None
    assert plan.eligible_support_count == 22
    assert plan.candidate_pool_count == 6
    assert len(contract["allowed_supports"]) == 6
    assert contract["eligible_support_count"] == 22
    assert contract["visible_support_count"] == 6
    assert contract["fact_candidate_pool_digest"] == (
        plan.candidate_pool_digest
    )
    output = {
        "program_cell_id": cell["program_cell_id"],
        "fact_atoms": [
            {
                "support_alias": row["support_alias"],
                "causal_relation": "supports",
                "materiality": "high",
                "confidence": "high",
                "priority": "high",
            }
            for row in contract["allowed_supports"]
        ],
        "terminal_class": "supported",
    }
    assembled = compiler.assemble(
        "facts_explanation_and_terminal",
        output,
        provider_output_utf8_bytes=len(
            json.dumps(output, ensure_ascii=False).encode("utf-8")
        ),
    )
    assert len(assembled["fact_layer"]) == 3


def test_hidden_duplicate_and_seventh_provider_candidates_fail_closed() -> None:
    input_pack, admission, cell = _adapted_cell("MU", 1)
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
        contract_ref=str(admission.judgment_atom_compiled_contract_ref),
        research_profile_ref=str(admission.research_profile_ref),
    )
    contract = compiler.model_visible_contract(
        "facts_explanation_and_terminal"
    )
    visible = {
        row["support_alias"] for row in contract["allowed_supports"]
    }
    hidden = next(
        row["alias"]
        for row in compiler._fact_catalog()
        if row["alias"] not in visible
    )
    baseline = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    baseline["fact_atoms"][0]["support_alias"] = hidden
    with pytest.raises(ValueError, match="alias_unknown_or_duplicate"):
        compiler.assemble(
            "facts_explanation_and_terminal",
            baseline,
            provider_output_utf8_bytes=200,
        )

    duplicate = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    duplicate["fact_atoms"].append(deepcopy(duplicate["fact_atoms"][0]))
    with pytest.raises(ValueError, match="alias_unknown_or_duplicate"):
        compiler.assemble(
            "facts_explanation_and_terminal",
            duplicate,
            provider_output_utf8_bytes=200,
        )

    seventh = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    atom = seventh["fact_atoms"][0]
    seventh["fact_atoms"] = [
        {**atom, "support_alias": row["support_alias"]}
        for row in contract["allowed_supports"]
    ] + [deepcopy(atom)]
    with pytest.raises(ValueError, match="shape_invalid"):
        compiler.assemble(
            "facts_explanation_and_terminal",
            seventh,
            provider_output_utf8_bytes=500,
        )


def test_pre_provider_profile_fault_is_typed_and_makes_zero_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, fake = _compiled_runtime("MU")
    cells = deepcopy(input_pack.cell_inputs)
    candidates = cells[0]["evidence_input"]["candidate_bundle"][
        "candidates"
    ]
    candidates[0]["evidence_role"] = "unknown_material_role"
    mutated = input_pack.model_copy(update={"cell_inputs": cells})
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as exc_info:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            mutated,
            admission,
            run_identity={
                "research_run_id": "fixture-fact-pool-pre-provider-fault",
                "attempt_id": "fixture-fact-pool-pre-provider-fault",
            },
        )
    assert len(fake.calls) == 0
    observation = exc_info.value.failure_observation
    assert observation["observed_counts"]["provider_calls"] == 0
    telemetry = observation["failure_telemetry"][
        "fact_candidate_pool"
    ]
    assert telemetry["failure_phase"] == (
        "pre_provider_fact_candidate_pool_planning"
    )
    assert telemetry["provider_calls"] == 0


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_zero_call_full_chain_remains_6_12_12_9(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission, fake = _compiled_runtime(ticker)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": f"fixture-{ticker.lower()}-fact-pool-v1",
            "attempt_id": f"fixture-{ticker.lower()}-fact-pool-v1",
        },
    )
    assert len(
        result.execution_observation["completed_node_receipts"]
    ) == 6
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    fact_requests = [
        row["request"]
        for row in fake.calls
        if row["request"].get("compiled_judgment_atom_contract", {}).get(
            "family_id"
        )
        == "specialist_fact_atoms"
    ]
    assert len(fact_requests) == 3
    assert all(
        1
        <= len(
            request["compiled_judgment_atom_contract"][
                "allowed_supports"
            ]
        )
        <= 6
        for request in fact_requests
    )
