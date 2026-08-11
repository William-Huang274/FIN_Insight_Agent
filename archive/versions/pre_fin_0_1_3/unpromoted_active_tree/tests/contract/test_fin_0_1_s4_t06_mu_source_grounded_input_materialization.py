from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from pydantic import ValidationError


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests" / "contract"))

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402
from sec_agent.s4_case_runtime import (  # noqa: E402
    S4SourceGroundedInputPack,
    load_s4_case_runtime_binding,
    load_s4_source_grounded_input_pack,
)
from apps.workbench.backend.application.bounded_agent_executor import (  # noqa: E402
    S3ThreeCellBoundedAgentAdmission,
    S3ThreeCellBoundedAgentExecutor,
    build_s4_source_grounded_bounded_agent_input,
)
from test_fin_0_1_s4_t03_case_runtime_injection_and_leakage_preflight import (  # noqa: E402
    _S4ZeroCallNodeExecutor,
)


SOURCE_PACK = (
    ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_s4_t06_mu_source_grounded_input_pack_v1_0.json"
)
GENERATOR = (
    ROOT
    / "scripts"
    / "releases"
    / "prepare_fin_ia_0_1_s4_t06_mu_source_grounded_input_pack.py"
)


def _load() -> dict:
    return json.loads(SOURCE_PACK.read_text(encoding="utf-8"))


def _generator_module():
    spec = importlib.util.spec_from_file_location(
        "fin_ia_s4_t06_mu_source_pack_generator",
        GENERATOR,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _redigest(payload: dict) -> dict:
    result = deepcopy(payload)
    result.pop("source_pack_digest", None)
    result["source_pack_digest"] = canonical_digest(result)
    return result


def test_generator_is_deterministic_and_saved_pack_is_contract_valid() -> None:
    saved = _load()
    generated = _generator_module().build_source_pack()
    assert generated == saved
    assert S4SourceGroundedInputPack.model_validate(
        saved
    ).model_dump(mode="json") == saved
    assert hashlib.sha256(SOURCE_PACK.read_bytes()).hexdigest()


def test_shared_loader_accepts_mu_without_weakening_dell() -> None:
    mu = load_s4_source_grounded_input_pack(ROOT, "MU")
    dell = load_s4_source_grounded_input_pack(ROOT, "DELL")
    assert mu.case_ticker == "MU"
    assert mu.issuer_identifier == "CIK0000723125"
    assert len(mu.route_execution_receipts) == 8
    assert all(
        row["route_id"].startswith("p34_route::mu_")
        for row in mu.route_execution_receipts
    )
    assert dell.case_ticker == "DELL"
    assert dell.issuer_identifier == "CIK0001571996"
    assert len(dell.route_execution_receipts) == 11
    assert all(
        row["route_id"].startswith("p34_route::dell_")
        for row in dell.route_execution_receipts
    )


def test_source_identity_dates_pdf_hashes_and_counts_are_exact() -> None:
    pack = _load()
    expected_counts = {
        "source_snapshots": 6,
        "route_execution_receipts": 8,
        "evidence_rows": 7,
        "numeric_rows": 16,
        "derived_metrics": 4,
        "graph_edges": 4,
        "typed_gaps": 9,
    }
    assert {
        key: pack["observed_counts"][key] for key in expected_counts
    } == expected_counts
    as_of = date.fromisoformat(pack["as_of"][:10])
    assert all(
        date.fromisoformat(row["published_at"]) <= as_of
        for row in pack["source_snapshots"]
    )
    snapshots = {
        row["source_id"]: row for row in pack["source_snapshots"]
    }
    assert snapshots["mu_q3_fy26_10q"]["full_document_sha256"] == (
        "713a12cd52689640bcc0df9e131d31c3db8c26b794cd2e8219fd727cf4cbd45a"
    )
    assert snapshots["mu_q3_fy26_earnings_deck"][
        "full_document_sha256"
    ] == "29468a786fa4a9c7728735ea8e3ad5853bb1375a297c636e86e6a4dd3b155929"
    assert snapshots["mu_q3_fy26_prepared_remarks"][
        "full_document_sha256"
    ] == "a3ce62b84a059e35fae80c2bfd5c89f9af334193fd6aceff698fc3008e7d4c27"


def test_financial_rows_preserve_scope_and_recompute_exactly() -> None:
    pack = _load()
    numeric = {
        (row["metric_family"], row["segment_ref"]): row
        for row in pack["numeric_rows"]
    }
    assert numeric[("revenue", "__company_total__")]["value"] == "41456"
    assert numeric[("gross_profit", "__company_total__")]["value"] == "35056"
    assert numeric[("operating_income", "__company_total__")][
        "value"
    ] == "33318"
    assert numeric[("operating_cash_flow", "__company_total__")][
        "value"
    ] == "25388"
    assert numeric[("capital_expenditures_net", "__company_total__")][
        "value"
    ] == "7084"
    assert numeric[("inventory_days", "__company_total__")]["value"] == "120"
    assert not any(
        "HBM" in row["segment_ref"] for row in pack["numeric_rows"]
    )
    assert all(
        any("HBM" in boundary for boundary in row["cannot_support"])
        for row in pack["numeric_rows"]
    )

    revenue = Decimal(numeric[("revenue", "__company_total__")]["value"])
    gross_profit = Decimal(
        numeric[("gross_profit", "__company_total__")]["value"]
    )
    operating_income = Decimal(
        numeric[("operating_income", "__company_total__")]["value"]
    )
    operating_cash_flow = Decimal(
        numeric[("operating_cash_flow", "__company_total__")]["value"]
    )
    net_capex = Decimal(
        numeric[("capital_expenditures_net", "__company_total__")]["value"]
    )
    derived = {row["metric"]: row for row in pack["derived_metrics"]}
    assert (gross_profit / revenue * 100).quantize(
        Decimal("0.01")
    ) == Decimal(derived["gaap_gross_margin_recomputed"]["value"])
    assert (operating_income / revenue * 100).quantize(
        Decimal("0.01")
    ) == Decimal(derived["gaap_operating_margin_recomputed"]["value"])
    assert operating_cash_flow - net_capex == Decimal(
        derived["adjusted_free_cash_flow_recomputed"]["value"]
    )
    assert (net_capex / revenue * 100).quantize(
        Decimal("0.01")
    ) == Decimal(derived["net_capital_intensity_recomputed"]["value"])


def test_hbm_economics_and_customer_claims_remain_typed_gaps() -> None:
    pack = _load()
    gap_codes = {row["gap_code"] for row in pack["typed_gaps"]}
    assert {
        "cannot_infer_HBM_specific_revenue",
        "cannot_infer_HBM_specific_gross_or_operating_profit",
        "cannot_infer_customer_identity_or_concentration",
        "cannot_infer_SCA_HBM_attribution",
        "cannot_infer_HBM_price_volume_mix_decomposition",
        "cannot_infer_HBM_demand_durability",
        "cannot_infer_HBM_capacity_yield_probability_and_impact",
        "cannot_infer_export_control_impact",
        "cannot_infer_independent_counterevidence",
    } == gap_codes
    assert all(
        row["graph_edge_is_direct_evidence"] is False
        and row["boundary"]
        for row in pack["graph_edges"]
    )


def test_cross_case_identity_and_route_prefix_mutations_fail_closed() -> None:
    pack = _load()

    wrong_identity = deepcopy(pack)
    wrong_identity["issuer_identifier"] = "CIK0001571996"
    with pytest.raises(ValidationError):
        S4SourceGroundedInputPack.model_validate(
            _redigest(wrong_identity)
        )

    wrong_prefix = deepcopy(pack)
    wrong_prefix["route_execution_receipts"][0][
        "route_id"
    ] = wrong_prefix["route_execution_receipts"][0]["route_id"].replace(
        "p34_route::mu_", "p34_route::dell_", 1
    )
    with pytest.raises(ValidationError):
        S4SourceGroundedInputPack.model_validate(_redigest(wrong_prefix))

    missing_route = deepcopy(pack)
    missing_route["route_execution_receipts"].pop()
    missing_route["observed_counts"]["route_execution_receipts"] = 7
    with pytest.raises(ValidationError):
        S4SourceGroundedInputPack.model_validate(_redigest(missing_route))


def test_mu_source_grounded_exact_input_double_compile_is_stable() -> None:
    binding = load_s4_case_runtime_binding(ROOT, "MU")
    source_pack = load_s4_source_grounded_input_pack(ROOT, "MU")
    compile_args = {
        "case_id": "case_fin01_s4_t06_mu_source_grounded_proof_r1",
        "case_version": 1,
        "decision_surface_contract_ref": (
            "decision_surface_fin01_s4_t06_mu_source_grounded_proof_r1"
        ),
        "query": (
            "Assess Micron HBM demand durability, value capture, cycle and "
            "bottleneck counterevidence under the frozen three-cell method."
        ),
    }
    first = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        **compile_args,
    )
    second = build_s4_source_grounded_bounded_agent_input(
        binding,
        source_pack,
        **compile_args,
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.company == "MU"
    assert first.input_digest == (
        "a6b9df3320b56d3a6ba47f67557ef490c20d81fae2ff407270e403152da56682"
    )
    assert first.lineage["S4_T04_source_grounded_input"]["digest"] == (
        source_pack.source_pack_digest
    )
    assert len(first.cell_inputs) == 3
    assert all(
        cell["s4_case_method"]["case_ticker"] == "MU"
        and cell["s4_case_method"]["source_pack_digest"]
        == source_pack.source_pack_digest
        for cell in first.cell_inputs
    )
    serialized = json.dumps(first.model_dump(mode="json"))
    assert "CIK0001571996" not in serialized
    assert "s4_dell_" not in serialized

    with pytest.raises(
        ValueError,
        match="s4_source_grounded_input_identity_mismatch",
    ):
        build_s4_source_grounded_bounded_agent_input(
            load_s4_case_runtime_binding(ROOT, "DELL"),
            source_pack,
            **compile_args,
        )

    admission = S3ThreeCellBoundedAgentAdmission(
        admission_id=(
            "fin01-s4-t06-mu-source-grounded-zero-call-proof-not-live"
        ),
        execution_mode="zero_call_S4_MU_source_grounded_preflight",
        company="MU",
        research_profile_ref=binding.research_profile_ref,
    )
    node_executor = _S4ZeroCallNodeExecutor("MU", binding.method_id)
    with pytest.raises(
        ValueError,
        match=(
            "s4_case_runtime_mandatory_material_truth_and_"
            "identity_safety_profile_required"
        ),
    ):
        S3ThreeCellBoundedAgentExecutor(node_executor).execute(
            first,
            admission,
            run_identity={
                "work_unit_id": "wu-s4-t06-mu-source-proof",
                "attempt_id": "attempt-s4-t06-mu-source-proof",
                "research_run_id": "run-s4-t06-mu-source-proof",
            },
        )
    assert node_executor.calls == []
