from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
IMPLEMENTATION = Path(
    "configs/releases/fin_ia_0_1_2_s4_t03_executable_search_"
    "controlled_successor_zero_call_implementation_v1_0.json"
)
PROJECTION = Path(
    "configs/runtime/fin_ia_0_1_2_current_program_projection_v2_40.json"
)
BACKLOG = Path("configs/releases/fin_ia_0_1_program_release_backlog_v2_0.json")
IMPLEMENTATION_NEXT = (
    "FIN-0.1.2-S4-T03-NVDA-CURRENT-SEARCH-CANARY-"
    "FRESH-ADMISSION-AUTHORITY-DECISION"
)
CURRENT_NEXT = "FIN-0.1.2-S4-T03-NVDA-CURRENT-SEARCH-CANARY-EXACT-LIVE-EXECUTION"


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


def test_implementation_bindings_are_content_addressed() -> None:
    implementation = _json(IMPLEMENTATION)
    for binding in implementation["implementation_bindings"]:
        path = Path(binding["ref"])
        assert _sha(path) == binding["sha256"]
        assert (ROOT / path).stat().st_size == binding["bytes"]


def test_zero_call_proof_closes_only_the_execution_integration_gap() -> None:
    implementation = _json(IMPLEMENTATION)
    proof = implementation["fresh_zero_call_proof"]
    assert implementation["status"] == (
        "implementation_and_fresh_zero_call_proof_pass_live_canary_not_yet_admitted"
    )
    assert proof["accepted_by_cell"] == [6, 6, 6]
    assert proof["live_source_network_calls"] == 0
    assert proof["model_provider_calls"] == [0, 0]
    assert proof["business_artifacts"] == 0
    assert implementation["root_cause_disposition"]["status"].startswith("closed_")
    assert implementation["next_action"] == IMPLEMENTATION_NEXT


def test_projection_backlog_and_latest_issue_row_agree_on_fresh_authority_next() -> None:
    projection = _json(PROJECTION)
    backlog = _json(BACKLOG)
    issue_rows = _jsonl(Path("docs/project_os/root_cause_issue_ledger.jsonl"))
    rc114 = [row for row in issue_rows if row.get("issue_id", "").startswith("RC-P36-114-")][-1]

    assert projection["current_truth"]["current_next_action"] == CURRENT_NEXT
    assert projection["current_truth"]["current_NVDA_R2"] is False
    assert projection["S4_T03_live_canary"]["issued"] is True
    assert projection["S4_T03_live_canary"]["consumed"] is False
    assert projection["S4_T03_live_canary"]["executed"] is False
    assert backlog["current_version_rebaseline"]["projection_ref"] == PROJECTION.as_posix()
    assert backlog["next_action"]["item_id"] == CURRENT_NEXT
    assert rc114["status"] == "closed"
    assert rc114["full_chain_blocker"] is False
