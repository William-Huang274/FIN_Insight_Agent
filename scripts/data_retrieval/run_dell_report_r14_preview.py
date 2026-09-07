from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from retrieval.dell_report_population_manifest_r14 import (  # noqa: E402
    build_input_population_manifest_r14,
)
from retrieval.dell_report_r14_common import (  # noqa: E402
    TARGET_IDS,
    canonical_digest,
    file_sha256,
)
from retrieval.dell_report_r14_contracts import (  # noqa: E402
    load_and_validate_r14_contracts,
)
from retrieval.dell_report_resource_gate_r14 import (  # noqa: E402
    FROZEN_HARD_LIMIT_MS,
    FROZEN_HARD_MEMORY_LIMIT_BYTES,
    FROZEN_WARNING_LIMIT_MS,
)
from retrieval.dell_report_runner_r14 import (  # noqa: E402
    run_measured_full_program_r14,
)


SOURCE_PATH = ROOT / "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/v5/records.jsonl"
OBJECT_PATH = ROOT / "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v9/objects.jsonl"


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"not_object:{path}:{line_number}")
            rows.append(value)
    return rows


def _bounded_population(
    source_rows: list[dict], object_rows: list[dict], *, source_limit: int, object_limit: int
) -> tuple[list[dict], list[dict]]:
    if source_limit > 0:
        source_rows = source_rows[:source_limit]
    source_ids = {row["evidence_id"] for row in source_rows}
    object_rows = [
        row
        for row in object_rows
        if row.get("base_object_view", {}).get("source_record_id") in source_ids
        and set(row.get("lineage_source_record_ids") or ()) <= source_ids
    ]
    if object_limit > 0:
        object_rows = object_rows[:object_limit]
    referenced_ids = {
        source_id
        for row in object_rows
        for source_id in row.get("lineage_source_record_ids") or ()
    }
    source_rows = [row for row in source_rows if row["evidence_id"] in referenced_ids]
    return source_rows, object_rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-limit", type=int, default=0)
    parser.add_argument("--object-limit", type=int, default=0)
    args = parser.parse_args()

    source_rows = _read_jsonl(SOURCE_PATH)
    object_rows = _read_jsonl(OBJECT_PATH)
    source_rows, object_rows = _bounded_population(
        source_rows,
        object_rows,
        source_limit=args.source_limit,
        object_limit=args.object_limit,
    )
    manifest = build_input_population_manifest_r14(
        source_rows=source_rows,
        object_rows=object_rows,
        source_ref=SOURCE_PATH.relative_to(ROOT).as_posix(),
        source_sha256=file_sha256(SOURCE_PATH),
        object_ref=OBJECT_PATH.relative_to(ROOT).as_posix(),
        object_sha256=file_sha256(OBJECT_PATH),
        implementation_identity="WORKTREE::R14::ZERO_CALL_PREVIEW",
        changed_path_digest=canonical_digest(
            {
                "source_limit": args.source_limit,
                "object_limit": args.object_limit,
                "mode": "read_only_stdout_only",
            }
        ),
        recorded_at="2026-08-29T00:00:00+08:00",
    )
    bundle = load_and_validate_r14_contracts(root=ROOT)
    routes = {target_id: "03C_EXTERNAL_LADDER_AFTER_R14" for target_id in TARGET_IDS}
    result, performance = run_measured_full_program_r14(
        manifest=manifest,
        source_rows=source_rows,
        object_rows=object_rows,
        bundle=bundle,
        route_registry=routes,
        warning_limit_ms=FROZEN_WARNING_LIMIT_MS,
        hard_limit_ms=FROZEN_HARD_LIMIT_MS,
        hard_memory_limit_bytes=FROZEN_HARD_MEMORY_LIMIT_BYTES,
    )
    output = {
        "schema_version": "fin_ia_dell_03B_R14_stdout_preview_summary_v1_0",
        "mode": "FULL" if not args.source_limit and not args.object_limit else "BOUNDED",
        "source_count": len(source_rows),
        "compiled_object_count": len(object_rows),
        "manifest_result_digest": manifest["result_digest"],
        "program_receipt": result.program_receipt,
        "performance_receipt": performance,
        "model_provider_calls": 0,
        "files_written": 0,
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
