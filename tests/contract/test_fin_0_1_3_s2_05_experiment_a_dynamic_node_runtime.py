from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_same_evidence_experiment_runtime import (
    POLICY_REF,
    S2SameEvidenceExperimentError,
    execute_campaign,
    execute_case,
    execute_case_layered,
    issue_case_admission,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "src/sec_agent/s2_same_evidence_experiment_runtime.py"
POLICY = ROOT / POLICY_REF
IMPLEMENTATION = ROOT / "configs/releases" / (
    "fin_ia_0_1_3_s2_05_experiment_a_"
    "dynamic_node_runner_zero_call_implementation_v1_0.json"
)
GIT = "a" * 40
OBSERVED = "2026-08-07T00:00:00+00:00"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    return policy, blind


def _admission(case: dict[str, Any], policy: dict[str, Any], nonce: str) -> dict[str, Any]:
    return issue_case_admission(
        case_input=case,
        policy=policy,
        execution_git_commit=GIT,
        runner_sha256=_sha(RUNNER),
        policy_sha256=_sha(POLICY),
        issued_at="2026-08-06T23:00:00+00:00",
        expires_at="2026-08-08T00:00:00+00:00",
        run_nonce=nonce,
        credential_present=True,
    )


class FakeProvider:
    def __init__(self, *, units: int = 6, mutation: str = "") -> None:
        self.units = units
        self.mutation = mutation
        self.calls: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        request = json.loads(kwargs["messages"][1]["content"])
        node = request["node_type"]
        context = request["context"]
        if self.mutation == "transport" and len(self.calls) == 2:
            raise TimeoutError("fixture timeout")
        if self.mutation == "invalid_json" and len(self.calls) == 2:
            return self._result("not-json")
        if node == "lead_planning":
            output = self._lead(request)
        elif node == "specialist_judgment":
            output = self._specialist(request)
        elif node == "cross_cell_synthesis":
            output = self._synthesis(request)
        elif node == "writer":
            output = self._writer(request)
        elif node == "verifier":
            output = self._verifier(request)
        else:  # pragma: no cover - runtime rejects unknown nodes first
            raise AssertionError(node)
        if self.mutation == "wrong_as_of" and len(self.calls) == 1:
            output["as_of"] = "2026-08-05"
        result = self._result(json.dumps(output, ensure_ascii=False))
        if self.mutation == "usage_budget" and len(self.calls) == 1:
            result["input_tokens"] = 200001
            result["total_tokens"] = 200051
        return result

    @staticmethod
    def _result(content: str) -> dict[str, Any]:
        return {
            "status": "ok",
            "content": content,
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "transport_attempt_count": 1,
            "raw_response": {"fixture": True},
        }

    def _lead(self, request: dict[str, Any]) -> dict[str, Any]:
        case = request["context"]["case_input"]
        families = request["required_output_contract"]["mandatory_families"]
        evidence = [row["evidence_id"] for row in case["evidence_items"]]
        gaps = [row["gap_id"] for row in case["explicit_gaps"]]
        units = []
        for index in range(self.units):
            units.append(
                {
                    "unit_id": f"unit_{chr(97 + index)}",
                    "family": families[index % len(families)],
                    "question": "What does the assigned evidence support?",
                    "why_material": "This issue can change the investment judgment.",
                    "evidence_ids": [],
                    "gap_ids": [],
                    "stop_condition": "Stop when the assigned evidence and gap are assessed.",
                }
            )
        for index, evidence_id in enumerate(evidence):
            units[index % len(units)]["evidence_ids"].append(evidence_id)
        for index, gap_id in enumerate(gaps):
            units[index % len(units)]["gap_ids"].append(gap_id)
        if self.mutation == "missing_family":
            units[-1]["family"] = families[0]
        if self.mutation == "cross_case_lead":
            units[0]["evidence_ids"] = ["NVDA_E99" if case["case_key"] != "NVDA" else "MU_E99"]
        if self.mutation == "lead_omits_evidence":
            units[0]["evidence_ids"].pop()
        return {"case_key": case["case_key"], "as_of": case["as_of"], "research_units": units}

    def _specialist(self, request: dict[str, Any]) -> dict[str, Any]:
        context = request["context"]
        identity = context["case_identity"]
        unit = context["research_unit"]
        evidence = list(unit["evidence_ids"])
        if self.mutation == "unassigned_specialist" and len(self.calls) == 2:
            evidence = ["NVDA_E99" if identity["case_key"] != "NVDA" else "MU_E99"]
        judgment = "The assigned evidence supports a bounded judgment."
        if self.mutation == "invented_numeric" and len(self.calls) == 2:
            judgment = "The assigned evidence implies 987654321 percent growth."
        return {
            "case_key": identity["case_key"],
            "as_of": identity["as_of"],
            "unit_id": unit["unit_id"],
            "epistemic_state": "mixed",
            "judgment": judgment,
            "mechanism": "The evidence affects the operating and valuation interpretation.",
            "financial_or_valuation_link": "The link remains bounded by the supplied evidence.",
            "evidence_ids": evidence,
            "counterevidence_ids": [],
            "gap_ids": list(unit["gap_ids"]),
            "what_would_change": "Additional case-local evidence could change the judgment.",
        }

    def _synthesis(self, request: dict[str, Any]) -> dict[str, Any]:
        context = request["context"]
        identity = context["case_identity"]
        units = [row["unit_id"] for row in context["specialist_outputs"]]
        gaps = [row["gap_id"] for row in context["explicit_gaps"]]
        if self.mutation == "synthesis_omits_gap":
            gaps = gaps[:-1]
        return {
            "case_key": identity["case_key"],
            "as_of": identity["as_of"],
            "thesis": "The evidence supports a bounded thesis with unresolved uncertainty.",
            "confidence": "Moderate because the evidence is useful but incomplete.",
            "unit_ids": units,
            "dependencies": [],
            "conflicts": [],
            "material_gap_ids": gaps,
            "counter_thesis": "The same evidence can support a weaker interpretation.",
            "what_would_change": "New case-local evidence could resolve the uncertainty.",
        }

    def _writer(self, request: dict[str, Any]) -> dict[str, Any]:
        context = request["context"]
        identity = context["case_identity"]
        evidence_ids = [row["evidence_id"] for row in context["evidence_index"]]
        gap_ids = [row["gap_id"] for row in context["explicit_gaps"]]
        unit_ids = [row["unit_id"] for row in context["specialist_outputs"]]
        sections = [
            {
                "section_id": section_id,
                "heading": section_id.replace("_", " ").title(),
                "narrative": "The cited evidence supports a bounded conclusion while uncertainty remains.",
                "evidence_ids": [evidence_ids[0]],
                "unit_ids": unit_ids,
                "gap_ids": [gap_ids[0]],
            }
            for section_id in context["required_section_ids"]
        ]
        sections[0]["evidence_ids"] = evidence_ids
        sections[0]["gap_ids"] = gap_ids
        if self.mutation == "writer_uncited":
            sections[0]["evidence_ids"] = []
            sections[0]["gap_ids"] = []
        if self.mutation == "writer_invented_numeric":
            sections[0]["narrative"] = "The evidence proves 987654321 percent growth."
        if self.mutation == "writer_omits_evidence":
            missing = evidence_ids[-1]
            for section in sections:
                section["evidence_ids"] = [
                    value for value in section["evidence_ids"] if value != missing
                ]
        return {
            "case_key": identity["case_key"],
            "as_of": identity["as_of"],
            "title": identity["case_key"] + " bounded same-evidence research candidate",
            "sections": sections,
            "overall_boundary": "This raw candidate uses only the frozen evidence and preserves gaps.",
        }

    def _verifier(self, request: dict[str, Any]) -> dict[str, Any]:
        context = request["context"]
        identity = context["case_identity"]
        material = self.mutation == "verifier_material"
        findings = (
            [
                {
                    "severity": "L1",
                    "code": "material_fixture_failure",
                    "node_refs": ["writer"],
                    "evidence_ids": [],
                    "explanation": "A material evidence-boundary failure remains.",
                }
            ]
            if material
            else []
        )
        return {
            "case_key": identity["case_key"],
            "as_of": identity["as_of"],
            "decision": "return_material_failure" if material else "accept_raw_candidate",
            "material_failure": material,
            "findings": findings,
            "checked_unit_ids": [row["unit_id"] for row in context["specialist_outputs"]],
            "checked_section_ids": [row["section_id"] for row in context["writer"]["sections"]],
        }


def _job(
    tmp_path: Path,
    *,
    case: dict[str, Any],
    policy: dict[str, Any],
    nonce: str,
) -> dict[str, Any]:
    return {
        "admission": _admission(case, policy, nonce),
        "case_input": case,
        "policy": policy,
        "execution_git_commit": GIT,
        "runner_sha256": _sha(RUNNER),
        "policy_sha256": _sha(POLICY),
        "runtime_root": tmp_path / (case["case_key"] + "_runtime_" + nonce),
        "shared_ledger": SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite3"),
        "observed_at": OBSERVED,
    }


def test_policy_and_blind_input_are_exact_and_hidden_free() -> None:
    policy, blind = _fixture()
    assert [row["case_key"] for row in blind["cases"]] == ["DELL", "MU", "NVDA"]
    assert policy["capacity"]["provider_calls_per_case"] == {"minimum": 10, "maximum": 12}
    assert policy["capacity"]["provider_calls_campaign_maximum"] == 36
    assert "evaluator_only" not in json.dumps(blind, ensure_ascii=False)
    assert policy["persistence"]["writable_track"] == "raw_model_only"


def test_zero_call_implementation_manifest_binds_code_and_honest_boundary() -> None:
    manifest = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    body = {
        key: value
        for key, value in manifest.items()
        if key != "implementation_digest"
    }
    assert manifest["implementation_digest"] == canonical_digest(body)
    # This v1 manifest is immutable evidence for the original runner slice.
    # A successor may change those files; current hashes are bound by its own
    # release record rather than by rewriting this historical manifest.
    for row in manifest["implementation"].values():
        assert (ROOT / row["ref"]).is_file()
        assert len(row["sha256"]) == 64
    assert manifest["verification"]["model_calls"] == 0
    assert manifest["verification"]["admissions_issued"] == 0
    assert manifest["stage_acceptance"]["S2_05_zero_call_engineering"] == "pass"
    assert manifest["stage_acceptance"]["Experiment_A_model_reasoning"] is False


@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_each_case_full_fake_produces_ten_capture_first_calls(
    tmp_path: Path, case_index: int
) -> None:
    policy, blind = _fixture()
    case = blind["cases"][case_index]
    fake = FakeProvider(units=6)
    result = execute_case(provider_call=fake, **_job(tmp_path, case=case, policy=policy, nonce=str(case_index)))
    assert result["status"] == "terminal_succeeded_raw_candidate"
    assert result["completed_calls"] == result["expected_calls"] == 10
    assert len(fake.calls) == 10
    runtime = tmp_path / (case["case_key"] + "_runtime_" + str(case_index))
    assert len(list((runtime / "raw_model_only/captures").glob("*.json"))) == 10
    assert (runtime / "raw_model_only/terminal_result.json").exists()
    assert not (runtime / "supervisor_corrections").exists()
    assert not (runtime / "corrected_candidates").exists()
    assert not (runtime / "evaluator_only").exists()
    for call in fake.calls:
        assert call["max_transport_attempts"] == 1
        assert "api_key_env" in call
        assert "hidden_gold" not in call["messages"][1]["content"]
    first_capture = json.loads(
        sorted((runtime / "raw_model_only/captures").glob("*.json"))[0].read_text(
            encoding="utf-8"
        )
    )
    assert "api_key_env" not in first_capture["provider_visible_request"]
    assert first_capture["gateway_result"]["raw_response"] == {"fixture": True}


def test_eight_unit_dynamic_fanout_reaches_twelve_call_ceiling(tmp_path: Path) -> None:
    policy, blind = _fixture()
    fake = FakeProvider(units=8)
    result = execute_case(
        provider_call=fake,
        **_job(tmp_path, case=blind["cases"][0], policy=policy, nonce="eight"),
    )
    assert result["status"] == "terminal_succeeded_raw_candidate"
    assert result["completed_calls"] == result["expected_calls"] == 12


@pytest.mark.parametrize("units", [5, 9])
def test_lead_fanout_outside_closed_range_fails_after_first_capture(
    tmp_path: Path, units: int
) -> None:
    policy, blind = _fixture()
    fake = FakeProvider(units=units)
    result = execute_case(
        provider_call=fake,
        **_job(tmp_path, case=blind["cases"][0], policy=policy, nonce=f"units_{units}"),
    )
    assert result["terminal_code"] == "experiment_a_lead_unit_count_invalid"
    assert result["completed_calls"] == 1


@pytest.mark.parametrize(
    ("mutation", "expected", "calls"),
    [
        ("missing_family", "experiment_a_lead_mandatory_family_missing", 1),
        ("cross_case_lead", "experiment_a_lead_cross_case_or_unknown_id", 1),
        ("wrong_as_of", "experiment_a_node_identity_or_as_of_invalid", 1),
        ("usage_budget", "experiment_a_case_token_or_cost_capacity_exceeded", 1),
        ("lead_omits_evidence", "experiment_a_lead_pack_coverage_incomplete", 1),
        ("unassigned_specialist", "experiment_a_specialist_cross_case_or_unassigned_id", 2),
        ("invented_numeric", "experiment_a_unbound_numeric_surface", 2),
        ("invalid_json", "experiment_a_node_output_json_invalid", 2),
        ("transport", "experiment_a_provider_transport_or_finish_failure", 2),
        ("synthesis_omits_gap", "experiment_a_synthesis_gap_coverage_incomplete", 8),
        ("writer_uncited", "experiment_a_writer_section_citation_missing", 9),
        ("writer_invented_numeric", "experiment_a_unbound_numeric_surface", 9),
        ("writer_omits_evidence", "experiment_a_writer_pack_coverage_incomplete", 9),
        ("verifier_material", "experiment_a_verifier_material_failure", 10),
    ],
)
def test_material_mutations_fail_closed_after_preserving_capture(
    tmp_path: Path, mutation: str, expected: str, calls: int
) -> None:
    policy, blind = _fixture()
    fake = FakeProvider(mutation=mutation)
    result = execute_case(
        provider_call=fake,
        **_job(tmp_path, case=blind["cases"][0], policy=policy, nonce=mutation),
    )
    assert result["status"] == "terminal_failed_no_retry"
    assert result["terminal_code"] == expected
    assert result["completed_calls"] == calls == len(fake.calls)
    assert len(result["call_results"]) == calls
    assert result["retry_count"] == result["fallback_count"] == 0


def test_campaign_stops_before_next_case_after_first_material_failure(tmp_path: Path) -> None:
    policy, blind = _fixture()
    jobs = [
        _job(tmp_path, case=case, policy=policy, nonce="campaign_" + case["case_key"])
        for case in blind["cases"]
    ]
    fake = FakeProvider(mutation="missing_family")
    results = execute_campaign(jobs, provider_call=fake)
    assert len(results) == 1
    assert results[0]["case_key"] == "DELL"
    assert len(fake.calls) == 1
    assert not (tmp_path / "MU_runtime_campaign_MU").exists()


def test_three_case_campaign_full_fake_is_ordered_and_bounded(tmp_path: Path) -> None:
    policy, blind = _fixture()
    jobs = [
        _job(tmp_path, case=case, policy=policy, nonce="positive_" + case["case_key"])
        for case in blind["cases"]
    ]
    fake = FakeProvider()
    results = execute_campaign(jobs, provider_call=fake)
    assert [row["case_key"] for row in results] == ["DELL", "MU", "NVDA"]
    assert all(row["status"] == "terminal_succeeded_raw_candidate" for row in results)
    assert sum(row["completed_calls"] for row in results) == len(fake.calls) == 30


def test_shared_admission_is_exact_once_even_with_new_runtime_root(tmp_path: Path) -> None:
    policy, blind = _fixture()
    case = blind["cases"][0]
    job = _job(tmp_path, case=case, policy=policy, nonce="once")
    first = execute_case(provider_call=FakeProvider(), **job)
    assert first["status"] == "terminal_succeeded_raw_candidate"
    replay = {**job, "runtime_root": tmp_path / "replay"}
    with pytest.raises(SharedAdmissionLedgerError, match="already_consumed"):
        execute_case(provider_call=FakeProvider(), **replay)


@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_layered_successor_runs_complete_raw_chain_and_never_promotes_business(
    tmp_path: Path, case_index: int
) -> None:
    policy, blind = _fixture()
    case = blind["cases"][case_index]
    fake = FakeProvider()
    result = execute_case_layered(
        provider_call=fake,
        **_job(tmp_path, case=case, policy=policy, nonce=f"layered_{case['case_key']}"),
    )
    assert result["status"] == "terminal_completed_layered_raw_evaluation"
    assert result["terminal_code"] == "experiment_a_layered_raw_candidate_pass"
    assert result["completed_calls"] == 10 == len(fake.calls)
    assert result["layered_evaluation"]["hidden_scoring_eligible"] is True
    assert result["layered_evaluation"]["business_promotion_gate_pass"] is True
    assert result["layered_evaluation"]["business_promotable"] is False
    assert result["business_artifact_promotions"] == 0


def test_layered_successor_collects_material_numeric_finding_through_verifier(
    tmp_path: Path,
) -> None:
    policy, blind = _fixture()
    fake = FakeProvider(mutation="invented_numeric")
    result = execute_case_layered(
        provider_call=fake,
        **_job(tmp_path, case=blind["cases"][0], policy=policy, nonce="layered_material"),
    )
    assert result["status"] == "terminal_completed_layered_raw_evaluation"
    assert result["terminal_code"] == "experiment_a_layered_raw_candidate_with_material_findings"
    assert result["completed_calls"] == 10 == len(fake.calls)
    assert result["layered_evaluation"]["hidden_scoring_eligible"] is True
    assert result["layered_evaluation"]["material_failure"] is True
    assert result["layered_evaluation"]["business_promotion_gate_pass"] is False
    assert result["layered_evaluation"]["business_promotable"] is False


def test_admission_and_input_mutations_fail_before_provider_call(tmp_path: Path) -> None:
    policy, blind = _fixture()
    case = blind["cases"][0]
    job = _job(tmp_path, case=case, policy=policy, nonce="binding")
    admission = deepcopy(job["admission"])
    admission["case_input_digest"] = "0" * 64
    body = {key: value for key, value in admission.items() if key != "admission_digest"}
    admission["admission_digest"] = canonical_digest(body)
    fake = FakeProvider()
    with pytest.raises(S2SameEvidenceExperimentError, match="execution_binding_invalid"):
        execute_case(provider_call=fake, **{**job, "admission": admission})
    assert fake.calls == []


def test_input_file_physical_mutation_is_rejected(tmp_path: Path) -> None:
    policy, blind = _fixture()
    root = tmp_path / "repo"
    target = root / policy["frozen_input"]["ref"]
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(blind, ensure_ascii=False) + "\n", encoding="utf-8")
    policy_root = root / POLICY_REF
    policy_root.parent.mkdir(parents=True)
    policy_root.write_text(json.dumps(policy, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(S2SameEvidenceExperimentError, match="input_sha256_mismatch"):
        load_frozen_blind_inputs(root, policy)
