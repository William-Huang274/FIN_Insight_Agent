"""Static/no-authority checks for the Phase-B0 M2-A1 v2.4 refreeze."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "scripts/engineering/run_point01_m2_a1_operational_qualification_v2_4_refreeze.py"
PARENT = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_v2_4.py"


@lru_cache(maxsize=1)
def _module():
    spec = importlib.util.spec_from_file_location("point01_m2_a1_b0_refreeze", FREEZE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@lru_cache(maxsize=1)
def _artifacts():
    return _module().build_artifacts()


def _child(code: str) -> dict[str, object]:
    completed = subprocess.run([sys.executable, "-I", "-c", code], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.strip().splitlines()[-1])


def test_v2_4_refreeze_binds_phase_a_clean_child_and_nonreplayable_history() -> None:
    module = _module()
    artifacts = _artifacts()
    assert module.verify_package(artifacts["package"])["status"] == "pass"
    assert module.verify_plan(artifacts["plan"], artifacts["package"], artifacts["package_gate"])["status"] == "pass"
    assert module.verify_blueprint(artifacts["blueprint"], artifacts["package"], artifacts["package_gate"], artifacts["plan"], artifacts["plan_gate"])["status"] == "pass"
    assert artifacts["package_gate"]["status"] == artifacts["plan_gate"]["status"] == artifacts["blueprint_gate"]["status"] == "pass"
    assert artifacts["plan"]["compatibility"]["group_counts"] == {"P01": 4, "P02": 6, "P03": 6}
    assert artifacts["blueprint"]["exact_binding"]["scenario_id"] == "p01-baseline-separated-input"
    assert artifacts["blueprint"]["exact_binding"]["package_gate_digest"] == artifacts["package_gate"]["gate_digest"]
    assert artifacts["blueprint"]["exact_binding"]["plan_gate_digest"] == artifacts["plan_gate"]["gate_digest"]
    assert artifacts["blueprint"]["all_other_scenarios"] == {"count": 15, "authority_issue_forbidden": True}
    assert module.validate_new_execution_identity(package_digest=module.OLD_PACKAGE_DIGEST, blueprint_digest="x", admission_or_receipt_digest="y") == "historical_authority_non_replayable"
    assert module.validate_new_execution_identity(package_digest=artifacts["package"]["package_digest"], blueprint_digest=artifacts["blueprint"]["blueprint_digest"], admission_or_receipt_digest="future") == "fresh_exact_external_admission_and_receipt_required"


def test_v2_4_package_plan_and_blueprint_tamper_fail_closed() -> None:
    module = _module()
    artifacts = _artifacts()
    source_tamper = copy.deepcopy(artifacts["package"])
    source_tamper["input_bytes_source"] = "working_tree"
    assert module.verify_package(source_tamper)["status"] == "fail_closed"
    hash_tamper = copy.deepcopy(artifacts["package"])
    hash_tamper["input_file_sha256"][module.CORPUS] = "0" * 64
    hash_tamper["package_digest"] = module.canonical_digest({key: value for key, value in hash_tamper.items() if key != "package_digest"})
    assert module.verify_package(hash_tamper)["status"] == "fail_closed"
    plan_tamper = copy.deepcopy(artifacts["plan"])
    plan_tamper["compatibility"]["group_counts"] = {"P01": 4, "P02": 5, "P03": 7}
    plan_tamper["plan_digest"] = module.canonical_digest({key: value for key, value in plan_tamper.items() if key != "plan_digest"})
    assert module.verify_plan(plan_tamper, artifacts["package"], artifacts["package_gate"])["status"] == "fail_closed"
    blueprint_tamper = copy.deepcopy(artifacts["blueprint"])
    blueprint_tamper["templates"]["external_admission"]["fields"]["nonce_sha256"] = "active_nonce_forbidden"
    blueprint_tamper["blueprint_digest"] = module.canonical_digest({key: value for key, value in blueprint_tamper.items() if key != "blueprint_digest"})
    assert module.verify_blueprint(blueprint_tamper, artifacts["package"], artifacts["package_gate"], artifacts["plan"], artifacts["plan_gate"])["status"] == "fail_closed"


def test_parent_preload_cannot_contaminate_python_isolated_clean_child() -> None:
    result = _child(
        "import subprocess, sys, json, requests; "
        f"p=subprocess.run([sys.executable, r'{PARENT}', '--transport-isolation-probe'], capture_output=True, text=True, check=False); "
        "assert p.returncode == 0, p.stderr; print(p.stdout.strip().splitlines()[-1])"
    )
    assert result["status"] == "clean_child_canary_before_harness_import_pass"
    counts = result["counts"]
    assert counts["transport_module_loaded_count"] == 0
    assert counts["transport_constructor_attempt_count"] == 0
    assert counts["network_request_success_count"] == 0


def test_m6_transport_module_context_is_not_transport_construction_or_request() -> None:
    result = _child(
        "import sys, json; sys.path.insert(0, 'src'); "
        "from sec_agent.canonical_runtime.m2_a1_audit_canary import M2A1AuditCanary, M2A1TransportAccessError; "
        "from sec_agent.canonical_runtime.bounded_sec_metadata_execution import SingleCallSecSubmissionsClient; "
        "c=M2A1AuditCanary(allowed_temporary_roots=(), fixed_paths=()); c.observe_transport_module_presence(); "
        "blocked=False; "
        "\ntry:\n with c.instrument(): SingleCallSecSubmissionsClient(user_agent='FinInsight security-contact@invalid.example', timeout_seconds=1)\nexcept M2A1TransportAccessError: blocked=True\n"
        "s=c.snapshot(); print(json.dumps({'blocked':blocked,'counts':s['counts']}))"
    )
    assert result["blocked"] is True
    counts = result["counts"]
    assert counts["transport_module_loaded_count"] >= 1
    assert counts["transport_constructor_attempt_count"] == 1
    assert counts["network_request_attempt_count"] == 0
    assert counts["network_request_success_count"] == 0
