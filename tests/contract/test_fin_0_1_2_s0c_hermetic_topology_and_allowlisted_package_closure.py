from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
from typing import Any

import pytest

import sec_agent.hermetic_test_runner as runner
from sec_agent.hermetic_test_runner import (
    HermeticTestRunnerError,
    build_content_addressed_package,
    compile_repository_inventory,
    validate_host_current_program_projection,
)


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(repository: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repository,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    _write(repository / ".gitignore", ".codex_runtime/\n")
    _write(repository / "runner.py", "RUNNER = True\n")
    _write(repository / "tests/pass.py", "def test_pass():\n    assert True\n")
    _write_json(repository / "configs/seed.json", {"binding_ref": "semantic:v1"})
    _git(repository, "add", ".gitignore", "runner.py", "tests/pass.py", "configs/seed.json")
    _git(
        repository,
        "-c",
        "user.name=FIN Test",
        "-c",
        "user.email=fin-test@example.invalid",
        "commit",
        "--quiet",
        "-m",
        "fixture",
    )
    return repository


def _manifest(*, seed_paths: list[str] | None = None) -> dict[str, Any]:
    return {
        "manifest_id": "s0c-inventory-fixture",
        "suites": [
            {
                "selected": True,
                "test_paths": ["tests/pass.py"],
            }
        ],
        "hermetic_package_policy": {
            "repository_inventory": "tracked_plus_typed_allowlist_closure",
            "required_runner_files": ["runner.py"],
            "repository_seed_paths": seed_paths or ["configs/seed.json"],
            "repository_prefixes": [],
            "external_read_only_bindings": [],
            "repository_reference_policy": {
                "schema_version": "fin_ia_hermetic_repository_reference_policy_v1_0",
                "tracked_repository_paths_allowed": True,
                "explicit_allowlist": [],
                "non_repository_reference_fields": [],
                "forbidden_prefixes": [".codex_runtime"],
                "untracked_or_ignored_reference_behavior": "fail_closed",
                "unknown_reference_behavior": "fail_closed",
                "traversal_or_symlink_escape_behavior": "fail_closed",
                "semantic_or_external_reference_behavior": "observe_not_package",
            },
        },
    }


def test_tracked_and_typed_allowlisted_reference_closure_is_stable(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    _write_json(repository / "configs/tracked.json", {"value": 1})
    _git(repository, "add", "configs/tracked.json")
    _write_json(repository / "explicit/input.json", {"value": 2})
    _write_json(
        repository / "configs/seed.json",
        {
            "z_ref": "explicit/input.json",
            "a_ref": "configs/tracked.json",
            "binding_ref": "semantic-contract:v1",
        },
    )
    manifest = _manifest()
    manifest["hermetic_package_policy"]["repository_reference_policy"][
        "explicit_allowlist"
    ] = [
        {
            "path": "explicit/input.json",
            "sha256": _sha256(repository / "explicit/input.json"),
            "classification": "bounded_test_input",
            "reason": "proves typed untracked input admission",
        }
    ]

    inventory = compile_repository_inventory(repository, manifest)
    assert Path("configs/tracked.json") in inventory.paths
    assert Path("explicit/input.json") in inventory.paths
    assert inventory.explicit_allowlist_paths == ("explicit/input.json",)
    assert inventory.semantic_or_external_reference_count == 1

    permuted = deepcopy(manifest)
    permuted["hermetic_package_policy"]["repository_seed_paths"] = [
        "configs/seed.json"
    ]
    assert (
        compile_repository_inventory(repository, permuted).closure_digest
        == inventory.closure_digest
    )


@pytest.mark.parametrize(
    ("reference", "expected_code"),
    [
        (
            "scratch/untracked.json",
            "hermetic_repository_reference_untracked_or_ignored",
        ),
        ("missing/unknown.json", "hermetic_repository_reference_unknown"),
        ("../outside.json", "hermetic_repository_reference_traversal"),
        (".codex_runtime/capture.json", "hermetic_repository_forbidden_path"),
    ],
)
def test_nonallowlisted_reference_classes_fail_before_object_storage(
    tmp_path: Path,
    reference: str,
    expected_code: str,
) -> None:
    repository = _repository(tmp_path)
    if reference == "scratch/untracked.json":
        _write_json(repository / reference, {"untracked": True})
    if reference == ".codex_runtime/capture.json":
        _write_json(repository / reference, {"ignored": True})
    _write_json(
        repository / "configs/seed.json",
        {"repository_payload_ref": reference},
    )
    with pytest.raises(HermeticTestRunnerError, match=expected_code):
        compile_repository_inventory(repository, _manifest())


def test_symlink_escape_fails_before_object_storage(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    outside = tmp_path / "outside.json"
    _write_json(outside, {"outside": True})
    link = repository / "links/escape.json"
    link.parent.mkdir(parents=True)
    try:
        os.symlink(outside, link)
    except OSError:
        with pytest.raises(
            HermeticTestRunnerError,
            match="hermetic_repository_reference_symlink_escape",
        ):
            runner._assert_resolved_repository_path(repository, outside)
        return
    _write_json(
        repository / "configs/seed.json",
        {"repository_payload_ref": "links/escape.json"},
    )
    manifest = _manifest()
    manifest["hermetic_package_policy"]["repository_reference_policy"][
        "explicit_allowlist"
    ] = [
        {
            "path": "links/escape.json",
            "sha256": _sha256(outside),
            "classification": "negative_fixture",
            "reason": "symlink escape must never be admitted",
        }
    ]
    with pytest.raises(
        HermeticTestRunnerError,
        match="hermetic_repository_reference_symlink_escape",
    ):
        compile_repository_inventory(repository, manifest)


def test_frozen_inventory_materializes_without_git_and_detects_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = _repository(tmp_path)
    package_root = tmp_path / "package"
    package_root.mkdir()
    manifest = _manifest()
    package = build_content_addressed_package(
        repository_root=repository,
        manifest=manifest,
        package_root=package_root,
    )
    assert package["repository_inventory_closure"][
        "explicit_allowlist_path_count"
    ] == 0
    assert len(package["frozen_repository_inventory_digest"]) == 64

    def _git_forbidden(*args: Any, **kwargs: Any) -> bytes:
        raise AssertionError("disposable materialization must not call Git")

    monkeypatch.setattr(runner, "_git_output", _git_forbidden)
    runner._materialize_package(package_root, package, tmp_path / "disposable")

    mutated = deepcopy(package)
    mutated["repository_files"][0]["sha256"] = "0" * 64
    with pytest.raises(
        HermeticTestRunnerError,
        match="hermetic_frozen_inventory_digest_mismatch",
    ):
        runner._materialize_package(
            package_root,
            mutated,
            tmp_path / "mutated_disposable",
        )


def _projection_repository(tmp_path: Path) -> tuple[Path, str]:
    repository = tmp_path / "projection_repository"
    next_action = "FIN-0.1.2-S0C-T03-CORRECTIVE-PROOF"
    sources = {
        "program_backlog": "state/program.json",
        "S4_backlog": "state/s4.json",
        "context_pack": "state/context.md",
        "capability_ledger": "state/capability.jsonl",
        "root_cause_ledger": "state/root.jsonl",
        "external_pattern_ledger": "state/pattern.jsonl",
    }
    _write_json(
        repository / sources["program_backlog"],
        {
            "active_slice": "FIN_0_1_2_S0_CORRECTIVE_TEST_PACKAGING_CONTRACT",
            "next_action": {"item_id": next_action},
            "current_truth": {
                "FIN_0_1_2_S2_entry_authorized": False,
                "FIN_0_1_release_qualified": False,
            },
        },
    )
    _write_json(repository / sources["S4_backlog"], {"current_next_action": next_action})
    _write(repository / sources["context_pack"], f"current next=`{next_action}`\n")
    _write(
        repository / sources["capability_ledger"],
        json.dumps(
            {
                "capability_id": "s0c-current",
                "current_next": next_action,
                "stage_acceptance": {
                    "S0C_T02": "pass",
                    "S0C_T03": "ready_not_started",
                },
            }
        )
        + "\n",
    )
    _write(
        repository / sources["root_cause_ledger"],
        json.dumps(
            {
                "issue_id": "RC-test",
                "status": "open",
                "full_chain_blocker": True,
                "allowed_run_scopes": [next_action],
            }
        )
        + "\n",
    )
    _write(
        repository / sources["external_pattern_ledger"],
        json.dumps({"pattern_id": "pattern-test", "status": "implemented_T03_pending"})
        + "\n",
    )
    projection_ref = "configs/current_projection.json"
    _write_json(
        repository / projection_ref,
        {
            "schema_version": "fin_ia_0_1_2_current_program_projection_v1_0",
            "projection_id": "fixture-current-projection",
            "recorded_at": "2026-08-01T00:00:00+08:00",
            "status": "current_host_validated_T02_pass_T03_ready",
            "source_paths": sources,
            "expectations": {
                "active_slice": "FIN_0_1_2_S0_CORRECTIVE_TEST_PACKAGING_CONTRACT",
                "current_next_action": next_action,
                "capability_id": "s0c-current",
                "capability_stage_acceptance": {
                    "S0C_T02": "pass",
                    "S0C_T03": "ready_not_started",
                },
                "open_issue_ids": ["RC-test"],
                "pattern_id": "pattern-test",
                "pattern_status": "implemented_T03_pending",
            },
            "package_governance": {
                "host_sources_packaged": False,
                "projection_document_packaged": True,
                "disposable_git_required": False,
                "failed_package_business_promotable": False,
                "raw_content_addressed_evidence_preserved": True,
                "restricted_review_before_share_or_promotion": True,
            },
        },
    )
    return repository, projection_ref


def test_legacy_projection_snapshot_does_not_reclaim_current_authority(
    tmp_path: Path,
) -> None:
    repository, projection_ref = _projection_repository(tmp_path)
    assert validate_host_current_program_projection(
        repository, projection_ref
    ) == Path(projection_ref)
    _write_json(
        repository / "state/s4.json",
        {"current_next_action": "stale-historical-next"},
    )
    assert validate_host_current_program_projection(
        repository, projection_ref
    ) == Path(projection_ref)
