"""Build and verify the bounded VT4 P07.0 internal fixture candidate manifest.

The sidecar is intentionally stdlib-only. It reads local bytes and optional Git
metadata; it never imports product runtime code or invokes network, model,
provider, tool, operational, or release-admission behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping


SCRIPT_SCHEMA = "fin_ia_0_1_vt4_candidate_freeze_manifest_v1_0"
CONTRACT_SCHEMA = "fin_ia_0_1_vt4_candidate_freeze_contract_v1_0"
DEFAULT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACT = (
    DEFAULT_ROOT
    / "configs"
    / "releases"
    / "fin_ia_0_1_vt4_candidate_freeze_contract_v1_0.json"
)
REQUIRED_BOUNDARY_KEYS = frozenset(
    {
        "network_calls",
        "model_calls",
        "provider_calls",
        "tool_invocations",
        "paid_full_chain",
        "full_chain",
        "real_business_case_write",
        "release_admission",
    }
)


class FreezeError(ValueError):
    """Raised when the freeze contract or a candidate cannot be proven closed."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return the single JSON representation used for digests and output."""
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def _as_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise FreezeError(f"mapping_required:{label}")
    return value


def _as_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise FreezeError(f"string_list_required:{label}")
    return list(value)


def _normalized_relative_path(root: Path, value: str, label: str) -> str:
    if not value or "\\" in value:
        raise FreezeError(f"invalid_repository_path:{label}:{value}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise FreezeError(f"invalid_repository_path:{label}:{value}")
    candidate = root.joinpath(*path.parts)
    try:
        candidate.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise FreezeError(f"repository_path_escapes_root:{label}:{value}") from exc
    return path.as_posix()


def _read_json(path: Path, label: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreezeError(f"json_read_failed:{label}:{path}") from exc
    return _as_mapping(value, label)


def _relative_to_root(root: Path, path: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _inventory_from_contract(root: Path, contract: Mapping[str, Any]) -> dict[str, list[str]]:
    inventory = _as_mapping(contract.get("input_inventory"), "input_inventory")
    if inventory.get("digest_algorithm") != "sha256":
        raise FreezeError("unsupported_input_digest_algorithm")
    if inventory.get("path_policy") != "repository_relative_posix_no_dotdot_no_duplicates":
        raise FreezeError("unsupported_input_path_policy")

    categories = ("source", "config", "frontend", "test")
    normalized: dict[str, list[str]] = {}
    seen: set[str] = set()
    for category in categories:
        paths = _as_string_list(inventory.get(category), f"input_inventory.{category}")
        if paths != sorted(paths):
            raise FreezeError(f"input_inventory_not_sorted:{category}")
        category_paths: list[str] = []
        for value in paths:
            relative = _normalized_relative_path(root, value, f"input_inventory.{category}")
            if relative in seen:
                raise FreezeError(f"duplicate_allowlisted_path:{relative}")
            seen.add(relative)
            category_paths.append(relative)
        normalized[category] = category_paths
    if not seen:
        raise FreezeError("empty_input_inventory")
    return normalized


def _validate_route_surface(contract: Mapping[str, Any]) -> dict[str, list[str]]:
    surface = _as_mapping(contract.get("allowed_route_surface"), "allowed_route_surface")
    browser_routes = _as_string_list(surface.get("browser_routes"), "browser_routes")
    api_routes = _as_string_list(surface.get("api_routes"), "api_routes")
    if not browser_routes or not api_routes:
        raise FreezeError("empty_allowed_route_surface")
    if len(browser_routes) != len(set(browser_routes)):
        raise FreezeError("duplicate_browser_route")
    if len(api_routes) != len(set(api_routes)):
        raise FreezeError("duplicate_api_route")
    if any(not route.startswith("/") for route in browser_routes):
        raise FreezeError("invalid_browser_route")
    if any(
        not route.startswith(("GET /api/v1/", "POST /api/v1/", "PATCH /api/v1/"))
        for route in api_routes
    ):
        raise FreezeError("invalid_api_route")
    return {"browser_routes": browser_routes, "api_routes": api_routes}


def _validate_boundaries(contract: Mapping[str, Any]) -> dict[str, int]:
    authority = _as_mapping(contract.get("authority"), "authority")
    expected_authority = {
        "development_mode": "fixture_shadow_internal_only",
        "runtime_admission": "not_granted",
        "production_readiness": "not_admitted",
        "legacy_global_authority": "retained",
        "release_candidate_not_a_commit_or_release": True,
    }
    if dict(authority) != expected_authority:
        raise FreezeError("authority_boundary_opened")

    boundaries = _as_mapping(contract.get("hard_boundaries"), "hard_boundaries")
    if set(boundaries) != REQUIRED_BOUNDARY_KEYS or any(
        boundaries[name] != 0 for name in REQUIRED_BOUNDARY_KEYS
    ):
        raise FreezeError("hard_boundary_opened")

    prohibitions = _as_mapping(contract.get("prohibitions"), "prohibitions")
    expected_prohibitions = {
        "new_gate_family": False,
        "release_admission": False,
        "operational_execution": False,
        "network_model_provider_tool_execution": False,
    }
    if dict(prohibitions) != expected_prohibitions:
        raise FreezeError("prohibition_boundary_opened")
    return {name: int(boundaries[name]) for name in sorted(REQUIRED_BOUNDARY_KEYS)}


def _validate_release_blockers(contract: Mapping[str, Any]) -> dict[str, Any]:
    blockers = _as_mapping(contract.get("release_blockers"), "release_blockers")
    p07_5 = _as_mapping(blockers.get("p07_5"), "release_blockers.p07_5")
    rg1 = _as_mapping(blockers.get("rg1_vertical_path"), "release_blockers.rg1_vertical_path")
    debt = _as_mapping(rg1.get("bounded_operational_run_debt"), "rg1.bounded_operational_run_debt")
    if p07_5.get("status") != "blocked" or p07_5.get("release_admission") != "not_issued":
        raise FreezeError("p07_5_not_blocked")
    if rg1.get("status") != "blocked":
        raise FreezeError("rg1_vertical_path_not_blocked")
    if rg1.get("exact_package_entry_to_leaf_identity") != "entry_to_adapter_to_subprocess_to_clean_child":
        raise FreezeError("rg1_exact_identity_missing")
    if rg1.get("identity_status") != "unproven_hard_blocker":
        raise FreezeError("rg1_identity_blocker_opened")
    if debt.get("status") != "not_run_separate_authority_required":
        raise FreezeError("rg1_operational_debt_opened")
    if debt.get("required_run_count") != 1 or debt.get("authority") != "not_granted":
        raise FreezeError("rg1_operational_run_boundary_opened")
    if debt.get("required_persisted_results") != ["actual", "oracle", "reviewer", "workbench"]:
        raise FreezeError("rg1_persisted_result_boundary_opened")
    return {"p07_5": dict(p07_5), "rg1_vertical_path": dict(rg1)}


def validate_contract(root: Path, contract_path: Path) -> tuple[Mapping[str, Any], dict[str, list[str]], dict[str, list[str]], dict[str, int], dict[str, Any]]:
    """Validate all boundary-bearing contract fields before reading candidate inputs."""
    root = root.resolve()
    contract_relative = _relative_to_root(root, contract_path)
    if contract_relative is None:
        raise FreezeError("contract_outside_repository")
    contract = _read_json(contract_path, "freeze_contract")
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise FreezeError("unsupported_contract_schema")
    if contract.get("status") != "fixture_shadow_internal_only_not_release_admission":
        raise FreezeError("contract_not_fixture_only")
    if not isinstance(contract.get("contract_id"), str) or not contract["contract_id"].strip():
        raise FreezeError("contract_id_missing")

    inventory = _inventory_from_contract(root, contract)
    all_paths = {path for paths in inventory.values() for path in paths}
    if contract_relative not in all_paths:
        raise FreezeError("contract_not_allowlisted")

    profile = _as_mapping(contract.get("candidate_profile"), "candidate_profile")
    profile_path = profile.get("path")
    if not isinstance(profile_path, str):
        raise FreezeError("profile_path_missing")
    profile_relative = _normalized_relative_path(root, profile_path, "candidate_profile.path")
    if profile_relative not in all_paths:
        raise FreezeError("profile_not_allowlisted")
    if profile.get("digest_algorithm") != "sha256" or profile.get("canonical_serialization") != "json_sort_keys_utf8_compact":
        raise FreezeError("profile_digest_contract_invalid")

    route_surface = _validate_route_surface(contract)
    boundaries = _validate_boundaries(contract)
    blockers = _validate_release_blockers(contract)
    return contract, inventory, route_surface, boundaries, blockers


def _git_output(root: Path, args: list[str]) -> bytes | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        return None
    return completed.stdout


def _nul_paths(value: bytes | None) -> list[str]:
    if value is None:
        return []
    return [item.decode("utf-8", errors="surrogateescape") for item in value.split(b"\0") if item]


def _path_bytes(root: Path, paths: Iterable[str]) -> tuple[int, int]:
    count = 0
    total = 0
    for value in paths:
        try:
            relative = _normalized_relative_path(root, value, "git_status")
        except FreezeError:
            continue
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            if path.is_file():
                total += path.stat().st_size
                count += 1
        except OSError:
            continue
    return count, total


def _is_generated_manifest(root: Path, relative_path: str, contract_id: str) -> bool:
    """Identify this contract's generated output without trusting its filename."""
    path = root.joinpath(*PurePosixPath(relative_path).parts)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, Mapping)
        and value.get("schema_version") == SCRIPT_SCHEMA
        and isinstance(value.get("contract"), Mapping)
        and value["contract"].get("contract_id") == contract_id
        and isinstance(value.get("manifest_sha256"), str)
    )


def _git_snapshot(
    root: Path,
    excluded_relative_path: str | None,
    contract_id: str,
) -> dict[str, Any]:
    """Read Git state without making a cleanliness or release-commit assertion."""
    head = _git_output(root, ["rev-parse", "HEAD"])
    branch = _git_output(root, ["branch", "--show-current"])
    staged_paths = _nul_paths(_git_output(root, ["diff", "--cached", "--name-only", "-z"]))
    working_paths = _nul_paths(_git_output(root, ["diff", "--name-only", "-z"]))
    untracked_paths = _nul_paths(_git_output(root, ["ls-files", "--others", "--exclude-standard", "-z"]))

    def filtered(paths: list[str]) -> list[str]:
        return [
            path
            for path in paths
            if path != excluded_relative_path
            and not _is_generated_manifest(root, path, contract_id)
        ]

    staged_count, staged_bytes = _path_bytes(root, filtered(staged_paths))
    working_count, working_bytes = _path_bytes(root, filtered(working_paths))
    untracked_count, untracked_bytes = _path_bytes(root, filtered(untracked_paths))
    return {
        "git_head": head.decode("ascii").strip() if head else "unavailable",
        "git_branch": branch.decode("utf-8").strip() if branch else "unavailable",
        "observation": "read_only_status_snapshot_no_clean_tree_claim",
        "release_commit_claimed": False,
        "staged": {"path_count": staged_count, "byte_count": staged_bytes},
        "working": {"path_count": working_count, "byte_count": working_bytes},
        "untracked": {"path_count": untracked_count, "byte_count": untracked_bytes},
        "generated_candidate_manifests_excluded": True,
    }


def _profile_binding(root: Path, contract: Mapping[str, Any]) -> dict[str, str]:
    profile = _as_mapping(contract["candidate_profile"], "candidate_profile")
    relative = _normalized_relative_path(root, str(profile["path"]), "candidate_profile.path")
    path = root.joinpath(*PurePosixPath(relative).parts)
    if not path.is_file():
        raise FreezeError(f"missing_allowlisted_file:{relative}")
    raw = path.read_bytes()
    parsed = _read_json(path, "candidate_profile")
    if parsed.get("schema_version") != profile.get("required_schema_version"):
        raise FreezeError("candidate_profile_schema_drift")
    if parsed.get("status") != profile.get("required_status"):
        raise FreezeError("candidate_profile_status_drift")
    return {
        "path": relative,
        "file_sha256": sha256_bytes(raw),
        "canonical_json_sha256": canonical_sha256(parsed),
    }


def _input_file_hashes(root: Path, inventory: Mapping[str, list[str]]) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in sorted(path for paths in inventory.values() for path in paths):
        path = root.joinpath(*PurePosixPath(relative).parts)
        if not path.is_file():
            raise FreezeError(f"missing_allowlisted_file:{relative}")
        hashes[relative] = sha256_bytes(path.read_bytes())
    return hashes


def _validate_output_path(root: Path, output_path: Path, allowlisted_paths: set[str]) -> str | None:
    resolved = output_path.resolve()
    relative = _relative_to_root(root, resolved)
    if relative in allowlisted_paths:
        raise FreezeError("output_path_overlaps_allowlisted_input")
    return relative


def build_manifest(*, root: Path, contract_path: Path, output_path: Path) -> dict[str, Any]:
    """Build a deterministic manifest without executing the candidate."""
    root = root.resolve()
    contract_path = contract_path.resolve()
    output_path = output_path.resolve()
    contract, inventory, route_surface, boundaries, blockers = validate_contract(root, contract_path)
    allowlisted_paths = {path for paths in inventory.values() for path in paths}
    output_relative = _validate_output_path(root, output_path, allowlisted_paths)
    file_hashes = _input_file_hashes(root, inventory)
    profile = _profile_binding(root, contract)
    contract_relative = _relative_to_root(root, contract_path)
    assert contract_relative is not None

    payload = {
        "schema_version": SCRIPT_SCHEMA,
        "manifest_id": "REL-PROD-001:VT4:P07.0:internal-fixture-candidate",
        "status": "frozen_internal_fixture_candidate_not_release_admission",
        "serialization": "json_sort_keys_utf8_compact",
        "contract": {
            "path": contract_relative,
            "sha256": sha256_bytes(contract_path.read_bytes()),
            "contract_id": contract["contract_id"],
            "schema_version": contract["schema_version"],
        },
        "candidate_profile": profile,
        "input_inventory": {
            "digest_algorithm": "sha256",
            "categories": {category: list(paths) for category, paths in sorted(inventory.items())},
            "files": file_hashes,
            "file_count": len(file_hashes),
            "files_sha256": canonical_sha256(file_hashes),
        },
        "allowed_route_surface": route_surface,
        "allowed_route_surface_sha256": canonical_sha256(route_surface),
        "authority": dict(_as_mapping(contract["authority"], "authority")),
        "hard_boundaries": boundaries,
        "release_blockers": blockers,
        "git_snapshot": _git_snapshot(root, output_relative, str(contract["contract_id"])),
    }
    return {**payload, "manifest_sha256": canonical_sha256(payload)}


def write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    """Write exactly one canonical JSON manifest to a caller-selected path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(dict(manifest)) + b"\n")


def verify_manifest(*, root: Path, contract_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Fail closed unless an existing canonical manifest matches current bytes and contract."""
    manifest_path = manifest_path.resolve()
    try:
        raw = manifest_path.read_bytes()
    except OSError as exc:
        raise FreezeError(f"manifest_read_failed:{manifest_path}") from exc
    try:
        manifest = _as_mapping(json.loads(raw.decode("utf-8")), "manifest")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FreezeError("manifest_json_invalid") from exc
    if raw != canonical_json_bytes(manifest) + b"\n":
        raise FreezeError("manifest_not_canonical_json")
    expected = build_manifest(root=root, contract_path=contract_path, output_path=manifest_path)
    if manifest.get("manifest_sha256") != canonical_sha256(
        {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    ):
        raise FreezeError("manifest_digest_invalid")
    if dict(manifest) != expected:
        raise FreezeError("manifest_current_bytes_or_contract_drift")
    return {"status": "pass", "manifest_sha256": manifest["manifest_sha256"]}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)
    for mode in ("freeze", "verify"):
        command = subparsers.add_parser(mode)
        command.add_argument("--repo-root", type=Path, default=DEFAULT_ROOT)
        command.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
        command.add_argument(
            "--output" if mode == "freeze" else "--manifest",
            dest="artifact_path",
            type=Path,
            required=True,
        )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.mode == "freeze":
            manifest = build_manifest(
                root=args.repo_root,
                contract_path=args.contract,
                output_path=args.artifact_path,
            )
            write_manifest(args.artifact_path, manifest)
            result: Mapping[str, Any] = {
                "status": "pass",
                "manifest_path": str(args.artifact_path),
                "manifest_sha256": manifest["manifest_sha256"],
            }
        else:
            result = verify_manifest(
                root=args.repo_root,
                contract_path=args.contract,
                manifest_path=args.artifact_path,
            )
    except FreezeError as exc:
        print(json.dumps({"status": "fail_closed", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
