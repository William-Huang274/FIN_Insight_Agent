from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s3_claim_quality_program import (
    compile_s3_claim_quality_all_natural_successor,
    load_s3_claim_quality_policy,
)
from sec_agent.s3_cross_cell_synthesis_program import (
    compile_s3_cross_cell_synthesis_program,
    load_s3_cross_cell_policy,
)
from sec_agent.s3_formal_anchor_runtime import (
    S3FormalAnchorRuntimeError,
    execute_formal_anchor,
    issue_formal_anchor_admission,
    validate_formal_anchor_admission,
)
from sec_agent.s3_research_quality_gate import (
    compile_s3_research_quality_gate_program,
    load_s3_research_quality_gate_policy,
)
from sec_agent.s3_workpaper_writer_content_program import (
    compile_s3_workpaper_writer_content_program,
    load_s3_workpaper_writer_content_policy,
)
from sec_agent.shared_admission_ledger import SharedAdmissionConsumptionLedger, SharedAdmissionLedgerError


ROOT = Path(__file__).resolve().parents[2]
READINESS = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_admission_readiness_v1_0.json"
ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_active_test_suite_successor_v1_0.json"
FAILURE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_terminal_failure_v1_0.json"
FAILURE_ACTIVE = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_r1_failure_active_test_suite_successor_v1_0.json"


def _load(ref: str) -> dict:
    return json.loads((ROOT / ref).read_text(encoding="utf-8"))


def _surface() -> tuple[dict[str, dict], dict[str, dict], list[dict[str, str]]]:
    s2 = _load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json")
    context_program = _load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_and_capacity_zero_call_v1_0.json")
    requests = {row["request_id"]: row for row in s2["research_question_method_program"]["representative_requests"]}
    contexts = {row["request_id"]: row for row in context_program["role_scoped_contexts"]}
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
    issued = datetime(2026, 8, 6, 18, 0, tzinfo=timezone.utc)
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
        run_nonce="formal-fixture",
        credential_present=True,
        provider=_load("configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v1_0.json")["provider"],
        budget=_load("configs/runtime/fin_ia_0_1_3_repair_closeout_s3_formal_anchor_execution_policy_v1_0.json")["budget"],
    )


class FakeProvider:
    def __init__(self, fail_at: int | None = None, semantic_invalid_at: int | None = None) -> None:
        self.fail_at = fail_at
        self.semantic_invalid_at = semantic_invalid_at
        self.calls: list[dict] = []

    def __call__(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        request = json.loads(kwargs["messages"][1]["content"])
        if self.fail_at == len(self.calls):
            return {"status": "provider_error", "content": "", "finish_reason": "", "transport_attempt_count": 1}
        evidence = [row["alias"] for row in request["evidence_options"]]
        gaps = [row["alias"] for row in request["gap_options"]]
        output = {
            "epistemic_state": "mixed_evidence" if evidence and gaps else "bounded_inference" if evidence else "cannot_infer",
            "answer_direction": "mixed" if evidence and gaps else "positive" if evidence else "cannot_infer",
            "mechanism_alias": request["mechanism_options"][0]["alias"],
            "support_aliases": evidence,
            "counterevidence_aliases": evidence if request["program_cell_id"].startswith("bottleneck") else [],
            "gap_aliases": gaps,
            "confidence": "medium" if evidence else "low",
            "what_would_change_aliases": [request["what_would_change_options"][0]["alias"]],
        }
        if self.semantic_invalid_at == len(self.calls):
            output["epistemic_state"] = "cannot_infer"
            output["answer_direction"] = "cannot_infer"
            output["support_aliases"] = evidence
        return {
            "status": "ok",
            "content": json.dumps(output),
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 40,
            "total_tokens": 140,
            "transport_attempt_count": 1,
            "raw_response": {"fixture": True, "output": output},
        }


def _execute(tmp_path: Path, provider: FakeProvider) -> dict:
    requests, contexts, _ = _surface()
    return execute_formal_anchor(
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
        provider_call=provider,
        observed_at="2026-08-06T18:10:00+00:00",
    )


def _record(body: dict) -> dict:
    return {**body, "record_digest": canonical_digest(body)}


def test_admission_binds_nine_ordered_requests_and_no_secret_value() -> None:
    admission = _admission()
    requests, contexts, _ = _surface()
    validate_formal_anchor_admission(
        admission,
        execution_git_commit="1" * 40,
        runner_sha256="2" * 64,
        s2_decision_sha256="3" * 64,
        context_program_sha256="4" * 64,
        quality_gate_sha256="5" * 64,
        policy_sha256="6" * 64,
        requests=requests,
        contexts=contexts,
        observed_at="2026-08-06T18:10:00+00:00",
    )
    assert len(admission["request_bindings"]) == 9
    assert admission["budget"]["retry_count"] == 0
    assert "sk-" not in json.dumps(admission)


def test_nine_call_fake_terminal_compiles_all_natural_claim_lead_writer_and_quality_entry(tmp_path: Path) -> None:
    provider = FakeProvider()
    result = _execute(tmp_path, provider)
    assert result["status"] == "terminal_succeeded_exact_once"
    assert result["completed_calls"] == 9
    assert len(provider.calls) == 9
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 9
    formal_result = _load_terminal(tmp_path)

    claim_program = compile_s3_claim_quality_all_natural_successor(
        policy=load_s3_claim_quality_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_claim_and_observable_wwc_policy_v1_0.json"),
        s1_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s1_05_retrieval_evidence_usefulness_and_s1_closeout_v1_0.json"),
        s2_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_01_research_question_method_contract_translation_v1_0.json"),
        representative_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_representative_node_context_precedence_and_canary_entry_v1_0.json"),
        s3_surface_decision=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s3_01_dynamic_decision_surface_v1_0.json"),
        natural_s2_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_02_three_family_natural_canary_result_v1_0.json"),
        natural_s2_03_result=_load("configs/releases/fin_ia_0_1_3_repair_closeout_s2_03_context_yield_natural_reproof_result_v1_0.json"),
        formal_anchor_result=formal_result,
    )
    assert claim_program["observed_counts"]["live_natural_claim_cards"] == 9
    claim_decision = _record({"acceptance": {"S3_02": "engineering_pass"}, "claim_quality_program": claim_program})
    synthesis_program = compile_s3_cross_cell_synthesis_program(
        policy=load_s3_cross_cell_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_cross_cell_synthesis_policy_v1_0.json"),
        claim_decision=claim_decision,
    )
    assert synthesis_program["observed_counts"]["all_natural_case_syntheses"] == 3
    synthesis_decision = _record({"acceptance": {"S3_03": "engineering_pass"}, "cross_cell_synthesis_program": synthesis_program})
    writer_program = compile_s3_workpaper_writer_content_program(
        policy=load_s3_workpaper_writer_content_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json"),
        claim_decision=claim_decision,
        synthesis_decision=synthesis_decision,
    )
    assert writer_program["observed_counts"]["natural_product_candidates"] == 3
    writer_decision = _record({"acceptance": {"S3_04": "engineering_pass"}, "workpaper_writer_content_program": writer_program})
    quality_program = compile_s3_research_quality_gate_program(
        policy=load_s3_research_quality_gate_policy(ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_research_quality_gate_policy_v1_0.json"),
        writer_decision=writer_decision,
        claim_decision=claim_decision,
    )
    assert all(row["authority"] == "all_natural_candidate" for row in quality_program["candidate_contexts"])
    assert all("fixture_mixed_authority" not in row["reasons"] for row in quality_program["current_case_dispositions"])
    assert quality_program["observed_counts"]["formal_case_scores"] == 0


def _load_terminal(tmp_path: Path) -> dict:
    return json.loads((tmp_path / "runtime" / "terminal_result.json").read_text(encoding="utf-8"))


def test_first_failure_stops_at_four_and_preserves_all_attempted_captures(tmp_path: Path) -> None:
    provider = FakeProvider(fail_at=4)
    result = _execute(tmp_path, provider)
    assert result["status"] == "terminal_failed_no_retry"
    assert result["completed_calls"] == 4
    assert len(result["skipped_request_ids"]) == 5
    assert len(provider.calls) == 4
    assert len(list((tmp_path / "runtime" / "captures").glob("*.json"))) == 4


def test_semantic_contract_error_is_not_misclassified_as_invalid_json(tmp_path: Path) -> None:
    result = _execute(tmp_path, FakeProvider(semantic_invalid_at=1))
    assert result["status"] == "terminal_failed_no_retry"
    assert result["terminal_code"] == (
        "s3_formal_provider_output_contract_invalid:s2_compact_output_cannot_infer_support"
    )
    assert result["completed_calls"] == 1
    assert len(result["skipped_request_ids"]) == 8


def test_same_admission_cannot_be_consumed_twice(tmp_path: Path) -> None:
    admission = _admission()
    requests, contexts, _ = _surface()
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "shared" / "ledger.sqlite")
    kwargs = {
        "admission": admission,
        "requests": requests,
        "contexts": contexts,
        "execution_git_commit": "1" * 40,
        "runner_sha256": "2" * 64,
        "s2_decision_sha256": "3" * 64,
        "context_program_sha256": "4" * 64,
        "quality_gate_sha256": "5" * 64,
        "policy_sha256": "6" * 64,
        "shared_ledger": ledger,
        "provider_call": FakeProvider(),
        "observed_at": "2026-08-06T18:10:00+00:00",
    }
    execute_formal_anchor(runtime_root=tmp_path / "runtime_a", **kwargs)
    with pytest.raises(SharedAdmissionLedgerError):
        execute_formal_anchor(runtime_root=tmp_path / "runtime_b", **kwargs)


def test_context_digest_or_execution_binding_mutation_fails_closed() -> None:
    admission = _admission()
    requests, contexts, _ = _surface()
    mutated = deepcopy(contexts)
    first = next(iter(mutated))
    mutated[first]["context_digest"] = "9" * 64
    with pytest.raises(S3FormalAnchorRuntimeError, match="request_binding_invalid"):
        validate_formal_anchor_admission(
            admission,
            execution_git_commit="1" * 40,
            runner_sha256="2" * 64,
            s2_decision_sha256="3" * 64,
            context_program_sha256="4" * 64,
            quality_gate_sha256="5" * 64,
            policy_sha256="6" * 64,
            requests=requests,
            contexts=mutated,
            observed_at="2026-08-06T18:10:00+00:00",
        )


def test_materialized_readiness_and_active_suite_are_digest_bound_without_claiming_live() -> None:
    readiness = json.loads(READINESS.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE.read_text(encoding="utf-8"))
    assert readiness["record_digest"] == canonical_digest(
        {key: value for key, value in readiness.items() if key != "record_digest"}
    )
    import hashlib

    assert active["decision_sha256"] == hashlib.sha256(READINESS.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert active["observed_result"] == "240 passed / 1 historical assertion deselected"
    assert readiness["authority"]["admission_issued"] is False
    assert readiness["stage_boundary"]["formal_anchor_live"] is False


def test_materialized_r1_failure_and_successor_suite_preserve_attempt_and_stop() -> None:
    failure = json.loads(FAILURE.read_text(encoding="utf-8"))
    active = json.loads(FAILURE_ACTIVE.read_text(encoding="utf-8"))
    assert failure["record_digest"] == canonical_digest(
        {key: value for key, value in failure.items() if key != "record_digest"}
    )
    import hashlib

    assert active["decision_sha256"] == hashlib.sha256(FAILURE.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest(
        {key: value for key, value in active.items() if key != "suite_digest"}
    )
    assert active["observed_result"] == "242 passed / 1 historical assertion deselected"
    assert failure["execution"]["completed_calls"] == 1
    assert failure["execution"]["skipped_requests"] == 8
    assert failure["classification_correction"]["actual_failure_code"] == "s2_compact_output_cannot_infer_support"
    assert failure["authority"]["replacement_or_second_run_authorized"] is False
