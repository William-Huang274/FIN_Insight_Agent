"""Static negative coverage for the non-active M2-A1 baseline blueprint."""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/engineering/run_point01_m2_a1_baseline_authority_blueprint_freeze.py"


def _module():
    spec = importlib.util.spec_from_file_location("m2_a1_baseline_blueprint", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_baseline_blueprint_is_non_active_and_exactly_bound() -> None:
    module = _module()
    blueprint = module.build_blueprint()
    gate = module.build_gate(blueprint)

    assert gate["status"] == "pass"
    assert blueprint["target"]["scenario_id"] == "p01-baseline-separated-input"
    assert blueprint["all_other_scenarios"] == {
        "count": 15,
        "status": "blocked_pending_baseline_actual_oracle_reviewer_checkpoint",
        "authority_issue_forbidden": True,
    }
    assert blueprint["execution_counts"]["active_receipts_created"] == 0
    assert blueprint["old_admission_artifacts"]["status"] == "expired_execution_unused"


def test_active_values_or_nonbaseline_or_unbounded_receipt_fail_closed() -> None:
    module = _module()
    blueprint = module.build_blueprint()

    active_nonce = copy.deepcopy(blueprint)
    active_nonce["runtime_compatible_templates"]["execution_receipt"]["nonce_sha256"] = "a" * 64
    active_nonce["blueprint_digest"] = module.canonical_digest({key: value for key, value in active_nonce.items() if key != "blueprint_digest"})
    assert module.build_gate(active_nonce)["status"] == "fail_closed"

    active_timestamp = copy.deepcopy(blueprint)
    active_timestamp["runtime_compatible_templates"]["external_admission"]["expires_at"] = "2026-07-14T00:00:00Z"
    active_timestamp["blueprint_digest"] = module.canonical_digest({key: value for key, value in active_timestamp.items() if key != "blueprint_digest"})
    assert module.build_gate(active_timestamp)["status"] == "fail_closed"

    active_digest = copy.deepcopy(blueprint)
    active_digest["runtime_compatible_templates"]["external_admission"]["admission_digest"] = "b" * 64
    active_digest["blueprint_digest"] = module.canonical_digest({key: value for key, value in active_digest.items() if key != "blueprint_digest"})
    assert module.build_gate(active_digest)["status"] == "fail_closed"

    alternate_scenario = copy.deepcopy(blueprint)
    alternate_scenario["target"]["scenario_id"] = "p02-valid-versioned-baseline"
    alternate_scenario["blueprint_digest"] = module.canonical_digest({key: value for key, value in alternate_scenario.items() if key != "blueprint_digest"})
    assert module.build_gate(alternate_scenario)["status"] == "fail_closed"

    too_long_receipt = copy.deepcopy(blueprint)
    too_long_receipt["just_in_time_issuance_contract"]["receipt_ttl_minutes"] = 31
    too_long_receipt["blueprint_digest"] = module.canonical_digest({key: value for key, value in too_long_receipt.items() if key != "blueprint_digest"})
    assert module.build_gate(too_long_receipt)["status"] == "fail_closed"

    missing_plan_binding = copy.deepcopy(blueprint)
    del missing_plan_binding["exact_binding"]["receipt_execution_plan_gate_digest"]
    missing_plan_binding["blueprint_digest"] = module.canonical_digest({key: value for key, value in missing_plan_binding.items() if key != "blueprint_digest"})
    assert module.build_gate(missing_plan_binding)["status"] == "fail_closed"


def test_blueprint_commands_cannot_be_activated_by_template_mutation() -> None:
    module = _module()
    blueprint = module.build_blueprint()
    forged = copy.deepcopy(blueprint)
    forged["command_contracts"]["registrar"]["invocation_permitted"] = True
    forged["blueprint_digest"] = module.canonical_digest({key: value for key, value in forged.items() if key != "blueprint_digest"})
    assert module.build_gate(forged)["status"] == "fail_closed"
