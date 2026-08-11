from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Iterable, Iterator


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from evidence.schema import EvidenceObject  # noqa: E402
from evidence.structured_extractor import extract_structured_objects  # noqa: E402
from evidence.structured_objects import (  # noqa: E402
    ClaimObject,
    MetricObject,
    TableObject,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build TableObject, MetricObject, and ClaimObject JSONL from EvidenceObject JSONL."
    )
    parser.add_argument(
        "--evidence-path",
        default="data/processed_private/evidence_objects/sec_tech_10k_evidence.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed_private/structured_objects",
    )
    parser.add_argument("--prefix", default="sec_tech_10k")
    parser.add_argument(
        "--progress-every",
        type=int,
        default=5000,
        help="Print progress to stderr every N evidence rows.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes for batch-level structured extraction.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Evidence rows per worker task.",
    )
    parser.add_argument("--limit", type=int, help="Optional max evidence rows to process.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    evidence_path = REPO_ROOT / args.evidence_path
    output_dir = REPO_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    per_ticker = defaultdict(lambda: {"tables": 0, "metrics": 0, "claims": 0})
    evidence_with_tables = 0
    table_path = output_dir / f"{args.prefix}_tables.jsonl"
    metric_path = output_dir / f"{args.prefix}_metrics.jsonl"
    claim_path = output_dir / f"{args.prefix}_claims.jsonl"
    summary_path = output_dir / f"{args.prefix}_structured_summary.json"
    tmp_paths = {
        "tables": table_path.with_suffix(table_path.suffix + ".tmp"),
        "metrics": metric_path.with_suffix(metric_path.suffix + ".tmp"),
        "claims": claim_path.with_suffix(claim_path.suffix + ".tmp"),
    }

    evidence_count = 0
    table_count = 0
    metric_count = 0
    claim_count = 0
    metric_method_counts = Counter()
    claim_type_counts = Counter()
    top_metric_names = Counter()

    with ExitStack() as stack:
        table_f = stack.enter_context(tmp_paths["tables"].open("w", encoding="utf-8"))
        metric_f = stack.enter_context(tmp_paths["metrics"].open("w", encoding="utf-8"))
        claim_f = stack.enter_context(tmp_paths["claims"].open("w", encoding="utf-8"))
        batch_iter = iter_evidence_jsonl_batches(
            evidence_path,
            batch_size=max(1, args.batch_size),
            limit=args.limit,
        )
        for result in iter_structured_batch_results(batch_iter, max(1, args.workers)):
            _write_lines(table_f, result["table_lines"])
            _write_lines(metric_f, result["metric_lines"])
            _write_lines(claim_f, result["claim_lines"])
            evidence_count += int(result["evidence_count"])
            evidence_with_tables += int(result["evidence_with_tables"])
            table_count += int(result["table_count"])
            metric_count += int(result["metric_count"])
            claim_count += int(result["claim_count"])
            for ticker, counts in result["per_ticker"].items():
                per_ticker[ticker]["tables"] += int(counts.get("tables") or 0)
                per_ticker[ticker]["metrics"] += int(counts.get("metrics") or 0)
                per_ticker[ticker]["claims"] += int(counts.get("claims") or 0)
            metric_method_counts.update(result["metric_method_counts"])
            claim_type_counts.update(result["claim_type_counts"])
            top_metric_names.update(result["top_metric_names"])
            if args.progress_every and evidence_count % args.progress_every == 0:
                print(
                    json.dumps(
                        {
                            "progress": evidence_count,
                            "tables": table_count,
                            "metrics": metric_count,
                            "claims": claim_count,
                        },
                        ensure_ascii=False,
                    ),
                    file=sys.stderr,
                )

    tmp_paths["tables"].replace(table_path)
    tmp_paths["metrics"].replace(metric_path)
    tmp_paths["claims"].replace(claim_path)

    summary = {
        "input_evidence_path": str(evidence_path),
        "evidence_count": evidence_count,
        "evidence_with_tables": evidence_with_tables,
        "table_count": table_count,
        "metric_count": metric_count,
        "claim_count": claim_count,
        "metric_method_counts": dict(metric_method_counts),
        "claim_type_counts": dict(claim_type_counts),
        "top_metric_names": top_metric_names.most_common(30),
        "per_ticker": dict(sorted(per_ticker.items())),
        "workers": max(1, args.workers),
        "batch_size": max(1, args.batch_size),
        "outputs": {
            "tables": str(table_path),
            "metrics": str(metric_path),
            "claims": str(claim_path),
            "summary": str(summary_path),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def iter_evidence_jsonl_batches(
    path: Path,
    *,
    batch_size: int,
    limit: int | None,
) -> Iterator[list[tuple[int, str]]]:
    batch: list[tuple[int, str]] = []
    emitted = 0
    with path.open("r", encoding="utf-8") as f:
        for line_number, line in enumerate(f, start=1):
            if limit is not None and emitted >= limit:
                break
            stripped = line.strip()
            if not stripped:
                continue
            batch.append((line_number, stripped))
            emitted += 1
            if len(batch) >= batch_size:
                yield batch
                batch = []
    if batch:
        yield batch


def iter_structured_batch_results(
    batches: Iterator[list[tuple[int, str]]],
    workers: int,
) -> Iterator[dict[str, Any]]:
    if workers <= 1:
        for batch in batches:
            yield _build_structured_batch(batch)
        return

    max_pending = max(workers * 2, 1)
    with ProcessPoolExecutor(max_workers=workers) as executor:
        pending: set[Future] = set()

        def submit_next() -> bool:
            try:
                batch = next(batches)
            except StopIteration:
                return False
            pending.add(executor.submit(_build_structured_batch, batch))
            return True

        for _ in range(max_pending):
            if not submit_next():
                break

        while pending:
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            for future in done:
                yield future.result()
                submit_next()


def _build_structured_batch(batch: list[tuple[int, str]]) -> dict[str, Any]:
    table_lines: list[str] = []
    metric_lines: list[str] = []
    claim_lines: list[str] = []
    per_ticker = defaultdict(lambda: {"tables": 0, "metrics": 0, "claims": 0})
    metric_method_counts = Counter()
    claim_type_counts = Counter()
    top_metric_names = Counter()
    evidence_with_tables = 0

    for line_number, line in batch:
        try:
            evidence = EvidenceObject.model_validate_json(line)
        except ValueError as exc:
            raise ValueError(f"Invalid EvidenceObject JSONL at line {line_number}") from exc
        result = extract_structured_objects(evidence)
        table_lines.extend(obj.to_jsonl_line() for obj in result.tables)
        metric_lines.extend(obj.to_jsonl_line() for obj in result.metrics)
        claim_lines.extend(obj.to_jsonl_line() for obj in result.claims)
        if result.tables:
            evidence_with_tables += 1
        per_ticker[evidence.ticker]["tables"] += len(result.tables)
        per_ticker[evidence.ticker]["metrics"] += len(result.metrics)
        per_ticker[evidence.ticker]["claims"] += len(result.claims)
        metric_method_counts.update(metric.extraction_method for metric in result.metrics)
        claim_type_counts.update(claim.claim_type for claim in result.claims)
        top_metric_names.update(metric.metric_name for metric in result.metrics)

    return {
        "table_lines": table_lines,
        "metric_lines": metric_lines,
        "claim_lines": claim_lines,
        "evidence_count": len(batch),
        "evidence_with_tables": evidence_with_tables,
        "table_count": len(table_lines),
        "metric_count": len(metric_lines),
        "claim_count": len(claim_lines),
        "per_ticker": dict(per_ticker),
        "metric_method_counts": dict(metric_method_counts),
        "claim_type_counts": dict(claim_type_counts),
        "top_metric_names": dict(top_metric_names),
    }


def _write_objects(handle, objects: Iterable[TableObject | MetricObject | ClaimObject]) -> None:
    for obj in objects:
        handle.write(obj.to_jsonl_line())
        handle.write("\n")


def _write_lines(handle, lines: Iterable[str]) -> None:
    for line in lines:
        handle.write(line)
        handle.write("\n")


if __name__ == "__main__":
    main()
