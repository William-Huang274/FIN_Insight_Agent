from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.bounded_agent_contract_policies import (
    research_profile_for_ref,
)
from apps.workbench.backend.application.bounded_agent_executor import (
    BOUNDED_AGENT_ARTIFACT_TYPES,
    S3_FOUR_LAYER_VERIFIER_LAYERS,
    DeepSeekS3ThreeCellNodeExecutor,
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    S3ThreeCellBoundedAgentInputPack,
    build_s4_case_pack_bounded_agent_input_fixture,
)
from apps.workbench.backend.application.evidence_service import (
    consume_s4_case_runtime_evidence_route,
)
from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.parser_numeric import (
    consume_s4_case_runtime_financial_numeric,
)
from sec_agent.langgraph_orchestrator import (
    consume_s4_case_runtime_specialist_and_research_lead,
)
from sec_agent.memo_llm import (
    consume_s4_case_runtime_writer_verifier_review,
)
from sec_agent.research_graph_store import (
    consume_s4_case_runtime_bounded_graph,
)
from sec_agent.s4_case_runtime import (
    S4CaseRuntimeError,
    S4_RUNTIME_CONSUMER_IDS,
    assemble_s4_case_local_judgment_atom,
    assert_s4_case_local_fact_rows,
    assert_s4_structural_fixture_has_no_case_facts,
    consume_s4_case_runtime_binding,
    load_s4_case_runtime_binding,
    s4_scoped_local_ref,
)


class _S4ZeroCallNodeExecutor:
    def __init__(self, case_ticker: str, method_id: str) -> None:
        self.case_ticker = case_ticker
        self.method_id = method_id
        self.calls: list[dict[str, Any]] = []

    def execute_node(
        self,
        node_id: str,
        payload: Mapping[str, Any],
        admission: S3ThreeCellBoundedAgentAdmission,
        *,
        run_identity: Mapping[str, str],
    ) -> Mapping[str, Any]:
        del admission
        s4 = payload.get("s4_case_runtime")
        assert isinstance(s4, Mapping)
        expected_consumer = (
            "specialist_and_research_lead"
            if node_id.startswith("domain_specialist:")
            or node_id == "research_lead"
            else "writer_verifier_and_review_surface"
        )
        assert s4["consumer_id"] == expected_consumer
        assert s4["case_ticker"] == self.case_ticker
        assert s4["method_id"] == self.method_id
        self.calls.append(
            {
                "node_id": node_id,
                "payload": dict(payload),
                "run_identity": dict(run_identity),
            }
        )

        if node_id.startswith("domain_specialist:"):
            cell_input = dict(payload["cell_input"])
            case_method = dict(cell_input["s4_case_method"])
            assert case_method["case_ticker"] == self.case_ticker
            assert case_method["method_id"] == self.method_id
            cell_id = str(cell_input["program_cell_id"])
            output: dict[str, Any] = {
                "program_cell_id": cell_id,
                "fact_layer": [],
                "explanation_layer": [
                    "T03 injects the case method but admits no factual row."
                ],
                "judgment_layer": [
                    "The deterministic fixture remains cannot-infer."
                ],
                "remaining_gaps": list(
                    case_method["program_cell_contract"][
                        "typed_cannot_infer_codes"
                    ][:1]
                ),
                "what_would_change": list(
                    case_method["program_cell_contract"][
                        "what_would_change_targets"
                    ][:1]
                ),
                "terminal_class": "typed_cannot_infer",
            }
        elif node_id == "research_lead":
            specialist_digests = dict(
                payload["specialist_output_digests"]
            )
            output = {
                "cell_heads": [
                    {
                        "program_cell_id": cell_id,
                        "specialist_output_digest": digest,
                    }
                    for cell_id, digest in specialist_digests.items()
                ],
                "cross_cell_dependencies": [
                    "Case-specific demand, value, and risk gaps stay linked."
                ],
                "conflict_adjudications": [
                    "No fact is admitted, so no attribution is promoted."
                ],
                "variant_view": (
                    f"{self.case_ticker} uses {self.method_id} without "
                    "borrowing a different Case fact."
                ),
                "remaining_gaps": [
                    "Official source rows remain pending a later admission."
                ],
            }
        elif node_id == "memo_writer":
            output = {
                "title_zh_cn": f"{self.case_ticker} 三单元 T03 预检",
                "executive_summary_zh_cn": (
                    "方法已注入共享 Runtime，但事实与付费研究尚未执行。"
                ),
                "sections": [
                    {
                        "program_cell_id": cell_id,
                        "content_zh_cn": (
                            "仅投影方法、typed gap 与 what-would-change。"
                        ),
                    }
                    for cell_id in payload["writer_contract"][
                        "required_program_cell_ids"
                    ]
                ],
                "limitations_zh_cn": [
                    "本 fixture 不包含 Evidence、Numeric 或 Graph 事实。"
                ],
                "consumed_lead_digest": str(
                    payload["cross_cell_lead_digest"]
                ),
                "source_calls": 0,
                "tool_calls": 0,
            }
        elif node_id == "verifier":
            output = {
                "findings": [
                    {
                        "layer": layer,
                        "status": "pass",
                        "issues": [],
                    }
                    for layer in S3_FOUR_LAYER_VERIFIER_LAYERS
                ],
                "bound_lead_digest": str(
                    payload["cross_cell_lead_digest"]
                ),
                "bound_writer_digest": str(payload["writer_digest"]),
                "decision": "accept_for_internal_review",
            }
        else:
            raise AssertionError(node_id)
        return {
            "node_id": node_id,
            "output": output,
            "observed_counts": {
                "model_calls": 0,
                "provider_calls": 0,
                "network_calls": 0,
                "source_network_calls": 0,
                "external_tool_calls": 0,
                "live_case_head_writes": 0,
                "evaluation_evidence_promotions": 0,
            },
            "usage_receipts": [],
            "version_bindings": {
                "agent_definition_version_ref": f"fixture:{node_id}:v1",
                "skill_pack_version_ref": f"fixture:{node_id}:v1",
                "fixture_only": True,
            },
        }


def _execute_fixture(case_ticker: str) -> tuple[Any, Any, Any]:
    binding = load_s4_case_runtime_binding(ROOT, case_ticker)
    input_pack = build_s4_case_pack_bounded_agent_input_fixture(
        binding,
        case_id=f"case-s4-t03-{case_ticker.lower()}",
        query=f"Evaluate the {case_ticker} S4 transfer contract",
    )
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id=(
            f"fin01-s4-t03-{case_ticker.lower()}-"
            "zero-call-fixture-not-live-admission"
        ),
        execution_mode="zero_call_S4_case_runtime_preflight",
        company=case_ticker,
        research_profile_ref=binding.research_profile_ref,
    )
    node_executor = _S4ZeroCallNodeExecutor(
        case_ticker, binding.method_id
    )
    result = S3ThreeCellBoundedAgentExecutor(node_executor).execute(
        input_pack,
        admission,
        run_identity={
            "work_unit_id": f"wu-s4-t03-{case_ticker.lower()}",
            "attempt_id": f"attempt-s4-t03-{case_ticker.lower()}",
            "research_run_id": f"run-s4-t03-{case_ticker.lower()}",
        },
    )
    return binding, node_executor, result


def test_official_identifiers_profiles_routes_and_binding_digests_resolve() -> None:
    expected = {
        "DELL": "CIK0001571996",
        "MU": "CIK0000723125",
    }
    bindings = {
        ticker: load_s4_case_runtime_binding(ROOT, ticker)
        for ticker in expected
    }

    for ticker, binding in bindings.items():
        assert binding.issuer_identifier == expected[ticker]
        assert binding.issuer_identifier_source_ref.startswith(
            "https://www.sec.gov/"
        )
        assert set(binding.local_source_routes_by_cell) == set(
            binding.program_cell_ids
        )
        assert all(binding.local_source_routes_by_cell.values())
        assert all(
            count == 0
            for count in binding.factual_content_counts.values()
        )
        profile = research_profile_for_ref(binding.research_profile_ref)
        assert profile.company == ticker
        assert profile.program_cell_ids == binding.program_cell_ids
    assert (
        bindings["DELL"].case_identity_namespace
        != bindings["MU"].case_identity_namespace
    )
    assert (
        bindings["DELL"].runtime_binding_digest
        != bindings["MU"].runtime_binding_digest
    )


def test_all_seven_existing_consumers_receive_exact_case_method_slices() -> None:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    injections = {
        "evidence_route_plan": consume_s4_case_runtime_evidence_route(
            binding
        ),
        "financial_numeric_pack": (
            consume_s4_case_runtime_financial_numeric(binding)
        ),
        "bounded_graph_pack": consume_s4_case_runtime_bounded_graph(
            binding
        ),
        "specialist_and_research_lead": (
            consume_s4_case_runtime_specialist_and_research_lead(binding)
        ),
        "bounded_agent_input_and_execution": (
            consume_s4_case_runtime_binding(
                binding, "bounded_agent_input_and_execution"
            ).model_dump(mode="json")
        ),
        "writer_verifier_and_review_surface": (
            consume_s4_case_runtime_writer_verifier_review(binding)
        ),
        "workbench_projection": consume_s4_case_runtime_binding(
            binding, "workbench_projection"
        ).model_dump(mode="json"),
    }

    assert tuple(injections) == S4_RUNTIME_CONSUMER_IDS
    assert all(
        value["runtime_binding_digest"]
        == binding.runtime_binding_digest
        for value in injections.values()
    )
    assert all(
        value["case_identity_namespace"]
        == binding.case_identity_namespace
        for value in injections.values()
    )
    assert all(value["runtime_injected"] for value in injections.values())
    assert all(
        value["paid_artifact_proven"] is False
        for value in injections.values()
    )


@pytest.mark.parametrize("case_ticker", ["DELL", "MU"])
def test_shared_executor_consumes_case_method_in_six_nodes_and_nine_artifacts(
    case_ticker: str,
) -> None:
    binding, node_executor, result = _execute_fixture(case_ticker)

    specialist_payload = node_executor.calls[0]["payload"]
    model_view = DeepSeekS3ThreeCellNodeExecutor._specialist_model_view(
        specialist_payload
    )
    assert model_view["s4_case_method"]["method_id"] == binding.method_id
    assert model_view["s4_case_method"]["case_identity_namespace"] == (
        binding.case_identity_namespace
    )
    assert len(node_executor.calls) == 6
    assert len(result.artifacts) == 9
    assert {artifact.artifact_type for artifact in result.artifacts} == set(
        BOUNDED_AGENT_ARTIFACT_TYPES
    )
    manifest = next(
        artifact.payload
        for artifact in result.artifacts
        if artifact.artifact_type == "bounded_agent_manifest"
    )
    assert len(manifest["node_receipts"]) == 6
    assert all(
        row["s4_case_runtime_consumption"]["runtime_binding_digest"]
        == binding.runtime_binding_digest
        for row in manifest["node_receipts"]
    )
    assert all(
        artifact.payload["s4_case_runtime"]["case_ticker"] == case_ticker
        for artifact in result.artifacts
    )
    assert all(
        artifact.payload["s4_case_runtime"]["paid_artifact_proven"]
        is False
        for artifact in result.artifacts
    )
    evidence = next(
        artifact.payload
        for artifact in result.artifacts
        if artifact.artifact_type == "bounded_agent_evidence"
    )
    numeric = next(
        artifact.payload
        for artifact in result.artifacts
        if artifact.artifact_type == "bounded_agent_numeric"
    )
    assert evidence["agent_fact_rows"] == []
    assert numeric["agent_numeric_fact_rows"] == []


@pytest.mark.parametrize("case_ticker", ["DELL", "MU"])
def test_fact_empty_fixture_carries_explicit_t04_lineage_without_fact_inflation(
    case_ticker: str,
) -> None:
    binding = load_s4_case_runtime_binding(ROOT, case_ticker)
    input_pack = build_s4_case_pack_bounded_agent_input_fixture(
        binding,
        case_id=f"case-s4-t03-{case_ticker.lower()}-lineage",
        query="Verify fact-empty T04 lineage",
    )
    source = input_pack.s4_case_runtime["source_grounded_input"]
    assert source["fixture_only"] is True
    assert source["fact_rows_admitted"] == 0
    assert source["source_network_calls"] == 0
    assert input_pack.lineage["S4_T04_source_grounded_input"] == {
        "version_ref": source["contract_ref"],
        "digest": source["source_pack_digest"],
    }


def test_local_scoped_identity_and_judgment_atom_assembly_are_case_cell_exact() -> None:
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    refs = [
        s4_scoped_local_ref(
            binding,
            program_cell_id=cell_id,
            identity_kind="claim",
            local_id="C001",
        )
        for cell_id in binding.program_cell_ids
    ]
    assert len({canonical_digest(ref) for ref in refs}) == 3

    atom = assemble_s4_case_local_judgment_atom(
        binding,
        program_cell_id=binding.program_cell_ids[0],
        provider_atom={
            "epistemic_status": "fact_supported",
            "direct_answer_atom": "One bounded answer atom.",
            "counterevidence_atom": "One bounded counterevidence atom.",
            "boundary_atom": "Exact issuer scope only.",
            "selected_fact_aliases": ["F001"],
            "selected_context_aliases": ["X001"],
            "selected_WWC_aliases": ["W001"],
        },
        fact_aliases={"F001": "fact_001"},
        context_aliases={"X001": "context_001"},
        what_would_change_aliases={"W001": "wwc_001"},
    )
    assert atom["claim_fact_links"]
    assert atom["canonical_scope"]["entity_ref"] == "MU"
    assert atom["lineage"]["local_assembly"] is True
    assert atom["lineage"]["provider_owned_ID_or_scope"] is False

    with pytest.raises(
        S4CaseRuntimeError,
        match="cannot_infer_fact_support_forbidden",
    ):
        assemble_s4_case_local_judgment_atom(
            binding,
            program_cell_id=binding.program_cell_ids[0],
            provider_atom={
                "epistemic_status": "cannot_infer",
                "direct_answer_atom": "Cannot infer.",
                "counterevidence_atom": "No admitted counterevidence.",
                "boundary_atom": "Exact source remains missing.",
                "selected_fact_aliases": ["F001"],
                "selected_context_aliases": [],
                "selected_WWC_aliases": ["W001"],
            },
            fact_aliases={"F001": "fact_001"},
            context_aliases={},
            what_would_change_aliases={"W001": "wwc_001"},
        )


def test_cross_case_and_structural_fact_leakage_fail_closed() -> None:
    dell = load_s4_case_runtime_binding(ROOT, "DELL")
    mu = load_s4_case_runtime_binding(ROOT, "MU")
    dell_row = {
        "case_identity_namespace": dell.case_identity_namespace,
        "entity_ref": "DELL",
        "issuer_identifier": dell.issuer_identifier,
        "program_cell_id": dell.program_cell_ids[0],
        "fact_id": "fixture_fact_001",
    }
    assert_s4_case_local_fact_rows(dell, [dell_row])

    with pytest.raises(
        S4CaseRuntimeError, match="cross_case_fact_leakage"
    ):
        assert_s4_case_local_fact_rows(mu, [dell_row])
    with pytest.raises(
        S4CaseRuntimeError, match="cross_case_fact_leakage"
    ):
        assert_s4_case_local_fact_rows(
            dell,
            [
                {
                    **dell_row,
                    "entity_ref": "NVDA",
                }
            ],
        )
    for structural_profile in ("SaaS", "Bank"):
        assert_s4_structural_fixture_has_no_case_facts(
            structural_profile, []
        )
        with pytest.raises(
            S4CaseRuntimeError,
            match="structural_fixture_fact_leakage",
        ):
            assert_s4_structural_fixture_has_no_case_facts(
                structural_profile, [dell_row]
            )


def test_tampered_consumer_injection_stops_before_any_node() -> None:
    binding = load_s4_case_runtime_binding(ROOT, "DELL")
    input_pack = build_s4_case_pack_bounded_agent_input_fixture(
        binding,
        case_id="case-s4-t03-dell-tamper",
        query="Tamper fixture",
    )
    payload = input_pack.model_dump(mode="json")
    payload["s4_case_runtime"]["consumer_injections"][
        "specialist_and_research_lead"
    ]["method_id"] = "s4_mu_hbm_supply_pricing_and_cycle_playbook"
    tampered = S3ThreeCellBoundedAgentInputPack.model_validate(payload)
    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id="fin01-s4-t03-tamper-not-live-admission",
        execution_mode="zero_call_S4_case_runtime_preflight",
        company="DELL",
        research_profile_ref=binding.research_profile_ref,
    )
    node_executor = _S4ZeroCallNodeExecutor("DELL", binding.method_id)

    with pytest.raises(
        S4CaseRuntimeError, match="injection_mismatch"
    ):
        S3ThreeCellBoundedAgentExecutor(node_executor).execute(
            tampered,
            admission,
            run_identity={
                "work_unit_id": "wu-s4-t03-tamper",
                "attempt_id": "attempt-s4-t03-tamper",
                "research_run_id": "run-s4-t03-tamper",
            },
        )
    assert node_executor.calls == []


def test_workbench_projection_reads_exact_case_method_without_maturity_inflation() -> None:
    source = (
        ROOT
        / "apps"
        / "workbench"
        / "frontend"
        / "vite"
        / "src"
        / "app"
        / "WorkbenchNext.tsx"
    ).read_text(encoding="utf-8")

    assert "projectS4CaseRuntime" in source
    assert "s4_case_runtime" in source
    assert "paid_artifact_proven !== false" in source
    assert "human_review_completed !== false" in source
