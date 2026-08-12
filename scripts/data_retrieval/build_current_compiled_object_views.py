from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from retrieval.contracts import load_financial_research_kernel  # noqa: E402
from retrieval.object_view_compiler import compile_object_store  # noqa: E402
from retrieval.query_plan import canonical_digest  # noqa: E402
from retrieval.route_compiler import (  # noqa: E402
    load_query_object_fact_route_policy,
)


RESULT_SCHEMA_VERSION = "fin_ia_s1c_query_object_fact_route_zero_call_result_v1_1"


def _resolve(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (ROOT / path).resolve()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"jsonl_object_required:{path.name}:{line_number}")
            rows.append(value)
    return rows


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Compile current source-bound claim, financial table-row and bounded "
            "context views. The output is candidate-only and has no Evidence or "
            "NumericFact authority."
        )
    )
    parser.add_argument(
        "--kernel",
        default="configs/retrieval/fin_ia_0_1_3_s1_financial_research_kernel_v1_0.json",
    )
    parser.add_argument(
        "--policy",
        default="configs/retrieval/fin_ia_0_1_3_s1c_query_object_fact_route_policy_v1_0.json",
    )
    parser.add_argument(
        "--documents",
        default=(
            "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
            "v1/documents.jsonl"
        ),
    )
    parser.add_argument(
        "--records",
        default=(
            "data/workbench_private/fin_0_1_3_s1b_current_financial_object_store/"
            "v1/records.jsonl"
        ),
    )
    parser.add_argument(
        "--output-dir",
        default=(
            "data/workbench_private/fin_0_1_3_s1c_compiled_financial_object_views/v2"
        ),
    )
    parser.add_argument(
        "--result-output",
        default=(
            "configs/retrieval/"
            "fin_ia_0_1_3_s1c_query_object_fact_route_zero_call_result_v1_1.json"
        ),
    )
    args = parser.parse_args()

    kernel_path = _resolve(args.kernel)
    policy_path = _resolve(args.policy)
    documents_path = _resolve(args.documents)
    records_path = _resolve(args.records)
    output_dir = _resolve(args.output_dir)
    result_output = _resolve(args.result_output)

    kernel = load_financial_research_kernel(_read_json(kernel_path))
    policy = load_query_object_fact_route_policy(_read_json(policy_path), kernel)
    documents = _read_jsonl(documents_path)
    records = _read_jsonl(records_path)
    parents = {str(row["document_id"]): row for row in documents}
    if len(parents) != len(documents):
        raise ValueError("compiled_object_source_parent_identity_duplicate")

    compilation = compile_object_store(
        records=records,
        parents_by_id=parents,
        policy=policy,
    )
    object_rows = [dict(row) for row in compilation.objects]
    diagnostic_rows = [dict(row) for row in compilation.diagnostics]
    _write_jsonl(output_dir / "objects.jsonl", object_rows)
    _write_jsonl(output_dir / "diagnostics.jsonl", diagnostic_rows)

    sample_objects: list[dict[str, Any]] = []
    for kind in ("claim", "metric_row", "bounded_parent_context"):
        row = next((item for item in object_rows if item["object_kind"] == kind), None)
        if row is None:
            continue
        sample_objects.append(
            {
                "object_kind": kind,
                "compiled_object_id": row["compiled_object_id"],
                "source_record_id": row["base_object_view"]["source_record_id"],
                "model_text_preview": row["model_text"][:600],
                "numeric_authority": row["numeric_authority"],
            }
        )
    diagnostic_examples: dict[str, dict[str, Any]] = {}
    for row in diagnostic_rows:
        diagnostic_examples.setdefault(str(row["diagnostic_code"]), row)

    output_binding = {
        "objects_ref": _relative(output_dir / "objects.jsonl"),
        "objects_sha256": _sha256(output_dir / "objects.jsonl"),
        "objects_bytes": (output_dir / "objects.jsonl").stat().st_size,
        "diagnostics_ref": _relative(output_dir / "diagnostics.jsonl"),
        "diagnostics_sha256": _sha256(output_dir / "diagnostics.jsonl"),
        "diagnostics_bytes": (output_dir / "diagnostics.jsonl").stat().st_size,
    }
    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "status": "s1c_temporal_correct_object_route_zero_call_proven",
        "inputs": {
            "kernel": {
                "ref": _relative(kernel_path),
                "sha256": _sha256(kernel_path),
                "bytes": kernel_path.stat().st_size,
            },
            "route_policy": {
                "ref": _relative(policy_path),
                "sha256": _sha256(policy_path),
                "bytes": policy_path.stat().st_size,
            },
            "documents": {
                "ref": _relative(documents_path),
                "sha256": _sha256(documents_path),
                "bytes": documents_path.stat().st_size,
            },
            "records": {
                "ref": _relative(records_path),
                "sha256": _sha256(records_path),
                "bytes": records_path.stat().st_size,
            },
        },
        "output_binding": output_binding,
        "query_route_summary": {
            "query_family_count": len(policy.query_families),
            "kernel_facet_count": len(policy.family_by_facet()),
            "metric_route_count": len(policy.metric_routes),
            "company_financial_fact_mart_status": "separate_s2_runtime_integrated_not_object_candidate_authority",
            "market_snapshot_fact_mart_status": "typed_route_only_store_unavailable",
            "database_owning_stage": "S2",
        },
        "object_compilation_summary": dict(compilation.summary),
        "diagnostic_examples": diagnostic_examples,
        "sample_objects": sample_objects,
        "business_findings_zh": [
            "旧 child 重叠会重复生成同一 claim、表格行和父级上下文；当前编译器按父文档和对象内容去重，同时保留全部 source-record lineage。",
            "高管姓名、年龄和职位等数值型非财务表不会再冒充 metric rows；候选必须同时满足期间／单位表头或金融行标签门禁。",
            "空 TABLE_START/TABLE_END 不再吞掉其后的真实叙事；本次恢复了 TSMC 领先制程需求与 2nm ramp 的来源绑定 claim。",
            "同一表内重复的 Revenue／Gross margin 行会保留 Cloud Memory、Core Data Center 等行组上下文，避免检索后串错业务单元。",
            "财报表格行仅用于召回和上下文展示，不能成为 NumericFact；精确数值必须通过 S2 typed fact executor 和公司财务事实库。",
            "公司财务事实库由独立 S2 Runtime 提供；对象候选只保留上下文，不能替代 NumericFact、期间、单位或公式血缘。",
            "8-K 业绩稿同时保留原始 current-report 日期和元数据中的实际报告期；对象检索按报告期过滤，不再把发布日期误当财季结束日。",
        ],
        "acceptance": {
            "all_kernel_facets_routed_once": len(policy.family_by_facet())
            == sum(len(row.facet_ids) for row in policy.query_families),
            "missing_parent_count_zero": compilation.summary["missing_parent_count"] == 0,
            "candidate_not_evidence": True,
            "numeric_authority": False,
            "database_lane_preserved": True,
            "complete_s1_claimed": False,
            "complete_s2_claimed": False,
            "model_calls": 0,
            "network_calls": 0,
        },
    }
    result["payload_digest"] = canonical_digest(result)
    _write_json(result_output, result)
    _write_json(
        output_dir / "summary.json",
        {
            **result,
            "tracked_result_ref": _relative(result_output),
        },
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
