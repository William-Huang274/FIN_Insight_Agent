from __future__ import annotations

from pathlib import Path

from scripts.data_retrieval.build_s2_company_financial_fact_mart import (
    CURRENT_BOUND_RESULT,
    DEFAULT_RESULT_OUTPUT,
)
from sec_agent.workbench.data_build import data_build_catalog


ROOT = Path(__file__).resolve().parents[1]


def test_every_admitted_data_build_script_and_default_config_exists() -> None:
    steps = data_build_catalog()
    assert steps
    assert len({step.step_id for step in steps}) == len(steps)

    missing: list[str] = []
    for step in steps:
        if not (ROOT / step.script).is_file():
            missing.append(f"script:{step.step_id}:{step.script}")
        for parameter in step.parameters:
            default = str(parameter.default or "")
            if default.startswith("configs/") and not (ROOT / default).is_file():
                missing.append(f"config:{step.step_id}:{default}")
    assert missing == []


def test_data_build_catalog_exposes_complete_8k_path_without_unbuilt_object_index() -> None:
    step_ids = {step.step_id for step in data_build_catalog()}

    assert {
        "sec_download_8k_earnings",
        "sec_build_8k_manifest",
        "sec_build_8k_chunks",
        "sec_build_evidence_store",
        "sec_build_bm25_index",
    }.issubset(step_ids)
    assert "sec_build_object_bm25_index" not in step_ids


def test_data_build_catalog_exposes_s1c_as_one_controlled_comparison_chain() -> None:
    steps = {step.step_id: step for step in data_build_catalog()}

    assert {
        "retrieval_build_current_compiled_object_views",
        "retrieval_materialize_s1c_qrels",
        "retrieval_run_s1c_ranking_comparison",
        "retrieval_materialize_s1c_financial_role_eval",
        "retrieval_run_s1c_cross_encoder_role_shadow",
        "retrieval_materialize_s1c_runtime_query_atoms",
        "retrieval_run_s1c_runtime_query_atom_model_shadow",
    }.issubset(steps)
    comparison = steps["retrieval_run_s1c_ranking_comparison"]
    model = next(row for row in comparison.parameters if row.name == "model")
    assert model.required is True
    assert comparison.timeout_hint_s == 1800
    shadow = steps["retrieval_run_s1c_cross_encoder_role_shadow"]
    assert next(
        row for row in shadow.parameters if row.name == "bge_model"
    ).required is True
    assert next(
        row for row in shadow.parameters if row.name == "cross_encoder_model"
    ).required is True
    assert shadow.timeout_hint_s == 1800
    atom_shadow = steps["retrieval_run_s1c_runtime_query_atom_model_shadow"]
    assert atom_shadow.timeout_hint_s == 7200
    assert {
        row.name for row in atom_shadow.parameters
    } == {"policy", "cache_root", "full_output_root", "summary_output"}
    fact_mart = steps["financial_facts_build_s2_company_mart"]
    assert fact_mart.timeout_hint_s == 900
    assert {row.name for row in fact_mart.parameters} == {
        "policy",
        "sqlite",
        "output",
    }
    fact_mart_output = next(
        row for row in fact_mart.parameters if row.name == "output"
    )
    assert fact_mart_output.default == DEFAULT_RESULT_OUTPUT
    assert str(fact_mart_output.default).startswith("data/workbench_private/")
    assert (ROOT / str(fact_mart_output.default)).resolve() != CURRENT_BOUND_RESULT
