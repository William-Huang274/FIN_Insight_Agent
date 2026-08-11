from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from sec_agent.multi_agent_runtime import build_agent_data_view
from sec_agent.product_intelligence_runtime import (
    product_intelligence_context_rows_for_state,
)
from sec_agent.s2_representative_node_program import (
    S2RepresentativeNodeError,
    build_representative_node_input,
    compile_representative_node_program,
    validate_representative_node_program,
)


ROOT = Path(__file__).resolve().parents[2]
S2_DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_01_"
    "research_question_method_contract_translation_v1_0.json"
)
POLICY = ROOT / "configs" / "runtime" / (
    "fin_ia_0_1_3_repair_closeout_s2_"
    "representative_node_and_natural_canary_policy_v1_0.json"
)
DECISION = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "representative_node_context_precedence_and_canary_entry_v1_0.json"
)
ACTIVE = ROOT / "configs" / "releases" / (
    "fin_ia_0_1_3_repair_closeout_s2_02_"
    "active_test_suite_successor_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _explicit_state() -> dict:
    return {
        "user_query": "Assess NVDA demand from the supplied evidence only.",
        "query_contract": {"focus_tickers": ["NVDA"]},
        "agent_activation_plan": {
            "execution_mode": "standard_memo",
            "activate_agents": ["industry_supply_chain_analyst"],
        },
        "industry_snapshot_rows": [
            {
                "evidence_ref": "explicit_nvda_industry_row",
                "source_family": "industry_snapshot",
                "ticker": "NVDA",
                "summary": "Explicit bounded industry evidence.",
            }
        ],
    }


def test_direct_specialist_view_is_hermetic_across_working_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = _explicit_state()
    repo_view = build_agent_data_view("industry_supply_chain_analyst", state)
    monkeypatch.chdir(tmp_path)
    isolated_view = build_agent_data_view("industry_supply_chain_analyst", state)

    assert repo_view["context_digest"] == isolated_view["context_digest"]
    assert repo_view["bounded_evidence_rows"] == isolated_view["bounded_evidence_rows"]
    assert {row["evidence_ref"] for row in repo_view["bounded_evidence_rows"]} == {
        "explicit_nvda_industry_row"
    }


def test_explicit_production_autoload_remains_available() -> None:
    state = {**_explicit_state(), "product_intelligence_runtime_autoload": True}
    rows = product_intelligence_context_rows_for_state(
        state,
        tickers=["NVDA"],
        repo_root=ROOT,
        autoload=True,
    )

    assert rows
    assert any(row.get("product_intelligence_row") for row in rows)


def test_representative_specialist_claim_lead_program_consumes_all_nodes() -> None:
    decision = _load(S2_DECISION)
    program = compile_representative_node_program(s2_decision=decision)
    validate_representative_node_program(program, s2_decision=decision)

    assert program["observed_counts"] == {
        "representative_specialist_nodes": 9,
        "materialized_claims": 9,
        "representative_lead_nodes": 3,
        "case_count": 3,
        "model_calls": 0,
        "provider_calls": 0,
        "network_calls": 0,
        "source_calls": 0,
        "business_runs": 0,
    }
    assert program["method_lifecycle"]["runtime_injected_into_representative_node"] is True
    assert program["method_lifecycle"]["node_level_consumed"] is True
    assert all(claim["provider_free_text_fields"] == [] for claim in program["materialized_claims"])
    assert all(len(lead["specialist_claim_refs"]) == 3 for lead in program["lead_syntheses"])


def test_representative_node_input_is_bound_to_explicit_governed_request() -> None:
    decision = _load(S2_DECISION)
    request = decision["research_question_method_program"]["representative_requests"][0]
    node_input = build_representative_node_input(request)

    assert node_input["context_authority"] == "explicit_current_governed_pack"
    assert node_input["repository_environment_autoload"] is False
    assert node_input["request_digest"] == request["request_digest"]
    assert node_input["model_visible_request"] == request["model_visible_request"]


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("cross_case_alias", "s2_provider_mechanism_alias_invalid"),
        ("free_text", "s2_provider_output_shape_invalid"),
        ("claim_digest", "representative_claim_digest_invalid"),
        ("autoload", "representative_context_injection_invalid"),
    ],
)
def test_representative_program_mutations_fail_closed(
    mutation: str, expected_code: str
) -> None:
    decision = _load(S2_DECISION)
    if mutation in {"cross_case_alias", "free_text"}:
        research = decision["research_question_method_program"]
        request = research["representative_requests"][0]
        output = deepcopy(research["fake_provider_outputs"][0]["provider_output"])
        if mutation == "cross_case_alias":
            output["mechanism_alias"] = "MU_M_DEMAND_01"
        else:
            output["narrative"] = "unbounded"
        with pytest.raises(S2RepresentativeNodeError) as exc:
            compile_representative_node_program(
                s2_decision=decision,
                provider_outputs={request["request_id"]: output},
            )
    else:
        program = compile_representative_node_program(s2_decision=decision)
        broken = deepcopy(program)
        if mutation == "claim_digest":
            broken["materialized_claims"][0]["claim_digest"] = "0" * 64
        else:
            broken["context_injection_contract"]["repository_environment_autoload"] = True
        body = {key: value for key, value in broken.items() if key != "program_digest"}
        from sec_agent.retrieval_evidence_usefulness_program import canonical_digest

        broken["program_digest"] = canonical_digest(body)
        with pytest.raises(S2RepresentativeNodeError) as exc:
            validate_representative_node_program(broken, s2_decision=decision)
    assert exc.value.code == expected_code


def test_natural_canary_policy_is_bounded_and_preregistered() -> None:
    policy = _load(POLICY)
    canary = policy["natural_canary"]

    assert policy["context_injection"]["implicit_repository_autoload"] is False
    assert len(canary["selected_requests"]) == 3
    assert len({row["family"] for row in canary["selected_requests"]}) == 3
    assert canary["budgets"] == {
        "maximum_provider_calls": 3,
        "maximum_calls_per_changed_family": 1,
        "retry_count": 0,
        "fallback_count": 0,
        "full_chain_calls": 0,
    }
    assert canary["rubric"]["all_three_requests_must_pass"] is True
    assert canary["rubric"]["no_cross_request_averaging"] is True
    assert policy["stage_boundary"]["canary_is_not_product_acceptance"] is True


def test_materialized_decision_and_active_suite_are_digest_bound() -> None:
    from sec_agent.retrieval_evidence_usefulness_program import canonical_digest

    decision = _load(DECISION)
    active = _load(ACTIVE)
    decision_body = {
        key: value for key, value in decision.items() if key != "record_digest"
    }
    active_body = {
        key: value for key, value in active.items() if key != "suite_digest"
    }

    assert decision["record_digest"] == canonical_digest(decision_body)
    assert active["suite_digest"] == canonical_digest(active_body)
    assert active["decision_sha256"] == hashlib.sha256(DECISION.read_bytes()).hexdigest()
    assert decision["root_cause_corrections"]["RC-P36-138"]["status"] == "closed_zero_call"
    assert decision["natural_canary_entry"]["status"] == "eligible_for_fresh_admission_not_issued_not_run"
    validate_representative_node_program(
        decision["representative_node_program"],
        s2_decision=_load(S2_DECISION),
    )


def test_materialized_public_contracts_do_not_expose_private_runtime_refs() -> None:
    serialized = json.dumps(
        {"decision": _load(DECISION), "active": _load(ACTIVE)},
        ensure_ascii=False,
    )

    for forbidden in (
        "data/workbench_private",
        "source_capture_ref",
        "credential_digest",
        "C:\\Users\\",
        "D:\\temp\\",
    ):
        assert forbidden not in serialized
