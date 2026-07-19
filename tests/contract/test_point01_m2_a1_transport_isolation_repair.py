"""Phase-A RC-P38-024 transport-isolation repair regressions.

All checks are synthetic/local.  They exercise fresh-process import boundaries
and the immutable repair-package validator; they never create authority or run
an admitted M2 scenario.
"""

from __future__ import annotations

from copy import deepcopy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BISECT_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_transport_isolation_bisect.py"
FREEZE_PATH = ROOT / "scripts/engineering/run_point01_m2_a1_transport_isolation_repair_freeze.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fresh_process_bisect_proves_local_planning_and_bootstrap_are_transport_free() -> None:
    bisect = _load(BISECT_PATH, "point01_m2_a1_transport_bisect")
    result = bisect.build_classification()
    probes = {row["probe_id"]: row for row in result["probes"]}
    assert set(probes) == set(bisect.PROBES)
    for probe_id in (
        "clean_python_baseline",
        "canonical_planning_local_compile",
        "legacy_bridge_runtime_facade_import",
        "actual_audit_bootstrap_import",
    ):
        assert probes[probe_id]["python_isolated_mode"] is True
        assert probes[probe_id]["transport_module_delta"] == {}
        assert probes[probe_id]["constructor_connect_request_counts"]["network_request_success_count"] == 0
    negative = probes["canary_constructor_connect_request_negative"]
    assert negative["constructor_connect_request_counts"] == {
        "transport_constructor_attempt_count": 1,
        "socket_connect_attempt_count": 1,
        "http_connect_attempt_count": 0,
        "network_request_attempt_count": 2,
        "network_request_success_count": 0,
    }
    assert result["classification"]["production_compiler_or_shadow_eager_transport"].startswith("confirmed_before_repair")
    assert result["side_effect_counters"]["new_admission_or_receipt_count"] == 0
    assert result["side_effect_counters"]["baseline_rerun_count"] == 0


def test_repair_package_binds_phase_a_authority_boundary_and_rejects_tamper() -> None:
    freeze = _load(FREEZE_PATH, "point01_m2_a1_transport_repair_freeze")
    package = freeze.build_package()
    assert freeze.verify_package(package)["status"] == "pass"
    gate = freeze.build_gate(package)
    assert gate["status"] == "repair_package_frozen_pending_independent_review_phase_b_blocked"
    assert all(gate["checks"].values())
    assert package["authority_status"]["admission_or_receipt_authorized"] is False
    assert package["authority_status"]["baseline_rerun_authorized"] is False
    assert package["zero_side_effect_counters"] == {key: 0 for key in package["zero_side_effect_counters"]}

    for field, replacement in (
        ("authority_boundary", "expanded"),
        ("input_bytes_source", "working_tree"),
        ("classification_digest", "0" * 64),
    ):
        tampered = deepcopy(package)
        tampered[field] = replacement
        assert freeze.verify_package(tampered)["status"] == "package_digest_mismatch"
