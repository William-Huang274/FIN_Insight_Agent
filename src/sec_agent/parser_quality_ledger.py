from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PARSER_RUN_LEDGER_SCHEMA_VERSION = "finsight_parser_run_ledger_v0_1"
PARSER_OUTPUT_ARTIFACT_LEDGER_SCHEMA_VERSION = "finsight_parser_output_artifact_ledger_v0_1"
PARSER_REJECTION_TAXONOMY_SCHEMA_VERSION = "finsight_parser_rejection_taxonomy_v0_1"
PARSER_QUALITY_SUMMARY_SCHEMA_VERSION = "finsight_parser_quality_summary_v0_1"


SUMMARY_PATTERNS: tuple[str, ...] = (
    "data/manifests/*summary*.json",
    "data/staging/**/summaries/*summary*.json",
    "data/staging/**/structured_objects/*summary*.json",
    "data/processed_private/structured_objects/*summary*.json",
)

DISCOVERED_ARTIFACT_PATTERNS: tuple[str, ...] = (
    "data/processed_private/chunks/*.jsonl",
    "data/processed_private/evidence_objects/*.jsonl",
    "data/processed_private/structured_objects/*.jsonl",
    "data/staging/**/chunks/*.jsonl",
    "data/staging/**/evidence/*.jsonl",
    "data/staging/**/structured_objects/*.jsonl",
    "data/manifests/*_runtime_rows_v0_1.jsonl",
    "data/manifests/*_context_rows_v0_1.jsonl",
    "data/manifests/*_metric_slot_rows_v0_1.jsonl",
    "data/manifests/*_data_mart_rows_v0_1.jsonl",
    "data/manifests/*_rejections_v0_1.jsonl",
)

TEMPORARY_PATH_TOKENS: tuple[str, ...] = (
    "/_tmp_",
    "\\_tmp_",
    "/.tmp",
    "\\.tmp",
)

NON_PARSER_SUMMARY_TOKENS: tuple[str, ...] = (
    "coverage_gate",
    "coverage_matrix",
    "primary_disclosure_coverage",
    "source_route",
    "source_coverage",
    "source_layer_capability",
    "inventory",
    "download_config",
    "source_plan",
    "access_probe",
    "access_plan",
    "information_strength",
    "endpoint_gate",
    "mapping_endpoint",
    "full_availability",
    "materialization_summary",
    "locator_summary",
    "attempts_summary",
    "exhaustion",
    "diagnostic",
    "closeout",
    "docket",
    "queue",
    "readiness_gate",
    "acceptance_gate",
    "admission_ledger",
    "registry",
    "matrix",
    "lane_coverage",
    "staging_assets",
    "download",
    "smoke",
    "supplement",
    "universe_tiers",
    "parser_quality_summary",
)

PARSER_SIGNAL_KEYS: tuple[str, ...] = (
    "outputs",
    "output",
    "rejection_reason_counts",
    "claim_count",
    "table_count",
    "metric_count",
    "chunk_count",
    "chunks",
    "parser_backed_row_count",
    "context_row_count",
    "runtime_row_count",
    "exact_runtime_row_count",
)


def build_parser_quality_ledger(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
    max_line_count_bytes: int = 64 * 1024 * 1024,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    summary_paths = discover_parser_summary_paths(root)
    parser_runs: list[dict[str, Any]] = []
    artifact_rows_by_path: dict[str, dict[str, Any]] = {}
    artifact_links: dict[str, set[str]] = defaultdict(set)
    rejection_rows: list[dict[str, Any]] = []

    for summary_path in summary_paths:
        summary = _read_json(summary_path)
        if not summary:
            continue
        parser_run = _parser_run_row(
            root,
            summary_path,
            summary,
            generated_at=generated_at,
            max_line_count_bytes=max_line_count_bytes,
        )
        parser_runs.append(parser_run)
        parser_run_id = parser_run["parser_run_id"]
        for artifact in _artifacts_from_summary(
            root,
            summary_path,
            summary,
            parser_run_id,
            generated_at=generated_at,
            max_line_count_bytes=max_line_count_bytes,
        ):
            artifact_rows_by_path.setdefault(artifact["artifact_path"], artifact)
            artifact_links[artifact["artifact_path"]].add(parser_run_id)
        rejection_rows.extend(_rejection_rows_from_summary(root, summary_path, summary, parser_run_id, generated_at=generated_at))

    for artifact_path in discover_parser_artifact_paths(root):
        rel = _rel(artifact_path, root)
        artifact_rows_by_path.setdefault(
            rel,
            _artifact_row(
                root,
                artifact_path,
                parser_run_id="",
                artifact_kind=_classify_artifact_kind(artifact_path),
                generated_at=generated_at,
                declared_row_count=0,
                declared_row_count_source="not_declared",
                max_line_count_bytes=max_line_count_bytes,
            ),
        )

    artifact_rows = []
    for row in artifact_rows_by_path.values():
        path = row["artifact_path"]
        linked_run_ids = sorted(artifact_links.get(path) or row.get("linked_parser_run_ids") or [])
        row = {**row, "linked_parser_run_ids": linked_run_ids}
        if row["line_count_status"] == "not_evaluated":
            resolved = _resolve_path(root, row["artifact_path"])
            row = _artifact_row(
                root,
                resolved,
                parser_run_id=linked_run_ids[0] if linked_run_ids else "",
                artifact_kind=row["artifact_kind"],
                generated_at=generated_at,
                declared_row_count=int(row.get("declared_row_count") or 0),
                declared_row_count_source=str(row.get("declared_row_count_source") or ""),
                max_line_count_bytes=max_line_count_bytes,
                linked_parser_run_ids=linked_run_ids,
            )
        artifact_rows.append(row)

    summary = build_parser_quality_summary(
        parser_runs=parser_runs,
        artifact_rows=artifact_rows,
        rejection_rows=rejection_rows,
        generated_at=generated_at,
    )
    return {
        "parser_runs": sorted(parser_runs, key=lambda row: row["parser_run_id"]),
        "artifact_rows": sorted(artifact_rows, key=lambda row: row["artifact_path"]),
        "rejection_rows": sorted(rejection_rows, key=lambda row: (row["parser_run_id"], row["rejection_reason"])),
        "summary": summary,
    }


def discover_parser_summary_paths(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root).resolve()
    paths: set[Path] = set()
    for pattern in SUMMARY_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() and _is_parser_summary(root, path):
                paths.add(path.resolve())
    return sorted(paths)


def discover_parser_artifact_paths(repo_root: str | Path) -> list[Path]:
    root = Path(repo_root).resolve()
    paths: set[Path] = set()
    for pattern in DISCOVERED_ARTIFACT_PATTERNS:
        for path in root.glob(pattern):
            if path.is_file() and not _is_temporary_path(root, path):
                paths.add(path.resolve())
    return sorted(paths)


def build_parser_quality_summary(
    *,
    parser_runs: Sequence[Mapping[str, Any]],
    artifact_rows: Sequence[Mapping[str, Any]],
    rejection_rows: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    missing_artifacts = [row for row in artifact_rows if not row.get("artifact_exists")]
    missing_declared_outputs = [
        row
        for row in artifact_rows
        if row.get("declared_by_summary") and not row.get("artifact_exists")
    ]
    action_required_runs = [
        row
        for row in parser_runs
        if str(row.get("quality_status") or "").startswith("action_required")
    ]
    row_count_status_counts = Counter(str(row.get("line_count_status") or "") for row in artifact_rows)
    parser_status_counts = Counter(str(row.get("parser_status") or "") for row in parser_runs)
    owner_stage_counts = Counter(str(row.get("owner_stage") or "") for row in parser_runs)
    artifact_kind_counts = Counter(str(row.get("artifact_kind") or "") for row in artifact_rows)
    rejection_class_counts = Counter(str(row.get("rejection_class") or "") for row in rejection_rows)
    total_rejections = sum(int(row.get("rejection_count") or 0) for row in rejection_rows)
    status = "pass"
    if missing_declared_outputs or action_required_runs:
        status = "action_required"
    elif total_rejections:
        status = "pass_with_recorded_rejections"
    return {
        "schema_version": PARSER_QUALITY_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "parser_run_count": len(parser_runs),
        "parser_output_artifact_count": len(artifact_rows),
        "parser_rejection_taxonomy_row_count": len(rejection_rows),
        "total_declared_runtime_rows": sum(int(row.get("runtime_row_count") or 0) for row in parser_runs),
        "total_declared_context_rows": sum(int(row.get("context_row_count") or 0) for row in parser_runs),
        "total_declared_chunks": sum(int(row.get("chunk_count") or 0) for row in parser_runs),
        "total_declared_tables": sum(int(row.get("table_count") or 0) for row in parser_runs),
        "total_declared_metric_candidates": sum(int(row.get("metric_candidate_count") or 0) for row in parser_runs),
        "total_declared_claim_candidates": sum(int(row.get("claim_candidate_count") or 0) for row in parser_runs),
        "total_rejection_count": total_rejections,
        "missing_artifact_count": len(missing_artifacts),
        "missing_declared_output_count": len(missing_declared_outputs),
        "large_artifact_not_line_counted_count": row_count_status_counts.get("not_counted_large_artifact", 0),
        "parser_status_counts": dict(parser_status_counts),
        "owner_stage_counts": dict(owner_stage_counts),
        "artifact_kind_counts": dict(artifact_kind_counts),
        "artifact_line_count_status_counts": dict(row_count_status_counts),
        "rejection_class_counts": dict(rejection_class_counts),
        "action_required_parser_run_samples": [_compact_parser_run(row) for row in action_required_runs[:50]],
        "missing_declared_output_samples": [
            {"artifact_path": row.get("artifact_path", ""), "linked_parser_run_ids": row.get("linked_parser_run_ids", [])}
            for row in missing_declared_outputs[:50]
        ],
        "policy": (
            "RD2 records parser/chunk/table/metric/claim output quality. Large JSONL files are not line-counted "
            "when a summary already declares their row counts. Rejection rows are audit evidence and must not be "
            "treated as accepted facts."
        ),
    }


def render_parser_quality_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD2 Silver Parser / Chunk / Table / Metric Ledger",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Parser runs: `{summary.get('parser_run_count', 0)}`",
        f"- Parser output artifacts: `{summary.get('parser_output_artifact_count', 0)}`",
        f"- Rejection taxonomy rows: `{summary.get('parser_rejection_taxonomy_row_count', 0)}`",
        f"- Missing declared outputs: `{summary.get('missing_declared_output_count', 0)}`",
        f"- Large artifacts not line-counted: `{summary.get('large_artifact_not_line_counted_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Declared Parser Volume",
            "",
            f"- Chunks: `{summary.get('total_declared_chunks', 0)}`",
            f"- Tables: `{summary.get('total_declared_tables', 0)}`",
            f"- Metric candidates: `{summary.get('total_declared_metric_candidates', 0)}`",
            f"- Claim candidates: `{summary.get('total_declared_claim_candidates', 0)}`",
            f"- Runtime rows: `{summary.get('total_declared_runtime_rows', 0)}`",
            f"- Context rows: `{summary.get('total_declared_context_rows', 0)}`",
            f"- Rejections: `{summary.get('total_rejection_count', 0)}`",
            "",
            "## Owner Stages",
            "",
            _markdown_counter_table(summary.get("owner_stage_counts") or {}, "Stage", "Runs"),
            "",
            "## Artifact Kinds",
            "",
            _markdown_counter_table(summary.get("artifact_kind_counts") or {}, "Kind", "Artifacts"),
            "",
            "## Rejection Classes",
            "",
            _markdown_counter_table(summary.get("rejection_class_counts") or {}, "Class", "Rejected rows"),
            "",
            "## Boundary",
            "",
            "- RD2 不把 parser rejections、closeout、boundary rows 升级成 accepted evidence。",
            "- GB 级 rowset 以 summary 声明的 row count 为准，避免为 ledger 重扫大文件；需要逐行质量审计时应另起 targeted audit。",
            "- RD2 只处理 parser/chunk/table/metric/claim 质量，不替代 RD3 Gold Fact Mart 和 RD5 retrieval parity。",
            "",
        ]
    )
    return "\n".join(lines)


def write_jsonl(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def write_json(path: str | Path, payload: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parser_run_row(
    root: Path,
    summary_path: Path,
    summary: Mapping[str, Any],
    *,
    generated_at: str,
    max_line_count_bytes: int,
) -> dict[str, Any]:
    rel = _rel(summary_path, root)
    parser_name = _parser_name(summary_path)
    owner_stage = _owner_stage(summary_path, summary)
    output_artifacts = [
        artifact["artifact_path"]
        for artifact in _artifacts_from_summary(
            root,
            summary_path,
            summary,
            "",
            generated_at=generated_at,
            max_line_count_bytes=max_line_count_bytes,
        )
    ]
    rejection_count = _int(summary.get("rejection_count")) or _int(summary.get("rejected_row_count"))
    quality_status = _quality_status(summary, output_artifacts, root)
    return {
        "schema_version": PARSER_RUN_LEDGER_SCHEMA_VERSION,
        "generated_at": generated_at,
        "parser_run_id": _stable_id("rd2_parser_run", rel, _summary_contract_fingerprint(summary)),
        "parser_name": parser_name,
        "owner_stage": owner_stage,
        "parser_status": str(summary.get("status") or "unknown"),
        "quality_status": quality_status,
        "summary_path": rel,
        "schema_hint": str(summary.get("schema_version") or ""),
        "input_artifacts": _input_artifacts(root, summary),
        "output_artifacts": output_artifacts,
        "row_count": _first_int(summary, "row_count", "input_fact_count", "input_verifier_row_count", "input_records", "evidence_count"),
        "runtime_row_count": _first_int(summary, "runtime_row_count", "exact_runtime_row_count"),
        "context_row_count": _first_int(summary, "context_row_count", "parser_backed_row_count"),
        "chunk_count": _first_int(summary, "chunks", "chunk_count"),
        "table_count": _first_int(summary, "table_count"),
        "metric_candidate_count": _first_int(summary, "metric_count", "metric_candidate_count"),
        "claim_candidate_count": _first_int(summary, "claim_count"),
        "rejection_count": rejection_count,
        "ticker_count": _first_int(summary, "runtime_ticker_count", "ticker_count", "company_count", "runtime_company_count"),
        "source_layer": _infer_source_layer(summary_path, summary),
        "authority_boundary": str(summary.get("claim_boundary") or summary.get("authority_boundary") or summary.get("boundary") or ""),
        "rejection_reason_count": len(summary.get("rejection_reason_counts") or {}),
    }


def _artifacts_from_summary(
    root: Path,
    summary_path: Path,
    summary: Mapping[str, Any],
    parser_run_id: str,
    *,
    generated_at: str,
    max_line_count_bytes: int,
) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    summary_rel = _rel(summary_path, root)
    artifacts.append(
        _artifact_row(
            root,
            summary_path,
            parser_run_id=parser_run_id,
            artifact_kind="summary_json",
            generated_at=generated_at,
            declared_row_count=0,
            declared_row_count_source="summary_file",
            declared_by_summary=False,
            max_line_count_bytes=0,
        )
    )
    output_items: list[tuple[str, str]] = []
    outputs = summary.get("outputs")
    if isinstance(outputs, Mapping):
        for key, value in outputs.items():
            if isinstance(value, (str, Path)) and str(value).strip():
                output_items.append((str(key), str(value)))
    for key in ("output", "input_evidence_path"):
        value = summary.get(key)
        if isinstance(value, (str, Path)) and str(value).strip():
            output_items.append((key, str(value)))
    seen: set[str] = {summary_rel}
    for output_key, output_value in output_items:
        output_path = _resolve_path(root, output_value)
        if not output_path:
            continue
        rel = _rel(output_path, root)
        if rel in seen:
            continue
        seen.add(rel)
        artifacts.append(
            _artifact_row(
                root,
                output_path,
                parser_run_id=parser_run_id,
                artifact_kind=_artifact_kind_from_output_key(output_key, output_path),
                generated_at=generated_at,
                declared_row_count=_declared_count_for_output(output_key, summary),
                declared_row_count_source=f"summary:{summary_rel}:{output_key}",
                declared_by_summary=True,
                max_line_count_bytes=max_line_count_bytes,
            )
        )
    return artifacts


def _artifact_row(
    root: Path,
    artifact_path: Path,
    *,
    parser_run_id: str,
    artifact_kind: str,
    generated_at: str,
    declared_row_count: int,
    declared_row_count_source: str,
    max_line_count_bytes: int,
    declared_by_summary: bool = False,
    linked_parser_run_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    rel = _rel(artifact_path, root)
    exists = artifact_path.exists()
    byte_count = artifact_path.stat().st_size if exists else 0
    line_count = 0
    line_count_status = "not_evaluated"
    if exists and artifact_path.suffix.lower() == ".jsonl":
        if byte_count <= max_line_count_bytes:
            line_count = _count_lines(artifact_path)
            line_count_status = "counted"
        elif declared_row_count:
            line_count_status = "not_counted_large_artifact_summary_declared"
        else:
            line_count_status = "not_counted_large_artifact"
    elif exists:
        line_count_status = "not_jsonl"
    else:
        line_count_status = "missing_artifact"
    row_count = declared_row_count or line_count
    return {
        "schema_version": PARSER_OUTPUT_ARTIFACT_LEDGER_SCHEMA_VERSION,
        "generated_at": generated_at,
        "artifact_id": _stable_id("rd2_parser_artifact", rel),
        "artifact_path": rel,
        "artifact_kind": artifact_kind,
        "artifact_exists": exists,
        "byte_count": byte_count,
        "line_count": line_count,
        "line_count_status": line_count_status,
        "declared_row_count": declared_row_count,
        "declared_row_count_source": declared_row_count_source,
        "effective_row_count": row_count,
        "declared_by_summary": declared_by_summary,
        "linked_parser_run_ids": list(linked_parser_run_ids or ([parser_run_id] if parser_run_id else [])),
        "source_layer": _infer_source_layer(artifact_path, {}),
    }


def _rejection_rows_from_summary(
    root: Path,
    summary_path: Path,
    summary: Mapping[str, Any],
    parser_run_id: str,
    *,
    generated_at: str,
) -> list[dict[str, Any]]:
    reason_counts = summary.get("rejection_reason_counts") or {}
    if not isinstance(reason_counts, Mapping):
        reason_counts = {}
    rows: list[dict[str, Any]] = []
    for reason, count in sorted(reason_counts.items(), key=lambda item: str(item[0])):
        reason_text = str(reason or "unclassified_rejection")
        count_value = _int(count)
        rows.append(
            {
                "schema_version": PARSER_REJECTION_TAXONOMY_SCHEMA_VERSION,
                "generated_at": generated_at,
                "rejection_taxonomy_id": _stable_id("rd2_rejection", _rel(summary_path, root), reason_text),
                "parser_run_id": parser_run_id,
                "summary_path": _rel(summary_path, root),
                "rejection_reason": reason_text,
                "rejection_class": _classify_rejection_reason(reason_text),
                "rejection_count": count_value,
                "source_layer": _infer_source_layer(summary_path, summary),
                "promotion_boundary": _promotion_boundary_for_rejection(reason_text),
            }
        )
    rejection_count = _int(summary.get("rejection_count")) or _int(summary.get("rejected_row_count"))
    if rejection_count and not rows:
        reason_text = "unclassified_rejection"
        rows.append(
            {
                "schema_version": PARSER_REJECTION_TAXONOMY_SCHEMA_VERSION,
                "generated_at": generated_at,
                "rejection_taxonomy_id": _stable_id("rd2_rejection", _rel(summary_path, root), reason_text),
                "parser_run_id": parser_run_id,
                "summary_path": _rel(summary_path, root),
                "rejection_reason": reason_text,
                "rejection_class": "unclassified",
                "rejection_count": rejection_count,
                "source_layer": _infer_source_layer(summary_path, summary),
                "promotion_boundary": "not_promotable_without_reason_specific_verifier",
            }
        )
    return rows


def _is_parser_summary(root: Path, path: Path) -> bool:
    if _is_temporary_path(root, path):
        return False
    name = path.name.lower()
    if any(token in name for token in NON_PARSER_SUMMARY_TOKENS):
        return False
    summary = _read_json(path)
    if not summary:
        return False
    if _is_source_attempt_or_locator_summary(summary):
        return False
    if any(key in summary for key in PARSER_SIGNAL_KEYS):
        return True
    return False


def _quality_status(summary: Mapping[str, Any], output_artifacts: Sequence[str], root: Path) -> str:
    parser_status = str(summary.get("status") or "").lower()
    missing_outputs = [
        path
        for path in output_artifacts
        if path.endswith(".jsonl") and not _resolve_path(root, path).exists()
    ]
    if missing_outputs:
        return "action_required_missing_declared_output"
    if parser_status and parser_status not in {"pass", "staging_only_pass", "completed", "unknown"}:
        return f"pass_with_recorded_source_or_boundary_status:{parser_status}"
    if _int(summary.get("rejection_count")) or _int(summary.get("rejected_row_count")) or summary.get("rejection_reason_counts"):
        return "pass_with_recorded_rejections"
    return "pass"


def _parser_name(path: Path) -> str:
    name = path.name
    for suffix in ("_summary_v0_1.json", "_summary_v0_2.json", "_structured_summary.json", "_summary.json", ".json"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def _owner_stage(path: Path, summary: Mapping[str, Any]) -> str:
    text = f"{path.as_posix()} {json.dumps(_compact_summary(summary), ensure_ascii=False)}".lower()
    if "chunk" in text and ("chunks" in summary or "chunk_build" in text):
        return "chunk_build"
    if "structured_objects" in text or "table_count" in summary or "metric_count" in summary or "claim_count" in summary:
        return "structured_object_extraction"
    if "financial_statement" in text or "statement_metric" in text:
        return "financial_statement_runtime_parser"
    if "product_kpi" in text or "product_operating" in text or "business_mix" in text:
        return "product_kpi_runtime_parser"
    if "industry_operating" in text:
        return "industry_operating_metric_parser"
    if "capital" in text or "ownership" in text:
        return "capital_market_context_parser"
    if "customer" in text or "deployment" in text:
        return "customer_deployment_context_parser"
    if "spec" in text or "catalog" in text or "product_surface" in text:
        return "product_surface_context_parser"
    if "market" in text:
        return "market_context_parser"
    if "context" in text:
        return "source_context_parser"
    return "manifest_parser_summary"


def _input_artifacts(root: Path, summary: Mapping[str, Any]) -> list[str]:
    inputs: list[str] = []
    for key, value in summary.items():
        if "input" not in str(key).lower() or not isinstance(value, (str, Path)):
            continue
        resolved = _resolve_path(root, str(value))
        if resolved:
            inputs.append(_rel(resolved, root))
    return _unique(inputs)


def _artifact_kind_from_output_key(output_key: str, path: Path) -> str:
    key = output_key.lower()
    if key in {"tables", "table"}:
        return "table_rows"
    if key in {"metrics", "metric"}:
        return "metric_candidates"
    if key in {"claims", "claim"}:
        return "claim_candidates"
    if key in {"rows", "runtime_rows"}:
        return "runtime_rows"
    if key == "rejections":
        return "rejection_rows"
    if key == "coverage_gate":
        return "coverage_gate_json"
    if key == "report":
        return "report_markdown"
    if key == "input_evidence_path":
        return "input_evidence_rows"
    if "chunk" in key or "chunks" in path.name.lower():
        return "chunk_rows"
    return _classify_artifact_kind(path)


def _classify_artifact_kind(path: Path) -> str:
    name = path.name.lower()
    parent = path.parent.as_posix().lower()
    if name.endswith(".json") and "summary" in name:
        return "summary_json"
    if "chunk" in name or "/chunks" in parent:
        return "chunk_rows"
    if "evidence" in name or "/evidence" in parent:
        return "input_evidence_rows"
    if "tables" in name:
        return "table_rows"
    if "metrics" in name:
        return "metric_candidates"
    if "claims" in name:
        return "claim_candidates"
    if "rejections" in name:
        return "rejection_rows"
    if "runtime_rows" in name:
        return "runtime_rows"
    if "context_rows" in name:
        return "context_rows"
    if "metric_slot_rows" in name:
        return "metric_slot_rows"
    if "data_mart_rows" in name:
        return "data_mart_rows"
    return "jsonl_rows"


def _declared_count_for_output(output_key: str, summary: Mapping[str, Any]) -> int:
    key = output_key.lower()
    if key == "tables":
        return _first_int(summary, "table_count")
    if key == "metrics":
        return _first_int(summary, "metric_count", "metric_candidate_count")
    if key == "claims":
        return _first_int(summary, "claim_count")
    if key == "rows":
        return _first_int(summary, "runtime_row_count", "exact_runtime_row_count", "context_row_count", "row_count")
    if key == "rejections":
        return _first_int(summary, "rejection_count", "rejected_row_count", "rejection_sample_count")
    if key == "output":
        return _first_int(summary, "chunks", "chunk_count", "row_count")
    if key == "input_evidence_path":
        return _first_int(summary, "evidence_count", "input_records")
    return 0


def _classify_rejection_reason(reason: str) -> str:
    text = reason.lower()
    if any(token in text for token in ("geographic", "region", "geography")):
        return "region_only_or_geography"
    if any(token in text for token in ("percentage", "percent", "change", "growth", "mix_only")):
        return "percentage_or_change_only"
    if any(token in text for token in ("sentence_relation", "relation_insufficient")):
        return "weak_sentence_relation"
    if any(token in text for token in ("conflict", "conflicting")):
        return "conflict_resolution"
    if any(token in text for token in ("period", "column", "binding", "missing_exact", "no_value", "unit", "ambiguous")):
        return "value_unit_period_binding"
    if any(token in text for token in ("business_segment", "segment")):
        return "business_segment_boundary"
    if any(token in text for token in ("cash_flow", "acquisition", "tax", "fx", "non_gaap", "currency")):
        return "financial_statement_not_product_kpi"
    if any(token in text for token in ("non_product", "not_product", "no_product", "product_or_segment_description")):
        return "not_product_kpi_exact"
    if any(token in text for token in ("parser", "structured", "schema")):
        return "parser_schema_gap"
    if "concept_not_in_canonical" in text:
        return "outside_canonical_scope"
    return "other"


def _promotion_boundary_for_rejection(reason: str) -> str:
    rejection_class = _classify_rejection_reason(reason)
    if rejection_class in {"region_only_or_geography", "percentage_or_change_only", "financial_statement_not_product_kpi"}:
        return "context_only_not_exact_fact"
    if rejection_class in {"value_unit_period_binding", "parser_schema_gap", "weak_sentence_relation"}:
        return "repairable_only_after_source_specific_parser_or_verifier"
    if rejection_class == "business_segment_boundary":
        return "may_promote_to_industry_operating_slot_not_product_kpi"
    return "not_promotable_without_reason_specific_verifier"


def _infer_source_layer(path: Path, summary: Mapping[str, Any]) -> str:
    explicit = str(summary.get("source_layer") or summary.get("source_layer_id") or "")
    if explicit:
        return explicit
    text = path.as_posix().lower()
    if "sec_" in text or "/sec" in text or "financial_statement" in text or "non_us" in text:
        return "L1"
    if "official" in text or "product" in text or "customer" in text or "trusted" in text:
        return "L2"
    if "market" in text or "developer" in text or "hiring" in text or "channel" in text or "app_" in text:
        return "L3"
    return "unknown"


def _summary_contract_fingerprint(summary: Mapping[str, Any]) -> str:
    compact = {
        key: summary.get(key)
        for key in (
            "schema_version",
            "generated_at",
            "status",
            "row_count",
            "runtime_row_count",
            "context_row_count",
            "table_count",
            "metric_count",
            "claim_count",
            "rejection_count",
        )
        if key in summary
    }
    return json.dumps(compact, ensure_ascii=False, sort_keys=True)


def _compact_summary(summary: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: summary.get(key)
        for key in (
            "status",
            "row_count",
            "runtime_row_count",
            "context_row_count",
            "table_count",
            "metric_count",
            "claim_count",
            "rejection_count",
        )
        if key in summary
    }


def _compact_parser_run(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "parser_run_id": row.get("parser_run_id", ""),
        "parser_name": row.get("parser_name", ""),
        "summary_path": row.get("summary_path", ""),
        "parser_status": row.get("parser_status", ""),
        "quality_status": row.get("quality_status", ""),
    }


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _count_lines(path: Path) -> int:
    count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            count += chunk.count(b"\n")
    return count


def _resolve_path(root: Path, value: str) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = root / path
    resolved = path.resolve()
    if resolved.exists():
        return resolved
    parts = list(path.parts)
    lowered = [part.lower() for part in parts]
    if "fin_insight_agent" in lowered:
        index = lowered.index("fin_insight_agent")
        suffix = Path(*parts[index + 1 :]) if index + 1 < len(parts) else Path()
        relocated = (root / suffix).resolve()
        if relocated.exists():
            return relocated
        return relocated
    return resolved


def _is_source_attempt_or_locator_summary(summary: Mapping[str, Any]) -> bool:
    if summary.get("attempt_count") and _first_int(summary, "context_row_count", "row_count", "runtime_row_count") == 0:
        return True
    outputs = summary.get("outputs")
    if isinstance(outputs, Mapping):
        output_keys = {str(key).lower() for key in outputs}
        if output_keys and output_keys <= {"attempts", "summary", "report"}:
            return True
    if summary.get("download_task_count") or summary.get("download_status_counts"):
        return True
    return False


def _is_temporary_path(root: Path, path: Path) -> bool:
    rel = f"/{_rel(path, root).lower()}"
    return any(token in rel for token in TEMPORARY_PATH_TOKENS)


def _first_int(row: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        value = _int(row.get(key))
        if value:
            return value
    return 0


def _int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _rel(path: Path | None, root: Path) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(part or "") for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _markdown_counter_table(counter: Mapping[str, Any], key_label: str, value_label: str) -> str:
    lines = [f"| {key_label} | {value_label} |", "| --- | ---: |"]
    for key, value in sorted(counter.items(), key=lambda item: str(item[0])):
        lines.append(f"| `{key}` | `{value}` |")
    return "\n".join(lines)
