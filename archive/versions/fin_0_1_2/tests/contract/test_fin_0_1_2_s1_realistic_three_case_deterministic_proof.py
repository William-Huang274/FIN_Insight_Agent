from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import re
import sys
from typing import Any, Callable, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseDeliveryIdentityPolicy,
    CaseNumericAuthorityPolicy,
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    compile_profile_aware_artifact_lineage_contract,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_TRACE_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    BoundedAgentExecutionError,
    S3_THREE_CELL_PROGRAM_CELL_IDS,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
)
from apps.workbench.backend.application.deterministic_judgment_atom_contract import (
    DeterministicJudgmentAtomCompiledContract,
)
from apps.workbench.backend.application.fact_candidate_pool_planner import (
    FactCandidatePoolPlannerError,
)
from apps.workbench.backend.application.fin_0_1_2_runtime_contract_binding import (
    load_fin_0_1_2_runtime_contract_binding,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_2_s1_bounded_production_consumer_migration import (
    _fin012_runtime,
)
from test_fin_0_1_s4_shared_runtime_deterministic_fact_candidate_pool_planner_minimum_zero_call_implementation import (
    _catalog_row,
    _planner,
)


ISO_DATE = re.compile(r"(?<!\d)20\d{2}-\d{2}-\d{2}(?!\d)")


def _compiled_contract(
    ticker: str,
    cell_index: int,
    *,
    validated_segments: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[Any, Any, Mapping[str, Any], DeterministicJudgmentAtomCompiledContract]:
    input_pack, admission, _ = _fin012_runtime(ticker)
    cell = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
        input_pack.cell_inputs[cell_index],
        policy_ref=admission.case_numeric_authority_policy_ref,
    )
    compiler = DeterministicJudgmentAtomCompiledContract(
        cell_input=cell,
        validated_segments=dict(validated_segments or {}),
        as_of=input_pack.as_of,
        contract_ref=admission.judgment_atom_compiled_contract_ref,
        research_profile_ref=admission.research_profile_ref,
        runtime_contract_family_binding_ref=(
            admission.runtime_contract_family_binding_ref
        ),
        runtime_contract_family_source_digest=(
            admission.runtime_contract_family_source_digest
        ),
    )
    return input_pack, admission, cell, compiler


def _assemble(
    compiler: DeterministicJudgmentAtomCompiledContract,
    segment_id: str,
    output: Mapping[str, Any],
) -> Mapping[str, Any]:
    encoded = json.dumps(
        dict(output), ensure_ascii=False, sort_keys=True
    ).encode("utf-8")
    return compiler.assemble(
        segment_id,
        output,
        provider_output_utf8_bytes=len(encoded),
    )


def _wwc_contract(
    ticker: str = "MU",
    cell_index: int = 0,
) -> tuple[
    Any,
    Any,
    Mapping[str, Any],
    DeterministicJudgmentAtomCompiledContract,
    dict[str, Any],
]:
    prior: dict[str, Mapping[str, Any]] = {}
    input_pack: Any = None
    admission: Any = None
    cell: Mapping[str, Any] = {}
    for segment_id in (
        "facts_explanation_and_terminal",
        "owner_grade_claim_cards",
    ):
        input_pack, admission, cell, compiler = _compiled_contract(
            ticker,
            cell_index,
            validated_segments=prior,
        )
        output = compiler.fake_provider_output(segment_id)
        prior[segment_id] = _assemble(compiler, segment_id, output)
    _, _, _, compiler = _compiled_contract(
        ticker,
        cell_index,
        validated_segments=prior,
    )
    output = compiler.fake_provider_output(
        "actionable_what_would_change_tasks"
    )
    return input_pack, admission, cell, compiler, output


def _execute_case(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> tuple[Any, Any, Any, Any]:
    input_pack, admission, fake = _fin012_runtime(ticker)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": f"fixture-fin012-s1-t03-{ticker.lower()}",
            "attempt_id": f"fixture-fin012-s1-t03-{ticker.lower()}",
        },
    )
    return input_pack, admission, fake, result


def _artifact_violation(
    *,
    input_pack: Any,
    admission: Any,
    artifacts: Mapping[str, Mapping[str, Any]],
    authority_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
) -> Any:
    authority = authority_artifacts or artifacts
    contracts = deepcopy(
        authority[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
            "case_numeric_authority_projections"
        ]
    )
    policies = {
        policy.program_cell_id: policy
        for policy in (
            CaseNumericAuthorityPolicy.from_prompt_contract(row)
            for row in contracts
        )
    }
    identity_projection = CaseDeliveryIdentityPolicy.compile(
        company=input_pack.company,
        s4_case_runtime=input_pack.s4_case_runtime,
        contract_ref=admission.case_delivery_identity_policy_ref,
    ).projection()
    lineage = compile_profile_aware_artifact_lineage_contract(
        input_pack.lineage,
        s4_case_runtime=input_pack.s4_case_runtime,
    )
    lineage_projection = {
        "manifest": {
            "lineage_contract_ref": lineage.contract_ref,
            "lineage_family": lineage.lineage_family,
            "lineage_digest": lineage.lineage_digest,
        },
        "trace_lineage": input_pack.lineage,
    }
    return S3ThreeCellBoundedAgentExecutor._first_s4_final_artifact_safety_violation(
        artifact_payloads=artifacts,
        specialists=artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE][
            "specialist_outputs"
        ],
        writer=artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"],
        verifier=artifacts[BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE][
            "verification"
        ],
        case_numeric_policies=policies,
        case_numeric_contracts=contracts,
        case_delivery_identity_projection=identity_projection,
        require_s4_runtime_projection=(input_pack.s4_case_runtime is not None),
        artifact_lineage_projection=lineage_projection,
    )


def _provider_atom_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, Mapping):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_provider_atom_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_provider_atom_keys(item))
    return keys


@pytest.mark.parametrize(
    ("catalog_count", "visible_count"),
    ((0, 0), (1, 1), (3, 3), (6, 6), (7, 6), (22, 6), (76, 6)),
)
def test_candidate_cardinality_is_bounded_before_provider(
    catalog_count: int,
    visible_count: int,
) -> None:
    catalog = [
        _catalog_row(ordinal)
        for ordinal in range(1, catalog_count + 1)
    ]
    if catalog_count == 0:
        with pytest.raises(
            FactCandidatePoolPlannerError,
            match="s4_fact_candidate_pool_empty",
        ) as exc_info:
            _planner().plan(catalog)
        assert exc_info.value.telemetry["provider_calls"] == 0
        return
    plan = _planner().plan(catalog)
    assert plan.eligible_support_count == catalog_count
    assert plan.candidate_pool_count == visible_count
    assert plan.omitted_eligible_support_count == (
        catalog_count - visible_count
    )


def test_seventy_six_candidate_permutations_have_one_stable_pool() -> None:
    catalog = [_catalog_row(ordinal) for ordinal in range(1, 77)]
    variants = (
        catalog,
        list(reversed(catalog)),
        [*catalog[31:], *catalog[:31]],
    )
    plans = [_planner().plan(variant) for variant in variants]
    assert plans[0].candidate_rows == plans[1].candidate_rows
    assert plans[0].candidate_rows == plans[2].candidate_rows
    assert len({plan.candidate_pool_digest for plan in plans}) == 1
    assert len({plan.eligible_catalog_digest for plan in plans}) == 1


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_nine_cell_fixture_has_local_identity_dates_and_numeric_authority(
    ticker: str,
) -> None:
    input_pack, admission, _ = _fin012_runtime(ticker)
    assert input_pack.company == ticker
    assert tuple(
        row["program_cell_id"] for row in input_pack.cell_inputs
    ) == S3_THREE_CELL_PROGRAM_CELL_IDS
    assert len(input_pack.cell_inputs) == 3
    for raw_cell in input_pack.cell_inputs:
        serialized = json.dumps(raw_cell, ensure_ascii=False)
        assert ticker in serialized
        assert ISO_DATE.search(serialized)
        cell = S3ThreeCellBoundedAgentExecutor._case_numeric_authority_cell_input(
            raw_cell,
            policy_ref=admission.case_numeric_authority_policy_ref,
        )
        policy = CaseNumericAuthorityPolicy.from_cell_input(cell)
        assert CaseNumericAuthorityPolicy.from_prompt_contract(
            policy.prompt_contract()
        ).projection_digest == policy.projection_digest
        assert (
            cell["evidence_input"]["candidate_bundle"]["candidates"]
            or policy.rows
        )

    if ticker in {"DELL", "MU"}:
        binding = input_pack.s4_case_runtime["binding"]
        assert binding["case_ticker"] == ticker
        assert binding["method_contract_ref"]
    else:
        # NVDA is an explicit structural compatibility fixture in S1. It is
        # not the post-transfer product proof owned by S3/S4.
        assert input_pack.s4_case_runtime is None
        assert "compatibility-fixture" in input_pack.case_id


def test_request_local_alias_mutations_fail_closed_without_provider_calls() -> None:
    _, _, _, target = _compiled_contract("DELL", 0)
    baseline = target.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    visible = {
        row["support_alias"]
        for row in target.model_visible_contract(
            "facts_explanation_and_terminal"
        )["allowed_supports"]
    }
    hidden = next(
        row["alias"]
        for row in target._fact_catalog()
        if row["alias"] not in visible
    )
    _, _, _, cross_case_source = _compiled_contract("MU", 0)
    cross_case_alias = next(
        row["support_alias"]
        for row in cross_case_source.model_visible_contract(
            "facts_explanation_and_terminal"
        )["allowed_supports"]
        if row["support_alias"] not in visible
    )
    _, _, _, cross_cell_source = _compiled_contract("DELL", 1)
    cross_cell_alias = next(
        row["support_alias"]
        for row in cross_cell_source.model_visible_contract(
            "facts_explanation_and_terminal"
        )["allowed_supports"]
        if row["support_alias"] not in visible
    )

    for mutation_id, alias in (
        ("unknown", "X999"),
        ("hidden", hidden),
        ("cross_case", cross_case_alias),
        ("cross_cell", cross_cell_alias),
    ):
        mutated = deepcopy(baseline)
        mutated["fact_atoms"][0]["support_alias"] = alias
        with pytest.raises(
            ValueError, match="alias_unknown_or_duplicate"
        ) as exc_info:
            _assemble(
                target,
                "facts_explanation_and_terminal",
                mutated,
            )
        assert "alias_unknown_or_duplicate" in str(exc_info.value), mutation_id

    duplicate = deepcopy(baseline)
    duplicate["fact_atoms"].append(deepcopy(duplicate["fact_atoms"][0]))
    with pytest.raises(ValueError, match="alias_unknown_or_duplicate"):
        _assemble(target, "facts_explanation_and_terminal", duplicate)

    _, _, _, six_candidate = _compiled_contract("DELL", 0)
    allowed = six_candidate.model_visible_contract(
        "facts_explanation_and_terminal"
    )["allowed_supports"]
    assert len(allowed) == 6
    seventh = six_candidate.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    atom = seventh["fact_atoms"][0]
    seventh["fact_atoms"] = [
        {**atom, "support_alias": row["support_alias"]}
        for row in allowed
    ] + [deepcopy(atom)]
    with pytest.raises(ValueError, match="shape_invalid"):
        _assemble(
            six_candidate,
            "facts_explanation_and_terminal",
            seventh,
        )


def test_date_alias_is_locally_rendered_and_unbound_values_fail_closed() -> None:
    _, _, _, compiler, baseline = _wwc_contract()
    assembled = _assemble(
        compiler,
        "actionable_what_would_change_tasks",
        baseline,
    )
    assert ISO_DATE.search(json.dumps(assembled, ensure_ascii=False))
    for invalid_alias in ("D999", "2026-10-31"):
        mutated = deepcopy(baseline)
        mutated["what_would_change_atoms"][0].update(
            {
                "review_cadence": "bound_date",
                "review_date_alias": invalid_alias,
            }
        )
        with pytest.raises(ValueError, match="date_alias_unknown"):
            _assemble(
                compiler,
                "actionable_what_would_change_tasks",
                mutated,
            )


def test_flat_and_legacy_numeric_rows_share_one_projection() -> None:
    common = {
        "program_cell_id": "value_and_profit_capture",
        "authority_refs": {"numeric_refs": ["numeric:fixture:revenue"]},
    }
    flat = {
        **common,
        "numeric_input": {
            "selected_financial_rows": [
                {
                    "numeric_ref": "numeric:fixture:revenue",
                    "entity_ref": "DELL",
                    "segment_ref": "__company_total__",
                    "period": "FY2025-FY",
                    "metric_family": "revenue",
                    "value": "100",
                    "currency": "USD",
                    "unit": "million",
                    "scale_multiplier": "1",
                    "source_ref": "fixture:issuer-filing",
                }
            ],
            "derived_metrics": [],
        },
    }
    legacy = {
        **common,
        "numeric_input": {
            "selected_financial_rows": [
                {
                    "financial_row_id": "numeric:fixture:revenue",
                    "selector": {
                        "entity_ref": "DELL",
                        "segment_ref": "__company_total__",
                        "period": "FY2025-FY",
                        "metric_family": "revenue",
                        "currency": "USD",
                        "unit": "million",
                    },
                    "normalized_value": "100",
                    "scale_multiplier": "1",
                    "evidence_ref": "fixture:issuer-filing",
                }
            ],
            "derived_metrics": [],
        },
    }
    flat_policy = CaseNumericAuthorityPolicy.from_cell_input(flat)
    legacy_policy = CaseNumericAuthorityPolicy.from_cell_input(legacy)
    assert flat_policy.prompt_contract() == legacy_policy.prompt_contract()


@pytest.mark.parametrize(
    "field",
    (
        "metric_family",
        "exact_value",
        "period",
        "unit",
        "scale_multiplier",
        "comparison_operator",
        "source_or_formula_lineage",
    ),
)
def test_numeric_correspondence_mutations_fail_independent_recompute(
    field: str,
) -> None:
    _, _, _, compiler = _compiled_contract("DELL", 1)
    contract = compiler.numeric_policy.prompt_contract()
    mutated = deepcopy(contract)
    row = mutated["rows"][0]
    if field == "exact_value":
        row[field] = str(-Decimal(row[field]))
    else:
        row[field] = "mutated"
    with pytest.raises(ValueError):
        CaseNumericAuthorityPolicy.from_prompt_contract(mutated)


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_case_identity_projection_rejects_removal_and_foreign_case(
    ticker: str,
) -> None:
    input_pack, admission, _ = _fin012_runtime(ticker)
    policy = CaseDeliveryIdentityPolicy.compile(
        company=ticker,
        s4_case_runtime=input_pack.s4_case_runtime,
        contract_ref=admission.case_delivery_identity_policy_ref,
    )
    assert (
        policy.first_provider_narrative_identity_violation(
            {"statement": f"{ticker} bounded context"}
        )
        is None
    )
    foreign = next(value for value in ("DELL", "MU", "NVDA") if value != ticker)
    assert policy.first_provider_narrative_identity_violation(
        {"statement": f"{foreign} foreign context"}
    )

    removed = policy.projection()
    removed["case_ticker"] = ""
    with pytest.raises(ValueError):
        CaseDeliveryIdentityPolicy.from_projection(removed)

    polluted = policy.projection()
    polluted["title_zh_cn"] = f"{foreign} 三单元内部研究备忘录"
    with pytest.raises(ValueError):
        CaseDeliveryIdentityPolicy.from_projection(polluted)


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_full_fake_and_final_artifact_mutations(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission, fake, result = _execute_case(
        monkeypatch, ticker
    )
    binding = load_fin_0_1_2_runtime_contract_binding()
    assert len(result.execution_observation["completed_node_receipts"]) == 6
    assert len(fake.calls) == 12
    assert fake.compiled_calls == 9
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )

    atom_keys = _provider_atom_keys(fake.compiled_outputs)
    assert not atom_keys.intersection(
        {
            "statement",
            "exact_value",
            "period",
            "unit",
            "scale_multiplier",
            "source_or_formula_lineage",
            "deadline_or_review_date",
            "authority_refs",
            "case_ticker",
        }
    )
    assert ticker not in json.dumps(fake.compiled_outputs, ensure_ascii=False)
    for capture in result.provider_output_captures:
        assert capture["model_visible_request"]
        assert capture["assistant_output_present"]
        assert capture["assistant_output_text"]
        assert capture["nonsecret_inference_arguments"]
        assert capture["model"]
        assert capture["finish_reason"]
        assert capture["credentials_included"] is False
        assert capture["private_reasoning_included"] is False
        assert capture["raw_provider_response_included"] is False
        assert capture["runtime_contract_family_binding"][
            "source_digest"
        ] == binding.source_digest

    artifacts = {
        row.artifact_type: deepcopy(row.payload)
        for row in result.artifacts
    }
    assert artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "case_ticker"
    ] == ticker
    assert artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"][
        "title_zh_cn"
    ] == f"{ticker} 三单元内部研究备忘录"
    assert artifacts[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
        "case_numeric_authority_projections"
    ]
    assert artifacts[BOUNDED_AGENT_TRACE_ARTIFACT_TYPE]["lineage"] == (
        input_pack.lineage
    )
    assert _artifact_violation(
        input_pack=input_pack,
        admission=admission,
        artifacts=artifacts,
    ) is None

    numeric = deepcopy(artifacts)
    next(
        row
        for contract in numeric[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
            "case_numeric_authority_projections"
        ]
        for row in contract["rows"]
    )["exact_value"] = "999"
    identity = deepcopy(artifacts)
    foreign = next(value for value in ("DELL", "MU", "NVDA") if value != ticker)
    identity[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE]["report"][
        "title_zh_cn"
    ] = f"{foreign} 三单元内部研究备忘录"
    lineage = deepcopy(artifacts)
    lineage[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE]["lineage_digest"] = (
        "0" * 64
    )

    expected = (
        (numeric, "numeric_projection_payload_mismatch"),
        (identity, "delivery_identity_surface_mismatch"),
        (lineage, "artifact_lineage_projection_mismatch"),
    )
    for mutated, expected_subtype in expected:
        violation = _artifact_violation(
            input_pack=input_pack,
            admission=admission,
            artifacts=mutated,
            authority_artifacts=artifacts,
        )
        assert violation is not None
        assert violation.subtype == expected_subtype
        assert violation.telemetry()["acceptance_layer"] == (
            "L1_hard_integrity"
        )


@dataclass(frozen=True)
class _DiagnosticProbe:
    code: str
    location: str
    phase: str
    operation: Callable[[], Any]


class _IsolatedCollectAllDiagnostic:
    def __init__(self) -> None:
        self.namespace = "diagnostic:fin012:s1:t03:collect-all"
        self.findings: list[dict[str, Any]] = []
        self.placeholders: list[dict[str, Any]] = []
        self.active = True

    def collect(self, probes: list[_DiagnosticProbe]) -> None:
        if not self.active:
            raise RuntimeError("diagnostic_namespace_cleared")
        for probe in probes:
            try:
                probe.operation()
            except (ValueError, FactCandidatePoolPlannerError) as exc:
                self.findings.append(
                    {
                        "code": probe.code,
                        "location": probe.location,
                        "phase": probe.phase,
                        "observed_failure": str(exc),
                        "promotable": False,
                    }
                )
                self.placeholders.append(
                    {
                        "location": probe.location,
                        "status": "deterministic_shape_placeholder",
                        "promotable": False,
                    }
                )

    def clear(self) -> None:
        self.findings.clear()
        self.placeholders.clear()
        self.active = False


def test_collect_all_is_isolated_typed_nonpromotable_and_cleared() -> None:
    _, _, _, compiler = _compiled_contract("MU", 0)
    baseline = compiler.fake_provider_output(
        "facts_explanation_and_terminal"
    )
    unknown = deepcopy(baseline)
    unknown["fact_atoms"][0]["support_alias"] = "X999"
    duplicate = deepcopy(baseline)
    duplicate["fact_atoms"].append(deepcopy(duplicate["fact_atoms"][0]))
    _, _, _, wwc, wwc_output = _wwc_contract()
    invalid_date = deepcopy(wwc_output)
    invalid_date["what_would_change_atoms"][0].update(
        {
            "review_cadence": "bound_date",
            "review_date_alias": "D999",
        }
    )
    collector = _IsolatedCollectAllDiagnostic()
    collector.collect(
        [
            _DiagnosticProbe(
                "unknown_alias",
                "cell[0].fact_atoms[0].support_alias",
                "local_validation",
                lambda: _assemble(
                    compiler,
                    "facts_explanation_and_terminal",
                    unknown,
                ),
            ),
            _DiagnosticProbe(
                "duplicate_alias",
                "cell[0].fact_atoms[1].support_alias",
                "local_validation",
                lambda: _assemble(
                    compiler,
                    "facts_explanation_and_terminal",
                    duplicate,
                ),
            ),
            _DiagnosticProbe(
                "unbound_date_alias",
                "cell[0].what_would_change_atoms[0].review_date_alias",
                "local_temporal_rendering",
                lambda: _assemble(
                    wwc,
                    "actionable_what_would_change_tasks",
                    invalid_date,
                ),
            ),
        ]
    )
    assert len(collector.findings) == 3
    assert len(collector.placeholders) == 3
    assert all(
        finding["code"] and finding["location"] and finding["phase"]
        for finding in collector.findings
    )
    assert all(not row["promotable"] for row in collector.findings)
    assert all(not row["promotable"] for row in collector.placeholders)
    collector.clear()
    assert not collector.active
    assert collector.findings == []
    assert collector.placeholders == []


@pytest.mark.parametrize(
    ("request_marker", "expected_capture_count"),
    (
        ("research_lead_transport_ref", 10),
        ("memo_writer_transport_ref", 11),
        ("output_state_machine", 12),
    ),
)
def test_downstream_failure_retains_request_output_usage_and_typed_terminal(
    monkeypatch: pytest.MonkeyPatch,
    request_marker: str,
    expected_capture_count: int,
) -> None:
    input_pack, admission, fake = _fin012_runtime("MU")
    original = fake.__call__

    def invalid(**kwargs: Any) -> Mapping[str, Any]:
        response = dict(original(**kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        if (
            request_marker in request
            and "compiled_judgment_atom_contract" not in request
        ):
            response["content"] = "{}"
        return response

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
                "research_run_id": f"fixture-t03-failure-{request_marker}",
                "attempt_id": f"fixture-t03-failure-{request_marker}",
            },
        )
    error = exc_info.value
    captures = error.provider_output_captures
    observation = error.failure_observation
    assert len(captures) == expected_capture_count
    assert len(observation["usage_receipts"]) == expected_capture_count
    assert observation["observed_counts"]["provider_calls"] == (
        expected_capture_count
    )
    assert observation["private_reasoning_persisted"] is False
    assert observation["raw_provider_response_persisted"] is False
    assert observation["contract_ref"] == (
        "fin01.bounded_agent.post_provider_failure_envelope:v1"
    )
    assert observation["failure_code"]
    assert observation["runtime_contract_family_binding"][
        "consumer_binding"
    ]["consumer_id"] == "typed_failure"

    failing = captures[-1]
    usage = observation["usage_receipts"][-1]
    assert failing["capture_sequence"] == expected_capture_count
    assert failing["model_visible_request"]
    assert failing["assistant_output_text"] == "{}"
    assert failing["nonsecret_inference_arguments"]
    assert failing["model"] == usage["model"]
    assert failing["finish_reason"] == usage["finish_reason"]
    assert failing["call_id"] == usage["call_id"]
    assert failing["credentials_included"] is False
    assert failing["private_reasoning_included"] is False
    assert failing["raw_provider_response_included"] is False

    # The hermetic runner content-addresses this compact stdout record plus
    # per-test stderr/detail and the complete terminal result. The Runtime
    # capture above retains the complete request/output bytes in memory.
    print(
        json.dumps(
            {
                "request_capture_ref": "sha256:"
                + canonical_digest(failing["model_visible_request"]),
                "assistant_output_capture_ref": "sha256:"
                + canonical_digest(
                    {"assistant_output_text": failing["assistant_output_text"]}
                ),
                "capture_sequence": expected_capture_count,
                "terminal_result_ref_owner": "hermetic_runner",
                "stdout_ref_owner": "hermetic_runner",
                "stderr_ref_owner": "hermetic_runner",
                "promotable": False,
            },
            sort_keys=True,
        )
    )
