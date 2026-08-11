from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Iterable


INDEX_RELATIVE = Path(
    "archive/versions/FIN_0_1_3_REBASELINE_REDIRECT_INDEX.jsonl"
)
PATH_MAP_RELATIVE = Path(
    "archive/versions/FIN_0_1_3_REBASELINE_PATH_MAP.jsonl"
)
PORTABLE_ARCHIVE_PATH_LIMIT = 180
VERSION_ROOTS = (
    "fin_0_1_1",
    "fin_0_1_2",
    "fin_0_1_3_prebaseline",
    "pre_fin_0_1_3",
)


def _git_paths(repository_root: Path, *args: str) -> list[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return [line.strip().replace("\\", "/") for line in completed.stdout.splitlines() if line.strip()]


def _archive_files(repository_root: Path) -> list[str]:
    tracked = _git_paths(repository_root, "ls-files", "--", "archive/versions")
    untracked = _git_paths(
        repository_root,
        "ls-files",
        "--others",
        "--exclude-standard",
        "--",
        "archive/versions",
    )
    paths = sorted(set(tracked + untracked))
    metadata = {INDEX_RELATIVE.as_posix(), PATH_MAP_RELATIVE.as_posix()}
    return [path for path in paths if path not in metadata]


def _read_path_map(repository_root: Path) -> dict[str, dict[str, str]]:
    path = repository_root / PATH_MAP_RELATIVE
    if not path.is_file():
        return {}
    mapped: dict[str, dict[str, str]] = {}
    observed_sources: set[str] = set()
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(), start=1
    ):
        if not line.strip():
            continue
        row = json.loads(line)
        archive_path = str(row.get("archive_path") or "").replace("\\", "/")
        source_path = str(row.get("source_path") or "").replace("\\", "/")
        origin_version = str(row.get("origin_version") or "")
        sha256 = str(row.get("sha256") or "")
        if (
            not archive_path.startswith("archive/versions/")
            or archive_path in mapped
            or not source_path
            or source_path in observed_sources
            or origin_version.split("/", 1)[0] not in VERSION_ROOTS
            or len(sha256) != 64
        ):
            raise ValueError(f"invalid_archive_path_map:{line_number}")
        mapped[archive_path] = {
            "archive_path": archive_path,
            "source_path": source_path,
            "origin_version": origin_version,
            "sha256": sha256,
        }
        observed_sources.add(source_path)
    return mapped


def _source_and_version(
    archive_path: str,
    path_map: dict[str, dict[str, str]] | None = None,
) -> tuple[str, str]:
    mapped = (path_map or {}).get(archive_path)
    if mapped is not None:
        return mapped["source_path"], mapped["origin_version"]
    prefix = "archive/versions/"
    if not archive_path.startswith(prefix):
        raise ValueError(f"archive_path_outside_versions:{archive_path}")
    remainder = archive_path[len(prefix) :]
    version, separator, source = remainder.partition("/")
    if not separator or version not in VERSION_ROOTS:
        raise ValueError(f"unknown_archive_version_root:{archive_path}")
    if version == "pre_fin_0_1_3" and source.startswith("unpromoted_active_tree/"):
        version = "pre_fin_0_1_3/unpromoted_active_tree"
        source = source[len("unpromoted_active_tree/") :]
    if source == "apps/workbench/backend/api/operations_legacy_full_bridge.py":
        source = "apps/workbench/backend/api/operations.py"
    return source, version


def _portable_archive_path(
    source_path: str,
    version: str,
    content_sha256: str,
) -> str:
    version_root = version.split("/", 1)[0]
    source_sha256 = hashlib.sha256(source_path.encode("utf-8")).hexdigest()
    suffix = Path(source_path).suffix.lower()
    if len(suffix) > 12 or any(character not in ".-_abcdefghijklmnopqrstuvwxyz0123456789" for character in suffix):
        suffix = ""
    return (
        f"archive/versions/{version_root}/_portable/{source_sha256[:2]}/"
        f"{source_sha256[:24]}_{content_sha256[:24]}{suffix}"
    )


def _classification(source_path: str) -> tuple[str, str, str]:
    if source_path.startswith(("src/", "apps/")):
        return (
            "unpromoted_or_superseded_code",
            "current FIN 0.1.3 active import graph",
            "reproducible_historical_code",
        )
    if source_path.startswith("scripts/"):
        return (
            "release_attempt_or_unadmitted_tooling",
            "admitted data-build and baseline engineering scripts",
            "reproducible_historical_tool",
        )
    if source_path.startswith("tests/"):
        return (
            "historical_or_unadmitted_capability_test",
            "FIN 0.1.3 current baseline suite",
            "reproducible_historical_test",
        )
    if source_path.startswith("configs/"):
        return (
            "historical_contract_release_or_attempt_record",
            "current runtime and repository manifests",
            "immutable_historical_contract_or_result",
        )
    if source_path.startswith("docs/"):
        return (
            "historical_design_execution_or_handoff_record",
            "current PRD TECH Project OS and code map",
            "immutable_historical_document",
        )
    if source_path.startswith(("data/", "reports/", "eval_sets/")):
        return (
            "historical_fixture_eval_or_model_run",
            "current reviewed three-case product resources",
            "immutable_historical_evidence",
        )
    return (
        "diagnostic_or_experimental_asset",
        "current FIN 0.1.3 baseline",
        "reproducible_historical_asset",
    )


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_rows(repository_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    observed_sources: dict[str, str] = {}
    path_map = _read_path_map(repository_root)
    archive_files = _archive_files(repository_root)
    missing_targets = sorted(set(path_map) - set(archive_files))
    if missing_targets:
        raise FileNotFoundError(f"archive_path_map_target_missing:{missing_targets[0]}")
    for archive_path in archive_files:
        if "/_portable/" in archive_path and archive_path not in path_map:
            raise ValueError(f"portable_archive_path_unmapped:{archive_path}")
        source_path, version = _source_and_version(archive_path, path_map)
        previous = observed_sources.get(source_path)
        if previous is not None and previous != archive_path:
            raise ValueError(
                f"duplicate_source_redirect:{source_path}:{previous}:{archive_path}"
            )
        observed_sources[source_path] = archive_path
        reason, replacement, evidence_classification = _classification(source_path)
        target = (repository_root / archive_path).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"archive_target_missing:{archive_path}")
        digest = _digest(target)
        mapped = path_map.get(archive_path)
        if mapped is not None and mapped["sha256"] != digest:
            raise ValueError(f"archive_path_map_digest_drift:{archive_path}")
        rows.append(
            {
                "source_path": source_path,
                "archive_path": archive_path,
                "origin_version": version,
                "reason": reason,
                "replacement": replacement,
                "evidence_classification": evidence_classification,
                "active_imports_allowed": False,
                "sha256": digest,
            }
        )
    return sorted(rows, key=lambda row: (str(row["source_path"]), str(row["archive_path"])))


def _write_jsonl(path: Path, rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def compact_long_paths(
    repository_root: Path,
    *,
    max_relative_length: int = PORTABLE_ARCHIVE_PATH_LIMIT,
) -> int:
    path_map = _read_path_map(repository_root)
    archive_files = _archive_files(repository_root)
    move_plan: list[tuple[str, str, dict[str, str]]] = []
    reserved_targets = set(archive_files) | set(path_map)

    for archive_path in archive_files:
        if len(archive_path) <= max_relative_length:
            continue
        source_path, version = _source_and_version(archive_path, path_map)
        source = repository_root / archive_path
        digest = _digest(source)
        target_path = _portable_archive_path(source_path, version, digest)
        if len(target_path) > max_relative_length:
            raise ValueError(f"portable_archive_path_still_too_long:{target_path}")
        if target_path in reserved_targets and target_path != archive_path:
            raise FileExistsError(f"portable_archive_target_collision:{target_path}")
        target = repository_root / target_path
        if target.exists() and target.resolve() != source.resolve():
            raise FileExistsError(f"portable_archive_target_exists:{target_path}")
        row = {
            "archive_path": target_path,
            "source_path": source_path,
            "origin_version": version,
            "sha256": digest,
        }
        move_plan.append((archive_path, target_path, row))
        reserved_targets.add(target_path)

    moved: list[tuple[Path, Path]] = []
    try:
        for source_path, target_path, row in move_plan:
            source = repository_root / source_path
            target = repository_root / target_path
            target.parent.mkdir(parents=True, exist_ok=True)
            source.rename(target)
            moved.append((source, target))
            path_map.pop(source_path, None)
            path_map[target_path] = row
        _write_jsonl(
            repository_root / PATH_MAP_RELATIVE,
            sorted(path_map.values(), key=lambda row: row["source_path"]),
        )
    except Exception:
        for source, target in reversed(moved):
            if target.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                target.rename(source)
        raise
    return len(move_plan)


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--compact-long-paths", action="store_true")
    parser.add_argument(
        "--max-relative-path",
        type=int,
        default=PORTABLE_ARCHIVE_PATH_LIMIT,
    )
    args = parser.parse_args()
    repository_root = Path(__file__).resolve().parents[2]
    compacted = 0
    if args.compact_long_paths:
        compacted = compact_long_paths(
            repository_root,
            max_relative_length=args.max_relative_path,
        )
    overlong = [
        path
        for path in _archive_files(repository_root)
        if len(path) > args.max_relative_path
    ]
    if overlong:
        raise SystemExit(f"archive_relative_path_too_long:{overlong[0]}")
    rows = build_rows(repository_root)
    index_path = repository_root / INDEX_RELATIVE
    rendered = "".join(
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        for row in rows
    )
    if args.check:
        if not index_path.is_file() or index_path.read_text(encoding="utf-8-sig") != rendered:
            raise SystemExit("archive_redirect_index_drift")
    else:
        _write_jsonl(index_path, rows)
    print(
        json.dumps(
            {
                "status": "pass",
                "mode": (
                    "check"
                    if args.check
                    else "compact_long_paths"
                    if args.compact_long_paths
                    else "write"
                ),
                "compacted_paths": compacted,
                "max_relative_path": args.max_relative_path,
                "redirect_count": len(rows),
                "index": INDEX_RELATIVE.as_posix(),
            },
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
