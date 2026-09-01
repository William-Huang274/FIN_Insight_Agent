from __future__ import annotations

import argparse
import base64
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "fin_ia_s1_docling_pdf_qualification_v1_0"
QUALIFICATION_ROOT = Path(r"Z:\FIN_Insight_Agent_qualification")
EXPECTED_BRANCH = "codex/fin013-dell-s1-s2-product-bridge"
EXPECTED_PYTHON_VERSION = "3.11.14"
MINIMUM_D_FREE_GIB = 2.5
MINIMUM_Z_FREE_GIB = 12.0
MINIMUM_FREE_MEMORY_GIB = 3.0

EXPECTED_RUNTIME_VERSIONS = {
    "docling": "2.124.0",
    "docling-slim": "2.124.0",
    "docling-core": "2.92.0",
    "docling-ibm-models": "4.0.0",
    "docling-parse": "7.16.0",
    "safetensors": "0.8.0",
    "torch": "2.7.1+cu118",
    "torchvision": "0.22.1+cu118",
    "transformers": "5.16.1",
}
EXPECTED_INSTALLED_DISTRIBUTION_MANIFEST_DIGEST = (
    "ed0163bde48d7d4ccfe17b9cf108aeb84af3fc2bdf7c820bb84e456fdcd2abcd"
)
EXPECTED_DISTRIBUTION_RECORD_SHA256 = {
    "docling": "e091a7eca839a1e495e037b470d07009d89542da4677690697724bea462c344f",
    "docling-slim": "5bdbcfda3a1459be02bc0de9494b002a664281ccf0eb328d3da8b3346d05fc57",
    "docling-core": "abf72af840cfe1edbaebf0b5e9df29737190f3f494c0b86bc5e7935676898619",
    "docling-ibm-models": "266f5c33fa2e932751d4e53cdc703d6ab32a67544982b6b1bb54bbc67ce314e5",
    "docling-parse": "3587f19af9b4b1c8803941453d678fda7cf37fc1175d8b64709da49269e9a791",
    "safetensors": "5104da9df47c2cfd517218e0450554a9045addf1f97b31cc83fda17f1e556625",
    "torch": "42b539d2a6080023f3a1332e73e13c2345638ad2347a80bea22332804a729ec9",
    "torchvision": "0799ccea9a00944f3a50e145912e9e17ee7b18689bdd22c6868caaeccc2975c7",
    "transformers": "ff8fb233333bcbe98bd8709de55650a16e47ce9e32f9a863fcbc9322b105e4f6",
}

MODEL_REVISIONS = {
    "docling-project/docling-layout-heron": {
        "upstream_revision": "main",
        "resolved_commit": "8f39ad3c0b4c58e9c2d2c84a38465abf757272d8",
        "license": "Apache-2.0",
    },
    "docling-project/docling-models": {
        "upstream_revision": "v2.3.0",
        "resolved_commit": "fc0f2d45e2218ea24bce5045f58a389aed16dc23",
        "license": "CDLA-Permissive-2.0 at the pinned v2.3.0 commit",
    },
}

EXPECTED_MODEL_FILES = {
    "docling-project--docling-layout-heron/.gitattributes": {
        "bytes": 1519,
        "sha256": "11ad7efa24975ee4b0c3c3a38ed18737f0658a5f75a0a96787b576a78a023361",
    },
    "docling-project--docling-layout-heron/README.md": {
        "bytes": 3219,
        "sha256": "175700839bc7808eac6af1d0c23e4f483606ab2276fe01122f4093e61a1a65b6",
    },
    "docling-project--docling-layout-heron/config.json": {
        "bytes": 3268,
        "sha256": "fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d",
    },
    "docling-project--docling-layout-heron/docling_heron_400.png": {
        "bytes": 96925,
        "sha256": "e7f78610372b32a7938e480d2c7fa1c3037ee170bd82282a5bd026232f6e6f9e",
    },
    "docling-project--docling-layout-heron/model.safetensors": {
        "bytes": 171658996,
        "sha256": "00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c",
    },
    "docling-project--docling-layout-heron/preprocessor_config.json": {
        "bytes": 444,
        "sha256": "cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1",
    },
    "docling-project--docling-models/README.md": {
        "bytes": 3413,
        "sha256": "d17f233378eff1240b623b36da76ee8b40afcca05d505949713bf03f7e00822a",
    },
    "docling-project--docling-models/config.json": {
        "bytes": 41,
        "sha256": "9c34024dc28ff47b75818f415e769809798c29bf9bde6f2ccc63a4acb62396d9",
    },
    (
        "docling-project--docling-models/model_artifacts/tableformer/accurate/"
        "tableformer_accurate.safetensors"
    ): {
        "bytes": 212758388,
        "sha256": "2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9",
    },
    (
        "docling-project--docling-models/model_artifacts/tableformer/accurate/"
        "tm_config.json"
    ): {
        "bytes": 7060,
        "sha256": "984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd",
    },
}

CASES = {
    "dell_fy26_results": {
        "relative_path": "tmp/pdfs/s4_t04_dell_sources/dell_fy26_results.pdf",
        "bytes": 683251,
        "sha256": "17be3981929167a2c6033a75abe24159e4de624bbbb7261b66fd8b189680e2f9",
        "expected_pages": 9,
        "page_range": [1, 9],
        "role": "small_control_full_document",
    },
    "tencent_2025_annual_report": {
        "relative_path": (
            "data/workbench_private/fin_0_1_3_s1_vs5_tencent_pdf_layout/live-r1/"
            "raw_bodies/sha256/2a/75/"
            "2a7547168077c3d9994af673125e77612e8656bc0f17ad189371d7e4088f4e98.pdf"
        ),
        "bytes": 3999857,
        "sha256": "2a7547168077c3d9994af673125e77612e8656bc0f17ad189371d7e4088f4e98",
        "expected_pages": 282,
        "page_range": [1, 282],
        "role": "complex_long_document",
    },
    "tel_fy25q4_presentation": {
        "relative_path": "data/raw_private/r17_product_family_evidence/tel_fy25q4_presentation.pdf",
        "bytes": 900677,
        "sha256": "d8ef16d708c91a7efa62e1113043ae2453ec2c63817c1e9413edfc853b65d577",
        "expected_pages": 29,
        "page_range": [1, 29],
        "role": "landscape_presentation",
    },
}


class DoclingQualificationError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _qualification_path(path: Path) -> Path:
    resolved = path.resolve()
    root = QUALIFICATION_ROOT.resolve()
    try:
        common = Path(os.path.commonpath((str(root), str(resolved))))
    except ValueError as exc:
        raise DoclingQualificationError(
            f"qualification_path_drive_mismatch:{path}"
        ) from exc
    if str(common).casefold() != str(root).casefold() or resolved == root:
        raise DoclingQualificationError(
            f"qualification_path_outside_root:{path}"
        )
    return resolved


def _atomic_write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _exclusive_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def _claim_attempt_directory(attempt_dir: Path) -> None:
    attempt_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        attempt_dir.mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise DoclingQualificationError(
            f"attempt_directory_already_claimed:{attempt_dir}"
        ) from exc


def _git_state(repository_root: Path) -> dict[str, Any]:
    def invoke(*arguments: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    status = invoke("status", "--short")
    branch = invoke("branch", "--show-current")
    if branch != EXPECTED_BRANCH:
        raise DoclingQualificationError(
            f"repository_branch_mismatch:{branch}:{EXPECTED_BRANCH}"
        )
    return {
        "head": invoke("rev-parse", "HEAD"),
        "branch": branch,
        "dirty": bool(status),
        "status_digest": canonical_digest(status.splitlines()),
    }


def _distribution_record_digest(name: str) -> str:
    record = importlib.metadata.distribution(name).read_text("RECORD")
    if record is None:
        raise DoclingQualificationError(f"distribution_record_missing:{name}")
    return hashlib.sha256(record.encode("utf-8")).hexdigest()


def _verify_distribution_record_files(
    distribution_name: str, *, allowed_root: Path | None = None
) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(distribution_name)
    record = distribution.read_text("RECORD")
    if record is None:
        raise DoclingQualificationError(
            f"distribution_record_missing:{distribution_name}"
        )
    containment_root = (allowed_root or Path(sys.prefix)).resolve()
    rows = list(csv.reader(io.StringIO(record)))
    verified_files = 0
    verified_bytes = 0
    unhashed_rows = 0
    for row_number, row in enumerate(rows, start=1):
        if len(row) != 3:
            raise DoclingQualificationError(
                f"distribution_record_row_invalid:{distribution_name}:"
                f"{row_number}"
            )
        relative_path, hash_field, size_field = row
        if not hash_field:
            unhashed_rows += 1
            continue
        try:
            algorithm, encoded_digest = hash_field.split("=", 1)
        except ValueError as exc:
            raise DoclingQualificationError(
                f"distribution_record_hash_invalid:{distribution_name}:"
                f"{relative_path}"
            ) from exc
        if algorithm != "sha256":
            raise DoclingQualificationError(
                f"distribution_record_hash_algorithm_not_sha256:"
                f"{distribution_name}:{relative_path}:{algorithm}"
            )
        try:
            expected_digest = base64.urlsafe_b64decode(
                encoded_digest + "=" * (-len(encoded_digest) % 4)
            ).hex()
            expected_size = int(size_field)
        except (ValueError, TypeError) as exc:
            raise DoclingQualificationError(
                f"distribution_record_identity_invalid:{distribution_name}:"
                f"{relative_path}"
            ) from exc
        path = Path(distribution.locate_file(relative_path)).resolve()
        try:
            path.relative_to(containment_root)
        except ValueError as exc:
            raise DoclingQualificationError(
                f"distribution_file_outside_runtime:{distribution_name}:"
                f"{relative_path}:{path}"
            ) from exc
        if not path.is_file():
            raise DoclingQualificationError(
                f"distribution_file_missing:{distribution_name}:{relative_path}"
            )
        if path.stat().st_size != expected_size:
            raise DoclingQualificationError(
                f"distribution_file_size_mismatch:{distribution_name}:"
                f"{relative_path}"
            )
        if sha256_file(path) != expected_digest:
            raise DoclingQualificationError(
                f"distribution_file_digest_mismatch:{distribution_name}:"
                f"{relative_path}"
            )
        verified_files += 1
        verified_bytes += expected_size
    return {
        "distribution": distribution_name,
        "record_rows": len(rows),
        "record_sha256": hashlib.sha256(record.encode("utf-8")).hexdigest(),
        "hashed_files_verified": verified_files,
        "unhashed_rows": unhashed_rows,
        "verified_bytes": verified_bytes,
    }


def _distribution_module_ownership(
    distribution_name: str, module_name: str
) -> dict[str, Any]:
    distribution = importlib.metadata.distribution(distribution_name)
    spec = importlib.util.find_spec(module_name)
    if spec is None or spec.origin is None:
        raise DoclingQualificationError(
            f"runtime_module_origin_missing:{module_name}"
        )
    distribution_root = Path(distribution.locate_file("")).resolve()
    module_origin = Path(spec.origin).resolve()
    try:
        relative_origin = module_origin.relative_to(distribution_root).as_posix()
    except ValueError as exc:
        raise DoclingQualificationError(
            f"runtime_module_outside_distribution:{module_name}:"
            f"{distribution_name}:{module_origin}"
        ) from exc
    distribution_files = {
        Path(str(path)).as_posix() for path in (distribution.files or ())
    }
    if relative_origin not in distribution_files:
        raise DoclingQualificationError(
            f"runtime_module_not_owned_by_distribution:{module_name}:"
            f"{distribution_name}:{relative_origin}"
        )
    return {
        "module": module_name,
        "module_origin": str(module_origin),
        "distribution": distribution_name,
        "distribution_version": distribution.version,
        "distribution_relative_path": relative_origin,
        "distribution_file_count": len(distribution_files),
    }


def _runtime_manifest() -> dict[str, Any]:
    if not sys.dont_write_bytecode:
        raise DoclingQualificationError(
            "python_bytecode_write_not_disabled_invoke_with_minus_B"
        )
    observed = {
        package: importlib.metadata.version(package)
        for package in EXPECTED_RUNTIME_VERSIONS
    }
    if observed != EXPECTED_RUNTIME_VERSIONS:
        raise DoclingQualificationError(
            f"runtime_version_drift:{observed}:{EXPECTED_RUNTIME_VERSIONS}"
        )
    if platform.python_version() != EXPECTED_PYTHON_VERSION:
        raise DoclingQualificationError(
            f"python_version_drift:{platform.python_version()}:{EXPECTED_PYTHON_VERSION}"
        )
    packages: dict[str, str] = {}
    for distribution in importlib.metadata.distributions():
        name = str(distribution.metadata.get("Name") or "").strip().casefold()
        if name:
            packages[name] = distribution.version
    installed = [
        {"name": name, "version": version}
        for name, version in sorted(packages.items())
    ]
    key_records = {
        name: _distribution_record_digest(name)
        for name in sorted(EXPECTED_RUNTIME_VERSIONS)
    }
    installed_digest = canonical_digest(installed)
    if installed_digest != EXPECTED_INSTALLED_DISTRIBUTION_MANIFEST_DIGEST:
        raise DoclingQualificationError(
            "installed_distribution_manifest_drift:"
            f"{installed_digest}:{EXPECTED_INSTALLED_DISTRIBUTION_MANIFEST_DIGEST}"
        )
    if key_records != EXPECTED_DISTRIBUTION_RECORD_SHA256:
        raise DoclingQualificationError(
            "distribution_record_digest_drift:"
            f"{key_records}:{EXPECTED_DISTRIBUTION_RECORD_SHA256}"
        )
    runtime_code_ownership = _distribution_module_ownership(
        "docling-slim", "docling"
    )
    runtime_code_file_verification = _verify_distribution_record_files(
        "docling-slim"
    )
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": str(Path(sys.executable).resolve()),
        "expected_versions": observed,
        "key_distribution_record_sha256": key_records,
        "runtime_code_ownership": runtime_code_ownership,
        "runtime_code_file_verification": runtime_code_file_verification,
        "bytecode_writes_disabled": sys.dont_write_bytecode,
        "installed_distributions": installed,
        "installed_distribution_manifest_digest": installed_digest,
    }


def _validate_file_manifest(
    root: Path, expected: Mapping[str, Mapping[str, Any]]
) -> dict[str, Any]:
    expected_paths = {Path(path).as_posix() for path in expected}
    observed_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and ".cache" not in path.relative_to(root).parts
    }
    if observed_paths != expected_paths:
        raise DoclingQualificationError(
            "model_runtime_allowlist_mismatch:"
            f"missing={sorted(expected_paths - observed_paths)}:"
            f"unexpected={sorted(observed_paths - expected_paths)}"
        )
    files: list[dict[str, Any]] = []
    for relative_path, identity in expected.items():
        path = root / Path(relative_path)
        if not path.is_file():
            raise DoclingQualificationError(
                f"model_file_missing:{relative_path}"
            )
        observed = {
            "relative_path": relative_path,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if observed["bytes"] != identity["bytes"]:
            raise DoclingQualificationError(
                f"model_file_size_mismatch:{relative_path}"
            )
        if observed["sha256"] != identity["sha256"]:
            raise DoclingQualificationError(
                f"model_file_digest_mismatch:{relative_path}"
            )
        files.append(observed)
    body = {
        "resolved_revisions": MODEL_REVISIONS,
        "files": files,
        "total_bytes": sum(int(row["bytes"]) for row in files),
    }
    return {**body, "model_package_digest": canonical_digest(body)}


def _input_identity(repository_root: Path, case_id: str) -> dict[str, Any]:
    if case_id not in CASES:
        raise DoclingQualificationError(f"case_not_registered:{case_id}")
    spec = CASES[case_id]
    path = (repository_root / Path(str(spec["relative_path"]))).resolve()
    if not path.is_file():
        raise DoclingQualificationError(f"case_input_missing:{case_id}")
    observed = {
        "case_id": case_id,
        "path": str(path),
        "relative_path": str(spec["relative_path"]),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "expected_pages": int(spec["expected_pages"]),
        "page_range": list(spec["page_range"]),
        "role": str(spec["role"]),
    }
    if observed["bytes"] != spec["bytes"]:
        raise DoclingQualificationError(f"case_input_size_mismatch:{case_id}")
    if observed["sha256"] != spec["sha256"]:
        raise DoclingQualificationError(f"case_input_digest_mismatch:{case_id}")
    return observed


def _resource_snapshot() -> dict[str, Any]:
    try:
        import psutil
    except ImportError as exc:
        raise DoclingQualificationError("psutil_missing") from exc
    d_usage = shutil.disk_usage("D:\\")
    z_usage = shutil.disk_usage("Z:\\")
    memory = psutil.virtual_memory()
    return {
        "d_free_gib": round(d_usage.free / (1024**3), 6),
        "z_free_gib": round(z_usage.free / (1024**3), 6),
        "free_physical_memory_gib": round(memory.available / (1024**3), 6),
        "total_physical_memory_gib": round(memory.total / (1024**3), 6),
    }


def _resource_gate(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if float(snapshot["d_free_gib"]) < MINIMUM_D_FREE_GIB:
        failures.append("d_free_below_stop_line")
    if float(snapshot["z_free_gib"]) < MINIMUM_Z_FREE_GIB:
        failures.append("z_free_below_stop_line")
    if float(snapshot["free_physical_memory_gib"]) < MINIMUM_FREE_MEMORY_GIB:
        failures.append("free_memory_below_runtime_safety_line")
    return {
        "passed": not failures,
        "failures": failures,
        "thresholds": {
            "d_free_gib": MINIMUM_D_FREE_GIB,
            "z_free_gib": MINIMUM_Z_FREE_GIB,
            "free_physical_memory_gib": MINIMUM_FREE_MEMORY_GIB,
        },
    }


class _PeakRssSampler:
    def __init__(self, interval_seconds: float = 0.1) -> None:
        import psutil

        self._process = psutil.Process()
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._sample, daemon=True)
        self.peak_bytes = self._process.memory_info().rss

    def _sample(self) -> None:
        while not self._stop.wait(self._interval_seconds):
            try:
                self.peak_bytes = max(
                    self.peak_bytes, self._process.memory_info().rss
                )
            except OSError:
                return

    def __enter__(self) -> "_PeakRssSampler":
        self._thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)


def _document_metrics(document: Any, markdown: str) -> dict[str, Any]:
    label_counts = Counter(str(item.label.value) for item in document.texts)
    provenance_items = 0
    bbox_items = 0
    provenance_pages: set[int] = set()
    for item, _level in document.iterate_items(with_groups=False):
        provenance = list(getattr(item, "prov", ()) or ())
        if provenance:
            provenance_items += 1
        if any(getattr(row, "bbox", None) is not None for row in provenance):
            bbox_items += 1
        provenance_pages.update(
            int(row.page_no)
            for row in provenance
            if getattr(row, "page_no", None) is not None
        )
    table_cells = sum(
        len(getattr(getattr(table, "data", None), "table_cells", ()) or ())
        for table in document.tables
    )
    return {
        "pages": len(document.pages),
        "texts": len(document.texts),
        "tables": len(document.tables),
        "table_cells": table_cells,
        "pictures": len(document.pictures),
        "groups": len(document.groups),
        "key_value_items": len(document.key_value_items),
        "text_label_counts": dict(sorted(label_counts.items())),
        "items_with_provenance": provenance_items,
        "items_with_bbox": bbox_items,
        "provenance_pages": sorted(provenance_pages),
        "markdown_characters": len(markdown),
        "markdown_non_whitespace_characters": len("".join(markdown.split())),
    }


def _configure_runtime_isolation(
    attempt_dir: Path, model_root: Path
) -> dict[str, Any]:
    cache_root = attempt_dir / "runtime-cache"
    temp_root = cache_root / "temp"
    pycache_root = cache_root / "pycache"
    temp_root.mkdir(parents=True, exist_ok=True)
    pycache_root.mkdir(parents=True, exist_ok=False)
    if any(pycache_root.iterdir()):
        raise DoclingQualificationError("attempt_pycache_not_empty")
    sys.pycache_prefix = str(pycache_root)
    os.environ["TEMP"] = str(temp_root)
    os.environ["TMP"] = str(temp_root)
    os.environ["TMPDIR"] = str(temp_root)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_DATASETS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    os.environ["DOCLING_ARTIFACTS_PATH"] = str(model_root)
    os.environ["HF_HOME"] = str(cache_root / "huggingface")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(cache_root / "huggingface" / "hub")
    os.environ["TORCH_HOME"] = str(cache_root / "torch")
    return {
        "cache_root": str(cache_root),
        "temp_root": str(temp_root),
        "pycache_prefix": str(pycache_root),
        "pycache_initially_empty": True,
        "bytecode_writes_disabled_required": True,
        "known_remote_services_disabled": True,
        "os_level_airgap_proven": False,
    }


def _run_docling(
    *,
    input_identity: Mapping[str, Any],
    model_root: Path,
    attempt_dir: Path,
    runtime_isolation: Mapping[str, Any],
) -> dict[str, Any]:
    import torch
    from docling.backend.docling_parse_backend import (
        ThreadedDoclingParseDocumentBackend,
    )
    from docling.datamodel.accelerator_options import (
        AcceleratorDevice,
        AcceleratorOptions,
    )
    from docling.datamodel.backend_options import (
        ThreadedDoclingParseBackendOptions,
    )
    from docling.datamodel.base_models import ConversionStatus, InputFormat
    from docling.datamodel.pipeline_options import (
        LayoutObjectDetectionOptions,
        PdfPipelineOptions,
        TableFormerMode,
        TableStructureOptions,
    )
    from docling.datamodel.settings import settings
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.pipeline.standard_pdf_pipeline import StandardPdfPipeline

    settings.perf.page_batch_size = 1
    layout_options = LayoutObjectDetectionOptions.from_preset(
        "layout_heron_default"
    )
    layout_options.model_spec.revision = MODEL_REVISIONS[
        "docling-project/docling-layout-heron"
    ]["resolved_commit"]
    pipeline_options = PdfPipelineOptions(
        artifacts_path=model_root,
        allow_external_plugins=False,
        enable_remote_services=False,
        accelerator_options=AcceleratorOptions(
            device=AcceleratorDevice.CPU,
            num_threads=2,
        ),
        do_ocr=False,
        do_table_structure=True,
        table_structure_options=TableStructureOptions(
            mode=TableFormerMode.ACCURATE,
            do_cell_matching=True,
        ),
        layout_options=layout_options,
        force_backend_text=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        do_picture_description=False,
        do_picture_classification=False,
        do_chart_extraction=False,
        generate_page_images=False,
        generate_picture_images=False,
        generate_parsed_pages=False,
        layout_batch_size=1,
        table_batch_size=1,
        ocr_batch_size=1,
        queue_max_size=8,
        document_timeout=1800.0,
    )

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_cls=StandardPdfPipeline,
                pipeline_options=pipeline_options,
                backend=ThreadedDoclingParseDocumentBackend,
                backend_options=ThreadedDoclingParseBackendOptions(
                    parser_threads=2,
                    release_native_memory_every_n_pages=4,
                ),
            )
        },
    )

    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    with _PeakRssSampler() as sampler:
        result = converter.convert(
            Path(str(input_identity["path"])),
            raises_on_error=False,
            max_num_pages=int(input_identity["expected_pages"]),
            max_file_size=int(input_identity["bytes"]),
            page_range=tuple(int(value) for value in input_identity["page_range"]),
        )
    elapsed = time.perf_counter() - started
    if result.status != ConversionStatus.SUCCESS:
        errors = [error.model_dump(mode="json") for error in result.errors]
        raise DoclingQualificationError(
            f"docling_conversion_not_success:{result.status.value}:{errors}"
        )
    document = result.document
    markdown = document.export_to_markdown()
    exported = document.export_to_dict()
    metrics = _document_metrics(document, markdown)
    if metrics["pages"] != int(input_identity["expected_pages"]):
        raise DoclingQualificationError(
            f"docling_page_count_mismatch:{metrics['pages']}:"
            f"{input_identity['expected_pages']}"
        )
    if metrics["texts"] < 1 or metrics["markdown_non_whitespace_characters"] < 100:
        raise DoclingQualificationError("docling_output_substantively_empty")
    pycache_root = Path(str(runtime_isolation["pycache_prefix"]))
    if any(path.is_file() for path in pycache_root.rglob("*")):
        raise DoclingQualificationError("attempt_pycache_write_observed")
    return {
        "document": exported,
        "markdown": markdown,
        "metrics": metrics,
        "conversion": {
            "status": result.status.value,
            "errors": [error.model_dump(mode="json") for error in result.errors],
            "timings": {
                name: item.model_dump(mode="json")
                for name, item in sorted(result.timings.items())
            },
            "confidence": result.confidence.model_dump(mode="json"),
            "elapsed_seconds": round(elapsed, 6),
            "peak_process_rss_bytes": sampler.peak_bytes,
            "peak_cuda_allocated_bytes": (
                int(torch.cuda.max_memory_allocated())
                if torch.cuda.is_available()
                else 0
            ),
        },
        "execution_profile": {
            "pipeline": "standard_threaded",
            "pdf_backend": "threaded_docling_parse",
            "device": "cpu",
            "num_threads": 2,
            "page_batch_size": 1,
            "layout_batch_size": 1,
            "table_batch_size": 1,
            "queue_max_size": 8,
            "layout_model": "Heron",
            "layout_model_resolved_commit": MODEL_REVISIONS[
                "docling-project/docling-layout-heron"
            ]["resolved_commit"],
            "table_model": "TableFormer accurate",
            "table_model_resolved_commit": MODEL_REVISIONS[
                "docling-project/docling-models"
            ]["resolved_commit"],
            "ocr": False,
            "remote_services": False,
            "external_plugins": False,
            "enrichments": False,
            "temp_directory": str(runtime_isolation["temp_root"]),
            "temp_environment_bound_to_attempt": True,
            "pycache_prefix": str(runtime_isolation["pycache_prefix"]),
            "adjacent_pyc_read_isolated": True,
            "pycache_writes_observed": False,
            "python_process_network_attempts_observed": "NOT_INSTRUMENTED",
            "os_level_airgap_proven": False,
        },
    }


def _receipt_base(
    *,
    mode: str,
    repository_root: Path,
    model_root: Path,
    case_id: str,
    script_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "script": {
            "path": str(script_path),
            "sha256": sha256_file(script_path),
        },
        "repository": _git_state(repository_root),
        "runtime": _runtime_manifest(),
        "models": _validate_file_manifest(model_root, EXPECTED_MODEL_FILES),
        "input": _input_identity(repository_root, case_id),
        "resource_before": _resource_snapshot(),
        "contract": {
            "docling_version_supersedes": "2.117.0",
            "docling_version": "2.124.0",
            "candidate_not_evidence": True,
            "development_qualification_only": True,
            "remote_services_forbidden": True,
            "external_plugins_forbidden": True,
            "ocr_not_tested": True,
            "adoption_not_decided_by_execution_success": True,
        },
    }


def run(args: argparse.Namespace) -> int:
    repository_root = Path(args.repository_root).resolve()
    model_root = _qualification_path(Path(args.model_root))
    attempt_dir = _qualification_path(Path(args.attempt_dir))
    receipt_path = attempt_dir / "receipt.json"
    _claim_attempt_directory(attempt_dir)
    base: dict[str, Any] = {}
    try:
        runtime_isolation = _configure_runtime_isolation(
            attempt_dir, model_root
        )
        base = _receipt_base(
            mode=args.mode,
            repository_root=repository_root,
            model_root=model_root,
            case_id=args.case_id,
            script_path=Path(__file__).resolve(),
        )
        base["runtime_isolation"] = runtime_isolation
        resource_gate = _resource_gate(base["resource_before"])
        base["resource_gate"] = resource_gate
        if not resource_gate["passed"]:
            receipt = {
                **base,
                "status": "HOLD_RESOURCE",
                "decision": {
                    "component_execution": "NOT_STARTED",
                    "adoption": "NOT_DECIDED",
                    "reasons": resource_gate["failures"],
                },
            }
            receipt["result_digest"] = canonical_digest(receipt)
            _exclusive_write_json(receipt_path, receipt)
            return 2
        if base["repository"]["dirty"]:
            receipt = {
                **base,
                "status": "HOLD_IMPLEMENTATION_BINDING",
                "decision": {
                    "component_execution": "NOT_STARTED",
                    "adoption": "NOT_DECIDED",
                    "reasons": ["repository_dirty_or_untracked"],
                },
            }
            receipt["result_digest"] = canonical_digest(receipt)
            _exclusive_write_json(receipt_path, receipt)
            return 2
        if args.mode == "preflight":
            receipt = {
                **base,
                "status": "READY_FOR_CONTROL_RUN",
                "decision": {
                    "component_execution": "NOT_STARTED",
                    "adoption": "NOT_DECIDED",
                    "reasons": [],
                },
            }
            receipt["result_digest"] = canonical_digest(receipt)
            _exclusive_write_json(receipt_path, receipt)
            return 0

        attempt_start = {
            **base,
            "schema_version": "fin_ia_s1_docling_pdf_attempt_start_v1_0",
            "status": "STARTED_IMMUTABLE_INPUTS_FROZEN",
        }
        attempt_start["result_digest"] = canonical_digest(attempt_start)
        _exclusive_write_json(attempt_dir / "attempt-start.json", attempt_start)
        output = _run_docling(
            input_identity=base["input"],
            model_root=model_root,
            attempt_dir=attempt_dir,
            runtime_isolation=runtime_isolation,
        )
        end_bindings = {
            "repository": _git_state(repository_root),
            "runtime": _runtime_manifest(),
            "models": _validate_file_manifest(model_root, EXPECTED_MODEL_FILES),
            "input": _input_identity(repository_root, args.case_id),
            "script_sha256": sha256_file(Path(__file__).resolve()),
        }
        if end_bindings["repository"] != base["repository"]:
            raise DoclingQualificationError("repository_changed_during_run")
        if end_bindings["runtime"] != base["runtime"]:
            raise DoclingQualificationError("runtime_changed_during_run")
        if end_bindings["models"] != base["models"]:
            raise DoclingQualificationError("model_files_changed_during_run")
        if end_bindings["input"] != base["input"]:
            raise DoclingQualificationError("input_changed_during_run")
        if end_bindings["script_sha256"] != base["script"]["sha256"]:
            raise DoclingQualificationError("script_changed_during_run")
        document_path = attempt_dir / "docling-document.json"
        markdown_path = attempt_dir / "docling-document.md"
        _atomic_write_json(document_path, output["document"])
        _atomic_write_text(markdown_path, output["markdown"])
        receipt = {
            **base,
            "status": "COMPONENT_OUTPUT_READY_FOR_COMPARISON",
            "execution_profile": output["execution_profile"],
            "conversion": output["conversion"],
            "metrics": output["metrics"],
            "start_end_bindings": {
                "repository_unchanged": True,
                "runtime_unchanged": True,
                "models_unchanged": True,
                "input_unchanged": True,
                "script_unchanged": True,
            },
            "outputs": {
                "document_json": {
                    "path": str(document_path),
                    "bytes": document_path.stat().st_size,
                    "sha256": sha256_file(document_path),
                },
                "markdown": {
                    "path": str(markdown_path),
                    "bytes": markdown_path.stat().st_size,
                    "sha256": sha256_file(markdown_path),
                },
            },
            "resource_after": _resource_snapshot(),
            "decision": {
                "component_execution": "PASS",
                "adoption": "NOT_DECIDED_PENDING_BASELINE_AND_HUMAN_REVIEW",
                "candidate_is_not_evidence": True,
                "ocr": "NOT_TESTED",
            },
        }
        receipt["result_digest"] = canonical_digest(receipt)
        _exclusive_write_json(receipt_path, receipt)
        return 0
    except Exception as exc:
        failure = {
            **base,
            "schema_version": SCHEMA_VERSION,
            "mode": args.mode,
            "status": "FAILED_WITH_EVIDENCE",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
            "decision": {
                "component_execution": "FAIL",
                "adoption": "NOT_DECIDED",
            },
        }
        failure["result_digest"] = canonical_digest(failure)
        _exclusive_write_json(receipt_path, failure)
        return 1


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight", "run"), required=True)
    parser.add_argument("--case-id", choices=tuple(CASES), required=True)
    parser.add_argument("--repository-root", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--attempt-dir", required=True)
    return parser.parse_args(argv)


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
