"""Run Point 01 M1-A1 independent adversarial audit on temporary SQLite only."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from sec_agent.canonical_runtime.m1_adversarial_audit import (  # noqa: E402
    run_p01,
    run_p02,
    run_p03,
    run_p04,
)
from sec_agent.canonical_runtime.m1_a1_audit_package import (  # noqa: E402
    PACKAGE_INPUT_BYTES_SOURCE,
    PACKAGE_MANIFEST_SCHEMA_VERSION,
    package_payload_digest,
    verify_package_admission,
    verify_package_manifest,
)
from sec_agent.canonical_runtime.m1_adversarial_audit_oracle import evaluate  # noqa: E402
from sec_agent.canonical_runtime.m1_adversarial_audit_canary import M1AuditAccessCanary  # noqa: E402
from sec_agent.canonical_runtime.models import canonical_digest  # noqa: E402


FIXTURE_PATH = ROOT / "configs/engineering_handoff/point01_m1_a1_adversarial_fixture_corpus_v1_0.json"
ORACLE_PATH = ROOT / "configs/engineering_handoff/point01_m1_a1_adversarial_oracle_policy_v1_0.json"
FIXED_APPROVAL_DB = ROOT / ".runtime_control/point01_m6_3_5_nvda_sec_document_parser_repaired_global_approval/canonical.sqlite"
DEFAULT_PACKAGE_OUTPUT = ROOT / "data/manifests/point01_m1_a1_adversarial_audit_package_manifest_v1_1.json"
DEFAULT_RESULT_OUTPUT = ROOT / "data/manifests/point01_m1_a1_adversarial_audit_gate_result_v1_1.json"

PACKAGE_INPUT_PATHS = (
    "configs/engineering_handoff/point01_m1_closeout_gate_manifest_v1_0.json",
    "configs/engineering_handoff/point01_m1_human_reviewer_approval_v1_0.json",
    "configs/engineering_handoff/point01_m1_rollback_recovery_drill_result_v1_0.json",
    "configs/engineering_handoff/point01_generated_json_schemas_v1_0.json",
    "data/manifests/point01_m1_closeout_gate_result_v1_0.json",
    "data/manifests/point01_m1_postgresql_conformance_sample_result_v1_0.json",
    "src/sec_agent/canonical_runtime/models.py",
    "src/sec_agent/canonical_runtime/store.py",
    "src/sec_agent/canonical_runtime/facade.py",
    "src/sec_agent/canonical_runtime/object_store.py",
    "src/sec_agent/canonical_runtime/feature_flags.py",
    "tests/contract/test_point01_canonical_models.py",
    "tests/contract/test_point01_sqlite_store.py",
    "tests/contract/test_point01_runtime_facade.py",
    "tests/contract/test_point01_legacy_objective_adapter.py",
    "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit.py",
    "src/sec_agent/canonical_runtime/m1_a1_audit_package.py",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit_oracle.py",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit_canary.py",
    "scripts/engineering/run_point01_m1_a1_adversarial_audit.py",
    "tests/contract/test_point01_m1_a1_adversarial_audit.py",
    "configs/engineering_handoff/point01_m1_a1_adversarial_fixture_corpus_v1_0.json",
    "configs/engineering_handoff/point01_m1_a1_adversarial_oracle_policy_v1_0.json",
)

EXECUTION_INPUT_PATHS = (
    "src/sec_agent/canonical_runtime/models.py",
    "src/sec_agent/canonical_runtime/store.py",
    "src/sec_agent/canonical_runtime/facade.py",
    "src/sec_agent/canonical_runtime/object_store.py",
    "src/sec_agent/canonical_runtime/feature_flags.py",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit.py",
    "src/sec_agent/canonical_runtime/m1_a1_audit_package.py",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit_oracle.py",
    "src/sec_agent/canonical_runtime/m1_adversarial_audit_canary.py",
    "scripts/engineering/run_point01_m1_a1_adversarial_audit.py",
    "tests/contract/test_point01_canonical_models.py",
    "tests/contract/test_point01_sqlite_store.py",
    "tests/contract/test_point01_runtime_facade.py",
    "tests/contract/test_point01_legacy_objective_adapter.py",
    "tests/contract/test_point01_m1_a1_adversarial_audit.py",
    "configs/engineering_handoff/point01_m1_a1_adversarial_fixture_corpus_v1_0.json",
    "configs/engineering_handoff/point01_m1_a1_adversarial_oracle_policy_v1_0.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _staged_bytes(relative_path: str) -> bytes:
    completed = subprocess.run(["git", "show", f":{relative_path}"], cwd=ROOT, capture_output=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"audit_package_input_not_staged:{relative_path}")
    return completed.stdout


def build_package_manifest() -> dict[str, Any]:
    """Build only from Git-index bytes; working-tree packages are forbidden."""
    files = {relative: hashlib.sha256(_staged_bytes(relative)).hexdigest() for relative in PACKAGE_INPUT_PATHS}
    fixed_fingerprints = {
        "fixed_approval_store": {"path": str(FIXED_APPROVAL_DB.relative_to(ROOT)).replace("\\", "/"), "sha256": _sha256(FIXED_APPROVAL_DB)},
        "canonical_or_business_store_absence_manifest": {
            "registered_paths": [],
            "status": "explicit_absence_no_M1_fixed_canonical_or_business_store_registered",
            "enforcement": "access_canary_rejects_every_nonallowlisted_store_path",
        },
    }
    payload = {
        "schema_version": PACKAGE_MANIFEST_SCHEMA_VERSION,
        "scope": "M1_A1_independent_adversarial_audit_only",
        "package_ref": "point01-m1-a1-isolated-adversarial-audit-package-v2-identity-bound",
        "authority_boundary": "temporary_explicit_sqlite_only_no_postgresql_write_no_fixed_store_open_no_network_tool_model_or_business_mutation",
        "input_bytes_source": PACKAGE_INPUT_BYTES_SOURCE,
        "a0_design_digest": _load(ROOT / "configs/engineering_handoff/point01_m1_m5_adversarial_retro_audit_design_freeze_v1_0.json")["design_digest"],
        "input_file_sha256": files,
        "fixed_store_fingerprints": fixed_fingerprints,
        "fixture_corpus_digest": canonical_digest(_load(FIXTURE_PATH)),
        "oracle_policy_digest": canonical_digest(_load(ORACLE_PATH)),
        "package_admission_ref": "point01-m1-a1-total-reviewer-package-admission:v1",
        "package_admission_required": True,
    }
    return {**payload, "package_digest": package_payload_digest(payload)}


def verify_staged_package_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    verified = verify_package_manifest(ROOT, manifest, read_bytes=lambda path: _staged_bytes(str(path.relative_to(ROOT)).replace("\\", "/")))
    if verified["status"] != "pass":
        return {
            **verified,
            "execution_working_tree_differs_from_staged": (),
            "historical_evidence_working_tree_differs_from_staged": (),
            "verification_source": "git_index_bytes_for_all_inputs_only",
        }
    working_tree_differs = [
        relative_path
        for relative_path in manifest["input_file_sha256"]
        if (ROOT / relative_path).read_bytes() != _staged_bytes(relative_path)
    ]
    execution_working_tree_differs = [relative_path for relative_path in working_tree_differs if relative_path in EXECUTION_INPUT_PATHS]
    evidence_working_tree_differs = [relative_path for relative_path in working_tree_differs if relative_path not in EXECUTION_INPUT_PATHS]
    return {
        **verified,
        "status": "pass" if verified["status"] == "pass" and not execution_working_tree_differs else "package_input_digest_mismatch",
        "execution_working_tree_differs_from_staged": tuple(execution_working_tree_differs),
        "historical_evidence_working_tree_differs_from_staged": tuple(evidence_working_tree_differs),
        "verification_source": "git_index_bytes_for_all_inputs_only",
    }


class _PytestCounter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report: Any) -> None:
        if report.when == "call":
            self.passed += int(report.passed)
            self.failed += int(report.failed)


def _run_scoped_m1_regression(*, basetemp: Path) -> dict[str, Any]:
    import pytest

    counter = _PytestCounter()
    paths = [
        "tests/contract/test_point01_canonical_models.py",
        "tests/contract/test_point01_sqlite_store.py",
        "tests/contract/test_point01_runtime_facade.py",
        "tests/contract/test_point01_legacy_objective_adapter.py",
    ]
    returncode = pytest.main(["-q", "-m", "fast_contract", "--basetemp", str(basetemp), *paths], plugins=[counter])
    return {"returncode": int(returncode), "passed_count": counter.passed, "failed_count": counter.failed, "paths": paths}


def _run_actual(package_manifest: dict[str, Any], *, run_broader: bool) -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, int]]:
    probe_functions = (run_p01, run_p02, run_p03, run_p04)
    actuals: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory(prefix="point01-m1-a1-") as temp_root:
        root = Path(temp_root)
        with M1AuditAccessCanary(allowed_roots=(root,), fixed_paths=(FIXED_APPROVAL_DB,)) as canary:
            for function in probe_functions:
                audit_root = root / function.__name__ / "m1-a1-isolated"
                if function is run_p01:
                    record = function(
                        audit_root,
                        repository_root=ROOT,
                        package_manifest=package_manifest,
                        package_verifier=verify_staged_package_manifest,
                    )
                elif function is run_p03:
                    record = function(audit_root, fixed_store_path=FIXED_APPROVAL_DB, canary=canary)
                else:
                    record = function(audit_root)
                actuals[record["probe_id"]] = record
            regression = _run_scoped_m1_regression(basetemp=root / "scoped-broader-pytest") if run_broader else {"returncode": 0, "passed_count": 0, "failed_count": 0, "paths": []}
            canary_snapshot = canary.snapshot()
    return actuals, regression, canary_snapshot


def _preflight_fail_result(
    package_manifest: dict[str, Any],
    *,
    package_current: dict[str, Any],
    admission: dict[str, Any],
) -> dict[str, Any]:
    failures = []
    if package_current["status"] != "pass":
        failures.append(package_current["status"])
    if admission["status"] != "pass":
        failures.append(admission["status"])
    return {
        "result_version": "finsight_point01_m1_a1_adversarial_audit_gate_result_v1_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "M1_A1_independent_adversarial_audit_only",
        "execution_stage": "M1_A1_audit_rejected_pending_package_identity_repair",
        "historical_m1_claim": "not_redeclared_by_A1",
        "package_ref": package_manifest.get("package_ref"),
        "package_digest": package_manifest.get("package_digest"),
        "package_digest_after": package_manifest.get("package_digest"),
        "package_stable": False,
        "package_current_verify_before": package_current,
        "package_current_verify_after": package_current,
        "package_admission_before": admission,
        "package_admission_after": admission,
        "input_snapshot": package_manifest,
        "oracle": {"status": "not_run_package_identity_preflight_fail_closed"},
        "probes": [],
        "access_canary": {"status": "not_run_package_identity_preflight_fail_closed"},
        "scoped_m1_regression": {"returncode": 0, "passed_count": 0, "failed_count": 0, "paths": [], "status": "not_run_package_identity_preflight_fail_closed"},
        "fixed_approval_store_sha256_before": _sha256(FIXED_APPROVAL_DB),
        "fixed_approval_store_sha256_after": _sha256(FIXED_APPROVAL_DB),
        "postgresql_conformance": "historical_sample_read_only_not_rerun_no_schema_write_authorized",
        "external_execution_counts": {"network": 0, "tool": 0, "model": 0, "provider": 0, "real_transport": 0, "postgresql_schema_write": 0},
        "gate_status": "fail_closed",
        "disposition": "M1_A1_audit_rejected_pending_package_identity_repair",
        "failures": failures,
        "boundary": "No M1 actual probe, scoped regression, fixed-store open, external source, M2/M6/R3 entry, or authority expansion runs without an exact external total-reviewer package admission.",
    }


def build_result(
    package_manifest: dict[str, Any],
    *,
    package_admission: dict[str, Any] | None = None,
    run_broader: bool = True,
) -> dict[str, Any]:
    fixed_before = _sha256(FIXED_APPROVAL_DB)
    package_current_before = verify_staged_package_manifest(package_manifest)
    admission_before = verify_package_admission(package_manifest, package_admission) if package_current_before["status"] == "pass" else {"status": "not_checked_package_invalid", "admission_digest": None}
    if package_current_before["status"] != "pass" or admission_before["status"] != "pass":
        return _preflight_fail_result(package_manifest, package_current=package_current_before, admission=admission_before)
    actuals, scoped_regression, canary_snapshot = _run_actual(package_manifest, run_broader=run_broader)
    fixed_after = _sha256(FIXED_APPROVAL_DB)
    oracle = evaluate(actuals, _load(ORACLE_PATH))
    oracle_checks = {row["probe_id"]: row for row in oracle["checks"]}
    probes = []
    for probe_id, actual in sorted(actuals.items()):
        check = oracle_checks[probe_id]
        probes.append(
            {
                **actual,
                "oracle_digest": canonical_digest(check),
                "oracle_status": check["status"],
                "temporary_write_count": actual["temporary_store_row_count"] + actual["temporary_object_count"],
                "fixed_or_production_write_count": 0 if fixed_before == fixed_after else -1,
                "network_count": 0,
                "tool_count": 0,
                "model_count": 0,
                "provider_count": 0,
            }
        )
    package_current_after = verify_staged_package_manifest(package_manifest)
    admission_after = verify_package_admission(package_manifest, package_admission)
    package_stable = (
        package_current_before["status"] == "pass"
        and package_current_after["status"] == "pass"
        and admission_before["status"] == "pass"
        and admission_after["status"] == "pass"
    )
    gate_failures = [row["probe_id"] for row in probes if row["oracle_status"] != "pass"]
    if fixed_before != fixed_after:
        gate_failures.append("fixed_approval_store_fingerprint_changed")
    if not package_stable:
        gate_failures.append("audit_package_current_verify_failed")
    if scoped_regression["returncode"] != 0:
        gate_failures.append("scoped_m1_regression_failed")
    return {
        "result_version": "finsight_point01_m1_a1_adversarial_audit_gate_result_v1_1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "M1_A1_independent_adversarial_audit_only",
        "execution_stage": "audit_harness_repaired_refrozen_pending_total_reviewer",
        "historical_m1_claim": "not_redeclared_by_A1",
        "package_ref": package_manifest["package_ref"],
        "package_digest": package_manifest["package_digest"],
        "package_digest_after": package_manifest["package_digest"],
        "package_stable": package_stable,
        "package_current_verify_before": package_current_before,
        "package_current_verify_after": package_current_after,
        "package_admission_before": admission_before,
        "package_admission_after": admission_after,
        "input_snapshot": package_manifest,
        "oracle": oracle,
        "probes": probes,
        "access_canary": canary_snapshot,
        "scoped_m1_regression": scoped_regression,
        "fixed_approval_store_sha256_before": fixed_before,
        "fixed_approval_store_sha256_after": fixed_after,
        "postgresql_conformance": "historical_sample_read_only_not_rerun_no_schema_write_authorized",
        "external_execution_counts": {"network": 0, "tool": 0, "model": 0, "provider": 0, "real_transport": 0, "postgresql_schema_write": 0},
        "gate_status": "pass" if not gate_failures else "fail_closed",
        "disposition": "audit_harness_repaired_refrozen_pending_total_reviewer" if not gate_failures else "M1_A1_audit_rejected_pending_package_identity_repair",
        "failures": gate_failures,
        "boundary": "No M1 completion re-declaration, M2/M6/R3 entry, external source, fixed-store mutation, business Case mutation, or legacy authority cutover is authorized by this audit.",
    }


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the isolated Point 01 M1-A1 adversarial audit.")
    parser.add_argument("--package-output", type=Path, default=DEFAULT_PACKAGE_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULT_OUTPUT)
    parser.add_argument("--package-admission", type=Path, help="Explicit package-external total-reviewer admission JSON. Omit to preflight fail-closed.")
    args = parser.parse_args()
    package_output = args.package_output if args.package_output.is_absolute() else ROOT / args.package_output
    result_output = args.output if args.output.is_absolute() else ROOT / args.output
    admission_path = args.package_admission if args.package_admission is None or args.package_admission.is_absolute() else ROOT / args.package_admission
    admission = _load(admission_path) if admission_path is not None else None
    package = build_package_manifest()
    _write(package_output, package)
    result = build_result(package, package_admission=admission)
    _write(result_output, result)
    print(json.dumps({"gate_status": result["gate_status"], "disposition": result["disposition"], "output": str(result_output)}, ensure_ascii=False))
    return 0 if result["gate_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
