from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import sys
import urllib.request
import uuid
import zipfile
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
sys.path[:0] = [str(ROOT), str(SRC_ROOT)]

from retrieval.model_identity import _regular_files_without_links  # noqa: E402
from retrieval.quantized_shadow import (  # noqa: E402
    QUANTIZED_MANIFEST_NAME,
    QUANTIZED_MANIFEST_SCHEMA,
    TOOL_MANIFEST_NAME,
    TOOL_MANIFEST_SCHEMA,
    llama_cpp_tool_identity,
    quantized_gguf_identity,
    sha256_file,
)
from retrieval.query_plan import canonical_digest  # noqa: E402


PROGRAM = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_quantized_4b_shadow_acquisition_program_v1_0.json"
)
OUTPUT = (
    "configs/retrieval/"
    "fin_ia_0_1_3_s1_quantized_4b_shadow_acquisition_result_v1_0.json"
)
ATTEMPT_ID = "acquisition-r1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Acquire the exact 4-bit 4B GGUF and llama.cpp assets for the "
            "owner-authorized, development-only S1 shadow."
        )
    )
    parser.add_argument("--program", default=PROGRAM)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--attempt-id", default=ATTEMPT_ID)
    return parser.parse_args()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"quantized_acquisition_json_object_required:{path}")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def _repo_path(raw: str) -> Path:
    path = (ROOT / raw).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError("quantized_acquisition_repo_path_escape")
    return path


def _sha256(path: Path) -> str:
    return sha256_file(path)


def _verify_program(program_path: Path, program: Mapping[str, Any]) -> None:
    unsigned = {key: value for key, value in program.items() if key != "result_digest"}
    if not (
        program.get("schema_version")
        == "fin_ia_s1_quantized_4b_shadow_acquisition_program_v1_0"
        and program.get("status")
        == "preregistered_owner_authorized_development_only_acquisition"
        and program.get("result_digest") == canonical_digest(unsigned)
        and program.get("acquisition_contract", {}).get("attempt_id") == ATTEMPT_ID
    ):
        raise ValueError("quantized_acquisition_program_invalid")
    for binding in program.get("predecessor_bindings") or []:
        if not isinstance(binding, Mapping):
            raise ValueError("quantized_acquisition_predecessor_binding_invalid")
        path = _repo_path(str(binding.get("path") or ""))
        if not path.is_file() or _sha256(path) != binding.get("sha256"):
            raise ValueError(
                f"quantized_acquisition_predecessor_drift:{binding.get('path')}"
            )
    if program_path != _repo_path(PROGRAM):
        raise ValueError("quantized_acquisition_program_path_not_frozen")


def _run_git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _clean_git_receipt() -> dict[str, Any]:
    status = _run_git("status", "--porcelain", "--untracked-files=all")
    head = _run_git("rev-parse", "HEAD")
    upstream = _run_git("rev-parse", "@{upstream}")
    if status or head != upstream:
        raise ValueError("quantized_acquisition_clean_synced_commit_required")
    return {
        "head": head,
        "upstream": upstream,
        "status_porcelain": status,
        "clean": True,
        "upstream_equal": True,
    }


def _hardware_receipt() -> dict[str, Any]:
    fields = "name,memory.total,memory.free,driver_version,compute_cap"
    completed = subprocess.run(
        [
            "nvidia-smi",
            f"--query-gpu={fields}",
            "--format=csv,noheader,nounits",
        ],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    rows = [row.strip() for row in completed.stdout.splitlines() if row.strip()]
    if len(rows) != 1:
        raise ValueError("quantized_acquisition_single_gpu_required")
    parts = [value.strip() for value in rows[0].split(",")]
    if len(parts) != 5:
        raise ValueError("quantized_acquisition_gpu_receipt_invalid")
    return {
        "device_name": parts[0],
        "total_vram_mib": int(parts[1]),
        "free_vram_mib": int(parts[2]),
        "driver_version": parts[3],
        "compute_capability": parts[4],
    }


def _storage_receipt(path: Path) -> dict[str, Any]:
    usage = shutil.disk_usage(path)
    return {
        "probe_root": str(path.resolve()),
        "total_bytes": int(usage.total),
        "used_bytes": int(usage.used),
        "free_bytes": int(usage.free),
    }


def _validate_resource_gate(
    program: Mapping[str, Any],
    hardware: Mapping[str, Any],
    storage: Mapping[str, Any],
) -> None:
    gate = program["execution_resource_gate"]
    if not (
        gate["required_device_name_contains"] in hardware["device_name"]
        and hardware["total_vram_mib"] >= gate["minimum_total_vram_mib"]
        and hardware["free_vram_mib"]
        >= gate["minimum_free_vram_mib_before_acquisition"]
        and storage["free_bytes"] >= gate["minimum_free_storage_bytes"]
    ):
        raise ValueError("quantized_acquisition_resource_gate_failed")


def _file_rows(root: Path, *, excluded_name: str) -> list[dict[str, Any]]:
    excluded = root / excluded_name
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in _regular_files_without_links(root)
        if path != excluded
    ]


def _stage_model(
    spec: Mapping[str, Any],
    *,
    stage: Path,
    cache_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from huggingface_hub import snapshot_download

    stage.mkdir(parents=True, exist_ok=False)
    selected = str(spec["selected_model_file"])
    snapshot = Path(
        snapshot_download(
            repo_id=str(spec["quantized_repo_id"]),
            revision=str(spec["resolved_revision"]),
            allow_patterns=[selected, "README.md"],
            cache_dir=str(cache_root),
            max_workers=1,
        )
    ).resolve()
    if snapshot.name != spec["resolved_revision"]:
        raise ValueError(
            f"quantized_acquisition_snapshot_revision_drift:{spec['artifact_key']}"
        )
    copied: list[str] = []
    for relative in ("README.md", selected):
        source = snapshot / relative
        if not source.is_file():
            raise ValueError(
                f"quantized_acquisition_snapshot_file_missing:{spec['artifact_key']}:{relative}"
            )
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(relative)
    model_path = stage / selected
    if model_path.stat().st_size != spec["expected_bytes"]:
        raise ValueError(
            f"quantized_acquisition_model_size_drift:{spec['artifact_key']}"
        )
    manifest = {
        "schema_version": QUANTIZED_MANIFEST_SCHEMA,
        "repo_id": spec["quantized_repo_id"],
        "resolved_revision": spec["resolved_revision"],
        "source_model_id": spec["source_model_id"],
        "upstream_provenance": spec["upstream_provenance"],
        "quantization": spec["quantization"],
        "acquisition_tool": "huggingface_hub.snapshot_download",
        "selected_model_file": selected,
        "snapshot_response_leaf": snapshot.name,
        "allow_patterns": [selected, "README.md"],
        "files": _file_rows(stage, excluded_name=QUANTIZED_MANIFEST_NAME),
    }
    _write_json(stage / QUANTIZED_MANIFEST_NAME, manifest)
    identity = quantized_gguf_identity(
        stage,
        expected_repo_id=str(spec["quantized_repo_id"]),
        expected_revision=str(spec["resolved_revision"]),
        expected_source_model_id=str(spec["source_model_id"]),
        expected_quantization=str(spec["quantization"]),
    )
    return identity, {
        "artifact_key": spec["artifact_key"],
        "repo_id": spec["quantized_repo_id"],
        "requested_revision": spec["resolved_revision"],
        "snapshot_response_leaf": snapshot.name,
        "copied_files": copied,
        "selected_model_bytes": model_path.stat().st_size,
    }


def _download_asset(
    asset: Mapping[str, Any],
    *,
    cache_root: Path,
    call_counts: dict[str, int],
) -> tuple[Path, dict[str, Any]]:
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / str(asset["name"])
    cache_hit = target.is_file()
    if cache_hit and not (
        target.stat().st_size == asset["expected_bytes"]
        and _sha256(target) == asset["sha256"]
    ):
        raise ValueError(f"quantized_acquisition_invalid_cached_asset:{asset['name']}")
    if not cache_hit:
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.part")
        request = urllib.request.Request(
            str(asset["url"]),
            headers={"User-Agent": "FIN-Insight-Agent/0.1.3-audited-acquisition"},
        )
        call_counts["github_asset_network_download"] += 1
        try:
            with urllib.request.urlopen(
                request, timeout=120
            ) as response, temporary.open("wb") as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            if not (
                temporary.stat().st_size == asset["expected_bytes"]
                and _sha256(temporary) == asset["sha256"]
            ):
                raise ValueError(
                    f"quantized_acquisition_download_drift:{asset['name']}"
                )
            os.replace(temporary, target)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
    return target, {
        "name": asset["name"],
        "url": asset["url"],
        "bytes": target.stat().st_size,
        "sha256": _sha256(target),
        "cache_hit": cache_hit,
        "network_invocations": 0 if cache_hit else 1,
    }


def _safe_extract_zip(archive: Path, destination: Path) -> None:
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for info in bundle.infolist():
            raw_name = info.filename.replace("\\", "/")
            relative = PurePosixPath(raw_name)
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if (
                not raw_name
                or relative.is_absolute()
                or ".." in relative.parts
                or any(":" in part for part in relative.parts)
                or stat.S_ISLNK(unix_mode)
            ):
                raise ValueError(
                    f"quantized_acquisition_unsafe_zip_member:{archive.name}:{raw_name}"
                )
            target = destination.joinpath(*relative.parts)
            if not target.resolve().is_relative_to(destination_root):
                raise ValueError(
                    f"quantized_acquisition_zip_escape:{archive.name}:{raw_name}"
                )
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
            with bundle.open(info) as source, temporary.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            if target.exists():
                if not (
                    target.is_file()
                    and target.stat().st_size == temporary.stat().st_size
                    and _sha256(target) == _sha256(temporary)
                ):
                    raise ValueError(
                        f"quantized_acquisition_zip_collision:{archive.name}:{raw_name}"
                    )
                temporary.unlink()
            else:
                os.replace(temporary, target)


def _stage_tool(
    spec: Mapping[str, Any],
    *,
    stage: Path,
    cache_root: Path,
    call_counts: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    stage.mkdir(parents=True, exist_ok=False)
    receipts: list[dict[str, Any]] = []
    for asset in spec["assets"]:
        archive, receipt = _download_asset(
            asset, cache_root=cache_root, call_counts=call_counts
        )
        receipts.append(receipt)
        _safe_extract_zip(archive, stage)
    server = stage / str(spec["server_relative_path"])
    if not server.is_file():
        candidates = [
            path.relative_to(stage).as_posix()
            for path in stage.rglob("llama-server.exe")
            if path.is_file()
        ]
        raise ValueError(
            "quantized_acquisition_server_path_missing:"
            + ",".join(sorted(candidates))
        )
    version = subprocess.run(
        [str(server), "--version"],
        cwd=stage,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if version.returncode != 0:
        raise ValueError(
            f"quantized_acquisition_llama_server_not_executable:{version.returncode}"
        )
    version_receipt = {
        "returncode": version.returncode,
        "stdout": version.stdout.strip()[:2000],
        "stderr": version.stderr.strip()[:2000],
    }
    manifest = {
        "schema_version": TOOL_MANIFEST_SCHEMA,
        "tool_id": spec["tool_id"],
        "release_tag": spec["release_tag"],
        "release_published_at": spec["release_published_at"],
        "server_relative_path": spec["server_relative_path"],
        "acquisition_tool": "urllib.request plus safe zipfile extraction",
        "source_assets": receipts,
        "version_receipt": version_receipt,
        "files": _file_rows(stage, excluded_name=TOOL_MANIFEST_NAME),
    }
    _write_json(stage / TOOL_MANIFEST_NAME, manifest)
    identity = llama_cpp_tool_identity(
        stage,
        expected_release_tag=str(spec["release_tag"]),
        expected_server_relative_path=str(spec["server_relative_path"]),
    )
    return identity, receipts, version_receipt


def _publish_directory(stage: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"quantized_acquisition_destination_exists:{destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(stage, destination)


def _result_with_digest(body: Mapping[str, Any]) -> dict[str, Any]:
    plain = dict(body)
    return {**plain, "result_digest": canonical_digest(plain)}


def main() -> int:
    args = parse_args()
    if args.attempt_id != ATTEMPT_ID:
        raise ValueError("quantized_acquisition_attempt_id_not_frozen")
    program_path = _repo_path(args.program)
    output_path = _repo_path(args.output)
    private_path = (
        ROOT
        / "data/workbench_private/fin_0_1_3_s1_quantized_4b_shadow"
        / args.attempt_id
        / "full_result.json"
    ).resolve()
    if output_path.exists() or private_path.exists():
        raise ValueError("quantized_acquisition_attempt_output_already_exists")
    program = _read_json(program_path)
    _verify_program(program_path, program)
    git_receipt = _clean_git_receipt()

    gate = program["execution_resource_gate"]
    storage_root = Path(str(gate["storage_probe_root"])).resolve()
    hardware = _hardware_receipt()
    storage_before = _storage_receipt(storage_root)
    _validate_resource_gate(program, hardware, storage_before)

    final_directories = {
        key: Path(str(spec["local_directory"])).resolve()
        for key, spec in program["models"].items()
    }
    final_directories["tool"] = Path(
        str(program["tool"]["local_directory"])
    ).resolve()
    existing = [str(path) for path in final_directories.values() if path.exists()]
    if existing:
        raise ValueError(
            "quantized_acquisition_destination_exists_before_attempt:" + ",".join(existing)
        )

    transaction_root = (
        storage_root / "fin_ia_staging" / f"{args.attempt_id}-{uuid.uuid4().hex}"
    )
    transaction_root.mkdir(parents=True, exist_ok=False)
    started_at = datetime.now(timezone.utc).isoformat()
    call_counts = {
        "huggingface_snapshot_download": 0,
        "github_asset_network_download": 0,
        "provider": 0,
        "model_inference": 0,
    }
    published: list[Path] = []
    try:
        model_identities: dict[str, Any] = {}
        model_receipts: dict[str, Any] = {}
        hf_cache = Path(str(gate["huggingface_cache_root"])).resolve()
        for key in ("embedding", "reranker"):
            call_counts["huggingface_snapshot_download"] += 1
            identity, receipt = _stage_model(
                program["models"][key],
                stage=transaction_root / key,
                cache_root=hf_cache,
            )
            model_identities[key] = identity
            model_receipts[key] = receipt

        tool_identity, asset_receipts, version_receipt = _stage_tool(
            program["tool"],
            stage=transaction_root / "tool",
            cache_root=Path(str(gate["download_cache_root"])).resolve(),
            call_counts=call_counts,
        )

        for key in ("embedding", "reranker", "tool"):
            _publish_directory(transaction_root / key, final_directories[key])
            published.append(final_directories[key])
        transaction_root.rmdir()

        final_model_identities = {
            key: quantized_gguf_identity(
                final_directories[key],
                expected_repo_id=str(program["models"][key]["quantized_repo_id"]),
                expected_revision=str(program["models"][key]["resolved_revision"]),
                expected_source_model_id=str(program["models"][key]["source_model_id"]),
                expected_quantization=str(program["models"][key]["quantization"]),
            )
            for key in ("embedding", "reranker")
        }
        final_tool_identity = llama_cpp_tool_identity(
            final_directories["tool"],
            expected_release_tag=str(program["tool"]["release_tag"]),
            expected_server_relative_path=str(program["tool"]["server_relative_path"]),
        )
        if not (
            final_model_identities == model_identities
            and final_tool_identity == tool_identity
        ):
            raise ValueError("quantized_acquisition_post_publish_identity_drift")

        body = {
            "schema_version": "fin_ia_s1_quantized_4b_shadow_acquisition_result_v1_0",
            "status": "acquisition_succeeded_development_shadow_only",
            "recorded_at": "2026-08-24",
            "started_at_utc": started_at,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_id": args.attempt_id,
            "program_ref": program_path.relative_to(ROOT).as_posix(),
            "program_sha256": _sha256(program_path),
            "program_result_digest": program["result_digest"],
            "git_receipt": git_receipt,
            "hardware": hardware,
            "storage_before": storage_before,
            "storage_after": _storage_receipt(storage_root),
            "model_receipts": model_receipts,
            "model_identities": final_model_identities,
            "tool_asset_receipts": asset_receipts,
            "tool_version_receipt": version_receipt,
            "tool_identity": final_tool_identity,
            "calls": {
                **call_counts,
                "high_level_network_total": (
                    call_counts["huggingface_snapshot_download"]
                    + call_counts["github_asset_network_download"]
                ),
            },
            "authority": dict(program["authority"]),
            "execution_authorized": True,
            "known_boundary": program["known_boundary"],
        }
        result = _result_with_digest(body)
        _write_json(private_path, result)
        _write_json(output_path, result)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "attempt_id": result["attempt_id"],
                    "model_digests": {
                        key: value["model_digest"]
                        for key, value in result["model_identities"].items()
                    },
                    "tool_digest": result["tool_identity"]["tool_digest"],
                    "calls": result["calls"],
                    "result_digest": result["result_digest"],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        if transaction_root.exists():
            shutil.rmtree(transaction_root)
        for path in reversed(published):
            if path.exists():
                shutil.rmtree(path)
        body = {
            "schema_version": "fin_ia_s1_quantized_4b_shadow_acquisition_result_v1_0",
            "status": "acquisition_failed_successor_attempt_required",
            "recorded_at": "2026-08-24",
            "started_at_utc": started_at,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "attempt_id": args.attempt_id,
            "program_ref": program_path.relative_to(ROOT).as_posix(),
            "program_sha256": _sha256(program_path),
            "program_result_digest": program["result_digest"],
            "git_receipt": git_receipt,
            "hardware": hardware,
            "storage_before": storage_before,
            "failure": {
                "exception_type": type(exc).__name__,
                "message": str(exc)[:4000],
            },
            "calls": {
                **call_counts,
                "high_level_network_total": (
                    call_counts["huggingface_snapshot_download"]
                    + call_counts["github_asset_network_download"]
                ),
            },
            "execution_authorized": False,
            "runtime_promotion_authorized": False,
            "S1_qualification_authorized": False,
            "successor_attempt_required": True,
        }
        result = _result_with_digest(body)
        _write_json(private_path, result)
        _write_json(output_path, result)
        print(json.dumps(result, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
