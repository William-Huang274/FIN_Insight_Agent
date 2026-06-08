from __future__ import annotations

import importlib.util
from argparse import Namespace
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_builder_module():
    path = REPO_ROOT / "scripts" / "ledger" / "10_build_lightweight_ledger_store.py"
    spec = importlib.util.spec_from_file_location("lightweight_ledger_builder_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_append_row_values_streaming_flushes_without_large_pending_copy() -> None:
    module = _load_builder_module()
    writer = _FakeLedgerWriter()

    pending: list[list[int]] = []
    pending = module._append_row_values_streaming([[0], [1], [2], [3]], writer, pending, batch_size=3)
    pending = module._append_row_values_streaming([[4], [5], [6]], writer, pending, batch_size=3)

    assert writer.batches == [[[0], [1], [2]], [[3], [4], [5]]]
    assert pending == [[6]]
    assert writer.row_count == 6


def test_append_row_values_streaming_normalizes_tiny_batch_size() -> None:
    module = _load_builder_module()
    writer = _FakeLedgerWriter()

    pending = module._append_row_values_streaming([[0], [1]], writer, [], batch_size=0)

    assert writer.batches == [[[0]], [[1]]]
    assert pending == []


def test_ledger_writer_context_supports_csv_copy(tmp_path: Path) -> None:
    module = _load_builder_module()
    args = Namespace(
        write_mode="csv_copy",
        duckdb_threads=1,
        transaction_commit_rows=0,
        staging_csv_path=str(tmp_path / "rows.tsv"),
    )

    writer = module._ledger_writer_context(args, tmp_path / "ledger.duckdb.tmp")

    assert writer.__class__.__name__ == "LedgerStoreBulkCsvWriter"


class _FakeLedgerWriter:
    def __init__(self) -> None:
        self.batches: list[list[list[int]]] = []
        self.row_count = 0

    def append_row_values(self, rows: list[list[int]]) -> None:
        self.batches.append([list(row) for row in rows])
        self.row_count += len(rows)
