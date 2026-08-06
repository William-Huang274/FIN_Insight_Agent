from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sec_agent.s3_claim_quality_program import (
    S3ClaimQualityError,
    compile_s3_claim_quality_all_natural_successor,
    load_s3_claim_quality_policy,
)
from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s3_cross_cell_synthesis_program import (
    compile_s3_cross_cell_synthesis_program,
    load_s3_cross_cell_policy,
)
from sec_agent.s3_evidence_role_contract import (
    S3EvidenceRoleContractError,
    compile_s3_evidence_selection_context,
    consume_s3_evidence_selection_output,
    validate_s3_evidence_selection_output,
)
from sec_agent.s3_evidence_role_canary_runtime import (
    execute_evidence_role_canary,
    issue_evidence_role_canary_admission,
)
from sec_agent.s3_formal_anchor_runtime import (
    execute_formal_anchor,
    issue_formal_anchor_admission,
)
from sec_agent.s3_research_quality_gate import (
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
)
from sec_agent.s3_workpaper_writer_content_program import (
    compile_s3_workpaper_writer_content_program,
    load_s3_workpaper_writer_content_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger


ROOT = Path(__file__).resolve().parents[2]
DECISION = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_disposition_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_active_test_suite_successor_v1_0.json"
CANARY_READINESS = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_v1_0.json"
CANARY_ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_readiness_active_test_suite_successor_v1_0.json"
CANARY_RESULT = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_and_replacement_authority_v1_0.json"
CANARY_RESULT_ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_result_active_test_suite_successor_v1_0.json"


def _load(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _surface() -> tuple[dict[str, dict], dict[str, dict], list[dict[str, str]]]:
    s2 = _load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json")
    old_program = _load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json")
    requests = {row["request_id"]: row for row in s2["research_question_method_program"]["representative_requests"]}
    old_contexts = {row["request_id"]: row for row in old_program["role_scoped_contexts"]}
    contexts = {
        request_id: compile_s3_evidence_selection_context(s2_context=old_contexts[request_id])
        for request_id in requests
    }
    bindings = [
        {
            "request_id": request_id,
            "request_digest": requests[request_id]["request_digest"],
            "context_digest": contexts[request_id]["context_digest"],
        }
        for request_id in requests
    ]
    return requests, contexts, bindings


def _admission() -> dict:
    _, _, bindings = _surface()
    policy = _load("configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v1_0.json")
    issued = datetime(2026, 8, 6, 19, 0, tzinfo=timezone.utc)
    return issue_formal_anchor_admission(
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        s2_decision_sha256="3" * 64,
        context_program_sha256="4" * 64,
        quality_gate_sha256="5" * 64,
        policy_sha256="6" * 64,
        request_bindings=bindings,
        issued_at=issued.isoformat(),
        expires_at=(issued + timedelta(minutes=30)).isoformat(),
        run_nonce="evidence-role-v2-fixture",
        credential_present=True,
        provider=policy["provider"],
        budget=policy["budget"],
        contract_version="v2",
    )


def _selection(context: dict, *, cannot_infer_with_observation: bool = False) -> dict:
    evidence = [row["alias"] for row in context["evidence_options"]]
    gaps = [row["alias"] for row in context["gap_options"]]
    cannot = cannot_infer_with_observation or not evidence
    return {
        "epistemic_state": "cannot_infer" if cannot else "bounded_inference",
        "answer_direction": "cannot_infer" if cannot else "positive",
        "mechanism_alias": context["mechanism_options"][0]["alias"],
        "selected_evidence_aliases": evidence,
        "selected_counterevidence_aliases": [],
        "gap_aliases": gaps,
        "confidence": "high" if cannot_infer_with_observation else "medium",
        "what_would_change_aliases": [context["what_would_change_options"][0]["alias"]],
    }


class V2Provider:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        context = json.loads(kwargs["messages"][1]["content"])
        output = _selection(
            context,
            cannot_infer_with_observation=len(self.calls) == 1,
        )
        return {
            "status": "ok",
            "content": json.dumps(output),
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
            "transport_attempt_count": 1,
        }


def _execute(tmp_path: Path) -> dict:
    requests, contexts, _ = _surface()
    execute_formal_anchor(
        admission=_admission(),
        requests=requests,
        contexts=contexts,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        s2_decision_sha256="3" * 64,
        context_program_sha256="4" * 64,
        quality_gate_sha256="5" * 64,
        policy_sha256="6" * 64,
        runtime_root=tmp_path / "runtime",
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite"),
        provider_call=V2Provider(),
        observed_at="2026-08-06T19:10:00+00:00",
    )
    return json.loads((tmp_path / "runtime" / "terminal_result.json").read_text(encoding="utf-8"))


def test_r1_semantics_are_valid_but_projected_as_boundary_only() -> None:
    requests, contexts, _ = _surface()
    request_id = next(iter(requests))
    output = {
        "epistemic_state": "cannot_infer",
        "answer_direction": "cannot_infer",
        "mechanism_alias": "DELL_M_DURABILITY_GAP",
        "selected_evidence_aliases": ["DELL_E01"],
        "selected_counterevidence_aliases": [],
        "gap_aliases": ["DELL_G01"],
        "confidence": "high",
        "what_would_change_aliases": ["DELL_W_DEMAND_BACKLOG", "DELL_W_DEMAND_REVERSAL"],
    }
    validate_s3_evidence_selection_output(output, compiled=contexts[request_id])
    claim = consume_s3_evidence_selection_output(
        request=requests[request_id], compiled=contexts[request_id], provider_output=output
    )
    assert claim["evidence_role_projection"] == {
        "observation_support": [],
        "thesis_support": [],
        "boundary_only": ["DELL_E01"],
    }
    assert claim["support_evidence"][0]["candidate_id"].startswith("fin013_retrieval_candidate_")


def test_cannot_infer_still_requires_gap_and_forbids_alias_overlap() -> None:
    requests, contexts, _ = _surface()
    context = contexts[next(iter(requests))]
    output = _selection(context["model_context"], cannot_infer_with_observation=True)
    output["gap_aliases"] = []
    with pytest.raises(S3EvidenceRoleContractError, match="gap_required"):
        validate_s3_evidence_selection_output(output, compiled=context)
    output = _selection(context["model_context"], cannot_infer_with_observation=True)
    output["selected_counterevidence_aliases"] = list(output["selected_evidence_aliases"])
    with pytest.raises(S3EvidenceRoleContractError, match="role_overlap"):
        validate_s3_evidence_selection_output(output, compiled=context)


def test_v2_full_fake_preserves_r1_shape_and_compiles_nine_natural_cards(tmp_path: Path) -> None:
    result = _execute(tmp_path)
    assert result["status"] == "terminal_succeeded_exact_once"
    assert result["completed_calls"] == 9
    first = result["family_results"][0]
    assert first["local_claim"]["evidence_role_projection"]["boundary_only"] == ["DELL_E01"]
    claim_program = compile_s3_claim_quality_all_natural_successor(
        policy=load_s3_claim_quality_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json"),
        s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
        s2_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"),
        representative_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json"),
        s3_surface_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"),
        natural_s2_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json"),
        natural_s2_03_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"),
        formal_anchor_result=result,
    )
    assert claim_program["observed_counts"]["live_natural_claim_cards"] == 9
    first_card = claim_program["core_claim_cards"][0]
    assert first_card["evidence_role_projection"]["thesis_support"] == []
    assert first_card["evidence_role_projection"]["boundary_only"] == first_card["support_candidate_ids"]
    claim_body = {"acceptance": {"S3_02": "engineering_pass"}, "claim_quality_program": claim_program}
    claim_decision = {**claim_body, "record_digest": canonical_digest(claim_body)}
    synthesis_program = compile_s3_cross_cell_synthesis_program(
        policy=load_s3_cross_cell_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_cross_cell_synthesis_policy_v1_0.json"),
        claim_decision=claim_decision,
    )
    synthesis_body = {"acceptance": {"S3_03": "engineering_pass"}, "cross_cell_synthesis_program": synthesis_program}
    synthesis_decision = {**synthesis_body, "record_digest": canonical_digest(synthesis_body)}
    writer_program = compile_s3_workpaper_writer_content_program(
        policy=load_s3_workpaper_writer_content_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json"),
        claim_decision=claim_decision,
        synthesis_decision=synthesis_decision,
    )
    writer_body = {"acceptance": {"S3_04": "engineering_pass"}, "workpaper_writer_content_program": writer_program}
    writer_decision = {**writer_body, "record_digest": canonical_digest(writer_body)}
    quality_program = compile_s3_research_quality_gate_program(
        policy=load_s3_research_quality_gate_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"),
        writer_decision=writer_decision,
        claim_decision=claim_decision,
    )
    assert synthesis_program["observed_counts"]["all_natural_case_syntheses"] == 3
    assert writer_program["observed_counts"]["natural_product_candidates"] == 3
    assert all(row["authority"] == "all_natural_candidate" for row in quality_program["candidate_contexts"])


def test_mutating_boundary_only_into_thesis_support_fails_card_validation(tmp_path: Path) -> None:
    result = _execute(tmp_path)
    result["family_results"][0]["local_claim"]["evidence_role_projection"] = {
        "observation_support": [],
        "thesis_support": ["DELL_E01"],
        "boundary_only": [],
    }
    # The formal result digest no longer matches, so mutation is rejected before
    # it can be promoted into a claim card.
    with pytest.raises(S3ClaimQualityError, match="formal_anchor_invalid"):
        compile_s3_claim_quality_all_natural_successor(
            policy=load_s3_claim_quality_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json"),
            s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
            s2_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"),
            representative_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json"),
            s3_surface_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"),
            natural_s2_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json"),
            natural_s2_03_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"),
            formal_anchor_result=result,
        )


def test_materialized_disposition_is_digest_bound_and_does_not_authorize_r2() -> None:
    import hashlib

    decision = json.loads(DECISION.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest(
        {key: value for key, value in decision.items() if key != "record_digest"}
    )
    assert active["decision_sha256"] == hashlib.sha256(DECISION.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert decision["root_cause_disposition"]["primary"] == "project_contract_conflated_observation_selection_with_thesis_support"
    assert decision["authority"]["nine_call_replacement_authorized"] is False
    assert decision["authority"]["single_node_natural_canary_required"] is True


def test_single_node_canary_is_capture_first_exact_once_and_preserves_boundary(tmp_path: Path) -> None:
    requests, contexts, _ = _surface()
    request_id = next(iter(requests))
    request = requests[request_id]
    compiled = contexts[request_id]
    policy = _load("configs/runtime/fin_ia_0_1_3_repair_closeout_s3_evidence_role_v2_canary_policy_v1_0.json")
    issued = datetime(2026, 8, 6, 20, 0, tzinfo=timezone.utc)
    admission = issue_evidence_role_canary_admission(
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        context_source_sha256="3" * 64,
        policy_sha256="4" * 64,
        request_binding={"request_id": request_id, "request_digest": request["request_digest"], "context_digest": compiled["context_digest"]},
        issued_at=issued.isoformat(),
        expires_at=(issued + timedelta(minutes=30)).isoformat(),
        run_nonce="v2-canary",
        credential_present=True,
        provider=policy["provider"],
        budget=policy["budget"],
    )

    def provider(**kwargs: dict) -> dict:
        context = json.loads(kwargs["messages"][1]["content"])
        output = _selection(context, cannot_infer_with_observation=True)
        return {"status": "ok", "content": json.dumps(output), "finish_reason": "stop", "input_tokens": 100, "output_tokens": 40, "total_tokens": 140, "transport_attempt_count": 1}

    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    kwargs = dict(
        admission=admission, request=request, compiled=compiled,
        execution_git_commit="1" * 40, runner_sha256="2" * 64, context_source_sha256="3" * 64, policy_sha256="4" * 64,
        shared_ledger=ledger, provider_call=provider, observed_at="2026-08-06T20:10:00+00:00",
    )
    result = execute_evidence_role_canary(runtime_root=tmp_path / "runtime", **kwargs)
    assert result["status"] == "terminal_succeeded_exact_once"
    assert result["local_claim"]["evidence_role_projection"]["boundary_only"] == ["DELL_E01"]
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 1
    with pytest.raises(Exception):
        execute_evidence_role_canary(runtime_root=tmp_path / "runtime_second", **kwargs)


def test_canary_readiness_is_digest_bound_and_does_not_authorize_full_replacement() -> None:
    import hashlib

    readiness = json.loads(CANARY_READINESS.read_text(encoding="utf-8"))
    active = json.loads(CANARY_ACTIVE.read_text(encoding="utf-8"))
    assert readiness["record_digest"] == canonical_digest(
        {key: value for key, value in readiness.items() if key != "record_digest"}
    )
    assert readiness["authority_basis"]["maximum_provider_calls"] == 1
    assert readiness["authority_basis"]["nine_call_replacement_authorized"] is False
    assert readiness["stage_boundary"]["single_node_v2_canary_live"] is False
    assert active["decision_sha256"] == hashlib.sha256(CANARY_READINESS.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert active["observed_result"] == "249 passed / 1 historical assertion deselected"
    result = json.loads(CANARY_RESULT.read_text(encoding="utf-8"))
    result_active = json.loads(CANARY_RESULT_ACTIVE.read_text(encoding="utf-8"))
    assert result["record_digest"] == canonical_digest(
        {key: value for key, value in result.items() if key != "record_digest"}
    )
    assert result["local_evidence_role_projection"]["boundary_only"] == ["DELL_E01"]
    assert result["local_evidence_role_projection"]["thesis_support"] == []
    assert result["authority"]["one_fresh_nine_call_v2_replacement_admission"] is True
    assert result_active["decision_sha256"] == hashlib.sha256(CANARY_RESULT.read_bytes()).hexdigest()
    assert result_active["suite_digest"] == canonical_digest(
        {key: value for key, value in result_active.items() if key != "suite_digest"}
    )
