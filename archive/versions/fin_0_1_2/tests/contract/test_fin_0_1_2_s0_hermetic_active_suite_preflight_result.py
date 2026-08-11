from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / (
    "configs/releases/"
    "fin_ia_0_1_2_s0_hermetic_package_and_active_suite_runner_"
    "preflight_result_v1_0.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_preflight_package_is_content_addressed_and_readable() -> None:
    result = _load(RESULT)
    package = result["external_preflight_package"]
    root = Path(package["path"])
    assert _sha256(root / "package_manifest.json") == package["package_manifest_sha256"]
    assert _sha256(root / "verification.json") == package["verification_sha256"]
    assert _sha256(root / "runs/disposable_a/terminal_result.json") == package[
        "disposable_a_terminal_result_sha256"
    ]
    assert _sha256(root / "runs/disposable_b/terminal_result.json") == package[
        "disposable_b_terminal_result_sha256"
    ]


def test_preflight_proves_complete_capture_parity_and_current_green() -> None:
    result = _load(RESULT)
    verification = result["verification"]
    assert result["status"].startswith("pass_")
    assert verification["repository_file_count"] == 888
    assert verification["disposable_runtime_count"] == 2
    assert verification["disposable_parity"] is True
    assert verification["tests_collected_and_passed"] == [25, 25]
    assert verification["current_active_suite_all_green"] is True
    assert verification["complete_per_test_stdout_stderr_content_addressed"] is True
    assert verification["failed_output_business_promotable"] is False
    assert set(result["observed_counts"].values()) == {0}
