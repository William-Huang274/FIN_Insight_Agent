import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "eval_multi_agent" / "run_vnext_case_catalog_replay_gate.py"
CATALOG_PATH = REPO_ROOT / "tests" / "fixtures" / "fin_agent_vnext_50_case_catalog_v0_1.json"


def test_r12_successor_catalog_replay_gate_passes(tmp_path: Path) -> None:
    module = _load_script_module()
    output_path = tmp_path / "r12_successor_gate.json"
    expanded_cases_path = tmp_path / "r12_successor_cases.jsonl"

    report = module.run_gate(
        catalog_path=CATALOG_PATH,
        subset="r12_successor_12",
        output_path=output_path,
        expanded_cases_path=expanded_cases_path,
    )

    assert report["status"] == "pass"
    assert report["case_count"] == 12
    assert report["family_counts"] == {"L3_deep_research": 12}
    assert report["mode_counts"] == {"deep_research": 12}
    assert report["workbench_command_check"]["failed_checks"] == []
    assert report["failures"] == []
    assert output_path.exists()
    assert expanded_cases_path.exists()
    assert all(check["failed_checks"] == [] for check in report["case_checks"])
    assert all(
        check["query_contract_summary"]["evidence_requirement_count"] == 6
        for check in report["case_checks"]
    )
    assert all(
        check["checks"]["smoke_state_query_contract_preserved"]
        for check in report["case_checks"]
    )


def _load_script_module():
    spec = importlib.util.spec_from_file_location("run_vnext_case_catalog_replay_gate_under_test", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
