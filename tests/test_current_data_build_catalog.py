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


def test_data_build_catalog_keeps_builders_without_retired_experiment_launchers() -> None:
    steps = {step.step_id: step for step in data_build_catalog()}

    assert "retrieval_build_current_compiled_object_views" in steps
    assert {
        "retrieval_materialize_s1c_qrels",
        "retrieval_run_s1c_ranking_comparison",
        "retrieval_materialize_s1c_financial_role_eval",
        "retrieval_run_s1c_cross_encoder_role_shadow",
        "retrieval_materialize_s1c_runtime_query_atoms",
        "retrieval_run_s1c_runtime_query_atom_model_shadow",
    }.isdisjoint(steps)
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
