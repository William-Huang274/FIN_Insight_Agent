from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sec_agent.p33_runtime_assimilation_fixture import (
    EXPECTED_ACTIVE_CONTRACT_IDS,
    RELEASE_DECISION_PASS,
    build_p33_runtime_assimilation_fixture,
    default_p33_runtime_assimilation_fixture_paths,
)


def seed_active_registry(tmp_path: Path) -> None:
    ledger = tmp_path / "docs" / "project_os" / "p32_active_registry_promotion_ledger.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for contract_id in EXPECTED_ACTIVE_CONTRACT_IDS:
        rows.append(
            {
                "schema_version": "fin_insight_p32_active_registry_promotion_ledger_v0_1",
                "updated_at": "2026-07-05",
                "contract_id": contract_id,
                "promotion_decision": "active_registry_ready_runtime_alignment_only",
                "promotion_scope": "unit_test",
                "status": "active_registry_ready",
                "evidence_refs": [f"fixture_ref:{contract_id}"],
                "runtime_entry_policy": f"{contract_id} may be consumed by P33-2 deterministic fixture.",
                "do_not_promote": ["raw_dump", "unbounded_claim"],
                "rollback_gate": ["contract_not_consumed"],
            }
        )
    ledger.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def test_p33_runtime_assimilation_outputs_l4_scope_pass(tmp_path: Path) -> None:
    seed_active_registry(tmp_path)

    manifest = build_p33_runtime_assimilation_fixture(tmp_path)
    paths = default_p33_runtime_assimilation_fixture_paths(tmp_path)

    assert manifest["status"] == "pass"
    assert manifest["release_decision"] == RELEASE_DECISION_PASS
    assert manifest["closeout_level"] == "L4_scope_pass"
    assert manifest["gate_fail_count"] == 0
    assert len(manifest["absorbed_contract_ids"]) == 15
    assert paths.manifest_path.exists()
    assert paths.report_path.exists()


def test_p33_research_lead_plan_uses_thesis_path_required_items_and_roles(tmp_path: Path) -> None:
    seed_active_registry(tmp_path)

    manifest = build_p33_runtime_assimilation_fixture(tmp_path)
    plan = manifest["research_lead_runtime_plan"]

    assert plan["status"] == "ready"
    assert plan["thesis_path"]["primary_thesis"]
    assert len(plan["thesis_path"]["path_nodes"]) >= 5
    assert len(plan["required_item_plan"]) == 4
    assert len(plan["evidence_role_plan"]) >= 5
    assert plan["plan_summary"]["specialist_activation_policy"] == "required_item_or_role_gap_only"
    required_ids = {row["question_item_id"] for row in plan["required_item_plan"]}
    assert "cloud_capex_to_ai_server_readthrough" in required_ids
    assert "dell_ai_server_margin_quality" in required_ids


def test_p33_context_injection_is_role_scoped_and_writer_no_raw_dump(tmp_path: Path) -> None:
    seed_active_registry(tmp_path)

    manifest = build_p33_runtime_assimilation_fixture(tmp_path)
    audit = manifest["context_injection_audit"]

    assert audit["status"] == "pass"
    assert audit["specialist_role_context_distinct"] is True
    assert audit["writer_raw_dump_blocked"] is True
    assert "role_context" not in audit["writer_context_types"]
    role_ids = [ids[0] for _, ids in audit["specialist_role_context_ids"]]
    assert len(role_ids) == 4
    assert len(set(role_ids)) == 4


def test_p33_judgment_state_and_memo_logic_plan_are_writer_ready(tmp_path: Path) -> None:
    seed_active_registry(tmp_path)

    manifest = build_p33_runtime_assimilation_fixture(tmp_path)
    judgment = manifest["judgment_state"]
    memo_plan = manifest["memo_logic_plan"]

    assert judgment["status"] == "ready"
    assert len(judgment["judgment_cards"]) >= 5
    assert memo_plan["validation"]["status"] == "pass"
    assert "database_query" in memo_plan["writer_forbidden_tools"]
    assert "live_web_snapshot" in memo_plan["writer_forbidden_tools"]
    assert memo_plan["writer_thesis_skeleton"]["judgment_card_moves"]
    assert memo_plan["writer_thesis_skeleton"]["product_reasoning_move"]["coverage_roles"]


def test_p33_typed_gap_and_workbench_trace_are_replayable(tmp_path: Path) -> None:
    seed_active_registry(tmp_path)

    manifest = build_p33_runtime_assimilation_fixture(tmp_path)
    trace = manifest["workbench_trace_projection"]
    gaps = manifest["evidence_packs"]["typed_gap_refs"]

    assert gaps
    assert all(gap["gap_type"] for gap in gaps)
    assert trace["status"] == "pass"
    assert trace["evidence_ref_count"] >= 5
    assert trace["judgment_card_count"] >= 5
    assert trace["artifact_ref_count"] >= 4
    assert trace["paid_llm_call_count"] == 0
    assert trace["full_chain_run_count"] == 0
    assert trace["review_policy"]["frontend_local_state_is_final_audit"] is False
