from __future__ import annotations

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.qualification import run_s1_docling_pdf_qualification as runner
from scripts.qualification.run_s1_docling_pdf_qualification import (
    DoclingQualificationError,
    _configure_runtime_isolation,
    _document_metrics,
    _distribution_module_ownership,
    _exclusive_write_json,
    _resource_gate,
    _validate_file_manifest,
    _verify_distribution_record_files,
    sha256_file,
)


def test_exclusive_receipt_write_cannot_overwrite(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"
    _exclusive_write_json(receipt, {"status": "first"})

    with pytest.raises(FileExistsError):
        _exclusive_write_json(receipt, {"status": "replacement"})

    assert receipt.read_text(encoding="utf-8").count('"status": "first"') == 1


def test_run_atomically_claims_attempt_and_preserves_terminal_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model_root = tmp_path / "models"
    attempt_dir = tmp_path / "attempts" / "concurrent"
    args = argparse.Namespace(
        mode="preflight",
        case_id="dell_fy26_results",
        repository_root=str(tmp_path),
        model_root=str(model_root),
        attempt_dir=str(attempt_dir),
    )
    monkeypatch.setattr(runner, "QUALIFICATION_ROOT", tmp_path)
    for name in (
        "TEMP",
        "TMP",
        "TMPDIR",
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_DATASETS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "DO_NOT_TRACK",
        "DOCLING_ARTIFACTS_PATH",
        "HF_HOME",
        "HUGGINGFACE_HUB_CACHE",
        "TORCH_HOME",
    ):
        monkeypatch.setenv(name, runner.os.environ.get(name, ""))
    monkeypatch.setattr(
        runner.sys, "pycache_prefix", runner.sys.pycache_prefix
    )
    monkeypatch.setattr(
        runner,
        "_receipt_base",
        lambda **_kwargs: {
            "resource_before": {
                "d_free_gib": 3.0,
                "z_free_gib": 20.0,
                "free_physical_memory_gib": 2.0,
            }
        },
    )

    def invoke() -> str:
        try:
            return f"return:{runner.run(args)}"
        except DoclingQualificationError as exc:
            return f"error:{exc}"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(lambda _index: invoke(), range(2)))

    assert outcomes[0].startswith("error:attempt_directory_already_claimed:")
    assert outcomes[1] == "return:2"
    receipt = attempt_dir / "receipt.json"
    original = receipt.read_bytes()
    assert b'"status": "HOLD_RESOURCE"' in original

    with pytest.raises(
        DoclingQualificationError, match="attempt_directory_already_claimed"
    ):
        runner.run(args)
    assert receipt.read_bytes() == original


def test_runtime_isolation_redirects_temp_and_ignores_adjacent_pyc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    attempt_dir = tmp_path / "attempt"
    attempt_dir.mkdir()
    model_root = tmp_path / "models"
    model_root.mkdir()
    isolated_environment: dict[str, str] = {}
    monkeypatch.setattr(runner.os, "environ", isolated_environment)
    monkeypatch.setattr(runner.sys, "pycache_prefix", None)

    result = _configure_runtime_isolation(attempt_dir, model_root)

    assert runner.sys.pycache_prefix == result["pycache_prefix"]
    assert Path(result["pycache_prefix"]).is_dir()
    assert list(Path(result["pycache_prefix"]).iterdir()) == []
    assert isolated_environment["TEMP"] == result["temp_root"]
    assert isolated_environment["TMP"] == result["temp_root"]
    assert isolated_environment["TMPDIR"] == result["temp_root"]
    assert isolated_environment["HF_HUB_OFFLINE"] == "1"
    assert isolated_environment["DOCLING_ARTIFACTS_PATH"] == str(model_root)


def test_validate_file_manifest_binds_bytes_and_digest(tmp_path: Path) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"frozen-model")

    result = _validate_file_manifest(
        tmp_path,
        {
            "model.bin": {
                "bytes": model.stat().st_size,
                "sha256": sha256_file(model),
            }
        },
    )

    assert result["total_bytes"] == len(b"frozen-model")
    assert result["files"][0]["relative_path"] == "model.bin"
    assert len(result["model_package_digest"]) == 64


def test_validate_file_manifest_rejects_digest_drift(tmp_path: Path) -> None:
    model = tmp_path / "model.bin"
    model.write_bytes(b"changed-model")

    with pytest.raises(
        DoclingQualificationError, match="model_file_digest_mismatch:model.bin"
    ):
        _validate_file_manifest(
            tmp_path,
            {
                "model.bin": {
                    "bytes": model.stat().st_size,
                    "sha256": "0" * 64,
                }
            },
        )


def test_runtime_module_must_be_owned_by_bound_distribution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = tmp_path / "docling" / "__init__.py"
    module.parent.mkdir()
    module.write_text("", encoding="utf-8")

    class _Distribution:
        version = "2.124.0"
        files = [Path("docling/__init__.py")]

        @staticmethod
        def locate_file(path: str) -> Path:
            return tmp_path / path

    monkeypatch.setattr(
        runner.importlib.metadata,
        "distribution",
        lambda _name: _Distribution(),
    )
    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace(origin=str(module)),
    )

    result = _distribution_module_ownership("docling-slim", "docling")

    assert result["distribution"] == "docling-slim"
    assert result["distribution_relative_path"] == "docling/__init__.py"
    assert result["distribution_file_count"] == 1


def test_runtime_module_rejects_unowned_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = tmp_path / "docling" / "__init__.py"
    module.parent.mkdir()
    module.write_text("", encoding="utf-8")

    class _Distribution:
        version = "2.124.0"
        files = [Path("different_package/__init__.py")]

        @staticmethod
        def locate_file(path: str) -> Path:
            return tmp_path / path

    monkeypatch.setattr(
        runner.importlib.metadata,
        "distribution",
        lambda _name: _Distribution(),
    )
    monkeypatch.setattr(
        runner.importlib.util,
        "find_spec",
        lambda _name: SimpleNamespace(origin=str(module)),
    )

    with pytest.raises(
        DoclingQualificationError,
        match="runtime_module_not_owned_by_distribution",
    ):
        _distribution_module_ownership("docling-slim", "docling")


def test_distribution_record_verifies_installed_file_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime_file = tmp_path / "docling" / "runtime.py"
    runtime_file.parent.mkdir()
    payload = b"bound-runtime-code"
    runtime_file.write_bytes(payload)
    encoded_digest = base64.urlsafe_b64encode(
        hashlib.sha256(payload).digest()
    ).rstrip(b"=").decode("ascii")
    record = (
        f"docling/runtime.py,sha256={encoded_digest},{len(payload)}\n"
        "docling_slim.dist-info/RECORD,,\n"
    )

    class _Distribution:
        @staticmethod
        def read_text(name: str) -> str | None:
            assert name == "RECORD"
            return record

        @staticmethod
        def locate_file(path: str) -> Path:
            return tmp_path / path

    monkeypatch.setattr(
        runner.importlib.metadata,
        "distribution",
        lambda _name: _Distribution(),
    )

    result = _verify_distribution_record_files(
        "docling-slim", allowed_root=tmp_path
    )

    assert result["record_rows"] == 2
    assert result["hashed_files_verified"] == 1
    assert result["unhashed_rows"] == 1
    assert result["verified_bytes"] == len(payload)

    runtime_file.write_bytes(b"drifted-runtime-code")
    with pytest.raises(
        DoclingQualificationError,
        match="distribution_file_size_mismatch|distribution_file_digest_mismatch",
    ):
        _verify_distribution_record_files(
            "docling-slim", allowed_root=tmp_path
        )


@pytest.mark.parametrize(
    ("snapshot", "expected_failure"),
    [
        (
            {
                "d_free_gib": 2.49,
                "z_free_gib": 20.0,
                "free_physical_memory_gib": 4.0,
            },
            "d_free_below_stop_line",
        ),
        (
            {
                "d_free_gib": 3.0,
                "z_free_gib": 11.99,
                "free_physical_memory_gib": 4.0,
            },
            "z_free_below_stop_line",
        ),
        (
            {
                "d_free_gib": 3.0,
                "z_free_gib": 20.0,
                "free_physical_memory_gib": 2.99,
            },
            "free_memory_below_runtime_safety_line",
        ),
    ],
)
def test_resource_gate_fails_closed(
    snapshot: dict[str, float], expected_failure: str
) -> None:
    result = _resource_gate(snapshot)

    assert result["passed"] is False
    assert expected_failure in result["failures"]


def test_resource_gate_passes_at_thresholds() -> None:
    result = _resource_gate(
        {
            "d_free_gib": 2.5,
            "z_free_gib": 12.0,
            "free_physical_memory_gib": 3.0,
        }
    )

    assert result["passed"] is True
    assert result["failures"] == []


@dataclass
class _Label:
    value: str


@dataclass
class _Provenance:
    page_no: int
    bbox: object | None


@dataclass
class _Item:
    prov: list[_Provenance]


@dataclass
class _Text:
    label: _Label


@dataclass
class _TableData:
    table_cells: list[object]


@dataclass
class _Table:
    data: _TableData


class _Document:
    pages = {1: object(), 2: object()}
    texts = [_Text(_Label("text")), _Text(_Label("section_header"))]
    tables = [_Table(_TableData([object(), object()]))]
    pictures = [object()]
    groups = []
    key_value_items = []

    def iterate_items(self, *, with_groups: bool):
        assert with_groups is False
        yield _Item([_Provenance(1, object())]), 0
        yield _Item([_Provenance(2, None)]), 0
        yield _Item([]), 0


def test_document_metrics_preserve_provenance_and_table_counts() -> None:
    metrics = _document_metrics(_Document(), "one two three")

    assert metrics["pages"] == 2
    assert metrics["texts"] == 2
    assert metrics["tables"] == 1
    assert metrics["table_cells"] == 2
    assert metrics["items_with_provenance"] == 2
    assert metrics["items_with_bbox"] == 1
    assert metrics["provenance_pages"] == [1, 2]
    assert metrics["text_label_counts"] == {
        "section_header": 1,
        "text": 1,
    }
