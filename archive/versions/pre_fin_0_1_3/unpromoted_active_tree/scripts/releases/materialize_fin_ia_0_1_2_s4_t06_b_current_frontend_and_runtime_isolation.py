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
    manifest = json.loads(T06_A_MANIFEST.read_text(encoding="utf-8"))
    source_refs = [
        "apps/workbench/backend/app.py",
        "apps/workbench/frontend/package.json",
        "apps/workbench/frontend/package-lock.json",
        "apps/workbench/frontend/playwright.config.ts",
        "apps/workbench/frontend/e2e/current-product.spec.ts",
        "apps/workbench/frontend/vite/src/api/currentProduct.ts",
        "apps/workbench/frontend/vite/src/app/CurrentProductWorkbench.tsx",
        "apps/workbench/frontend/vite/src/app/current-product.css",
        "apps/workbench/frontend/vite/src/app/AppShell.tsx",
        "apps/workbench/frontend/vite/src/app/AnalystWorkspaceChrome.tsx",
        "scripts/dev/run_workbench_backend.py",
        "scripts/releases/materialize_fin_ia_0_1_2_s4_t06_b_current_frontend_and_runtime_isolation.py",
        "tests/contract/test_fin_0_1_2_s4_t06_b_current_mode_frontend_and_runtime_isolation.py",
        "tests/contract/test_point03_evidence_fixture_api.py",
        "tests/contract/test_vt2_integrity_workpaper_api.py",
        "tests/contract/test_vt3_deliverable_review_trace_api.py",
    ]
    body: dict[str, Any] = {
        "schema_version": (
            "fin_ia_0_1_2_s4_t06_b_current_frontend_runtime_isolation_"
            "and_browser_zero_call_implementation_v1_0"
        ),
        "recorded_at": "2026-08-05T22:00:00+08:00",
        "status": "T06_B_engineering_pass_current_frontend_available_T06_C_pending",
        "source_T06_A": {
            "manifest_ref": T06_A_MANIFEST.relative_to(ROOT).as_posix(),
            "manifest_digest": manifest["manifest_digest"],
            "historical_implementation_ref": (
                "configs/releases/fin_ia_0_1_2_s4_t06_a_current_product_"
                "projection_read_only_service_and_api_zero_call_implementation_v1_0.json"
            ),
            "historical_implementation_digest": (
                "f30c387cfe7c4ae8c999ed75eeb82a18ea83ed7b57c98d6fd4466faa6817617d"
            ),
            "historical_record_preserved_not_rewritten": True,
            "T06_B_is_controlled_successor_code_binding": True,
        },
        "product_increment": {
            "entry_path": "/current",
            "current_cases": ["DELL", "MU", "NVDA"],
            "surfaces": [
                "case", "run", "evidence", "numeric", "graph", "gaps",
                "workpaper", "report", "trace", "quality",
            ],
            "desktop_and_mobile_layout": True,
            "explicit_current_headers": ["current", "current_product:read"],
            "API_methods": ["GET"],
            "typed_empty_graph_rendered": True,
            "raw_capture_or_private_reasoning_exposed": False,
            "current_fixture_product_truth_mixed": False,
            "return_request_repair_available": False,
        },
        "runtime_mode_isolation": {
            "default_mode": "current",
            "explicit_fixture_mode": "fixture",
            "current_background_dispatch_enabled": True,
            "fixture_background_dispatch_enabled": False,
            "evidence_state_checks_weakened": False,
            "current_runtime_globally_disabled": False,
            "RC_P36_127": "closed_root_cause_explicit_runtime_mode_and_11_of_11_regression_green",
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
            "T06_B_plus_historical_fixture_contracts": "17 passed",
            "playwright_chromium_desktop_mobile": "6 passed",
            "typescript": "pass",
            "vite_production_build": "pass_with_existing_chunk_size_warning",
            "npm_audit_after_bounded_security_update": "0 vulnerabilities",
            "broad_selected_T05_T06_Workbench_regression": "148 passed / 4 historical_non_replayable_or_stale_binding_failures",
            "broad_failure_classification": {
                "T05_C_consumed_fresh_runtime_identity": 3,
                "T05_entry_historical_mutable_code_sha_binding": 1,
                "T06_B_regression_established": 0,
            },
            "business_model_provider_financial_source_calls": [0, 0, 0],
            "business_runtime_writes": 0,
            "dependency_install_network_access": True,
            "dependency_install_authorized_by_user": True,
        },
        "acceptance_boundary": {
            "S4_T06_A": "engineering_pass_historical_record_preserved",
            "S4_T06_B": "engineering_pass",
            "S4_T06_product_acceptance": False,
            "S4_T06_C": "not_started",
            "qualified_human_review": False,
            "NVDA_R3": False,
            "S4_T07": "not_entered",
            "S5": "not_entered",
            "release": "not_qualified",
            "production": "not_qualified",
        },
        "recommended_next": (
            "FIN-0.1.2-S4-T06-C-TYPED-RETURN-REQUEST-REPAIR-REPLAY-"
            "AND-T07-HANDOFF-READINESS-ZERO-CALL-IMPLEMENTATION"
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
    print(json.dumps({"output": str(OUTPUT), "record_digest": record["record_digest"]}))
