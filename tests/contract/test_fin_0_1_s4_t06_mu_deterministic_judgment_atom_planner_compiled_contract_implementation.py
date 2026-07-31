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
    S3_TASK_CLAIM_LINK_POLICY_REF,
    S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF,
    S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF,
    estimate_provider_input_tokens,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BoundedAgentExecutionError,
    S3ThreeCellBoundedAgentExecutor,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s4_t06_mu_current_case_aware_delivery_identity_boundary_zero_call_implementation import (
    _case_runtime,
)


class _CompiledAtomFake:
    def __init__(self, base: Any) -> None:
        self.base = base
        self.compiled_calls = 0
        self.compiled_outputs: list[dict[str, Any]] = []

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.base.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request.get("compiled_judgment_atom_contract")
        if not isinstance(contract, Mapping):
            return dict(self.base(**kwargs))
        self.calls.append({"kwargs": dict(kwargs), "request": request})
        family = contract["family_id"]
        cell_id = contract["program_cell_id"]
        if family == "specialist_fact_atoms":
            supports = contract["allowed_supports"]
            selected = next(
                (
                    row
                    for row in supports
                    if row["support_kind"] == "Numeric"
                ),
                supports[0],
            )
            output = {
                "program_cell_id": cell_id,
                "fact_atoms": [
                    {
                        "support_alias": selected["support_alias"],
                        "causal_relation": "supports",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
                "terminal_class": "supported",
            }
        elif family == "claim_candidate_atoms":
            alias = contract["allowed_facts"][0]["fact_alias"]
            if "claim_kind_support_role_rules" in contract:
                output = {
                    "program_cell_id": cell_id,
                    "claim_candidate_atoms": [
                        {
                            "support_fact_aliases": [alias],
                            "claim_kind": "evidence_direction",
                            "direction": "unknown",
                            "materiality": "high",
                            "confidence": "high",
                            "priority": "high",
                        },
                    ],
                }
            else:
                output = {
                    "program_cell_id": cell_id,
                    "claim_candidate_atoms": [
                        {
                            "support_fact_aliases": [alias],
                            "claim_kind": "economic_mechanism",
                            "direction": "supports",
                            "materiality": "high",
                            "confidence": "high",
                            "priority": "high",
                        }
                    ],
                }
        else:
            claim = contract["allowed_claims"][0]["claim_alias"]
            authority = contract["allowed_authorities"][0][
                "authority_alias"
            ]
            patterns = (
                (
                    "authority_contradiction",
                    "challenges",
                    "next_authority_event",
                    "weaken",
                ),
                (
                    "authority_confirmation",
                    "supports",
                    "next_reporting_event",
                    "strengthen",
                ),
                (
                    "bounded_event_occurs",
                    "mixed",
                    "next_month_end",
                    "resolve_cannot_infer",
                ),
                (
                    "trend_persists",
                    "unknown",
                    "next_quarter_end",
                    "no_change",
                ),
                (
                    "authority_contradiction",
                    "challenges",
                    "unscheduled",
                    "invalidate",
                ),
                (
                    "authority_confirmation",
                    "supports",
                    "next_quarter_end",
                    "strengthen",
                ),
            )
            output = {
                "program_cell_id": cell_id,
                "what_would_change_atoms": [
                    {
                        "claim_alias": claim,
                        "primary_authority_alias": authority,
                        "authority_aliases": [authority],
                        "trigger_code": trigger,
                        "direction": direction,
                        "review_cadence": cadence,
                        "start_date_alias": "NONE",
                        "review_date_alias": "NONE",
                        "expected_claim_transition": transition,
                    }
                    for trigger, direction, cadence, transition in patterns
                ],
            }
        self.compiled_calls += 1
        self.compiled_outputs.append(output)
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(
                output,
                ensure_ascii=False,
                sort_keys=True,
            ),
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "call_id": f"fixture-compiled-atom-{len(self.calls)}",
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "latency_ms": 1,
            "transport_attempt_count": 1,
            "raw_response": {
                "usage": {
                    "prompt_cache_hit_tokens": 0,
                    "prompt_cache_miss_tokens": 10,
                }
            },
        }


def _compiled_runtime(ticker: str) -> tuple[Any, Any, _CompiledAtomFake]:
    input_pack, admission, base = _case_runtime(ticker)
    compiled = admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t06-{ticker.lower()}-compiled-atom-v1"
            ),
            "execution_mode": "zero_call_compiled_judgment_atom_v1",
            "judgment_atom_compiled_contract_ref": (
                S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
            ),
            "transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V8_REF
            ),
            "task_claim_link_policy_ref": (
                S3_TASK_CLAIM_LINK_POLICY_REF
            ),
            "wwc_judgment_atom_policy_ref": (
                S4_SPECIALIST_WWC_TEMPORAL_AUTHORITY_POLICY_REF
            ),
            "case_numeric_authority_policy_ref": (
                S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF
            ),
        }
    )
    compiled.assert_profile_admissible()
    return input_pack, compiled, _CompiledAtomFake(base)


def _wwc_compiler(
    ticker: str = "MU",
) -> tuple[
    Any,
    DeterministicJudgmentAtomCompiledContract,
    dict[str, Any],
]:
    input_pack, _, _ = _compiled_runtime(ticker)
    cell = input_pack.cell_inputs[0]
    prior: dict[str, Mapping[str, Any]] = {}
    for segment_id in (
        "facts_explanation_and_terminal",
        "owner_grade_claim_cards",
    ):
        compiler = DeterministicJudgmentAtomCompiledContract(
            cell_input=cell,
            validated_segments=prior,
            as_of=input_pack.as_of,
        )
        provider_output = compiler.fake_provider_output(segment_id)
        prior[segment_id] = compiler.assemble(
            segment_id,
            provider_output,
            provider_output_utf8_bytes=len(
                json.dumps(
                    provider_output,
                    ensure_ascii=False,
                    sort_keys=True,
                ).encode("utf-8")
            ),
        )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments=prior,
        as_of=input_pack.as_of,
    )
    output = compiler.fake_provider_output(
        "actionable_what_would_change_tasks"
    )
    return cell, compiler, output


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_compiled_atom_full_fake_reaches_12_calls_and_9_artifacts(
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
            "research_run_id": (
                f"fixture-s4-t06-{ticker.lower()}-compiled-atom-v1"
            ),
            "attempt_id": (
                f"fixture-s4-t06-{ticker.lower()}-compiled-atom-v1"
            ),
        },
    )
    assert len(fake.calls) == 12
    assert fake.compiled_calls == 9
    wwc_outputs = [
        output
        for output in fake.compiled_outputs
        if "what_would_change_atoms" in output
    ]
    assert len(wwc_outputs) == 3
    assert all(
        len(output["what_would_change_atoms"]) == 6
        for output in wwc_outputs
    )
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    provider_text = json.dumps(
        fake.compiled_outputs,
        ensure_ascii=False,
    )
    for forbidden in (
        "statement",
        "threshold_or_observation",
        "deadline_or_review_date",
        "authority_refs",
        "claim_id",
        "fact_id",
    ):
        assert forbidden not in provider_text


@pytest.mark.parametrize(
    ("candidate_count", "selected_count"),
    ((1, 1), (3, 3), (6, 3)),
)
def test_wwc_candidate_boundary_selects_at_most_three_after_validation(
    candidate_count: int,
    selected_count: int,
) -> None:
    cell, compiler, output = _wwc_compiler()
    output["what_would_change_atoms"] = output[
        "what_would_change_atoms"
    ][:candidate_count]
    assembled = compiler.assemble(
        "actionable_what_would_change_tasks",
        output,
        provider_output_utf8_bytes=len(
            json.dumps(output, ensure_ascii=False).encode("utf-8")
        ),
    )
    assert len(assembled["what_would_change"]) == selected_count
    assert [
        row["task_id"] for row in assembled["what_would_change"]
    ] == [
        (
            f"{cell['program_cell_id']}:what_would_change:"
            f"{ordinal:03d}"
        )
        for ordinal in range(1, selected_count + 1)
    ]


@pytest.mark.parametrize("candidate_count", (0, 7))
def test_wwc_candidate_count_outside_one_to_six_fails_closed(
    candidate_count: int,
) -> None:
    _, compiler, output = _wwc_compiler()
    atoms = output["what_would_change_atoms"]
    if candidate_count == 0:
        output["what_would_change_atoms"] = []
    else:
        output["what_would_change_atoms"] = [
            *atoms,
            deepcopy(atoms[0]),
        ]
    with pytest.raises(
        ValueError, match="s4_compiled_wwc_atom_shape_invalid"
    ):
        compiler.assemble(
            "actionable_what_would_change_tasks",
            output,
            provider_output_utf8_bytes=len(
                json.dumps(output, ensure_ascii=False).encode("utf-8")
            ),
        )


def test_wwc_validates_all_six_candidates_before_selection() -> None:
    _, compiler, baseline = _wwc_compiler()
    mutations = (
        (
            "unknown_claim",
            lambda output: output["what_would_change_atoms"][5].__setitem__(
                "claim_alias", "Q-CROSS-CASE"
            ),
            "claim_alias_unknown_or_cross_case",
        ),
        (
            "unknown_authority",
            lambda output: output["what_would_change_atoms"][5].__setitem__(
                "primary_authority_alias", "A-CROSS-CASE"
            ),
            "authority_alias_invalid",
        ),
        (
            "invalid_enum",
            lambda output: output["what_would_change_atoms"][5].__setitem__(
                "trigger_code", "provider_free_trigger"
            ),
            "enum_invalid:trigger_code",
        ),
        (
            "unbound_date",
            lambda output: output["what_would_change_atoms"][5].update(
                {
                    "review_cadence": "bound_date",
                    "review_date_alias": "D-CROSS-CASE",
                }
            ),
            "date_alias_unknown",
        ),
    )
    for mutation_id, mutate, expected in mutations:
        output = deepcopy(baseline)
        mutate(output)
        with pytest.raises(ValueError, match=expected) as exc_info:
            compiler.assemble(
                "actionable_what_would_change_tasks",
                output,
                provider_output_utf8_bytes=len(
                    json.dumps(
                        output, ensure_ascii=False
                    ).encode("utf-8")
                ),
            )
        assert expected in str(exc_info.value), mutation_id


def test_wwc_exact_duplicate_fails_before_selection() -> None:
    _, compiler, output = _wwc_compiler()
    output["what_would_change_atoms"][5] = deepcopy(
        output["what_would_change_atoms"][0]
    )
    with pytest.raises(ValueError, match="exact_duplicate"):
        compiler.assemble(
            "actionable_what_would_change_tasks",
            output,
            provider_output_utf8_bytes=len(
                json.dumps(output, ensure_ascii=False).encode("utf-8")
            ),
        )


def test_wwc_candidate_permutation_has_stable_selected_result() -> None:
    _, compiler, output = _wwc_compiler()
    reverse = deepcopy(output)
    reverse["what_would_change_atoms"] = list(
        reversed(reverse["what_would_change_atoms"])
    )
    rotated = deepcopy(output)
    rotated["what_would_change_atoms"] = [
        *rotated["what_would_change_atoms"][2:],
        *rotated["what_would_change_atoms"][:2],
    ]
    results = []
    for candidate_set in (output, reverse, rotated):
        results.append(
            compiler.assemble(
                "actionable_what_would_change_tasks",
                candidate_set,
                provider_output_utf8_bytes=len(
                    json.dumps(
                        candidate_set, ensure_ascii=False
                    ).encode("utf-8")
                ),
            )
        )
    assert results[0] == results[1] == results[2]


@pytest.mark.parametrize(
    ("request_marker", "expected_capture_count"),
    (
        ("research_lead_transport_ref", 10),
        ("memo_writer_transport_ref", 11),
        ("output_state_machine", 12),
    ),
)
def test_downstream_failure_preserves_all_prior_and_failing_capture(
    monkeypatch: pytest.MonkeyPatch,
    request_marker: str,
    expected_capture_count: int,
) -> None:
    input_pack, admission, fake = _compiled_runtime("MU")
    original = fake.__call__

    def invalid(**kwargs: Any) -> Mapping[str, Any]:
        result = dict(original(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if (
            request_marker in request
            and "compiled_judgment_atom_contract" not in request
        ):
            result["content"] = "{}"
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
                "research_run_id": (
                    f"fixture-downstream-{request_marker}"
                ),
                "attempt_id": f"fixture-downstream-{request_marker}",
            },
        )
    captures = exc_info.value.provider_output_captures
    assert len(captures) == expected_capture_count
    assert captures[-1]["assistant_output_present"] is True
    assert captures[-1]["capture_sequence"] == expected_capture_count


def test_compiler_generates_all_surfaces_from_one_version() -> None:
    input_pack, admission, _ = _compiled_runtime("MU")
    cell = input_pack.cell_inputs[0]
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
    )
    surface = compiler.compiled_surface(
        "facts_explanation_and_terminal"
    )
    assert surface["contract_ref"] == (
        S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
    )
    assert {
        "model_visible_contract",
        "wire_schema",
        "local_validator",
        "fake_provider_fixture",
        "selector",
        "renderer",
        "capacity",
        "budget",
        "failure_descriptor",
        "capture_safe_index_semantic_classes",
    }.issubset(surface)
    assert surface["budget"] == {
        "projected_input_unit": "estimated_input_tokens",
        "projected_output_unit": "reserved_output_tokens",
        "utf8_bytes_as_pricing_tokens": False,
    }
    assert admission.judgment_atom_compiled_contract_ref == (
        S4_DETERMINISTIC_JUDGMENT_ATOM_COMPILED_CONTRACT_REF
    )


def test_unknown_alias_and_arbitrary_narrative_fail_closed() -> None:
    input_pack, _, _ = _compiled_runtime("MU")
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=input_pack.cell_inputs[0],
        validated_segments={},
        as_of=input_pack.as_of,
    )
    output = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    output["fact_atoms"][0]["support_alias"] = "N-CROSS-CASE"
    with pytest.raises(
        ValueError,
        match="alias_unknown_or_duplicate",
    ):
        compiler.assemble(
            "facts_explanation_and_terminal",
            output,
            provider_output_utf8_bytes=100,
        )
    output = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    output["fact_atoms"][0]["final_sentence"] = "free narrative"
    with pytest.raises(ValueError, match="shape_invalid"):
        compiler.assemble(
            "facts_explanation_and_terminal",
            output,
            provider_output_utf8_bytes=100,
        )


def test_explicit_token_unit_estimator_is_not_utf8_byte_pricing() -> None:
    multibyte = "财务研究判断" * 100
    utf8_bytes = len(multibyte.encode("utf-8"))
    estimated_tokens = estimate_provider_input_tokens(multibyte)
    assert 0 < estimated_tokens < utf8_bytes
    assert estimated_tokens == estimate_provider_input_tokens(multibyte)


def _adapted_mu_value_cell() -> tuple[Any, Mapping[str, Any]]:
    input_pack, _, _ = _compiled_runtime("MU")
    raw = input_pack.cell_inputs[1]
    adapted = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
        raw,
        policy_ref=S4_CASE_MATERIAL_NUMERIC_CLASSIFIER_POLICY_REF,
    )
    return input_pack, adapted


def test_numeric_material_truth_is_selected_by_alias_and_rendered_locally() -> None:
    input_pack, cell = _adapted_mu_value_cell()
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
    )
    contract = compiler.model_visible_contract(
        "facts_explanation_and_terminal"
    )
    numeric_alias = next(
        row["support_alias"]
        for row in contract["allowed_supports"]
        if row["support_kind"] == "Numeric"
    )
    provider_output = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    provider_output["fact_atoms"][0]["support_alias"] = numeric_alias
    provider_text = json.dumps(provider_output, ensure_ascii=False)
    assert "exact_value" not in provider_text
    assembled = compiler.assemble(
        "facts_explanation_and_terminal",
        provider_output,
        provider_output_utf8_bytes=len(provider_text.encode("utf-8")),
    )
    row = next(
        item
        for item in compiler.numeric_policy.rows
        if item.alias == numeric_alias
    )
    assert assembled["fact_layer"][0]["statement"].startswith(
        row.rendered_clause()
    )
    assert assembled["fact_layer"][0]["support_refs"] == [
        row.numeric_ref
    ]


def test_selector_rejects_invalid_leading_mixed_scope_candidate() -> None:
    input_pack, cell = _adapted_mu_value_cell()
    first = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
    )
    numeric_rows = list(first.numeric_policy.rows)
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
    fact_output = {
        "program_cell_id": cell["program_cell_id"],
        "fact_atoms": [
            {
                "support_alias": left.alias,
                "causal_relation": "supports",
                "materiality": "high",
                "confidence": "high",
                "priority": "high",
            },
            {
                "support_alias": right.alias,
                "causal_relation": "supports",
                "materiality": "high",
                "confidence": "high",
                "priority": "high",
            },
        ],
        "terminal_class": "supported",
    }
    facts = first.assemble(
        "facts_explanation_and_terminal",
        fact_output,
        provider_output_utf8_bytes=400,
    )
    claim_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={
            "facts_explanation_and_terminal": facts
        },
        as_of=input_pack.as_of,
    )
    aliases = [
        row["fact_alias"]
        for row in claim_compiler.model_visible_contract(
            "owner_grade_claim_cards"
        )["allowed_facts"]
    ]
    output = {
        "program_cell_id": cell["program_cell_id"],
        "claim_candidate_atoms": [
            {
                "support_fact_aliases": aliases,
                "claim_kind": "economic_mechanism",
                "direction": "supports",
                "materiality": "high",
                "confidence": "high",
                "priority": "critical",
            },
            {
                "support_fact_aliases": [aliases[0]],
                "claim_kind": "evidence_direction",
                "direction": "supports",
                "materiality": "low",
                "confidence": "medium",
                "priority": "low",
            },
        ],
    }
    assembled = claim_compiler.assemble(
        "owner_grade_claim_cards",
        output,
        provider_output_utf8_bytes=500,
    )
    assert len(assembled["judgment_layer"]) == 1
    assert assembled["judgment_layer"][0][
        "support_fact_aliases"
    ] == [aliases[0]]


def test_candidate_permutation_has_one_stable_selected_result() -> None:
    input_pack, _, _ = _compiled_runtime("MU")
    cell = input_pack.cell_inputs[0]
    fact_compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
    )
    facts = fact_compiler.assemble(
        "facts_explanation_and_terminal",
        fact_compiler.fake_provider_output(
            "facts_explanation_and_terminal"
        ),
        provider_output_utf8_bytes=200,
    )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={
            "facts_explanation_and_terminal": facts
        },
        as_of=input_pack.as_of,
    )
    alias = compiler.model_visible_contract(
        "owner_grade_claim_cards"
    )["allowed_facts"][0]["fact_alias"]
    atoms = [
        {
            "support_fact_aliases": [alias],
            "claim_kind": "counterevidence",
            "direction": "challenges",
            "materiality": "medium",
            "confidence": "medium",
            "priority": "normal",
        },
        {
            "support_fact_aliases": [alias],
            "claim_kind": "evidence_direction",
            "direction": "supports",
            "materiality": "high",
            "confidence": "high",
            "priority": "high",
        },
    ]
    forward = compiler.assemble(
        "owner_grade_claim_cards",
        {
            "program_cell_id": cell["program_cell_id"],
            "claim_candidate_atoms": atoms,
        },
        provider_output_utf8_bytes=500,
    )
    reverse = compiler.assemble(
        "owner_grade_claim_cards",
        {
            "program_cell_id": cell["program_cell_id"],
            "claim_candidate_atoms": list(reversed(atoms)),
        },
        provider_output_utf8_bytes=500,
    )
    assert forward == reverse


def test_unknown_calendar_alias_fails_before_local_monitoring_render() -> None:
    input_pack, _, _ = _compiled_runtime("MU")
    cell = input_pack.cell_inputs[0]
    prior: dict[str, Mapping[str, Any]] = {}
    for segment in (
        "facts_explanation_and_terminal",
        "owner_grade_claim_cards",
    ):
        compiler = DeterministicJudgmentAtomCompiledContract(
            cell_input=cell,
            validated_segments=prior,
            as_of=input_pack.as_of,
        )
        output = compiler.fake_provider_output(segment)
        prior[segment] = compiler.assemble(
            segment,
            output,
            provider_output_utf8_bytes=400,
        )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments=prior,
        as_of=input_pack.as_of,
    )
    output = compiler.fake_provider_output(
        "actionable_what_would_change_tasks"
    )
    atom = output["what_would_change_atoms"][0]
    atom["review_cadence"] = "bound_date"
    atom["review_date_alias"] = "D999"
    with pytest.raises(ValueError, match="date_alias_unknown"):
        compiler.assemble(
            "actionable_what_would_change_tasks",
            output,
            provider_output_utf8_bytes=400,
        )


def test_fault_injection_preserves_provider_capture(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission, fake = _compiled_runtime("MU")
    original = fake.__call__

    def invalid(**kwargs: Any) -> Mapping[str, Any]:
        result = dict(original(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request.get("compiled_judgment_atom_contract")
        if (
            isinstance(contract, Mapping)
            and contract["family_id"] == "specialist_fact_atoms"
        ):
            output = json.loads(result["content"])
            output["fact_atoms"][0]["support_alias"] = "N-CROSS-CASE"
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
                "research_run_id": "fixture-compiled-fault",
                "attempt_id": "fixture-compiled-fault",
            },
        )
    assert len(exc_info.value.provider_output_captures) == 1
    assert exc_info.value.provider_output_captures[0][
        "assistant_output_present"
    ] is True


def test_r6_capture_v2_cached_replay_is_rejected_by_new_atom_wire() -> None:
    digest = (
        "16545e6fd94bb6f86b48d1885d5c42788"
        "c886b57ff4ff1cee1a12b10a72d92e5"
    )
    capture_path = (
        ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
        / "canonical-runtime"
        / "objects"
        / "fin01"
        / "provider-output-captures"
        / digest[:2]
        / digest[2:4]
        / f"{digest}.json"
    )
    capture = json.loads(capture_path.read_text(encoding="utf-8"))
    assert canonical_digest(capture) == digest
    assert capture["capture_policy_ref"] == (
        "fin01.runtime.provider_interaction_audit_capture:v2"
    )
    assert capture["assistant_output_present"] is True
    old_output = json.loads(capture["assistant_output_text"])
    input_pack, cell = _adapted_mu_value_cell()
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments={},
        as_of=input_pack.as_of,
    )
    with pytest.raises(ValueError, match="top_level_invalid"):
        compiler.assemble(
            "facts_explanation_and_terminal",
            old_output,
            provider_output_utf8_bytes=len(
                capture["assistant_output_text"].encode("utf-8")
            ),
        )
    replacement = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    assert set(replacement) == {
        "program_cell_id",
        "fact_atoms",
        "terminal_class",
    }
