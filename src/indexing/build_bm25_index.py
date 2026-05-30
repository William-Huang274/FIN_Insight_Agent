from __future__ import annotations

import json
import pickle
import sys
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from pathlib import Path
from typing import Any, Iterator

from rank_bm25 import BM25Okapi

from evidence.schema import EvidenceObject
from retrieval.text import evidence_search_text, tokenize


def build_bm25_index(
    evidence_path: str | Path,
    output_dir: str | Path,
    *,
    workers: int = 1,
    batch_size: int = 1000,
    progress_every: int = 0,
    validate_schema: bool = False,
) -> dict:
    evidence_path = Path(evidence_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    records_path = output_path / "records.jsonl"
    records_tmp_path = output_path / "records.jsonl.tmp"
    bm25_path = output_path / "bm25.pkl"
    bm25_tmp_path = output_path / "bm25.pkl.tmp"
    metadata_path = output_path / "metadata.json"
    for tmp_path in (records_tmp_path, bm25_tmp_path):
        if tmp_path.exists():
            tmp_path.unlink()

    record_count = 0
    tokenized_corpus: list[list[str]] = []
    with records_tmp_path.open("w", encoding="utf-8") as record_handle:
        batch_iter = _iter_evidence_jsonl_batches(evidence_path, batch_size=max(1, int(batch_size)))
        for result in _iter_tokenized_batch_results(
            batch_iter,
            workers=max(1, int(workers)),
            validate_schema=validate_schema,
        ):
            tokenized_corpus.extend(result["tokenized_corpus"])
            for line in result["record_lines"]:
                record_handle.write(line)
                record_handle.write("\n")
            record_count += int(result["record_count"])
            if progress_every and record_count % progress_every == 0:
                print(json.dumps({"progress": record_count}, ensure_ascii=False), file=sys.stderr)

    bm25 = BM25Okapi(tokenized_corpus)

    with bm25_tmp_path.open("wb") as f:
        pickle.dump(bm25, f)
    records_tmp_path.replace(records_path)
    bm25_tmp_path.replace(bm25_path)
    metadata = {
        "evidence_path": str(evidence_path),
        "records": record_count,
        "index_type": "rank_bm25",
        "workers": max(1, int(workers)),
        "batch_size": max(1, int(batch_size)),
        "validate_schema": bool(validate_schema),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return metadata


def _iter_evidence_jsonl_batches(path: Path, *, batch_size: int) -> Iterator[list[tuple[int, str]]]:
    batch: list[tuple[int, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            batch.append((line_number, stripped))
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def _iter_tokenized_batch_results(
    batches: Iterator[list[tuple[int, str]]],
    *,
    workers: int,
    validate_schema: bool,
) -> Iterator[dict[str, Any]]:
    if workers <= 1:
        for batch in batches:
            yield _tokenize_batch(batch, validate_schema)
        return

    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: set[Future] = set()

        def submit_next() -> bool:
            try:
                batch = next(batches)
            except StopIteration:
                return False
            pending.add(executor.submit(_tokenize_batch, batch, validate_schema))
            return True

        for _ in range(max_pending):
            if not submit_next():
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit_next()


def _tokenize_batch(batch: list[tuple[int, str]], validate_schema: bool) -> dict[str, Any]:
    tokenized_corpus: list[list[str]] = []
    record_lines: list[str] = []
    for line_number, line in batch:
        try:
            if validate_schema:
                record = EvidenceObject.model_validate_json(line).model_dump(mode="json")
            else:
                record = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"Invalid EvidenceObject JSONL at line {line_number}") from exc
        tokenized_corpus.append(tokenize(evidence_search_text(record)))
        record_lines.append(json.dumps(record, ensure_ascii=False))
    return {
        "record_count": len(batch),
        "tokenized_corpus": tokenized_corpus,
        "record_lines": record_lines,
    }
