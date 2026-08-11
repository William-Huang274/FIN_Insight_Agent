from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.s1_residual_gap_external_readjudication import (
    ResidualGapExternalReadjudicationError,
    load_inputs,
    readjudicate_external_capture,
)


ROOT = Path(__file__).resolve().parents[2]
EXTERNAL = ROOT / "configs/releases/fin_ia_0_1_3_s1_residual_gap_external_live_result_v1_0.json"
LOCAL_PACK = ROOT / "configs/releases/fin_ia_0_1_3_s1_six_case_local_evidence_pack_result_v1_0.json"
PLAN = ROOT / "configs/releases/fin_ia_0_1_3_s1_residual_gap_external_priority_plan_v1_0.json"
PRIVATE_ROOT = ROOT / ".codex_runtime/fin013_s1_residual_gap_external_live/r1/objects"


def _inputs() -> tuple[dict, dict, dict]:
    return load_inputs(
        external_result_path=EXTERNAL,
        local_pack_result_path=LOCAL_PACK,
        priority_plan_path=PLAN,
    )


def test_actual_live_readjudicates_to_zero_additions_and_reuses_original_pack() -> None:
    external, local_pack, plan = _inputs()
    result = readjudicate_external_capture(
        external_result=external,
        local_pack_result=local_pack,
        priority_plan=plan,
        private_object_root=PRIVATE_ROOT,
    )
    assert result["status"] == "terminal_readjudicated_zero_external_additions_original_pack_reused"
    assert result["observed_counts"] == {
        "intents_readjudicated": 12,
        "eligible_for_successor_pack_build": 0,
        "rejected_or_typed_gap": 12,
        "external_evidence_additions": 0,
        "evidence_items_before": 84,
        "evidence_items_after": 84,
        "residual_gaps_before": 126,
        "residual_gaps_after": 126,
        "network_calls": 0,
        "provider_calls": 0,
        "model_calls": 0,
        "embedding_calls": 0,
        "rerank_calls": 0,
    }
    assert result["successor_pack_decision"]["mode"] == "reuse_original_local_pack_unchanged"
    assert result["successor_pack_decision"]["resulting_pack_payload_digests"] == local_pack["pack_payload_digests"]


def test_anet_candidates_are_full_text_read_and_rejected_as_generic_shells() -> None:
    external, local_pack, plan = _inputs()
    result = readjudicate_external_capture(
        external_result=external,
        local_pack_result=local_pack,
        priority_plan=plan,
        private_object_root=PRIVATE_ROOT,
    )
    rows = [row for row in result["decisions"] if row["case_key"] == "ANET"]
    assert len(rows) == 2
    assert all(row["full_text_read"] for row in rows)
    assert all(row["decision"] == "rejected_content_or_date_gate" for row in rows)
    assert all("publication_date_unproven" in row["reason_codes"] for row in rows)
    assert all("generic_ir_page_not_disclosure" in row["reason_codes"] for row in rows)
    assert all("navigation_or_script_shell_dominates" in row["reason_codes"] for row in rows)


def test_provider_content_never_surfaces_in_readjudication_result() -> None:
    external, local_pack, plan = _inputs()
    result = readjudicate_external_capture(
        external_result=external,
        local_pack_result=local_pack,
        priority_plan=plan,
        private_object_root=PRIVATE_ROOT,
    )
    serialized = json.dumps(result, ensure_ascii=False)
    assert "passage" not in serialized
    assert "published_at_raw" not in serialized
    assert all(row["provider_snippet_used"] is False for row in result["decisions"])
    assert all(row["evidence_promoted"] is False for row in result["decisions"])


def test_external_result_mutation_fails_digest_validation() -> None:
    external, local_pack, plan = _inputs()
    mutated = deepcopy(external)
    mutated["intent_results"][0]["terminal_code"] = "forged"
    with pytest.raises(ResidualGapExternalReadjudicationError, match="result_digest_invalid"):
        readjudicate_external_capture(
            external_result=mutated,
            local_pack_result=local_pack,
            priority_plan=plan,
            private_object_root=PRIVATE_ROOT,
        )


def test_private_capture_binding_mutation_fails_closed(tmp_path: Path) -> None:
    external, local_pack, plan = _inputs()
    mutated = deepcopy(external)
    for row in mutated["intent_results"]:
        if row["case_key"] == "ANET":
            row["document"]["parser_capture"]["digest"] = "0" * 64
    body = deepcopy(mutated)
    body.pop("result_digest")
    mutated["result_digest"] = canonical_digest(body)
    with pytest.raises(Exception):
        readjudicate_external_capture(
            external_result=mutated,
            local_pack_result=local_pack,
            priority_plan=plan,
            private_object_root=PRIVATE_ROOT,
        )


def test_all_selected_gap_ids_remain_open_when_no_external_evidence_is_added() -> None:
    external, local_pack, plan = _inputs()
    result = readjudicate_external_capture(
        external_result=external,
        local_pack_result=local_pack,
        priority_plan=plan,
        private_object_root=PRIVATE_ROOT,
    )
    expected = sorted(
        gap_id
        for intent in plan["selected_intents"]
        for gap_id in intent["selected_gap_ids"]
    )
    observed = sorted(
        gap_id
        for decision in result["decisions"]
        for gap_id in decision["selected_gap_ids"]
    )
    assert observed == expected
    assert len(observed) == plan["selected_gap_count"]
