from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


DATA_QUALITY_RELEASE_GATE_ROW_SCHEMA_VERSION = "finsight_data_quality_release_gate_row_v0_1"
DATA_QUALITY_RELEASE_GATE_SUMMARY_SCHEMA_VERSION = "finsight_data_quality_release_gate_summary_v0_1"


SUMMARY_PATHS: dict[str, str] = {
    "rd1_raw_source_provenance": "data/manifests/raw_source_provenance_summary_v0_1.json",
    "rd2_parser_quality": "data/manifests/parser_quality_summary_v0_1.json",
    "rd3_gold_fact_signal_mart": "data/manifests/gold_fact_signal_mart_summary_v0_1.json",
    "rd4_research_graph_store": "data/manifests/research_graph_summary_v0_1.json",
    "rd5_retrieval_index_registry": "data/manifests/retrieval_index_registry_summary_v0_1.json",
    "rd6_agent_runtime_consumption": "data/manifests/agent_runtime_consumption_contract_summary_v0_1.json",
}


def build_data_quality_release_eval_gate(
    repo_root: str | Path,
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    generated_at = generated_at or _utc_now()
    summaries: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []

    for group, relative_path in SUMMARY_PATHS.items():
        path = root / relative_path
        if not path.exists():
            rows.append(
                _gate_row(
                    generated_at=generated_at,
                    gate_group=group,
                    gate_name="summary_artifact_exists",
                    status="fail",
                    severity="hard",
                    observed_value="missing",
                    threshold=relative_path,
                    message=f"Missing required RD summary: {relative_path}",
                    evidence_refs=[relative_path],
                )
            )
            continue
        summary = _read_json(path)
        summaries[group] = summary
        rows.append(
            _gate_row(
                generated_at=generated_at,
                gate_group=group,
                gate_name="summary_artifact_exists",
                status="pass",
                severity="hard",
                observed_value="present",
                threshold=relative_path,
                message="Required RD summary exists.",
                evidence_refs=[relative_path],
            )
        )
        rows.append(_summary_freshness_gate(root, group, path, summary, generated_at=generated_at))

    if "rd1_raw_source_provenance" in summaries:
        rows.extend(_rd1_gates(summaries["rd1_raw_source_provenance"], generated_at=generated_at))
    if "rd2_parser_quality" in summaries:
        rows.extend(_rd2_gates(summaries["rd2_parser_quality"], generated_at=generated_at))
    if "rd3_gold_fact_signal_mart" in summaries:
        rows.extend(_rd3_gates(summaries["rd3_gold_fact_signal_mart"], generated_at=generated_at))
    if "rd4_research_graph_store" in summaries:
        rows.extend(_rd4_gates(summaries["rd4_research_graph_store"], generated_at=generated_at))
    if "rd5_retrieval_index_registry" in summaries:
        rows.extend(_rd5_gates(summaries["rd5_retrieval_index_registry"], generated_at=generated_at))
    if "rd6_agent_runtime_consumption" in summaries:
        rows.extend(_rd6_gates(summaries["rd6_agent_runtime_consumption"], generated_at=generated_at))
    if "rd3_gold_fact_signal_mart" in summaries and "rd6_agent_runtime_consumption" in summaries:
        rows.extend(
            _rd3_rd6_cross_gates(
                summaries["rd3_gold_fact_signal_mart"],
                summaries["rd6_agent_runtime_consumption"],
                generated_at=generated_at,
            )
        )

    summary = build_data_quality_release_eval_summary(gate_rows=rows, generated_at=generated_at)
    summary["upstream_summary_statuses"] = {
        group: str(summary_obj.get("status") or "")
        for group, summary_obj in summaries.items()
    }
    summary["policy"] = (
        "RD7 is a release-eval gate for the data base. Hard failures block runtime promotion; warnings remain visible "
        "as replay/cache/parser-depth debt and must not be hidden by downstream agent prompts."
    )
    return {"gate_rows": rows, "summary": summary}


def build_data_quality_release_eval_summary(
    *,
    gate_rows: Sequence[Mapping[str, Any]],
    generated_at: str | None = None,
) -> dict[str, Any]:
    generated_at = generated_at or _utc_now()
    status_counts = Counter(str(row.get("status") or "") for row in gate_rows)
    severity_counts = Counter(str(row.get("severity") or "") for row in gate_rows)
    group_status_counts: dict[str, dict[str, int]] = {}
    for group, rows in _group_by(gate_rows, "gate_group").items():
        group_status_counts[group] = dict(Counter(str(row.get("status") or "") for row in rows))
    fail_count = status_counts.get("fail", 0)
    warn_count = status_counts.get("warn", 0)
    status = "action_required" if fail_count else ("pass_with_warnings" if warn_count else "pass")
    release_decision = "block_release" if fail_count else ("release_allowed_with_recorded_warnings" if warn_count else "release_allowed")
    return {
        "schema_version": DATA_QUALITY_RELEASE_GATE_SUMMARY_SCHEMA_VERSION,
        "generated_at": generated_at,
        "status": status,
        "release_decision": release_decision,
        "gate_count": len(gate_rows),
        "pass_count": status_counts.get("pass", 0),
        "warn_count": warn_count,
        "fail_count": fail_count,
        "status_counts": dict(status_counts),
        "severity_counts": dict(severity_counts),
        "group_status_counts": group_status_counts,
        "fail_samples": [_compact_gate(row) for row in gate_rows if row.get("status") == "fail"][:30],
        "warn_samples": [_compact_gate(row) for row in gate_rows if row.get("status") == "warn"][:30],
    }


def write_data_quality_release_eval_sqlite(path: str | Path, *, gate_rows: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    conn = sqlite3.connect(target)
    try:
        conn.execute(
            """
            CREATE TABLE data_quality_release_gate (
                gate_id TEXT PRIMARY KEY,
                schema_version TEXT,
                generated_at TEXT,
                gate_group TEXT,
                gate_name TEXT,
                status TEXT,
                severity TEXT,
                observed_value TEXT,
                threshold TEXT,
                message TEXT,
                evidence_refs_json TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO data_quality_release_gate (
                gate_id, schema_version, generated_at, gate_group, gate_name, status, severity,
                observed_value, threshold, message, evidence_refs_json
            ) VALUES (
                :gate_id, :schema_version, :generated_at, :gate_group, :gate_name, :status, :severity,
                :observed_value, :threshold, :message, :evidence_refs_json
            )
            """,
            [dict(row) for row in gate_rows],
        )
        conn.commit()
        row_count = int(conn.execute("SELECT COUNT(*) FROM data_quality_release_gate").fetchone()[0])
    finally:
        conn.close()
    return {"gate_row_count": row_count}


def render_data_quality_release_eval_report(summary: Mapping[str, Any], *, output_paths: Mapping[str, str]) -> str:
    lines = [
        "# RD7 Data Quality / Release Eval Gate",
        "",
        f"- Generated at: `{summary.get('generated_at', '')}`",
        f"- Status: `{summary.get('status', '')}`",
        f"- Release decision: `{summary.get('release_decision', '')}`",
        f"- Gate rows: `{summary.get('gate_count', 0)}`",
        f"- Pass / Warn / Fail: `{summary.get('pass_count', 0)}` / `{summary.get('warn_count', 0)}` / `{summary.get('fail_count', 0)}`",
        "",
        "## Outputs",
        "",
    ]
    for key, path in output_paths.items():
        lines.append(f"- `{key}`: `{path}`")
    lines.extend(
        [
            "",
            "## Gate Status By Group",
            "",
            _markdown_group_status_table(summary.get("group_status_counts") or {}),
            "",
            "## Warnings",
            "",
            _markdown_samples(summary.get("warn_samples") or []),
            "",
            "## Failures",
            "",
            _markdown_samples(summary.get("fail_samples") or []),
            "",
            "## Boundary",
            "",
            "- RD7 不新增事实、不放松 authority gate，只判断 RD1-RD6 数据底座是否可作为 agent runtime 输入。",
            "- `warn` 项允许进入下一阶段，但必须作为 replay/cache/parser-depth debt 暴露给 Research Lead / eval registry。",
            "- `fail` 项阻断 release：尤其是 exact-authority unresolved、缺 artifact、SQLite parity、unsupported graph edge、planning/gap row 被选入 evidence。",
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


def _rd1_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _status_gate("rd1_raw_source_provenance", summary, accepted={"pass"}, generated_at=generated_at),
        _zero_gate("rd1_raw_source_provenance", "exact_authority_unresolved_count", summary, severity="hard", generated_at=generated_at),
        _zero_gate("rd1_raw_source_provenance", "unresolved_lineage_count", summary, severity="hard", generated_at=generated_at),
        _minimum_gate(
            "rd1_raw_source_provenance",
            "companyfacts_external_key_document_count",
            summary,
            minimum=500,
            severity="hard",
            generated_at=generated_at,
            missing_ok=False,
        ),
        _positive_warning_gate(
            "rd1_raw_source_provenance",
            "url_only_context_lineage_count",
            summary,
            message="URL-only rows are traceable but not locally replayable until cached.",
            generated_at=generated_at,
        ),
    ]


def _rd2_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _status_gate("rd2_parser_quality", summary, accepted={"pass", "pass_with_recorded_rejections"}, generated_at=generated_at),
        _zero_gate("rd2_parser_quality", "missing_declared_output_count", summary, severity="hard", generated_at=generated_at),
        _zero_gate("rd2_parser_quality", "missing_artifact_count", summary, severity="hard", generated_at=generated_at),
        _minimum_gate("rd2_parser_quality", "parser_run_count", summary, minimum=1, severity="hard", generated_at=generated_at),
        _counter_warning_gate(
            "rd2_parser_quality",
            "parser_status_counts",
            "unknown",
            summary,
            message="Parser run status has unknown rows; keep as parser-ledger quality debt.",
            generated_at=generated_at,
        ),
    ]


def _rd3_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    rows = [
        _status_gate("rd3_gold_fact_signal_mart", summary, accepted={"pass"}, generated_at=generated_at),
        _zero_gate("rd3_gold_fact_signal_mart", "missing_source_rowset_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate(
            "rd3_gold_fact_signal_mart",
            "sqlite_row_count",
            "row_count",
            summary,
            severity="hard",
            generated_at=generated_at,
        ),
    ]
    by_authority = summary.get("by_authority_mode") if isinstance(summary.get("by_authority_mode"), Mapping) else {}
    row_count = _int(summary.get("row_count"))
    authority_total = sum(_int(value) for value in by_authority.values())
    rows.append(
        _gate_row(
            generated_at=generated_at,
            gate_group="rd3_gold_fact_signal_mart",
            gate_name="authority_mode_count_parity",
            status="pass" if authority_total == row_count else "fail",
            severity="hard",
            observed_value=str(authority_total),
            threshold=str(row_count),
            message="Authority-mode counts must sum to Gold Mart row_count.",
            evidence_refs=["data/manifests/gold_fact_signal_mart_summary_v0_1.json"],
        )
    )
    return rows


def _rd4_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _status_gate("rd4_research_graph_store", summary, accepted={"pass"}, generated_at=generated_at),
        _zero_gate("rd4_research_graph_store", "dangling_edge_count", summary, severity="hard", generated_at=generated_at),
        _zero_gate("rd4_research_graph_store", "unsupported_edge_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd4_research_graph_store", "sqlite_node_count", "node_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd4_research_graph_store", "sqlite_edge_count", "edge_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd4_research_graph_store", "sqlite_support_count", "evidence_support_row_count", summary, severity="hard", generated_at=generated_at),
        _counter_warning_gate(
            "rd4_research_graph_store",
            "support_status_counts",
            "modelled_relationship_without_direct_evidence_ref",
            summary,
            message="Modelled relationship edges exist without direct evidence ref; keep bounded and auditable.",
            generated_at=generated_at,
        ),
    ]


def _rd5_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _status_gate("rd5_retrieval_index_registry", summary, accepted={"pass"}, generated_at=generated_at),
        _zero_gate("rd5_retrieval_index_registry", "missing_source_artifact_count", summary, severity="hard", generated_at=generated_at),
        _zero_gate("rd5_retrieval_index_registry", "missing_record_file_snapshot_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd5_retrieval_index_registry", "sqlite_snapshot_count", "index_snapshot_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd5_retrieval_index_registry", "sqlite_lineage_count", "source_lineage_count", summary, severity="hard", generated_at=generated_at),
        _counter_warning_gate(
            "rd5_retrieval_index_registry",
            "record_snapshot_trace_status_counts",
            "record_snapshot_without_verified_raw_trace",
            summary,
            message="Index records contain a source artifact but not a verified local raw trace.",
            generated_at=generated_at,
        ),
        _counter_warning_gate(
            "rd5_retrieval_index_registry",
            "parser_artifact_link_status_counts",
            "no_parser_artifact_match",
            summary,
            message="Some index lineage rows do not map to a parser artifact; allowed for Milvus summary/legacy raw-trace rows only.",
            generated_at=generated_at,
        ),
    ]


def _rd6_gates(summary: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _status_gate("rd6_agent_runtime_consumption", summary, accepted={"pass"}, generated_at=generated_at),
        _minimum_gate("rd6_agent_runtime_consumption", "company_brief_count", summary, minimum=603, severity="hard", generated_at=generated_at),
        _equality_gate(
            "rd6_agent_runtime_consumption",
            "role_evidence_pack_count",
            "expected_role_evidence_pack_count",
            summary,
            severity="hard",
            generated_at=generated_at,
        ),
        _zero_gate("rd6_agent_runtime_consumption", "invalid_selected_gap_row_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd6_agent_runtime_consumption", "sqlite_brief_count", "company_brief_count", summary, severity="hard", generated_at=generated_at),
        _equality_gate("rd6_agent_runtime_consumption", "sqlite_pack_count", "role_evidence_pack_count", summary, severity="hard", generated_at=generated_at),
    ]


def _rd3_rd6_cross_gates(rd3: Mapping[str, Any], rd6: Mapping[str, Any], *, generated_at: str) -> list[dict[str, Any]]:
    return [
        _gate_row(
            generated_at=generated_at,
            gate_group="cross_authority_consumption",
            gate_name="planning_gap_ref_parity",
            status="pass" if _int(rd3.get("planning_or_gap_only_count")) == _int(rd6.get("gap_ref_count")) else "fail",
            severity="hard",
            observed_value=str(rd6.get("gap_ref_count", "")),
            threshold=str(rd3.get("planning_or_gap_only_count", "")),
            message="RD6 gap refs should mirror RD3 planning_or_gap_only rows without selecting them as evidence.",
            evidence_refs=[
                "data/manifests/gold_fact_signal_mart_summary_v0_1.json",
                "data/manifests/agent_runtime_consumption_contract_summary_v0_1.json",
            ],
        )
    ]


def _summary_freshness_gate(
    root: Path,
    gate_group: str,
    summary_path: Path,
    summary: Mapping[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    output_paths = summary.get("outputs") if isinstance(summary.get("outputs"), Mapping) else {}
    summary_mtime = summary_path.stat().st_mtime
    newer: list[str] = []
    for value in output_paths.values():
        path = Path(str(value))
        if not path.is_absolute():
            path = root / path
        if not path.exists() or path.resolve() == summary_path.resolve():
            continue
        if path.stat().st_mtime > summary_mtime + 60:
            newer.append(str(path))
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name="summary_not_stale_vs_outputs",
        status="fail" if newer else "pass",
        severity="hard",
        observed_value=str(len(newer)),
        threshold="0 newer output artifacts",
        message="Summary must not be older than its declared outputs by more than 60 seconds.",
        evidence_refs=[str(summary_path), *newer[:10]],
    )


def _status_gate(
    gate_group: str,
    summary: Mapping[str, Any],
    *,
    accepted: set[str],
    generated_at: str,
) -> dict[str, Any]:
    status = str(summary.get("status") or "")
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name="upstream_summary_status",
        status="pass" if status in accepted else "fail",
        severity="hard",
        observed_value=status,
        threshold="|".join(sorted(accepted)),
        message="Upstream RD summary status must be accepted for release evaluation.",
        evidence_refs=[],
    )


def _zero_gate(
    gate_group: str,
    key: str,
    summary: Mapping[str, Any],
    *,
    severity: str,
    generated_at: str,
) -> dict[str, Any]:
    value = _int(summary.get(key))
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name=key,
        status="pass" if value == 0 else "fail",
        severity=severity,
        observed_value=str(value),
        threshold="0",
        message=f"{key} must be zero.",
        evidence_refs=[],
    )


def _minimum_gate(
    gate_group: str,
    key: str,
    summary: Mapping[str, Any],
    *,
    minimum: int,
    severity: str,
    generated_at: str,
    missing_ok: bool = False,
) -> dict[str, Any]:
    exists = key in summary
    value = _int(summary.get(key))
    passed = (missing_ok and not exists) or value >= minimum
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name=key,
        status="pass" if passed else "fail",
        severity=severity,
        observed_value="missing" if not exists else str(value),
        threshold=f">={minimum}",
        message=f"{key} must be at least {minimum}.",
        evidence_refs=[],
    )


def _equality_gate(
    gate_group: str,
    observed_key: str,
    expected_key: str,
    summary: Mapping[str, Any],
    *,
    severity: str,
    generated_at: str,
) -> dict[str, Any]:
    observed = _int(summary.get(observed_key))
    expected = _int(summary.get(expected_key))
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name=f"{observed_key}_equals_{expected_key}",
        status="pass" if observed == expected else "fail",
        severity=severity,
        observed_value=str(observed),
        threshold=str(expected),
        message=f"{observed_key} must equal {expected_key}.",
        evidence_refs=[],
    )


def _positive_warning_gate(
    gate_group: str,
    key: str,
    summary: Mapping[str, Any],
    *,
    message: str,
    generated_at: str,
) -> dict[str, Any]:
    value = _int(summary.get(key))
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name=key,
        status="warn" if value > 0 else "pass",
        severity="soft",
        observed_value=str(value),
        threshold="0 preferred",
        message=message,
        evidence_refs=[],
    )


def _counter_warning_gate(
    gate_group: str,
    counter_key: str,
    item_key: str,
    summary: Mapping[str, Any],
    *,
    message: str,
    generated_at: str,
) -> dict[str, Any]:
    counter = summary.get(counter_key) if isinstance(summary.get(counter_key), Mapping) else {}
    value = _int(counter.get(item_key))
    return _gate_row(
        generated_at=generated_at,
        gate_group=gate_group,
        gate_name=f"{counter_key}.{item_key}",
        status="warn" if value > 0 else "pass",
        severity="soft",
        observed_value=str(value),
        threshold="0 preferred",
        message=message,
        evidence_refs=[],
    )


def _gate_row(
    *,
    generated_at: str,
    gate_group: str,
    gate_name: str,
    status: str,
    severity: str,
    observed_value: str,
    threshold: str,
    message: str,
    evidence_refs: Sequence[str],
) -> dict[str, Any]:
    gate_id = f"{gate_group}:{gate_name}"
    return {
        "schema_version": DATA_QUALITY_RELEASE_GATE_ROW_SCHEMA_VERSION,
        "generated_at": generated_at,
        "gate_id": gate_id,
        "gate_group": gate_group,
        "gate_name": gate_name,
        "status": status,
        "severity": severity,
        "observed_value": observed_value,
        "threshold": threshold,
        "message": message,
        "evidence_refs_json": json.dumps(list(evidence_refs), ensure_ascii=False),
    }


def _compact_gate(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "gate_group": row.get("gate_group"),
        "gate_name": row.get("gate_name"),
        "status": row.get("status"),
        "severity": row.get("severity"),
        "observed_value": row.get("observed_value"),
        "threshold": row.get("threshold"),
        "message": row.get("message"),
    }


def _markdown_group_status_table(group_status_counts: Mapping[str, Mapping[str, int]]) -> str:
    if not group_status_counts:
        return "_No gate groups._"
    lines = ["| Group | Pass | Warn | Fail |", "| --- | ---: | ---: | ---: |"]
    for group in sorted(group_status_counts):
        counts = group_status_counts[group]
        lines.append(f"| `{group}` | {counts.get('pass', 0)} | {counts.get('warn', 0)} | {counts.get('fail', 0)} |")
    return "\n".join(lines)


def _markdown_samples(samples: Sequence[Mapping[str, Any]]) -> str:
    if not samples:
        return "_None._"
    lines = ["| Gate | Status | Observed | Threshold | Message |", "| --- | --- | ---: | --- | --- |"]
    for sample in samples:
        gate = f"{sample.get('gate_group', '')}.{sample.get('gate_name', '')}"
        lines.append(
            f"| `{gate}` | `{sample.get('status', '')}` | `{sample.get('observed_value', '')}` | "
            f"`{sample.get('threshold', '')}` | {sample.get('message', '')} |"
        )
    return "\n".join(lines)


def _group_by(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get(key) or ""), []).append(row)
    return grouped


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
