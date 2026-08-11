from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from test_fin_0_1_s4_t06_mu_deterministic_judgment_atom_planner_compiled_contract_implementation import (
    _adapted_mu_value_cell,
    _compiled_runtime,
)


CLAIM_SEGMENT = "owner_grade_claim_cards"
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_claim_epistemic_support_"
    "role_compiled_contract_v2_minimum_zero_call_implementation_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v2_runtime(ticker: str) -> tuple[Any, Any, Any]:
    input_pack, v1_admission, fake = _compiled_runtime(ticker)
    admission = v1_admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t06-{ticker.lower()}-claim-support-role-v2"
            ),
            "execution_mode": "zero_call_claim_support_role_v2",
            "judgment_atom_compiled_contract_ref": (
                S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
            ),
        }
    )
    admission.assert_profile_admissible()
    return input_pack, admission, fake


def _claim_compiler(ticker: str = "MU") -> tuple[Any, Any, str]:
    input_pack, _, _ = _v2_runtime(ticker)
    cell = input_pack.cell_inputs[0]
    fact_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
        contract_ref=S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
    )
    fact_output = fact_compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    facts = fact_compiler.assemble(
        "facts_explanation_and_terminal",
        fact_output,
        provider_output_utf8_bytes=len(
            json.dumps(fact_output).encode("utf-8")
        ),
    )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={"facts_explanation_and_terminal": facts},
        as_of=input_pack.as_of,
        contract_ref=S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
    )
    alias = compiler.model_visible_contract(CLAIM_SEGMENT)[
        "allowed_facts"
    ][0]["fact_alias"]
    return compiler, cell, alias


def _atom(
    *,
    aliases: list[str],
    claim_kind: str,
    direction: str = "unknown",
    priority: str = "high",
) -> dict[str, Any]:
    return {
        "support_fact_aliases": aliases,
        "claim_kind": claim_kind,
        "direction": direction,
        "materiality": "high",
        "confidence": "high",
        "priority": priority,
    }


def _assemble(
    compiler: DeterministicJudgmentAtomCompiledContract,
    cell_id: str,
    atoms: list[dict[str, Any]],
) -> dict[str, Any]:
    output = {
        "program_cell_id": cell_id,
        "claim_candidate_atoms": atoms,
    }
    return compiler.assemble(
        CLAIM_SEGMENT,
        output,
        provider_output_utf8_bytes=len(
            json.dumps(output).encode("utf-8")
        ),
    )


def test_v1_surface_and_system_instruction_remain_byte_for_byte_compatible() -> None:
    v2_compiler, cell, _ = _claim_compiler()
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments=v2_compiler.validated_segments,
        as_of=v2_compiler.as_of,
    )
    contract = compiler.model_visible_contract(CLAIM_SEGMENT)
    assert compiler.contract_ref == (
        S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
    )
    assert "claim_kind_support_role_rules" not in contract
    assert compiler.wire_schema(CLAIM_SEGMENT)[
        "claim_candidate_atoms"
    ][0]["support_fact_aliases"] == [
        "zero or more exact allowed fact aliases"
    ]
    assert compiler.provider_system_instruction(CLAIM_SEGMENT) == (
        "Return exactly one native JSON object matching "
        "required_output_schema. Emit only exact request-local aliases "
        "and closed enum values listed in "
        "compiled_judgment_atom_contract. Do not emit final prose, "
        "material numbers, periods, thresholds, calendar dates, case "
        "identity, canonical IDs, raw refs, lineage, markdown, or extra "
        "fields. The local deterministic planner owns validation, "
        "selection, ordering, rendering, and final cardinality."
    )


def test_persisted_v2_implementation_binds_current_runtime_and_scope() -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    assert implementation["status"] == (
        "pass_claim_contract_v2_runtime_injected_three_case_fixture_"
        "proven_independent_fresh_proof_pending"
    )
    assert implementation["implemented_contract"]["contract_ref"] == (
        S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
    )
    assert implementation["implemented_contract"]["scope"] == (
        "claim_candidate_atoms_only"
    )
    assert implementation["implemented_contract"][
        "historical_v1_semantics_changed"
    ] is False
    assert implementation["observed_counts"][
        "model_provider_network_source_calls"
    ] == [0, 0, 0, 0]
    assert implementation["stage_acceptance"]["second_claim_canary"] == (
        "forbidden_consumed_quota"
    )
    for binding in implementation["runtime_changes"].values():
        path = ROOT / binding["ref"]
        assert _sha256(path) == binding["sha256"]


def test_v2_one_rule_source_projects_to_every_claim_contract_surface() -> None:
    compiler, _, _ = _claim_compiler()
    rule = compiler.claim_kind_support_role_contract()
    contract = compiler.model_visible_contract(CLAIM_SEGMENT)
    surface = compiler.compiled_surface(CLAIM_SEGMENT)
    wire = surface["wire_schema"]["claim_candidate_atoms"][0]
    system = compiler.provider_system_instruction(CLAIM_SEGMENT)
    assert contract["contract_ref"] == (
        S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF
    )
    assert contract["claim_kind_support_role_rules"] == rule
    assert surface["local_validator"][
        "claim_kind_support_role_rules"
    ] == rule
    assert surface["selector"]["claim_kind_support_role_rules"] == rule
    assert surface["failure_descriptor"]["conditional_failure"] == {
        "rule_id": rule["rule_id"],
        "code": rule["invalid_failure_code"],
    }
    assert "exactly [] when claim_kind=insufficient_evidence" in (
        wire["support_fact_aliases"][0]
    )
    assert "insufficient_evidence requires support_fact_aliases" in system
    assert "never emit insufficient_evidence with support aliases" in system
    assert surface["fake_provider_fixture"]["claim_candidate_atoms"] == [
        _atom(
            aliases=[
                contract["allowed_facts"][0]["fact_alias"]
            ],
            claim_kind="evidence_direction",
        ),
        _atom(
            aliases=[],
            claim_kind="insufficient_evidence",
            priority="normal",
        )
        | {"materiality": "medium", "confidence": "medium"},
    ]


def test_v2_both_legal_epistemic_routes_render_deterministically() -> None:
    compiler, cell, alias = _claim_compiler()
    assembled = _assemble(
        compiler,
        cell["program_cell_id"],
        [
            _atom(
                aliases=[alias],
                claim_kind="evidence_direction",
                direction="unknown",
            ),
            _atom(
                aliases=[],
                claim_kind="insufficient_evidence",
                priority="normal",
            ),
        ],
    )
    claims = assembled["judgment_layer"]
    assert [claim["epistemic_status"] for claim in claims] == [
        "bounded_inference",
        "cannot_infer",
    ]
    assert claims[0]["support_fact_aliases"] == [alias]
    assert claims[0]["cannot_support"]
    assert claims[1]["support_fact_aliases"] == []
    assert claims[1]["cannot_support"] == [
        "当前绑定事实不足以支持更强结论"
    ]
    expanded, violation = compiler._claim_policy().expand_claim_output(
        assembled
    )
    assert violation is None
    assert expanded is not None
    assert expanded["judgment_layer"][0]["support_fact_ids"]
    assert expanded["judgment_layer"][1]["support_fact_ids"] == []


@pytest.mark.parametrize(
    ("claim_kind", "direction", "expected_status"),
    (
        ("economic_mechanism", "supports", "fact_supported"),
        ("counterevidence", "challenges", "fact_supported"),
    ),
)
def test_v2_supported_judgment_kinds_keep_exact_support(
    claim_kind: str,
    direction: str,
    expected_status: str,
) -> None:
    compiler, cell, alias = _claim_compiler()
    assembled = _assemble(
        compiler,
        cell["program_cell_id"],
        [
            _atom(
                aliases=[alias],
                claim_kind=claim_kind,
                direction=direction,
            )
        ],
    )
    claim = assembled["judgment_layer"][0]
    assert claim["epistemic_status"] == expected_status
    assert claim["support_fact_aliases"] == [alias]
    expanded, violation = compiler._claim_policy().expand_claim_output(
        assembled
    )
    assert violation is None
    assert expanded is not None
    assert len(expanded["judgment_layer"][0]["support_fact_ids"]) == 1


@pytest.mark.parametrize(
    ("claim_kind", "aliases_factory"),
    (
        ("insufficient_evidence", lambda alias: [alias]),
        ("evidence_direction", lambda alias: []),
        ("economic_mechanism", lambda alias: [alias, alias]),
        ("counterevidence", lambda alias: []),
    ),
)
def test_v2_invalid_kind_support_combinations_fail_with_typed_code(
    claim_kind: str,
    aliases_factory: Any,
) -> None:
    compiler, cell, alias = _claim_compiler()
    with pytest.raises(
        ValueError,
        match="s4_compiled_claim_atom_epistemic_support_role_invalid",
    ):
        _assemble(
            compiler,
            cell["program_cell_id"],
            [
                _atom(
                    aliases=aliases_factory(alias),
                    claim_kind=claim_kind,
                )
            ],
        )


def test_v2_unknown_alias_still_fails_as_cross_case_not_role_error() -> None:
    compiler, cell, _ = _claim_compiler()
    with pytest.raises(
        ValueError,
        match="s4_compiled_claim_atom_alias_unknown_or_cross_case",
    ):
        _assemble(
            compiler,
            cell["program_cell_id"],
            [
                _atom(
                    aliases=["F-CROSS-CASE"],
                    claim_kind="evidence_direction",
                )
            ],
        )


def test_v2_runtime_typed_failure_preserves_terminal_claim_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, fake = _v2_runtime("MU")
    original = fake.__call__

    def invalid(**kwargs: Any) -> Any:
        result = dict(original(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request.get("compiled_judgment_atom_contract")
        if (
            isinstance(contract, dict)
            and contract.get("family_id") == "claim_candidate_atoms"
        ):
            output = json.loads(result["content"])
            output["claim_candidate_atoms"][0]["claim_kind"] = (
                "insufficient_evidence"
            )
            result["content"] = json.dumps(output)
        return result

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    with pytest.raises(BoundedAgentExecutionError) as exc_info:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=invalid,
        ).execute(
            input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-claim-support-role-v2-invalid",
                "attempt_id": "fixture-claim-support-role-v2-invalid",
            },
        )
    error = exc_info.value
    assert any(
        "s4_compiled_claim_atom_epistemic_support_role_invalid"
        in code
        for code in error.failure_observation["failure_codes"]
    )
    assert len(error.provider_output_captures) == 2
    terminal_capture = error.provider_output_captures[-1]
    assert terminal_capture["assistant_output_present"] is True
    assert "insufficient_evidence" in terminal_capture[
        "assistant_output_text"
    ]


def test_v2_mixed_scope_candidate_is_not_silently_promoted() -> None:
    compiler, cell, alias = _claim_compiler()
    mutated = deepcopy(compiler._claim_policy().alias_rows[0])
    object.__setattr__(
        mutated,
        "locally_assembled_scope_summary",
        {"entity": "mixed"},
    )
    original = compiler._claim_policy

    class _Policy:
        alias_rows = (mutated,)

    compiler._claim_policy = lambda: _Policy()  # type: ignore[method-assign]
    try:
        with pytest.raises(
            ValueError,
            match="s4_compiled_claim_atom_no_valid_scope_compatible_subset",
        ):
            _assemble(
                compiler,
                cell["program_cell_id"],
                [
                    _atom(
                        aliases=[alias],
                        claim_kind="evidence_direction",
                    )
                ],
            )
    finally:
        compiler._claim_policy = original  # type: ignore[method-assign]


def test_v2_conflicting_concrete_scopes_are_filtered_before_selection() -> None:
    input_pack, cell = _adapted_mu_value_cell()
    fact_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
        contract_ref=S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
    )
    numeric_rows = list(fact_compiler.numeric_policy.rows)
    left = next(
        row
        for row in numeric_rows
        if row.business_scope_ref == "__company_total__"
    )
    right = next(
        row
        for row in numeric_rows
        if row.business_scope_ref != "__company_total__"
    )
    facts = fact_compiler.assemble(
        "facts_explanation_and_terminal",
        {
            "program_cell_id": cell["program_cell_id"],
            "fact_atoms": [
                {
                    "support_alias": row.alias,
                    "causal_relation": "supports",
                    "materiality": "high",
                    "confidence": "high",
                    "priority": "high",
                }
                for row in (left, right)
            ],
            "terminal_class": "supported",
        },
        provider_output_utf8_bytes=500,
    )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={"facts_explanation_and_terminal": facts},
        as_of=input_pack.as_of,
        contract_ref=S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_V2_REF,
    )
    aliases = [
        row["fact_alias"]
        for row in compiler.model_visible_contract(CLAIM_SEGMENT)[
            "allowed_facts"
        ]
    ]
    with pytest.raises(
        ValueError,
        match="s4_compiled_claim_atom_no_valid_scope_compatible_subset",
    ):
        _assemble(
            compiler,
            cell["program_cell_id"],
            [
                _atom(
                    aliases=aliases,
                    claim_kind="economic_mechanism",
                )
            ],
        )


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_v2_three_case_full_fake_reaches_6_nodes_12_captures_9_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission, fake = _v2_runtime(ticker)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": (
                f"fixture-s4-t06-{ticker.lower()}-claim-support-role-v2"
            ),
            "attempt_id": (
                f"fixture-s4-t06-{ticker.lower()}-claim-support-role-v2"
            ),
        },
    )
    assert len(
        {call["request"]["node_id"] for call in fake.calls}
    ) == 6
    assert len(fake.calls) == 12
    assert fake.compiled_calls == 9
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    claim_requests = [
        call["request"]
        for call in fake.calls
        if call["request"].get(
            "compiled_judgment_atom_contract", {}
        ).get("family_id") == "claim_candidate_atoms"
    ]
    assert len(claim_requests) == 3
    assert all(
        "claim_kind_support_role_rules"
        in request["compiled_judgment_atom_contract"]
        for request in claim_requests
    )
    assert all(
        "insufficient_evidence requires support_fact_aliases"
        in call["kwargs"]["messages"][0]["content"]
        for call in fake.calls
        if call["request"].get(
            "compiled_judgment_atom_contract", {}
        ).get("family_id") == "claim_candidate_atoms"
    )
