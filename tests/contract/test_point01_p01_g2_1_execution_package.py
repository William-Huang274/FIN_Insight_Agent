"""P01-G2.1 execution package and pre-authority boundary regressions."""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

from sec_agent.canonical_runtime.models import canonical_digest
from sec_agent.canonical_runtime.p01_g2_1_operational_tranche import (
    P01_G2_1_GATE_SCHEMA,
    P01_G2_1_PACKAGE_SCHEMA,
    package_payload,
    pre_authority_terminal,
    validate_execution_package,
)


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_PATH = ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_manifest_v1_0.json"
GATE_PATH = ROOT / "data/manifests/point01_p01_g2_1_operational_execution_package_gate_v1_0.json"
TRANCHE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_manifest_v1_1.json"
TRANCHE_GATE_PATH = ROOT / "data/manifests/point01_p01_g2_operational_tranche_gate_v1_1.json"
V2 = {
    "package": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_manifest_v2_10.json",
    "package_gate": ROOT / "data/manifests/point01_m2_a1_execution_ready_audit_package_freeze_gate_result_v2_10.json",
    "plan": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof.json",
    "plan_gate": ROOT / "data/manifests/point01_m2_a1_receipt_execution_plan_v1_7_execution_proof_gate.json",
    "blueprint": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof.json",
    "blueprint_gate": ROOT / "data/manifests/point01_m2_a1_baseline_authority_blueprint_v1_7_execution_proof_gate.json",
}


def _mapping(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(package: dict[str, object]) -> dict[str, object]:
    v2 = {name: _mapping(path) for name, path in V2.items()}
    return validate_execution_package(
        package,
        tranche=_mapping(TRANCHE_PATH), tranche_gate=_mapping(TRANCHE_GATE_PATH),
        v2_package=v2["package"], v2_package_gate=v2["package_gate"], v2_plan=v2["plan"],
        v2_plan_gate=v2["plan_gate"], v2_blueprint=v2["blueprint"], v2_blueprint_gate=v2["blueprint_gate"],
    )


def test_p01_g2_1_frozen_execution_package_is_exact_and_default_deny() -> None:
    package, gate = _mapping(PACKAGE_PATH), _mapping(GATE_PATH)
    assert package["schema_version"] == P01_G2_1_PACKAGE_SCHEMA
    assert package["package_digest"] == canonical_digest(package_payload(package))
    assert gate["schema_version"] == P01_G2_1_GATE_SCHEMA
    assert gate["status"] == "pass"
    assert gate["package_digest"] == package["package_digest"]
    assert _validate(package)["status"] == "pass"
    assert package["authority_boundary"]["v2_10_production_kernel_only"] is True


def test_p01_g2_1_rejects_digest_binding_and_negative_authority_drift() -> None:
    package = copy.deepcopy(_mapping(PACKAGE_PATH))
    package["exact_bindings"]["tranche_digest"] = "0" * 64
    package["package_digest"] = canonical_digest(package_payload(package))
    assert _validate(package)["status"] == "fail_closed"
    package = copy.deepcopy(_mapping(PACKAGE_PATH))
    package["cases"][1]["authority"] = 1
    package["package_digest"] = canonical_digest(package_payload(package))
    assert _validate(package)["status"] == "fail_closed"


def test_p01_g2_1_pre_authority_terminal_taxonomy_is_fixed() -> None:
    assert pre_authority_terminal(case_id="g2-wrong-package-or-approval") == "pre_authority_typed_deny:package_or_approval_mismatch"
    assert pre_authority_terminal(case_id="g2-stale-input-version-drift") == "typed_stop:superseded_pack_version_or_pack_not_fresh"
    assert pre_authority_terminal(case_id="g2-unauthorized-transport") == "typed_stop:shadow_scope_violation"


def test_p01_g2_1_runner_is_default_deny_without_creating_case_root(monkeypatch: object, tmp_path: Path) -> None:
    script = ROOT / "scripts/engineering/run_point01_p01_g2_1_execute_tranche.py"
    spec = importlib.util.spec_from_file_location("p01_g2_1_runner_test", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "P01_ROOT", tmp_path / "formal")
    assert module.main([]) == 2
    assert not (tmp_path / "formal").exists()


def test_p01_g2_1_transport_probe_is_permission_only_no_network_success(tmp_path: Path) -> None:
    script = ROOT / "scripts/engineering/run_point01_p01_g2_1_execute_tranche.py"
    spec = importlib.util.spec_from_file_location("p01_g2_1_runner_transport", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    v2 = {name: _mapping(path) for name, path in V2.items()}
    package = _mapping(PACKAGE_PATH)
    result = module._run_pre_authority_probe("g2-unauthorized-transport", case_root=tmp_path / "probe", package=package, v2=v2)
    assert result["terminal"] == "typed_stop:shadow_scope_violation"
    assert result["counts"]["valid_authority_issue_count"] == 0
    assert result["counts"]["network_success"] == 0
    assert result["details"]["canary"]["counts"]["network_request_attempt_count"] == 1
