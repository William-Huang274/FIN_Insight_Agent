from __future__ import annotations

import json
from pathlib import Path

from sec_agent.hermetic_test_runner import (
    ContentAddressedStore,
    read_object,
    run_hermetic_active_suite,
)


ROOT = Path(__file__).resolve().parents[2]
PLUGIN = ROOT / "src/sec_agent/hermetic_test_capture.py"


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _mini_manifest() -> dict:
    pass_path = "tests/test_current_pass.py"
    historical_path = "tests/test_historical_failure.py"
    return {
        "schema_version": "fin_ia_active_test_suite_manifest_v1_0",
        "manifest_id": "mini-hermetic-runner-proof",
        "status": "runner_migrated",
        "historical_failures_are_ignored": False,
        "suites": [
            {
                "suite_id": "event",
                "proof_class": "immutable_event",
                "selected": True,
                "gates_current_release": False,
                "assertion_surfaces": ["event_status"],
                "test_paths": [pass_path],
            },
            {
                "suite_id": "projection",
                "proof_class": "current_projection",
                "selected": True,
                "gates_current_release": True,
                "assertion_surfaces": ["current_next_action"],
                "test_paths": [pass_path],
            },
            {
                "suite_id": "runtime",
                "proof_class": "current_runtime",
                "selected": True,
                "gates_current_release": True,
                "assertion_surfaces": ["current_code_digest"],
                "test_paths": [pass_path],
            },
            {
                "suite_id": "historical",
                "proof_class": "historical_audit",
                "selected": True,
                "gates_current_release": False,
                "assertion_surfaces": ["historical_output_digest"],
                "test_paths": [historical_path],
            },
            {
                "suite_id": "release",
                "proof_class": "release_gate",
                "selected": True,
                "gates_current_release": True,
                "assertion_surfaces": ["release_gate_truth"],
                "test_paths": [pass_path],
            },
        ],
        "runner_policy": {
            "manifest_selection_is_authoritative": True,
            "unlisted_historical_test_failure_is_visible_but_not_implicitly_current": True,
            "listed_current_test_failure_is_blocking": True,
            "bulk_relax_historical_assertions_for_green_forbidden": True,
            "runner_migration_completed": True,
        },
        "hermetic_package_policy": {
            "required_runner_files": ["src/sec_agent/hermetic_test_capture.py"],
            "capture_plugin_path": "src/sec_agent/hermetic_test_capture.py",
            "external_read_only_bindings": [],
        },
        "next_action": "mini",
    }


def test_content_store_preserves_complete_unicode_bytes(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    value = ("完整输出" * 2000).encode("utf-8")
    ref = store.put_bytes(value)
    assert ref.bytes == len(value)
    assert read_object(tmp_path, ref.as_dict()) == value


def test_runner_keeps_historical_failure_visible_without_blocking_current_gate(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "repository"
    _write(
        repository / "tests/test_current_pass.py",
        "def test_current():\n    print('CURRENT-' + 'x' * 5000)\n    assert True\n",
    )
    _write(
        repository / "tests/test_historical_failure.py",
        "import sys\n\ndef test_historical():\n    print('STDOUT-' + 'y' * 6000)\n    print('STDERR-' + 'z' * 7000, file=sys.stderr)\n    assert False, 'historical remains visible'\n",
    )
    plugin_relative = Path("src/sec_agent/hermetic_test_capture.py")
    _write(repository / plugin_relative, PLUGIN.read_text(encoding="utf-8"))
    manifest = _mini_manifest()
    manifest_path = repository / "manifest.json"
    _write(manifest_path, json.dumps(manifest, ensure_ascii=False))
    output = tmp_path / "package"
    result = run_hermetic_active_suite(
        repository_root=repository,
        manifest_path=manifest_path,
        output_root=output,
        repository_paths=(
            Path("tests/test_current_pass.py"),
            Path("tests/test_historical_failure.py"),
            plugin_relative,
        ),
    )
    assert result["status"] == "pass"
    assert result["disposable_parity"] is True
    assert result["current_active_suite_all_green"] is True
    terminal = json.loads(
        (output / "runs/disposable_a/terminal_result.json").read_text(encoding="utf-8")
    )
    historical = next(row for row in terminal["tests"] if "historical" in row["nodeid"])
    assert historical["outcome"] == "failed"
    assert historical["gates_current_release"] is False
    assert len(read_object(output, historical["stdout"])) > 6000
    assert len(read_object(output, historical["stderr"])) > 7000
    assert b"historical remains visible" in read_object(output, historical["detail"])
