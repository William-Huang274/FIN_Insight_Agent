from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping


CASE_ARTIFACTS = {
    "pre_memo_fact_selection": "pre_memo_fact_selection.json",
    "claim_cards": "claim_cards.json",
    "verified_judgment_plan": "verified_judgment_plan.json",
    "memo_logic_plan": "memo_logic_plan.json",
    "memo_answer": "memo_answer.json",
    "rendered_answer": "qwen/rendered_answer.md",
    "multi_agent_summary": "multi_agent_summary.json",
    "p30_root_cause_quality_audit": "p30_root_cause_quality_audit.json",
    "typed_gap_ledger": "typed_gap_ledger.json",
    "source_layer_capability_audit": "source_layer_capability_audit.json",
    "supervising_analyst_pack": "supervising_analyst_pack.json",
}

BLOCKING_ISSUES = {
    "memo_logic_plan_artifact_missing",
    "required_item_available_not_rendered",
    "memo_writer_deterministic_salvage_used",
    "product_evidence_available_not_rendered",
    "display_value_lineage_missing",
    "owned_parser_locator_gap_present",
    "source_route_scope_false_gap_present",
    "bounded_answer_salvage_surface",
    "p30_root_cause_rows_open",
}


def build_data_script_quality_summary(
    aggregate: Mapping[str, Any],
    *,
    artifact_root: str | Path | None = None,
) -> dict[str, Any]:
    """Audit saved full-chain artifacts for project-owned data/script defects.

    The audit is intentionally deterministic and offline. It does not call models,
    retrieval, web search, or parsers; it only checks whether the artifacts already
    produced by a run are complete enough to explain the final answer quality.
    """

    root = Path(artifact_root or aggregate.get("output_dir") or ".")
    cases = _case_rows(aggregate)
    case_audits = [_audit_case(case, root) for case in cases]
    issue_counts = Counter(issue for case in case_audits for issue in case.get("issues") or [])
    failed_case_ids = [
        str(case.get("case_id") or "")
        for case in case_audits
        if str(case.get("status") or "") == "fail" and str(case.get("case_id") or "")
    ]
    return {
        "schema_version": "sec_agent_data_script_quality_audit_v0.1",
        "diagnostic_only": False,
        "run_id": aggregate.get("run_id") or "",
        "artifact_root": str(root.resolve()) if root else "",
        "status": "fail" if failed_case_ids else "pass",
        "case_count": len(case_audits),
        "failed_case_ids": failed_case_ids,
        "issue_counts": dict(sorted(issue_counts.items())),
        "policy": (
            "Project-owned data/script defects must be repaired before paid broad full-chain regression. "
            "Gates may contain bad output, but they do not replace fixing the earliest faulty artifact."
        ),
        "cases": case_audits,
    }


def render_data_script_quality_markdown(audit: Mapping[str, Any]) -> str:
    lines = [
        f"# Data / Script Quality Audit: {audit.get('run_id') or ''}",
        "",
        "Deterministic audit generated from saved runtime artifacts. It does not call models, retrieval tools, or web repair.",
        "",
        f"- Status: `{audit.get('status') or ''}`",
        f"- Cases: `{audit.get('case_count') or 0}`",
        f"- Failed cases: `{', '.join(str(item) for item in audit.get('failed_case_ids') or []) or 'none'}`",
        "",
        "## Issue Counts",
        "",
    ]
    issue_counts = audit.get("issue_counts") if isinstance(audit.get("issue_counts"), Mapping) else {}
    if issue_counts:
        for issue, count in sorted(issue_counts.items()):
            lines.append(f"- `{issue}`: {count}")
    else:
        lines.append("- none")
    lines.extend(["", "## Cases", ""])
    for case in audit.get("cases") or []:
        if not isinstance(case, Mapping):
            continue
        lines.append(f"### {case.get('case_id') or ''}")
        lines.append(f"- Status: `{case.get('status') or ''}`")
        lines.append(f"- Issues: `{', '.join(str(item) for item in case.get('issues') or []) or 'none'}`")
        metrics = case.get("metrics") if isinstance(case.get("metrics"), Mapping) else {}
        lines.append(
            "- Metrics: "
            f"approved_facts=`{metrics.get('approved_fact_count') or 0}`, "
            f"supported_claims=`{metrics.get('supported_claim_count') or 0}`, "
            f"available_not_rendered=`{metrics.get('required_available_not_rendered_count') or 0}`, "
            f"rendered_chars=`{metrics.get('rendered_answer_chars') or 0}`"
        )
        root_causes = case.get("root_cause_candidates") or []
        if root_causes:
            lines.append(f"- Root-cause candidates: `{', '.join(str(item) for item in root_causes)}`")
        artifact_presence = case.get("artifact_presence") if isinstance(case.get("artifact_presence"), Mapping) else {}
        missing = [name for name, present in artifact_presence.items() if not present]
        if missing:
            lines.append(f"- Missing artifacts: `{', '.join(missing)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _case_rows(aggregate: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [dict(row) for row in aggregate.get("cases") or [] if isinstance(row, Mapping)]
    if rows:
        return rows
    output_quality = aggregate.get("output_quality_audit") if isinstance(aggregate.get("output_quality_audit"), Mapping) else {}
    return [dict(row) for row in output_quality.get("cases") or [] if isinstance(row, Mapping)]


def _audit_case(case: Mapping[str, Any], artifact_root: Path) -> dict[str, Any]:
    case_id = str(case.get("case_id") or "").strip()
    case_dir = artifact_root / case_id if case_id else artifact_root
    artifacts = _load_case_artifacts(case_dir)
    issues: list[str] = []
    root_causes: set[str] = set()
    if not artifacts["presence"].get("memo_logic_plan"):
        issues.append("memo_logic_plan_artifact_missing")
        embedded_plan_present = _embedded_memo_logic_plan_present(artifacts["json"].get("memo_answer"))
        summary_plan_present = _summary_memo_logic_plan_present(artifacts["json"].get("multi_agent_summary"))
        if embedded_plan_present or summary_plan_present:
            root_causes.add("memo_logic_plan_standalone_artifact_persistence")
        else:
            root_causes.add("memo_logic_plan_generation_or_state_loss")
    if _deterministic_salvage_used(artifacts["json"].get("memo_answer")):
        issues.append("memo_writer_deterministic_salvage_used")
        root_causes.add("writer_salvage_renderer_projection")
    rendered = str(artifacts["text"].get("rendered_answer") or "")
    if rendered.strip().lower().startswith("bounded answer only:"):
        issues.append("bounded_answer_salvage_surface")
        root_causes.add("writer_salvage_renderer_projection")

    p30 = artifacts["json"].get("p30_root_cause_quality_audit")
    required_available_not_rendered = _required_items_by_status(p30, "available_not_rendered")
    if required_available_not_rendered:
        issues.append("required_item_available_not_rendered")
        root_causes.add("memo_logic_plan_to_writer_projection")
    if _product_evidence_available_not_rendered(p30, required_available_not_rendered):
        issues.append("product_evidence_available_not_rendered")
        root_causes.add("product_intelligence_pack_to_memo_projection")

    display_violations = _display_value_lineage_violations(artifacts["json"].get("pre_memo_fact_selection"))
    if display_violations:
        issues.append("display_value_lineage_missing")
        root_causes.add("numeric_display_lineage")

    open_root_rows = _open_p30_root_cause_rows(p30)
    if open_root_rows:
        issues.append("p30_root_cause_rows_open")
        root_causes.update(_p30_root_cause_layers(open_root_rows))

    parser_gap_count = _owned_parser_locator_gap_count(artifacts)
    if parser_gap_count:
        issues.append("owned_parser_locator_gap_present")
        root_causes.add("parser_locator_adapter_root_cause")
    source_scope_gap_count = _source_route_scope_false_gap_count(artifacts)
    if source_scope_gap_count:
        issues.append("source_route_scope_false_gap_present")
        root_causes.add("source_route_scope_or_manifest_adapter")

    supported_claim_count = _supported_claim_count(artifacts["json"].get("claim_cards"), artifacts["json"].get("verified_judgment_plan"))
    approved_fact_count = _approved_fact_count(artifacts["json"].get("pre_memo_fact_selection"))
    issues = _unique(issues)
    blocking = [issue for issue in issues if issue in BLOCKING_ISSUES]
    return {
        "case_id": case_id,
        "status": "fail" if blocking else "pass",
        "issues": issues,
        "blocking_issues": blocking,
        "root_cause_candidates": sorted(root_causes),
        "artifact_dir": str(case_dir.resolve()),
        "artifact_presence": artifacts["presence"],
        "metrics": {
            "approved_fact_count": approved_fact_count,
            "supported_claim_count": supported_claim_count,
            "required_available_not_rendered_count": len(required_available_not_rendered),
            "display_value_lineage_violation_count": len(display_violations),
            "p30_open_root_cause_row_count": len(open_root_rows),
            "owned_parser_locator_gap_count": parser_gap_count,
            "source_route_scope_false_gap_count": source_scope_gap_count,
            "rendered_answer_chars": len(rendered),
            "memo_answer_embedded_memo_logic_plan_present": _embedded_memo_logic_plan_present(
                artifacts["json"].get("memo_answer")
            ),
            "summary_memo_logic_plan_present": _summary_memo_logic_plan_present(
                artifacts["json"].get("multi_agent_summary")
            ),
        },
        "required_available_not_rendered": required_available_not_rendered[:12],
        "display_value_lineage_violations": display_violations[:12],
    }


def _load_case_artifacts(case_dir: Path) -> dict[str, Any]:
    json_artifacts: dict[str, Any] = {}
    text_artifacts: dict[str, str] = {}
    presence: dict[str, bool] = {}
    for name, relative in CASE_ARTIFACTS.items():
        path = case_dir / relative
        presence[name] = path.exists()
        if not path.exists():
            continue
        if path.suffix.lower() == ".json":
            json_artifacts[name] = _read_json(path)
        else:
            text_artifacts[name] = path.read_text(encoding="utf-8", errors="replace")
    return {"json": json_artifacts, "text": text_artifacts, "presence": presence}


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _deterministic_salvage_used(memo_answer: Any) -> bool:
    memo = memo_answer if isinstance(memo_answer, Mapping) else {}
    diagnostics = memo.get("memo_writer_diagnostics") if isinstance(memo.get("memo_writer_diagnostics"), Mapping) else {}
    if bool(diagnostics.get("deterministic_salvage_used")):
        return True
    reason = str(diagnostics.get("salvage_reason") or "").lower()
    return "salvage" in reason or "deterministic_memo_gate_failed" in reason


def _embedded_memo_logic_plan_present(memo_answer: Any) -> bool:
    memo = memo_answer if isinstance(memo_answer, Mapping) else {}
    return isinstance(memo.get("memo_logic_plan"), Mapping) and bool(memo.get("memo_logic_plan"))


def _summary_memo_logic_plan_present(summary: Any) -> bool:
    payload = summary if isinstance(summary, Mapping) else {}
    return isinstance(payload.get("memo_logic_plan"), Mapping) and bool(payload.get("memo_logic_plan"))


def _required_items_by_status(p30: Any, status: str) -> list[dict[str, Any]]:
    audit = p30 if isinstance(p30, Mapping) else {}
    raw_matrix = audit.get("required_item_matrix")
    if isinstance(raw_matrix, list):
        rows = raw_matrix
    elif isinstance(raw_matrix, Mapping):
        rows = raw_matrix.get("items") or raw_matrix.get("required_items") or []
    else:
        rows = []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        row_status = str(row.get("status") or row.get("coverage_status") or "").strip()
        if row_status == status:
            out.append(dict(row))
    return out


def _product_evidence_available_not_rendered(p30: Any, available_not_rendered: list[dict[str, Any]]) -> bool:
    audit = p30 if isinstance(p30, Mapping) else {}
    frame = audit.get("product_reasoning_frame") if isinstance(audit.get("product_reasoning_frame"), Mapping) else {}
    if not frame:
        frame = (
            audit.get("product_reasoning_frame_summary")
            if isinstance(audit.get("product_reasoning_frame_summary"), Mapping)
            else {}
        )
    if not frame:
        layer_checks = audit.get("layer_checks") if isinstance(audit.get("layer_checks"), Mapping) else {}
        frame = layer_checks.get("product_reasoning_frame") if isinstance(layer_checks.get("product_reasoning_frame"), Mapping) else {}
    if not frame:
        return False
    text = json.dumps(available_not_rendered, ensure_ascii=False).lower()
    product_terms = ("product", "gpu", "server", "deployment", "customer", "supply", "capex", "architecture")
    return bool(available_not_rendered) and any(term in text for term in product_terms)


def _display_value_lineage_violations(fact_selection: Any) -> list[dict[str, Any]]:
    facts = fact_selection if isinstance(fact_selection, Mapping) else {}
    rows: list[Mapping[str, Any]] = []
    for key in ("approved_facts", "approved_derived_metrics", "facts"):
        rows.extend(row for row in facts.get(key) or [] if isinstance(row, Mapping))
    violations: list[dict[str, Any]] = []
    for row in rows:
        if not _row_has_numeric_value(row):
            continue
        status = str(row.get("display_lineage_status") or "").strip().lower()
        display_value = str(row.get("display_value") or "").strip()
        if display_value and status in {"", "pass", "ok"}:
            continue
        violations.append(
            {
                "fact_id": row.get("fact_id") or row.get("id") or row.get("evidence_ref") or "",
                "metric": row.get("metric") or row.get("label") or row.get("claim") or "",
                "display_value": display_value,
                "display_lineage_status": status,
            }
        )
    return violations


def _row_has_numeric_value(row: Mapping[str, Any]) -> bool:
    for key in ("value", "raw_value", "numeric_value", "amount", "metric_value"):
        if key not in row:
            continue
        value = row.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if isinstance(value, str) and re.search(r"\d", value):
            return True
    return False


def _owned_parser_locator_gap_count(artifacts: Mapping[str, Any]) -> int:
    rows = _owned_root_or_gap_rows(artifacts)
    count = 0
    for row in rows:
        if _row_has_complete_parser_diagnosis(row):
            continue
        if _row_status_closed(row):
            continue
        if _row_is_owned_parser_locator_gap(row):
            count += 1
    return count


def _row_is_owned_parser_locator_gap(row: Mapping[str, Any]) -> bool:
    """Return true only for explicit parser/locator/adapter gaps.

    P30 root-cause rows often contain generic repair text such as
    "or diagnose parser/source boundary". That text is a repair instruction,
    not proof that the earliest faulty artifact is a parser. Counting it as a
    parser gap hides the actual problem, such as MemoLogicPlan projection or
    writer execution. Explicit gap fields remain blocking until diagnosed.
    """

    external_terms = ("commercial", "subscription", "credential", "license", "paid")
    full_text = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).lower()
    if any(external in full_text for external in external_terms):
        return False

    explicit_fields = (
        "gap_type",
        "source_gap_type",
        "reason_code",
        "diagnostic_class",
        "cluster_id",
        "issue_type",
        "root_cause_layer",
        "earliest_faulty_artifact",
        "parser_failure_reason",
        "exact_fact_parser_failure_reason",
        "source_specific_parser_status",
        "exact_value_parser_status",
    )
    explicit_text = " ".join(str(row.get(key) or "") for key in explicit_fields).lower()
    explicit_terms = (
        "parser_gap",
        "locator_gap",
        "adapter_gap",
        "parser_required",
        "parser_missing",
        "source_specific_table_relation_parser_gap",
        "parser",
        "locator",
        "adapter",
    )
    if any(term in explicit_text for term in explicit_terms):
        return True

    symptom_text = str(row.get("symptom") or "").lower()
    if any(term in symptom_text for term in ("parser_gap", "locator_gap", "adapter_gap")):
        return True

    return False


def _source_route_scope_false_gap_count(artifacts: Mapping[str, Any]) -> int:
    rows = _owned_root_or_gap_rows(artifacts)
    diagnosed_tickers = _source_route_gap_diagnosed_tickers(artifacts)
    covered_tickers = _source_route_gap_covered_tickers(artifacts)
    focus_tickers = _p30_focus_tickers(artifacts)
    markers = (
        "not_in_manifest_for_mcp_route_scope",
        "not_in_manifest",
        "mcp route scope",
        "route_scope",
        "local_or_sec_route_scope_missing",
    )
    count = 0
    for row in rows:
        text = json.dumps(row, ensure_ascii=False, sort_keys=True, default=str).lower()
        ticker = str(row.get("ticker") or "").upper().strip()
        if ticker and ticker in diagnosed_tickers and any(marker in text for marker in markers):
            continue
        if ticker and ticker in covered_tickers and any(marker in text for marker in markers):
            continue
        if ticker and focus_tickers and ticker not in focus_tickers and any(marker in text for marker in markers):
            continue
        if any(marker in text for marker in markers):
            count += 1
    return count


def _owned_root_or_gap_rows(artifacts: Mapping[str, Any]) -> list[dict[str, Any]]:
    json_payload = artifacts.get("json") if isinstance(artifacts.get("json"), Mapping) else {}
    rows: list[dict[str, Any]] = []
    p30 = json_payload.get("p30_root_cause_quality_audit")
    if isinstance(p30, Mapping):
        rows.extend(dict(row) for row in p30.get("root_cause_rows") or [] if isinstance(row, Mapping))
    typed_gap = json_payload.get("typed_gap_ledger")
    if isinstance(typed_gap, Mapping):
        rows.extend(dict(row) for row in typed_gap.get("gaps") or [] if isinstance(row, Mapping))
    source_audit = json_payload.get("source_layer_capability_audit")
    if isinstance(source_audit, Mapping):
        for key in ("gaps", "source_gaps", "repair_rows", "root_cause_rows"):
            rows.extend(dict(row) for row in source_audit.get(key) or [] if isinstance(row, Mapping))
    return rows


def _open_p30_root_cause_rows(p30: Any) -> list[dict[str, Any]]:
    audit = p30 if isinstance(p30, Mapping) else {}
    rows = [dict(row) for row in audit.get("root_cause_rows") or [] if isinstance(row, Mapping)]
    return [row for row in rows if not _row_status_closed(row)]


def _p30_root_cause_layers(rows: list[Mapping[str, Any]]) -> set[str]:
    layers: set[str] = set()
    for row in rows:
        layer = str(row.get("root_cause_layer") or "").strip()
        if layer:
            layers.add(layer)
            continue
        test = str(row.get("verification_test") or "").strip()
        if test:
            layers.add(test)
    return layers


def _source_route_gap_diagnosed_tickers(artifacts: Mapping[str, Any]) -> set[str]:
    json_payload = artifacts.get("json") if isinstance(artifacts.get("json"), Mapping) else {}
    diagnosed: set[str] = set()
    for payload in json_payload.values():
        for row in _walk_mappings(payload):
            ticker = str(row.get("ticker") or "").upper().strip()
            tickers = {ticker} if ticker else {str(item).upper().strip() for item in row.get("ticker_scope") or []}
            tickers = {item for item in tickers if item}
            if not tickers:
                continue
            if _row_has_complete_parser_diagnosis(row):
                diagnosed.update(tickers)
    return diagnosed


def _source_route_gap_covered_tickers(artifacts: Mapping[str, Any]) -> set[str]:
    json_payload = artifacts.get("json") if isinstance(artifacts.get("json"), Mapping) else {}
    covered: set[str] = set()
    p30 = json_payload.get("p30_root_cause_quality_audit")
    if isinstance(p30, Mapping):
        for row in p30.get("focus_ticker_coverage_matrix") or []:
            if not isinstance(row, Mapping):
                continue
            ticker = str(row.get("ticker") or "").upper().strip()
            if not ticker:
                continue
            if int(row.get("approved_fact_count") or 0) > 0 or int(row.get("supported_claim_count") or 0) > 0:
                covered.add(ticker)
    for payload_name in ("pre_memo_fact_selection", "claim_cards", "verified_judgment_plan"):
        payload = json_payload.get(payload_name)
        if not isinstance(payload, Mapping):
            continue
        rows = payload.get("approved_facts") if payload_name == "pre_memo_fact_selection" else payload.get("supported_claims")
        for row in rows or []:
            if not isinstance(row, Mapping) or not _row_has_machine_evidence_ref(row):
                continue
            source_families = set(_string_list(row.get("source_families") or row.get("source_family")))
            if source_families and not (
                source_families & {"primary_sec_filing", "company_authored_unaudited_sec_filing"}
            ):
                continue
            for ticker in _row_tickers(row):
                covered.add(ticker)
    return covered


def _p30_focus_tickers(artifacts: Mapping[str, Any]) -> set[str]:
    json_payload = artifacts.get("json") if isinstance(artifacts.get("json"), Mapping) else {}
    p30 = json_payload.get("p30_root_cause_quality_audit")
    if not isinstance(p30, Mapping):
        return set()
    return {
        str(row.get("ticker") or "").upper().strip()
        for row in p30.get("focus_ticker_coverage_matrix") or []
        if isinstance(row, Mapping) and str(row.get("ticker") or "").strip()
    }


def _row_tickers(row: Mapping[str, Any]) -> set[str]:
    values: list[str] = []
    for key in ("ticker", "company", "ticker_scope", "tickers"):
        values.extend(_string_list(row.get(key)))
    return {value.upper().strip() for value in values if value.strip()}


def _row_has_machine_evidence_ref(row: Mapping[str, Any]) -> bool:
    for key in ("evidence_refs", "refs", "evidence_ref", "source_id", "source_fact_id", "line_item_id", "metric_id"):
        if _string_list(row.get(key)):
            return True
    return False


def _row_has_complete_parser_diagnosis(row: Mapping[str, Any]) -> bool:
    diagnosis = row.get("parser_diagnosis") if isinstance(row.get("parser_diagnosis"), Mapping) else {}
    complete = bool(row.get("parser_diagnosis_complete") or diagnosis.get("parser_diagnosis_complete"))
    failure_reason = str(
        row.get("exact_fact_parser_failure_reason")
        or row.get("parser_failure_reason")
        or "; ".join(_string_list(diagnosis.get("exact_fact_parser_failure_reasons")))
        or ""
    ).strip()
    next_action = str(row.get("next_parser_action") or "; ".join(_string_list(diagnosis.get("next_parser_actions"))) or "").strip()
    parser_status = str(
        row.get("source_specific_parser_status")
        or row.get("exact_value_parser_status")
        or "; ".join(_string_list(diagnosis.get("source_specific_parser_statuses")))
        or ""
    ).strip()
    return bool(complete and failure_reason and next_action and parser_status)


def _row_status_closed(row: Mapping[str, Any]) -> bool:
    status = str(row.get("status") or row.get("repair_status") or "").strip().lower()
    return status in {"closed", "resolved", "diagnosed", "parser_diagnosed", "non_blocking"}


def _walk_mappings(value: Any) -> list[Mapping[str, Any]]:
    rows: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        rows.append(value)
        for nested in value.values():
            rows.extend(_walk_mappings(nested))
    elif isinstance(value, list):
        for item in value:
            rows.extend(_walk_mappings(item))
    return rows


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return [str(value)]


def _supported_claim_count(claim_cards: Any, judgment: Any) -> int:
    cards = claim_cards if isinstance(claim_cards, Mapping) else {}
    supported = [row for row in cards.get("supported_claims") or [] if isinstance(row, Mapping)]
    if supported:
        return len(supported)
    judgment_map = judgment if isinstance(judgment, Mapping) else {}
    return len([row for row in judgment_map.get("supported_claims") or [] if isinstance(row, Mapping)])


def _approved_fact_count(fact_selection: Any) -> int:
    facts = fact_selection if isinstance(fact_selection, Mapping) else {}
    summary = facts.get("summary") if isinstance(facts.get("summary"), Mapping) else {}
    if summary.get("approved_fact_count") is not None:
        try:
            return int(summary.get("approved_fact_count") or 0)
        except (TypeError, ValueError):
            pass
    return len([row for row in facts.get("approved_facts") or [] if isinstance(row, Mapping)])


def _unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
