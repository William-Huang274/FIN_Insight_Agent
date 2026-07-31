from __future__ import annotations

from copy import deepcopy
import hashlib
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
    S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY,
    research_lead_transport_contract,
    research_profile_for_ref,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE,
    BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE,
    DeepSeekS3ThreeCellNodeExecutor,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V6_REF,
    S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF,
    S3ResearchLeadV3ContractError,
    S3ScopedIdentityContractError,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S3ThreeCellBoundedAgentInputPack,
    build_s3_three_cell_bounded_agent_executor_for_admission,
    compile_s4_case_runtime_mandatory_safety_admission,
)
from sec_agent.canonical_runtime.models import canonical_digest
from test_fin_0_1_s3_t09_cross_cell_scoped_identity_zero_call_implementation import (
    _ScopedV4FullFakeProvider,
    _shared_local_id_specialists,
)
from test_fin_0_1_s3_t09_research_lead_v5_compact_scoped_reference_dual_capacity_zero_call_implementation import (
    _surface_and_capacity,
)
from test_fin_0_1_s4_t05_case_numeric_authority_and_delivery_identity_zero_call_implementation import (
    _sanitize_provider_narratives,
)


MU_ADMISSION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_fresh_exact_admission_r1.json"
)
MU_PREPARATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_canonical_case_surface_and_fresh_exact_"
    "admission_preparation_zero_call_proof_v1_0.json"
)
IMPLEMENTATION = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_research_lead_fact_presence_local_"
    "materialization_minimum_zero_call_implementation_v1_0.json"
)
CURRENT_RUNTIME_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_runtime_audit_evidence_v2_"
    "and_material_numeric_classifier_minimum_zero_call_"
    "implementation_v1_0.json"
)
CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_s4_t06_mu_current_case_aware_"
    "delivery_identity_boundary_scope_replacement_minimum_zero_call_"
    "implementation_v1_0.json"
)


def _provider_response(
    output: Mapping[str, Any],
    call_number: int,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "finish_reason": "stop",
        "content": json.dumps(output, ensure_ascii=False, sort_keys=True),
        "input_tokens": 10,
        "output_tokens": 100,
        "total_tokens": 110,
        "call_id": f"fixture-mu-source-grounded-v7-{call_number}",
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


class _MuSourceGroundedV7FullFakeProvider(_ScopedV4FullFakeProvider):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        request = json.loads(kwargs["messages"][1]["content"])
        node_id = str(request["node_id"])
        if node_id.startswith("domain_specialist:"):
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            cell_id = node_id.split(":", 1)[1]
            segment_id = str(request["segment_id"])
            if segment_id == "facts_explanation_and_terminal":
                allowed = request["fact_support_authority_contract"][
                    "allowed_refs_by_support_type"
                ]
                support_type = (
                    "Evidence" if allowed["Evidence"] else "Numeric"
                )
                output = {
                    "program_cell_id": cell_id,
                    "fact_layer": [
                        {
                            "fact_id": "fact-local-001",
                            "statement": "Official issuer evidence is present.",
                            "support_type": support_type,
                            "support_refs": [allowed[support_type][0]],
                            "boundary": (
                                "The evidence supports only a bounded judgment."
                            ),
                        }
                    ],
                    "explanation_layer": [
                        "The admitted source supports a bounded conclusion."
                    ],
                    "remaining_gaps": [
                        "Future durability remains unproven."
                    ],
                    "terminal_class": "bounded_inference",
                }
            elif segment_id == "owner_grade_claim_cards":
                fact_alias = request["claim_fact_link_contract"][
                    "allowed_facts"
                ][0]["fact_alias"]
                output = {
                    "program_cell_id": cell_id,
                    "judgment_layer": [
                        {
                            "claim_id": "claim-local-001",
                            "statement": (
                                "Issuer evidence supports a bounded outlook."
                            ),
                            "epistemic_status": "bounded_inference",
                            "scope": {
                                "metric_or_mechanism": (
                                    "HBM demand and value capture"
                                )
                            },
                            "context_refs": [],
                            "support_fact_aliases": [fact_alias],
                            "qualification": (
                                "The conclusion is bounded by disclosed evidence."
                            ),
                            "cannot_support": [
                                "It does not prove a future financial outcome."
                            ],
                        }
                    ],
                }
            else:
                allowed = request["what_would_change_authority_contract"][
                    "allowed_refs_by_authority_class"
                ]
                authority_ref = next(
                    ref
                    for authority_class in (
                        "Evidence",
                        "Numeric",
                        "Graph",
                        "Candidate",
                    )
                    for ref in allowed[authority_class]
                )
                output = {
                    "program_cell_id": cell_id,
                    "what_would_change": [
                        {
                            "task_id": "wwc-local-001",
                            "claim_id": "claim-local-001",
                            "metric_or_observation": (
                                "An updated issuer disclosure"
                            ),
                            "source_target": {
                                "source_type": "issuer filing",
                                "entity_or_owner": "MU",
                                "document_event_or_dataset": (
                                    "next earnings disclosure"
                                ),
                            },
                            "decision_rule": {
                                "rule_type": "directional_update",
                                "comparator_or_condition": (
                                    "new evidence changes the bounded outlook"
                                ),
                                "threshold_or_observation": (
                                    "issuer-bound evidence is observed"
                                ),
                            },
                            "expected_claim_transition": (
                                "Reassess the claim's epistemic status."
                            ),
                            "time_window": {
                                "as_of": "2026-07-26",
                                "start_or_trigger": "next issuer disclosure",
                                "deadline_or_review_date": (
                                    "next scheduled review"
                                ),
                            },
                            "fallback_stop_condition": (
                                "Stop if no issuer-bound update is available."
                            ),
                            "authority_refs": [authority_ref],
                        }
                    ],
                }
            return _provider_response(output, len(self.calls))
        if node_id == "research_lead":
            self.calls.append({"kwargs": dict(kwargs), "request": request})
            rows = request["analysis_input"][
                "compact_scoped_reference_alias_table"
            ]["rows"]
            claims = [
                row["alias"]
                for row in rows
                if row["identity_kind"] == "claim"
            ]
            tasks = [
                row["alias"]
                for row in rows
                if row["identity_kind"] == "what_would_change"
            ]
            output = {
                "cross_cell_dependencies": [
                    {
                        "statement": (
                            "Demand durability constrains value capture."
                        ),
                        "claim_ids": claims,
                    }
                ],
                "conflict_adjudications": [
                    {
                        "involved_claim_ids": claims,
                        "terminal_state_summary": (
                            "All three cells remain bounded."
                        ),
                        "resolution_status": "bounded_not_resolved",
                        "statement": (
                            "The evidence supports a bounded joint view."
                        ),
                    }
                ],
                "variant_view": {
                    "statement": (
                        "The outlook varies with demand conversion."
                    ),
                    "claim_ids": claims,
                    "what_would_change_task_ids": tasks,
                },
                "remaining_gaps": [
                    {
                        "statement": (
                            "Future HBM financial durability remains unproven."
                        ),
                        "claim_ids": claims,
                        "what_would_change_task_ids": tasks,
                    }
                ],
            }
            return _provider_response(output, len(self.calls))
        return super().__call__(**kwargs)


class _NumericIdentitySafeMuSourceGroundedV7FullFakeProvider(
    _MuSourceGroundedV7FullFakeProvider
):
    def __call__(self, **kwargs: Any) -> Mapping[str, Any]:
        response = dict(super().__call__(**kwargs))
        output = json.loads(str(response["content"]))
        response["content"] = json.dumps(
            _sanitize_provider_narratives(output),
            ensure_ascii=False,
            sort_keys=True,
        )
        return response


def _v7_surface(
    support_mode: str,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
    Any,
    dict[str, Any],
]:
    specialists, _, _, _, _ = _surface_and_capacity()
    specialists = deepcopy(specialists)
    for ordinal, specialist in enumerate(specialists):
        claim = specialist["judgment_layer"][0]
        claim["support_fact_ids"] = (
            ["fact-local-001"]
            if support_mode == "all"
            or (support_mode == "some" and ordinal == 0)
            else []
        )
        if not claim["support_fact_ids"]:
            claim["epistemic_status"] = "hypothesis"
            claim["qualification"] = "No direct Fact supports this claim."
    surface = S3ThreeCellBoundedAgentExecutor._derive_scoped_identity_surface(
        specialists
    )
    digests = {
        str(row["program_cell_id"]): canonical_digest(row)
        for row in specialists
    }
    profile = research_profile_for_ref(
        "fin01.s3.research_profile.nvda_three_cell:v2"
    )
    heads = DeepSeekS3ThreeCellNodeExecutor._derive_research_lead_cell_heads(
        specialists,
        digests,
        research_profile=profile,
    )
    alias_table = (
        S3ThreeCellBoundedAgentExecutor._compact_scoped_alias_table(
            specialists,
            surface,
        )
    )
    capacity = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_capacity_envelope(
            alias_table=alias_table,
            cell_heads=heads,
            research_profile=profile,
        )
    )
    return specialists, surface, heads, profile, capacity


def _v7_segment(involved_claim_ids: list[str]) -> dict[str, Any]:
    return {
        "cross_cell_dependencies": [
            {"statement": "dependency", "claim_ids": ["C001"]}
        ],
        "conflict_adjudications": [
            {
                "involved_claim_ids": involved_claim_ids,
                "terminal_state_summary": "bounded",
                "resolution_status": "unresolved",
                "statement": "conflict",
            }
        ],
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


def _assemble(
    support_mode: str,
    involved_claim_ids: list[str],
) -> dict[str, Any]:
    specialists, surface, heads, profile, capacity = _v7_surface(
        support_mode
    )
    return DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v7_output(
        _v7_segment(involved_claim_ids),
        specialists,
        surface,
        cell_heads=heads,
        research_profile=profile,
        capacity=capacity,
    )


def _mu_input_and_admission() -> tuple[
    S3ThreeCellBoundedAgentInputPack,
    S3ThreeCellBoundedAgentAdmission,
]:
    preparation = json.loads(MU_PREPARATION.read_text(encoding="utf-8"))
    object_key = preparation["canonical_materialization"][
        "input_object_ref"
    ]["object_key"]
    object_path = (
        ROOT
        / ".codex_runtime"
        / "fin01-s3-t09-three-cell-deepseek-segmented-live-validation-r1"
        / "canonical-runtime"
        / "objects"
        / object_key
    )
    prepared = json.loads(object_path.read_text(encoding="utf-8"))
    input_pack = S3ThreeCellBoundedAgentInputPack.model_validate(
        prepared["input_pack"]
    )
    admission = compile_s4_case_runtime_mandatory_safety_admission(
        S3ThreeCellBoundedAgentAdmission.model_validate(
            json.loads(MU_ADMISSION.read_text(encoding="utf-8"))
        ),
        updates={
            "admission_id": "fixture-s4-t06-mu-source-grounded-v7",
            "execution_mode": "fixture_only_mu_source_grounded_v7",
            "research_lead_transport_ref": (
                S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
            ),
        },
    )
    return input_pack, admission


def test_v7_registry_is_v5_plus_local_fact_presence_only() -> None:
    policy = (
        S3_RESEARCH_LEAD_CONFLICT_FACT_PRESENCE_LOCAL_MATERIALIZATION_POLICY
    )
    v5 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V5_REF
    )
    v7 = research_lead_transport_contract(
        S3_OWNER_GRADE_RESEARCH_LEAD_TRANSPORT_V7_REF
    )
    assert v7.conflict_fact_presence_materialization_policy_ref == (
        policy.policy_ref
    )
    assert v7.gap_atom_deterministic_projection is False
    assert {
        key: value
        for key, value in v7.__dict__.items()
        if key
        not in {
            "transport_ref",
            "conflict_fact_presence_materialization_policy_ref",
        }
    } == {
        key: value
        for key, value in v5.__dict__.items()
        if key
        not in {
            "transport_ref",
            "conflict_fact_presence_materialization_policy_ref",
        }
    }


def test_v7_request_omits_provider_field_and_preserves_v5_v6_history() -> None:
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
        research_profile=research_profile_for_ref(
            "fin01.s3.research_profile.nvda_three_cell:v2"
        ),
        capacity=capacity,
    )
    _, v6_before, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v6_request(
        payload,
        heads,
        research_profile=research_profile_for_ref(
            "fin01.s3.research_profile.nvda_three_cell:v2"
        ),
        capacity=capacity,
    )
    v5_digest = canonical_digest(v5_before)
    v6_digest = canonical_digest(v6_before)
    system, request, binding = (
        DeepSeekS3ThreeCellNodeExecutor._research_lead_v7_request(
            payload,
            heads,
            research_profile=research_profile_for_ref(
                "fin01.s3.research_profile.nvda_three_cell:v2"
            ),
            capacity=capacity,
        )
    )
    conflict_schema = request["required_output_schema"][
        "conflict_adjudications"
    ][0]
    assert "fact_presence_summary" not in conflict_schema
    assert request["output_constraints"][
        "provider_emits_fact_presence_summary"
    ] is False
    assert request["output_constraints"][
        "conflict_fact_presence_owner"
    ] == "local_deterministic_runtime"
    assert "Do not emit fact_presence_summary" in system
    assert binding["conflict_fact_presence_materialization_policy_ref"]
    _, v5_after, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v5_request(
        payload,
        heads,
        research_profile=research_profile_for_ref(
            "fin01.s3.research_profile.nvda_three_cell:v2"
        ),
        capacity=capacity,
    )
    _, v6_after, _ = DeepSeekS3ThreeCellNodeExecutor._research_lead_v6_request(
        payload,
        heads,
        research_profile=research_profile_for_ref(
            "fin01.s3.research_profile.nvda_three_cell:v2"
        ),
        capacity=capacity,
    )
    assert canonical_digest(v5_after) == v5_digest
    assert canonical_digest(v6_after) == v6_digest


@pytest.mark.parametrize(
    ("support_mode", "expected"),
    (
        ("all", "facts_present"),
        ("none", "no_facts_present"),
        ("some", "mixed_fact_presence"),
    ),
)
def test_v7_materializes_all_none_some_truth_table(
    support_mode: str,
    expected: str,
) -> None:
    output = _assemble(support_mode, ["C001", "C002", "C003"])
    assert output["conflict_adjudications"][0][
        "fact_presence_summary"
    ] == expected
    assert canonical_digest(output) == canonical_digest(
        _assemble(support_mode, ["C001", "C002", "C003"])
    )


@pytest.mark.parametrize(
    "involved_claim_ids",
    (
        ["C999"],
        ["W001"],
        ["C001", "C001"],
    ),
)
def test_v7_invalid_aliases_fail_before_local_materialization(
    involved_claim_ids: list[str],
) -> None:
    with pytest.raises(S3ScopedIdentityContractError):
        _assemble("all", involved_claim_ids)


def test_v7_rejects_provider_attempt_to_emit_runtime_owned_field() -> None:
    specialists, surface, heads, profile, capacity = _v7_surface("all")
    segment = _v7_segment(["C001", "C002", "C003"])
    segment["conflict_adjudications"][0][
        "fact_presence_summary"
    ] = "facts_present"
    with pytest.raises(
        S3ResearchLeadV3ContractError,
        match="item_schema_invalid",
    ):
        DeepSeekS3ThreeCellNodeExecutor._assemble_research_lead_v7_output(
            segment,
            specialists,
            surface,
            cell_heads=heads,
            research_profile=profile,
            capacity=capacity,
        )


def test_mu_source_grounded_full_fake_reaches_twelve_calls_and_nine_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    input_pack, admission = _mu_input_and_admission()
    _, specialists = _shared_local_id_specialists()
    fake = _NumericIdentitySafeMuSourceGroundedV7FullFakeProvider(
        specialists
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
            "research_run_id": "fixture-s4-t06-mu-source-grounded-v7"
        },
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
    judgment = artifacts[BOUNDED_AGENT_JUDGMENT_ARTIFACT_TYPE]
    manifest = artifacts[BOUNDED_AGENT_MANIFEST_ARTIFACT_TYPE]
    assert judgment["cross_cell_lead"]["conflict_adjudications"][0][
        "fact_presence_summary"
    ] == "facts_present"
    assert manifest["recoverable_protocol_findings"] == []
    lead_request = next(
        call["request"]
        for call in fake.calls
        if call["request"]["node_id"] == "research_lead"
    )
    assert "fact_presence_summary" not in lead_request[
        "required_output_schema"
    ]["conflict_adjudications"][0]


def test_implementation_record_binds_current_code_and_next_gate() -> None:
    implementation = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    assert implementation["status"] == (
        "pass_zero_call_implementation_fixture_proven_"
        "fresh_agent_proof_pending"
    )
    assert implementation["authority"]["implementation_bundles_consumed"] == 1
    assert implementation["authority"][
        "automatic_follow_on_repair_bundles"
    ] == 0
    assert implementation["fixture_proof"]["focused_tests"] == "11 passed"
    assert implementation["fixture_proof"]["MU_source_grounded_full_fake"][
        "logical_artifacts"
    ] == 9
    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["next_action"] == (
        "S4-T06-MU-RESEARCH-LEAD-CONFLICT-FACT-PRESENCE-LOCAL-"
        "MATERIALIZATION-FRESH-AGENT-PROOF-DECISION"
    )
    for relative_path, expected_sha256 in implementation[
        "exact_code_bindings"
    ].items():
        observed = hashlib.sha256(
            (ROOT / relative_path).read_bytes()
        ).hexdigest()
        if observed == expected_sha256:
            continue
        identity_boundary = json.loads(
            CURRENT_IDENTITY_BOUNDARY_IMPLEMENTATION.read_text(
                encoding="utf-8"
            )
        )
        if (
            identity_boundary["exact_code_bindings"].get(
                relative_path
            )
            == observed
        ):
            continue
        current = json.loads(
            CURRENT_RUNTIME_IMPLEMENTATION.read_text(
                encoding="utf-8"
            )
        )
        current_digest = current["exact_code_bindings"].get(
            relative_path
        )
        if current_digest is not None:
            assert current_digest == observed
            continue
        assert relative_path in current[
            "historical_exact_binding_supersession"
        ]["allowed_changed_paths"]
