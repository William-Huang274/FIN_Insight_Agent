from __future__ import annotations

import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import pytest


pytest.importorskip("mcp", reason="agent-runtime optional dependency")

import sec_agent.agent_runtime.deepseek_structured_agents as deepseek_adapter

from sec_agent.agent_runtime.dell_agent_server_data_composition import (
    DELL_APPROVED_DATA_SNAPSHOT_ID,
    DELL_APPROVED_RESEARCH_AS_OF,
    DellApprovedDataComposition,
    DellApprovedDataCompositionError,
    open_dell_approved_data_composition,
)
from sec_agent.agent_runtime.dell_reference_vertical_contracts import (
    BoundBranchTask,
    CaseFoundationBinding,
    ToolLaneResult,
    ToolLaneTask,
    canonical_sha256,
)
from sec_agent.agent_runtime.dell_reference_vertical_graph import (
    build_dell_reference_vertical_state_graph,
)
from sec_agent.research_foundation.contracts import (
    load_dell_reference_vertical_foundation,
)


ROOT = Path(__file__).resolve().parents[1]
FOUNDATION_PATH = (
    ROOT
    / "configs"
    / "research"
    / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
)
DEFAULT_ARTIFACT_ENV = {
    "FIN_REPO_ROOT": str(ROOT),
    "FINSIGHT_DELL_S1_NODES_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "rag_mature_stack/retrieval_qualification/"
            "dell_rag_full_stack_preview_attempt_20260902_03/"
            "retrieval_nodes.jsonl"
        )
    ),
    "FINSIGHT_DELL_REVIEWED_BASE_PACK_PATH": str(
        ROOT
        / "data"
        / "workbench_private"
        / "fin_0_1_3_s1_dell_direct_source_evidence"
        / "r4"
        / "successor"
        / "pack.json"
    ),
    "FINSIGHT_DELL_REVIEWED_OVERLAY_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "evidence_overlay/attempts/"
            "20260902T051005+0800-dell-fy27q2-sec-ex99-review-a01/"
            "reviewed-evidence-case-projection.json"
        )
    ),
    "FINSIGHT_DELL_S2_RESULT_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
            "s2_exact_period_contract_successor_20260902_r1/"
            "company_financial_fact_mart_result.json"
        )
    ),
    "FINSIGHT_COMPANY_FINANCIAL_FACT_MART_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/s2/"
            "s2_exact_period_contract_successor_20260902_r1/"
            "company_financial_facts.sqlite"
        )
    ),
    "FINSIGHT_DELL_EXTERNAL_MANIFEST_PATH": str(
        Path(
            "Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/"
            "external_exact_url_qualification/"
            "dell_external_exact_url_zero_model_20260902_r12/manifest.json"
        )
    ),
}
EXPECTED_DECISION_DIGEST = (
    "739df0f5d2880af8e27a08b5f9e31e10e894f4900fb72681e7b02e065e89b204"
)
PHYSICAL_SELECTOR_KEYS = frozenset(
    {
        "issuer_ids",
        "fiscal_periods",
        "source_roles",
        "route_ids",
        "lanes",
        "domain_allowlist",
        "external_route_ref",
        "local_scope",
        "locator",
        "path",
    }
)
PHYSICAL_RESULT_SELECTOR_KEYS = frozenset(
    {"issuer_id", "fiscal_period", "source_role", "route_id", "lane", "branches"}
)
REVIEWED_TOPIC_REFS = (
    "capacity_inputs_execution",
    "capital_allocation_and_valuation",
    "cash_conversion_balance_sheet",
    "counterevidence_and_what_would_change",
    "demand_volume_quality",
    "management_outlook",
    "operating_performance",
    "pricing_mix_value_capture",
    "regulatory_policy_exposure",
    "relationship_attribution",
)


def _all_artifacts_available() -> bool:
    return FOUNDATION_PATH.is_file() and all(
        Path(value).is_file()
        for name, value in DEFAULT_ARTIFACT_ENV.items()
        if name != "FIN_REPO_ROOT"
    )


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return {
            *(str(key) for key in value),
            *(
                child_key
                for child in value.values()
                for child_key in _nested_keys(child)
            ),
        }
    if isinstance(value, (list, tuple)):
        return {
            child_key
            for child in value
            for child_key in _nested_keys(child)
        }
    return set()


def _foundation_binding(
    composition: DellApprovedDataComposition,
) -> CaseFoundationBinding:
    foundation = load_dell_reference_vertical_foundation(FOUNDATION_PATH)
    raw = composition.dependencies.foundation_binder(
        {
            "case_id": foundation.case_identity.case_id,
            "research_as_of": DELL_APPROVED_RESEARCH_AS_OF,
            "snapshot_id": DELL_APPROVED_DATA_SNAPSHOT_ID,
            "foundation_digest": canonical_sha256(foundation),
        }
    )
    # The binder deliberately returns ordinary JSON for Agent Server state.
    # Validate at that native boundary so strict tuple fields are reconstructed.
    return CaseFoundationBinding.model_validate_json(
        json.dumps(raw, ensure_ascii=False, allow_nan=False)
    )


def _route(
    composition: DellApprovedDataComposition,
    *,
    branch_id: str,
    intent_kind: str,
    semantic_source_family_ref: str | None = None,
) -> Mapping[str, Any]:
    matches = [
        row
        for row in composition.dependencies.planner_source_route_catalog["routes"]
        if row["coverage_obligation_id"] == branch_id
        and row["intent_kind"] == intent_kind
        and (
            semantic_source_family_ref is None
            or tuple(row["semantic_source_family_refs"])
            == (semantic_source_family_ref,)
        )
    ]
    if intent_kind == "reviewed_evidence":
        matches = [row for row in matches if row["requirement"] == "required"]
    assert len(matches) == 1
    return matches[0]


def _reviewed_request(
    composition: DellApprovedDataComposition,
) -> dict[str, Any]:
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="reviewed_evidence",
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "reviewed_evidence",
            "query": "Dell AI optimized server orders revenue backlog",
            "purpose": "Retrieve reviewed Dell issuer evidence for issuer truth.",
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Resolve issuer performance using reviewed evidence."
            ),
            "limit": 12,
            "topic_refs": list(REVIEWED_TOPIC_REFS),
            "evidence_role_refs": [],
            "minimum_authority_tier": "reviewed",
        },
    }


def _local_request(
    composition: DellApprovedDataComposition,
) -> dict[str, Any]:
    family = "F1_SEC_ISSUER_FACTS"
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="local_evidence",
        semantic_source_family_ref=family,
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "local_evidence",
            "query": (
                "Dell FY2027 Q1 revenue gross profit operating income "
                "infrastructure solutions group servers"
            ),
            "purpose": (
                "Retrieve primary Dell filing candidate blocks for issuer truth."
            ),
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Locate structured filing sections relevant to operating performance."
            ),
            "limit": 6,
            "semantic_source_family_refs": [family],
            "source_role_intents": [],
            "content_surface_intents": ["prose", "table"],
        },
    }


def _external_request(
    composition: DellApprovedDataComposition,
) -> dict[str, Any]:
    family = "F2_DELL_IR_EARNINGS"
    route = _route(
        composition,
        branch_id="Q1_ISSUER_TRUTH",
        intent_kind="external_source",
        semantic_source_family_ref=family,
    )
    return {
        "minimum_route_obligation_id": route["minimum_route_obligation_id"],
        "intent": {
            "intent_kind": "external_source",
            "query": "Dell fiscal 2027 second quarter AI server earnings release",
            "purpose": "Retrieve frozen Dell investor relations source candidate.",
            "entity_refs": [],
            "period_intents": [],
            "expected_information_gain": (
                "Locate the exact investor relations source without live web access."
            ),
            "limit": 2,
            "semantic_source_family_refs": [family],
            "domain_allowlist": [],
        },
    }


def _branch_task(
    composition: DellApprovedDataComposition,
    *,
    label: str,
    evidence_request: Mapping[str, Any],
    fact_requests: tuple[dict[str, Any], ...] = (),
) -> BoundBranchTask:
    foundation = _foundation_binding(composition)
    method = next(
        row
        for row in foundation.branch_methods
        if row.branch_id == "Q1_ISSUER_TRUTH"
    )
    return BoundBranchTask(
        task_id=f"data-composition-test:{label}",
        case_id=foundation.case_id,
        branch_id=method.branch_id,
        revision=0,
        priority=method.priority,
        objective=method.objective,
        evidence_requests=(dict(evidence_request),),
        fact_requests=fact_requests,
        research_as_of=foundation.research_as_of,
        snapshot_id=foundation.snapshot_id,
        foundation_digest=foundation.foundation_digest,
        method_digest=method.method_digest,
        plan_digest=canonical_sha256({"test_task": label}),
    )


def _execute_evidence(
    composition: DellApprovedDataComposition,
    *,
    label: str,
    request: Mapping[str, Any],
) -> ToolLaneResult:
    lane_task = ToolLaneTask(
        lane="evidence",
        task=_branch_task(
            composition,
            label=label,
            evidence_request=request,
        ),
    )
    raw = composition.dependencies.evidence_tool(lane_task.model_dump(mode="json"))
    return ToolLaneResult.model_validate_json(
        json.dumps(raw, ensure_ascii=False, allow_nan=False)
    )


def test_composition_fails_closed_when_repository_root_is_missing() -> None:
    with pytest.raises(
        DellApprovedDataCompositionError,
        match="^approved_repository_root_missing$",
    ):
        with open_dell_approved_data_composition(
            run_invocation_id="missing-root",
            environment={},
        ):
            pass


def test_composition_fails_closed_when_required_data_path_is_missing() -> None:
    with pytest.raises(
        DellApprovedDataCompositionError,
        match=(
            "^approved_data_path_environment_missing:"
            "FINSIGHT_DELL_S1_NODES_PATH$"
        ),
    ):
        with open_dell_approved_data_composition(
            run_invocation_id="missing-data-path",
            environment={"FIN_REPO_ROOT": str(ROOT)},
        ):
            pass


def test_composition_fails_closed_when_data_path_is_not_a_file(
    tmp_path: Path,
) -> None:
    not_a_file = tmp_path / "directory-not-data"
    not_a_file.mkdir()
    environment = {
        "FIN_REPO_ROOT": str(ROOT),
        **{
            name: str(not_a_file)
            for name in DEFAULT_ARTIFACT_ENV
            if name != "FIN_REPO_ROOT"
        },
    }
    with pytest.raises(
        DellApprovedDataCompositionError,
        match=(
            "^approved_data_path_not_file:"
            "FINSIGHT_DELL_S1_NODES_PATH$"
        ),
    ):
        with open_dell_approved_data_composition(
            run_invocation_id="non-file-data-path",
            environment=environment,
        ):
            pass


def test_composition_rejects_content_drift_in_catalog_bound_foundation(
    tmp_path: Path,
) -> None:
    temp_root = tmp_path / "repo"
    temp_config = temp_root / "configs" / "research"
    temp_config.mkdir(parents=True)
    for name in (
        "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json",
        "fin_ia_0_1_3_dell_source_family_physical_route_catalog_v1_0.json",
        "fin_ia_0_1_3_dell_reviewed_evidence_enrichment_v1_0.json",
        "fin_ia_0_1_3_dell_owner_data_gate_decision_v1_0.json",
    ):
        shutil.copy2(ROOT / "configs" / "research" / name, temp_config / name)
    drifted_foundation = (
        temp_config
        / "fin_ia_0_1_3_dell_reference_vertical_foundation_v1_0.json"
    )
    # Extra JSON whitespace preserves semantic validity while changing bytes.
    # The composition must enforce the catalog's raw content binding anyway.
    drifted_foundation.write_text(
        drifted_foundation.read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    existing_file = str(drifted_foundation)
    environment = {
        "FIN_REPO_ROOT": str(temp_root),
        **{
            name: existing_file
            for name in DEFAULT_ARTIFACT_ENV
            if name != "FIN_REPO_ROOT"
        },
    }

    with pytest.raises(
        DellApprovedDataCompositionError,
        match="^approved_foundation_file_sha256_mismatch$",
    ):
        with open_dell_approved_data_composition(
            run_invocation_id="drifted-foundation",
            environment=environment,
        ):
            pass


@pytest.mark.skipif(
    not _all_artifacts_available(),
    reason="default D/Z frozen Dell data artifacts are unavailable",
)
@pytest.mark.local_data_integration
def test_real_approved_composition_exposes_semantic_catalog_and_four_data_lanes(
) -> None:
    with open_dell_approved_data_composition(
        run_invocation_id="real-data-composition-four-lanes",
        environment=DEFAULT_ARTIFACT_ENV,
    ) as composition:
        assert composition.decision_digest == EXPECTED_DECISION_DIGEST
        assert composition.reviewed_evidence_count == 56
        assert composition.local_candidate_count == 890
        assert composition.external_route_count == 12
        assert composition.s2_observation_count == 1_319
        assert composition.model_calls_authorized is False
        assert composition.network_calls_authorized is False
        assert composition.paid_calls_authorized is False

        catalog = composition.dependencies.planner_source_route_catalog
        assert catalog["schema_version"] == (
            "fin_ia_dell_provider_source_route_catalog_v1_0"
        )
        assert catalog["catalog_digest"] == composition.source_route_catalog_digest
        assert catalog["physical_selectors_exposed"] is False
        assert catalog["answer_free"] is True
        assert len(catalog["routes"]) == 36
        assert not PHYSICAL_SELECTOR_KEYS.intersection(_nested_keys(catalog))
        compiled_graph = build_dell_reference_vertical_state_graph(
            dependencies=composition.dependencies
        ).compile(name="dell_reference_vertical_data_gate_qualification")
        assert compiled_graph.name == (
            "dell_reference_vertical_data_gate_qualification"
        )

        reviewed = _execute_evidence(
            composition,
            label="reviewed",
            request=_reviewed_request(composition),
        )
        assert reviewed.status == "success"
        assert "reviewed_evidence" in reviewed.result_states
        reviewed_items = [
            row for row in reviewed.items if row["result_state"] == "reviewed_evidence"
        ]
        assert reviewed_items
        assert all(row["writer_citable"] is True for row in reviewed_items)

        local = _execute_evidence(
            composition,
            label="local",
            request=_local_request(composition),
        )
        assert local.status == "success"
        assert "retrieval_candidate" in local.result_states
        local_items = [
            row for row in local.items if row["result_state"] == "retrieval_candidate"
        ]
        assert local_items
        assert all(row["candidate_is_not_evidence"] is True for row in local_items)
        assert all(row["citation_eligible"] is False for row in local_items)

        external = _execute_evidence(
            composition,
            label="external-frozen",
            request=_external_request(composition),
        )
        assert external.status == "success"
        assert set(external.result_states) >= {
            "retrieval_candidate",
            "captured_source_candidate",
        }
        captured_items = [
            row
            for row in external.items
            if row["result_state"] == "captured_source_candidate"
        ]
        assert captured_items
        discovered_items = [
            row
            for row in external.items
            if row["result_state"] == "retrieval_candidate"
        ]
        assert len(discovered_items) <= 2
        assert len(captured_items) <= 2
        assert all(
            row["capture_method"] == "frozen_exact_url_candidate_replay"
            and row["transport_authority"] == "qualification_only"
            and row["captured_candidate_is_not_evidence"] is True
            and row["admission_required_before_citation"] is True
            and row["source_capture_authority"] is False
            and row["citation_eligible"] is False
            for row in captured_items
        )

        finance_task = ToolLaneTask(
            lane="finance",
            task=_branch_task(
                composition,
                label="finance",
                evidence_request=_reviewed_request(composition),
                fact_requests=(
                    {
                        "ticker": "DELL",
                        "metric_ids": ["revenue", "gross_profit"],
                        "research_as_of": "2026-09-02",
                        "granularity": "quarter_discrete",
                        "period_start": "2026-01-31",
                        "period_end": "2026-05-01",
                        "fiscal_years": [2027],
                        "selection_mode": "exact_period_end",
                        "requested_unit": "reported_source_unit",
                        "unit_family": None,
                    },
                ),
            ),
        )
        finance_raw = composition.dependencies.finance_tool(
            finance_task.model_dump(mode="json")
        )
        finance = ToolLaneResult.model_validate_json(
            json.dumps(finance_raw, ensure_ascii=False, allow_nan=False)
        )
        assert finance.status == "success"
        assert "numeric_fact" in finance.result_states
        numeric_facts = [
            row for row in finance.items if row["result_state"] == "numeric_fact"
        ]
        assert {row["metric_id"] for row in numeric_facts} == {
            "revenue",
            "gross_profit",
        }
        assert all(row["numeric_fact_authority"] is True for row in numeric_facts)

        specialist_projection = deepseek_adapter._project_request(
            "specialist",
            {
                "turn_index": 1,
                "task": finance_task.task.model_dump(mode="json"),
                "method_context": {"candidate_is_not_evidence": True},
                "evidence_result": local.model_dump(mode="json"),
                "finance_result": finance.model_dump(mode="json"),
                "prior_workpaper": None,
                "counter_challenge": None,
            },
        )
        specialist_keys = _nested_keys(specialist_projection)
        assert not PHYSICAL_SELECTOR_KEYS.intersection(specialist_keys)
        assert "mcp_receipt_chain" not in specialist_keys
        projected_evidence = specialist_projection["evidence_result"]["items"]
        assert projected_evidence
        assert not PHYSICAL_RESULT_SELECTOR_KEYS.intersection(
            _nested_keys(specialist_projection["evidence_result"])
        )
        assert all("candidate_id" in row for row in projected_evidence)
        projected_facts = specialist_projection["finance_result"]["items"]
        assert projected_facts
        assert all("fiscal_period" in row for row in projected_facts)

        public_lane_projection = json.dumps(
            {
                "catalog": catalog,
                "reviewed": reviewed.model_dump(mode="json"),
                "local": local.model_dump(mode="json"),
                "external": external.model_dump(mode="json"),
                "finance": finance.model_dump(mode="json"),
            },
            ensure_ascii=False,
            allow_nan=False,
        ).lower()
        assert "d:\\fin_insight_agent" not in public_lane_projection
        assert "z:\\fin_insight_agent_qualification" not in public_lane_projection
        assert "/run/fin-insight" not in public_lane_projection
        assert "cell_id" not in public_lane_projection

        for role in (
            "planner_agent",
            "specialist_agent",
            "counter_agent",
            "lead_agent",
        ):
            with pytest.raises(
                DellApprovedDataCompositionError,
                match="^model_execution_not_authorized$",
            ):
                getattr(composition.dependencies, role)({})
