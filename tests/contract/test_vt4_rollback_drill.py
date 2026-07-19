from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "releases" / "run_fin_ia_0_1_vt4_rollback_drill.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vt4_rollback_drill", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DRILL = _module()


def _build(tmp_path: Path) -> dict[str, object]:
    return DRILL.build_result(fixture_root=tmp_path / "fixture", repo_root=REPO_ROOT)


def _write_result(path: Path, value: object) -> None:
    path.write_bytes(DRILL.canonical_json_bytes(value) + b"\n")


def test_rollback_drill_disables_new_lane_preserves_audit_and_keeps_legacy_shell(tmp_path: Path) -> None:
    result = _build(tmp_path)

    assert result["schema_version"] == DRILL.SCRIPT_SCHEMA
    assert result["status"] == DRILL.RESULT_STATUS
    assert result["fixture_case"]["case_type"] == "fixture_internal"
    assert result["fixture_case"]["planning_checkpoint_state"] == "legacy_authority_retained"
    assert result["lane_disable"]["new_lane_case_read"] == {
        "status": "fail_closed",
        "status_code": 403,
        "error_code": "operation_not_admitted",
    }
    assert result["lane_disable"]["new_lane_case_create"] == {
        "status": "fail_closed",
        "status_code": 403,
        "error_code": "operation_not_admitted",
        "admitted_writes": 0,
    }
    assert result["lane_disable"]["legacy_browser_fallback"] == {
        "status": "available_shell_only",
        "status_code": 200,
        "root_mount_present": True,
    }
    assert result["authority"] == {
        "legacy_global_authority": "retained",
        "production_readiness": "not_admitted",
        "fixture_lane": "disabled_fail_closed",
        "legacy_fallback": "available_shell_only",
    }
    assert result["canonical_audit"]["preserved"] is True
    assert result["canonical_audit"]["before"] == result["canonical_audit"]["after"]
    assert result["canonical_audit"]["before"]["database"]["record_count"] > 0
    assert result["canonical_audit"]["before"]["objects"]["object_count"] == 1
    assert result["local_fixture_actions"]["disabled_new_lane_admitted_writes"] == 0
    assert all(value == 0 for value in result["boundary_counts"].values())
    assert result["operational_execution"] == "not_run"
    assert result["rg1_vertical_path"] == "not_run_separate_authority_required"
    assert result["release_admission"] == "not_granted"


def test_rollback_drill_is_deterministic_canonical_and_verifiable(tmp_path: Path) -> None:
    first = _build(tmp_path / "first")
    second = _build(tmp_path / "second")
    assert first == second

    result_path = tmp_path / "rollback.json"
    _write_result(result_path, first)
    assert DRILL.verify_result(result_path=result_path, repo_root=REPO_ROOT) == {
        "status": "pass",
        "result_sha256": first["result_sha256"],
    }

    completed = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "run", "--repo-root", str(REPO_ROOT), "--output", str(result_path)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert DRILL.verify_result(result_path=result_path, repo_root=REPO_ROOT)["status"] == "pass"


@pytest.mark.parametrize(
    ("mutate", "error"),
    [
        (
            lambda result: result["canonical_audit"]["after"]["database"].__setitem__("file_sha256", "0" * 64),
            "result_digest_invalid",
        ),
        (
            lambda result: result["authority"].__setitem__("production_readiness", "admitted"),
            "result_or_fixture_drift",
        ),
    ],
)
def test_rollback_drill_verify_detects_digest_and_semantic_tamper(
    tmp_path: Path,
    mutate: object,
    error: str,
) -> None:
    result = _build(tmp_path / "source")
    tampered = copy.deepcopy(result)
    assert callable(mutate)
    mutate(tampered)
    if error == "result_or_fixture_drift":
        tampered["result_sha256"] = DRILL.canonical_sha256(
            {key: value for key, value in tampered.items() if key != "result_sha256"}
        )
    result_path = tmp_path / "tampered.json"
    _write_result(result_path, tampered)
    with pytest.raises(DRILL.RollbackDrillError, match=error):
        DRILL.verify_result(result_path=result_path, repo_root=REPO_ROOT)
