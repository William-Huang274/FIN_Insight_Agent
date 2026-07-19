import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "engineering" / "validate_p32_learning_gate.py"
SPEC = importlib.util.spec_from_file_location("validate_p32_learning_gate", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


validate = module.validate


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _minimal_repo(tmp_path: Path) -> None:
    base = tmp_path / "docs" / "project_os"
    _write_jsonl(
        base / "financial_research_method_learning_ledger.jsonl",
        [
            {
                "source_id": "s1",
                "source_type": "report",
                "source_title": "Report",
                "source_url": "https://example.com",
                "status": "candidate_l1_discovered",
            }
        ],
    )
    _write_jsonl(
        base / "agent_engineering_pattern_learning_ledger.jsonl",
        [
            {
                "pattern_id": "p1",
                "source_type": "docs",
                "source_title": "Docs",
                "source_url": "https://example.com/docs",
                "status": "candidate_l1_discovered",
            }
        ],
    )
    _write_jsonl(
        base / "financial_research_method_extraction_ledger.jsonl",
        [
            {
                "extraction_id": "e1",
                "source_ids": ["s1"],
                "status": "candidate_l2_extracted",
            }
        ],
    )
    _write_jsonl(
        base / "agent_engineering_pattern_extraction_ledger.jsonl",
        [
            {
                "extraction_id": "e2",
                "source_ids": ["p1"],
                "status": "candidate_l2_extracted",
            }
        ],
    )
    _write_jsonl(
        base / "p32_l1_coverage_matrix.jsonl",
        [
            {
                "coverage_domain": "domain",
                "track": "financial_research_method",
                "coverage_status": "sufficient_for_initial_l3",
                "current_source_ids": ["s1"],
                "supports_next_proof": True,
                "next_action": "translate",
                "pass_condition": "ok",
            }
        ],
    )
    _write_jsonl(
        base / "p32_l3_contract_translation_ledger.jsonl",
        [
            {
                "contract_id": "c1",
                "source_extraction_ids": ["e1", "e2"],
                "target_runtime_objects": ["Obj"],
                "target_agent_nodes": ["Agent"],
                "input_contract": {"required_fields": ["a"]},
                "output_contract": {"required_fields": ["b"]},
                "acceptance_non_llm_gate": ["gate"],
                "status": "candidate_l3_translated",
            }
        ],
    )


def test_validate_minimal_repo_passes(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)

    result = validate(tmp_path)

    assert result["status"] == "pass"
    assert result["source_count"] == 2
    assert result["contract_count"] == 1


def test_validate_unknown_extraction_fails(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    contracts = tmp_path / "docs" / "project_os" / "p32_l3_contract_translation_ledger.jsonl"
    row = json.loads(contracts.read_text(encoding="utf-8").splitlines()[0])
    row["source_extraction_ids"] = ["missing"]
    _write_jsonl(contracts, [row])

    result = validate(tmp_path)

    assert result["status"] == "fail"
    assert any("unknown extraction_id missing" in error for error in result["errors"])


def test_validate_gap_cannot_support_next_proof(tmp_path: Path) -> None:
    _minimal_repo(tmp_path)
    coverage = tmp_path / "docs" / "project_os" / "p32_l1_coverage_matrix.jsonl"
    row = json.loads(coverage.read_text(encoding="utf-8").splitlines()[0])
    row["coverage_status"] = "gap_needs_l1"
    row["supports_next_proof"] = True
    _write_jsonl(coverage, [row])

    result = validate(tmp_path)

    assert result["status"] == "fail"
    assert any("cannot support next proof" in error for error in result["errors"])
