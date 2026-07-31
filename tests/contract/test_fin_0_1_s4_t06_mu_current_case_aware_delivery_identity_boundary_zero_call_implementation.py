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
    CaseDeliveryIdentityPolicy,
    CaseNumericAuthorityPolicy,
    S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_POLICY_REF,
    S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BoundedAgentExecutionError,
    S3ThreeCellBoundedAgentAdmission,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_s4_case_runtime_mandatory_safety_admission,
)
from sec_agent.canonical_runtime.failure_observation_policy import (
    is_registered_failure_observation,
    registered_failure_observation,
)
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
    _NumericIdentitySafeFake,
    _case_fixture_input_and_admission,
)
from test_fin_0_1_s4_t06_mu_case_runtime_mandatory_material_truth_identity_safety_closure_zero_call_implementation import (
    _NumericIdentitySafeMuV7Fake,
)
from test_fin_0_1_s4_t06_mu_research_lead_fact_presence_local_materialization_zero_call_implementation import (
    _mu_input_and_admission,
)

IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)
PROGRAM_BACKLOG = (
    ROOT / "configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json"
)
S4_BACKLOG = (
    ROOT
    / "configs/releases/fin_ia_0_1_s4_detailed_execution_backlog_v1_0.json"
)
R4_RESULT = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_r4_exact_live_execution_failure_"
    "result_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)


class _NaturalCurrentCaseIdentityFake:
    """Keep the fake path natural by emitting the exact current ticker."""

    def __init__(
        self,
        base: Any,
        *,
        current_ticker: str,
        inject_nonlocal_phase: str | None = None,
        nonlocal_ticker: str = "NVDA",
    ) -> None:
        self._base = base
        self.current_ticker = current_ticker
        self.inject_nonlocal_phase = inject_nonlocal_phase
        self.nonlocal_ticker = nonlocal_ticker
        self.systems: list[str] = []

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self._base.calls

    @staticmethod
    def _phase(request: Mapping[str, Any]) -> str:
        node_id = str(request.get("node_id") or "")
        if node_id.startswith("domain_specialist:"):
            return "specialist"
        return node_id

    @staticmethod
    def _prefix_narrative(
        output: dict[str, Any],
        request: Mapping[str, Any],
        ticker: str,
    ) -> None:
        node_id = str(request.get("node_id") or "")
        segment_id = str(request.get("segment_id") or "")
        if node_id.startswith("domain_specialist:"):
            if segment_id == "facts_explanation_and_terminal":
                output["fact_layer"][0]["statement"] = (
                    f"{ticker} "
                    + str(output["fact_layer"][0]["statement"])
                )
            elif segment_id == "owner_grade_claim_cards":
                output["judgment_layer"][0]["statement"] = (
                    f"{ticker} "
                    + str(output["judgment_layer"][0]["statement"])
                )
            elif segment_id == "actionable_what_would_change_tasks":
                task_key = (
                    "what_would_change"
                    if "what_would_change" in output
                    else "what_would_change_judgment_atoms"
                )
                output[task_key][0][
                    "metric_or_observation"
                ] = (
                    f"{ticker} "
                    + str(
                        output[task_key][0][
                            "metric_or_observation"
                        ]
                    )
                )
        elif node_id == "research_lead":
            output["cross_cell_dependencies"][0]["statement"] = (
                f"{ticker} "
                + str(
                    output["cross_cell_dependencies"][0]["statement"]
                )
            )
        elif node_id == "memo_writer":
            output["claim_renderings"][0]["analysis_text_zh_cn"] = (
                f"{ticker} "
                + str(
                    output["claim_renderings"][0][
                        "analysis_text_zh_cn"
                    ]
                )
            )

    @staticmethod
    def _inject_nonlocal(
        output: dict[str, Any],
        request: Mapping[str, Any],
        ticker: str,
    ) -> None:
        node_id = str(request.get("node_id") or "")
        segment_id = str(request.get("segment_id") or "")
        if node_id.startswith("domain_specialist:"):
            if segment_id == "facts_explanation_and_terminal":
                output["fact_layer"][0]["statement"] = (
                    f"{ticker} 非本案污染"
                )
            else:
                return
        elif node_id == "research_lead":
            output["cross_cell_dependencies"][0]["statement"] = (
                f"{ticker} 非本案污染"
            )
        elif node_id == "memo_writer":
            output["claim_renderings"][0]["analysis_text_zh_cn"] = (
                f"{ticker} 非本案污染"
            )
        elif node_id == "verifier":
            output["findings"][0]["issue_codes"] = [ticker]

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        messages = kwargs.get("messages")
        system = ""
        if isinstance(messages, list) and messages:
            first = messages[0]
            if isinstance(first, Mapping):
                system = str(first.get("content") or "")
        self.systems.append(system)
        response = dict(self._base(**kwargs))
        request = self.calls[-1]["request"]
        output = json.loads(str(response["content"]))
        self._prefix_narrative(
            output,
            request,
            self.current_ticker,
        )
        if self._phase(request) == self.inject_nonlocal_phase:
            self._inject_nonlocal(
                output,
                request,
                self.nonlocal_ticker,
            )
        response["content"] = json.dumps(
            output,
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def _case_runtime(
    ticker: str,
) -> tuple[Any, S3ThreeCellBoundedAgentAdmission, Any]:
    _, specialists = _shared_local_id_specialists()
    if ticker == "MU":
        input_pack, _ = _mu_input_and_admission()
        historical = json.loads(
            (
                ROOT
                / "configs"
                / "releases"
                / (
                    "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_"
                    "local_materialization_fresh_exact_admission_r2.json"
                )
            ).read_text(encoding="utf-8")
        )
        source_admission = (
            S3ThreeCellBoundedAgentAdmission.model_validate(historical)
        )
        base = _NumericIdentitySafeMuV7Fake(specialists)
    else:
        input_pack, source_admission = (
            _case_fixture_input_and_admission(ticker)
        )
        base = _NumericIdentitySafeFake(input_pack, specialists)
    admission = compile_s4_case_runtime_mandatory_safety_admission(
        source_admission,
        updates={
            "admission_id": (
                f"fixture-s4-t06-{ticker.lower()}-identity-boundary-v2"
            ),
            "execution_mode": (
                "zero_call_current_case_aware_identity_boundary_v2"
            ),
            "case_id": input_pack.case_id,
            "case_version": input_pack.case_version,
            "as_of": input_pack.as_of,
            "input_digest": input_pack.input_digest,
        },
    )
    return input_pack, admission, base


def _execute(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
    *,
    inject_nonlocal_phase: str | None = None,
) -> tuple[Any, _NaturalCurrentCaseIdentityFake]:
    input_pack, admission, base = _case_runtime(ticker)
    nonlocal_ticker = next(
        value
        for value in CaseDeliveryIdentityPolicy.registered_identity_tickers()
        if value != ticker
    )
    fake = _NaturalCurrentCaseIdentityFake(
        base,
        current_ticker=ticker,
        inject_nonlocal_phase=inject_nonlocal_phase,
        nonlocal_ticker=nonlocal_ticker,
    )
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
                f"fixture-s4-t06-{ticker.lower()}-identity-boundary-v2"
            ),
            "attempt_id": (
                f"fixture-s4-t06-{ticker.lower()}-identity-boundary-v2"
            ),
        },
    )
    return result, fake


def test_v1_is_immutable_and_v2_uses_the_versioned_case_registry() -> None:
    v1 = CaseDeliveryIdentityPolicy.compile(
        company="MU",
        s4_case_runtime=None,
    )
    assert v1.contract_ref == S4_CASE_DELIVERY_IDENTITY_POLICY_REF
    assert v1.provider_narrative_has_entity_token(
        {"statement": "MU local context"}
    )

    v2 = CaseDeliveryIdentityPolicy.compile(
        company="MU",
        s4_case_runtime=None,
        contract_ref=(
            S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ),
    )
    assert v2.case_identity_registry_ref == (
        S4_CASE_DELIVERY_IDENTITY_REGISTRY_REF
    )
    assert v2.registered_case_tickers == (
        "NVDA",
        "DELL",
        "MU",
    )
    assert (
        v2.first_provider_narrative_identity_violation(
            {"statement": "MU MU 本案定性判断"}
        )
        is None
    )
    violation = v2.first_provider_narrative_identity_violation(
        {"statement": "MU 与 DELL 混合污染"}
    )
    assert violation is not None
    assert violation["failure_subtype"] == (
        "provider_narrative_nonlocal_registered_case_identity_token"
    )
    assert violation["registered_nonlocal_match_count"] == 1
    assert set(v2.projection()) == {
        "contract_ref",
        "company",
        "case_ticker",
        "case_identity_namespace",
        "case_profile_ref",
        "delivery_language",
        "title_zh_cn",
        "workpaper_entity_label",
        "review_surface_entity_label",
        "manifest_case_ticker",
        "projection_digest",
        "case_identity_registry_ref",
        "registered_case_tickers",
    }
    assert CaseDeliveryIdentityPolicy.from_projection(
        v2.projection()
    ) == v2


@pytest.mark.parametrize("ticker", ("DELL", "MU", "NVDA"))
def test_three_case_natural_current_ticker_full_fake_reaches_six_twelve_nine(
    monkeypatch: pytest.MonkeyPatch,
    ticker: str,
) -> None:
    result, fake = _execute(monkeypatch, ticker)
    assert len(fake.calls) == 12
    assert len(result.provider_output_captures) == 12
    assert len(result.artifacts) == 9
    assert result.terminal_reason == (
        "s3_bounded_agent_three_cell_execution_succeeded"
    )
    narrative_outputs_with_current_ticker = 0
    for capture in result.provider_output_captures:
        output = json.loads(str(capture["assistant_output_text"]))
        narratives = CaseNumericAuthorityPolicy._narrative_values(
            output
        )
        if any(ticker in text for _, text in narratives):
            narrative_outputs_with_current_ticker += 1
    # The first eleven calls own narrative; a passing typed Verifier has no
    # free-narrative field by schema.
    assert narrative_outputs_with_current_ticker == 11
    assert all(
        (
            f"The current case ticker {ticker} may appear only as "
            "non-authoritative analytical context."
        )
        in system
        for system in fake.systems
    )
    manifest = next(
        artifact.payload
        for artifact in result.artifacts
        if artifact.artifact_type == "bounded_agent_manifest"
    )
    assert manifest["case_delivery_identity_policy_ref"] == (
        S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
    )
    assert manifest["case_ticker"] == ticker


@pytest.mark.parametrize(
    ("phase", "expected_call_count"),
    (
        ("specialist", 1),
        ("research_lead", 10),
        ("memo_writer", 11),
        ("verifier", 12),
    ),
)
def test_every_provider_phase_rejects_nonlocal_registered_identity(
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
    expected_call_count: int,
) -> None:
    with pytest.raises(BoundedAgentExecutionError) as caught:
        _execute(
            monkeypatch,
            "MU",
            inject_nonlocal_phase=phase,
        )
    observation = caught.value.failure_observation
    assert observation["failure_codes"] == [
        "s4_case_delivery_identity_provider_narrative_invalid"
    ]
    telemetry = observation["failure_telemetry"][
        "case_delivery_identity"
    ]
    assert telemetry["contract_ref"] == (
        S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
    )
    assert telemetry["failure_subtype"] == (
        "provider_narrative_nonlocal_registered_case_identity_token"
    )
    assert telemetry["registered_nonlocal_match_count"] >= 1
    assert len(telemetry["current_case_identity_digest"]) == 64
    assert telemetry["provider_phase"]
    assert telemetry["segment_id"]
    assert telemetry["raw_text_persisted"] is False
    assert telemetry["private_reasoning_persisted"] is False
    assert len(observation["usage_receipts"]) == expected_call_count
    assert (
        len(caught.value.provider_output_captures)
        == expected_call_count
    )


def test_v2_projection_and_final_delivery_owner_reject_mutation() -> None:
    policy = CaseDeliveryIdentityPolicy.compile(
        company="MU",
        s4_case_runtime=None,
        contract_ref=(
            S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ),
    )
    projection = policy.projection()
    mutated = deepcopy(projection)
    mutated["title_zh_cn"] = "NVDA 三单元内部研究备忘录"
    with pytest.raises(
        ValueError,
        match="projection_mismatch",
    ):
        CaseDeliveryIdentityPolicy.from_projection(mutated)


def test_v2_nonlocal_failure_telemetry_is_canonically_registered() -> None:
    policy = CaseDeliveryIdentityPolicy.compile(
        company="MU",
        s4_case_runtime=None,
        contract_ref=(
            S4_CASE_DELIVERY_IDENTITY_CURRENT_CASE_AWARE_POLICY_REF
        ),
    )
    violation = policy.first_provider_narrative_identity_violation(
        {"statement": "NVDA 非本案污染"}
    )
    assert violation is not None
    telemetry = dict(violation)
    telemetry.update(
        {
            "provider_phase": "domain_specialist:cell",
            "segment_id": "facts_explanation_and_terminal",
        }
    )
    registered = registered_failure_observation(
        "case_delivery_identity",
        telemetry,
    )
    assert is_registered_failure_observation(registered)
    assert registered["failure_subtype"] == (
        "provider_narrative_nonlocal_registered_case_identity_token"
    )
    assert registered["current_case_identity_digest"] == (
        telemetry["current_case_identity_digest"]
    )
    assert registered["registered_nonlocal_match_count"] == 1
    assert registered["raw_text_persisted"] is False
    assert registered["private_reasoning_persisted"] is False


def test_implementation_record_binds_replacement_and_fresh_proof_next() -> None:
    implementation = json.loads(
        IMPLEMENTATION.read_text(encoding="utf-8")
    )
    expected_next = (
        "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-BOUNDARY-"
        "FRESH-AGENT-PROOF-DECISION"
    )
    current_post_R4 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-MINIMUM-ZERO-CALL-IMPLEMENTATION"
    )
    current_after_v2 = (
        "S4-T06-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-FRESH-AGENT-PROOF-DECISION"
    )
    current_after_fresh = (
        "S4-T06-MU-RUNTIME-AUDIT-EVIDENCE-V2-AND-MATERIAL-NUMERIC-"
        "CLASSIFIER-R5-EXACT-LIVE-EXECUTION-AND-SUCCESS-ONLY-PAIRED-ASSESSMENT"
    )
    assert implementation["status"] == (
        "pass_single_zero_call_replacement_bundle_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert implementation["authority"][
        "implementation_bundles_consumed"
    ] == 1
    assert implementation["authority"][
        "automatic_follow_on_repair_bundles"
    ] == 0
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["next_action"] == expected_next
    assert json.loads(
        PROGRAM_BACKLOG.read_text(encoding="utf-8")
    )["next_action"]["item_id"] in {
        expected_next,
        (
            "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-"
            "BOUNDARY-FRESH-EXACT-ADMISSION-R4"
        ),
        current_post_R4,
        current_after_v2,
        current_after_fresh,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    assert json.loads(
        S4_BACKLOG.read_text(encoding="utf-8")
    )["current_next_action"] in {
        expected_next,
        (
            "S4-T06-MU-CURRENT-CASE-AWARE-DELIVERY-IDENTITY-"
            "BOUNDARY-FRESH-EXACT-ADMISSION-R4"
        ),
        current_post_R4,
        current_after_v2,
        current_after_fresh,
        "S4-T06-MU-ACTION-PLANNING-TEMPORAL-AUTHORITY-AND-CAPTURE-V2-"
        "TERMINAL-RESULT-MATERIALIZATION-MINIMUM-ZERO-CALL-IMPLEMENTATION",
    }
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        observed = __import__("hashlib").sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if relative_path == str(
            Path(__file__).resolve().relative_to(ROOT)
        ).replace("\\", "/"):
            continue
        if observed != expected_sha256:
            current = json.loads(
                CURRENT_RUNTIME_IMPLEMENTATION.read_text(
                    encoding="utf-8"
                )
            )
            if (
                current["exact_code_bindings"].get(relative_path)
                == observed
            ):
                continue
            if relative_path in current[
                "historical_exact_binding_supersession"
            ]["allowed_changed_paths"]:
                continue
            successor = json.loads(
                R4_RESULT.read_text(encoding="utf-8")
            )
            assert relative_path in successor[
                "historical_test_binding_supersession"
            ]["allowed_changed_paths"]
