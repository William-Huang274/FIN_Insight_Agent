import json
import sys
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sec_agent.eval_case_catalog import expand_case_catalog, load_case_catalog  # noqa: E402

CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"


REQUIRED_CASE_FIELDS = {
    "ordinal",
    "case_id",
    "case_family",
    "priority",
    "industry_schema",
    "prompt",
    "focus_tickers",
    "search_scope_tickers",
    "metric_families",
    "expected_gap_types",
    "eval_focus",
}

EXPECTED_FAMILY_COUNTS = {
    "L1_basic_focused": 10,
    "L2_standard_memo": 12,
    "L3_deep_research": 12,
    "L4_gap_boundary": 8,
    "L5_non_us_supply_chain": 4,
    "L6_backend_runtime_stress": 4,
}


def _load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


def test_vnext_50_case_catalog_has_stable_shape() -> None:
    catalog = _load_catalog()
    cases = catalog["cases"]
    case_ids = [case["case_id"] for case in cases]

    assert catalog["schema_version"] == "fin_agent_vnext_50_case_catalog_v0_1"
    assert len(cases) == 50
    assert len(set(case_ids)) == 50
    assert [case["ordinal"] for case in cases] == list(range(1, 51))
    assert Counter(case["case_family"] for case in cases) == EXPECTED_FAMILY_COUNTS


def test_vnext_50_case_catalog_case_contract_fields() -> None:
    catalog = _load_catalog()
    defaults = catalog["case_defaults"]
    default_dimensions = defaults["required_dimension_ids"]
    default_profiles = set(defaults["execution_profiles"])
    default_backend = defaults["backend_profile"]

    for case in catalog["cases"]:
        assert REQUIRED_CASE_FIELDS <= set(case), case["case_id"]
        assert case["prompt"].strip(), case["case_id"]
        assert case["focus_tickers"], case["case_id"]
        assert set(case["focus_tickers"]) <= set(case["search_scope_tickers"]), case["case_id"]
        assert case["metric_families"], case["case_id"]
        assert case["expected_gap_types"], case["case_id"]
        assert case["eval_focus"], case["case_id"]

        dimensions = case.get("required_dimension_ids", default_dimensions)
        assert {"fundamentals", "risk_and_counterevidence"} <= set(dimensions), case["case_id"]

        execution_profiles = set(case.get("execution_profiles", default_profiles))
        assert execution_profiles <= {"full_chain_live", "node_replay", "backend_smoke", "load_multiplex"}
        assert execution_profiles, case["case_id"]

        backend_profile = {**default_backend, **case.get("backend_profile", {})}
        assert backend_profile["load_class"] in {"light", "medium", "heavy", "stress"}
        assert backend_profile["sla_target_ms_p95"] > 0
        assert backend_profile["artifact_trace_required"] is True


def test_vnext_50_case_catalog_release_subsets_reference_existing_cases() -> None:
    catalog = _load_catalog()
    cases_by_id = {case["case_id"]: case for case in catalog["cases"]}
    subsets = catalog["release_subsets"]

    assert len(subsets["r12_successor_12"]) == 12
    assert len(subsets["broader_release_20"]) == 20
    assert len(subsets["load_mix_15"]) == 15

    for subset_name, subset_case_ids in subsets.items():
        assert len(subset_case_ids) == len(set(subset_case_ids)), subset_name
        assert set(subset_case_ids) <= set(cases_by_id), subset_name

    assert all(cases_by_id[case_id]["case_family"] == "L3_deep_research" for case_id in subsets["r12_successor_12"])
    assert set(subsets["r12_successor_12"]) <= set(subsets["broader_release_20"])

    broader_families = Counter(cases_by_id[case_id]["case_family"] for case_id in subsets["broader_release_20"])
    assert broader_families == {"L3_deep_research": 12, "L4_gap_boundary": 8}


def test_vnext_50_case_catalog_runtime_stress_cases_are_load_ready() -> None:
    catalog = _load_catalog()
    stress_cases = [case for case in catalog["cases"] if case["case_family"] == "L6_backend_runtime_stress"]

    assert len(stress_cases) == 4
    for case in stress_cases:
        assert "load_multiplex" in case["execution_profiles"], case["case_id"]
        assert case["backend_profile"]["load_class"] == "stress"
        assert case["backend_profile"]["multiplex_count"] >= case["load_scenario"]["concurrency"]
        assert case["load_scenario"]["task_count"] >= case["load_scenario"]["concurrency"]
        assert case["load_scenario"]["cancel_count"] <= case["load_scenario"]["task_count"]
        assert case["load_scenario"]["resume_count"] <= case["load_scenario"]["task_count"]


def test_vnext_50_case_catalog_expands_r12_successor_to_runner_cases() -> None:
    catalog = load_case_catalog(CATALOG_PATH)
    cases = expand_case_catalog(catalog, subset="r12_successor_12")

    assert len(cases) == 12
    assert all(case["category"] == "sector_depth" for case in cases)
    assert all(case["expected_execution_mode"] == "deep_research" for case in cases)
    assert all(case["require_vnext_contract"] for case in cases)
    assert all(case["require_milvus_runtime_contract"] for case in cases)
    assert all(case["require_run_audit_store"] for case in cases)
    assert all("product_technology_analyst" in case["expected_specialist_agents"] for case in cases)
    assert all("relationship_graph_lookup" in case["expected_tool_names"] for case in cases)
    assert all(case["catalog_id"] == catalog["catalog_id"] for case in cases)
    assert all("r12_successor_12" in case["catalog_release_subsets"] for case in cases)


def test_vnext_50_case_catalog_expands_load_mix_stress_cases() -> None:
    catalog = load_case_catalog(CATALOG_PATH)
    cases = expand_case_catalog(catalog, subset="load_mix_15")
    stress_cases = [case for case in cases if case["catalog_case_family"] == "L6_backend_runtime_stress"]

    assert len(cases) == 15
    assert len(stress_cases) == 4
    assert {case["expected_execution_mode"] for case in stress_cases} == {
        "focused_answer",
        "standard_memo",
        "deep_research",
    }
    assert all(case["require_run_audit_store"] for case in stress_cases)
