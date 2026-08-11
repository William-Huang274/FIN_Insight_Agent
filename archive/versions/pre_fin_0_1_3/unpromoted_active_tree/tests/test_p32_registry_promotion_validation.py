import importlib.util
import json
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "engineering" / "validate_p32_registry_promotion.py"
SPEC = importlib.util.spec_from_file_location("validate_p32_registry_promotion", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


validate = module.validate


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _minimal_repo(tmp_path: Path, *, active_contract: str = "c1", fixture_contracts: list[str] | None = None) -> None:
    fixture_contracts = fixture_contracts or [active_contract]
    base = tmp_path / "docs" / "project_os"
    _write_jsonl(
        base / "p32_l3_contract_translation_ledger.jsonl",
        [
            {"contract_id": "c1", "status": "candidate_l3_translated"},
            {"contract_id": "c2", "status": "candidate_l3_translated"},
        ],
    )
    fixture = tmp_path / "data" / "manifests" / "p32_l4_ai_semis_deterministic_fixture_v0_1.json"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "contract_aligned_plan": {
                            "absorbed_contract_ids": fixture_contracts,
                            "used_case_contract_ids": fixture_contracts,
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(
        base / "p32_active_registry_promotion_ledger.jsonl",
        [
            {
                "contract_id": active_contract,
                "promotion_decision": "active_registry_ready_feature_flagged",
                "promotion_scope": "scope",
                "status": "active_registry_ready",
                "evidence_refs": ["data/manifests/p32_l4_ai_semis_deterministic_fixture_v0_1.json"],
                "runtime_entry_policy": "feature_flag_p32",
                "localization_notes": "local",
                "do_not_promote": ["x"],
                "rollback_gate": ["y"],
            },
            {
                "contract_id": "c2",
                "promotion_decision": "deferred_pending_l4_fixture",
                "promotion_scope": "scope",
                "status": "deferred",
                "defer_reason": "new",
                "runtime_entry_policy": "do not enter active runtime",
                "localization_notes": "local",
                "do_not_promote": ["x"],
                "rollback_gate": ["y"],
            },
        ],
    )


def test_current_repo_p32_promotion_ledger_passes() -> None:
    result = validate(Path(__file__).resolve().parents[1])

    assert result["status"] == "pass"
    assert result["active_registry_ready_count"] == 15
    assert result["deferred_count"] == 0


def test_active_unknown_contract_fails(tmp_path: Path) -> None:
    _minimal_repo(tmp_path, active_contract="missing", fixture_contracts=["missing"])

    result = validate(tmp_path)

    assert result["status"] == "fail"
    assert any("promoted contract not found" in error for error in result["errors"])


def test_active_contract_without_fixture_proof_fails(tmp_path: Path) -> None:
    _minimal_repo(tmp_path, active_contract="c1", fixture_contracts=["other"])

    result = validate(tmp_path)

    assert result["status"] == "fail"
    assert any("active promotion lacks P32-L4 fixture proof" in error for error in result["errors"])


def test_gap_domain_contracts_are_promoted_after_dedicated_fixtures() -> None:
    promotion_path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "project_os"
        / "p32_active_registry_promotion_ledger.jsonl"
    )
    rows = [json.loads(line) for line in promotion_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    status_by_contract = {row["contract_id"]: row["status"] for row in rows}

    assert status_by_contract["l3_enterprise_rag_data_pipeline_contract_v0_1"] == "active_registry_ready"
    assert status_by_contract["l3_sandbox_resource_scheduler_contract_v0_1"] == "active_registry_ready"
    assert status_by_contract["l3_capital_market_feedback_contract_v0_1"] == "active_registry_ready"
    assert status_by_contract["l3_workbench_artifact_review_surface_contract_v0_1"] == "active_registry_ready"
    assert status_by_contract["l3_research_to_quant_factor_handoff_contract_v0_1"] == "active_registry_ready"
