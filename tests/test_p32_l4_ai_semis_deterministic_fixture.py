import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "engineering" / "run_p32_l4_ai_semis_deterministic_fixture.py"
SPEC = importlib.util.spec_from_file_location("run_p32_l4_ai_semis_deterministic_fixture", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


build_fixture_cases = module.build_fixture_cases
build_baseline_plan = module.build_baseline_plan
build_contract_aligned_plan = module.build_contract_aligned_plan
evaluate_case = module.evaluate_case
run_fixture = module.run_fixture
REQUIRED_CONTRACT_IDS = module.REQUIRED_CONTRACT_IDS


def _write_contract_ledger(repo_root: Path, contract_ids: set[str] | None = None) -> None:
    contract_ids = contract_ids or REQUIRED_CONTRACT_IDS
    path = repo_root / "docs" / "project_os" / "p32_l3_contract_translation_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for contract_id in sorted(contract_ids):
        rows.append(
            {
                "contract_id": contract_id,
                "source_extraction_ids": ["e"],
                "target_runtime_objects": ["Obj"],
                "target_agent_nodes": ["Agent"],
                "input_contract": {"required_fields": ["a"]},
                "output_contract": {"required_fields": ["b"]},
                "acceptance_non_llm_gate": ["gate"],
                "status": "candidate_l3_translated",
            }
        )
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_contract_aligned_plan_improves_each_fixture_case() -> None:
    contract_ids = set(REQUIRED_CONTRACT_IDS)
    for case in build_fixture_cases():
        baseline = build_baseline_plan(case)
        enhanced = build_contract_aligned_plan(case, contract_ids)
        evaluation = evaluate_case(case, baseline, enhanced, contract_ids)

        assert evaluation["status"] == "pass"
        assert evaluation["quality_delta"] >= 5
        assert enhanced["writer_material"]["shape"] == "writer_ready_judgment_material"
        assert enhanced["writer_material"]["uses_product_graph_as_spine"] is True
        assert not enhanced["writer_material"]["uses_peer_group_as_primary_evidence"]


def test_fixture_fails_when_required_contract_missing(tmp_path: Path) -> None:
    _write_contract_ledger(tmp_path, REQUIRED_CONTRACT_IDS - {"l3_context_engine_injection_contract_v0_1"})

    result = run_fixture(tmp_path)

    assert result["status"] == "fail"
    assert "l3_context_engine_injection_contract_v0_1" in result["missing_contracts"]


def test_product_judgment_does_not_require_sku_revenue() -> None:
    case = build_fixture_cases()[0]
    enhanced = build_contract_aligned_plan(case, set(REQUIRED_CONTRACT_IDS))
    evaluation = evaluate_case(case, build_baseline_plan(case), enhanced, set(REQUIRED_CONTRACT_IDS))

    assert evaluation["gate_details"]["product_kpi_not_required_for_product_judgment"]
    assert evaluation["gate_details"]["no_sku_revenue_absence_reason_traced"]
    product_card = next(card for card in enhanced["judgment_cards"] if card["supports_required_item"] == "product_architecture")
    assert product_card["strength"] == "high"


def test_semicap_keeps_peer_group_from_becoming_primary_evidence() -> None:
    case = build_fixture_cases()[1]
    enhanced = build_contract_aligned_plan(case, set(REQUIRED_CONTRACT_IDS))

    assert not enhanced["writer_material"]["uses_peer_group_as_primary_evidence"]
    dimensions = {row["dimension"] for row in enhanced["thesis_path"]}
    assert "industry_cycle" in dimensions
    assert "value_chain_position" in dimensions
