from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    CaseDeliveryIdentityPolicy,
    CaseNumericAuthorityPolicy,
    S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF,
    S3_SPECIALIST_WWC_JUDGMENT_ATOM_POLICY_REF,
    S4_MU_THREE_CELL_RESEARCH_PROFILE_REF,
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_NUMERIC_AUTHORITY_POLICY_REF,
    S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF,
    SpecialistWWCJudgmentAtomPolicy,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE,
    BOUNDED_AGENT_REPORT_ARTIFACT_TYPE,
    BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE,
    BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE,
    BoundedAgentExecutionError,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    build_s4_source_grounded_bounded_agent_input,
    resolve_s4_case_runtime_binding_for_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s4_case_runtime import (
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from test_fin_0_1_s3_t09_claim_fact_link_policy_zero_call_implementation import (
    _emit_claim_fact_aliases,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_zero_call_implementation import (
    _GapAtomV6FullFakeProvider,
)


R10_ADMISSION = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_s4_t05_dell_r10_profile_aware_artifact_lineage_"
    "fresh_exact_admission_r10.json"
)
RUN_IDENTITY = {
    "research_run_id": "fixture-s4-t05-dell-numeric-identity",
    "attempt_id": "fixture-s4-t05-dell-numeric-identity",
}


def _dell_input_and_admission():
    historical = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(R10_ADMISSION.read_text(encoding="utf-8"))
    )
    binding, overlay = resolve_s4_case_runtime_binding_for_admission(
        ROOT,
        historical,
    )
    input_pack = build_s4_source_grounded_bounded_agent_input(
        binding,
        load_s4_source_grounded_input_pack(ROOT, "DELL"),
        case_id="case-s4-t05-dell-numeric-identity-fixture",
        case_version=1,
        query="Exercise deterministic numeric and delivery identity ownership.",
        decision_surface_contract_ref=(
            "fin01.s4.t05.numeric_identity_fixture:v1"
        ),
        research_profile_overlay=overlay,
    )
    admission = historical.model_copy(
        update={
            "admission_id": (
                "fixture-s4-t05-dell-numeric-identity"
            ),
            "execution_mode": (
                "zero_call_fake_provider_numeric_identity"
            ),
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
            "case_numeric_authority_policy_ref": (
                S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
            ),
            "case_delivery_identity_policy_ref": (
                S4_CASE_DELIVERY_IDENTITY_POLICY_REF
            ),
        }
    )
    admission.assert_profile_admissible()
    return input_pack, admission


def _replace_case_tokens(value: Any, ticker: str) -> Any:
    if isinstance(value, dict):
        return {
            key: _replace_case_tokens(item, ticker)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_replace_case_tokens(item, ticker) for item in value]
    if isinstance(value, tuple):
        return tuple(
            _replace_case_tokens(item, ticker) for item in value
        )
    if isinstance(value, str):
        return value.replace("DELL", ticker).replace(
            "dell", ticker.lower()
        )
    return value


def _case_fixture_input_and_admission(
    ticker: str,
) -> tuple[Any, S3ThreeCellBoundedAgentAdmission]:
    if ticker == "DELL":
        return _dell_input_and_admission()
    dell_input, dell_admission = _dell_input_and_admission()
    lineage = {
        key: {
            "version_ref": f"fixture:{ticker}:{key}:v1",
            "digest": canonical_digest((ticker, key)),
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
    fixture_input = dell_input.model_copy(
        update={
            "case_id": f"case-s4-t05-{ticker.lower()}-compatibility-fixture",
            "company": ticker,
            "query": (
                f"Exercise {ticker} compatibility without source or paid proof."
            ),
            "decision_surface_contract_ref": (
                f"fin01.s4.t05.{ticker.lower()}.compatibility_fixture:v1"
            ),
            "lineage": lineage,
            "cell_inputs": _replace_case_tokens(
                dell_input.cell_inputs, ticker
            ),
            "s4_case_runtime": None,
        }
    )
    fixture_input = fixture_input.model_copy(
        update={
            "input_digest": canonical_digest(
                fixture_input.model_dump(
                    mode="json",
                    exclude={"input_digest"},
                )
            )
        }
    )
    profile_ref = (
        S4_MU_THREE_CELL_RESEARCH_PROFILE_REF
        if ticker == "MU"
        else S3_NVDA_THREE_CELL_RESEARCH_PROFILE_V4_REF
    )
    admission = dell_admission.model_copy(
        update={
            "admission_id": (
                f"fixture-s4-t05-{ticker.lower()}-numeric-identity"
            ),
            "execution_mode": (
                "zero_call_cross_case_numeric_identity_compatibility"
            ),
            "company": ticker,
            "research_profile_ref": profile_ref,
            "case_id": fixture_input.case_id,
            "case_version": fixture_input.case_version,
            "as_of": fixture_input.as_of,
            "input_digest": fixture_input.input_digest,
            "transport_ref": (
                S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V7_REF
            ),
            "wwc_judgment_atom_policy_ref": None,
            "specialist_max_output_tokens": 4200,
            "lead_max_output_tokens": 1800,
            "writer_max_output_tokens": 1400,
            "verifier_max_output_tokens": 1000,
        }
    )
    admission.assert_profile_admissible()
    return fixture_input, admission


def _sanitize_provider_narratives(value: Any, field_id: str = "") -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize_provider_narratives(item, str(key))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _sanitize_provider_narratives(item, field_id)
            for item in value
        ]
    if (
        isinstance(value, str)
        and field_id
        in CaseNumericAuthorityPolicy._NARRATIVE_FIELDS
    ):
        sanitized = re.sub(r"[0-9０-９%％$¥￥+\-]", "", value)
        for ticker in ("DELL", "MU", "NVDA"):
            sanitized = sanitized.replace(ticker, "发行人")
        return sanitized.strip() or "定性边界"
    return value


class _NumericIdentitySafeFake:
    def __init__(
        self,
        input_pack: Any,
        specialists: Mapping[str, Mapping[str, Any]],
        *,
        inject_node: str | None = None,
        injected_text: str = "",
    ) -> None:
        self.responses: list[dict[str, Any]] = []
        cells = {
            str(row["program_cell_id"]): row
            for row in input_pack.cell_inputs
        }
        self._wwc = {
            cell_id: SpecialistWWCJudgmentAtomPolicy.from_cell_input(
                cell_input=(
                    S3ThreeCellBoundedAgentExecutor
                    ._case_numeric_authority_cell_input(
                        cells[cell_id]
                    )
                ),
                claims=list(specialist["judgment_layer"]),
                as_of=input_pack.as_of,
            )
            for cell_id, specialist in specialists.items()
        }

        def mutation(
            request: dict[str, Any],
            output: dict[str, Any],
        ) -> dict[str, Any]:
            output = _emit_claim_fact_aliases(request, output)
            segment_id = request.get("segment_id")
            if segment_id == "facts_explanation_and_terminal":
                aliases = request[
                    "case_numeric_authority_contract"
                ]["provider_selection_values"]
                for fact in output["fact_layer"]:
                    fact.update(
                        {
                            "statement": "该指标支持方向性判断",
                            "support_type": "Numeric",
                            "support_refs": [aliases[0]],
                            "boundary": "仅支持所列口径",
                        }
                    )
            elif (
                segment_id
                == "actionable_what_would_change_tasks"
                and "WWC_judgment_atom_contract" in request
            ):
                cell_id = str(request["node_id"]).split(
                    ":", 1
                )[1]
                return self._wwc[cell_id].fake_provider_output(
                    atom_count=3,
                    narrative_characters=24,
                )
            elif (
                segment_id
                == "actionable_what_would_change_tasks"
            ):
                cell_id = str(request["node_id"]).split(
                    ":", 1
                )[1]
                claim_ids = sorted(
                    str(row["claim_id"])
                    for row in specialists[cell_id][
                        "judgment_layer"
                    ]
                )
                aliases = [
                    str(row["claim_alias"])
                    for row in request[
                        "task_claim_link_contract"
                    ]["allowed_claims"]
                ]
                alias_by_claim_id = dict(
                    zip(claim_ids, aliases, strict=True)
                )
                for task in output["what_would_change"]:
                    claim_id = str(task.pop("claim_id"))
                    task["claim_alias"] = (
                        alias_by_claim_id[claim_id]
                    )
                    allowed = request[
                        "what_would_change_authority_contract"
                    ]["allowed_refs_by_authority_class"]
                    task["authority_refs"] = [
                        next(
                            ref
                            for rows in allowed.values()
                            for ref in rows
                        )
                    ]
            return output

        self._base = _GapAtomV6FullFakeProvider(
            specialists,
            mutation=mutation,
        )
        self._inject_node = inject_node
        self._injected_text = injected_text

    @property
    def calls(self):
        return self._base.calls

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(self._base(**kwargs))
        request = self._base.calls[-1]["request"]
        output = json.loads(str(response["content"]))
        output = _sanitize_provider_narratives(output)
        node_id = str(request["node_id"])
        if (
            self._inject_node == "specialist"
            and node_id.startswith("domain_specialist:")
            and request.get("segment_id")
            == "facts_explanation_and_terminal"
        ):
            output["fact_layer"][0]["statement"] = (
                self._injected_text
            )
        elif (
            self._inject_node == "research_lead"
            and node_id == "research_lead"
        ):
            output["cross_cell_dependencies"][0][
                "statement"
            ] = self._injected_text
        elif (
            self._inject_node == "memo_writer"
            and node_id == "memo_writer"
        ):
            output["claim_renderings"][0][
                "analysis_text_zh_cn"
            ] = self._injected_text
        elif (
            self._inject_node == "verifier"
            and node_id == "verifier"
        ):
            output["findings"][0]["issue_codes"] = [
                self._injected_text
            ]
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.responses.append(deepcopy(output))
        return response


def test_s4_flat_and_derived_rows_compile_to_one_closed_projection() -> None:
    input_pack, _ = _dell_input_and_admission()
    policies = []
    for cell_input in input_pack.cell_inputs:
        adapted = (
            S3ThreeCellBoundedAgentExecutor
            ._case_numeric_authority_cell_input(cell_input)
        )
        policy = CaseNumericAuthorityPolicy.from_cell_input(
            adapted
        )
        policies.append(policy)
        assert (
            CaseNumericAuthorityPolicy.from_prompt_contract(
                policy.prompt_contract()
            ).projection_digest
            == policy.projection_digest
        )
        surface = (
            S3ThreeCellBoundedAgentExecutor
            ._owner_grade_authority_surface(adapted)
        )
        assert set(
            surface["numeric_fact_scope_and_cannot_support"]
        ) == {row.numeric_ref for row in policy.rows}

    unique_rows = {
        row.numeric_ref: row
        for policy in policies
        for row in policy.rows
    }
    assert (
        sum(
            row.authority_kind == "financial_row"
            for row in unique_rows.values()
        ),
        sum(
            row.authority_kind == "derived_metric"
            for row in unique_rows.values()
        ),
    ) == (22, 2)


def test_numeric_alias_expands_locally_and_wrong_alias_fails_closed() -> None:
    input_pack, _ = _dell_input_and_admission()
    adapted = (
        S3ThreeCellBoundedAgentExecutor
        ._case_numeric_authority_cell_input(
            input_pack.cell_inputs[0]
        )
    )
    policy = CaseNumericAuthorityPolicy.from_cell_input(adapted)
    provider_output = {
        "program_cell_id": policy.program_cell_id,
        "fact_layer": [
            {
                "fact_id": "fact-local",
                "statement": "该指标支持方向性判断",
                "support_type": "Numeric",
                "support_refs": [policy.rows[0].alias],
                "boundary": "仅支持所列口径",
            }
        ],
        "explanation_layer": ["保持定性解释"],
        "remaining_gaps": ["仍需后续验证"],
        "terminal_class": "bounded",
    }
    expanded, violation = policy.expand_provider_fact_output(
        provider_output
    )
    assert violation is None
    assert expanded is not None
    fact = expanded["fact_layer"][0]
    assert fact["support_refs"] == [
        policy.rows[0].numeric_ref
    ]
    assert fact["statement"].startswith(
        policy.rows[0].rendered_clause() + "；"
    )
    assert (
        policy.first_canonical_fact_violation(
            expanded["fact_layer"]
        )
        is None
    )

    wrong = deepcopy(provider_output)
    wrong["fact_layer"][0]["support_refs"] = ["N999"]
    expanded, violation = policy.expand_provider_fact_output(
        wrong
    )
    assert expanded is None
    assert violation is not None
    assert violation.subtype == "numeric_alias_unknown_or_duplicate"


@pytest.mark.parametrize(
    "field",
    (
        "entity_ref",
        "business_scope_ref",
        "period",
        "metric_family",
        "comparison_operator",
        "exact_value",
        "currency",
        "unit",
        "scale_multiplier",
        "formula",
        "input_numeric_refs",
    ),
)
def test_projection_mutations_fail_independent_digest_recompute(
    field: str,
) -> None:
    input_pack, _ = _dell_input_and_admission()
    adapted = (
        S3ThreeCellBoundedAgentExecutor
        ._case_numeric_authority_cell_input(
            input_pack.cell_inputs[1]
        )
    )
    contract = (
        CaseNumericAuthorityPolicy.from_cell_input(
            adapted
        ).prompt_contract()
    )
    mutated = deepcopy(contract)
    row = next(
        item
        for item in mutated["rows"]
        if (
            field not in {"formula", "input_numeric_refs"}
            or item["authority_kind"] == "derived_metric"
        )
    )
    row[field] = (
        ["s4_unknown_numeric_ref"]
        if field == "input_numeric_refs"
        else "999"
    )
    with pytest.raises(ValueError):
        CaseNumericAuthorityPolicy.from_prompt_contract(mutated)


def test_delivery_identity_is_case_local_and_cross_case_projection_fails() -> None:
    input_pack, _ = _dell_input_and_admission()
    dell = CaseDeliveryIdentityPolicy.compile(
        company="DELL",
        s4_case_runtime=input_pack.s4_case_runtime,
    )
    assert dell.title_zh_cn == "DELL 三单元内部研究备忘录"
    assert (
        CaseDeliveryIdentityPolicy.from_projection(
            dell.projection()
        )
        == dell
    )
    assert (
        CaseDeliveryIdentityPolicy.compile(
            company="NVDA",
            s4_case_runtime=None,
        ).title_zh_cn
        == "NVDA 三单元内部研究备忘录"
    )
    mu_binding = load_s4_case_runtime_binding(ROOT, "MU")
    mu_runtime = {"binding": mu_binding.model_dump(mode="json")}
    assert (
        CaseDeliveryIdentityPolicy.compile(
            company="MU",
            s4_case_runtime=mu_runtime,
        ).title_zh_cn
        == "MU 三单元内部研究备忘录"
    )
    with pytest.raises(
        ValueError,
        match="binding_mismatch",
    ):
        CaseDeliveryIdentityPolicy.compile(
            company="NVDA",
            s4_case_runtime=mu_runtime,
        )


def test_policy_pair_is_explicit_and_historical_admission_is_unchanged() -> None:
    historical = S3ThreeCellBoundedAgentAdmission.model_validate(
        json.loads(R10_ADMISSION.read_text(encoding="utf-8"))
    )
    assert historical.case_numeric_authority_policy_ref is None
    assert historical.case_delivery_identity_policy_ref is None
    historical.assert_profile_admissible()
    _, bound = _dell_input_and_admission()
    assert bound.case_numeric_authority_policy_ref == (
        S4_CASE_NUMERIC_AUTHORITY_POLICY_REF
    )
    assert bound.case_delivery_identity_policy_ref == (
        S4_CASE_DELIVERY_IDENTITY_POLICY_REF
    )
    with pytest.raises(ValueError, match="policy_pair_required"):
        bound.model_copy(
            update={"case_delivery_identity_policy_ref": None}
        ).assert_profile_admissible()


@pytest.mark.parametrize(
    ("inject_node", "expected_call_count"),
    (
        ("specialist", 1),
        ("research_lead", 10),
        ("memo_writer", 11),
        ("verifier", 12),
    ),
)
def test_every_provider_phase_rejects_numeric_narrative_with_typed_receipts(
    monkeypatch: pytest.MonkeyPatch,
    inject_node: str,
    expected_call_count: int,
) -> None:
    input_pack, admission = _dell_input_and_admission()
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeFake(
        input_pack,
        specialists,
        inject_node=inject_node,
        injected_text="非法数值 123",
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY",
        "fixture-not-a-real-secret",
    )
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity=RUN_IDENTITY,
        )
    observation = caught.value.failure_observation
    assert observation["failure_codes"] == [
        "s4_case_numeric_authority_provider_narrative_invalid"
    ]
    telemetry = observation["failure_telemetry"][
        "case_numeric_authority"
    ]
    assert telemetry["acceptance_layer"] == "L1_hard_integrity"
    assert telemetry["raw_text_persisted"] is False
    assert len(observation["usage_receipts"]) == expected_call_count
    assert (
        len(caught.value.provider_output_captures)
        == expected_call_count
    )


def test_cross_case_provider_narrative_fails_with_identity_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission = _dell_input_and_admission()
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeFake(
        input_pack,
        specialists,
        inject_node="memo_writer",
        injected_text="NVDA 的结论",
    )
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY",
        "fixture-not-a-real-secret",
    )
    with pytest.raises(BoundedAgentExecutionError) as caught:
        build_s3_three_cell_bounded_agent_executor_for_admission(
            admission,
            chat_completion_fn=fake,
        ).execute(
            input_pack,
            admission,
            run_identity=RUN_IDENTITY,
        )
    observation = caught.value.failure_observation
    assert observation["failure_codes"] == [
        "s4_case_delivery_identity_provider_narrative_invalid"
    ]
    telemetry = observation["failure_telemetry"][
        "case_delivery_identity"
    ]
    assert telemetry["acceptance_layer"] == "L1_hard_integrity"
    assert telemetry["raw_text_persisted"] is False
    assert len(observation["usage_receipts"]) == 11
    assert len(caught.value.provider_output_captures) == 11


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_full_fake_reaches_twelve_callbacks_nine_artifacts_and_local_truth(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    input_pack, admission = _case_fixture_input_and_admission(
        ticker
    )
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeFake(input_pack, specialists)
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv(
        "DEEPSEEK_API_KEY",
        "fixture-not-a-real-secret",
    )
    result = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission,
        chat_completion_fn=fake,
    ).execute(
        input_pack,
        admission,
        run_identity={
            "research_run_id": (
                f"fixture-s4-t05-{ticker.lower()}-numeric-identity"
            ),
            "attempt_id": (
                f"fixture-s4-t05-{ticker.lower()}-numeric-identity"
            ),
        },
    )
    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert {row.artifact_type for row in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    artifacts = {
        row.artifact_type: row.payload
        for row in result.artifacts
    }
    assert artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "case_ticker"
    ] == ticker
    assert artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE][
        "case_runtime_safety_profile_ref"
    ] == (
        S4_CASE_RUNTIME_MANDATORY_MATERIAL_TRUTH_IDENTITY_SAFETY_REF
    )
    assert len(
        artifacts[BOUNDED_AGENT_NUMERIC_ARTIFACT_TYPE][
            "case_numeric_authority_projections"
        ]
    ) == 3
    assert artifacts[BOUNDED_AGENT_WORKPAPER_ARTIFACT_TYPE][
        "entity_label"
    ] == ticker
    report = artifacts[BOUNDED_AGENT_REPORT_ARTIFACT_TYPE][
        "report"
    ]
    assert report["title_zh_cn"] == (
        f"{ticker} 三单元内部研究备忘录"
    )
    assert "USD" in report["executive_summary_zh_cn"]
    assert artifacts[
        BOUNDED_AGENT_VERIFICATION_ARTIFACT_TYPE
    ]["entity_label"] == ticker
    for capture in result.provider_output_captures:
        provider_output = json.loads(
            str(capture["assistant_output_text"])
        )
        assert (
            CaseNumericAuthorityPolicy._PROVIDER_NUMERIC_TOKEN.search(
                " ".join(
                    text
                    for _, text in (
                        CaseNumericAuthorityPolicy._narrative_values(
                            provider_output
                        )
                    )
                )
            )
            is None
        )
