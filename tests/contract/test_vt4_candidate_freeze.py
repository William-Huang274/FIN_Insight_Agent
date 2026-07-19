from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "releases" / "freeze_fin_ia_0_1_vt4_candidate.py"
CONTRACT_PATH = (
    REPO_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_candidate_freeze_contract_v1_0.json"
)


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("vt4_candidate_freeze", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FREEZE = _module()


def _run(root: Path, *args: str) -> None:
    completed = subprocess.run(args, cwd=root, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(FREEZE.canonical_json_bytes(value) + b"\n")


def _fixture_contract() -> dict[str, object]:
    return {
        "schema_version": FREEZE.CONTRACT_SCHEMA,
        "contract_id": "test:vt4-candidate-freeze",
        "version": "1.0",
        "status": "fixture_shadow_internal_only_not_release_admission",
        "candidate_profile": {
            "path": "configs/profile.json",
            "required_schema_version": "profile-v1",
            "required_status": "fixture_only",
            "digest_algorithm": "sha256",
            "canonical_serialization": "json_sort_keys_utf8_compact",
        },
        "input_inventory": {
            "digest_algorithm": "sha256",
            "path_policy": "repository_relative_posix_no_dotdot_no_duplicates",
            "source": ["scripts/source.py"],
            "config": ["configs/contract.json", "configs/profile.json"],
            "frontend": ["frontend/view.tsx"],
            "test": ["tests/test_slice.py"],
        },
        "allowed_route_surface": {
            "browser_routes": ["/tasks", "/cases/:caseId/deliverable"],
            "api_routes": ["GET /api/v1/cases/{case_id}", "POST /api/v1/cases/{case_id}/deliverables"],
        },
        "authority": {
            "development_mode": "fixture_shadow_internal_only",
            "runtime_admission": "not_granted",
            "production_readiness": "not_admitted",
            "legacy_global_authority": "retained",
            "release_candidate_not_a_commit_or_release": True,
        },
        "hard_boundaries": {name: 0 for name in sorted(FREEZE.REQUIRED_BOUNDARY_KEYS)},
        "release_blockers": {
            "p07_5": {
                "status": "blocked",
                "reason": "RG1 through RG5 remain required.",
                "release_admission": "not_issued",
            },
            "rg1_vertical_path": {
                "status": "blocked",
                "exact_package_entry_to_leaf_identity": "entry_to_adapter_to_subprocess_to_clean_child",
                "identity_status": "unproven_hard_blocker",
                "bounded_operational_run_debt": {
                    "status": "not_run_separate_authority_required",
                    "required_run_count": 1,
                    "authority": "not_granted",
                    "required_persisted_results": ["actual", "oracle", "reviewer", "workbench"],
                },
            },
        },
        "prohibitions": {
            "new_gate_family": False,
            "release_admission": False,
            "operational_execution": False,
            "network_model_provider_tool_execution": False,
        },
    }


def _fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    root.mkdir()
    _write_json(root / "configs" / "profile.json", {"schema_version": "profile-v1", "status": "fixture_only", "value": "p36"})
    _write_json(root / "configs" / "contract.json", _fixture_contract())
    for relative, contents in {
        "scripts/source.py": "VALUE = 'fixture'\n",
        "frontend/view.tsx": "export const View = 'fixture';\n",
        "tests/test_slice.py": "def test_fixture():\n    assert True\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")
    _run(root, "git", "init", "--quiet")
    _run(root, "git", "config", "user.email", "fixture@example.test")
    _run(root, "git", "config", "user.name", "Fixture")
    _run(root, "git", "add", ".")
    _run(root, "git", "commit", "--quiet", "-m", "fixture")
    return root, root / "configs" / "contract.json"


def _freeze(root: Path, contract_path: Path, manifest_path: Path) -> dict[str, object]:
    manifest = FREEZE.build_manifest(root=root, contract_path=contract_path, output_path=manifest_path)
    FREEZE.write_manifest(manifest_path, manifest)
    return manifest


def test_shipped_contract_binds_the_vt1_vt4_slice_and_release_boundaries() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    _, inventory, routes, boundaries, blockers = FREEZE.validate_contract(REPO_ROOT, CONTRACT_PATH)

    assert set(inventory) == {"source", "config", "frontend", "test"}
    assert CONTRACT_PATH.relative_to(REPO_ROOT).as_posix() in inventory["config"]
    assert SCRIPT_PATH.relative_to(REPO_ROOT).as_posix() in inventory["source"]
    assert "tests/contract/test_vt4_candidate_freeze.py" in inventory["test"]
    assert routes == contract["allowed_route_surface"]
    assert boundaries == {name: 0 for name in sorted(FREEZE.REQUIRED_BOUNDARY_KEYS)}
    assert blockers["p07_5"]["status"] == "blocked"
    assert blockers["rg1_vertical_path"]["exact_package_entry_to_leaf_identity"] == "entry_to_adapter_to_subprocess_to_clean_child"
    assert blockers["rg1_vertical_path"]["bounded_operational_run_debt"]["required_run_count"] == 1


def test_freeze_is_deterministic_canonical_and_verifiable(tmp_path: Path) -> None:
    root, contract_path = _fixture_repo(tmp_path)
    first_path = root / "out" / "first.json"
    second_path = root / "out" / "second.json"

    first = _freeze(root, contract_path, first_path)
    second = _freeze(root, contract_path, second_path)

    assert first == second
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first["candidate_profile"]["file_sha256"]
    assert first["candidate_profile"]["canonical_json_sha256"]
    assert FREEZE.verify_manifest(root=root, contract_path=contract_path, manifest_path=first_path)["status"] == "pass"


def test_verify_fails_closed_for_manifest_and_allowlisted_byte_tamper(tmp_path: Path) -> None:
    root, contract_path = _fixture_repo(tmp_path)
    manifest_path = root / "out" / "candidate.json"
    _freeze(root, contract_path, manifest_path)

    (root / "scripts" / "source.py").write_text("VALUE = 'tampered'\n", encoding="utf-8")
    with pytest.raises(FREEZE.FreezeError, match="manifest_current_bytes_or_contract_drift"):
        FREEZE.verify_manifest(root=root, contract_path=contract_path, manifest_path=manifest_path)

    _freeze(root, contract_path, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["input_inventory"]["files"]["unallowlisted.py"] = "0" * 64
    manifest["manifest_sha256"] = FREEZE.canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    )
    _write_json(manifest_path, manifest)
    with pytest.raises(FREEZE.FreezeError, match="manifest_current_bytes_or_contract_drift"):
        FREEZE.verify_manifest(root=root, contract_path=contract_path, manifest_path=manifest_path)


def test_git_dirty_byte_counts_are_observed_without_a_clean_tree_claim(tmp_path: Path) -> None:
    root, contract_path = _fixture_repo(tmp_path)
    (root / "scripts" / "source.py").write_text("VALUE = 'staged'\n", encoding="utf-8")
    _run(root, "git", "add", "scripts/source.py")
    (root / "frontend" / "view.tsx").write_text("export const View = 'working';\n", encoding="utf-8")
    (root / "untracked.bin").write_bytes(b"untracked-bytes")

    manifest = _freeze(root, contract_path, root / "out" / "candidate.json")
    git_snapshot = manifest["git_snapshot"]

    assert git_snapshot["observation"] == "read_only_status_snapshot_no_clean_tree_claim"
    assert git_snapshot["release_commit_claimed"] is False
    assert git_snapshot["git_head"] != "unavailable"
    assert git_snapshot["git_branch"] != "unavailable"
    assert git_snapshot["staged"]["byte_count"] > 0
    assert git_snapshot["working"]["byte_count"] > 0
    assert git_snapshot["untracked"]["byte_count"] == len(b"untracked-bytes")


@pytest.mark.parametrize(
    ("mutator", "error"),
    [
        (
            lambda contract: contract["input_inventory"]["test"].append("tests/test_slice.py"),
            "input_inventory_not_sorted|duplicate_allowlisted_path",
        ),
        (
            lambda contract: contract["input_inventory"]["source"].__setitem__(0, "../outside.py"),
            "invalid_repository_path",
        ),
        (
            lambda contract: contract["hard_boundaries"].__setitem__("network_calls", 1),
            "hard_boundary_opened",
        ),
    ],
)
def test_contract_fails_closed_for_duplicate_traversal_and_boundary_opening(
    tmp_path: Path,
    mutator: object,
    error: str,
) -> None:
    root, contract_path = _fixture_repo(tmp_path)
    contract = copy.deepcopy(json.loads(contract_path.read_text(encoding="utf-8")))
    assert callable(mutator)
    mutator(contract)
    _write_json(contract_path, contract)

    with pytest.raises(FREEZE.FreezeError, match=error):
        FREEZE.build_manifest(root=root, contract_path=contract_path, output_path=root / "out" / "candidate.json")
