from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
for value in (ROOT, ROOT / "src"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from sec_agent.retrieval_evidence_usefulness_program import canonical_digest  # noqa: E402
from sec_agent.s3_workpaper_writer_content_program import (  # noqa: E402
    S3WorkpaperWriterContentError,
    compile_s3_workpaper_writer_content_program,
    load_s3_workpaper_writer_content_policy,
    validate_s3_workpaper_writer_content_program,
)


POLICY_PATH = ROOT / "configs/runtime/fin_ia_0_1_3_repair_closeout_s3_workpaper_writer_content_policy_v1_0.json"
CLAIM_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_02_claim_and_observable_wwc_v1_0.json"
SYNTHESIS_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_03_cross_cell_synthesis_v1_0.json"
DECISION_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_workpaper_writer_decision_ready_content_v1_0.json"
ACTIVE_PATH = ROOT / "configs/releases/fin_ia_0_1_3_repair_closeout_s3_04_active_test_suite_successor_v1_0.json"


def _compile() -> tuple[dict, dict]:
    policy = load_s3_workpaper_writer_content_policy(POLICY_PATH)
    claim = json.loads(CLAIM_PATH.read_text(encoding="utf-8"))
    synthesis = json.loads(SYNTHESIS_PATH.read_text(encoding="utf-8"))
    return compile_s3_workpaper_writer_content_program(policy=policy, claim_decision=claim, synthesis_decision=synthesis), policy


def _reseal(program: dict, case_index: int) -> None:
    workpaper = program["case_workpapers"][case_index]
    workpaper["workpaper_digest"] = canonical_digest({key: value for key, value in workpaper.items() if key != "workpaper_digest"})
    program["program_digest"] = canonical_digest({key: value for key, value in program.items() if key != "program_digest"})


def test_three_workpapers_answer_five_decision_questions_across_eight_lenses() -> None:
    program, policy = _compile()
    validate_s3_workpaper_writer_content_program(program, policy=policy)
    assert program["observed_counts"] == {
        "case_workpapers": 3, "content_lenses": 24, "bounded_judgment_lenses": 21,
        "explicit_research_gap_lenses": 3, "natural_product_candidates": 0,
        "fixture_mixed_engineering_previews": 3, "planned_cells_rendered_as_findings": 0,
        "writer_raw_source_rows": 0, "model_calls": 0, "provider_calls": 0,
        "network_calls": 0, "source_calls": 0, "business_runs": 0,
    }
    for workpaper in program["case_workpapers"]:
        assert len(workpaper["sections"]) == 8
        assert all(set(section["answers"]) == set(policy["required_answer_fields"]) for section in workpaper["sections"])
        assert workpaper["content_precheck"]["lead_dependency_conflict_gap_bound"] is True


def test_content_is_company_specific_numeric_exact_and_not_old_generic_projection() -> None:
    program, policy = _compile()
    text = json.dumps(program, ensure_ascii=False)
    assert all(fragment not in text for fragment in policy["forbidden_generic_fragments"])
    for workpaper in program["case_workpapers"]:
        case_text = json.dumps(workpaper["sections"], ensure_ascii=False)
        assert workpaper["ticker"] in case_text
        assert "跨判断影响" in case_text
        for section in workpaper["sections"]:
            for fact in section["numeric_facts"]:
                assert fact["normalized_value"] in fact["rendered"].replace(",", "")
                assert fact["claim_boundary"] in fact["rendered"]


def test_uncovered_lenses_are_explicit_gaps_not_fabricated_findings() -> None:
    program, _ = _compile()
    gaps = [section for row in program["case_workpapers"] for section in row["sections"] if section["coverage_status"] == "explicit_research_gap"]
    assert {(row["lens_id"], row["authority"]) for row in gaps} == {
        ("capital_price_in_and_valuation_boundary", "planned_no_claim"),
        ("competition_and_market_position", "planned_no_claim"),
    }
    assert len(gaps) == 3
    assert all(not row["claim_card_ids"] and not row["numeric_facts"] and row["planned_cell_ids"] for row in gaps)


def test_fixture_mixed_preview_cannot_be_promoted_to_product_delivery() -> None:
    program, policy = _compile()
    assert all(row["workpaper_authority"] == "fixture_mixed_engineering_only" for row in program["case_workpapers"])
    assert all(row["display_ready"] is False and row["product_candidate"] is False for row in program["case_workpapers"])
    mutated = deepcopy(program)
    mutated["case_workpapers"][0]["display_ready"] = True
    mutated["case_workpapers"][0]["product_candidate"] = True
    _reseal(mutated, 0)
    with pytest.raises(S3WorkpaperWriterContentError, match="fixture_promotion_forbidden"):
        validate_s3_workpaper_writer_content_program(mutated, policy=policy)


def test_cross_case_claim_generic_phrase_numeric_and_planned_promotion_mutations_fail_closed() -> None:
    program, policy = _compile()
    mutated = deepcopy(program)
    mutated["case_workpapers"][0]["sections"][0]["claim_card_ids"][0] = mutated["case_workpapers"][1]["claim_card_ids"][0]
    _reseal(mutated, 0)
    with pytest.raises(S3WorkpaperWriterContentError, match="claim_binding_invalid"):
        validate_s3_workpaper_writer_content_program(mutated, policy=policy)

    mutated = deepcopy(program)
    mutated["case_workpapers"][0]["sections"][0]["answers"]["conclusion"] = "证据方向支持当前单元判断"
    _reseal(mutated, 0)
    with pytest.raises(S3WorkpaperWriterContentError, match="generic_content_forbidden"):
        validate_s3_workpaper_writer_content_program(mutated, policy=policy)

    mutated = deepcopy(program)
    target = next(section for section in mutated["case_workpapers"][0]["sections"] if section["numeric_facts"])
    target["numeric_facts"][0]["rendered"] = "USD 999"
    _reseal(mutated, 0)
    with pytest.raises(S3WorkpaperWriterContentError, match="numeric_rendering_invalid"):
        validate_s3_workpaper_writer_content_program(mutated, policy=policy)

    mutated = deepcopy(program)
    target = next(section for section in mutated["case_workpapers"][0]["sections"] if section["coverage_status"] == "explicit_research_gap")
    target["claim_card_ids"] = [mutated["case_workpapers"][0]["claim_card_ids"][0]]
    _reseal(mutated, 0)
    with pytest.raises(S3WorkpaperWriterContentError, match="planned_cell_promotion_invalid"):
        validate_s3_workpaper_writer_content_program(mutated, policy=policy)


def test_writer_packet_is_no_source_and_not_yet_provider_activated() -> None:
    program, _ = _compile()
    assert program["stage_boundary"]["model_visible_writer_input_activated"] is False
    assert program["stage_boundary"]["additional_paid_canary_required_now"] is False
    for row in program["case_workpapers"]:
        packet = row["writer_no_source_packet"]
        assert packet["source_access_allowed"] is False
        assert packet["raw_retrieval_rows"] == []
        assert packet["authority"] == "fixture_mixed_engineering_only"
        assert packet["section_material_ref"] == "case_workpaper.sections"
        assert packet["section_digests"] == [canonical_digest(section) for section in row["sections"]]


def test_materialized_decision_and_active_suite_are_digest_bound_and_honest() -> None:
    decision = json.loads(DECISION_PATH.read_text(encoding="utf-8"))
    active = json.loads(ACTIVE_PATH.read_text(encoding="utf-8"))
    assert decision["record_digest"] == canonical_digest({key: value for key, value in decision.items() if key != "record_digest"})
    assert active["decision_sha256"] == hashlib.sha256(DECISION_PATH.read_bytes()).hexdigest()
    assert active["suite_digest"] == canonical_digest({key: value for key, value in active.items() if key != "suite_digest"})
    assert active["observed_result"] == "226 passed / 1 historical assertion deselected"
    assert decision["acceptance"]["S3_04"] == "engineering_pass"
    assert decision["acceptance"]["all_natural_workpapers"] == 0
    assert decision["stage_boundary"]["writer_runtime_natural_output"] is False
    assert decision["stage_boundary"]["product_delivery"] is False
