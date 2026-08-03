from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    BoundedAgentExecutionError,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF,
    S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V9_REF,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_fin_0_1_2_s3_production_admission,
)
from apps.workbench.backend.application.fin_0_1_2_s3_product_input import (
    assert_fin_0_1_2_s3_exact_input_matches_manifest,
)
from apps.workbench.backend.application.fin_0_1_2_s3_runtime_contract_binding import (
    FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF,
    FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF,
    Fin012RuntimeContractBindingError,
    compile_fin_0_1_2_s3_runtime_contract_binding,
    load_fin_0_1_2_s3_runtime_contract_binding,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_deepseek_transport_exact_input_preflight_repair import (
    _admission,
    _create_accepted_case,
    _prepare,
)
from test_fin_0_1_s4_t05_research_lead_gap_atom_deterministic_projection_zero_call_implementation import (
    _GapAtomV6FullFakeProvider,
)


class _CurrentS3ProductionFake:
    """Input-driven compiled atoms plus the established downstream fake."""

    def __init__(
        self,
        *,
        safe_lead: bool,
        inject_runtime_owned_lead_field: bool = False,
    ) -> None:
        _, historical_specialists = _shared_local_id_specialists()
        self.base = _GapAtomV6FullFakeProvider(historical_specialists)
        self.safe_lead = safe_lead
        self.inject_runtime_owned_lead_field = inject_runtime_owned_lead_field
        self.compiled_calls = 0

    @property
    def calls(self) -> list[dict[str, Any]]:
        return self.base.calls

    @staticmethod
    def _response(output: Mapping[str, Any], call_number: int) -> dict[str, Any]:
        return {
            "status": "ok",
            "finish_reason": "stop",
            "content": json.dumps(output, ensure_ascii=False, sort_keys=True),
            "input_tokens": 10,
            "output_tokens": 10,
            "total_tokens": 20,
            "call_id": f"fixture-s3-production-{call_number}",
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

    @staticmethod
    def _compiled_output(contract: Mapping[str, Any]) -> dict[str, Any]:
        family = str(contract["family_id"])
        cell_id = str(contract["program_cell_id"])
        if family == "claim_candidate_atoms":
            facts = list(contract["allowed_facts"])
            return {
                "program_cell_id": cell_id,
                "claim_candidate_atoms": [
                    {
                        "support_fact_aliases": (
                            [str(facts[0]["fact_alias"])] if facts else []
                        ),
                        "claim_kind": (
                            "evidence_direction"
                            if facts
                            else "insufficient_evidence"
                        ),
                        "direction": "unknown",
                        "materiality": "high",
                        "confidence": "high",
                        "priority": "high",
                    }
                ],
            }
        if family != "what_would_change_atoms":
            raise AssertionError(f"unexpected Provider family: {family}")
        claim = str(contract["allowed_claims"][0]["claim_alias"])
        authority = str(
            contract["allowed_authorities"][0]["authority_alias"]
        )
        return {
            "program_cell_id": cell_id,
            "what_would_change_atoms": [
                {
                    "claim_alias": claim,
                    "primary_authority_alias": authority,
                    "authority_aliases": [authority],
                    "trigger_code": "authority_contradiction",
                    "direction": "challenges",
                    "review_cadence": "next_authority_event",
                    "start_date_alias": "NONE",
                    "review_date_alias": "NONE",
                    "expected_claim_transition": "weaken",
                }
            ],
        }

    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        contract = request.get("compiled_judgment_atom_contract")
        if isinstance(contract, Mapping):
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            self.compiled_calls += 1
            return self._response(
                self._compiled_output(contract), len(self.calls)
            )

        response = dict(self.base(**kwargs))
        if request["node_id"] == "research_lead":
            output = json.loads(str(response["content"]))
            if self.safe_lead:
                labels = "甲乙丙丁戊己庚辛"
                for row, label in zip(
                    output["remaining_gap_atoms"], labels, strict=True
                ):
                    row["statement"] = (
                        str(row["statement"]).split(" #", 1)[0]
                        + f" {label}"
                    )
            if (
                request.get("research_lead_transport_ref")
                == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF
            ):
                for row in output["conflict_adjudications"]:
                    row.pop("fact_presence_summary", None)
                if self.inject_runtime_owned_lead_field:
                    output["conflict_adjudications"][0][
                        "fact_presence_summary"
                    ] = "mixed_fact_presence"
            response["content"] = json.dumps(
                output, ensure_ascii=False, sort_keys=True
            )
        return response


def _compiled_admission(prepared: Any, *, enabled: bool = True) -> Any:
    source = _admission(prepared).model_copy(
        update={"execution_enabled": enabled}
    )
    return compile_fin_0_1_2_s3_production_admission(
        source,
        updates={
            "admission_id": "fixture-fin012-s3-t02-production-v1",
            "execution_mode": "zero_call_s3_t02_production_proof",
        },
    )


def test_s3_binding_rejects_manifest_mutation() -> None:
    binding = load_fin_0_1_2_s3_runtime_contract_binding()
    assert binding.binding_ref == FIN_0_1_2_S3_COMMON_RUNTIME_BINDING_REF
    assert (
        binding.compiled_contract_ref
        == FIN_0_1_2_S3_COMMON_RUNTIME_COMPILED_CONTRACT_REF
    )

    manifest_path = ROOT / (
        "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
        "binding_v1_3.json"
    )
    source_path = ROOT / (
        "configs/runtime/fin_ia_0_1_2_common_runtime_contract_family_"
        "source_v1_3.json"
    )
    mutated = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutated["source_canonical_digest"] = canonical_digest("mutation")
    with pytest.raises(Fin012RuntimeContractBindingError):
        compile_fin_0_1_2_s3_runtime_contract_binding(
            source_bytes=source_path.read_bytes(),
            manifest=mutated,
        )


def test_current_nvda_exact_input_runs_six_nodes_twelve_interactions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, local_service, evidence_service, case, accepted = _create_accepted_case(
        tmp_path
    )
    prepared = _prepare(local_service, evidence_service, case, accepted)
    input_receipt = assert_fin_0_1_2_s3_exact_input_matches_manifest(
        prepared.input_pack,
        source_digest=prepared.preparation_digest,
    )
    assert input_receipt["paid_execution_authorized"] is False
    mutated_input = prepared.input_pack.model_copy(
        update={"query": "mutated input must not match the tracked head"}
    )
    with pytest.raises(
        ValueError, match="fin012_s3_exact_product_input_manifest_mismatch"
    ):
        assert_fin_0_1_2_s3_exact_input_matches_manifest(
            mutated_input,
            source_digest=prepared.preparation_digest,
        )

    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    prospective = _compiled_admission(prepared, enabled=False)
    assert prospective.execution_enabled is False
    assert prospective.max_provider_calls == 0
    assert prospective.max_total_cost_usd == 0.0

    admission = _compiled_admission(prepared)
    assert admission.transport_ref == S3_OWNER_GRADE_SEGMENTED_SPECIALIST_TRANSPORT_V9_REF
    assert (
        admission.research_lead_transport_ref
        == S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V8_REF
    )
    assert (
        admission.max_provider_calls,
        admission.max_total_cost_usd,
        admission.specialist_max_output_tokens * 3
        + admission.lead_max_output_tokens
        + admission.writer_max_output_tokens
        + admission.verifier_max_output_tokens,
    ) == (9, 0.06, 10000)

    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")
    fake = _CurrentS3ProductionFake(safe_lead=True)
    executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=fake
    )
    result = executor.execute(
        prepared.input_pack,
        admission,
        run_identity={
            "research_run_id": "fixture-s3-t02-current-nvda",
            "attempt_id": "fixture-s3-t02-current-nvda-a1",
        },
    )

    assert len(fake.calls) == 9
    assert fake.compiled_calls == 6
    assert all(
        row["request"].get("compiled_judgment_atom_contract", {}).get(
            "family_id"
        )
        != "specialist_fact_atoms"
        for row in fake.calls
    )
    assert len(result.provider_output_captures) == 9
    assert len(result.artifacts) == 9
    assert len(result.execution_observation["local_fact_receipts"]) == 3
    assert result.execution_observation["observed_counts"] == {
        "model_calls": 9,
        "provider_calls": 9,
        "network_calls": 9,
        "source_network_calls": 0,
        "external_tool_calls": 0,
        "live_case_head_writes": 0,
        "evaluation_evidence_promotions": 0,
    }
    manifest = next(
        row.payload
        for row in result.artifacts
        if row.artifact_type == BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE
    )
    assert manifest["interaction_topology"] == {
        "logical_node_count": 6,
        "logical_interaction_count": 12,
        "local_fact_interaction_count": 3,
        "provider_interaction_count": 9,
        "provider_capture_count": 9,
        "business_artifact_count": 9,
    }

    failing_fake = _CurrentS3ProductionFake(
        safe_lead=True,
        inject_runtime_owned_lead_field=True,
    )
    failing_executor = build_s3_three_cell_bounded_agent_executor_for_admission(
        admission, chat_completion_fn=failing_fake
    )
    with pytest.raises(BoundedAgentExecutionError) as captured:
        failing_executor.execute(
            prepared.input_pack,
            admission,
            run_identity={
                "research_run_id": "fixture-s3-t02-failure",
                "attempt_id": "fixture-s3-t02-failure-a1",
            },
        )
    failure = captured.value
    assert failure.stage == "research_lead"
    assert len(failure.provider_output_captures) == 7
    assert len(failure.failure_observation["local_fact_receipts"]) == 3
    assert len(failure.failure_observation["completed_node_receipts"]) == 3
    assert failure.failure_observation["failure_code"] == (
        "s3_bounded_research_lead_v3_shape_item_schema_invalid"
    )
