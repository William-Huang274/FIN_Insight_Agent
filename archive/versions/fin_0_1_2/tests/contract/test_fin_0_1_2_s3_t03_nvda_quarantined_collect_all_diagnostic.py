from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from scripts.releases.run_fin_ia_0_1_2_s3_t03_nvda_quarantined_collect_all_diagnostic import (
    AUTHORITY,
    EXPECTED_CAPTURE_DIGESTS,
    SOURCE_RUNTIME,
    _request_from_messages,
    _source_interactions,
    _tree_digest,
    execute,
    preflight,
    repair_research_lead,
)
from test_fin_0_1_2_s3_t02_production_runtime_integration import (
    _CurrentS3ProductionFake,
)


def _credential_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_GATEWAY_TRANSPORT_RETRIES", "0")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fixture-not-a-real-secret")


def test_authority_is_diagnostic_only_and_source_captures_are_exact() -> None:
    authority = json.loads(AUTHORITY.read_text(encoding="utf-8"))
    assert authority["status"] == (
        "authorized_diagnostic_only_non_promotable_downstream_continuation"
    )
    assert authority["hard_limits"]["maximum_new_live_calls"] == 2
    assert authority["hard_limits"]["retry_budget"] == 0
    assert authority["acceptance_boundary"] == {
        "diagnostic_only": True,
        "S3_T03_pass_eligible": False,
        "current_NVDA_R2_eligible": False,
        "paired_assessment_eligible": False,
        "owner_acceptance_eligible": False,
        "S3_T04_entry_eligible": False,
        "release_or_production_eligible": False,
    }
    source = _source_interactions()
    assert len(source) == 7
    assert tuple(
        row["capture_digest"]
        for row in sorted(source.values(), key=lambda item: item["capture_sequence"])
    ) == EXPECTED_CAPTURE_DIGESTS


def test_lead_repair_swaps_adjacent_claim_semantics_and_materializes_truth() -> None:
    source = _source_interactions()["research_lead"]
    request = _request_from_messages(source["messages"])
    repaired_text, findings = repair_research_lead(
        request=request,
        assistant_output_text=source["assistant_output_text"],
    )
    repaired = json.loads(repaired_text)
    assert any(
        row["repair_code"] == "adjacent_same_cell_claim_alias_semantic_swap"
        for row in findings
    )
    support_truth = {"C001": 0, "C002": 0, "C003": 3, "C004": 0}
    for row in repaired["conflict_adjudications"]:
        aliases = row["involved_claim_ids"]
        supported = sum(support_truth[alias] > 0 for alias in aliases)
        expected = (
            "no_facts_present"
            if supported == 0
            else "facts_present"
            if supported == len(aliases)
            else "mixed_fact_presence"
        )
        assert row["fact_presence_summary"] == expected
    assert repaired["cross_cell_dependencies"][0]["claim_ids"] == ["C003"]
    assert repaired["remaining_gap_atoms"][1]["claim_ids"] == ["C002"]


def test_zero_call_preflight_reaches_writer_without_mutating_formal_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _credential_environment(monkeypatch)
    before = _tree_digest(SOURCE_RUNTIME)
    result = preflight(tmp_path / "diagnostic-preflight")
    assert result["status"] == (
        "pass_zero_call_replay_lead_repair_reaches_memo_writer"
    )
    assert result["source_replay_count"] == 7
    assert result["next_live_stage"] == "memo_writer"
    assert result["model_provider_network_calls"] == [0, 0, 0]
    assert _tree_digest(SOURCE_RUNTIME) == before


def test_fake_downstream_continuation_materializes_nine_quarantined_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _credential_environment(monkeypatch)
    before = _tree_digest(SOURCE_RUNTIME)
    fake = _CurrentS3ProductionFake(safe_lead=True)
    result = execute(
        tmp_path / "diagnostic-execute",
        live_completion=fake,
    )
    assert result["status"] == "diagnostic_terminal_succeeded_quarantined"
    assert result["quarantined_artifact_count"] == 9
    assert result["business_artifact_promotions"] == 0
    assert result["paired_assessment_performed"] is False
    assert result["owner_acceptance_performed"] is False
    summary = result["cache_and_repairs"]
    assert summary["seed_replay_count"] == 7
    assert summary["new_live_call_count"] == 2
    assert [row["stage"] for row in summary["live_interactions"]] == [
        "memo_writer",
        "verifier",
    ]
    assert len(fake.calls) == 2
    assert _tree_digest(SOURCE_RUNTIME) == before
