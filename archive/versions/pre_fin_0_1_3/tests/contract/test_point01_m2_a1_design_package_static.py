"""Static-only regressions for the M2-A1 repaired audit design package.

These tests load the standard-library-only package builder.  They deliberately
do not import M2 compiler, shadow, serializer, registry or store runtime.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_design_package_repair_freeze.py"


def _runner():
    spec = importlib.util.spec_from_file_location("point01_m2_a1_design_package_repair_freeze", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _package():
    runner = _runner()
    package = runner.build_package()
    assert runner.verify_package(package)["status"] == "pass"
    return runner, package


def test_m2_a1_repair_runner_is_standard_library_only_and_m2_runtime_free() -> None:
    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert imported <= {"__future__", "hashlib", "json", "re", "subprocess", "pathlib", "typing"}
    source = RUNNER_PATH.read_text(encoding="utf-8")
    for forbidden in ("import sec_agent", "from sec_agent", "SQLiteCanonicalStore(", "RuntimeFacade("):
        assert forbidden not in source


def test_m2_a1_repaired_static_contracts_are_complete_and_actual_remains_forbidden() -> None:
    runner = _runner()
    corpus = runner._staged_json(runner.CORPUS)
    oracle = runner._staged_json(runner.ORACLE)
    matrix = runner._staged_json(runner.MATRIX)
    result = runner.validate_design_contracts(corpus, oracle, matrix)
    assert result["status"] == "pass", result["errors"]
    assert all(result["checks"].values())
    assert matrix["future_actual_authority"]["actual_probes_currently_authorized"] is False
    assert matrix["design_execution_counts"]["compiler_or_shadow_fixture_runs"] == 0


def test_m2_a1_package_digest_binds_every_authority_and_contract_field() -> None:
    runner, package = _package()
    variants = {
        "source": ("input_bytes_source", "working_tree"),
        "input_hash": ("input_file_sha256", {**package["input_file_sha256"], runner.CORPUS: "0" * 64}),
        "a0": ("a0_design_digest", "1" * 64),
        "fixed_fingerprint": ("fixed_store_fingerprints", {**package["fixed_store_fingerprints"], "fixed_approval_store": {**package["fixed_store_fingerprints"]["fixed_approval_store"], "sha256": "2" * 64}}),
        "corpus": ("corpus_digest", "3" * 64),
        "oracle": ("oracle_digest", "4" * 64),
        "matrix": ("scenario_matrix_digest", "5" * 64),
        "authority": ("authority_boundary", "authority_expanded"),
        "actual_flag": ("actual_probes_currently_authorized", True),
    }
    for name, (field, value) in variants.items():
        tampered = copy.deepcopy(package)
        tampered[field] = value
        assert runner.verify_package(tampered)["status"] == "package_digest_mismatch", name


def test_m2_a1_self_signed_package_still_requires_external_exact_admission() -> None:
    runner, package = _package()
    self_signed = copy.deepcopy(package)
    self_signed["package_ref"] = "attacker-self-signed-m2-a1-package"
    self_signed["package_digest"] = runner.package_payload_digest(self_signed)
    assert runner.verify_package(self_signed)["status"] == "pass"
    assert runner.verify_external_admission(self_signed, None)["status"] == "package_admission_required"

    replay = copy.deepcopy(package)
    replay["package_digest"] = runner.package_payload_digest(replay)
    assert runner.verify_package(replay)["status"] == "pass"
    assert runner.verify_external_admission(replay, None)["status"] == "package_admission_required"


def test_m2_a1_repaired_gate_is_static_and_fail_closed_for_actual_authority() -> None:
    runner, package = _package()
    gate = runner.build_gate(package)
    assert gate["status"] == "design_package_repaired_pending_independent_review"
    assert gate["future_actual_admission_status"] == "package_admission_required"
    assert all(value == 0 for value in gate["execution_counts"].values())
    assert json.loads(json.dumps(gate))["package_digest"] == package["package_digest"]
