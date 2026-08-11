from __future__ import annotations

import ast
import importlib.util
import json
import sys
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from sec_agent.canonical_runtime.m1_adversarial_audit import run_p01, run_p02, run_p03, run_p04
from sec_agent.canonical_runtime.m1_adversarial_audit_canary import M1AuditAccessCanary
from sec_agent.canonical_runtime.m1_adversarial_audit_oracle import evaluate
from sec_agent.canonical_runtime.models import canonical_digest


ROOT = Path(__file__).resolve().parents[2]
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m1_a1_adversarial_oracle_policy_v1_0.json"


@lru_cache(maxsize=1)
def _runner_module():
    path = ROOT / "scripts/engineering/run_point01_m1_a1_adversarial_audit.py"
    spec = importlib.util.spec_from_file_location("point01_m1_a1_audit_runner", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _package_manifest() -> dict:
    return _runner_module().build_package_manifest()


def _synthetic_admission(package: dict) -> dict:
    """Injected test-only authority; it is never a real reviewer receipt."""
    return {
        "schema_version": "finsight_point01_m1_a1_external_package_admission_v1_0",
        "admission_ref": package["package_admission_ref"],
        "reviewer_identity": "william/003/total_reviewer",
        "decision": "admitted",
        "package_manifest_schema_version": package["schema_version"],
        "package_ref": package["package_ref"],
        "package_digest": package["package_digest"],
        "scope": package["scope"],
        "authority_boundary": package["authority_boundary"],
    }


def _actuals(tmp_path: Path) -> dict[str, dict]:
    runner = _runner_module()
    package = _package_manifest()
    fixed = ROOT / ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
    with M1AuditAccessCanary(allowed_roots=(tmp_path,), fixed_paths=(fixed,)) as canary:
        return {
            "A0-M1-P01": run_p01(
                tmp_path / "p01" / "m1-a1-isolated",
                repository_root=ROOT,
                package_manifest=package,
                package_verifier=runner.verify_staged_package_manifest,
            ),
            "A0-M1-P02": run_p02(tmp_path / "p02" / "m1-a1-isolated"),
            "A0-M1-P03": run_p03(tmp_path / "p03" / "m1-a1-isolated", fixed_store_path=fixed, canary=canary),
            "A0-M1-P04": run_p04(tmp_path / "p04" / "m1-a1-isolated"),
        }


def test_actual_module_has_no_oracle_import_or_ambient_authority_path() -> None:
    source_path = ROOT / "src/sec_agent/canonical_runtime/m1_adversarial_audit.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imports = "\n".join(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
        for alias in node.names
    )
    source = source_path.read_text(encoding="utf-8")
    assert "m1_adversarial_audit_oracle" not in imports
    assert "os.environ" not in source
    assert ".runtime_control" not in source
    assert "Path.home" not in source


def test_package_excludes_post_run_governance_documents() -> None:
    runner = _runner_module()
    assert all(not path.startswith("docs/") for path in runner.PACKAGE_INPUT_PATHS)
    assert "data/manifests/point01_m1_a1_adversarial_audit_gate_result_v1_0.json" not in runner.PACKAGE_INPUT_PATHS
    assert "data/manifests/point01_m1_a1_adversarial_audit_package_manifest_v1_0.json" not in runner.PACKAGE_INPUT_PATHS


def test_package_identity_is_canonical_and_git_index_only() -> None:
    runner = _runner_module()
    package = _package_manifest()
    assert package["input_bytes_source"] == "git_index"
    assert package["package_admission_required"] is True
    assert package["package_digest"] == runner.package_payload_digest(package)
    assert runner.verify_staged_package_manifest(package)["status"] == "pass"


def test_package_tamper_variants_fail_closed_before_actual_execution() -> None:
    runner = _runner_module()
    package = _package_manifest()
    cases: dict[str, dict] = {}

    changed_source = deepcopy(package)
    changed_source["input_bytes_source"] = "working_tree"
    cases["source_without_digest"] = changed_source

    changed_file_hash = deepcopy(package)
    first_path = sorted(changed_file_hash["input_file_sha256"])[0]
    changed_file_hash["input_file_sha256"][first_path] = "0" * 64
    cases["file_hash_without_digest"] = changed_file_hash

    changed_source_and_hashes = deepcopy(package)
    changed_source_and_hashes["input_bytes_source"] = "working_tree"
    changed_source_and_hashes["input_file_sha256"] = {
        relative: runner._sha256(ROOT / relative)
        for relative in changed_source_and_hashes["input_file_sha256"]
    }
    cases["source_and_hashes_without_digest"] = changed_source_and_hashes

    for name, tampered in cases.items():
        verification = runner.verify_staged_package_manifest(tampered)
        result = runner.build_result(tampered, run_broader=False)
        assert verification["status"] == "package_digest_mismatch", name
        assert result["gate_status"] == "fail_closed", name
        assert result["probes"] == [], name
        assert result["external_execution_counts"]["network"] == 0, name

    self_signed = deepcopy(package)
    self_signed["package_ref"] = "attacker-self-signed-package"
    self_signed["package_digest"] = runner.package_payload_digest(self_signed)
    assert runner.verify_staged_package_manifest(self_signed)["status"] == "pass"
    no_admission = runner.build_result(self_signed, run_broader=False)
    assert no_admission["gate_status"] == "fail_closed"
    assert no_admission["package_admission_before"]["status"] == "package_admission_required"
    assert no_admission["probes"] == []

    stale_admission = runner.build_result(self_signed, package_admission=_synthetic_admission(package), run_broader=False)
    assert stale_admission["gate_status"] == "fail_closed"
    assert stale_admission["package_admission_before"]["status"] == "package_admission_binding_mismatch"


def test_package_admission_is_external_to_payload_but_exactly_bound() -> None:
    runner = _runner_module()
    package = _package_manifest()
    admission = _synthetic_admission(package)
    verification = runner.verify_package_admission(package, admission)
    assert verification["status"] == "pass"
    assert verification["admission_digest"] == canonical_digest(admission)


def test_p01_to_p04_actual_paths_and_independent_oracle(tmp_path) -> None:
    actuals = _actuals(tmp_path)
    policy = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    outcome = evaluate(actuals, policy)
    assert outcome["status"] == "pass"
    assert actuals["A0-M1-P01"]["package_tamper_stop"] == "package_digest_mismatch"
    assert actuals["A0-M1-P01"]["event_payload_digest_tamper"]["mutation_status"] == "write_rejected"
    assert actuals["A0-M1-P02"]["duplicate_idempotent"] is True
    assert "audit_fixed_store_path_forbidden" in actuals["A0-M1-P03"]["fixed_store_open_stop"]
    assert "audit_transport_constructor_forbidden" in actuals["A0-M1-P03"]["transport_constructor_stop"]
    assert actuals["A0-M1-P04"]["event_sequence_tamper"]["mutation_status"] == "write_rejected"
    assert actuals["A0-M1-P04"]["recovery_projection_matches"] is True


def test_oracle_mutation_cannot_change_actual_result(tmp_path) -> None:
    actuals = _actuals(tmp_path)
    policy = json.loads(ORACLE_PATH.read_text(encoding="utf-8"))
    actual_digest_before = actuals["A0-M1-P01"]["actual_digest"]
    tampered = deepcopy(policy)
    tampered["required_actual_assertions"]["A0-M1-P01"]["package_tamper_stop"] = "attacker_supplied_reason"
    assert evaluate(actuals, tampered)["status"] == "fail_closed"
    assert actuals["A0-M1-P01"]["actual_digest"] == actual_digest_before


def test_gate_builds_only_temporary_actual_stores_and_preserves_fixed_fingerprint(tmp_path) -> None:
    runner = _runner_module()
    package = _package_manifest()
    before = runner._sha256(runner.FIXED_APPROVAL_DB)
    result = runner.build_result(package, package_admission=_synthetic_admission(package), run_broader=False)
    after = runner._sha256(runner.FIXED_APPROVAL_DB)
    assert result["gate_status"] == "pass"
    assert before == after == result["fixed_approval_store_sha256_before"] == result["fixed_approval_store_sha256_after"]
    assert result["external_execution_counts"] == {"network": 0, "tool": 0, "model": 0, "provider": 0, "real_transport": 0, "postgresql_schema_write": 0}
