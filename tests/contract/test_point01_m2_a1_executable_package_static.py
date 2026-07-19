"""Static package regressions for the executable-but-not-admitted M2-A1 harness."""

from __future__ import annotations

import ast
import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FREEZE = ROOT / "scripts/engineering/run_point01_m2_a1_executable_audit_package_freeze.py"
HARNESS = ROOT / "src/sec_agent/canonical_runtime/m2_a1_audit_harness.py"
ACTUAL_RUNNER = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit.py"
CLEAN_CHILD = ROOT / "scripts/engineering/run_point01_m2_a1_actual_audit_clean_child.py"


def _runner():
    spec = importlib.util.spec_from_file_location("point01_m2_a1_executable_audit_package_freeze", FREEZE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package():
    runner = _runner()
    package = runner.build_package()
    assert runner.verify_package(package)["status"] == "pass"
    return runner, package


def test_freeze_runner_is_standard_library_only_and_actual_harness_has_no_compiler_call() -> None:
    tree = ast.parse(FREEZE.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= {"__future__", "hashlib", "json", "re", "subprocess", "pathlib", "typing"}
    harness_tree = ast.parse(HARNESS.read_text(encoding="utf-8"))
    called = {node.func.id for node in ast.walk(harness_tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert "DecisionSurfacePlanningService" not in called
    assert "DeterministicShadowCompiler" not in called
    actual_imports = {node.module for node in ast.walk(ast.parse(ACTUAL_RUNNER.read_text(encoding="utf-8"))) if isinstance(node, ast.ImportFrom) and node.module}
    assert "sec_agent.canonical_runtime.m2_a1_audit_oracle" not in actual_imports
    assert '"-I"' in ACTUAL_RUNNER.read_text(encoding="utf-8")
    child_imports = {node.module for node in ast.walk(ast.parse(CLEAN_CHILD.read_text(encoding="utf-8"))) if isinstance(node, ast.ImportFrom) and node.module}
    assert "sec_agent.canonical_runtime.m2_a1_audit_oracle" not in child_imports


def test_executable_package_binds_harness_authority_and_staged_inputs() -> None:
    runner, package = _package()
    gate = runner.build_gate(package)
    assert gate["status"] == "executable_package_frozen_pending_exact_admission"
    assert gate["actual_admission_status"] == "package_admission_required"
    assert all(value == 0 for value in gate["execution_counts"].values())
    assert all(gate["harness_policy_checks"].values())


def test_executable_package_digest_rejects_authority_and_contract_tamper() -> None:
    runner, package = _package()
    variants = {
        "source": ("input_bytes_source", "working_tree"),
        "input": ("input_file_sha256", {**package["input_file_sha256"], runner.HARNESS_POLICY: "0" * 64}),
        "design": ("design_package_digest", "1" * 64),
        "fingerprint": ("fixed_store_fingerprints", {**package["fixed_store_fingerprints"], "fixed_approval_store": {**package["fixed_store_fingerprints"]["fixed_approval_store"], "sha256": "2" * 64}}),
        "harness": ("harness_policy_digest", "3" * 64),
        "authority": ("authority_boundary", "expanded"),
        "actual": ("actual_probes_currently_authorized", True),
        "compiler": ("compiler_shadow_execution_authorized", True),
        "receipt": ("receipt_wrapper_persistence_authorized", True),
    }
    for name, (field, value) in variants.items():
        tampered = copy.deepcopy(package)
        tampered[field] = value
        assert runner.verify_package(tampered)["status"] == "package_digest_mismatch", name


def test_self_signed_exact_bytes_still_need_external_admission() -> None:
    runner, package = _package()
    self_signed = copy.deepcopy(package)
    self_signed["package_ref"] = "self-signed-m2-a1-executable-package"
    self_signed["package_digest"] = runner.package_payload_digest(self_signed)
    assert runner.verify_package(self_signed)["status"] == "pass"
    assert runner.verify_external_admission(self_signed, None)["status"] == "package_admission_required"
