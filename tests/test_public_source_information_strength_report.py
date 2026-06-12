from __future__ import annotations

import importlib.util
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module():
    path = REPO_ROOT / "scripts" / "data_expansion" / "build_public_source_information_strength_report.py"
    spec = importlib.util.spec_from_file_location("public_source_information_strength_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def test_strength_config_covers_registry_sources_and_defers_commercial() -> None:
    module = _load_module()
    strength = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_information_strength_v0_1.yaml")
    registry = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_coverage_v0_1.yaml")

    validation = module.validate_strength_config(strength, registry)
    assessments = {row["source_id"]: row for row in strength["source_assessments"]}

    assert validation["error_count"] == 0
    assert assessments["commercial_market_data_and_consensus"]["integration_mode"] == "deferred_no_commercial_api"
    assert assessments["sec_edgar_apis"]["information_strength_tier"] == "S5_primary_authority"
    assert assessments["openfigi_api"]["integration_mode"] == "resolver_registry"


def test_matrix_keeps_context_and_resolver_sources_out_of_company_fact_authority() -> None:
    module = _load_module()
    strength = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_information_strength_v0_1.yaml")
    registry = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_coverage_v0_1.yaml")

    rows = module.build_matrix_rows(strength_config=strength, registry=registry, audit_rows=[], generated_at="2026-06-11T00:00:00+00:00")
    by_source = {row["source_id"]: row for row in rows}

    assert by_source["eia_open_data"]["runtime_surface"] == "bounded_context_only"
    assert by_source["eia_open_data"]["can_support_company_facts_by_source_strength"] is False
    assert by_source["clinicaltrials_api"]["runtime_surface"] == "gap_queue"
    assert by_source["gleif_api"]["runtime_surface"] == "source_inventory_or_resolver"
    assert by_source["company_reported_product_operating_metrics"]["runtime_surface"] == "company_product_operating_metric"


def test_summary_exposes_no_commercial_quality_ceiling() -> None:
    module = _load_module()
    strength = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_information_strength_v0_1.yaml")
    registry = _load_yaml(REPO_ROOT / "configs" / "data_sources" / "public_source_coverage_v0_1.yaml")
    validation = module.validate_strength_config(strength, registry)
    rows = module.build_matrix_rows(strength_config=strength, registry=registry, audit_rows=[], generated_at="2026-06-11T00:00:00+00:00")

    summary = module.build_summary(
        strength_config=strength,
        matrix_rows=rows,
        validation=validation,
        mapping_summary={"status": "pass_with_gaps", "universe_company_count": 603},
        adapter_summary={"status": "pass", "runtime_eligible_row_count": 1103, "bounded_evidence_eligible_row_count": 3, "exact_value_authority_row_count": 0},
        generated_at="2026-06-11T00:00:00+00:00",
        inputs={},
        outputs={},
    )

    assert summary["status"] == "pass"
    assert summary["quality_ceiling"]["overall_current_verified_ceiling"].startswith("medium_high")
    assert "commercial_market_data_and_consensus" in summary["blocked_or_deferred_sources"]
    assert summary["inventory_adapter_exact_value_authority_row_count"] == 0
