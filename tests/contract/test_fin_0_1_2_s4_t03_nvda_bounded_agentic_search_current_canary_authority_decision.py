from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from apps.workbench.backend.application.fin_0_1_2_s4_retrieval_evidence_readiness import (
    load_current_fin_0_1_2_s4_t02_readiness,
)


DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t03_nvda_bounded_agentic_search_"
    "current_canary_authority_decision_v1_0.json"
)
NEXT = (
    "FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-"
    "CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
ROUTE_IDS = {
    "official_issuer_disclosure_metadata_route",
    "local_relationship_graph_metadata_route",
    "public_source_index_metadata_route",
    "local_exact_value_sql_metadata_route",
}


def _json(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _function_node(path: Path, *, class_name: str | None, function_name: str) -> ast.FunctionDef:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    scope: list[ast.stmt] = tree.body
    if class_name is not None:
        owner = next(
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        scope = owner.body
    return next(
        node
        for node in scope
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    )


def test_decision_evidence_bindings_are_content_addressed() -> None:
    decision = _json(DECISION_REF)
    for binding in decision["evidence_bindings"]:
        path = Path(binding["ref"])
        assert _sha(path) == binding["sha256"]
        assert (ROOT / path).stat().st_size == binding["bytes"]


def test_current_nvda_requests_remain_unadmitted_and_have_no_current_evidence() -> None:
    decision = _json(DECISION_REF)
    current = load_current_fin_0_1_2_s4_t02_readiness("NVDA")
    expected = decision["current_NVDA_readiness"]

    assert [row.request_digest for row in current.evidence_requests] == expected[
        "request_digests"
    ]
    assert [row.execution_admission for row in current.evidence_requests] == [
        "not_admitted",
        "not_admitted",
        "not_admitted",
    ]
    assert (
        current.receipt.accepted_candidate_count,
        current.receipt.rejected_candidate_count,
        current.receipt.citation_count,
        current.receipt.promoted_evidence_count,
    ) == (0, 0, 0, 0)
    assert set(current.receipt.typed_gap_codes) == set(expected["typed_gap_codes"])


def test_metadata_route_ids_have_no_python_executor_binding() -> None:
    executable_sources = [
        path
        for path in ROOT.rglob("*.py")
        if "tests" not in path.parts and ".git" not in path.parts
    ]
    occurrences = {
        route_id: [
            path.relative_to(ROOT).as_posix()
            for path in executable_sources
            if route_id in path.read_text(encoding="utf-8", errors="ignore")
        ]
        for route_id in ROUTE_IDS
    }
    assert occurrences == {route_id: [] for route_id in ROUTE_IDS}


def test_local_retrieval_skeleton_does_not_invoke_adapter_recall() -> None:
    node = _function_node(
        Path("src/sec_agent/canonical_runtime/local_retrieval_skeleton.py"),
        class_name="NonExecutingLocalRetrievalSkeleton",
        function_name="project_from_supplied_candidates",
    )
    called_attributes = {
        call.func.attr
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    }
    assert "recall" not in called_attributes


def test_orchestrator_default_retrieval_path_is_a_state_stub() -> None:
    node = _function_node(
        Path("src/sec_agent/langgraph_orchestrator.py"),
        class_name=None,
        function_name="_node_execute_retrieval_routes",
    )
    constants = {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    }
    assert "state_stub" in constants
    assert "injected" in constants


def test_web_snapshot_wrapper_is_not_source_fetch_or_capture_proof() -> None:
    node = _function_node(
        Path("src/sec_agent/mcp_tool_registry.py"),
        class_name=None,
        function_name="_invoke_web_evidence_snapshot",
    )
    constants = {
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, (str, bool))
    }
    called_names = {
        call.func.id
        for call in ast.walk(node)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
    }
    assert "live_web_snapshot_context_only_no_sec_or_product_fact_overwrite" in constants
    assert True in constants
    assert not {"urlopen", "request", "get", "post"}.intersection(called_names)


def test_canary_fails_closed_and_selects_one_in_stage_zero_call_successor() -> None:
    decision = _json(DECISION_REF)
    assert decision["decision"] == {
        "authority_scope": "pass",
        "canary_execution_authority": "fail_closed",
        "canary_admission_issuance": "not_authorized",
        "root_cause_class": (
            "project_owned_T03_execution_integration_gap_not_model_provider_or_"
            "external_data_failure"
        ),
        "issue_id": (
            "RC-P36-114-fin-0-1-2-s4-t03-metadata-route-to-executable-search-"
            "and-source-capture-binding-gap"
        ),
    }
    assert decision["next_action"] == NEXT
    assert set(decision["observed_counts"].values()) == {0}
    successor = decision["selected_controlled_successor_contract"]
    assert successor["implementation_authorized_by_this_decision"] is False
    assert successor["prospective_canary_ceiling"]["model_calls"] == 0
    assert successor["prospective_canary_ceiling"]["provider_calls"] == 0
    assert successor["prospective_canary_ceiling"]["source_network_calls"] == 2
    assert successor["T04_consumption_boundary"] == {
        "current_evidence_candidate_may_be_created_after_gate": True,
        "writer_citable_in_T03": False,
        "domain_judgment_eligible_in_T03": False,
        "business_artifact_created_in_T03": False,
    }
