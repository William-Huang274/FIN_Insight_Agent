from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest
from sec_agent.s2_same_evidence_experiment_runtime import (
    SECTION_IDS,
    load_frozen_blind_inputs,
    load_runtime_policy,
)
from sec_agent.s2_same_evidence_supervision import (
    compile_case_scoped_supervision_boundary,
)
from sec_agent.s2_same_evidence_supervisor_runtime import (
    SUPERVISOR_PLAN_SCHEMA,
    S2SupervisorRuntimeError,
    assert_hidden_scoring_allowed,
    compile_capacity_proof,
    compile_corrected_admission_candidate,
    compile_fixture_supervisor_plan,
    compile_supervisor_plan_spec,
    compile_supervisor_request,
    execute_corrected_candidate,
    validate_supervisor_plan,
)
from sec_agent.shared_admission_ledger import (
    SharedAdmissionConsumptionLedger,
    SharedAdmissionLedgerError,
)


ROOT = Path(__file__).resolve().parents[2]
OBSERVED = "2026-08-07T12:00:00+00:00"
IMPLEMENTATION = ROOT / (
    "configs/releases/fin_ia_0_1_3_s2_06_supervisor_nonempty_"
    "case_authority_compiled_contract_alignment_v1_1.json"
)


def _fixture(case_index: int = 0, *, units: int = 6) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    policy = load_runtime_policy(ROOT)
    blind = load_frozen_blind_inputs(ROOT, policy)
    case = blind["cases"][case_index]
    return policy, case, _raw_outputs(case, units=units)


def _evaluation() -> dict[str, Any]:
    return {
        "raw_chain_complete": True,
        "hidden_scoring_eligible": True,
        "material_failure": True,
        "findings": [
            {
                "severity": "L1",
                "code": "unbound_material_numeric_surface",
                "node_ref": "lead",
                "path": "$.research_units[0].question",
                "tokens": ["999%"],
            },
            {
                "severity": "L1",
                "code": "specialist_assigned_pack_coverage_incomplete",
                "node_ref": "specialist[0]",
            },
            {
                "severity": "L1",
                "code": "writer_case_pack_coverage_incomplete",
                "node_ref": "writer",
            },
            {
                "severity": "L2",
                "code": "verifier_missed_material_failure",
                "node_ref": "verifier",
            },
            {
                "severity": "L3",
                "code": "hypothetical_planning_threshold",
                "node_ref": "specialist[1]",
                "path": "$.what_would_change",
                "tokens": ["20%"],
            },
        ],
    }


def _boundary(case: dict[str, Any], *, evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    return compile_case_scoped_supervision_boundary(
        evaluation or _evaluation(),
        case_key=case["case_key"],
        raw_run_id="raw-" + case["case_key"],
        raw_terminal_digest=(case["case_key"].lower()[0] * 64),
    )


def _admission(
    *,
    boundary: dict[str, Any],
    case: dict[str, Any],
    raw: dict[str, Any],
    corrected_run_id: str,
    corrected_attempt_id: str,
    authorized: bool = True,
) -> dict[str, Any]:
    spec = compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)
    return compile_corrected_admission_candidate(
        spec=spec,
        raw_outputs=raw,
        corrected_run_id=corrected_run_id,
        corrected_attempt_id=corrected_attempt_id,
        admission_id="admission-" + corrected_run_id,
        issued_at="2026-08-07T11:00:00+00:00",
        expires_at="2026-08-08T12:00:00+00:00",
        credential_present=True,
        provider_execution_authorized=authorized,
    )


def _raw_outputs(case: dict[str, Any], *, units: int = 6) -> dict[str, Any]:
    families = [
        "demand_and_customer_authenticity",
        "product_and_technology_position",
        "supply_chain_and_competition",
        "financial_transmission_profit_and_cash",
        "capital_market_and_price_in_boundary",
        "counter_thesis_risk_and_what_would_change",
    ]
    evidence_ids = [row["evidence_id"] for row in case["evidence_items"]]
    gap_ids = [row["gap_id"] for row in case["explicit_gaps"]]
    research_units = [
        {
            "unit_id": f"unit_{index}",
            "family": families[index % len(families)],
            "question": "What does the assigned evidence support?",
            "why_material": "The answer can change the bounded investment judgment.",
            "evidence_ids": [],
            "gap_ids": [],
            "stop_condition": "Stop after all assigned evidence and gaps are assessed.",
        }
        for index in range(units)
    ]
    for index, evidence_id in enumerate(evidence_ids):
        research_units[index % units]["evidence_ids"].append(evidence_id)
    for index, gap_id in enumerate(gap_ids):
        research_units[index % units]["gap_ids"].append(gap_id)
    specialists = [
        {
            "case_key": case["case_key"],
            "as_of": case["as_of"],
            "unit_id": unit["unit_id"],
            "epistemic_state": "mixed",
            "judgment": "The assigned evidence supports a bounded judgment.",
            "mechanism": "The evidence changes the operating interpretation.",
            "financial_or_valuation_link": "The financial link remains bounded by the supplied evidence.",
            "evidence_ids": list(unit["evidence_ids"]),
            "counterevidence_ids": [],
            "gap_ids": list(unit["gap_ids"]),
            "what_would_change": "Additional case-local evidence could change the judgment.",
        }
        for unit in research_units
    ]
    synthesis = {
        "case_key": case["case_key"],
        "as_of": case["as_of"],
        "thesis": "The supplied evidence supports a bounded thesis with unresolved uncertainty.",
        "confidence": "Moderate because the evidence is useful but incomplete.",
        "unit_ids": [row["unit_id"] for row in specialists],
        "dependencies": [],
        "conflicts": [],
        "material_gap_ids": gap_ids,
        "counter_thesis": "The same evidence can support a weaker interpretation.",
        "what_would_change": "New case-local evidence could resolve the uncertainty.",
    }
    sections = [
        {
            "section_id": section_id,
            "heading": section_id.replace("_", " ").title(),
            "narrative": "The cited evidence supports a bounded conclusion while uncertainty remains.",
            "evidence_ids": [evidence_ids[0]],
            "unit_ids": [row["unit_id"] for row in specialists],
            "gap_ids": [gap_ids[0]],
        }
        for section_id in SECTION_IDS
    ]
    sections[0]["evidence_ids"] = evidence_ids
    sections[0]["gap_ids"] = gap_ids
    writer = {
        "case_key": case["case_key"],
        "as_of": case["as_of"],
        "title": case["case_key"] + " bounded corrected candidate",
        "sections": sections,
        "overall_boundary": "This candidate uses only the frozen evidence and preserves gaps.",
    }
    verifier = {
        "case_key": case["case_key"],
        "as_of": case["as_of"],
        "decision": "accept_raw_candidate",
        "material_failure": False,
        "findings": [],
        "checked_unit_ids": [row["unit_id"] for row in specialists],
        "checked_section_ids": list(SECTION_IDS),
    }
    return {
        "lead": {
            "case_key": case["case_key"],
            "as_of": case["as_of"],
            "research_units": research_units,
        },
        "specialists": specialists,
        "synthesis": synthesis,
        "writer": writer,
        "verifier": verifier,
    }


class FullFakeCorrectedProvider:
    def __init__(self, *, mutation: str = "") -> None:
        self.calls: list[dict[str, Any]] = []
        self.mutation = mutation

    def __call__(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(deepcopy(kwargs))
        if self.mutation == "transport" and len(self.calls) == 3:
            raise TimeoutError("fixture transport failure")
        request = json.loads(kwargs["messages"][1]["content"])
        if kwargs["role"] == "fin013_s2_06_supervisor_plan":
            output = {
                "schema_version": SUPERVISOR_PLAN_SCHEMA,
                "case_key": request["case_key"],
                "raw_run_id": request["raw_binding"]["run_id"],
                "node_directives": [
                    {
                        **row,
                        "evidence_ids": list(request["case_aliases"]["evidence_ids"]),
                        "numeric_aliases": list(request["case_aliases"]["numeric_aliases"]),
                        "gap_ids": list(request["case_aliases"]["gap_ids"]),
                    }
                    for row in request["directive_requirements"]
                ],
                "deterministic_correction_ids": [
                    row["correction_id"]
                    for row in request["visible_findings"]
                    if row["action_code"] == "deterministic_source_bound_deletion"
                ],
                "retained_nonfactual_request_ids": [
                    row["correction_id"]
                    for row in request["visible_findings"]
                    if row["action_code"] == "retain_typed_nonfactual_request"
                ],
            }
        else:
            output = self._graph_output(request)
        if self.mutation == "lead_topology" and request.get("node_type") == "lead_planning":
            output["research_units"][0]["unit_id"] = "changed_unit"
        return {
            "status": "ok",
            "content": json.dumps(output, ensure_ascii=False),
            "finish_reason": "stop",
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "transport_attempt_count": 1,
            "raw_response": {"fixture": True},
        }

    @staticmethod
    def _graph_output(request: dict[str, Any]) -> dict[str, Any]:
        node = request["node_type"]
        context = request["context"]
        if node == "lead_planning":
            case = context["case_input"]
            return _raw_outputs(case)["lead"]
        if node == "specialist_judgment":
            identity = context["case_identity"]
            unit = context["research_unit"]
            return {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "unit_id": unit["unit_id"], "epistemic_state": "mixed",
                "judgment": "The assigned evidence supports a bounded judgment.",
                "mechanism": "The evidence changes the operating interpretation.",
                "financial_or_valuation_link": "The financial link remains bounded by supplied evidence.",
                "evidence_ids": list(unit["evidence_ids"]), "counterevidence_ids": [],
                "gap_ids": list(unit["gap_ids"]),
                "what_would_change": "Additional case-local evidence could change the judgment.",
            }
        if node == "cross_cell_synthesis":
            identity = context["case_identity"]
            return {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "thesis": "The supplied evidence supports a bounded thesis with unresolved uncertainty.",
                "confidence": "Moderate because the evidence is useful but incomplete.",
                "unit_ids": [row["unit_id"] for row in context["specialist_outputs"]],
                "dependencies": [], "conflicts": [],
                "material_gap_ids": [row["gap_id"] for row in context["explicit_gaps"]],
                "counter_thesis": "The same evidence can support a weaker interpretation.",
                "what_would_change": "New case-local evidence could resolve the uncertainty.",
            }
        if node == "writer":
            identity = context["case_identity"]
            evidence_ids = [row["evidence_id"] for row in context["evidence_index"]]
            gap_ids = [row["gap_id"] for row in context["explicit_gaps"]]
            unit_ids = [row["unit_id"] for row in context["specialist_outputs"]]
            sections = [
                {
                    "section_id": section_id,
                    "heading": section_id.replace("_", " ").title(),
                    "narrative": "The cited evidence supports a bounded conclusion while uncertainty remains.",
                    "evidence_ids": [evidence_ids[0]], "unit_ids": unit_ids,
                    "gap_ids": [gap_ids[0]],
                }
                for section_id in context["required_section_ids"]
            ]
            sections[0]["evidence_ids"] = evidence_ids
            sections[0]["gap_ids"] = gap_ids
            return {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "title": identity["case_key"] + " bounded corrected candidate",
                "sections": sections,
                "overall_boundary": "This candidate uses only the frozen evidence and preserves gaps.",
            }
        if node == "verifier":
            identity = context["case_identity"]
            return {
                "case_key": identity["case_key"], "as_of": identity["as_of"],
                "decision": "accept_raw_candidate", "material_failure": False,
                "findings": [],
                "checked_unit_ids": [row["unit_id"] for row in context["specialist_outputs"]],
                "checked_section_ids": [row["section_id"] for row in context["writer"]["sections"]],
            }
        raise AssertionError(node)


@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_three_cases_compile_same_protocol_with_case_qualified_ids(case_index: int) -> None:
    policy, case, raw = _fixture(case_index)
    boundary = _boundary(case)
    spec = compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)
    plan = compile_fixture_supervisor_plan(spec)
    validate_supervisor_plan(plan, spec)
    assert all(row["correction_id"].startswith(case["case_key"] + "-CORR-") for row in boundary["corrections"])
    assert [row["node_ref"].split(":", 1)[0] for row in plan["node_directives"]] == [
        "lead", "specialist", "writer", "verifier"
    ]
    request = compile_supervisor_request(
        spec=spec, raw_outputs=raw, policy=policy, corrected_run_id="corrected-" + case["case_key"]
    )
    encoded = request["messages"][1]["content"].lower()
    assert "expected_thesis" not in encoded
    assert "strongest_counter_thesis" not in encoded
    assert request["max_transport_attempts"] == 1


@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_nonempty_case_authority_is_compiled_into_schema_prompt_and_validator(
    case_index: int,
) -> None:
    policy, case, raw = _fixture(case_index)
    boundary = _boundary(case)
    spec = compile_supervisor_plan_spec(
        boundary=boundary,
        case_input=case,
        raw_outputs=raw,
    )
    item_schema = spec["output_schema"]["properties"]["node_directives"]["items"]
    assert item_schema["anyOf"] == [
        {"properties": {"evidence_ids": {"minItems": 1}}},
        {"properties": {"gap_ids": {"minItems": 1}}},
    ]
    request = compile_supervisor_request(
        spec=spec,
        raw_outputs=raw,
        policy=policy,
        corrected_run_id="compiled-authority-" + case["case_key"],
    )
    system_prompt = request["messages"][0]["content"]
    assert "including Verifier" in system_prompt
    assert "at least one supplied Evidence or Gap alias" in system_prompt
    assert "Numeric aliases alone are insufficient" in system_prompt

    captured_r1_shape = compile_fixture_supervisor_plan(spec)
    verifier = next(
        row
        for row in captured_r1_shape["node_directives"]
        if row["node_ref"] == "verifier"
    )
    verifier["evidence_ids"] = []
    verifier["numeric_aliases"] = []
    verifier["gap_ids"] = []
    with pytest.raises(
        S2SupervisorRuntimeError,
        match="s2_06_supervisor_empty_case_authority",
    ):
        validate_supervisor_plan(captured_r1_shape, spec)


def test_current_citation_and_coverage_findings_have_executable_owners() -> None:
    _, case, raw = _fixture()
    boundary = _boundary(case)
    by_code = {row["source_finding"]["code"]: row for row in boundary["corrections"]}
    for code in (
        "specialist_assigned_pack_coverage_incomplete",
        "writer_case_pack_coverage_incomplete",
        "verifier_missed_material_failure",
    ):
        assert by_code[code]["action_code"] in {"return_to_originating_node", "return_to_verifier"}
        assert by_code[code]["new_model_call_required"] is True
    compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)


def test_unknown_current_finding_class_fails_before_prompt() -> None:
    _, case, raw = _fixture()
    evaluation = _evaluation()
    evaluation["findings"].append({"severity": "L1", "code": "new_unowned_code", "node_ref": "writer"})
    with pytest.raises(ValueError, match="s2_06_unowned_finding_class"):
        _boundary(case, evaluation=evaluation)


def test_cross_case_alias_and_hidden_surface_mutations_fail_closed() -> None:
    policy, case, raw = _fixture()
    boundary = _boundary(case)
    spec = compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)
    plan = compile_fixture_supervisor_plan(spec)
    plan["node_directives"][0]["evidence_ids"].append("MU_E99")
    with pytest.raises(S2SupervisorRuntimeError, match="cross_case_or_unknown_alias"):
        validate_supervisor_plan(plan, spec)
    numeric_mutation = compile_fixture_supervisor_plan(spec)
    numeric_mutation["node_directives"][0]["numeric_aliases"].append("derived::unknown_metric")
    with pytest.raises(S2SupervisorRuntimeError, match="cross_case_or_unknown_alias"):
        validate_supervisor_plan(numeric_mutation, spec)
    dependency_mutation = compile_fixture_supervisor_plan(spec)
    dependency_mutation["node_directives"][0]["correction_ids"] = ["DELL-CORR-999"]
    with pytest.raises(S2SupervisorRuntimeError, match="directive_binding_invalid"):
        validate_supervisor_plan(dependency_mutation, spec)
    contaminated = deepcopy(raw)
    contaminated["writer"]["expected_thesis"] = "hidden answer"
    contaminated_spec = compile_supervisor_plan_spec(
        boundary=boundary, case_input=case, raw_outputs=contaminated
    )
    with pytest.raises(S2SupervisorRuntimeError, match="forbidden_hidden_surface"):
        compile_supervisor_request(
            spec=contaminated_spec,
            raw_outputs=contaminated,
            policy=policy,
            corrected_run_id="corrected-DELL",
        )
    cross_raw = deepcopy(raw)
    cross_raw["writer"]["sections"][0]["evidence_ids"].append("MU_E99")
    with pytest.raises(S2SupervisorRuntimeError, match="cross_case_raw_alias_forbidden"):
        compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=cross_raw)


def test_dependency_closure_and_capacity_are_exact() -> None:
    _, case, raw = _fixture()
    boundary = _boundary(case)
    spec = compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)
    plan = compile_fixture_supervisor_plan(spec)
    proof = compile_capacity_proof(plan=plan, spec=spec, raw_outputs=raw)
    assert proof["corrected_graph_calls"] == 10
    assert proof["provider_calls"] == 11
    assert proof["affected_nodes"] == [
        "lead", *[f"specialist:unit_{index}" for index in range(6)],
        "synthesis", "writer", "verifier",
    ]
    assert proof["pass"] is True


def test_eight_unit_full_graph_is_blocked_by_frozen_capacity() -> None:
    _, case, raw = _fixture(units=8)
    boundary = _boundary(case)
    spec = compile_supervisor_plan_spec(boundary=boundary, case_input=case, raw_outputs=raw)
    plan = compile_fixture_supervisor_plan(spec)
    proof = compile_capacity_proof(plan=plan, spec=spec, raw_outputs=raw)
    assert proof["corrected_graph_calls"] == 12
    assert proof["provider_calls"] == 13
    assert proof["pass"] is False


@pytest.mark.parametrize("case_index", [0, 1, 2])
def test_three_case_full_fake_freezes_capture_first_candidate_without_raw_mutation(
    tmp_path: Path, case_index: int
) -> None:
    policy, case, raw = _fixture(case_index)
    raw_digest = canonical_digest(raw)
    fake = FullFakeCorrectedProvider()
    runtime_root = tmp_path / case["case_key"]
    boundary = _boundary(case)
    run_id = "corrected-" + case["case_key"]
    attempt_id = "attempt-1-" + case["case_key"]
    terminal = execute_corrected_candidate(
        admission=_admission(
            boundary=boundary, case=case, raw=raw,
            corrected_run_id=run_id, corrected_attempt_id=attempt_id,
        ),
        boundary=boundary,
        case_input=case,
        raw_outputs=raw,
        policy=policy,
        corrected_run_id=run_id,
        corrected_attempt_id=attempt_id,
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "shared.sqlite3"),
        provider_call=fake,
        observed_at=OBSERVED,
    )
    assert terminal["status"] == "terminal_completed"
    assert terminal["candidate_frozen"] is True
    assert terminal["completed_calls"] == len(fake.calls) == 11
    assert terminal["retry_count"] == terminal["fallback_count"] == 0
    assert terminal["raw_mutations"] == 0
    assert canonical_digest(raw) == raw_digest
    assert len(list((runtime_root / "supervisor_augmented/captures").glob("*.json"))) == 1
    assert len(list((runtime_root / "corrected_candidate/captures").glob("*.json"))) == 10
    scoring = assert_hidden_scoring_allowed(runtime_root)
    assert scoring["scoring_allowed"] is True
    assert terminal["hidden_scoring_executed"] is False


def test_authority_and_freeze_guards_fail_before_unsafe_actions(tmp_path: Path) -> None:
    policy, case, raw = _fixture()
    boundary = _boundary(case)
    run_id = "corrected-DELL"
    attempt_id = "attempt-DELL"
    with pytest.raises(S2SupervisorRuntimeError, match="not_authorized"):
        execute_corrected_candidate(
            admission=_admission(
                boundary=boundary, case=case, raw=raw,
                corrected_run_id=run_id, corrected_attempt_id=attempt_id,
                authorized=False,
            ),
            boundary=boundary, case_input=case, raw_outputs=raw, policy=policy,
            corrected_run_id=run_id, corrected_attempt_id=attempt_id,
            runtime_root=tmp_path / "unauthorized", provider_call=FullFakeCorrectedProvider(),
            shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "unauthorized.sqlite3"),
            observed_at=OBSERVED,
        )
    assert not (tmp_path / "unauthorized").exists()
    with pytest.raises(S2SupervisorRuntimeError, match="freeze_artifact_invalid"):
        assert_hidden_scoring_allowed(tmp_path / "missing")


@pytest.mark.parametrize(
    ("mutation", "code", "calls"),
    [
        ("transport", "s2_06_provider_transport_or_finish_failure", 3),
        ("lead_topology", "s2_06_corrected_lead_topology_changed", 2),
    ],
)
def test_failure_terminal_preserves_every_capture_and_stops_without_retry(
    tmp_path: Path, mutation: str, code: str, calls: int
) -> None:
    policy, case, raw = _fixture()
    runtime_root = tmp_path / mutation
    boundary = _boundary(case)
    run_id = "corrected-DELL-" + mutation
    attempt_id = "attempt-DELL-" + mutation
    terminal = execute_corrected_candidate(
        admission=_admission(
            boundary=boundary, case=case, raw=raw,
            corrected_run_id=run_id, corrected_attempt_id=attempt_id,
        ),
        boundary=boundary, case_input=case, raw_outputs=raw, policy=policy,
        corrected_run_id=run_id,
        corrected_attempt_id=attempt_id,
        runtime_root=runtime_root,
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "failure.sqlite3"),
        provider_call=FullFakeCorrectedProvider(mutation=mutation),
        observed_at=OBSERVED,
    )
    assert terminal["status"] == "terminal_failed_no_retry"
    assert terminal["terminal_code"] == code
    assert terminal["completed_calls"] == len(terminal["call_results"]) == calls
    assert terminal["retry_count"] == terminal["fallback_count"] == 0
    assert len(list(runtime_root.rglob("captures/*.json"))) == calls


def test_deterministic_deletion_changes_only_corrected_copy_and_reruns_downstream(
    tmp_path: Path,
) -> None:
    policy, case, raw = _fixture()
    raw["writer"]["sections"][0]["narrative"] = (
        "The evidence supports a bounded conclusion; an unsupported 999% range remains."
    )
    raw_digest = canonical_digest(raw)
    evaluation = {
        "raw_chain_complete": True,
        "hidden_scoring_eligible": True,
        "material_failure": True,
        "findings": [
            {
                "severity": "L1",
                "code": "directional_margin_sharpened_to_unsupported_range",
                "node_ref": "writer",
                "path": "$.sections[0].narrative",
                "tokens": ["999%"],
            }
        ],
    }
    runtime_root = tmp_path / "deterministic"
    boundary = _boundary(case, evaluation=evaluation)
    run_id = "corrected-DELL-deterministic"
    attempt_id = "attempt-DELL-deterministic"
    terminal = execute_corrected_candidate(
        admission=_admission(
            boundary=boundary, case=case, raw=raw,
            corrected_run_id=run_id, corrected_attempt_id=attempt_id,
        ),
        boundary=boundary,
        case_input=case, raw_outputs=raw, policy=policy,
        corrected_run_id=run_id,
        corrected_attempt_id=attempt_id,
        runtime_root=runtime_root, provider_call=FullFakeCorrectedProvider(),
        shared_ledger=SharedAdmissionConsumptionLedger(tmp_path / "deterministic.sqlite3"),
        observed_at=OBSERVED,
    )
    assert terminal["status"] == "terminal_completed"
    assert terminal["completed_calls"] == 2
    candidate = json.loads((runtime_root / "corrected_candidate/candidate.json").read_text(encoding="utf-8"))
    assert "999%" not in candidate["outputs"]["writer"]["sections"][0]["narrative"]
    assert canonical_digest(raw) == raw_digest


def test_corrected_admission_is_exact_once_even_with_new_runtime_root(tmp_path: Path) -> None:
    policy, case, raw = _fixture()
    boundary = _boundary(case)
    run_id = "corrected-DELL-exact-once"
    attempt_id = "attempt-DELL-exact-once"
    admission = _admission(
        boundary=boundary, case=case, raw=raw,
        corrected_run_id=run_id, corrected_attempt_id=attempt_id,
    )
    ledger = SharedAdmissionConsumptionLedger(tmp_path / "exact-once.sqlite3")
    common = {
        "admission": admission, "boundary": boundary, "case_input": case,
        "raw_outputs": raw, "policy": policy, "corrected_run_id": run_id,
        "corrected_attempt_id": attempt_id, "shared_ledger": ledger,
        "provider_call": FullFakeCorrectedProvider(), "observed_at": OBSERVED,
    }
    first = execute_corrected_candidate(runtime_root=tmp_path / "first", **common)
    assert first["status"] == "terminal_completed"
    with pytest.raises(SharedAdmissionLedgerError, match="already_consumed"):
        execute_corrected_candidate(runtime_root=tmp_path / "second", **common)


def test_implementation_record_binds_runtime_and_honest_acceptance_boundary() -> None:
    record = json.loads(IMPLEMENTATION.read_text(encoding="utf-8"))
    body = {key: value for key, value in record.items() if key != "implementation_digest"}
    assert record["implementation_digest"] == canonical_digest(body)
    for key in ("case_scoped_disposition_compiler", "supervisor_and_corrected_candidate_runtime"):
        binding = record["implementation"][key]
        assert hashlib.sha256((ROOT / binding["ref"]).read_bytes()).hexdigest() == binding["sha256"]
    assert record["verification"]["model_provider_network_calls"] == [0, 0, 0]
    assert record["stage_acceptance"]["S2_06_shared_zero_call_contract_alignment"] == "engineering_pass"
    assert record["stage_acceptance"]["supervised_recoverability"] == "not_proven"
