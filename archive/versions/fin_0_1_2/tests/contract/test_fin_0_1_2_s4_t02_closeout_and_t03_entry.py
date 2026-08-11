from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION_REF = Path(
    "configs/releases/fin_ia_0_1_2_s4_t02_three_case_retrieval_evidence_deterministic_readiness_zero_call_implementation_v1_0.json"
)
PROJECTION_REF = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_37.json"
)
BACKLOG_REF = Path("configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json")
NEXT = (
    "FIN-0.1.2-S4-T03-NVDA-BOUNDED-AGENTIC-SEARCH-"
    "CURRENT-CANARY-AUTHORITY-DECISION"
)


def _json(path: Path) -> dict[str, Any]:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def _sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (ROOT / path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_implementation_bindings_are_content_addressed_and_zero_call() -> None:
    implementation = _json(IMPLEMENTATION_REF)
    for binding in implementation["implementation_bindings"]:
        path = Path(binding["ref"])
        assert _sha(path) == binding["sha256"]
        assert (ROOT / path).stat().st_size == binding["bytes"]

    assert set(implementation["observed_counts"].values()) == {0}
    assert implementation["contract"]["T03_authorized"] is False
    assert implementation["next_action"] == NEXT


def test_projection_closes_t02_without_starting_or_authorizing_t03() -> None:
    projection = _json(PROJECTION_REF)
    closeout = projection["S4_T02_closeout"]

    assert closeout["implementation_sha256"] == _sha(IMPLEMENTATION_REF)
    assert closeout["accepted_rejected_citations_promoted_by_case"] == {
        "DELL": [2, 8, 2, 0],
        "MU": [13, 1, 13, 0],
        "NVDA": [0, 0, 0, 0],
    }
    assert closeout["historical_Dell_and_MU_rows_are_current_Evidence"] is False
    assert closeout["NVDA_current_search_required"] is True
    assert closeout["T03_authorized"] is False
    assert projection["S4_T03_entry"]["admission_issued"] is False
    assert projection["current_truth"]["current_next_action"] == NEXT


def test_backlog_points_to_exact_current_projection_and_next_authority_decision() -> None:
    backlog = _json(BACKLOG_REF)
    next_action = backlog["next_action"]

    assert backlog["current_version_rebaseline"]["projection_ref"] == str(
        PROJECTION_REF
    ).replace("\\", "/")
    assert next_action["current_projection_sha256"] == _sha(PROJECTION_REF)
    assert next_action["item_id"] == NEXT
    assert next_action["S4_T02_completed"] is True
    assert next_action["S4_T02_T03_authorized"] is False
    assert next_action["S4_T02_historical_fixtures_are_current_Evidence"] is False
    assert next_action["S4_T02_pre_T03_issue_status"].startswith("closed_")
    assert "S4_T02_pre_T03_open_issue_id" not in next_action
    assert "RC_P36_113_default_runtime_resource_registry_drift_before_S4_T03" not in next_action["still_blocks"]


def test_project_os_appends_t02_pass_and_rc113_closure() -> None:
    capabilities = _jsonl(Path("docs/project_os/capability_status_ledger.jsonl"))
    issues = _jsonl(Path("docs/project_os/root_cause_issue_ledger.jsonl"))
    patterns = _jsonl(Path("docs/project_os/external_pattern_registry.jsonl"))

    assert capabilities[-1]["capability_id"] == (
        "fin_0_1_2_S4_T02_three_case_retrieval_evidence_deterministic_readiness"
    )
    assert capabilities[-1]["current_next"] == NEXT
    assert issues[-1]["issue_id"].startswith("RC-P36-113-")
    assert issues[-1]["status"].startswith("closed_")
    assert patterns[-1]["pattern_id"] == (
        "historical_source_pack_readiness_must_not_be_reclassified_as_current_evidence"
    )


def test_current_docs_do_not_claim_live_search_or_current_evidence() -> None:
    paths = [
        Path(
            "docs/architecture/repository/FIN_0_1_2_S4_EVIDENCE_TO_WORKBENCH_STAGE_PLAN_20260804.zh-CN.md"
        ),
        Path(
            "docs/worklog/product_strategy/587_fin_0_1_2_s4_t02_retrieval_evidence_deterministic_readiness.md"
        ),
        Path("docs/project_os/current_context_pack.zh-CN.md"),
    ]
    texts = [(ROOT / path).read_text(encoding="utf-8") for path in paths]

    assert all(NEXT in text for text in texts)
    assert "不意味着已经执行 RAG/Agentic Search" in texts[0]
    assert "readiness 通过不等于 RAG/Agentic Search 已经运行" in texts[1]
    assert "promoted Evidence 仍为 `0/3`" not in texts[0]
