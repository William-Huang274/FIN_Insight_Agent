from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


OUTPUT = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_"
    "and_t07_handoff_zero_call_implementation_v1_0.json"
)
T06_B_RECORD = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_b_current_frontend_runtime_"
    "isolation_and_browser_zero_call_implementation_v1_0.json"
)
T06_A_MANIFEST = ROOT / (
    "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_projection_"
    "manifest_v1_0.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize() -> dict[str, Any]:
    predecessor = json.loads(T06_B_RECORD.read_text(encoding="utf-8"))
    manifest = json.loads(T06_A_MANIFEST.read_text(encoding="utf-8"))
    source_refs = [
        "configs/releases/fin_ia_0_1_2_s4_t06_c_current_review_control_contract_v1_0.json",
        "configs/runtime/fin_ia_0_1_2_s4_t06_current_product_review_control_runtime_resource_registry_v1_0.json",
        "apps/workbench/backend/application/fin_0_1_2_s4_t06_current_review_control.py",
        "apps/workbench/backend/api/v1/current_product.py",
        "apps/workbench/backend/app.py",
        "apps/workbench/frontend/vite/src/api/currentProduct.ts",
        "apps/workbench/frontend/vite/src/app/CurrentProductWorkbench.tsx",
        "apps/workbench/frontend/vite/src/app/current-product.css",
        "apps/workbench/frontend/e2e/current-product.spec.ts",
        "tests/contract/test_fin_0_1_2_s4_t06_a_current_product_projection.py",
        "tests/contract/test_fin_0_1_2_s4_t06_b_current_mode_frontend_and_runtime_isolation.py",
        "tests/contract/test_fin_0_1_2_s4_t06_c_current_review_control_and_t07_handoff.py",
        "scripts/releases/materialize_fin_ia_0_1_2_s4_t06_c_current_review_control_and_t07_handoff.py",
    ]
    body: dict[str, Any] = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t06_c_current_review_control_and_t07_"
            "handoff_zero_call_implementation_v1_0"
        ),
        "recorded_at": "2026-08-05T23:45:00+08:00",
        "status": "T06_C_engineering_pass_T07_handoff_ready",
        "predecessor": {
            "T06_B_record_ref": T06_B_RECORD.relative_to(ROOT).as_posix(),
            "T06_B_record_digest": predecessor["record_digest"],
            "current_product_manifest_ref": T06_A_MANIFEST.relative_to(ROOT).as_posix(),
            "current_product_manifest_digest": manifest["manifest_digest"],
            "historical_records_preserved_not_rewritten": True,
            "T06_C_is_controlled_successor_code_binding": True,
        },
        "product_increment": {
            "current_cases": ["DELL", "MU", "NVDA"],
            "immutable_business_surfaces": [
                "case", "run", "evidence", "numeric", "graph", "gaps",
                "workpaper", "report", "trace", "quality",
            ],
            "typed_action": "return_for_repair",
            "typed_reason_count": 6,
            "exact_bindings": [
                "manifest_digest",
                "case_projection_digest",
                "target_view_digest",
            ],
            "append_only_hash_chained_review_events": True,
            "idempotent_control_writes": True,
            "restart_replay": True,
            "three_case_isolation": True,
            "T07_handoff_packet": True,
            "business_truth_mutated": False,
            "automatic_repair_executed": False,
        },
        "T07_handoff_boundary": {
            "empty_queue_status": "ready_for_qualified_review",
            "open_request_status": "repair_required_before_qualified_review",
            "qualified_review_executed": False,
            "authenticated_reviewer_identity_established": False,
            "NVDA_R3_executed": False,
            "T07_entered": False,
            "required_permission": "current_product:qualified_review",
        },
        "test_governance": {
            "T06_A_T06_B_historical_receipts_remain_digest_bound": True,
            "successor_sources_not_frozen_to_predecessor_SHA": True,
            "RC_P36_128_original_four_historical_debts_closed": False,
            "historical_results_rewritten": False,
        },
        "code_and_test_bindings": [
            {
                "ref": ref,
                "sha256": _sha256(ROOT / ref),
                "bytes": (ROOT / ref).stat().st_size,
            }
            for ref in source_refs
        ],
        "verification": {
            "T06_A_B_C_plus_historical_fixture_contracts": "36 passed",
            "playwright_chromium_desktop_mobile": "8 passed",
            "typescript": "pass",
            "vite_production_build": "pass_with_existing_chunk_size_warning",
            "broad_selected_T05_T06_Workbench_regression": (
                "158 passed / 4 known RC-P36-128 historical failures"
            ),
            "new_T06_C_regression_failures": 0,
            "three_case_default_handoff_ready": True,
            "model_provider_network_financial_source_calls": [0, 0, 0, 0],
            "accepted_R2_business_truth_writes": 0,
            "control_plane_test_writes": "temporary_SQLite_only",
        },
        "acceptance_boundary": {
            "S4_T06_A": "engineering_pass",
            "S4_T06_B": "engineering_pass",
            "S4_T06_C": "engineering_pass",
            "S4_T06_product_projection": "pass_ready_for_T07_entry",
            "qualified_human_review": False,
            "NVDA_R3": False,
            "S4_T07": "not_entered",
            "S4_T08": "not_entered",
            "S5": "not_entered",
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T07-EXACT-QUALIFIED-HUMAN-REVIEW-"
            "NVDA-R3-AND-BOUNDED-EXPLANATION-ENTRY-DECISION"
        ),
    }
    body["record_digest"] = canonical_digest(body)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return body


if __name__ == "__main__":
    record = materialize()
    print(
        json.dumps(
            {"output": str(OUTPUT), "record_digest": record["record_digest"]}
        )
    )
