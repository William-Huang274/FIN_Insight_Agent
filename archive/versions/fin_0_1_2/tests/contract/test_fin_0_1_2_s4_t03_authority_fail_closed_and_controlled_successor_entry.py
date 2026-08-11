from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.project_os_preflight import run_project_os_preflight


DECISION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t03_nvda_bounded_agentic_search_"
    "current_canary_authority_decision_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_38.json"
)
BACKLOG_REF = Path("configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json")
NEXT = (
    "FIN-0.1.2-S4-T03-NVDA-EXECUTABLE-SEARCH-REQUEST-ROUTE-ADAPTER-"
    "CAPTURE-FIRST-CONTROLLED-SUCCESSOR-MINIMUM-ZERO-CALL-IMPLEMENTATION"
)
CANARY_SCOPE = "FIN-0.1.2-S4-T03-NVDA-CURRENT-AGENTIC-SEARCH-CANARY"


def _json(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def test_projection_records_fail_closed_authority_without_starting_successor() -> None:
    projection = _json(PROJECTION_REF)
    decision = projection["S4_T03_authority_decision"]

    assert decision["decision_sha256"] == _sha(DECISION_REF)
    assert decision["authority_scope"] == "pass"
    assert decision["canary_execution_authority"] == "fail_closed"
    assert decision["admission_issued"] is False
    assert decision["execution_authorized"] is False
    assert projection["execution_policy"][
        "S4_T03_controlled_successor_implementation_authorized"
    ] is False
    assert projection["current_truth"]["current_next_action"] == NEXT
    assert projection["current_truth"]["current_NVDA_R2"] is False


def test_historical_t02_closeout_contract_remains_byte_identical() -> None:
    implementation = _json(
        Path(
            "configs/releases/fin_ia_0_1_2_s4_t02_three_case_retrieval_"
            "evidence_deterministic_readiness_zero_call_implementation_v1_0.json"
        )
    )
    binding = next(
        row
        for row in implementation["implementation_bindings"]
        if row["ref"]
        == "tests/contract/test_fin_0_1_2_s4_t02_closeout_and_t03_entry.py"
    )
    assert _sha(Path(binding["ref"])) == binding["sha256"]


def test_backlog_points_to_exact_projection_and_one_controlled_successor() -> None:
    backlog = _json(BACKLOG_REF)
    next_action = backlog["next_action"]

    assert backlog["current_version_rebaseline"]["projection_ref"] == str(
        PROJECTION_REF
    ).replace("\\", "/")
    assert next_action["current_projection_sha256"] == _sha(PROJECTION_REF)
    assert next_action["item_id"] == NEXT
    assert next_action["S4_T03_authority_decision_completed"] is True
    assert next_action["S4_T03_authority_decision_sha256"] == _sha(DECISION_REF)
    assert next_action["S4_T03_canary_execution_authority"] == "fail_closed"
    assert next_action["S4_T03_canary_admission_issued"] is False
    assert next_action["S4_T03_controlled_successor_authorized"] is False
    assert any("RC_P36_114" in item for item in next_action["still_blocks"])


def test_project_os_records_capability_boundary_issue_and_reusable_pattern() -> None:
    capabilities = _jsonl(Path("docs/project_os/capability_status_ledger.jsonl"))
    issues = _jsonl(Path("docs/project_os/root_cause_issue_ledger.jsonl"))
    patterns = _jsonl(Path("docs/project_os/external_pattern_registry.jsonl"))

    assert capabilities[-1]["capability_id"] == (
        "fin_0_1_2_S4_T03_NVDA_bounded_agentic_search_current_canary_authority"
    )
    assert capabilities[-1]["current_next"] == NEXT
    assert issues[-1]["issue_id"].startswith("RC-P36-114-")
    assert issues[-1]["owned_by_project"] is True
    assert issues[-1]["model_or_provider_fault_established"] is False
    assert issues[-1]["status"] == "open"
    assert issues[-1]["status_detail"].startswith("T03_execution_integration_gap")
    assert issues[-1]["blocking_run_scopes"] == ["*"]
    assert issues[-1]["allowed_run_scopes"][0] == NEXT
    assert patterns[-1]["pattern_id"] == (
        "metadata_route_contract_must_bind_to_executable_adapter_and_capture_"
        "before_live_authority"
    )


def test_project_os_allows_only_controlled_successor_and_blocks_canary() -> None:
    successor = run_project_os_preflight(ROOT, run_scope=NEXT)
    canary = run_project_os_preflight(ROOT, run_scope=CANARY_SCOPE)

    assert successor["status"] == "pass"
    assert successor["open_full_chain_blockers"] == []
    assert canary["status"] == "blocked"
    assert canary["open_full_chain_blockers"][-1]["issue_id"].startswith(
        "RC-P36-114-"
    )


def test_current_source_documents_publish_the_same_honest_boundary() -> None:
    paths = [
        Path(
            "docs/architecture/repository/"
            "FIN_0_1_2_S4_EVIDENCE_TO_WORKBENCH_STAGE_PLAN_20260804.zh-CN.md"
        ),
        Path(
            "docs/product/"
            "FIN_0_1_2_CANONICAL_S0_TO_S5_PRODUCT_PROGRESSION_PLAN_20260802.zh-CN.md"
        ),
        Path(
            "docs/product/"
            "FIN_0_1_1_0_1_2_PRD_CAPABILITY_ALIGNMENT_AND_S0_TO_S5_REBASELINE_"
            "20260804.zh-CN.md"
        ),
        Path("docs/project_os/current_context_pack.zh-CN.md"),
        Path(
            "docs/worklog/product_strategy/"
            "588_fin_0_1_2_s4_t03_agentic_search_canary_authority_fail_closed.md"
        ),
    ]
    texts = [(ROOT / path).read_text(encoding="utf-8") for path in paths]

    assert all(NEXT in text for text in texts)
    assert all("RC-P36-114" in text for text in texts)
    assert "不是 DeepSeek、Provider 或外部数据" in texts[0]
    assert "不能把 state stub" in texts[2]
    assert "产品能力增量因此诚实记为 0" in texts[4]


def test_no_canary_or_successor_execution_artifact_was_created() -> None:
    decision = _json(DECISION_REF)
    assert set(decision["observed_counts"].values()) == {0}
    assert decision["authority"]["controlled_successor_implementation_executed"] is False
    assert decision["authority"]["canary_admission_issued"] is False
    assert decision["authority"]["canary_execution_authorized"] is False
    assert not list(
        (ROOT / "configs/releases").glob(
            "fin_ia_0_1_2_s4_t03_nvda_executable_search_request_route_adapter_*"
        )
    )
