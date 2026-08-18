from __future__ import annotations

import json
from pathlib import Path

from retrieval.evaluation_assets import (
    EvaluationInput,
    load_qualification_preregistration,
)
from retrieval.qualification_runtime import load_qualification_runtime_bundle


ROOT = Path(__file__).resolve().parents[1]
PREREG = ROOT / "eval_sets/fin_0_1_3_s1/qualification_preregistration_v1_0.json"
OVERLAY = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_overlay_v1_0.json"
)
RESULT = (
    ROOT
    / "configs/retrieval/fin_ia_0_1_3_s1_vs5_qualification_runtime_inputs_result_v1_0.json"
)


def _bundle():
    return load_qualification_runtime_bundle(
        repo_root=ROOT,
        preregistration=load_qualification_preregistration(PREREG),
        overlay_path=OVERLAY,
    )


def test_vs5_runtime_overlay_covers_all_new_cases_without_base_case_replacement() -> None:
    bundle = _bundle()
    assert set(bundle.kernel.cases) == {
        "DELL",
        "MU",
        "NVDA",
        "COST",
        "JPM",
        "CAT",
        "NVO",
        "SHEL",
        "0700.HK",
    }
    assert {row for row in bundle.kernel.industry_packs} >= {
        "membership_retail",
        "diversified_banking",
        "industrial_machinery",
        "biopharma",
        "integrated_energy",
        "internet_platform",
    }
    assert all(
        "ANNUAL_REPORT" in slot.source_types for slot in bundle.kernel.slots
    )


def test_vs5_runtime_inputs_are_split_safe_label_free_and_complete() -> None:
    bundle = _bundle()
    assert {key: len(value) for key, value in bundle.inputs_by_split.items()} == {
        "valid_temporal": 5,
        "test_frozen": 10,
        "holdout_heterogeneous": 15,
    }
    rows = [row for values in bundle.inputs_by_split.values() for row in values]
    assert len(rows) == 30
    assert len({row.example_id for row in rows}) == 30
    assert all(row.runtime_input["authority"]["references_visible_to_runtime"] is False for row in rows)
    assert all(row.runtime_input["authority"]["candidate_is_not_evidence"] is True for row in rows)
    assert all(row.runtime_input["authority"]["numeric_fact_authority"] is False for row in rows)
    serialized = json.dumps(
        [row.model_dump(mode="json") for row in rows], ensure_ascii=False
    ).casefold()
    for forbidden in (
        '"gold"',
        '"label"',
        '"expected_outcome"',
        '"hard_negative"',
        '"target_source_record_ids"',
    ):
        assert forbidden not in serialized


def test_materialized_vs5_runtime_input_files_validate_against_contract() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    assert result["summary"] == {
        "candidate_is_not_evidence": True,
        "case_count": 6,
        "example_count": 30,
        "generation_model_calls": 0,
        "learned_vector_calls": 0,
        "network_calls": 0,
        "numeric_fact_authority": False,
        "references_present_in_runtime_inputs": False,
        "split_count": 3,
    }
    for binding in result["outputs"]:
        path = ROOT / binding["ref"]
        rows = [
            EvaluationInput.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert len(rows) == binding["example_count"]
        assert all(row.split == binding["split"] for row in rows)


def test_vs5_learned_runtime_is_cuda_fp16_without_cpu_fallback() -> None:
    overlay = json.loads(OVERLAY.read_text(encoding="utf-8"))
    authority = overlay["authority"]
    assert authority["learned_vector_device"] == "cuda"
    assert authority["learned_vector_precision"] == "fp16"
    assert authority["cpu_vector_fallback_allowed"] is False
    assert set(overlay["token_budget_basis"]) == {
        "bge_embedding",
        "qwen_embedding",
        "bge_reranker",
        "qwen_reranker",
    }
