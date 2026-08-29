from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from retrieval.dell_report_r14_common import (
    DellReportR14ContractError,
    with_result_digest,
)
from retrieval.dell_report_resource_gate_r14 import (
    FORMAL_FREE_FLOOR_BYTES,
    build_performance_receipt_r14,
    build_resource_gate_receipt_r14,
    validate_performance_receipt_r14,
    validate_resource_gate_receipt_r14,
)
from retrieval.dell_report_transaction_r14 import (
    probe_transaction_durability_r14,
)


ROOT = Path(__file__).resolve().parents[1]


def _planned() -> list[dict]:
    payload = b"planned-artifact"
    return [
        {
            "relative_path": "private/result.json",
            "exact_bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "semantic_root": hashlib.sha256(b"semantic-root").hexdigest(),
        }
    ]


def _binding_kwargs() -> dict[str, str]:
    return {
        "implementation_commit": "1" * 40,
        "implementation_tree": "2" * 40,
        "population_manifest_result_digest": "3" * 64,
        "program_receipt_result_digest": "4" * 64,
        "performance_receipt_result_digest": "5" * 64,
    }


def test_r14_performance_receipt_recomputes_status_and_rejects_resign() -> None:
    receipt = build_performance_receipt_r14(
        source_input_count=1888,
        compiled_input_count=34199,
        logical_decision_count=216522,
        elapsed_ms=30_000,
        peak_memory_bytes=256 * 1024 * 1024,
        warning_limit_ms=45_000,
        hard_limit_ms=90_000,
        hard_memory_limit_bytes=2 * 1024**3,
    )
    validate_performance_receipt_r14(receipt)
    assert receipt["status"] == "PASS"

    forged = deepcopy(receipt)
    forged["status"] = "PASS_WITH_WARNING"
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_performance_receipt_recomputation_failed",
    ):
        validate_performance_receipt_r14(forged)


def test_r14_resource_gate_uses_exact_formula_and_fails_closed_before_attempt(
    tmp_path: Path, monkeypatch
) -> None:
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    monkeypatch.setattr(
        "retrieval.dell_report_resource_gate_r14.shutil.disk_usage",
        lambda _: SimpleNamespace(total=1024**3, used=1024**3, free=1),
    )
    receipt = build_resource_gate_receipt_r14(
        attempt_root=tmp_path,
        planned_artifacts=_planned(),
        durability_capability=capability,
        **_binding_kwargs(),
        serializer_scratch_bytes=10,
        raw_capture_or_copy_bytes=20,
        replay_temp_bytes=30,
        failure_receipt_bytes=40,
        runtime_drift_bytes=50,
    )
    validate_resource_gate_receipt_r14(receipt)

    assert receipt["required_free_bytes"] == FORMAL_FREE_FLOOR_BYTES
    assert receipt["status"] == "FAIL_INSUFFICIENT_FREE_BYTES"
    assert receipt["shortfall_bytes"] == FORMAL_FREE_FLOOR_BYTES - 1
    assert not list((tmp_path / "attempt_reservations").glob("*.json"))


def test_r14_resource_gate_rejects_resigned_shortfall(tmp_path: Path, monkeypatch) -> None:
    capability = probe_transaction_durability_r14(attempt_root=tmp_path)
    monkeypatch.setattr(
        "retrieval.dell_report_resource_gate_r14.shutil.disk_usage",
        lambda _: SimpleNamespace(total=4 * 1024**3, used=1024**3, free=3 * 1024**3),
    )
    receipt = build_resource_gate_receipt_r14(
        attempt_root=tmp_path,
        planned_artifacts=_planned(),
        durability_capability=capability,
        **_binding_kwargs(),
        serializer_scratch_bytes=10,
        raw_capture_or_copy_bytes=20,
        replay_temp_bytes=30,
        failure_receipt_bytes=40,
        runtime_drift_bytes=50,
    )
    assert receipt["status"] == "PASS"
    forged = deepcopy(receipt)
    forged["observed_free_bytes"] = 0
    forged = with_result_digest(forged)
    with pytest.raises(
        DellReportR14ContractError,
        match="R14_resource_gate_receipt_recomputation_failed",
    ):
        validate_resource_gate_receipt_r14(forged)


def test_r14_preview_cli_cannot_override_frozen_performance_thresholds() -> None:
    source = (
        ROOT / "scripts/data_retrieval/run_dell_report_r14_preview.py"
    ).read_text(encoding="utf-8")

    assert "--warning-ms" not in source
    assert "--hard-ms" not in source
    assert "--hard-memory-bytes" not in source
    assert "warning_limit_ms=FROZEN_WARNING_LIMIT_MS" in source
    assert "hard_limit_ms=FROZEN_HARD_LIMIT_MS" in source
    assert "hard_memory_limit_bytes=FROZEN_HARD_MEMORY_LIMIT_BYTES" in source
