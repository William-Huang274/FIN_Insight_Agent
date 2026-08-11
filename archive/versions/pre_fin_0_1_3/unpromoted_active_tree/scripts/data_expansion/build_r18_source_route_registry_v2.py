from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sec_agent.source_route_registry_v2 import (  # noqa: E402
    SIGNAL_AUTHORITY_MAPPER_SCHEMA_VERSION,
    SOURCE_ROUTE_REGISTRY_V2_SCHEMA_VERSION,
    map_signal_authority_from_admission_row,
    source_route_registry_payload,
)


DEFAULT_ADMISSION_LEDGER_PATH = Path("data/manifests/r18_data_source_admission_ledger_v0_1.jsonl")
DEFAULT_OUTPUT_REGISTRY_PATH = Path("data/manifests/r18_source_route_registry_v2.json")
DEFAULT_OUTPUT_MATRIX_PATH = Path("data/manifests/r18_signal_authority_coverage_matrix_v0_2.jsonl")
DEFAULT_OUTPUT_SUMMARY_PATH = Path("data/manifests/r18_source_route_registry_v2_summary.json")
DEFAULT_OUTPUT_REPORT_PATH = Path("docs/internal/vnext_20260610/r18_source_route_registry_v2.zh-CN.md")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_registry_and_signal_matrix(
    admission_rows: list[dict[str, Any]],
    *,
    generated_at: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    observed_source_ids_by_role: dict[str, set[str]] = defaultdict(set)
    matrix_rows: list[dict[str, Any]] = []
    for row in admission_rows:
        source_role = str(row.get("source_role") or "")
        source_id = str(row.get("source_id") or "")
        if source_role and source_id:
            observed_source_ids_by_role[source_role].add(source_id)
        authority = map_signal_authority_from_admission_row(row)
        matrix_row = {
            "schema_version": SIGNAL_AUTHORITY_MAPPER_SCHEMA_VERSION,
            "generated_at": generated_at,
            "ledger_id": row.get("ledger_id") or "",
            "ticker": row.get("ticker") or "",
            "company_name": row.get("company_name") or "",
            "primary_lane_id": row.get("primary_lane_id") or "",
            "support_surface": row.get("support_surface") or authority.get("support_surface") or "",
            "source_role": source_role,
            "source_id": source_id,
            "source_layer": row.get("source_layer") or "",
            "availability_status": row.get("availability_status") or "",
            "adapter_parser_status": row.get("adapter_parser_status") or "",
            "can_enter_evidence_bundle": bool(row.get("can_enter_evidence_bundle"))
            and bool(authority.get("can_enter_evidence_bundle")),
            "authority": authority,
            "claim_boundary": row.get("claim_boundary") or "",
            "sample_urls": row.get("sample_urls") or [],
            "sample_evidence_refs": row.get("sample_evidence_refs") or [],
            "next_action": row.get("next_action") or "",
        }
        matrix_rows.append(matrix_row)

    registry = source_route_registry_payload(observed_source_ids_by_role=observed_source_ids_by_role)
    registry["generated_at"] = generated_at

    summary = build_summary(admission_rows, matrix_rows, registry, generated_at=generated_at)
    return registry, matrix_rows, summary


def build_summary(
    admission_rows: list[dict[str, Any]],
    matrix_rows: list[dict[str, Any]],
    registry: dict[str, Any],
    *,
    generated_at: str,
) -> dict[str, Any]:
    registered_roles = {
        contract.get("source_role")
        for contract in registry.get("contracts", [])
        if isinstance(contract, dict) and contract.get("source_role")
    }
    evidence_rows = [row for row in matrix_rows if bool(row.get("can_enter_evidence_bundle"))]
    unregistered_rows = [
        row
        for row in matrix_rows
        if not bool((row.get("authority") or {}).get("registered_source_role"))
    ]
    evidence_missing_required = [
        row
        for row in evidence_rows
        if (row.get("authority") or {}).get("missing_required_fields")
    ]
    summary = {
        "schema_version": "finsight_r18_source_route_registry_v2_summary",
        "generated_at": generated_at,
        "status": "pass",
        "admission_row_count": len(admission_rows),
        "signal_matrix_row_count": len(matrix_rows),
        "registry_source_role_count": len(registered_roles),
        "observed_source_role_count": len({row.get("source_role") for row in admission_rows}),
        "observed_source_id_count": len({row.get("source_id") for row in admission_rows}),
        "evidence_bundle_allowed_count": len(evidence_rows),
        "planning_or_gap_only_count": len(matrix_rows) - len(evidence_rows),
        "by_authority_mode": dict(Counter((row.get("authority") or {}).get("authority_mode", "unregistered") for row in matrix_rows)),
        "by_signal_authority_type": dict(
            Counter((row.get("authority") or {}).get("signal_authority_type", "unregistered") for row in matrix_rows)
        ),
        "by_admission_decision": dict(
            Counter((row.get("authority") or {}).get("admission_decision", "unknown") for row in matrix_rows)
        ),
        "by_primary_lane": dict(Counter(str(row.get("primary_lane_id") or "") for row in admission_rows)),
        "by_support_surface": dict(Counter(str(row.get("support_surface") or "") for row in admission_rows)),
        "hard_gate": {
            "unregistered_source_role_count": len(unregistered_rows),
            "evidence_row_without_registry_count": len(
                [row for row in evidence_rows if row.get("source_role") not in registered_roles]
            ),
            "evidence_row_missing_required_fields_count": len(evidence_missing_required),
            "non_evidence_row_marked_allowed_count": len(
                [
                    row
                    for row in matrix_rows
                    if not _original_admission_allowed(row, admission_rows)
                    and bool(row.get("can_enter_evidence_bundle"))
                ]
            ),
        },
    }
    if any(value != 0 for value in summary["hard_gate"].values()):
        summary["status"] = "action_required"
    return summary


def _original_admission_allowed(matrix_row: dict[str, Any], admission_rows: list[dict[str, Any]]) -> bool:
    ledger_id = matrix_row.get("ledger_id")
    if not ledger_id:
        return False
    for row in admission_rows:
        if row.get("ledger_id") == ledger_id:
            return bool(row.get("can_enter_evidence_bundle"))
    return False


def render_report(summary: dict[str, Any], registry: dict[str, Any], matrix_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# R18 SourceRouteRegistry v2 / SignalAuthorityMapper v0.2",
        "",
        f"生成时间：{summary['generated_at']}",
        "",
        "## 摘要",
        "",
        f"- 状态：`{summary['status']}`",
        f"- registry source roles：`{summary['registry_source_role_count']}`",
        f"- signal matrix rows：`{summary['signal_matrix_row_count']}`",
        f"- evidence bundle allowed：`{summary['evidence_bundle_allowed_count']}`",
        f"- planning / gap only：`{summary['planning_or_gap_only_count']}`",
        "",
        "## Hard Gate",
        "",
    ]
    for key, value in summary["hard_gate"].items():
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## Authority Mode", ""])
    for key, value in sorted(summary["by_authority_mode"].items()):
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## Signal Authority Type", ""])
    for key, value in sorted(summary["by_signal_authority_type"].items()):
        lines.append(f"- `{key}`：`{value}`")
    lines.extend(["", "## Source Roles", ""])
    for contract in registry.get("contracts", []):
        if not isinstance(contract, dict):
            continue
        lines.append(
            f"- `{contract.get('source_role')}`：{contract.get('support_surface')} / "
            f"{contract.get('authority_mode')} / observed source ids "
            f"`{len(contract.get('observed_source_ids') or [])}`"
        )
    lines.extend(["", "## 代表性 planning / gap rows", ""])
    for row in [row for row in matrix_rows if not row.get("can_enter_evidence_bundle")][:20]:
        authority = row.get("authority") or {}
        lines.append(
            "- "
            f"`{row.get('ticker')}` / `{row.get('source_role')}` / `{row.get('source_id')}`："
            f"{authority.get('admission_decision')}；{row.get('adapter_parser_status')}；{row.get('next_action')}"
        )
    lines.extend(
        [
            "",
            "## 使用边界",
            "",
            "- 本 registry 是 source-role 合同，不是外部数据抓取结果。",
            "- SignalAuthorityMapper v0.2 只允许 Data Source Admission Ledger 已准入的 rows 进入 evidence bundle。",
            "- planning / gap rows 只能触发 targeted repair 或 gap ledger，不得被 ClaimCard / Memo 使用。",
        ]
    )
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build SourceRouteRegistry v2 and SignalAuthorityMapper coverage matrix.")
    parser.add_argument("--admission-ledger-path", type=Path, default=DEFAULT_ADMISSION_LEDGER_PATH)
    parser.add_argument("--output-registry-path", type=Path, default=DEFAULT_OUTPUT_REGISTRY_PATH)
    parser.add_argument("--output-matrix-path", type=Path, default=DEFAULT_OUTPUT_MATRIX_PATH)
    parser.add_argument("--output-summary-path", type=Path, default=DEFAULT_OUTPUT_SUMMARY_PATH)
    parser.add_argument("--output-report-path", type=Path, default=DEFAULT_OUTPUT_REPORT_PATH)
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    admission_rows = _read_jsonl(args.admission_ledger_path)
    registry, matrix_rows, summary = build_registry_and_signal_matrix(admission_rows, generated_at=generated_at)
    _write_json(args.output_registry_path, registry)
    _write_jsonl(args.output_matrix_path, matrix_rows)
    _write_json(args.output_summary_path, summary)
    args.output_report_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_report_path.write_text(render_report(summary, registry, matrix_rows), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": summary["status"],
                "registry_source_role_count": summary["registry_source_role_count"],
                "signal_matrix_row_count": summary["signal_matrix_row_count"],
                "evidence_bundle_allowed_count": summary["evidence_bundle_allowed_count"],
                "hard_gate": summary["hard_gate"],
                "output_registry": str(args.output_registry_path),
                "output_matrix": str(args.output_matrix_path),
                "output_summary": str(args.output_summary_path),
                "output_report": str(args.output_report_path),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if args.strict and summary["status"] != "pass":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
